"""Local-only Beads keeps lifecycle proof without publishing bookkeeping."""
import json
import subprocess

import pytest

from test_work_continuation import runtime  # noqa: F401


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def prepare_local(runtime, monkeypatch, *, worktree=False):
    repo = runtime["other"] if worktree else runtime["repo"]
    exclude = runtime["repo"] / ".git/info/exclude"
    exclude.write_text(exclude.read_text() + "\n.beads/\n")
    if not worktree:
        (repo / ".beads").mkdir()
    monkeypatch.chdir(repo)
    (runtime["root"] / "source.jsonl").write_text(
        json.dumps({"type": "session", "id": "session-a", "cwd": str(repo)}) + "\n"
    )
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    original = runtime["work"].run_beads_json

    def runner(args):
        if args[0] == "close":
            runtime["beads"]["pi-a"].update(
                status="closed", closed_at="2026-10-28T00:00:00Z", close_reason=args[-1]
            )
        return original(args)

    monkeypatch.setattr(runtime["work"], "run_beads_json", runner)
    monkeypatch.setattr(runtime["work"], "beads_bin", lambda: pytest.fail("local closeout must not export"))
    return repo, exclude


@pytest.mark.parametrize("worktree", [False, True])
@pytest.mark.parametrize("export_exists", [False, True])
def test_local_closeout_retry_and_handoff_without_git_commit(runtime, monkeypatch, worktree, export_exists):  # Tests INV-9
    repo, _ = prepare_local(runtime, monkeypatch, worktree=worktree)
    portable = repo / ".beads/issues.jsonl"
    if export_exists:
        portable.parent.mkdir(exist_ok=True)
        portable.write_text("stale optional export\n")
    head = git(repo, "rev-parse", "HEAD")
    for _ in range(2):
        result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
        assert result["status"] == "closed", result
        assert result["commit"] is None
        for stage in ("export", "stage", "commit"):
            assert result["stages"][stage] == {"status": "skipped", "reason": "local-only"}
        assert runtime["store"].owner("pi-a")["phase"] == "completed"
        assert runtime["work"].handoff_check("pi-b", session_id="session-a")["status"] == "ready"
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "ls-files", "--", ".beads") == ""
    if export_exists:
        assert portable.read_text() == "stale optional export\n"
    else:
        assert not portable.exists()


@pytest.mark.parametrize("mode", ["unignored", "file-only-ignore", "mixed"])
def test_ambiguous_tracking_fails_before_outcome(runtime, monkeypatch, mode):  # Tests FAIL-6
    repo, exclude = prepare_local(runtime, monkeypatch)
    if mode == "unignored":
        exclude.write_text("")
    elif mode == "file-only-ignore":
        exclude.write_text(".beads/issues.jsonl\n")
    else:
        (repo / ".beads/config.yaml").write_text("export.auto: false\n")
        git(repo, "add", "-f", ".beads/config.yaml")
        git(repo, "commit", "-qm", "mixed fixture")
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["stages"]["preflight"]["status"] == "failed"
    assert "tracking" in result["stages"]["preflight"]["error"]
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])
    assert not runtime["work"].handoff_closeout_is_clean(runtime["beads"]["pi-a"])


@pytest.mark.parametrize("change", ["ignore", "tracked", "symlink", "revoke"])
def test_local_mode_drift_stops_before_native_close(runtime, monkeypatch, change):
    repo, exclude = prepare_local(runtime, monkeypatch)
    original = runtime["work"].record_current_session_outcome

    def record(*args):
        result = original(*args)
        if change == "ignore":
            exclude.write_text("")
        elif change == "tracked":
            (repo / ".beads/issues.jsonl").write_text("{}\n")
            git(repo, "add", "-f", ".beads/issues.jsonl")
        elif change == "symlink":
            (repo / ".beads").rename(repo / "saved-beads")
            (repo / ".beads").symlink_to(repo / "saved-beads", target_is_directory=True)
        else:
            runtime["permission"].revoke("stop closeout")
        return result

    monkeypatch.setattr(runtime["work"], "record_current_session_outcome", record)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["stages"]["authority"]["status"] == "failed"
    assert result["repair"]["safeToRetry"] is False
    assert not any(args[0] == "close" for args in runtime["calls"])


@pytest.mark.parametrize("runtime", [{"effects": ["repo-write"]}, {"effects": ["beads-write"]}], indirect=True)
def test_local_closeout_still_requires_write_authority(runtime, monkeypatch):
    prepare_local(runtime, monkeypatch)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["stages"]["authority"]["status"] == "failed"
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not any(args[0] == "close" for args in runtime["calls"])


@pytest.mark.parametrize("dirty_after_close", [False, True])
def test_local_closeout_preserves_dirty_code_gate(runtime, monkeypatch, dirty_after_close):
    repo, _ = prepare_local(runtime, monkeypatch)
    code = repo / "code.txt"
    code.write_text("committed\n")
    git(repo, "add", "code.txt")
    git(repo, "commit", "-qm", "code fixture")
    if dirty_after_close:
        assert runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")["status"] == "closed"
    code.write_text("uncommitted\n")
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["stages"]["preflight"]["status"] == "failed"
    assert not runtime["work"].handoff_closeout_is_clean(runtime["beads"]["pi-a"])
    assert code.read_text() == "uncommitted\n"


@pytest.mark.parametrize("field,value", [("status", "open"), ("closed_at", ""), ("close_reason", "wrong reason"), ("id", "pi-b")])
def test_local_closeout_requires_canonical_closure_readback(runtime, monkeypatch, field, value):
    prepare_local(runtime, monkeypatch)
    original = runtime["work"].run_beads_json

    def runner(args):
        result = original(args)
        if args[0] == "close":
            runtime["beads"]["pi-a"][field] = value
        return result

    monkeypatch.setattr(runtime["work"], "run_beads_json", runner)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert runtime["store"].owner("pi-a")["phase"] != "completed"


@pytest.mark.parametrize("change", ["ignore", "revoke"])
def test_local_drift_after_native_close_preserves_partial_state(runtime, monkeypatch, change):
    _, exclude = prepare_local(runtime, monkeypatch)
    original = runtime["work"].run_beads_json

    def runner(args):
        result = original(args)
        if args[0] == "close":
            if change == "ignore":
                exclude.write_text("")
            else:
                runtime["permission"].revoke("stop after close")
        return result

    monkeypatch.setattr(runtime["work"], "run_beads_json", runner)
    result = runtime["work"].direct_closeout("pi-a", outcome="success", reason="fixture complete")
    assert result["status"] == "partial"
    assert result["repair"]["safeToRetry"] is False
    assert runtime["beads"]["pi-a"]["status"] == "closed"
    assert runtime["store"].owner("pi-a")["phase"] != "completed"
    handoff = runtime["work"].handoff_check("pi-b", session_id="session-a")
    assert handoff["status"] == "error"
    assert "finalization" in handoff["error"]


@pytest.mark.parametrize("field", ["status", "closed_at", "close_reason"])
def test_local_handoff_rejects_incomplete_closure(runtime, monkeypatch, field):
    prepare_local(runtime, monkeypatch)
    row = {"id": "pi-a", "status": "closed", "closed_at": "2026-10-28T00:00:00Z", "close_reason": "done"}
    row.pop(field)
    assert not runtime["work"].handoff_closeout_is_clean(row)
