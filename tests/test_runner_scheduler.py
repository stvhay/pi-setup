from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib import runner_protocol as rp
from agnt_lib.runner import save_runner_state
from agnt_lib.runner_scheduler import load_scheduler_state, runner_scheduler_tick, save_scheduler_state
from agnt_lib.runs import create_run_bundle, load_yaml_json, update_run_result


VALID_REVIEW_META = {
    "pi": {
        "action": "review",
        "routingTask": "review",
        "allowedEffects": ["read_workspace", "write_artifacts"],
        "modelPolicy": {"mode": "auto"},
        "sessionPolicy": "recorded",
        "memoryPolicy": "auto",
    }
}

VALID_IMPLEMENT_META = {
    "pi": {
        "action": "implement",
        "routingTask": "implementation",
        "approved": True,
        "humanApproval": {"decisionBead": "pi-approval.1", "resolver": {"kind": "human-ui", "sessionId": "pi-session-1"}},
        "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
        "modelPolicy": {"mode": "auto"},
        "epicId": "pi-epic",
        "worktreePolicy": "existing-worktree",
        "writeSet": ["src/shared.py"],
        "closeout": {
            "requiresEvidence": True,
            "requiresResolvedApprovals": True,
            "requiresFollowUpsReconciled": True,
        },
        "sessionPolicy": "recorded",
        "memoryPolicy": "auto",
    }
}


def _ready(*items: dict):
    def fake_beads(args):
        if args == ["ready"]:
            return 0, list(items), ""
        if len(args) >= 4 and args[0] == "dep":
            return 0, {"dependency": args}, ""
        raise AssertionError(args)

    return fake_beads


def _review_bead(bead_id: str) -> dict:
    return {"id": bead_id, "title": f"Review {bead_id}", "issue_type": "task", "status": "open", "metadata": json.dumps(VALID_REVIEW_META)}


def _implement_bead(bead_id: str) -> dict:
    return {
        "id": bead_id,
        "title": f"Implement {bead_id}",
        "issue_type": "task",
        "status": "open",
        "acceptance_criteria": "tests pass",
        "metadata": json.dumps(VALID_IMPLEMENT_META),
    }


def test_scheduler_respects_concurrency_and_cleans_active_snapshots(tmp_path):
    save_runner_state(tmp_path, {"concurrency": 2})
    started = []

    def fake_start(bead, **kwargs):
        started.append(bead["id"])
        active_files = sorted((tmp_path / ".pi" / "runner" / "active").glob("*.json"))
        active_docs = [json.loads(path.read_text(encoding="utf-8")) for path in active_files]
        matching = [doc for doc in active_docs if doc["bead"] == bead["id"]]
        assert matching
        assert matching[0]["liveLogPath"].endswith("/live/session.jsonl")
        assert matching[0]["liveStatusPath"].endswith("/live/status.json")
        assert matching[0]["lessonsPath"].endswith("/artifacts/lessons.md")
        assert matching[0]["handoffPath"].endswith("/artifacts/handoff.md")
        state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
        assert any(run["bead"] == bead["id"] and run.get("liveLogPath") for run in state["activeRuns"])
        return {"started": {"bundle": str(tmp_path / "runs" / bead["id"]), "dispatch": {"bead": bead["id"]}}, "invoked": {"exitCode": 0}}

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=3,
        beads_runner=_ready(_review_bead("pi-ready.1"), _review_bead("pi-ready.2"), _review_bead("pi-ready.3")),
        runner_start=fake_start,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert started == ["pi-ready.1", "pi-ready.2"]
    assert [action["action"] for action in result["actions"]] == ["started", "started", "deferred_concurrency"]
    assert list((tmp_path / ".pi" / "runner" / "active").glob("*.json")) == []
    final_state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
    assert final_state["activeRuns"] == []


def test_scheduler_skips_duplicate_active_bead_and_does_not_start_when_draining(tmp_path):
    save_runner_state(tmp_path, {"activeRuns": [{"bead": "pi-ready.1", "runId": "run-existing", "status": "running"}]})
    calls = []

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.1")),
        runner_start=lambda bead, **kwargs: calls.append(bead),
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert calls == []
    assert result["actions"][0]["action"] == "already_active"

    save_runner_state(tmp_path, {"draining": True, "activeRuns": [{"bead": "pi-ready.2", "runId": "run-existing", "status": "running"}]})
    draining = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.2")),
        runner_start=lambda bead, **kwargs: calls.append(bead),
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert draining["skippedReason"] == "runner draining"
    assert calls == []


