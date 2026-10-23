"""CLI/quality/Beads adapter journeys; no real Beads or live Pi state."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_authority import historical_record


@pytest.fixture
def runtime(agnt, tmp_path, monkeypatch, request):
    from agnt_lib import authority, improvement, quality, work, work_lifecycle
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "fixture@example.test"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-qm", "base"], check=True)
    other = tmp_path / "other"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb", "other", str(other)], check=True)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PI_SESSION_ID", "session-a")
    source_file = tmp_path / "source.jsonl"
    source_file.write_text(json.dumps({"type": "session", "id": "session-a", "cwd": str(repo)}) + "\n")
    monkeypatch.setenv("PI_SESSION_FILE", str(source_file))
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda _, **_kwargs: tmp_path / "quality")
    monkeypatch.setattr(improvement, "_best_effort_projection", lambda summary, _: summary)
    store = work_lifecycle.LifecycleStore(tmp_path / "lifecycle")
    monkeypatch.setattr(work_lifecycle, "runtime_store", lambda *_: store, raising=False)
    permission = authority.AuthorityStore(tmp_path / "authority")
    permission.admit_historical(historical_record(authority.load_policy()))
    effects = getattr(request, "param", {}).get("effects", ["repo-write", "work-transition", "beads-write"])
    permission.assign("queue", repository=str(repo), beads=["pi-a", "pi-b"],
                      effects=effects, intent_ref="fixture:delegated-queue")
    monkeypatch.setattr(authority, "AuthorityStore", lambda: permission)
    monkeypatch.setattr(work_lifecycle, "authority_store", lambda: permission)
    beads = {key: {"id": key, "title": key, "status": "open", "priority": 1, "dependencies": []}
             for key in ("pi-a", "pi-b")}
    calls = []
    def runner(args):
        calls.append(args)
        if args[0] == "ready":
            return 0, [b.copy() for b in beads.values() if b["status"] == "open"], ""
        if args[0] == "list":
            return 0, [b.copy() for b in beads.values() if b["status"] == "in_progress"], ""
        if args[0] == "update":
            beads[args[1]]["status"] = "in_progress"
        return (0, [beads[args[1]].copy()], "") if args[1] in beads else (1, None, "missing")
    monkeypatch.setattr(work, "run_beads_json", runner)
    return {"repo": repo, "other": other, "root": tmp_path, "quality": quality, "work": work,
            "store": store, "beads": beads, "calls": calls, "permission": permission}


def progress():
    return {"objective": "finish assigned work", "decisions": ["keep history"], "completed": [],
            "next": ["implement"], "blockers": [], "verification": [], "ownedPaths": [],
            "artifactRefs": [], "assignmentRef": "queue"}


def checkpoint(agnt, runtime, capsys):
    payload = runtime["root"] / "progress.json"
    payload.write_text(json.dumps(progress()))
    assert agnt.main(["work", "checkpoint", "pi-a", "--input-file", str(payload)]) == 0
    return json.loads(capsys.readouterr().out)["checkpoint"]


def prepare(agnt, runtime, cp, capsys, *, target="pi-a", checkout=None):
    args = ["work", "transition-prepare", target, "--mode", "resume" if target == "pi-a" else "switch",
            "--session-id", "session-a", "--checkpoint-ref", cp["id"], "--runtime-ready"]
    if checkout:
        args += ["--checkout", str(checkout)]
    assert agnt.main(args) == 0
    return json.loads(capsys.readouterr().out)["transition"]


def stage(agnt, tx, capsys):
    path = Path(tx["childSessionFile"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "session", "version": 3, "id": tx["childSession"],
                               "cwd": tx["targetCheckout"], "parentSession": tx.get("sourceSessionFile")}) + "\n")
    assert agnt.main(["work", "transition-stage", tx["id"], "--session-id", tx["sourceSession"]]) == 0
    capsys.readouterr()


def test_direct_sessions_share_canonical_checkout_without_relabeling(runtime, monkeypatch):
    repo, store = runtime["repo"], runtime["store"]
    nested = repo / "nested"
    nested.mkdir()
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    owner = store.owner("pi-a")
    monkeypatch.setenv("PI_SESSION_ID", "session-b")
    monkeypatch.chdir(nested)
    assert runtime["work"].direct_start("pi-b", claim=True)["status"] == "started"
    assert store.owner("pi-a") == owner
    assert store.owner("pi-b")["checkout"] == str(repo)
    for session, bead in (("session-a", "pi-a"), ("session-b", "pi-b")):
        assert runtime["quality"].session_attempt_state(session) == {"beadId": bead, "outcome": None}


def test_workspace_snapshot_ignores_git_environment(runtime, monkeypatch):
    from agnt_lib.work_lifecycle import workspace_snapshot
    (runtime["repo"] / "source-only.txt").write_text("source")
    (runtime["other"] / "target-only.txt").write_text("target")
    expected = workspace_snapshot(str(runtime["other"]))
    monkeypatch.setenv("GIT_DIR", str(runtime["repo"] / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(runtime["repo"]))
    assert workspace_snapshot(str(runtime["other"])) == expected


def test_nested_session_preserves_parent_identity_and_full_checkout(agnt, runtime, capsys, monkeypatch):
    nested = runtime["repo"] / "nested"
    nested.mkdir()
    (runtime["repo"] / "outside.txt").write_text("preserve outside cwd")
    source = runtime["root"] / "source.jsonl"
    source.write_text(json.dumps({"type": "session", "id": "session-a", "cwd": str(nested)}) + "\n")
    monkeypatch.chdir(nested)
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    cp = checkpoint(agnt, runtime, capsys)
    assert cp["workspace"]["checkout"] == str(runtime["repo"])
    assert "outside.txt" in cp["workspace"]["changed"]
    tx = prepare(agnt, runtime, cp, capsys)
    assert tx["sourceSessionFile"] == str(source)
    assert tx["targetCheckout"] == str(runtime["repo"])


@pytest.mark.parametrize("runtime", [{"effects": ["repo-write", "work-transition"]}], indirect=True)
def test_transition_requires_authority_for_native_beads_claim(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    cp = checkpoint(agnt, runtime, capsys)
    from agnt_lib.work_lifecycle import transition_check
    with pytest.raises(ValueError, match="authority"):
        transition_check("pi-a", mode="resume", session_id="session-a", checkpoint_ref=cp["id"])
    assert runtime["store"].pending_transition("session-a") is None


@pytest.mark.parametrize("runtime", [{"effects": ["repo-write", "work-transition"]}], indirect=True)
def test_direct_claim_cannot_bypass_assignment_effects(runtime):
    result = runtime["work"].direct_start("pi-a", claim=True)
    assert result["status"] == "error"
    assert result["stages"]["claim"] == {"status": "skipped", "reason": "authority-denied"}
    assert result["repair"]["safeToRetry"] is False
    assert not any(call[0] == "update" for call in runtime["calls"])
    assert runtime["quality"].session_work_item("session-a") is None
    assert runtime["store"].owner("pi-a") is None


def test_ambiguous_assignment_reports_authority_not_session_conflict(runtime):
    runtime["permission"].assign("another", repository=str(runtime["repo"]), beads=["pi-a"],
                                effects=["beads-write"], intent_ref="fixture:another-user-intent")
    result = runtime["work"].direct_start("pi-a", claim=True)
    assert result["stages"]["claim"]["reason"] == "authority-denied"
    assert result["repair"]["requiredAction"] == "inspect-current-authority"
    assert not any(call[0] == "update" for call in runtime["calls"])


def test_revocation_while_direct_link_waits_prevents_native_claim(runtime, monkeypatch):
    from agnt_lib import improvement
    capture = improvement.capture_session_link
    def revoke_then_link(*args, **kwargs):
        runtime["permission"].revoke("queued direct claim revoked")
        return capture(*args, **kwargs)
    monkeypatch.setattr(improvement, "capture_session_link", revoke_then_link)
    result = runtime["work"].direct_start("pi-a", claim=True)
    assert result["status"] == "error"
    assert result["stages"]["claim"]["reason"] == "authority-denied"
    assert not any(call[0] == "update" for call in runtime["calls"])
    assert runtime["quality"].session_work_item("session-a") is None


def test_revocation_while_attachment_link_waits_prevents_native_claim(agnt, runtime, capsys, monkeypatch):
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    quality = runtime["quality"]
    capture = quality.capture_session_link
    def revoke_then_link(*args, **kwargs):
        runtime["permission"].revoke("queued attachment claim revoked")
        return capture(*args, **kwargs)
    monkeypatch.setattr(quality, "capture_session_link", revoke_then_link)
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    runtime["calls"].clear()
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) != 0
    capsys.readouterr()
    assert not any(call[0] == "update" for call in runtime["calls"])
    assert quality.session_work_item(tx["childSession"]) is None
    assert runtime["store"].status(tx["id"])["state"] == "attaching"


def test_work_cli_advertises_continuation(agnt, capsys):
    with pytest.raises(SystemExit) as stopped:
        agnt.main(["work", "--help"])
    assert stopped.value.code == 0
    assert "transition-check" in capsys.readouterr().out


def test_partial_same_bead_resume_preserves_outcome(agnt, runtime, capsys, monkeypatch):
    work, quality = runtime["work"], runtime["quality"]
    assert work.direct_start("pi-a", claim=True)["status"] == "started"
    quality.capture_session_outcome("session-a", "pi-a", "partial", beads_runner=work.run_beads_json)
    cp = checkpoint(agnt, runtime, capsys)
    tx = prepare(agnt, runtime, cp, capsys)
    stage(agnt, tx, capsys)
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
    assert json.loads(capsys.readouterr().out)["transition"]["state"] == "attached"
    assert quality.session_handoff_source("session-a")["outcome"] == "partial"
    assert quality.session_work_item(tx["childSession"]) == "pi-a"
    claims = len([call for call in runtime["calls"] if call[0] == "update"])
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
    capsys.readouterr()
    assert len([call for call in runtime["calls"] if call[0] == "update"]) == claims


def test_direct_start_prevents_same_actor_competition(agnt, runtime, monkeypatch):
    work = runtime["work"]
    assert work.direct_start("pi-a", claim=True)["status"] == "started"
    monkeypatch.setenv("PI_SESSION_ID", "competitor")
    runtime["calls"].clear()
    assert work.direct_start("pi-a", claim=True)["status"] != "started"
    assert not any(call[0] == "update" for call in runtime["calls"])


def test_cli_switch_preserves_dirty_source(agnt, runtime, capsys, monkeypatch):
    work = runtime["work"]
    assert work.direct_start("pi-a", claim=True)["status"] == "started"
    dirty = runtime["repo"] / "unfinished.txt"
    dirty.write_text("keep this")
    cp = checkpoint(agnt, runtime, capsys)
    tx = prepare(agnt, runtime, cp, capsys, target="pi-b", checkout=runtime["other"])
    stage(agnt, tx, capsys)
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    monkeypatch.chdir(runtime["other"])
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
    capsys.readouterr()
    assert dirty.read_text() == "keep this"
    assert runtime["quality"].session_work_item(tx["childSession"]) == "pi-b"
    assert work.direct_start("pi-b", claim=False)["status"] == "started"


def test_revocation_blocks_prepared_child(agnt, runtime, capsys, monkeypatch):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    runtime["permission"].revoke("stop")
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) != 0
    assert runtime["quality"].session_work_item(tx["childSession"]) is None


def test_in_progress_target_does_not_require_ready_membership(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    cp = checkpoint(agnt, runtime, capsys)
    runtime["beads"]["pi-b"]["status"] = "in_progress"
    tx = prepare(agnt, runtime, cp, capsys, target="pi-b", checkout=runtime["other"])
    assert tx["targetBead"] == "pi-b"


def test_launch_reservation_cannot_be_replayed(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    args = ["work", "transition-launch", tx["id"], "--session-id", "session-a"]
    assert agnt.main(args) == 0
    assert json.loads(capsys.readouterr().out)["transition"]["state"] == "launch-requested"
    assert agnt.main(args) != 0
    capsys.readouterr()
    assert agnt.main(["work", "transition-recover", tx["id"]]) == 0
    assert json.loads(capsys.readouterr().out)["transition"]["requiredAction"] == "reconcile-launch"


@pytest.mark.parametrize("launch", [False, True])
def test_compact_recovery_preserves_progress_and_uncertainty(agnt, runtime, capsys, launch):  # Tests INV-3
    from agnt_lib.authority import fingerprint
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    for i in range(100):
        (runtime["repo"] / f"dirty-{i}.txt").write_text("preserve")
    facts = progress()
    facts.update(decisions=["prior grant consumed", "do not replay"], blockers=["cleanup unverified"],
                 verification=["historical only"], artifactRefs=["evidence.json"], ownedPaths=["dirty-0.txt"])
    cp = runtime["store"].checkpoint("pi-a", "session-a", facts)
    tx = prepare(agnt, runtime, cp, capsys)
    if launch:
        stage(agnt, tx, capsys)
        assert agnt.main(["work", "transition-launch", tx["id"], "--session-id", "session-a"]) == 0
        capsys.readouterr()
    assert agnt.main(["work", "transition-recover", tx["id"]]) == 0
    full = json.loads(capsys.readouterr().out)
    assert agnt.main(["work", "transition-recover", tx["id"], "--compact"]) == 0
    output = capsys.readouterr().out
    compact = json.loads(output)
    assert compact["checkpoint"]["progress"] == facts
    assert compact["transition"]["requiredAction"] == ("reconcile-launch" if launch else "stage-exact-child")
    for field, workspace in [("checkpoint", "workspace"), ("transition", "targetWorkspace")]:
        original = full[field][workspace]
        projected = compact[field][workspace]
        assert projected == {**{k: v for k, v in original.items() if k != "changed"},
                             "changedPathCount": len(original["changed"]),
                             "changedFingerprint": fingerprint(original["changed"])}
        assert {k: v for k, v in compact[field].items() if k != workspace} == {
            k: v for k, v in full[field].items() if k != workspace}
    assert compact["presentation"]["fullCommand"] == f"agnt work transition-recover {tx['id']}"
    assert "not authority" in compact["presentation"]["warning"]
    assert len(output) < len(json.dumps(full)) // 2
    assert runtime["store"].get_checkpoint(cp["id"]) == cp


def test_compact_recovery_keeps_unresolved_isolation(agnt, runtime, capsys, monkeypatch):  # Tests INV-3
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    cp = checkpoint(agnt, runtime, capsys)
    tx = prepare(agnt, runtime, cp, capsys)
    unresolved = {**tx, "state": "isolating", "targetWorkspace": None, "cancelRequested": True,
                  "requiredAction": "finish-cancellation", "deliveryStatus": "uncertain"}
    monkeypatch.setattr(runtime["store"], "recover", lambda _: unresolved.copy())
    assert agnt.main(["work", "transition-recover", tx["id"], "--compact"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["transition"] == unresolved
    assert result["checkpoint"]["progress"] == cp["progress"]


def test_compact_recovery_missing_checkpoint_stays_blocked(agnt, runtime, capsys, monkeypatch):  # Tests FAIL-2
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    def missing(_):
        raise KeyError("missing checkpoint")
    monkeypatch.setattr(runtime["store"], "get_checkpoint", missing)
    assert agnt.main(["work", "transition-recover", tx["id"], "--compact"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert "missing checkpoint" in result["reason"]
    assert "checkpoint" not in result


@pytest.mark.parametrize("reason", ["shutdown-request-failed", "launch-request-failed"])
def test_known_preexit_failure_restores_source(agnt, runtime, capsys, monkeypatch, reason):
    from agnt_lib import work_lifecycle
    monkeypatch.setattr(work_lifecycle, "_launch_proof_hash", lambda *_: "sha256:fixture-host-secret")
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    assert agnt.main(["work", "transition-launch", tx["id"], "--session-id", "session-a"]) == 0
    capsys.readouterr()
    assert agnt.main(["work", "transition-abort-launch", tx["id"], "--session-id", "session-a",
                      "--reason", reason]) == 0
    capsys.readouterr()
    assert runtime["store"].owner("pi-a")["phase"] == "active"
    checkpoint(agnt, runtime, capsys)


@pytest.mark.parametrize("reason", ["exec-failed", "launch-request-failed"])
def test_failure_reason_alone_cannot_cancel_uncertain_launch(agnt, runtime, capsys, reason):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    assert agnt.main(["work", "transition-launch", tx["id"], "--session-id", "session-a"]) == 0
    capsys.readouterr()
    assert agnt.main(["work", "transition-abort-launch", tx["id"], "--session-id", "session-a",
                      "--reason", reason]) != 0
    assert runtime["store"].status(tx["id"])["state"] == "launch-requested"


def test_private_launch_pipe_binds_compensation_to_reserved_host(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    script = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(Path(__file__).resolve().parents[1] / 'pi/agent/bin')!r})
from agnt_lib import work_lifecycle, work
work_lifecycle.runtime_store = lambda: work_lifecycle.LifecycleStore(Path({str(runtime['store'].root)!r}))
work_lifecycle._transition_authorized = lambda _: True
raise SystemExit(work.cmd_work(sys.argv[1:]))
"""
    proof = {"kind": "work-launch-v1", "transition": tx["id"], "sourceSession": "session-a", "secret": "d" * 64}
    def call(command, payload):
        args = [sys.executable, "-c", script, command, tx["id"], "--session-id", "session-a"]
        if command == "transition-abort-launch":
            args += ["--reason", "exec-failed"]
        return subprocess.run(args, input=json.dumps(payload), text=True, capture_output=True,
                              env={**os.environ, "AGNT_WORK_LAUNCH_PROOF_FD": "0"})
    launched = call("transition-launch", proof)
    assert launched.returncode == 0, launched.stdout + launched.stderr
    assert proof["secret"] not in launched.stdout
    denied = call("transition-abort-launch", {**proof, "secret": "e" * 64})
    assert denied.returncode == 2
    assert runtime["store"].status(tx["id"])["state"] == "launch-requested"
    assert call("transition-abort-launch", proof).returncode == 0
    assert runtime["store"].owner("pi-a")["phase"] == "active"


