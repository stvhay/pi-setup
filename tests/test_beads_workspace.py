import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_work_continuation import runtime  # noqa: F401


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

    assert "BEADS_VERSION: 1.3.1" in workflow
    assert "BEADS_LINUX_AMD64_SHA256: 3219443a9734b89b93fb16ee8d65844759fa1b3cd3cf139c606b7353cfb0715c" in workflow
    assert "beads_${BEADS_VERSION}_linux_amd64.tar.gz" in workflow
    assert "tar -xzf /tmp/beads.tar.gz -C /tmp bd" in workflow
    assert 'test "$(bd version | awk' in workflow
    assert "bd comments --help" in workflow
    assert "          bd provenance --help >/dev/null" in workflow
    assert "unexpected v65-only" not in workflow
    assert "1.3.1" in (ROOT / ".beads/README.md").read_text()


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
    assert manifest["devDependencies"]["@earendil-works/pi-coding-agent"] == "1.4.0"
    assert lock["packages"][""]["devDependencies"] == manifest["devDependencies"]
    assert lock["packages"]["node_modules/undici"]["version"] == "8.10.2"
    assert lock["packages"]["node_modules/brace-expansion"]["version"] == "5.0.12"
    missing_integrity = [
        path
        for path, package in lock["packages"].items()
        if package.get("resolved", "").startswith("https://") and "integrity" not in package
    ]
    assert missing_integrity == []
    assert "nodejs_24" in (ROOT / "flake.nix").read_text()
    assert "node_modules/" in (ROOT / ".gitignore").read_text().splitlines()


