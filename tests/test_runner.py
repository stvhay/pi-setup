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


def test_dispatch_plan_uses_metadata_action_before_title_heuristics(agnt):
    bead = {
        "id": "pi-ready.1",
        "title": "Execute critical harness fix",
        "issue_type": "bug",
        "status": "open",
        "acceptance_criteria": "tests pass",
        "metadata": json.dumps({
            "pi": {
                "action": "implement",
                "routingTask": "implementation",
                "approved": True,
                "humanApproval": {"decisionBead": "pi-approval.1", "resolver": {"kind": "human-ui", "sessionId": "pi-session-1"}},
                "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
                "epicId": "pi-epic",
                "worktreePolicy": "epic-worktree",
                "writeSet": ["src/shared.py"],
                "closeout": {
                    "requiresEvidence": True,
                    "requiresResolvedApprovals": True,
                    "requiresFollowUpsReconciled": True,
                },
            }
        }),
    }

    plan = agnt.dispatch_plan(bead, None, [])

    assert plan["action"] == "implement"
    assert plan["routingTask"] == "implementation"


def test_runner_tick_dry_run_plans_start_and_awaits_approval_without_mutation(agnt, tmp_path):
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
    assert [action["action"] for action in result["actions"]] == ["would_start", "awaiting_approval"]
    assert result["actions"][0]["bead"] == "pi-ready.1"
    assert result["actions"][0]["sessionPolicy"] == "recorded"
    assert result["actions"][1]["validationStatus"] == "needs-human"
    assert calls == [["ready"]]


def test_runner_tick_live_starts_dispatchable_and_awaits_explicit_approval(agnt, tmp_path):
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

    assert [action["action"] for action in result["actions"]] == ["started", "awaiting_approval"]
    assert started[0][0]["id"] == "pi-ready.1"
    assert started[0][1]["claim"] is True
    assert blocked == []
    assert "metadata.pi.approved" in result["actions"][1]["context"]


