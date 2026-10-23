"""Filesystem gates; real locked npm/package proof lives in the release verifier."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/install-pi-langfuse-runtime.py"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encoded(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()


@pytest.fixture
def delivery():
    assert SCRIPT.is_file(), "isolated runtime installer is missing"
    spec = importlib.util.spec_from_file_location("langfuse_runtime_delivery", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / "bundle"
    source.mkdir()
    contents = {"index.js": b"export default () => {};\n", "package.json": b'{"name":"pi-langfuse","version":"1.7.0"}\n'}
    dependency = b'{"name":"fixture-dependency","version":"1.0.0"}\n'
    for name, data in contents.items():
        (source / name).write_bytes(data)
    payload = {"inputs": {"index.ts": digest(b"source")}, "files": {name: digest(data) for name, data in sorted(contents.items())},
               "dependencies": {"fixture-dependency/package.json": digest(dependency)}}
    proof = {"schemaVersion": 1, "id": digest(encoded(payload)), "toolchain": {"npm": "12.2.1"}, **payload}
    (source / "release.json").write_text(json.dumps(proof, indent=2) + "\n")
    return source, proof, dependency


def installed_copy(source, release, dependency):
    release.mkdir(parents=True)
    for path in source.iterdir():
        (release / path.name).write_bytes(path.read_bytes())
    package = release / "node_modules/fixture-dependency/package.json"
    package.parent.mkdir(parents=True)
    package.write_bytes(dependency)


def test_dry_run_is_read_only_and_names_exact_release(delivery, bundle, tmp_path):
    source, proof, _ = bundle
    dest = tmp_path / ".pi"
    result = delivery.install(source, dest, npm_cli=None, dry_run=True)
    assert result["status"] == "would-install"
    assert result["release"] == str(dest / "runtime/pi-langfuse/releases" / proof["id"])
    assert not dest.exists()


def test_reuse_verifies_all_bytes_without_npm_or_other_writes(delivery, bundle, tmp_path):
    source, proof, dependency = bundle
    dest = tmp_path / ".pi"
    release = dest / "runtime/pi-langfuse/releases" / proof["id"]
    installed_copy(source, release, dependency)
    before = {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in release.rglob("*")}
    assert delivery.install(source, dest, npm_cli=None)["status"] == "verified-existing"
    assert before == {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in release.rglob("*")}
    assert not (dest / "runtime/pi-langfuse/.install.lock").exists()


@pytest.mark.parametrize("kind", ["code", "dependency", "extra", "symlink", "receipt"])
def test_corrupt_reuse_fails_closed_without_repair(delivery, bundle, tmp_path, kind):
    source, proof, dependency = bundle
    dest = tmp_path / ".pi"
    release = dest / "runtime/pi-langfuse/releases" / proof["id"]
    installed_copy(source, release, dependency)
    path = release / {"code": "index.js", "dependency": "node_modules/fixture-dependency/package.json", "extra": "node_modules/unlocked.js", "receipt": "release.json", "symlink": "foreign"}[kind]
    if kind == "symlink":
        path.symlink_to(source, target_is_directory=True)
    else:
        path.write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="mismatch|symlink"):
        delivery.install(source, dest, npm_cli=None)
    assert path.is_symlink() or path.read_bytes() == b"unexpected"


@pytest.mark.parametrize("part", ["runtime", "runtime/pi-langfuse", "runtime/pi-langfuse/releases"])
def test_destination_symlink_is_refused_before_writes(delivery, bundle, tmp_path, part):
    source, _, _ = bundle
    dest = tmp_path / ".pi"
    outside = tmp_path / "outside"
    outside.mkdir()
    link = dest / part
    link.parent.mkdir(parents=True)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        delivery.install(source, dest, npm_cli=None, dry_run=True)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("kind", ["id", "extra", "file", "traversal", "symlink", "duplicate-key"])
def test_bundle_validation_before_any_destination_write(delivery, bundle, tmp_path, kind):
    source, proof, _ = bundle
    if kind == "id":
        proof["id"] = "0" * 64
    elif kind == "extra":
        (source / "unowned").write_text("extra")
    elif kind == "file":
        (source / "index.js").write_text("changed")
    elif kind == "traversal":
        proof["files"]["../escape"] = "0" * 64
    elif kind == "symlink":
        (source / "foreign").symlink_to(tmp_path)
    else:
        (source / "release.json").write_text('{"schemaVersion":1,"schemaVersion":1}')
    if kind in {"id", "traversal"}:
        (source / "release.json").write_text(json.dumps(proof))
    dest = tmp_path / ".pi"
    with pytest.raises(ValueError):
        delivery.install(source, dest, npm_cli=None)
    assert not dest.exists()


def test_failed_install_retains_stage_but_never_activates(delivery, bundle, tmp_path, monkeypatch):
    source, proof, _ = bundle
    dest = tmp_path / ".pi"

    def fail_install(*args, **kwargs):
        raise RuntimeError("simulated install failure")

    monkeypatch.setattr(delivery, "install_dependencies", fail_install)
    with pytest.raises(RuntimeError, match="simulated"):
        delivery.install(source, dest, npm_cli=Path("explicit-npm-cli"))
    releases = dest / "runtime/pi-langfuse/releases"
    assert not (releases / proof["id"]).exists()
    assert len(list(releases.glob(".stage-*"))) == 1
    assert not (dest / "agent/settings.json").exists()


def test_verified_install_preserves_shared_npm_and_config(delivery, bundle, tmp_path, monkeypatch):
    source, proof, dependency = bundle
    dest = tmp_path / ".pi"
    shared = dest / "agent/npm/node_modules/unrelated/sentinel"
    shared.parent.mkdir(parents=True)
    shared.write_bytes(b"unchanged")
    settings = dest / "agent/settings.json"
    settings.write_bytes(b"settings unchanged")

    def fake_install(stage, npm_cli):
        path = stage / "node_modules/fixture-dependency/package.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(dependency)

    monkeypatch.setattr(delivery, "install_dependencies", fake_install)
    result = delivery.install(source, dest, npm_cli=Path("explicit-npm-cli"))
    assert result["status"] == "installed"
    assert result["release"].endswith(proof["id"])
    assert shared.read_bytes() == b"unchanged"
    assert settings.read_bytes() == b"settings unchanged"
    assert delivery.install(source, dest, npm_cli=None)["status"] == "verified-existing"