def test_scheduler_records_retry_backoff_and_retry_exhaustion(tmp_path):
    now = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
    attempts = []

    def failing_start(bead, **kwargs):
        attempts.append(bead["id"])
        raise RuntimeError("provider unavailable")

    first = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.1")),
        runner_start=failing_start,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        now=now,
    )
    assert first["actions"][0]["action"] == "start_failed"
    assert len(attempts) == 1

    deferred = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.1")),
        runner_start=failing_start,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        now=now + timedelta(seconds=10),
    )
    assert deferred["actions"][0]["action"] == "retry_deferred"
    assert len(attempts) == 1

    second = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.1")),
        runner_start=failing_start,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        now=now + timedelta(seconds=61),
    )
    assert second["actions"][0]["action"] == "start_failed"
    assert len(attempts) == 2

    exhausted = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.1")),
        runner_start=failing_start,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        now=now + timedelta(seconds=122),
    )
    assert exhausted["actions"][0]["action"] == "retry_exhausted"
    assert len(attempts) == 2

    state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
    assert state["attempts"]["pi-ready.1"]["count"] == 2
    assert state["attempts"]["pi-ready.1"]["lastError"] == "provider unavailable"


def test_scheduler_state_save_preserves_newer_service_pause_control(tmp_path):
    save_runner_state(tmp_path, {"paused": True, "pauseReason": "operator", "activeRuns": [{"bead": "pi-active", "runId": "run-active"}]})

    save_scheduler_state(
        tmp_path,
        {"paused": False, "activeRuns": [], "attempts": {"pi-ready": {"count": 1}}},
        now=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
    )

    state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
    assert state["paused"] is True
    assert state["pauseReason"] == "operator"
    assert state["activeRuns"] == []
    assert state["attempts"]["pi-ready"]["count"] == 1


def test_scheduler_treats_runner_error_dictionary_as_start_failure(tmp_path):
    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.1")),
        runner_start=lambda _bead, **_kwargs: {"error": "claim rejected", "reason": "bead already claimed"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        now=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
    )

    assert result["actions"][0]["action"] == "start_failed"
    assert "claim rejected" in result["actions"][0]["error"]
    state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
    assert state["attempts"]["pi-ready.1"]["count"] == 1