def test_nix_npm_matches_runtime_delivery_toolchain():
    manifest = json.loads((ROOT / "patches/pi-packages/langfuse-runtime/package.json").read_text())
    version = manifest["packageManager"].removeprefix("npm@")
    flake = (ROOT / "flake.nix").read_text()

    assert f'version = "{version}";' in flake
    assert 'url = "https://registry.npmjs.org/npm/-/npm-${version}.tgz";' in flake
    assert 'hash = "sha512-' in flake
    assert "npm-toolchain =" in flake


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
    subprocess.run(
        ["bd", "export", "--readonly", "-o", str(beads / "issues.jsonl")],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    after = [json.loads(line) for line in (beads / "issues.jsonl").read_text(encoding="utf-8").splitlines()]

    assert len(after) == len(before) + 1
    assert any(issue["id"] == created_id for issue in after)


@pytest.mark.parametrize("shared_checkout", [False, True])
@pytest.mark.parametrize("audit_enabled", [False, True])
def test_real_beads_start_closeout_handoff_and_export(agnt, monkeypatch, tmp_path, capsys, audit_enabled, shared_checkout):
    for key in list(os.environ):
        if key.startswith(("BD_", "BEADS_", "GIT_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("BD_AUDIT_ENABLED", "1" if audit_enabled else "0")
    monkeypatch.setenv("BD_ACTOR", "lifecycle-tester")
    monkeypatch.setenv("BD_EXPORT_AUTO", "false")
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)

    def run(*args):
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout

    def bd(*args):
        return json.loads(run("bd", *args, "--json"))

    assert bd("version")["version"] == "1.3.1"
    run("git", "init", "-q")
    run("git", "config", "user.name", "Lifecycle Test")
    run("git", "config", "user.email", "test@example.invalid")
    run("bd", "init", "--prefix", "probe", "--skip-agents", "--skip-hooks", "--non-interactive")
    first = bd("create", "--title", "First", "--type", "task")["id"]
    second = bd("create", "--title", "Second", "--type", "task")["id"]
    bd("update", first, "--claim")
    bd("update", first, "--status", "open")
    audit = repo / ".beads/interactions.jsonl"
    legacy = audit.read_bytes() if audit.exists() else b""
    if audit_enabled:
        assert json.loads(legacy)["extra"]["new_value"] == "open"
        run("git", "add", "-f", ".beads/interactions.jsonl")
    else:
        assert not legacy
    portable = repo / ".beads/issues.jsonl"
    run("bd", "export", "--readonly", "-o", str(portable))
    rows = {row["id"]: row for row in map(json.loads, portable.read_text().splitlines())}
    assert rows[first]["status"] == "open" and rows[second]["status"] == "open"
    run("git", "add", ".beads")
    run("git", "commit", "-qm", "portable baseline")

    quality = sys.modules["agnt_lib.quality"]
    improvement = sys.modules["agnt_lib.improvement"]
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda _kind, **_kwargs: tmp_path / "quality")
    monkeypatch.setattr(improvement, "_best_effort_projection", lambda summary, _project: summary)
    monkeypatch.setenv("PI_SESSION_ID", "fresh-first")
    assert agnt.handoff_check(first, session_id="unassigned")["status"] == "ready"
    assert agnt.direct_start(first, claim=True)["status"] == "started"
    assert agnt.direct_start(first, claim=True)["status"] == "started"
    # A known foreign claim must not become a local session link.
    monkeypatch.setenv("BD_ACTOR", "foreign-actor")
    monkeypatch.setenv("PI_SESSION_ID", "foreign-session")
    # New lifecycle ownership guard rejects before invoking native claim.
    assert agnt.direct_start(first, claim=True)["stages"]["claim"] == {
        "status": "skipped", "reason": "session-conflict",
    }
    assert quality.session_work_item("foreign-session") is None
    # Preserve coverage that native CAS independently rejects a foreign actor.
    foreign_claim = subprocess.run(["bd", "update", first, "--claim", "--json"], capture_output=True, text=True)
    assert foreign_claim.returncode != 0
    monkeypatch.setenv("BD_ACTOR", "lifecycle-tester")
    from agnt_lib.work_lifecycle import runtime_store
    if shared_checkout:
        monkeypatch.setenv("PI_SESSION_ID", "fresh-second")
        assert agnt.direct_start(second, claim=True)["status"] == "started"
        second_owner = runtime_store().owner(second)
    def resume(bead, session):
        from agnt_lib.work_lifecycle import checkpoint_current
        monkeypatch.setenv("PI_SESSION_ID", session)
        source = tmp_path / f"{session}.jsonl"
        header = json.dumps({"type": "session", "id": session, "cwd": str(repo)}) + "\n"
        source.write_text(header)
        monkeypatch.setenv("PI_SESSION_FILE", str(source))
        cp = checkpoint_current(bead)["checkpoint"]
        assert agnt.main(["work", "transition-prepare", bead, "--mode", "resume", "--session-id", session,
                          "--checkpoint-ref", cp["id"], "--runtime-ready"]) == 0
        tx = json.loads(capsys.readouterr().out)["transition"]
        child = Path(tx["childSessionFile"])
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(json.dumps({"type": "session", "id": tx["childSession"], "cwd": str(repo),
                                     "parentSession": str(source)}) + "\n")
        assert agnt.main(["work", "transition-stage", tx["id"], "--session-id", session]) == 0
        capsys.readouterr()
        monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
        monkeypatch.setenv("PI_SESSION_FILE", str(child))
        assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
        capsys.readouterr()
        assert source.read_text() == header
        assert quality.session_attempt_state(session) == {"beadId": bead, "outcome": None}
        return tx["childSession"]

    monkeypatch.setenv("PI_SESSION_ID", "fresh-first")
    if shared_checkout:
        resume(first, "fresh-first")
    assert agnt.direct_closeout(first, outcome="success", reason="Verified.")["status"] == "closed"
    rows = {row["id"]: row for row in map(json.loads, portable.read_text().splitlines())}
    canonical = bd("show", first)[0]
    for field in ("status", "closed_at", "close_reason"):
        assert rows[first][field] == canonical[field]
    if audit_enabled:
        assert audit.read_bytes().startswith(legacy)
        assert len(audit.read_text().splitlines()) == 2
    if shared_checkout:
        assert runtime_store().owner(second) == second_owner
        assert bd("show", second)[0]["status"] == "in_progress"
        assert quality.session_attempt_state("fresh-second")["outcome"] is None
    else:
        assert agnt.handoff_check(second, session_id="fresh-first")["status"] == "ready"
    monkeypatch.delenv("PI_SESSION_FILE", raising=False)
    monkeypatch.setenv("PI_SESSION_ID", "fresh-second")
    if shared_checkout:
        resume(second, "fresh-second")
    assert agnt.direct_start(second, claim=True)["status"] == "started"
    assert agnt.direct_closeout(second, outcome="success", reason="Verified second.")["status"] == "closed"
    assert run("git", "status", "--porcelain", "--untracked-files=no") == ""


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "work-transition", "repo-write", "git-commit"]}], indirect=True)
def test_native_terminal_departure_preserves_cancelled_source(agnt, runtime, monkeypatch, capsys, isolated):
    from test_work_continuation import checkpoint, prepare, stage
    for key in list(os.environ):
        if key.startswith(("BD_", "BEADS_", "GIT_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("BD_EXPORT_AUTO", "false")
    monkeypatch.setenv("BD_AUDIT_ENABLED", "0")
    monkeypatch.setenv("BD_ACTOR", "terminal-fixture")
    def run(*args, cwd=None):
        result = subprocess.run(args, cwd=cwd or runtime["repo"], check=True, capture_output=True, text=True)
        return result.stdout
    def native(args):
        result = subprocess.run(["bd", *args, "--json"], check=False, capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout) if result.returncode == 0 else None, result.stderr
    run("bd", "init", "--prefix", "pi", "--skip-agents", "--skip-hooks", "--non-interactive")
    for bead in ("pi-a", "pi-b"):
        run("bd", "create", "--id", bead, "--title", bead, "--type", "task")
    run("bd", "export", "--readonly", "-o", str(runtime["repo"] / ".beads/issues.jsonl"))
    run("git", "add", ".beads")
    run("git", "commit", "-qm", "native terminal fixture")
    run("git", "checkout", "--detach", run("git", "rev-parse", "HEAD").strip(), cwd=runtime["other"])
    monkeypatch.setattr(runtime["work"], "run_beads_json", native)
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    runtime["quality"].capture_session_outcome("session-a", "pi-a", "partial", beads_runner=native)
    run("bd", "close", "pi-a", "--reason", "Wontfix: cancelled fixture")
    cancelled = native(["show", "pi-a"])[1][0]
    if isolated:
        (runtime["repo"] / "unfinished.txt").write_text("preserve cancelled work")
    cp = checkpoint(agnt, runtime, capsys)
    target = runtime["other"] if isolated else runtime["repo"]
    tx = prepare(agnt, runtime, cp, capsys, target="pi-b", checkout=target)
    stage(agnt, tx, capsys)
    monkeypatch.chdir(target)
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
    capsys.readouterr()
    assert runtime["work"].direct_closeout("pi-b", outcome="success", reason="Verified next work")["status"] == "closed"
    assert runtime["store"].owner("pi-a")["phase"] == "completed"
    assert runtime["quality"].session_attempt_state("session-a") == {"beadId": "pi-a", "outcome": "partial"}
    current = native(["show", "pi-a"])[1][0]
    assert all(current[key] == cancelled[key] for key in ("status", "closed_at", "close_reason"))
    if isolated:
        assert (runtime["repo"] / "unfinished.txt").read_text() == "preserve cancelled work"


def test_project_init_requires_tested_lifecycle_profile():
    skill = ROOT / "pi/agent/skills/project-init"
    assert "Read `references/audit-checklist.md`, including the Beads/Pi lifecycle profile" in (skill / "SKILL.md").read_text()
    checklist = (skill / "references/audit-checklist.md").read_text()
    for marker in ("1.3.1", "bd version --json", "agnt work direct-start", "agnt work direct-closeout",
                   "bd export --readonly", "audit.enabled", "embedded_unsupported", "origin-owner"):
        assert marker in checklist
