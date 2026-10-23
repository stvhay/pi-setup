#!/usr/bin/env python3
"""Prepare/verify one immutable Langfuse release; never activate or prune it.

Input is the maintained fork's deterministic runtime-release build. Deployment
owns settings activation and legacy shared-root migration as separate gates.
No default destination: callers must resolve and approve the target explicitly.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile

HASH = re.compile(r"[0-9a-f]{64}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def safe_relative(path: str) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and "\\" not in path
        and "\x00" not in path
        and not path.startswith("/")
        and all(part not in {"", ".", ".."} for part in path.split("/"))
        and str(PurePosixPath(path)) == path
    )


def reject_symlink(path: Path) -> None:
    # Reject aliases, including ancestor components, before touching a target.
    for current in [*reversed(path.parents), path]:
        if current.is_symlink():
            raise ValueError(f"symlink refused: {current}")
        if current.exists() and current != path and not current.is_dir():
            raise ValueError(f"non-directory parent: {current}")


def inventory(root: Path) -> dict[str, str]:
    reject_symlink(root)
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory, name)
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"symlink refused: {path}")
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ValueError(f"non-regular file refused: {path}")
            result[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return dict(sorted(result.items()))


def load_bundle(bundle: Path) -> tuple[dict, bytes]:
    reject_symlink(bundle)
    raw = (bundle / "release.json").read_bytes()
    proof = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(proof, dict) or proof.get("schemaVersion") != 1:
        raise ValueError("unsupported release descriptor")
    for key in ("inputs", "files", "dependencies"):
        values = proof.get(key)
        if not isinstance(values, dict) or not values:
            raise ValueError(f"missing release {key}")
        if any(not safe_relative(path) or not isinstance(value, str) or not HASH.fullmatch(value)
               for path, value in values.items()):
            raise ValueError(f"invalid release {key}")
    if "release.json" in proof["files"] or any(path.startswith("node_modules/") for path in proof["files"]):
        raise ValueError("reserved release path")
    payload = {key: proof[key] for key in ("inputs", "files", "dependencies")}
    expected_id = digest(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    if proof.get("id") != expected_id:
        raise ValueError("release identity mismatch")
    if proof.get("toolchain", {}).get("npm") != "12.2.1":
        raise ValueError("unsupported npm toolchain")
    expected = {**proof["files"], "release.json": digest(raw)}
    if inventory(bundle) != expected:
        raise ValueError("bundle file inventory mismatch")
    return proof, raw


def verify_release(release: Path, proof: dict, raw: bytes) -> None:
    expected = {**proof["files"], "release.json": digest(raw),
                **{f"node_modules/{path}": value for path, value in proof["dependencies"].items()}}
    if inventory(release) != expected:
        raise ValueError(f"release inventory mismatch (no repair attempted): {release}")


def install_dependencies(stage: Path, npm_cli: Path) -> None:
    # No provider/telemetry credentials, NODE_OPTIONS or npm config injection.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "SystemRoot") if key in os.environ}
    command = ["node", str(npm_cli)]
    version = subprocess.run([*command, "--version"], check=True, capture_output=True,
                             text=True, env=env, timeout=30).stdout.strip()
    if version != "12.2.1":
        raise ValueError("pinned npm 12.2.1 required")
    # npm refuses loading /dev/null twice under different config roles. Use
    # distinct absent paths in an owned private directory; never read home config.
    config_dir = Path(tempfile.mkdtemp(prefix=".npm-config-", dir=stage.parent))
    flags = [f"--userconfig={config_dir / 'user'}", f"--globalconfig={config_dir / 'global'}"]
    subprocess.run([*command, "ci", "--ignore-scripts", "--strict-peer-deps", "--omit=dev",
                    "--engine-strict", "--install-links=true", "--bin-links=false", "--no-audit", "--no-fund", *flags],
                   cwd=stage, env=env, check=True, timeout=180, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run([*command, "ls", "--all", "--json", *flags], cwd=stage, env=env,
                   check=True, timeout=30, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def install(bundle: Path, dest: Path, npm_cli: Path | None, *, dry_run: bool = False, check: bool = False) -> dict:
    bundle, dest = Path(bundle).absolute(), Path(dest).absolute()
    if ".." in bundle.parts or ".." in dest.parts:
        raise ValueError("noncanonical path refused")
    proof, raw = load_bundle(bundle)
    base = dest / "runtime/pi-langfuse"
    releases = base / "releases"
    release = releases / proof["id"]
    reject_symlink(release)
    result = {"id": proof["id"], "release": str(release)}
    if release.exists():
        verify_release(release, proof, raw)
        return {**result, "status": "verified-existing"}
    if check:
        raise ValueError(f"release missing: {release}")
    if dry_run:
        return {**result, "status": "would-install"}
    if npm_cli is None:
        raise ValueError("--npm-cli is required for installation")
    releases.mkdir(parents=True, exist_ok=True)
    lock_path = base / ".install.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reject_symlink(release)
        if release.exists():
            verify_release(release, proof, raw)
            return {**result, "status": "verified-existing"}
        stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=releases))
        # Keep failed stages for diagnosis. Neither partial source nor partial
        # dependencies can become the exact content-addressed activation target.
        for name in [*proof["files"], "release.json"]:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle / name, target)
        copied_proof, copied_raw = load_bundle(stage)
        if copied_proof != proof or copied_raw != raw:
            raise ValueError("bundle changed while staging")
        install_dependencies(stage, Path(npm_cli).absolute())
        verify_release(stage, proof, raw)
        # Recheck original inputs and destination identity before promotion.
        latest, latest_raw = load_bundle(bundle)
        if latest != proof or latest_raw != raw:
            raise ValueError("bundle changed during installation")
        reject_symlink(release)
        if release.exists():
            raise ValueError("release appeared concurrently; stage retained")
        os.rename(stage, release)
        verify_release(release, proof, raw)
    return {**result, "status": "installed"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--npm-cli", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        result = install(args.bundle, args.dest, args.npm_cli, dry_run=args.dry_run, check=args.check)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Subprocess errors deliberately omit stdout/stderr (no package/server
        # text or environment values enter the deployment diagnostic).
        parser.exit(1, f"Langfuse release preparation failed: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
