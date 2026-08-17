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

    assert "BEADS_VERSION: 1.2.2" in workflow
    assert "BEADS_LINUX_AMD64_SHA256: 8140098a51d3b81d5548d1c5e6db1a2d9930e5d141efe2a4bff7d079c4d321e8" in workflow
    assert "beads_${BEADS_VERSION}_linux_amd64.tar.gz" in workflow
    assert "tar -xzf /tmp/beads.tar.gz -C /tmp ./bd" in workflow
    assert 'test "$(bd version | awk' in workflow
    assert "bd comments --help" in workflow
    assert "bd provenance --help" in workflow


def test_beads_config_keeps_mutations_versioned():
    config = (ROOT / ".beads/config.yaml").read_text()

    assert "dolt.auto-commit: on" in config


def test_node_test_runtime_is_pinned():
    manifest_path = ROOT / "package.json"
    lock_path = ROOT / "package-lock.json"
    assert manifest_path.is_file(), "Node-backed tests need a tracked package manifest"
    assert lock_path.is_file(), "Node-backed tests need a tracked dependency lock"

    manifest = json.loads(manifest_path.read_text())
    lock = json.loads(lock_path.read_text())
    assert manifest["private"] is True
    assert manifest["engines"]["node"] == ">=24 <25"
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
    assert "nodejs_24" in (ROOT / "flake.nix").read_text()
    assert "node_modules/" in (ROOT / ".gitignore").read_text().splitlines()


def test_checkout_local_artifacts_are_ignored_without_hiding_durable_skill_evals():
    ignored_paths = (
        ".beads.gate.lock",
        ".pi/deploy-previews/example/evidence.txt",
        ".pi/skill-evals/runtime-package-patch-projection/candidate-output.jsonl",
    )
    for path in ignored_paths:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", "--", path],
            cwd=ROOT,
        )
        assert ignored.returncode == 0, f"local artifact must be ignored: {path}"

    durable_eval = subprocess.run(
        [
            "git",
            "check-ignore",
            "-q",
            "--no-index",
            "--",
            ".pi/skill-evals/skill-creator/scenarios/example.md",
        ],
        cwd=ROOT,
    )
    assert durable_eval.returncode == 1


def test_ci_installs_pinned_node_dependencies_before_tests():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    markers = (
        "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",  # v7.0.0
        "npm ci --ignore-scripts",
        "python -m pytest tests/",
    )
    for marker in markers:
        assert marker in workflow

    assert "node-version: '24'" in workflow
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
