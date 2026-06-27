"""bootstrap-pi-config deploy safety guardrails."""

from __future__ import annotations

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