def test_invoke_one_reports_timeout(agnt, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise agnt.invoke_one.__globals__["subprocess"].TimeoutExpired(cmd, timeout=12, output="partial", stderr="waiting")

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", fake_run)

    code, out, err, record = agnt.invoke_one(
        "olla-cloud/gpt-4.1-mini",
        "prompt",
        metrics=False,
        timeout_seconds=12,
    )

    assert code == 124
    assert out == "partial"
    assert "timed out after 12s" in err
    assert "waiting" in err
    assert record is None


def test_invoke_one_can_record_named_session(agnt, monkeypatch, tmp_path):
    calls = []

    class Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Proc()

    monkeypatch.setattr(agnt.invoke_one.__globals__["subprocess"], "run", fake_run)

    code, out, err, record = agnt.invoke_one(
        "olla-cloud/gpt-4.1-mini",
        "prompt",
        metrics=False,
        record_session=True,
        session_id="run-abc",
        session_name="run:abc bead:pi-1 action:review",
        cwd=tmp_path,
        pi_args=["--no-extensions", "--tools", "read"],
    )

    assert code == 0
    assert out == "ok"
    assert record is None
    cmd, kwargs = calls[0]
    assert kwargs["cwd"] == str(tmp_path)
    assert "--no-session" not in cmd
    assert "--no-extensions" in cmd
    assert "--tools" in cmd and cmd[cmd.index("--tools") + 1] == "read"
    assert "--session-id" in cmd and cmd[cmd.index("--session-id") + 1] == "run-abc"
    assert "--name" in cmd and cmd[cmd.index("--name") + 1] == "run:abc bead:pi-1 action:review"


def test_invoke_run_bundle_implementation_uses_worktree_write_tools(agnt, monkeypatch, tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    bundle = agnt.create_run_bundle(
        action="implement",
        routing_task="implementation",
        bead="pi-ready.1",
        selected_model="olla-cloud/gpt-4.1-mini",
        worktree={"schemaVersion": 1, "path": str(worktree), "dispatchable": True, "status": "ready"},
        allowed_effects=["read_workspace", "write_artifacts", "edit_files", "write_workspace", "update_beads"],
        output_contract="implementation-report",
        runs_dir=tmp_path / "runs",
        id_value="run-implement",
    )
    calls = []

    def fake_invoke_one(target, prompt, **kwargs):
        calls.append((target, prompt, kwargs))
        return 0, "ok", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False, record_session=True, session_id="run-implement")

    assert result["exitCode"] == 0
    kwargs = calls[0][2]
    assert kwargs["cwd"] == str(worktree)
    assert "--no-extensions" in kwargs["pi_args"]
    assert "--tools" in kwargs["pi_args"]
    tools = kwargs["pi_args"][kwargs["pi_args"].index("--tools") + 1].split(",")
    assert {"read", "bash", "edit", "write", "grep", "find", "ls"}.issubset(set(tools))


def test_invoke_run_bundle_review_stays_read_only(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="olla-cloud/gpt-4.1-mini",
        allowed_effects=["read_workspace", "write_artifacts"],
        output_contract="findings-with-evidence",
        runs_dir=tmp_path / "runs",
        id_value="run-review",
    )
    calls = []

    def fake_invoke_one(target, prompt, **kwargs):
        calls.append((target, prompt, kwargs))
        return 0, "ok", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 0
    kwargs = calls[0][2]
    assert kwargs["cwd"] is None
    assert kwargs["timeout_seconds"] == 300
    assert "--no-extensions" in kwargs["pi_args"]
    tools = kwargs["pi_args"][kwargs["pi_args"].index("--tools") + 1].split(",")
    assert set(tools) == {"read", "grep", "find", "ls"}


def test_invoke_run_bundle_verify_with_command_evidence_gets_safe_bash(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="verify",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="olla-cloud/gpt-4.1-mini",
        allowed_effects=["read_workspace", "write_artifacts"],
        acceptance_criteria=["Run `/usr/bin/python -m pytest e2e-test/test_edabit_challenges.py -q` and report result."],
        output_contract="verification-review",
        runs_dir=tmp_path / "runs",
        id_value="run-verify",
    )
    calls = []

    def fake_invoke_one(target, prompt, **kwargs):
        calls.append((target, prompt, kwargs))
        return 0, "OK: verified", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 0
    tools = calls[0][2]["pi_args"][calls[0][2]["pi_args"].index("--tools") + 1].split(",")
    assert "bash" in tools
    assert "edit" not in tools
    assert "write" not in tools


def test_create_run_bundle_initializes_live_logs_and_lessons_handoff(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="verify",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="olla-cloud/gpt-4.1-mini",
        output_contract="verification-review",
        runs_dir=tmp_path / "runs",
        id_value="run-live-layout",
    )

    assert (bundle / "live" / "session.jsonl").exists()
    status = json.loads((bundle / "live" / "status.json").read_text(encoding="utf-8"))
    assert status["phase"] == "created"
    assert status["runId"] == "run-live-layout"
    assert (bundle / "artifacts" / "lessons.md").read_text(encoding="utf-8").startswith("# Lessons")
    assert (bundle / "artifacts" / "handoff.md").read_text(encoding="utf-8").startswith("# Handoff")
    result = agnt.load_yaml_json(bundle / "result.yaml")
    assert "live/session.jsonl" in result["artifacts"]
    assert "live/status.json" in result["artifacts"]
    assert "artifacts/lessons.md" in result["artifacts"]
    assert "artifacts/handoff.md" in result["artifacts"]


def test_render_invocation_prompt_includes_ticket_description(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="olla-cloud/gpt-4.1-mini",
        ticket_metadata={"title": "Review plan", "description": "Read docs/PLAN.md and report stop conditions."},
        output_contract="findings-with-evidence",
        runs_dir=tmp_path / "runs",
        id_value="run-description",
    )

    prompt = agnt.render_invocation_prompt(agnt.load_yaml_json(bundle / "invocation.yaml"))

    assert "Review plan" in prompt
    assert "Read docs/PLAN.md and report stop conditions." in prompt


def test_invoke_run_bundle_fails_unresolved_tool_call_markup(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.1",
        selected_model="olla-cloud/gpt-4.1-mini",
        output_contract="findings-with-evidence",
        runs_dir=tmp_path / "runs",
        id_value="run-tool-call",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, '<|tool_call>call:ls{path:"."}<tool_call|>', "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "unresolved tool call" in result_doc["summary"]


def test_invoke_run_bundle_fails_empty_terminal_response(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.empty-response",
        runs_dir=tmp_path,
        id_value="empty-response",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, " \n\t ", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "empty terminal response" in result_doc["summary"]
    assert any("empty terminal response" in item for item in result_doc["evidence"])


def test_invoke_run_bundle_fails_explicit_error_terminal_response(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-error",
        runs_dir=tmp_path,
        id_value="semantic-error",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "# Review — ERROR\n\nEvidence: portability defect remains.\n\n**Verdict: ERROR**\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "explicit ERROR terminal response" in result_doc["summary"]
    assert any("semantic outcome was ERROR" in item for item in result_doc["evidence"])
    live_status = agnt.load_yaml_json(bundle / "live" / "status.json")
    assert live_status["semanticOutcome"] == "error"


def test_invoke_run_bundle_accepts_markdown_ok_terminal_response(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-ok",
        runs_dir=tmp_path,
        id_value="semantic-ok",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "# Verification Review — OK\n\nEvidence: the report discusses ERROR outcomes, but checks passed.\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 0
    assert result["semanticOutcome"] == "ok"
    assert agnt.load_yaml_json(bundle / "result.yaml")["status"] == "succeeded"


def test_invoke_run_bundle_transport_failure_wins_over_ok_marker(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.transport-error",
        runs_dir=tmp_path,
        id_value="transport-error",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 7, "OK: report was generated before transport failure.\n", "worker crashed", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] == 7
    assert result["semanticOutcome"] == "ok"
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "exit code 7" in result_doc["summary"]


def test_invoke_run_bundle_fails_missing_terminal_marker(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-missing",
        runs_dir=tmp_path,
        id_value="semantic-missing",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "Checks passed, but no terminal marker was emitted.\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    assert result["semanticOutcome"] == "missing"
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "lacked an explicit terminal marker" in result_doc["summary"]


def test_invoke_run_bundle_fails_ambiguous_terminal_markers(agnt, monkeypatch, tmp_path):
    bundle = agnt.create_run_bundle(
        action="review",
        routing_task="review",
        bead="pi-ready.semantic-ambiguous",
        runs_dir=tmp_path,
        id_value="semantic-ambiguous",
    )

    def fake_invoke_one(target, prompt, **kwargs):
        return 0, "ERROR: first conclusion.\nOK: second conflicting conclusion.\n", "", None

    monkeypatch.setitem(agnt.invoke_run_bundle.__globals__, "invoke_one", fake_invoke_one)

    result = agnt.invoke_run_bundle(bundle, metrics=False)

    assert result["exitCode"] != 0
    assert result["semanticOutcome"] == "ambiguous"
    result_doc = agnt.load_yaml_json(bundle / "result.yaml")
    assert result_doc["status"] == "failed"
    assert "ambiguous terminal markers" in result_doc["summary"]


def test_work_runner_cli_status_and_tick_json(agnt, tmp_path, capsys):
    tick_result = {"schemaVersion": 1, "dryRun": True, "actions": []}
    status_result = {"schemaVersion": 1, "status": "running", "running": True, "paused": False}
    calls = []

    with patch.dict(agnt.cmd_work.__globals__, {
        "runner_client_status": lambda root=None: calls.append(("status", root)) or status_result,
        "runner_client_tick": lambda **kwargs: calls.append(("tick", kwargs)) or tick_result,
    }):
        assert agnt.cmd_work(["runner", "status", "--json", "--root", str(tmp_path)]) == 0
        status_out = json.loads(capsys.readouterr().out)
        assert status_out["status"] == "running"
        assert agnt.cmd_work(["runner", "tick", "--dry-run", "--json", "--limit", "1", "--root", str(tmp_path)]) == 0
        tick_out = json.loads(capsys.readouterr().out)
        assert tick_out["dryRun"] is True

    assert calls[0] == ("status", tmp_path)
    assert calls[1][0] == "tick"
    assert calls[1][1]["root"] == tmp_path


def test_work_runner_cli_reports_missing_service_json(agnt, tmp_path, capsys):
    class MissingService(Exception):
        payload = {"schemaVersion": 1, "status": "not-running", "suggestedAction": "agnt work daemon start --json"}

    with patch.dict(agnt.cmd_work.__globals__, {"RunnerClientError": MissingService, "runner_client_status": lambda root=None: (_ for _ in ()).throw(MissingService())}):
        assert agnt.cmd_work(["runner", "status", "--json", "--root", str(tmp_path)]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "not-running"
    assert output["suggestedAction"] == "agnt work daemon start --json"
