"""Automatic isolation through real Git and private continuation journals."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_work_continuation import checkpoint, prepare, runtime, stage  # noqa: F401

pytestmark = pytest.mark.parametrize("runtime", [{"effects": ["repo-write", "work-transition", "beads-write", "worktree-create"]}], indirect=True)


@pytest.fixture
def isolation(runtime, monkeypatch):
    from agnt_lib import delivery, work_lifecycle
    receipts = delivery.DeliveryStore(runtime["root"] / "receipts", authority=runtime["permission"])
    monkeypatch.setattr(work_lifecycle, "delivery_store", lambda: receipts, raising=False)
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    (runtime["repo"] / "unfinished.txt").write_text("preserve source")
    return {**runtime, "receipts": receipts}


def test_cancellation_waits_for_receipt_publication(agnt, isolation, runtime, capsys, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    cp = checkpoint(agnt, runtime, capsys)
    entered, release, cancelling, cancelled = Event(), Event(), Event(), Event()
    original_prepare, original_execute = isolation["receipts"].prepare, isolation["receipts"].execute
    seen = {}

    def paused_prepare(*args, **kwargs):
        state = json.loads((isolation["store"].root / "journal.json").read_text())["state"]
        seen["tx"] = next(tx for tx in state["transitions"].values() if tx["state"] == "isolating")
        entered.set()
        assert release.wait(5), "fixture publication release timed out"
        return original_prepare(*args, **kwargs)

    def wait_before_effect(*args, **kwargs):
        assert cancelled.wait(5), "fixture cancellation did not settle"
        return original_execute(*args, **kwargs)

    def cancel():
        cancelling.set()
        try:
            return agnt.main(["work", "transition-cancel", seen["tx"]["id"], "--session-id", "session-a"])
        finally:
            cancelled.set()

    monkeypatch.setattr(isolation["receipts"], "prepare", paused_prepare)
    monkeypatch.setattr(isolation["receipts"], "execute", wait_before_effect)
    with ThreadPoolExecutor(max_workers=2) as pool:
        advancing = pool.submit(agnt.main, ["work", "transition-prepare", "pi-b", "--mode", "switch",
                                          "--session-id", "session-a", "--checkpoint-ref", cp["id"], "--runtime-ready"])
        try:
            assert entered.wait(5)
            cancellation = pool.submit(cancel)
            assert cancelling.wait(5)
            assert not cancelled.wait(0.2), "cancellation released ownership before receipt publication settled"
        finally:
            release.set()
        assert cancellation.result(timeout=5) == 0
        assert advancing.result(timeout=5) != 0
    capsys.readouterr()
    tx = isolation["store"].status(seen["tx"]["id"])
    assert tx["state"] == "cancelled" and tx["isolationSettlement"]["status"] == "cancelled"
    assert isolation["store"].owner("pi-b") is None
    assert isolation["receipts"].inspect(tx["isolationSettlement"]["receipt"])["status"] == "cancelled"
    assert not Path(tx["targetCheckout"]).exists()


@pytest.mark.parametrize("project_local_quality", [False, True])
def test_native_attachment_uses_source_quality_ledger(agnt, runtime, capsys, monkeypatch, project_local_quality):
    import subprocess
    from agnt_lib import delivery, runtime_paths, work_lifecycle

    repo = runtime["repo"]
    if project_local_quality:
        (repo / ".gitignore").write_text(".pi/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fixture ignored runtime"], cwd=repo, check=True, capture_output=True)
    monkeypatch.setattr(runtime["quality"], "resolve_runtime_directory", runtime_paths.resolve_runtime_directory)
    receipts = delivery.DeliveryStore(runtime["root"] / "real-resolver-receipts", authority=runtime["permission"])
    monkeypatch.setattr(work_lifecycle, "delivery_store", lambda: receipts)
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    source_quality = runtime_paths.resolve_runtime_directory("quality")
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys, target="pi-b")
    stage(agnt, tx, capsys)
    monkeypatch.chdir(tx["targetCheckout"])
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    with pytest.raises(ValueError, match="pending transition"):
        runtime["quality"].capture_session_outcome("session-a", "pi-a", "success", directory=source_quality,
                                                  beads_runner=runtime["work"].run_beads_json)
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
    assert json.loads(capsys.readouterr().out)["transition"]["state"] == "attached"
    assert runtime["quality"].session_attempt_state("session-a", directory=source_quality) == {"beadId": "pi-a", "outcome": None}
    assert runtime["quality"].session_attempt_state(tx["childSession"])["beadId"] == "pi-b"


def test_existing_target_checks_its_local_legacy_ledger(agnt, runtime, capsys, monkeypatch):
    import subprocess
    from agnt_lib import runtime_paths

    for checkout in (runtime["repo"], runtime["other"]):
        (checkout / ".gitignore").write_text(".pi/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=checkout, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fixture local runtime"], cwd=checkout, check=True, capture_output=True)
    monkeypatch.setattr(runtime["quality"], "resolve_runtime_directory", runtime_paths.resolve_runtime_directory)
    runtime["quality"].capture_session_link("legacy-target", "pi-b", beads_runner=runtime["work"].run_beads_json,
                                           directory=runtime_paths.resolve_runtime_directory("quality", cwd=runtime["other"]))
    assert runtime["work"].direct_start("pi-a", claim=True)["status"] == "started"
    cp = checkpoint(agnt, runtime, capsys)
    assert agnt.main(["work", "transition-check", "pi-b", "--mode", "switch", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"], "--checkout", str(runtime["other"])]) != 0
    assert "legacy ownership" in capsys.readouterr().out
    assert runtime["store"].owner("pi-b") is None


def test_missing_checkout_readiness_has_no_mutations(agnt, isolation, runtime, capsys):
    cp = checkpoint(agnt, runtime, capsys)
    assert agnt.main(["work", "transition-check", "pi-b", "--mode", "switch", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"]]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "needs-isolation"
    assert not Path(result["target"]["checkout"]).exists()
    assert isolation["store"].pending_transition("session-a") is None
    assert not isolation["receipts"].root.exists()


def test_automatic_worktree_is_reserved_before_native_effect(agnt, isolation, runtime, capsys, monkeypatch):
    from agnt_lib.worktree_policy import WorktreeCreationAdapter
    cp = checkpoint(agnt, runtime, capsys)
    execute = WorktreeCreationAdapter.execute
    calls = []
    def checked(self, action, *, lease_fds):
        owner = isolation["store"].owner("pi-b")
        assert owner["phase"] == "reserved" and owner["checkout"] == action["facts"]["checkout"]
        assert isolation["store"].owner("pi-a")["phase"] == "active"
        calls.append(action["facts"]["checkout"])
        return execute(self, action, lease_fds=lease_fds)
    monkeypatch.setattr(WorktreeCreationAdapter, "execute", checked)
    tx = prepare(agnt, runtime, cp, capsys, target="pi-b")
    assert tx["state"] == "prepared"
    assert isolation["receipts"].inspect(tx["isolation"]["receipt"])["status"] == "applied"
    assert len(calls) == 1
    # Exact source retry discovers its reservation, not a second worktree/receipt.
    assert prepare(agnt, runtime, cp, capsys, target="pi-b")["id"] == tx["id"]
    assert len(calls) == 1
    stage(agnt, tx, capsys)
    monkeypatch.chdir(tx["targetCheckout"])
    monkeypatch.setenv("PI_SESSION_ID", tx["childSession"])
    monkeypatch.setenv("PI_SESSION_FILE", tx["childSessionFile"])
    assert agnt.main(["work", "transition-attach", tx["id"], "--session-id", tx["childSession"]]) == 0
    capsys.readouterr()
    assert isolation["quality"].session_work_item(tx["childSession"]) == "pi-b"
    assert (isolation["repo"] / "unfinished.txt").read_text() == "preserve source"


def test_applied_creation_crash_recovers_without_replay(agnt, isolation, runtime, capsys, monkeypatch):
    cp = checkpoint(agnt, runtime, capsys)
    complete = isolation["store"].complete_isolation
    def crash(*args, **kwargs):
        raise SystemExit("fixture crash after creation")
    monkeypatch.setattr(isolation["store"], "complete_isolation", crash)
    with pytest.raises(SystemExit, match="fixture crash"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    tx = isolation["store"].pending_transition("session-a")
    assert tx["state"] == "isolating"
    ref = tx["isolation"]["receipt"]
    assert isolation["receipts"].inspect(ref)["status"] == "applied"
    monkeypatch.setattr(isolation["store"], "complete_isolation", complete)
    assert agnt.main(["work", "transition-isolate", tx["id"], "--session-id", "session-a"]) == 0
    recovered = json.loads(capsys.readouterr().out)["transition"]
    assert recovered["state"] == "prepared" and recovered["childSession"] == tx["childSession"]
    assert sum(event["phase"] == "started" for event in isolation["receipts"].inspect(ref)["receipt"]["events"]) == 1


def test_failed_lifecycle_reservation_cannot_orphan_delivery_receipt(agnt, isolation, runtime, capsys, monkeypatch):
    cp = checkpoint(agnt, runtime, capsys)
    def crash(*args, **kwargs):
        raise SystemExit("fixture lifecycle persistence failure")
    monkeypatch.setattr(isolation["store"], "prepare", crash)
    with pytest.raises(SystemExit, match="persistence failure"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    assert not isolation["receipts"].root.exists()
    assert isolation["store"].owner("pi-b") is None


def test_changed_native_plan_cannot_orphan_mismatched_receipt(agnt, isolation, runtime, capsys, monkeypatch):
    from agnt_lib.worktree_policy import WorktreeCreationAdapter
    import subprocess
    cp = checkpoint(agnt, runtime, capsys)
    resolve = WorktreeCreationAdapter.resolve
    calls = 0
    def moved_source(self):
        nonlocal calls
        calls += 1
        if calls == 2:
            subprocess.run(["git", "-C", str(isolation["repo"]), "-c", "user.name=Test", "-c", "user.email=test@example.test",
                            "commit", "--allow-empty", "-qm", "fixture concurrent source move"], check=True)
        return resolve(self)
    monkeypatch.setattr(WorktreeCreationAdapter, "resolve", moved_source)
    assert agnt.main(["work", "transition-prepare", "pi-b", "--mode", "switch", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"], "--runtime-ready"]) != 0
    capsys.readouterr()
    assert not (isolation["receipts"].root / "state.json").exists()
    tx = isolation["store"].pending_transition("session-a")
    assert tx["state"] == "isolating" and tx["isolation"]["receipt"] is None


def test_receipt_binding_crash_reuses_unissued_receipt(agnt, isolation, runtime, capsys, monkeypatch):
    cp = checkpoint(agnt, runtime, capsys)
    publish = isolation["receipts"].prepare
    def crash(*args, **kwargs):
        publish(*args, **kwargs)
        raise SystemExit("fixture crash before receipt binding")
    monkeypatch.setattr(isolation["receipts"], "prepare", crash)
    with pytest.raises(SystemExit, match="before receipt binding"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    tx = isolation["store"].pending_transition("session-a")
    assert tx["isolation"]["receipt"] is None and not Path(tx["targetCheckout"]).exists()
    refs = list(json.loads((isolation["receipts"].root / "state.json").read_text())["state"]["receipts"])
    assert len(refs) == 1
    monkeypatch.setattr(isolation["receipts"], "prepare", publish)
    assert agnt.main(["work", "transition-isolate", tx["id"], "--session-id", "session-a"]) == 0
    recovered = json.loads(capsys.readouterr().out)["transition"]
    assert recovered["isolation"]["receipt"] == refs[0]


def test_revoked_isolation_reconciles_started_effect_without_launch(agnt, isolation, runtime, capsys, monkeypatch):
    from agnt_lib.worktree_policy import WorktreeCreationAdapter
    cp = checkpoint(agnt, runtime, capsys)
    execute = WorktreeCreationAdapter.execute
    def crash(self, action, *, lease_fds):
        execute(self, action, lease_fds=lease_fds)
        raise SystemExit("fixture crash after native writer exits")
    monkeypatch.setattr(WorktreeCreationAdapter, "execute", crash)
    with pytest.raises(SystemExit, match="writer exits"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    tx = isolation["store"].pending_transition("session-a")
    ref = tx["isolation"]["receipt"]
    assert isolation["receipts"].inspect(ref)["status"] == "started"
    isolation["permission"].revoke("fixture stop queued work")
    assert agnt.main(["work", "transition-isolate", tx["id"], "--session-id", "session-a"]) != 0
    capsys.readouterr()
    assert isolation["receipts"].inspect(ref)["status"] == "applied"
    assert isolation["store"].status(tx["id"])["state"] == "isolating"
    assert isolation["store"].owner("pi-a")["phase"] == "active"
    assert not Path(tx["childSessionFile"]).exists()


def test_native_branch_switch_after_preparation_blocks_staging(agnt, isolation, runtime, capsys):
    import subprocess
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys, target="pi-b")
    subprocess.run(["git", "-C", tx["targetCheckout"], "switch", "-qc", "foreign-unoccupied-branch"], check=True)
    Path(tx["childSessionFile"]).parent.mkdir(mode=0o700, exist_ok=True)
    Path(tx["childSessionFile"]).write_text(json.dumps({"type": "session", "id": tx["childSession"],
        "cwd": tx["targetCheckout"], "parentSession": tx["sourceSessionFile"]}) + "\n")
    assert agnt.main(["work", "transition-stage", tx["id"], "--session-id", "session-a"]) != 0
    capsys.readouterr()
    assert isolation["store"].owner("pi-a")["phase"] == "active"


def test_index_only_change_after_preparation_blocks_staging(agnt, isolation, runtime, capsys):
    import subprocess
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys, target="pi-b")
    foreign = Path(tx["targetCheckout"]) / "foreign.txt"
    foreign.write_text("fixture staged content")
    subprocess.run(["git", "-C", tx["targetCheckout"], "add", "foreign.txt"], check=True)
    foreign.unlink()
    Path(tx["childSessionFile"]).parent.mkdir(mode=0o700, exist_ok=True)
    Path(tx["childSessionFile"]).write_text(json.dumps({"type": "session", "id": tx["childSession"],
        "cwd": tx["targetCheckout"], "parentSession": tx["sourceSessionFile"]}) + "\n")
    assert agnt.main(["work", "transition-stage", tx["id"], "--session-id", "session-a"]) != 0
    capsys.readouterr()
    assert isolation["store"].owner("pi-a")["phase"] == "active"


def test_snapshot_hashes_material_files_hidden_by_index_flags(isolation):
    import subprocess
    from agnt_lib.work_lifecycle import workspace_snapshot
    repo = isolation["repo"]
    watched = repo / "watched.txt"
    watched.write_text("fixture committed content")
    subprocess.run(["git", "-C", str(repo), "add", "watched.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.test",
                    "commit", "-qm", "fixture tracked file"], check=True)
    subprocess.run(["git", "-C", str(repo), "update-index", "--assume-unchanged", "watched.txt"], check=True)
    before = workspace_snapshot(str(repo))
    watched.write_text("fixture changed content")
    assert workspace_snapshot(str(repo)) != before


def test_cancel_crash_does_not_restart_unbound_effect(agnt, isolation, runtime, capsys, monkeypatch):
    cp = checkpoint(agnt, runtime, capsys)
    publish, cancel = isolation["receipts"].prepare, isolation["receipts"].cancel

    def unbound(*args, **kwargs):
        publish(*args, **kwargs)
        raise SystemExit("fixture unbound publication")

    monkeypatch.setattr(isolation["receipts"], "prepare", unbound)
    with pytest.raises(SystemExit, match="unbound publication"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    monkeypatch.setattr(isolation["receipts"], "prepare", publish)
    tx = isolation["store"].pending_transition("session-a")

    def interrupted_cancel(*args, **kwargs):
        cancel(*args, **kwargs)
        raise SystemExit("fixture after receipt cancellation")

    monkeypatch.setattr(isolation["receipts"], "cancel", interrupted_cancel)
    with pytest.raises(SystemExit, match="after receipt cancellation"):
        agnt.main(["work", "transition-cancel", tx["id"], "--session-id", "session-a"])
    monkeypatch.setattr(isolation["receipts"], "cancel", cancel)
    assert agnt.main(["work", "transition-isolate", tx["id"], "--session-id", "session-a"]) != 0
    capsys.readouterr()
    assert not Path(tx["targetCheckout"]).exists()
    assert len(json.loads((isolation["receipts"].root / "state.json").read_text())["state"]["receipts"]) == 1
    assert agnt.main(["work", "transition-cancel", tx["id"], "--session-id", "session-a"]) == 0
    capsys.readouterr()
    assert isolation["store"].owner("pi-b") is None


def test_cancel_unbound_unissued_receipt_after_revocation(agnt, isolation, runtime, capsys, monkeypatch):
    cp = checkpoint(agnt, runtime, capsys)
    publish = isolation["receipts"].prepare
    def crash(*args, **kwargs):
        publish(*args, **kwargs)
        raise SystemExit("fixture before binding")
    monkeypatch.setattr(isolation["receipts"], "prepare", crash)
    with pytest.raises(SystemExit, match="before binding"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    tx = isolation["store"].pending_transition("session-a")
    refs = list(json.loads((isolation["receipts"].root / "state.json").read_text())["state"]["receipts"])
    isolation["permission"].revoke("fixture revoke before cancellation")
    assert agnt.main(["work", "transition-cancel", tx["id"], "--session-id", "session-a"]) == 0
    capsys.readouterr()
    assert isolation["store"].owner("pi-b") is None
    assert isolation["store"].owner("pi-a")["phase"] == "active"
    assert isolation["receipts"].inspect(refs[0])["status"] == "cancelled"
    assert not Path(tx["targetCheckout"]).exists()


def test_unknown_creation_cannot_release_reserved_target(agnt, isolation, runtime, capsys, monkeypatch):
    from agnt_lib.worktree_policy import WorktreeCreationAdapter
    cp = checkpoint(agnt, runtime, capsys)
    def crash(*args, **kwargs):
        raise SystemExit("fixture ambiguous native submission")
    monkeypatch.setattr(WorktreeCreationAdapter, "execute", crash)
    with pytest.raises(SystemExit, match="ambiguous native submission"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    tx = isolation["store"].pending_transition("session-a")
    # No absent path alone proves that an unknown writer cannot finish later.
    monkeypatch.setattr(WorktreeCreationAdapter, "observe", lambda self, action, **kwargs: {
        "status": "uncertain", "targetIdentity": action["target"]["identity"],
        "sourceIdentity": action["source"]["identity"], "evidenceRefs": ["fixture:writer-unknown"],
    })
    assert agnt.main(["work", "transition-cancel", tx["id"], "--session-id", "session-a"]) != 0
    capsys.readouterr()
    assert isolation["store"].owner("pi-b")["phase"] == "reserved"
    assert isolation["store"].status(tx["id"])["state"] == "isolating"


def test_pending_isolation_blocks_closeout_before_outcome(agnt, isolation, runtime, capsys, monkeypatch):
    cp = checkpoint(agnt, runtime, capsys)
    def crash(*args, **kwargs):
        raise SystemExit("fixture before receipt binding")
    monkeypatch.setattr(isolation["store"], "bind_isolation_receipt", crash)
    with pytest.raises(SystemExit, match="before receipt binding"):
        prepare(agnt, runtime, cp, capsys, target="pi-b")
    def no_outcome(*args, **kwargs):
        pytest.fail("pending native effect must be settled before recording final success")
    monkeypatch.setattr(isolation["work"], "record_current_session_outcome", no_outcome)
    result = isolation["work"].direct_closeout("pi-a", outcome="success", reason="fixture")
    assert result["status"] == "error"
    assert "pending transition" in result["stages"]["ownership"]["error"]


@pytest.mark.parametrize("command", ["transition-stage", "transition-cancel"])
def test_copied_source_flags_cannot_mutate_foreign_session(agnt, isolation, runtime, capsys, monkeypatch, command):
    tx = prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys, target="pi-b")
    Path(tx["childSessionFile"]).parent.mkdir(mode=0o700, exist_ok=True)
    Path(tx["childSessionFile"]).write_text(json.dumps({"type": "session", "id": tx["childSession"],
        "cwd": tx["targetCheckout"], "parentSession": tx["sourceSessionFile"]}) + "\n")
    foreign = isolation["root"] / "foreign-session.jsonl"
    foreign.write_text(json.dumps({"type": "session", "id": "foreign", "cwd": str(isolation["repo"])}) + "\n")
    monkeypatch.setenv("PI_SESSION_ID", "foreign")
    monkeypatch.setenv("PI_SESSION_FILE", str(foreign))
    assert agnt.main(["work", command, tx["id"], "--session-id", "session-a"]) != 0
    capsys.readouterr()
    assert isolation["store"].status(tx["id"])["state"] == "prepared"
    assert isolation["store"].owner("pi-a")["phase"] == "active"


def test_successful_source_cannot_prepare_unfinished_continuation(agnt, isolation, runtime, capsys):
    cp = checkpoint(agnt, runtime, capsys)
    isolation["quality"].capture_session_outcome("session-a", "pi-a", "success", beads_runner=isolation["work"].run_beads_json)
    assert agnt.main(["work", "transition-prepare", "pi-b", "--mode", "switch", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"], "--runtime-ready"]) != 0
    capsys.readouterr()
    assert isolation["store"].pending_transition("session-a") is None
    assert isolation["store"].owner("pi-b") is None


def test_success_between_readiness_and_reservation_blocks_creation(agnt, isolation, runtime, capsys, monkeypatch):
    cp = checkpoint(agnt, runtime, capsys)
    original = isolation["store"].prepare

    def finish_before_reservation(**kwargs):
        isolation["quality"].capture_session_outcome("session-a", "pi-a", "success",
                                                    beads_runner=isolation["work"].run_beads_json)
        return original(**kwargs)

    monkeypatch.setattr(isolation["store"], "prepare", finish_before_reservation)
    assert agnt.main(["work", "transition-prepare", "pi-b", "--mode", "switch", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"], "--runtime-ready"]) != 0
    capsys.readouterr()
    assert isolation["store"].pending_transition("session-a") is None
    assert isolation["store"].owner("pi-b") is None
    assert not list(isolation["receipts"].root.glob("*.json"))


def test_success_and_reservation_share_lifecycle_lock(agnt, isolation, runtime, capsys, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from agnt_lib import work_lifecycle

    cp = checkpoint(agnt, runtime, capsys)
    entered, release, recording, raw_recording = Event(), Event(), Event(), Event()
    raw = isolation["quality"]._capture_session_outcome

    def observed_record(*args, **kwargs):
        raw_recording.set()
        return raw(*args, **kwargs)

    def authorize(request):
        entered.set()
        assert release.wait(5), "fixture reservation release timed out"
        return work_lifecycle._transition_authorized(request)

    def finish():
        recording.set()
        return isolation["quality"].capture_session_outcome("session-a", "pi-a", "success",
                                                           beads_runner=isolation["work"].run_beads_json)

    monkeypatch.setattr(isolation["quality"], "_capture_session_outcome", observed_record)
    with ThreadPoolExecutor(max_workers=2) as pool:
        prepared = pool.submit(isolation["store"].prepare, source_session="session-a", checkpoint_ref=cp["id"],
                               target_bead="pi-a", target_checkout=str(isolation["repo"]),
                               target_status="in_progress", blockers=[], mode="resume", runtime_ready=True,
                               source_quality_directory=str(isolation["quality"].resolve_runtime_directory("quality").resolve()),
                               authorize=authorize)
        try:
            assert entered.wait(5)
            finished = pool.submit(finish)
            assert recording.wait(5)
            assert not raw_recording.wait(0.2), "success crossed the held reservation lock"
        finally:
            release.set()
        assert prepared.result(timeout=5)["state"] == "prepared"
        with pytest.raises(ValueError, match="pending transition"):
            finished.result(timeout=5)
    assert isolation["quality"].session_attempt_state("session-a")["outcome"] is None


def test_wrong_checkout_closeout_cannot_record_success(isolation, monkeypatch):
    monkeypatch.chdir(isolation["other"])
    result = isolation["work"].direct_closeout("pi-a", outcome="success", reason="fixture wrong checkout")
    assert result["status"] == "error"
    assert isolation["quality"].session_attempt_state("session-a")["outcome"] is None
    assert isolation["store"].owner("pi-a")["phase"] == "active"


def test_closeout_git_ignores_inherited_repository_redirect(isolation, monkeypatch):
    import subprocess

    foreign = isolation["root"] / "foreign"
    subprocess.run(["git", "init", str(foreign)], check=True, capture_output=True)
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(foreign))
    result = isolation["work"]._git(isolation["repo"], ["rev-parse", "--show-toplevel"])
    assert result.returncode == 0
    assert Path(result.stdout.strip()).resolve() == isolation["repo"].resolve()


def test_dirty_closeout_preflight_preserves_unfinished_outcome(isolation):
    import subprocess

    repo = isolation["repo"]
    (repo / ".beads").mkdir(exist_ok=True)
    (repo / ".beads" / "issues.jsonl").write_text("{}\n")
    (repo / "owned.txt").write_text("base\n")
    subprocess.run(["git", "add", ".beads/issues.jsonl", "owned.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)
    (repo / "owned.txt").write_text("unfinished\n")
    result = isolation["work"].direct_closeout("pi-a", outcome="success", reason="fixture dirty checkout")
    assert result["status"] == "error"
    assert result["repair"]["failedStage"] == "preflight"
    assert isolation["quality"].session_attempt_state("session-a")["outcome"] is None
    assert (repo / "owned.txt").read_text() == "unfinished\n"


def test_distinct_telemetry_ledger_does_not_finalize_execution(agnt, isolation, runtime, capsys):
    quality = isolation["quality"]
    archive = isolation["root"] / "telemetry-sample"
    quality.capture_session_link("session-a", "pi-a", directory=archive,
                                 beads_runner=isolation["work"].run_beads_json)
    prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys, target="pi-b")
    quality.capture_session_outcome("session-a", "pi-a", "success", directory=archive,
                                    beads_runner=isolation["work"].run_beads_json)
    assert quality.session_attempt_state("session-a", directory=archive)["outcome"] == "success"
    assert quality.session_attempt_state("session-a")["outcome"] is None


def test_explicit_canonical_quality_path_cannot_bypass_pending_transition(agnt, isolation, runtime, capsys):
    prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys, target="pi-b")
    quality = isolation["quality"]
    with pytest.raises(ValueError, match="pending transition"):
        quality.capture_session_outcome("session-a", "pi-a", "success",
                                        directory=quality.resolve_runtime_directory("quality"),
                                        beads_runner=isolation["work"].run_beads_json)
    assert quality.session_attempt_state("session-a")["outcome"] is None


def test_pending_transition_blocks_direct_quality_success(agnt, isolation, runtime, capsys):
    prepare(agnt, runtime, checkpoint(agnt, runtime, capsys), capsys, target="pi-b")
    with pytest.raises(ValueError, match="pending transition"):
        isolation["quality"].capture_session_outcome("session-a", "pi-a", "success", beads_runner=isolation["work"].run_beads_json)
    assert isolation["quality"].session_attempt_state("session-a")["outcome"] is None


def test_runtime_preflight_prevents_native_creation(agnt, isolation, runtime, capsys):
    cp = checkpoint(agnt, runtime, capsys)
    assert agnt.main(["work", "transition-prepare", "pi-b", "--mode", "switch", "--session-id", "session-a",
                      "--checkpoint-ref", cp["id"]]) != 0
    capsys.readouterr()
    assert isolation["store"].pending_transition("session-a") is None
    assert not isolation["receipts"].root.exists()
