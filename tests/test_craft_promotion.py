"""Promotion checks are offline and need no artcraft checkout or app process."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check-craft-promotion.py"
FILES = {
    "scripts/start-craft-mcp.sh": ("agent/bin/start-craft-mcp.sh", "0755"),
    "integration/crafting-apps/SKILL.md": ("agent/skills/crafting-apps/SKILL.md", "0644"),
    "integration/crafting-apps/vectorcraft.md": ("agent/skills/crafting-apps/vectorcraft.md", "0644"),
    "integration/craft-mcp.json": ("agent/craft/mcp.json", "0644"),
}


def fixture(root):
    manifest = {"repository": "artcraft-setup", "commit": "a" * 40, "files": {}}
    for source, (target, mode) in FILES.items():
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
        path.chmod(int(mode, 8))
        manifest["files"][source] = {"target": target, "mode": mode,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (root / "agent/craft/source.json").write_text(json.dumps(manifest))
    return manifest


def check(root):
    assert SCRIPT.is_file(), "promotion consistency checker missing"
    return subprocess.run([sys.executable, "-B", str(SCRIPT), str(root)],
                          capture_output=True, text=True, timeout=5)


def test_promotion_manifest_and_files_match(tmp_path):
    fixture(tmp_path)
    result = check(tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("drift", ["bytes", "mode", "symlink", "missing", "commit", "mapping", "extra"])
def test_promotion_refuses_drift(tmp_path, drift):
    manifest = fixture(tmp_path)
    path = tmp_path / "agent/bin/start-craft-mcp.sh"
    if drift == "bytes":
        path.write_text("changed")
    elif drift == "mode":
        path.chmod(0o644)
    elif drift == "symlink":
        path.unlink()
        path.symlink_to(tmp_path / "agent/craft/mcp.json")
    elif drift == "missing":
        path.unlink()
    elif drift == "commit":
        manifest["commit"] = "HEAD"
    elif drift == "mapping":
        manifest["files"]["scripts/start-craft-mcp.sh"]["target"] = "../escape"
    else:
        manifest["files"]["other"] = {}
    (tmp_path / "agent/craft/source.json").write_text(json.dumps(manifest))
    assert check(tmp_path).returncode != 0


def test_tracked_promotion():
    assert (ROOT / "pi/agent/craft/source.json").is_file(), "committed promotion missing"
    result = check(ROOT / "pi")
    assert result.returncode == 0, result.stderr


def load_reconciler():
    spec = importlib.util.spec_from_file_location("craft_reconciler", ROOT / "scripts/reconcile-craft-mcp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("failure", ["drift", "replace"])
def test_reconcile_retains_backup_on_failure(tmp_path, monkeypatch, failure):
    module = load_reconciler()
    source, dest = tmp_path / "source", tmp_path / ".pi"
    for root in (source, dest):
        (root / "agent/craft").mkdir(parents=True)
    (source / "agent/craft/mcp.json").write_text(json.dumps(module.TEMPLATE))
    (source / "agent/bin").mkdir()
    launcher = source / "agent/bin/start-craft-mcp.sh"
    launcher.write_text("#!/bin/sh\nexit 99\n")
    launcher.chmod(0o755)
    target = dest / "agent/mcp.json"
    old = b'{"mcpServers":{}}\n'
    target.write_bytes(old)
    if failure == "replace":
        def fail_replace(*args):
            raise OSError("fixture replace failure")
        monkeypatch.setattr(module.os, "replace", fail_replace)
    else:
        snapshot = module.snapshot
        calls = 0
        def changed_snapshot(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_bytes(b'{"human-change":true}')
            return snapshot(path)
        monkeypatch.setattr(module, "snapshot", changed_snapshot)
    with pytest.raises((ValueError, OSError)):
        module.reconcile(source, dest, apply=True)
    backups = list((dest / "runtime/deployment-backups").glob("craft-*/before.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == old
    receipt = json.loads((backups[0].parent / "receipt.json").read_text())
    assert receipt["verified"] is False
    assert target.read_bytes() == (old if failure == "replace" else b'{"human-change":true}')
    assert not list(target.parent.glob(".craft-mcp-*"))
