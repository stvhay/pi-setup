import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKED_BEADS_FILES = (
    ".gitignore",
    "README.md",
    "config.yaml",
    "issues.jsonl",
    "metadata.json",
)


def test_ci_installs_pinned_beads_before_tests():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    assert "BEADS_VERSION: 1.1.0" in workflow
    assert "beads_${BEADS_VERSION}_linux_amd64.tar.gz" in workflow


def test_fresh_checkout_bootstraps_tracked_beads(tmp_path):
    beads = tmp_path / ".beads"
    beads.mkdir(mode=0o700)
    for name in TRACKED_BEADS_FILES:
        shutil.copy2(ROOT / ".beads" / name, beads / name)

    plan = subprocess.run(
        ["bd", "bootstrap", "--dry-run", "--json"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(plan.stdout)["action"] == "jsonl-import"

    subprocess.run(
        ["bd", "bootstrap", "--yes"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["bd", "list", "--limit", "1", "--json"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert isinstance(json.loads(result.stdout), list)
