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


def test_node_test_runtime_is_pinned():
    manifest_path = ROOT / "package.json"
    lock_path = ROOT / "package-lock.json"
    assert manifest_path.is_file(), "Node-backed tests need a tracked package manifest"
    assert lock_path.is_file(), "Node-backed tests need a tracked dependency lock"

    manifest = json.loads(manifest_path.read_text())
    lock = json.loads(lock_path.read_text())
    assert manifest["private"] is True
    assert manifest["engines"]["node"] == ">=22.19.0 <23"
    assert manifest["devDependencies"]["@earendil-works/pi-coding-agent"] == "0.84.1"
    assert lock["packages"][""]["devDependencies"] == manifest["devDependencies"]
    nested = "node_modules/@earendil-works/pi-coding-agent/node_modules/"
    assert lock["packages"][nested + "undici"]["version"] == "8.9.0"
    assert lock["packages"][nested + "brace-expansion"]["version"] == "5.0.9"
    missing_integrity = [
        path
        for path, package in lock["packages"].items()
        if package.get("resolved", "").startswith("https://") and "integrity" not in package
    ]
    assert missing_integrity == []
    assert "nodejs_22" in (ROOT / "flake.nix").read_text()
    assert "node_modules/" in (ROOT / ".gitignore").read_text().splitlines()


def test_ci_installs_pinned_node_dependencies_before_tests():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    markers = (
        "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",  # v7.0.0
        "npm ci --ignore-scripts",
        "python -m pytest tests/",
    )
    for marker in markers:
        assert marker in workflow

    assert "node-version: '22.22.0'" in workflow
    assert [workflow.index(marker) for marker in markers] == sorted(workflow.index(marker) for marker in markers)


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

    before = (beads / "issues.jsonl").read_text(encoding="utf-8").splitlines()
    created = subprocess.run(
        ["bd", "create", "--title=auto export probe", "--description=isolated regression probe", "--type=task", "--priority=4", "--json"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    created_id = json.loads(created.stdout)["id"]
    after = [json.loads(line) for line in (beads / "issues.jsonl").read_text(encoding="utf-8").splitlines()]

    assert len(after) == len(before) + 1
    assert any(issue["id"] == created_id for issue in after)
