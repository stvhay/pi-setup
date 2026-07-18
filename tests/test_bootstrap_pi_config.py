"""bootstrap-pi-config deploy safety guardrails."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap-pi-config.sh"


def run_bootstrap(dest: Path, mode: str = "--dry-run") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PI_CONFIG_DEST"] = str(dest)
    return subprocess.run(
        ["bash", str(SCRIPT), mode],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_bootstrap_refuses_home_destination_without_mutating(tmp_path):
    home_dest = Path.home()
    marker = home_dest / ".managed-by-pi-setup"
    before = marker.exists()

    proc = run_bootstrap(home_dest)

    assert proc.returncode == 1
    assert "Refusing unsafe PI_CONFIG_DEST" in proc.stderr
    assert marker.exists() is before


def test_bootstrap_refuses_non_pi_basename_before_creating_parent(tmp_path):
    dest = tmp_path / "nested" / "not-pi"

    proc = run_bootstrap(dest, "--apply")

    assert proc.returncode == 1
    assert "destination basename must be .pi" in proc.stderr
    assert not dest.exists()
    assert not dest.parent.exists()


def test_bootstrap_preserves_pi_managed_mutable_state(tmp_path):
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

    proc = run_bootstrap(dest, "--apply")

    assert proc.returncode == 0, proc.stderr
    deployed_settings = json.loads((agent / "settings.json").read_text(encoding="utf-8"))
    source_settings = json.loads(
        (ROOT / "pi" / "agent" / "settings.json").read_text(encoding="utf-8")
    )
    assert deployed_settings["lastChangelogVersion"] == "99.0.0"
    assert deployed_settings["packages"] == source_settings["packages"]
    assert "runtimeOnly" not in deployed_settings
    assert (agent / "models-store.json").read_text(encoding="utf-8") == models_store


def test_bootstrap_dry_run_excludes_models_store(tmp_path):
    proc = run_bootstrap(tmp_path / ".pi")

    assert proc.returncode == 0, proc.stderr
    assert "--exclude=agent/models-store.json" in proc.stdout


def test_tracked_settings_omit_pi_managed_changelog_version():
    settings = json.loads(
        (ROOT / "pi" / "agent" / "settings.json").read_text(encoding="utf-8")
    )

    assert "lastChangelogVersion" not in settings
