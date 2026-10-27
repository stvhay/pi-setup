"""Direct closeout must not widen the current assignment's effect ceiling."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_work_continuation import runtime  # noqa: F401


def prepare_closeout(runtime, monkeypatch):
    repo = runtime["repo"]
    portable = repo / ".beads" / "issues.jsonl"
    portable.parent.mkdir()
    portable.write_text(json.dumps({"id": "pi-a", "status": "open"}) + "\n")
    subprocess.run(["git", "add", ".beads/issues.jsonl"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "fixture portable state"], cwd=repo, check=True, capture_output=True)
    for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid")):
        subprocess.run(["git", "config", key, value], cwd=repo, check=True, capture_output=True)
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    # Baseline must not invoke a real exporter after its unauthorized close.
    monkeypatch.setattr(runtime["work"], "beads_bin", lambda: None)
    return portable


@pytest.mark.parametrize("runtime", [
    {"effects": ["repo-write", "git-commit"]},
    {"effects": ["beads-write", "repo-write"]},
    {"effects": ["beads-write", "git-commit"]},
], indirect=True)
def test_closeout_denies_missing_effect_before_outcome_or_native_write(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    before = portable.read_bytes()
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert portable.read_bytes() == before
    assert result["stages"]["authority"]["status"] == "failed"
    assert result["repair"]["safeToRetry"] is False


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_closeout_rechecks_scope_before_native_close(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    original = runtime["work"].record_current_session_outcome
    def record(*args):
        result = original(*args)
        runtime["permission"].revoke("stop before native close")
        return result
    monkeypatch.setattr(runtime["work"], "record_current_session_outcome", record)
    before = portable.read_bytes()
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert portable.read_bytes() == before
    assert result["stages"]["authority"]["status"] == "failed"
    assert result["stages"]["outcome"]["status"] == "succeeded"
    assert result["repair"]["safeToRetry"] is False


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_closeout_stops_export_after_revocation(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    monkeypatch.setattr(runtime["work"], "beads_bin", lambda: str(runtime["root"] / "must-not-run"))
    original = runtime["work"].run_beads_json
    def close(args):
        result = original(args)
        if args[0] == "close":
            runtime["permission"].revoke("stop after close")
        return result
    monkeypatch.setattr(runtime["work"], "run_beads_json", close)
    before = portable.read_bytes()
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert result["stages"]["close"]["status"] == "succeeded"
    assert result["stages"]["authority"]["status"] == "failed"
    assert portable.read_bytes() == before
    assert result["repair"]["safeToRetry"] is False


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_closeout_rejects_redirected_portable_directory_before_success(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    foreign = runtime["root"] / "foreign-portable"
    portable.parent.rename(foreign)
    portable.parent.symlink_to(foreign, target_is_directory=True)
    runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])


@pytest.mark.parametrize("change", ["pending-dependency", "closed-elsewhere"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_changed_canonical_work_cannot_be_finalized(runtime, monkeypatch, change):
    prepare_closeout(runtime, monkeypatch)
    if change == "pending-dependency":
        runtime["beads"]["pi-a"]["dependencies"] = [{"depends_on_id": "pi-b", "dependency_type": "blocks"}]
    else:
        runtime["beads"]["pi-a"].update(status="closed", close_reason="cancelled externally")
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert result["stages"]["authority"]["status"] == "failed"


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_portable_replace_cannot_follow_foreign_namespace_after_guard(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    closeout_backend(runtime, monkeypatch)
    foreign = runtime["root"] / "foreign-portable"
    foreign.mkdir()
    sentinel = b"unrelated foreign state\n"
    (foreign / "issues.jsonl").write_bytes(sentinel)
    original_replace = runtime["work"].os.replace
    swapped = False
    def replace(source, destination, **kwargs):
        nonlocal swapped
        if Path(destination).name == "issues.jsonl" and not swapped:
            swapped = True
            original_source = Path(source) if Path(source).is_absolute() else portable.parent / source
            shutil.copyfile(original_source, foreign / Path(source).name)
            portable.parent.rename(runtime["repo"] / "saved-beads")
            portable.parent.symlink_to(foreign, target_is_directory=True)
        return original_replace(source, destination, **kwargs)
    monkeypatch.setattr(runtime["work"].os, "replace", replace)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert swapped
    assert (foreign / "issues.jsonl").read_bytes() == sentinel
    assert result["status"] == "partial"


def closeout_backend(runtime, monkeypatch):
    row = {**runtime["beads"]["pi-a"], "status": "closed",
           "closed_at": "2026-10-20T00:00:00Z", "close_reason": "fixture complete"}
    exporter = runtime["root"] / "fixture-exporter"
    exporter.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        f"sys.stdout.write({(json.dumps(row) + chr(10))!r})\n"
    )
    exporter.chmod(0o755)
    monkeypatch.setattr(runtime["work"], "beads_bin", lambda: str(exporter))
    original = runtime["work"].run_beads_json
    def runner(args):
        if args[0] == "close":
            runtime["beads"]["pi-a"].update(row)
        return original(args)
    monkeypatch.setattr(runtime["work"], "run_beads_json", runner)
    return exporter


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_captured_local_scope_completes_closeout(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    closeout_backend(runtime, monkeypatch)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "closed"
    assert result["commit"]
    assert json.loads(portable.read_text())["status"] == "closed"
    assert runtime["store"].owner("pi-a")["phase"] == "completed"


@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_later_portable_dirt_does_not_relabel_verified_closeout(runtime, monkeypatch):
    portable = prepare_closeout(runtime, monkeypatch)
    closeout_backend(runtime, monkeypatch)
    assert runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")["status"] == "closed"
    with portable.open("a") as stream:
        stream.write(json.dumps(runtime["beads"]["pi-b"]) + "\n")
    before = portable.read_bytes()
    result = runtime["work"].handoff_check("pi-b", session_id="session-a")
    assert result["status"] == "error"
    assert "already committed" in result["error"]
    assert "newer uncommitted" in result["error"]
    assert portable.read_bytes() == before
    assert runtime["store"].owner("pi-a")["phase"] == "completed"


@pytest.mark.parametrize("phase, native_error, expected", [
    ("close", "cannot close issue with unclosed children: pi-child (deferred)", "children"),
    ("export", "permission denied", "permission"),
    ("stage", "unable to create index.lock: File exists", "lock"),
    ("commit", "error: gpg failed to sign the data", "signing"),
])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_native_closeout_failure_keeps_safe_diagnosis(runtime, monkeypatch, phase, native_error, expected):
    prepare_closeout(runtime, monkeypatch)
    exporter = closeout_backend(runtime, monkeypatch)
    original_exporter = exporter.read_bytes()
    original_beads, original_git = runtime["work"].run_beads_json, runtime["work"]._git
    private = "password=fixture-private-value https://user:fixture-credential@example.invalid SECRET-DETAIL"
    error = native_error + "\n" + private + "\n" + "x" * 5000
    if phase == "close":
        original = runtime["work"].run_beads_json
        monkeypatch.setattr(runtime["work"], "run_beads_json",
                            lambda args: (7, None, error) if args[0] == "close" else original(args))
    elif phase == "export":
        exporter.write_text("#!/usr/bin/env python3\nimport sys\nsys.stderr.write(" + repr(error) + "); sys.exit(7)\n")
    else:
        original = runtime["work"]._git
        def fail_git(root, args):
            if args[0] == ("add" if phase == "stage" else "commit"):
                return subprocess.CompletedProcess(args, 7, "", error)
            return original(root, args)
        monkeypatch.setattr(runtime["work"], "_git", fail_git)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["repair"]["failedStage"] == phase
    diagnostic = result["stages"][phase]["diagnostic"]
    assert diagnostic["exitCode"] == 7
    assert expected in diagnostic["detail"]
    assert len(diagnostic["detail"]) < 500
    assert "fixture-private" not in json.dumps(result)
    assert "fixture-credential" not in json.dumps(result)
    assert "SECRET-DETAIL" not in json.dumps(result)
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] == "success"
    assert runtime["store"].owner("pi-a")["phase"] == "active"
    monkeypatch.setattr(runtime["work"], "run_beads_json", original_beads)
    monkeypatch.setattr(runtime["work"], "_git", original_git)
    exporter.write_bytes(original_exporter)
    assert runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")["status"] == "closed"
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] == "success"


@pytest.mark.parametrize("other_phase", ["active", "paused", "reserved", "yielding", "completed"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_shared_checkout_closes_only_owned_bead(runtime, monkeypatch, other_phase):  # Tests INV-5
    prepare_closeout(runtime, monkeypatch)
    closeout_backend(runtime, monkeypatch)
    store = runtime["store"]
    store.claim("pi-b", "session-b", str(runtime["repo"]))
    with store.locked() as state:
        state["owners"]["pi-b"]["phase"] = other_phase
        store._write(state)
    other = store.owner("pi-b")
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "closed"
    assert store.owner("pi-a")["phase"] == "completed"
    assert store.owner("pi-b") == other
    assert runtime["beads"]["pi-b"]["status"] == "open"
    assert runtime["quality"].session_attempt_state("session-b")["outcome"] is None
    # Completed-owner retries must also coexist with unfinished neighbours.
    assert runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")["status"] == "closed"


@pytest.mark.parametrize("violation", ["foreign-session", "wrong-checkout", "wrong-header", "missing-owner",
                                      "paused", "reserved", "yielding", "pending-transition", "dirty-tree"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_shared_checkout_preserves_closeout_guards(runtime, monkeypatch, violation):  # Tests FAIL-1
    from test_work_continuation import progress
    portable = prepare_closeout(runtime, monkeypatch)
    store = runtime["store"]
    if violation == "pending-transition":
        cp = store.checkpoint("pi-a", "session-a", progress())
        store.prepare(source_session="session-a", checkpoint_ref=cp["id"], target_bead="pi-a",
                      target_checkout=str(runtime["repo"]), target_status="open", blockers=[],
                      mode="resume", runtime_ready=True, authorize=lambda _: True)
    store.claim("pi-b", "session-b", str(runtime["repo"]))
    if violation in {"paused", "reserved", "yielding", "missing-owner"}:
        with store.locked() as state:
            if violation == "missing-owner":
                del state["owners"]["pi-a"]
            else:
                state["owners"]["pi-a"]["phase"] = violation
            store._write(state)
    elif violation == "foreign-session":
        monkeypatch.setenv("PI_SESSION_ID", "session-b")
    elif violation == "wrong-checkout":
        monkeypatch.chdir(runtime["other"])
    elif violation == "wrong-header":
        (runtime["root"] / "source.jsonl").write_text(json.dumps(
            {"type": "session", "id": "session-b", "cwd": str(runtime["repo"])}))
    elif violation == "dirty-tree":
        dirty = runtime["repo"] / "dirty.txt"
        dirty.write_text("other task's work")
        subprocess.run(["git", "add", "--", "dirty.txt"], cwd=runtime["repo"], check=True, capture_output=True)
    before = portable.read_bytes(), (store.root / "journal.json").read_bytes()
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "error"
    stage = "preflight" if violation == "dirty-tree" else "ownership"
    assert result["stages"][stage]["status"] == "failed"
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert (portable.read_bytes(), (store.root / "journal.json").read_bytes()) == before


@pytest.mark.parametrize("phase", ["export", "stage"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_revocation_preserves_partial_export_or_index_without_commit(runtime, monkeypatch, phase):
    portable = prepare_closeout(runtime, monkeypatch)
    exporter = closeout_backend(runtime, monkeypatch)
    before = portable.read_bytes()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=runtime["repo"], check=True,
                          capture_output=True, text=True).stdout
    if phase == "export":
        original_run = subprocess.run
        def run(args, *positional, **kwargs):
            result = original_run(args, *positional, **kwargs)
            if args[0] == str(exporter):
                runtime["permission"].revoke("stop before portable replacement")
            return result
        monkeypatch.setattr(subprocess, "run", run)
    else:
        original_git = runtime["work"]._git
        def git(root, args):
            result = original_git(root, args)
            if args[0] == "add":
                runtime["permission"].revoke("stop before commit")
            return result
        monkeypatch.setattr(runtime["work"], "_git", git)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert result["stages"]["authority"]["status"] == "failed"
    assert result["repair"]["safeToRetry"] is False
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=runtime["repo"], check=True,
                          capture_output=True, text=True).stdout == head
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=runtime["repo"], check=True,
                            capture_output=True, text=True).stdout
    if phase == "export":
        assert portable.read_bytes() == before
        assert not staged
    else:
        assert json.loads(portable.read_text())["status"] == "closed"
        assert staged.strip() == ".beads/issues.jsonl"


@pytest.mark.parametrize("phase", ["export", "cleanup"])
@pytest.mark.parametrize("runtime", [{"effects": ["beads-write", "repo-write", "git-commit"]}], indirect=True)
def test_export_and_cleanup_keep_pinned_objects_when_parent_moves(runtime, monkeypatch, phase):
    portable = prepare_closeout(runtime, monkeypatch)
    exporter = closeout_backend(runtime, monkeypatch)
    foreign = runtime["root"] / "foreign-portable"
    foreign.mkdir()
    sentinel = b"unrelated foreign state\n"
    (foreign / "issues.jsonl").write_bytes(sentinel)
    moved_name = None
    def redirect(name):
        nonlocal moved_name
        moved_name = Path(name).name
        (foreign / moved_name).write_bytes(sentinel)
        portable.parent.rename(runtime["repo"] / "saved-beads")
        portable.parent.symlink_to(foreign, target_is_directory=True)
    if phase == "export":
        original_run = subprocess.run
        def run(args, *positional, **kwargs):
            if args[0] == str(exporter):
                assert "-o" not in args
                assert hasattr(kwargs["stdout"], "fileno")
                redirect(next(portable.parent.glob("issues-*.jsonl")))
            return original_run(args, *positional, **kwargs)
        monkeypatch.setattr(subprocess, "run", run)
    else:
        exporter.write_text(exporter.read_text() + "\nsys.exit(1)\n")
        original_unlink = runtime["work"].os.unlink
        def unlink(name, **kwargs):
            if Path(name).name.startswith("issues-"):
                redirect(name)
            return original_unlink(name, **kwargs)
        monkeypatch.setattr(runtime["work"].os, "unlink", unlink)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert moved_name is not None
    assert (foreign / moved_name).read_bytes() == sentinel
    assert (foreign / "issues.jsonl").read_bytes() == sentinel
    assert not (runtime["repo"] / "saved-beads" / moved_name).exists()