def test_wrong_parent_session_cannot_stage_child(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    path = Path(tx["childSessionFile"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "session", "id": tx["childSession"], "cwd": tx["targetCheckout"],
                               "parentSession": "/foreign/session.jsonl"}) + "\n")
    assert agnt.main(["work", "transition-stage", tx["id"], "--session-id", "session-a"]) != 0
    assert runtime["store"].owner("pi-a")["phase"] == "active"


def test_missing_child_checkout_cannot_inherit_current_directory(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    path = Path(tx["childSessionFile"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "session", "id": tx["childSession"],
                               "parentSession": tx["sourceSessionFile"]}) + "\n")
    assert agnt.main(["work", "transition-stage", tx["id"], "--session-id", "session-a"]) != 0
    assert runtime["store"].owner("pi-a")["phase"] == "active"


def test_attachment_rejects_wrong_persisted_child_file(agnt, runtime, capsys, monkeypatch):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    monkeypatch.setenv("PI_SESSION_FILE", str(runtime["root"] / "different.jsonl"))
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) != 0
    assert runtime["quality"].session_work_item(tx["childSession"]) is None


def test_work_status_distinguishes_yielding_source(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    assert runtime["work"].work_status("session-a")["executionPhase"] == "yielding"


def test_source_context_discovers_pending_transition(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    assert agnt.main(["work", "transition-context", "--session-id", "session-a"]) == 0
    assert json.loads(capsys.readouterr().out)["pendingTransition"]["id"] == tx["id"]


def test_child_context_finds_reserved_attachment(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    stage(agnt, tx, capsys)
    assert agnt.main(["work", "transition-context", "--session-id", tx["childSession"]]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "child"
    assert result["transition"]["id"] == tx["id"]


def test_checkpoint_stdin_captures_progress_without_scope_json(agnt, runtime, capsys, monkeypatch):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    supplied = {key: value for key, value in progress().items() if key != "assignmentRef"}
    supplied.update(decisions=["Keep current API"], next=["Run tests/test_work_continuation.py"],
                    verification=["Focused tests passed; full suite not run"], artifactRefs=[".pi/plans/current.md"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(supplied)))
    assert agnt.main(["work", "checkpoint", "pi-a", "--input-file", "-"]) == 0
    cp = json.loads(capsys.readouterr().out)["checkpoint"]
    assert cp["progress"] == {**supplied, "assignmentRef": "queue"}
    assert runtime["store"].latest_checkpoint("pi-a") == cp
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None
    assert not (runtime["repo"] / "progress.json").exists()
    tx = prepare(agnt, runtime, cp, capsys)
    assert agnt.main(["work", "transition-recover", tx["id"]]) == 0
    recovered = json.loads(capsys.readouterr().out)
    assert recovered.get("checkpoint") == cp, "child needs readable checkpoint, not only an opaque ID"


@pytest.mark.parametrize("payload", ["[]", json.dumps({**progress(), "assignmentRef": "direct:pi-a"}), " " * 65537])
def test_checkpoint_stdin_rejects_invalid_scope_or_oversize(agnt, runtime, capsys, monkeypatch, payload):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert agnt.main(["work", "checkpoint", "pi-a", "--input-file", "-"]) != 0
    assert runtime["store"].latest_checkpoint("pi-a") is None
    capsys.readouterr()


def test_auto_checkpoint_preserves_curated_progress(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    previous = checkpoint(agnt, runtime, capsys)
    assert agnt.main(["work", "checkpoint", "pi-a"]) == 0
    current = json.loads(capsys.readouterr().out)["checkpoint"]
    assert current["progress"]["decisions"] == ["keep history"]
    assert current["previousCheckpointRef"] == previous["id"]


def test_direct_start_scope_supports_dirty_switch_without_authority_json(agnt, runtime, capsys, monkeypatch):
    from agnt_lib import authority, work_lifecycle
    # No preconfigured queue: only owner admission, then ordinary work command.
    permission_class = type(runtime["permission"])
    permission = permission_class(runtime["root"] / "ordinary-authority")
    permission.admit_historical(historical_record(authority.load_policy()))
    monkeypatch.setattr(work_lifecycle, "authority_store", lambda: permission)
    runtime["permission"] = permission
    assert agnt.main(["work", "direct-start", "pi-a", "--claim", "--scope-bead", "pi-b"]) == 0
    capsys.readouterr()
    assignment = permission.assignment_for(str(runtime["repo"]), "pi-a")
    assert assignment == permission.assignment_for(str(runtime["repo"]), "pi-b")
    assert assignment["beads"] == ["pi-a", "pi-b"]
    assert "worktree-create" in assignment["effects"]
    assert not {"push", "deploy-production", "external_write"} & set(assignment["effects"])
    (runtime["repo"] / "dirty-a").write_text("keep a")
    assert agnt.main(["work", "checkpoint", "pi-a"]) == 0
    cp = json.loads(capsys.readouterr().out)["checkpoint"]
    tx = prepare(agnt, runtime, cp, capsys, target="pi-b")
    stage(agnt, tx, capsys)
    monkeypatch.chdir(tx["targetCheckout"])
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
    capsys.readouterr()
    Path("dirty-b").write_text("keep b")
    assert agnt.main(["work", "checkpoint", "pi-b"]) == 0
    cp_b = json.loads(capsys.readouterr().out)["checkpoint"]
    assert cp_b["progress"]["objective"] == "pi-b", "B must not inherit A's claimed progress as its own"
    assert agnt.main(["work", "transition-prepare", "pi-a", "--mode", "switch", "--session-id", tx["childSession"],
                      "--checkpoint-ref", cp_b["id"], "--runtime-ready"]) == 0
    back = json.loads(capsys.readouterr().out)["transition"]
    stage(agnt, back, capsys)
    monkeypatch.chdir(back["targetCheckout"])
    monkeypatch.setenv("PI_SESSION_ID", back["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", back["childSessionFile"])
    assert agnt.main(["work", "transition-attach", back["id"], "--session-id", back["childSession"]]) == 0
    capsys.readouterr()
    assert runtime["store"].owner("pi-a")["phase"] == "active"
    assert runtime["store"].owner("pi-b")["phase"] == "paused"
    assert (runtime["repo"] / "dirty-a").read_text() == "keep a"
    assert (Path(tx["targetCheckout"]) / "dirty-b").read_text() == "keep b"
    assert permission.assignment_for(str(runtime["repo"]), "pi-c") is None
    assert runtime["quality"].session_attempt_state("session-a")["outcome"] is None


def test_explicit_work_scope_cannot_widen_existing_assignment(agnt, runtime, capsys):
    runtime["beads"]["pi-c"] = {"id": "pi-c", "title": "other", "status": "open", "dependencies": []}
    before = runtime["permission"].inspect()
    assert agnt.main(["work", "direct-start", "pi-a", "--claim", "--scope-bead", "pi-b", "--scope-bead", "pi-c"]) != 0
    result = json.loads(capsys.readouterr().out)
    assert result["repair"]["failedStage"] == "authority"
    assert runtime["permission"].inspect() == before
    assert runtime["permission"].assignment_for(str(runtime["repo"]), "pi-c") is None
    assert runtime["store"].owner("pi-a") is None
    assert not any(call[0] == "update" for call in runtime["calls"])


@pytest.mark.parametrize("failure", ["missing", "closed", "revoked"])
def test_work_scope_denial_does_not_claim_or_enroll(agnt, runtime, capsys, failure):
    before = runtime["permission"].inspect()
    target = "pi-missing" if failure == "missing" else "pi-b"
    if failure == "closed":
        runtime["beads"]["pi-b"]["status"] = "closed"
    if failure == "revoked":
        runtime["permission"].revoke("owner stops work")
        before = runtime["permission"].inspect()
    assert agnt.main(["work", "direct-start", "pi-a", "--claim", "--scope-bead", target]) != 0
    result = json.loads(capsys.readouterr().out)
    assert result["repair"]["failedStage"] == "authority"
    assert runtime["permission"].inspect() == before
    assert runtime["store"].owner("pi-a") is None
    assert not any(call[0] == "update" for call in runtime["calls"])


def test_explicit_scope_reuses_restricted_effects_without_widening(agnt, runtime, capsys):
    before = runtime["permission"].assignment_for(str(runtime["repo"]), "pi-a")
    assert agnt.main(["work", "direct-start", "pi-a", "--claim", "--scope-bead", "pi-b"]) == 0
    capsys.readouterr()
    assert runtime["permission"].assignment_for(str(runtime["repo"]), "pi-a") == before
    cp = checkpoint(agnt, runtime, capsys)
    assert agnt.main(["work", "transition-prepare", "pi-b", "--mode", "switch", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"], "--runtime-ready"]) != 0
    assert "outside assignment authority" in json.loads(capsys.readouterr().out)["reason"]
    assert runtime["store"].owner("pi-b") is None


def test_direct_start_lazily_enrolls_only_selected_bead(agnt, runtime):
    runtime["beads"]["pi-c"] = {"id": "pi-c", "title": "selected work", "status": "open", "dependencies": []}
    assert runtime["work"].direct_start("pi-c", claim=False)["status"] == "started"
    assignment = runtime["permission"].assignment_for(str(runtime["repo"]), "pi-c")
    assert assignment["beads"] == ["pi-c"]
    assert "deploy-production" not in assignment["effects"]
    assert not (runtime["repo"] / ".pi").exists()


def test_a_b_a_round_trip_preserves_checkouts_and_attempts(agnt, runtime, capsys, monkeypatch):
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    (runtime["repo"] / "dirty-a").write_text("a preserved")
    tx_b = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys,
                   target="pi-b", checkout=runtime["other"])
    stage(agnt, tx_b, capsys)
    monkeypatch.setenv("PI_SESSION_ID", tx_b["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx_b["childSessionFile"])
    monkeypatch.chdir(runtime["other"])
    assert agnt.main(["work", "transition-attach", tx_b["id"], "--session-id", tx_b["childSession"]]) == 0
    capsys.readouterr()
    (runtime["other"] / "dirty-b").write_text("b preserved")
    assert agnt.main(["work", "checkpoint", "pi-b"]) == 0
    cp_b = json.loads(capsys.readouterr().out)["checkpoint"]
    assert agnt.main(["work", "transition-prepare", "pi-a", "--mode", "switch", "--session-id", tx_b["childSession"],
                      "--checkpoint-ref", cp_b["id"], "--runtime-ready"]) == 0
    tx_a = json.loads(capsys.readouterr().out)["transition"]
    stage(agnt, tx_a, capsys)
    monkeypatch.setenv("PI_SESSION_ID", tx_a["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx_a["childSessionFile"])
    monkeypatch.chdir(runtime["repo"])
    assert agnt.main(["work", "transition-attach", tx_a["id"], "--session-id", tx_a["childSession"]]) == 0
    capsys.readouterr()
    assert runtime["store"].owner("pi-a")["session"] == tx_a["childSession"]
    assert runtime["store"].owner("pi-b")["phase"] == "paused"
    assert (runtime["repo"] / "dirty-a").read_text() == "a preserved"
    assert (runtime["other"] / "dirty-b").read_text() == "b preserved"
    assert runtime["quality"].session_work_item("session-a") == "pi-a"
    assert runtime["quality"].session_work_item(tx_b["childSession"]) == "pi-b"
    assert runtime["quality"].session_work_item(tx_a["childSession"]) == "pi-a"


def test_auto_checkpoint_uses_current_private_assignment(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    assert agnt.main(["work", "checkpoint", "pi-a"]) == 0
    cp = json.loads(capsys.readouterr().out)["checkpoint"]
    assert cp["progress"]["assignmentRef"] == "queue"


def test_checkpoint_cannot_downgrade_standing_scope_to_direct(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    payload = runtime["root"] / "downgrade.json"
    payload.write_text(json.dumps({**progress(), "assignmentRef": "direct:pi-a"}))
    assert agnt.main(["work", "checkpoint", "pi-a", "--input-file", str(payload)]) != 0


def test_headless_check_is_readonly_continuation_manifest(agnt, runtime, capsys):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    cp = checkpoint(agnt, runtime, capsys)
    before = (runtime["store"].root / "journal.json").read_bytes()
    assert agnt.main(["work", "transition-check", "pi-a", "--mode", "resume", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"]]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ready"
    assert result["launch"] == "host-required"
    assert (runtime["store"].root / "journal.json").read_bytes() == before


@pytest.mark.parametrize("native,cancelling", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("runtime", [{"effects": ["repo-write", "work-transition", "beads-write", "worktree-create"]}], indirect=True)
def test_crash_before_child_path_has_source_checked_repair(agnt, runtime, capsys, monkeypatch, native, cancelling):
    from agnt_lib import delivery, work_lifecycle
    receipts = delivery.DeliveryStore(runtime["root"] / "receipts", authority=runtime["permission"])
    monkeypatch.setattr(work_lifecycle, "delivery_store", lambda: receipts)
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    cp = checkpoint(agnt, runtime, capsys)
    original = runtime["store"].reserve_child_file
    def crash(*_args, **_kwargs):
        raise SystemExit("fixture crash before child path")
    monkeypatch.setattr(runtime["store"], "reserve_child_file", crash)
    with pytest.raises(SystemExit, match="fixture crash"):
        prepare(agnt, runtime, cp, capsys, target="pi-b" if native else "pi-a")
    monkeypatch.setattr(runtime["store"], "reserve_child_file", original)
    tx = runtime["store"].pending_transition("session-a")
    assert tx["childSessionFile"] is None
    if cancelling:
        def interrupted(_tx):
            raise SystemExit("fixture cancellation interruption")
        with pytest.raises(SystemExit):
            runtime["store"].cancel(tx["id"], source_session="session-a", settle_isolation=interrupted)
        runtime["permission"].revoke("cancel after revocation")
    args = ["work", "transition-bind-child", tx["id"], "--session-id", "session-a"]
    assert agnt.main(args) == 0
    repaired = json.loads(capsys.readouterr().out)["transition"]
    assert repaired["id"] == tx["id"] and repaired["childSession"] == tx["childSession"]
    assert repaired["state"] == tx["state"]
    assert Path(repaired["childSessionFile"]).is_absolute()
    assert not Path(repaired["childSessionFile"]).exists()
    assert not receipts.root.exists()
    assert agnt.main(args) == 0
    assert json.loads(capsys.readouterr().out)["transition"]["childSessionFile"] == repaired["childSessionFile"]


def test_child_path_repair_rejects_copied_source_identity(agnt, runtime, capsys, monkeypatch):
    assert runtime["work"].direct_start("pi-a", claim=False)["status"] == "started"
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys)
    before = (runtime["store"].root / "journal.json").read_bytes()
    monkeypatch.setenv("PI_SESSION_ID", "foreign-session")
    assert agnt.main(["work", "transition-bind-child", tx["id"], "--session-id", "session-a"]) != 0
    capsys.readouterr()
    assert (runtime["store"].root / "journal.json").read_bytes() == before