def test_scheduler_serializes_conflicting_writes_against_active_runs(tmp_path):
    save_runner_state(
        tmp_path,
        {"activeRuns": [{"bead": "pi-active.1", "epicId": "pi-epic", "writeSet": ["src/shared.py"], "runId": "run-active"}]},
    )

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=True,
        limit=1,
        beads_runner=_ready(_implement_bead("pi-ready.1")),
        runner_start=lambda bead, **kwargs: (_ for _ in ()).throw(AssertionError("should not start")),
        worktree_resolver=lambda _bead, _validation: {"dispatchable": True, "status": "ready", "policy": "existing-worktree"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert result["actions"][0]["action"] == "would_add_dependency"
    assert result["actions"][0]["blockedBy"] == "pi-active.1"
    assert result["actions"][0]["overlap"] == ["src/shared.py"]


def test_scheduler_dispatches_using_metadata_action_not_title_inference(tmp_path):
    started = []

    def fake_start(bead, **kwargs):
        started.append(kwargs)
        return {"started": {"bundle": str(tmp_path / "runs" / bead["id"]), "dispatch": {"bead": bead["id"]}}, "invoked": {"exitCode": 0}}

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready({**_implement_bead("pi-ready.1"), "title": "Execute critical harness fix"}),
        runner_start=fake_start,
        worktree_resolver=lambda _bead, _validation: {"dispatchable": True, "status": "ready", "policy": "epic-worktree"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert result["actions"][0]["action"] == "started"
    assert started[0]["action_id"] == "implement"
    assert started[0]["close_bead"] is False


def test_scheduler_checkpoints_approved_dirty_epic_worktree_before_dependent_start(tmp_path):
    bead = _implement_bead("pi-ready.2")
    metadata = json.loads(bead["metadata"])
    metadata["pi"]["worktreePolicy"] = "epic-worktree"
    metadata["pi"]["continuation"] = {"mode": "checkpoint", "predecessor": "pi-ready.1", "approvalRef": "pi-5eu"}
    bead["metadata"] = json.dumps(metadata)
    snapshots = iter([
        {"dispatchable": False, "status": "checkpoint-required", "path": str(tmp_path), "continuation": metadata["pi"]["continuation"]},
        {"dispatchable": True, "status": "ready", "path": str(tmp_path)},
    ])
    checkpoints = []

    def fake_start(item, **kwargs):
        bundle = create_run_bundle(
            action="implement",
            routing_task="implementation",
            bead=item["id"],
            approval_refs=["pi-5eu"],
            continuation=metadata["pi"]["continuation"],
            runs_dir=tmp_path / "runs",
            id_value=kwargs["id_value"],
        )
        return {"started": {"bundle": str(bundle)}}

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(bead),
        runner_start=fake_start,
        worktree_resolver=lambda _bead, _validation: next(snapshots),
        checkpoint_handler=lambda worktree, item, validation: checkpoints.append((worktree, item["id"], validation)) or {"ok": True, "checkpointSha": "checkpoint-sha", "baselineSha": "baseline-sha", "approvalRef": "pi-5eu"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        runs_dir=tmp_path / "runs",
    )

    assert result["actions"][0]["action"] == "started"
    assert result["actions"][0]["checkpoint"]["checkpointSha"] == "checkpoint-sha"
    assert checkpoints[0][1] == "pi-ready.2"
    bundle = Path(result["actions"][0]["result"]["started"]["bundle"])
    invocation = load_yaml_json(bundle / "invocation.yaml")
    assert invocation["continuationCheckpoint"]["checkpointSha"] == "checkpoint-sha"
    assert invocation["provenance"]["continuation"] == metadata["pi"]["continuation"]
    assert invocation["provenance"]["approvalRefs"] == ["pi-5eu"]
    assert load_yaml_json(bundle / "result.yaml")["approvalRefs"] == ["pi-5eu"]
    assert (bundle / "artifacts" / "checkpoint.json").is_file()


def test_scheduler_auto_closes_read_only_successes(tmp_path):
    started = []

    def fake_start(bead, **kwargs):
        started.append(kwargs)
        return {"started": {"bundle": str(tmp_path / "runs" / bead["id"]), "dispatch": {"bead": bead["id"]}}, "invoked": {"exitCode": 0}, "closed": {"beadClose": {"code": 0}}}

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.1")),
        runner_start=fake_start,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert result["actions"][0]["action"] == "started"
    assert started[0]["action_id"] == "review"
    assert started[0]["close_bead"] is True


def test_scheduler_creates_actionable_blocker_for_semantic_worker_failure(tmp_path):
    blockers = []

    def create_blocker(**kwargs):
        assert kwargs["run_bundle"] is None
        blockers.append(kwargs)
        return {"decisionBead": "pi-retry-gate"}

    def fake_start(bead, **kwargs):
        bundle = create_run_bundle(
            action="review",
            routing_task="review",
            bead=bead["id"],
            decision_refs=["pi-existing-decision"],
            runs_dir=tmp_path / "runs",
            id_value=kwargs["id_value"],
        )
        update_run_result(bundle, status="failed", summary="Worker produced an explicit ERROR terminal response.")
        return {
            "started": {"bundle": str(bundle), "dispatch": {"bead": bead["id"]}},
            "invoked": {
                "exitCode": 2,
                "semanticOutcome": "error",
            },
            "closed": None,
        }

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-ready.semantic-error")),
        runner_start=fake_start,
        blocker_creator=create_blocker,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert result["actions"][0]["action"] == "worker_failed"
    assert result["actions"][0]["semanticOutcome"] == "error"
    assert result["actions"][0]["blocker"]["decisionBead"] == "pi-retry-gate"
    assert blockers[0]["target_bead"] == "pi-ready.semantic-error"
    assert blockers[0]["requesting_run"].startswith("runner-pi-ready.semantic-error-")
    assert "fresh retry" in blockers[0]["context"]
    bundle = Path(result["actions"][0]["result"]["started"]["bundle"])
    run_result = load_yaml_json(bundle / "result.yaml")
    assert run_result["status"] == "failed"
    assert run_result["decisionRefs"] == ["pi-existing-decision", "pi-retry-gate"]
    invocation = load_yaml_json(bundle / "invocation.yaml")
    assert invocation["provenance"]["decisionRefs"] == ["pi-existing-decision"]
    state = load_scheduler_state(tmp_path)
    assert state["attempts"]["pi-ready.semantic-error"]["count"] == 1


def test_scheduler_ignores_human_gate_decision_beads_without_recursive_blockers(tmp_path):
    decision = {
        "id": "pi-decision.1",
        "title": "Resolve runner dispatch blocker",
        "issue_type": "decision",
        "status": "open",
        "labels": ["human", "human-gate", "question"],
        "metadata": json.dumps({"pi": {"approval": {"status": "pending"}}}),
    }
    ready = _review_bead("pi-ready.1")
    blockers = []

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(decision, ready),
        runner_start=lambda bead, **kwargs: {"started": {"bundle": str(tmp_path / "runs" / bead["id"]), "dispatch": {"bead": bead["id"]}}, "invoked": {"exitCode": 0}},
        blocker_creator=lambda **kwargs: blockers.append(kwargs) or {"decisionBead": "unexpected"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert [action["action"] for action in result["actions"]] == ["started"]
    assert result["actions"][0]["bead"] == "pi-ready.1"
    assert blockers == []


def test_scheduler_awaits_explicit_human_approval_without_creating_redundant_blocker(tmp_path):
    unapproved = _implement_bead("pi-awaiting.1")
    unapproved_meta = json.loads(unapproved["metadata"])
    unapproved_meta["pi"]["approved"] = False
    unapproved_meta["pi"].pop("humanApproval")
    unapproved["metadata"] = json.dumps(unapproved_meta)
    blockers = []
    starts = []

    awaiting = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(unapproved),
        runner_start=lambda bead, **kwargs: starts.append(bead) or {},
        blocker_creator=lambda **kwargs: blockers.append(kwargs) or {"decisionBead": "unexpected"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert awaiting["actions"][0]["action"] == "awaiting_approval"
    assert awaiting["actions"][0]["validationStatus"] == "needs-human"
    assert blockers == []
    assert starts == []

    approved = _implement_bead("pi-awaiting.1")
    dispatched = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(approved),
        runner_start=lambda bead, **kwargs: {
            "started": {"bundle": str(tmp_path / "runs" / bead["id"]), "dispatch": {"bead": bead["id"]}},
            "invoked": {"exitCode": 0},
        },
        blocker_creator=lambda **kwargs: blockers.append(kwargs) or {"decisionBead": "unexpected"},
        worktree_resolver=lambda _bead, _validation: {"dispatchable": True, "status": "ready", "policy": "existing-worktree"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert dispatched["actions"][0]["action"] == "started"
    assert blockers == []


def test_scheduler_creates_blocker_when_unapproved_work_also_has_invalid_dispatch_metadata(tmp_path):
    invalid = _implement_bead("pi-invalid.1")
    invalid_meta = json.loads(invalid["metadata"])
    invalid_meta["pi"]["approved"] = False
    invalid_meta["pi"].pop("humanApproval")
    invalid_meta["pi"].pop("epicId")
    invalid["metadata"] = json.dumps(invalid_meta)
    blockers = []

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(invalid),
        runner_start=lambda bead, **kwargs: (_ for _ in ()).throw(AssertionError(f"must not start {bead['id']}")),
        blocker_creator=lambda **kwargs: blockers.append(kwargs) or {"decisionBead": "pi-metadata-blocker.1"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert result["actions"][0]["action"] == "blocked"
    assert blockers[0]["target_bead"] == "pi-invalid.1"
    assert "metadata.pi.epicId" in blockers[0]["context"]


def test_scheduler_skips_unmanaged_ready_items_without_creating_blockers(tmp_path):
    unmanaged = {"id": "pi-unmanaged.1", "title": "Generic backlog", "issue_type": "task", "status": "open"}
    ready = _review_bead("pi-ready.1")
    blocked = []

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(unmanaged, ready),
        runner_start=lambda bead, **kwargs: {"started": {"bundle": str(tmp_path / "runs" / bead["id"]), "dispatch": {"bead": bead["id"]}}, "invoked": {"exitCode": 0}},
        blocker_creator=lambda **kwargs: blocked.append(kwargs) or {"decisionBead": "unexpected"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert [action["action"] for action in result["actions"]] == ["skipped_unmanaged", "started"]
    assert blocked == []


def test_scheduler_scans_past_blocked_ready_item_to_dispatch_next_candidate(tmp_path):
    blocked = _implement_bead("pi-blocked.1")
    ready = _review_bead("pi-ready.1")

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=True,
        limit=1,
        beads_runner=_ready(blocked, ready),
        runner_start=lambda bead, **kwargs: (_ for _ in ()).throw(AssertionError("dry run should not start")),
        worktree_resolver=lambda bead, _validation: (
            {"dispatchable": False, "status": "blocked", "reason": "bad worktree", "policy": "existing-worktree"}
            if bead["id"] == "pi-blocked.1"
            else {"dispatchable": True, "status": "ready", "policy": "none"}
        ),
        maintenance_due_provider=lambda **_kwargs: {"due": False},
    )

    assert [action["action"] for action in result["actions"]] == ["would_block", "would_start"]
    assert result["actions"][1]["bead"] == "pi-ready.1"
