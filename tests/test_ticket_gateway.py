from __future__ import annotations

import json
from pathlib import Path

import pytest


class FakeBeads:
    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]):
        self.calls.append(list(args))
        if args[0] == "ready":
            return 0, [
                {"id": "pi-task.1", "title": "Ready task", "issue_type": "task", "status": "open", "priority": 2},
                {"id": "pi-epic", "title": "Epic", "issue_type": "epic", "status": "open", "priority": 1},
            ], ""
        if args[0] == "show":
            return 0, [{"id": args[1], "title": "Shown task", "issue_type": "task", "status": "open", "priority": 2}], ""
        if args[0] == "create":
            return 0, {"id": "pi-draft.1", "title": args[1]}, ""
        raise AssertionError(f"unexpected beads command: {args}")


def test_gateway_list_returns_compact_ready_items(agnt):
    fake = FakeBeads()

    result = agnt.ticket_gateway({"operation": "list"}, beads_runner=fake)

    assert result["schemaVersion"] == 1
    assert result["operation"] == "list"
    assert [item["id"] for item in result["items"]] == ["pi-task.1", "pi-epic"]
    assert set(result["items"][0]) >= {"id", "title", "type", "status", "priority", "metadataValidation"}
    assert fake.calls == [["ready"]]


def test_gateway_rejects_shell_like_payloads(agnt):
    with pytest.raises(ValueError, match="shell-like"):
        agnt.ticket_gateway({"operation": "show", "bead": "pi-task.1", "command": "bd show pi-task.1"})

    with pytest.raises(ValueError, match="operation"):
        agnt.ticket_gateway({"operation": "bd show pi-task.1"})


def test_gateway_show_returns_validation_and_run_context(agnt, tmp_path):
    fake = FakeBeads()
    run = tmp_path / "run-1"
    run.mkdir()
    (run / "invocation.yaml").write_text(json.dumps({"id": "run-1", "bead": "pi-task.1"}), encoding="utf-8")
    (run / "result.yaml").write_text(json.dumps({"status": "needs-human", "completedAt": None}), encoding="utf-8")

    result = agnt.ticket_gateway({"operation": "show", "bead": "pi-task.1"}, beads_runner=fake, runs_dir=tmp_path)

    assert result["item"]["id"] == "pi-task.1"
    assert result["item"]["metadataValidation"]["status"] in {"blocked", "dispatchable", "invalid", "needs-human"}
    assert result["item"]["activeRunRefs"] == [{"id": "run-1", "bundle": str(run), "status": "needs-human", "active": True, "completedAt": None}]
    assert fake.calls == [["show", "pi-task.1"]]


def test_gateway_tree_uses_existing_work_tree_core(agnt, tmp_path):
    calls = []

    def fake_tree(root, *, runs_dir):
        calls.append((root, runs_dir))
        return {"schemaVersion": 1, "root": root, "nodes": {root: {"id": root}}, "edges": [], "errors": []}

    result = agnt.ticket_gateway({"operation": "tree", "root": "pi-epic"}, tree_builder=fake_tree, runs_dir=tmp_path)

    assert result["tree"]["root"] == "pi-epic"
    assert calls == [("pi-epic", tmp_path)]


def test_gateway_create_draft_uses_structured_beads_create(agnt):
    fake = FakeBeads()

    result = agnt.ticket_gateway(
        {
            "operation": "create_draft",
            "title": "Draft follow-up",
            "description": "Follow-up description",
            "issueType": "task",
            "priority": 2,
            "labels": ["follow-up"],
            "metadata": {"pi": {"action": "review"}},
        },
        beads_runner=fake,
    )

    assert result["created"]["id"] == "pi-draft.1"
    create_call = fake.calls[0]
    assert create_call[:2] == ["create", "Draft follow-up"]
    assert "--type" in create_call and create_call[create_call.index("--type") + 1] == "task"
    assert "--labels" in create_call
    labels = set(create_call[create_call.index("--labels") + 1].split(","))
    assert {"draft", "gateway", "follow-up"}.issubset(labels)
    assert "--metadata" in create_call


