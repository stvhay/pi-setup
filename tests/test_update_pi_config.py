"""update-pi-config deploy safety guardrails."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update-pi-config.sh"


def run_update(dest: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PI_CONFIG_DEST"] = str(dest)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_update_refuses_home_destination_without_mutating(tmp_path):
    home_dest = Path.home()
    marker = home_dest / ".managed-by-pi-setup"
    before = marker.exists()

    proc = run_update(home_dest)

    assert proc.returncode == 1
    assert "Refusing unsafe PI_CONFIG_DEST" in proc.stderr
    assert marker.exists() is before


def test_update_refuses_non_pi_basename_before_creating_parent(tmp_path):
    dest = tmp_path / "nested" / "not-pi"

    proc = run_update(dest)

    assert proc.returncode == 1
    assert "destination basename must be .pi" in proc.stderr
    assert not dest.exists()
    assert not dest.parent.exists()


def test_update_preserves_pi_managed_mutable_state(tmp_path):
    dest = tmp_path / ".pi"
    agent = dest / "agent"
    agent.mkdir(parents=True)
    runtime_settings = {
        "lastChangelogVersion": "99.0.0",
        "runtimeOnly": "must not survive",
    }
    (agent / "settings.json").write_text(json.dumps(runtime_settings), encoding="utf-8")
    models_store = '{"openrouter":{"models":[{"id":"cached-model"}]}}\n'
    (agent / "models-store.json").write_text(models_store, encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    deployed_settings = json.loads((agent / "settings.json").read_text(encoding="utf-8"))
    source_settings = json.loads(
        (ROOT / "pi" / "agent" / "settings.json").read_text(encoding="utf-8")
    )
    assert deployed_settings["lastChangelogVersion"] == "99.0.0"
    assert deployed_settings["packages"] == source_settings["packages"]
    assert "runtimeOnly" not in deployed_settings
    assert (agent / "models-store.json").read_text(encoding="utf-8") == models_store


def test_update_preserves_langfuse_credentials(tmp_path):
    dest = tmp_path / ".pi"
    config = dest / "agent" / "pi-langfuse" / "config.json"
    config.parent.mkdir(parents=True)
    credentials = '{"publicKey":"pk-test","secretKey":"sk-test"}\n'
    config.write_text(credentials, encoding="utf-8")

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert config.read_text(encoding="utf-8") == credentials


def test_update_dry_run_excludes_models_store(tmp_path):
    proc = run_update(tmp_path / ".pi", "--dry-run")

    assert proc.returncode == 0, proc.stderr
    assert "--exclude=agent/models-store.json" in proc.stdout


def test_update_rejects_apply_flag(tmp_path):
    proc = run_update(tmp_path / ".pi", "--apply")

    assert proc.returncode == 2
    assert "Unknown argument: --apply" in proc.stderr


def test_update_removes_stale_python_cache(tmp_path):
    dest = tmp_path / ".pi"
    stale = dest / "agent" / "skills" / "stale-skill" / "tools" / "__pycache__"
    stale.mkdir(parents=True)
    (stale / "tool.cpython-313.pyc").touch()

    proc = run_update(dest)

    assert proc.returncode == 0, proc.stderr
    assert "cannot delete non-empty directory" not in proc.stdout + proc.stderr
    assert not stale.parent.parent.exists()


def test_tracked_settings_omit_pi_managed_changelog_version():
    settings = json.loads(
        (ROOT / "pi" / "agent" / "settings.json").read_text(encoding="utf-8")
    )

    assert "lastChangelogVersion" not in settings
