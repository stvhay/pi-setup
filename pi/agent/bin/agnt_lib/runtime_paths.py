from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

_KIND_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _kind_parts(kind: str) -> tuple[str, ...]:
    parts = tuple(kind.split("/"))
    if not parts or any(not _KIND_PART.fullmatch(part) for part in parts):
        raise ValueError("runtime kind must contain only safe relative path components")
    return parts


def _git(git: str, cwd: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [git, "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _git_context(cwd: Path) -> tuple[str, Path, str] | None:
    git = shutil.which("git")
    if not git:
        return None
    root_result = _git(git, cwd, ["rev-parse", "--show-toplevel"])
    if root_result.returncode != 0 or not root_result.stdout.strip():
        return None
    root = Path(root_result.stdout.strip()).resolve()
    common_result = _git(git, root, ["rev-parse", "--git-common-dir"])
    common = Path(common_result.stdout.strip()) if common_result.returncode == 0 and common_result.stdout.strip() else root
    if not common.is_absolute():
        common = root / common
    return git, root, f"git:{common.resolve()}"


def _has_symlink(root: Path, parts: Sequence[str]) -> bool:
    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _safe_project_candidate(git: str, root: Path, parts: Sequence[str]) -> Path | None:
    relative = Path(".pi", *parts)
    if _has_symlink(root, relative.parts):
        return None
    ignored = _git(
        git,
        root,
        ["check-ignore", "-q", "--no-index", "--", f"{relative.as_posix()}/"],
    )
    if ignored.returncode != 0:
        return None
    tracked = _git(
        git,
        root,
        ["ls-files", "--cached", "--", relative.as_posix(), f"{relative.as_posix()}/**"],
    )
    if tracked.returncode != 0 or tracked.stdout.strip():
        return None
    return root / relative


def _private_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise OSError("private runtime path is not a directory")
    path.chmod(0o700)
    return path


def _private_tree(root: Path, parts: Sequence[str]) -> Path:
    current = _private_directory(root)
    for part in parts:
        current = _private_directory(current / part)
    return current


def resolve_runtime_directories(
    kinds: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    global_root: str | os.PathLike[str] | None = None,
) -> tuple[Path, ...]:
    parts_by_kind = tuple(_kind_parts(kind) for kind in kinds)
    if not parts_by_kind:
        return ()
    start = Path(cwd or os.getcwd()).expanduser().resolve()
    context = _git_context(start)
    identity = context[2] if context else f"path:{start}"
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    runtime_root = Path(global_root).expanduser() if global_root is not None else Path.home() / ".pi" / "runtime"
    paths: list[Path] = []
    for parts in parts_by_kind:
        if context:
            candidate = _safe_project_candidate(context[0], context[1], parts)
            if candidate is not None:
                try:
                    paths.append(_private_directory(candidate))
                    continue
                except OSError:
                    pass
        paths.append(_private_tree(runtime_root, (key, *parts)))
    return tuple(paths)


def resolve_runtime_directory(
    kind: str,
    *,
    cwd: str | os.PathLike[str] | None = None,
    global_root: str | os.PathLike[str] | None = None,
) -> Path:
    return resolve_runtime_directories((kind,), cwd=cwd, global_root=global_root)[0]


def cmd_plans_dir(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt plans-dir", description="Print and create the active plans directory.")
    parser.parse_args(argv)
    override = os.environ.get("PI_PLANS_DIR")
    cwd = Path.cwd().resolve()
    context = _git_context(cwd)
    path = Path(override).expanduser() if override else (context[1] if context else cwd) / ".pi" / "plans"
    path.mkdir(parents=True, exist_ok=True)
    print(path)
    return 0


def cmd_runtime_path(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt runtime-path", description="Resolve safe private runtime directories.")
    parser.add_argument("kinds", nargs="+", help="relative artifact kinds, such as runs or metrics/invocations")
    args = parser.parse_args(argv)
    try:
        paths = resolve_runtime_directories(args.kinds)
    except (OSError, ValueError):
        print("agnt runtime-path: could not resolve private runtime directory", file=os.sys.stderr)
        return 2
    payload = {"path": str(paths[0])} if len(paths) == 1 else {
        "paths": {kind: str(path) for kind, path in zip(args.kinds, paths)},
    }
    print(json.dumps({"schemaVersion": 1, **payload}, sort_keys=True))
    return 0