def test_gateway_create_draft_rejects_caller_supplied_implementation_approval(agnt):
    with pytest.raises(ValueError, match="must not set metadata.pi.approved"):
        agnt.ticket_gateway(
            {
                "operation": "create_draft",
                "title": "Bypass approval",
                "description": "Attempt to make implementation dispatchable without a human gate.",
                "metadata": {"pi": {"action": "implement", "approved": True}},
            },
            beads_runner=FakeBeads(),
        )


def test_gateway_model_resolution_rejects_approval_outcomes(agnt):
    with pytest.raises(ValueError, match="cannot resolve approved or answered"):
        agnt.ticket_gateway(
            {"operation": "resolve_blocker", "decisionBead": "pi-decision.1", "outcome": "approved"},
            approval_resolver=lambda **_kwargs: {},
        )


def test_gateway_request_approval_accepts_legacy_snake_case_target_bead(agnt):
    calls = []

    def fake_approval(**kwargs):
        calls.append(kwargs)
        return {"decisionBead": "pi-decision.1", "blockerCreated": True}

    agnt.ticket_gateway(
        {
            "operation": "request_approval",
            "target_bead": "pi-task.1",
            "question": "Approve?",
            "context": "Need approval.",
            "options": ["approve", "reject"],
            "preview": {
                "action": "Edit files",
                "scope": "one file",
                "consequences": "writes change",
                "reversibility": "git revert",
                "closeoutPath": "tests pass",
            },
        },
        approval_creator=fake_approval,
    )

    assert calls[0]["target_bead"] == "pi-task.1"


def test_gateway_request_approval_and_resolve_blocker_delegate_to_approval_core(agnt):
    approval_calls = []
    resolve_calls = []

    def fake_approval(**kwargs):
        approval_calls.append(kwargs)
        return {"decisionBead": "pi-decision.1", "blockerCreated": True}

    def fake_resolve(**kwargs):
        resolve_calls.append(kwargs)
        return {"decisionBead": "pi-decision.1", "outcome": "cancelled", "blockerVisible": True}

    request = agnt.ticket_gateway(
        {
            "operation": "request_approval",
            "targetBead": "pi-task.1",
            "question": "Approve?",
            "context": "Need approval.",
            "options": ["approve", "reject"],
            "default": "reject",
            "requestingRun": "run-1",
            "preview": {
                "action": "Edit files",
                "scope": "one file",
                "consequences": "writes change",
                "reversibility": "git revert",
                "closeoutPath": "tests pass",
            },
        },
        approval_creator=fake_approval,
    )
    resolved = agnt.ticket_gateway(
        {"operation": "resolve_blocker", "decisionBead": "pi-decision.1", "outcome": "cancelled", "answer": "Cancelled."},
        approval_resolver=fake_resolve,
    )

    assert request["approval"]["decisionBead"] == "pi-decision.1"
    assert approval_calls[0]["kind"] == "approval"
    assert approval_calls[0]["target_bead"] == "pi-task.1"
    assert resolved["resolution"]["outcome"] == "cancelled"
    assert resolve_calls[0]["decision_bead"] == "pi-decision.1"


def test_gateway_runner_status_surfaces_runner_state(agnt, tmp_path):
    result = agnt.ticket_gateway({"operation": "runner_status", "root": str(tmp_path)})

    assert result["runner"]["service"]["state"] == "absent"
    assert result["runner"]["status"] == "not-running"
    assert result["runner"]["running"] is False
    assert result["runner"]["activeRuns"] == []
    assert result["runner"]["suggestedAction"] == "agnt work daemon start --json"


def test_ticket_gateway_approval_requests_prompt_the_interactive_human():
    text = Path("pi/agent/extensions/ticket-gateway.ts").read_text(encoding="utf-8")
    assert 'params.operation === "request_approval"' in text
    assert 'ctx.ui.confirm("Approval requested"' in text
    assert '["approvals", "resolve"' in text
    assert '"--resolver-kind", "human-ui"' in text


def test_ticket_gateway_extension_registers_tool_and_work_command():
    path = Path("pi/agent/extensions/ticket-gateway.ts")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "ticket_gateway" in text
    assert "registerTool" in text
    assert "registerCommand" in text
    assert '"/work"' in text or "registerCommand(\"work\"" in text
    assert "StringEnum" in text
    assert "approvals" not in text or "request_approval" in text
