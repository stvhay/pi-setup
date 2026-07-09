from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


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

NEEDS_APPROVAL_META = {
    "pi": {
        "action": "implement",
        "routingTask": "implementation",
        "approved": False,
        "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
        "modelPolicy": {"mode": "auto"},
        "epicId": "pi-epic",
        "worktreePolicy": "epic-worktree",
        "writeSet": ["pi/agent/bin/agnt_lib/runner.py"],
        "closeout": {
            "requiresEvidence": True,
            "requiresResolvedApprovals": True,
            "requiresFollowUpsReconciled": True,
        },
        "sessionPolicy": "recorded",
        "memoryPolicy": "auto",
    }
}


def test_runner_status_pause_resume_and_singleton_lock(agnt, tmp_path):
    status = agnt.runner_status(root=tmp_path)
    assert status["status"] == "idle"
    assert status["running"] is False
    assert status["paused"] is False

    paused = agnt.runner_pause(root=tmp_path, reason="maintenance")
    assert paused["paused"] is True
    assert agnt.runner_status(root=tmp_path)["paused"] is True

    lock = agnt.acquire_runner_lock(root=tmp_path, owner="test-runner")
    assert lock["acquired"] is True
    second = agnt.acquire_runner_lock(root=tmp_path, owner="other-runner")
    assert second["acquired"] is False
    assert second["existing"]["owner"] == "test-runner"
    assert agnt.runner_status(root=tmp_path)["running"] is True

    released = agnt.release_runner_lock(root=tmp_path, owner="test-runner")
    assert released["released"] is True
    resumed = agnt.runner_resume(root=tmp_path)
    assert resumed["paused"] is False
    assert agnt.runner_status(root=tmp_path)["status"] == "idle"


def test_runner_tick_dry_run_plans_start_and_block_without_mutation(agnt, tmp_path):
    ready = [
        {"id": "pi-ready.1", "title": "Review docs", "issue_type": "task", "status": "open", "metadata": json.dumps(VALID_REVIEW_META)},
        {"id": "pi-needs.1", "title": "Implement change", "issue_type": "task", "status": "open", "acceptance_criteria": "tests pass", "metadata": json.dumps(NEEDS_APPROVAL_META)},
    ]
    calls = []

    def fake_beads(args):
        calls.append(args)
        assert args == ["ready"]
        return 0, ready, ""

    result = agnt.runner_tick(root=tmp_path, dry_run=True, beads_runner=fake_beads, limit=2)

    assert result["dryRun"] is True
    assert [action["action"] for action in result["actions"]] == ["would_start", "would_block"]
    assert result["actions"][0]["bead"] == "pi-ready.1"
    assert result["actions"][0]["sessionPolicy"] == "recorded"
    assert result["actions"][1]["validationStatus"] == "needs-human"
    assert calls == [["ready"]]


def test_runner_tick_live_starts_dispatchable_and_creates_blocker(agnt, tmp_path):
    ready = [
        {"id": "pi-ready.1", "title": "Review docs", "issue_type": "task", "status": "open", "metadata": json.dumps(VALID_REVIEW_META)},
        {"id": "pi-needs.1", "title": "Implement change", "issue_type": "task", "status": "open", "acceptance_criteria": "tests pass", "metadata": json.dumps(NEEDS_APPROVAL_META)},
    ]
    started = []
    blocked = []

    def fake_beads(args):
        assert args == ["ready"]
        return 0, ready, ""

    def fake_runner_start(bead, **kwargs):
        started.append((bead, kwargs))
        return {"started": {"bundle": str(tmp_path / "runs" / "run-1")}, "invoked": {"exitCode": 0}}

    def fake_blocker(**kwargs):
        blocked.append(kwargs)
        return {"decisionBead": "pi-blocker.1", "blockerCreated": True}

    result = agnt.runner_tick(
        root=tmp_path,
        dry_run=False,
        beads_runner=fake_beads,
        runner_start=fake_runner_start,
        blocker_creator=fake_blocker,
        limit=2,
    )

    assert [action["action"] for action in result["actions"]] == ["started", "blocked"]
    assert started[0][0]["id"] == "pi-ready.1"
    assert started[0][1]["claim"] is True
    assert blocked[0]["target_bead"] == "pi-needs.1"
    assert "metadata.pi.approved" in blocked[0]["context"]


def test_invoke_one_can_record_named_session(agnt, monkeypatch):
    calls = []

    class Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Proc()

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", fake_run)

    code, out, err, record = agnt.invoke_one(
        "olla-cloud/gpt-4.1-mini",
        "prompt",
        metrics=False,
        record_session=True,
        session_id="run-abc",
        session_name="run:abc bead:pi-1 action:review",
    )

    assert code == 0
    assert out == "ok"
    assert record is None
    cmd = calls[0]
    assert "--no-session" not in cmd
    assert "--session-id" in cmd and cmd[cmd.index("--session-id") + 1] == "run-abc"
    assert "--name" in cmd and cmd[cmd.index("--name") + 1] == "run:abc bead:pi-1 action:review"


def test_work_runner_cli_status_and_tick_json(agnt, tmp_path, capsys):
    tick_result = {"schemaVersion": 1, "dryRun": True, "actions": []}
    status_result = {"schemaVersion": 1, "status": "idle", "running": False, "paused": False}

    with patch.dict(agnt.cmd_work.__globals__, {
        "runner_status": lambda root=None: status_result,
        "runner_tick": lambda **kwargs: tick_result,
    }):
        assert agnt.cmd_work(["runner", "status", "--json"]) == 0
        status_out = json.loads(capsys.readouterr().out)
        assert status_out["status"] == "idle"
        assert agnt.cmd_work(["runner", "tick", "--dry-run", "--json", "--limit", "1"]) == 0
        tick_out = json.loads(capsys.readouterr().out)
        assert tick_out["dryRun"] is True
