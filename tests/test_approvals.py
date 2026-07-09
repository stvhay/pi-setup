from __future__ import annotations

import json
from pathlib import Path

import pytest


class FakeBeads:
    def __init__(self, show_metadata: dict | None = None):
        self.calls: list[list[str]] = []
        self.show_metadata = show_metadata or {
            "pi": {
                "approval": {
                    "kind": "approval",
                    "targetBead": "pi-work.1",
                    "requestingRun": "approval-run",
                    "status": "pending",
                }
            }
        }

    def __call__(self, args: list[str]):
        self.calls.append(list(args))
        if args[0] == "create":
            return 0, {"id": "pi-decision.1", "title": "Approve risky edit"}, ""
        if args[0] == "dep":
            return 0, {"ok": True}, ""
        if args[0] == "show":
            return 0, {"id": args[1], "metadata": json.dumps(self.show_metadata)}, ""
        if args[0] == "update":
            return 0, {"id": args[1]}, ""
        if args[0] == "close":
            return 0, {"id": args[1], "status": "closed"}, ""
        raise AssertionError(f"unexpected beads command: {args}")


def approval_preview() -> dict:
    return {
        "action": "Edit orchestration files",
        "scope": "pi/agent/bin/agnt_lib/approvals.py and tests/test_approvals.py",
        "consequences": "Creates durable decision beads and updates run result refs.",
        "reversibility": "Code changes are revertible; Beads decision history remains auditable.",
        "closeoutPath": "Resolve the decision bead, run focused tests, and record evidence.",
    }


def test_create_approval_request_creates_decision_blocks_target_and_updates_run_result(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="implement",
        routing_task="implementation",
        bead="pi-work.1",
        runs_dir=tmp_path,
        id_value="approval-run",
    )
    fake = FakeBeads()

    result = agnt.create_beads_approval_request(
        kind="approval",
        target_bead="pi-work.1",
        question="Approve risky edit?",
        context="Implementation needs explicit approval before mutating code.",
        options=["approve", "reject"],
        default="reject",
        requesting_run="approval-run",
        preview=approval_preview(),
        run_bundle=bundle,
        beads_runner=fake,
    )

    assert result["decisionBead"] == "pi-decision.1"
    assert result["blockerCreated"] is True
    create_call = fake.calls[0]
    assert create_call[:2] == ["create", "Approve risky edit?"]
    assert "--type" in create_call and create_call[create_call.index("--type") + 1] == "decision"
    assert "--labels" in create_call
    labels = set(create_call[create_call.index("--labels") + 1].split(","))
    assert {"approval", "human", "human-gate", "beads-backed"}.issubset(labels)
    metadata = json.loads(create_call[create_call.index("--metadata") + 1])
    assert metadata["pi"]["approval"]["targetBead"] == "pi-work.1"
    assert metadata["pi"]["approval"]["requestingRun"] == "approval-run"
    assert metadata["pi"]["approval"]["default"] == "reject"
    assert metadata["pi"]["approval"]["preview"] == approval_preview()
    assert fake.calls[1] == ["dep", "pi-decision.1", "--blocks", "pi-work.1"]

    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["status"] == "needs-human"
    assert run_result["approvalRefs"] == ["pi-decision.1"]
    assert run_result["decisionRefs"] == ["pi-decision.1"]


def test_create_question_request_records_decision_ref_without_approval_ref(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="plan",
        routing_task="planning",
        bead="pi-work.2",
        runs_dir=tmp_path,
        id_value="question-run",
    )
    fake = FakeBeads()

    result = agnt.create_beads_approval_request(
        kind="question",
        target_bead="pi-work.2",
        question="Which implementation surface first?",
        context="Need a durable human preference before proceeding.",
        options=["CLI core", "Pi extension", "Both"],
        default="Both",
        requesting_run="question-run",
        preview=approval_preview(),
        run_bundle=bundle,
        beads_runner=fake,
    )

    assert result["decisionBead"] == "pi-decision.1"
    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["decisionRefs"] == ["pi-decision.1"]
    assert run_result["approvalRefs"] == []


def test_approval_preview_requires_informed_consent_fields(agnt):
    preview = approval_preview()
    preview.pop("reversibility")

    with pytest.raises(ValueError, match="preview.reversibility"):
        agnt.approval_request_payload(
            kind="approval",
            target_bead="pi-work.1",
            question="Approve?",
            context="Need approval.",
            options=["approve", "reject"],
            default="reject",
            requesting_run="run-1",
            preview=preview,
        )


def test_resolve_approved_decision_closes_bead_and_records_run_result(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="implement",
        routing_task="implementation",
        bead="pi-work.1",
        runs_dir=tmp_path,
        id_value="approval-run",
    )
    fake = FakeBeads()

    result = agnt.resolve_beads_approval_request(
        decision_bead="pi-decision.1",
        outcome="approved",
        answer="Approved for the stated write set.",
        run_bundle=bundle,
        beads_runner=fake,
    )

    assert result["decisionBead"] == "pi-decision.1"
    assert result["outcome"] == "approved"
    assert result["blockerVisible"] is False
    update_call = next(call for call in fake.calls if call[0] == "update")
    updated_metadata = json.loads(update_call[update_call.index("--metadata") + 1])
    assert updated_metadata["pi"]["approval"]["status"] == "approved"
    assert updated_metadata["pi"]["approval"]["answer"] == "Approved for the stated write set."
    assert any(call[:2] == ["close", "pi-decision.1"] for call in fake.calls)
    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["status"] == "succeeded"
    assert run_result["approvalRefs"] == ["pi-decision.1"]
    assert run_result["decisionRefs"] == ["pi-decision.1"]


def test_timeout_keeps_decision_bead_open_as_visible_blocker(agnt, tmp_path):
    bundle = agnt.create_run_bundle(
        action="implement",
        routing_task="implementation",
        bead="pi-work.1",
        runs_dir=tmp_path,
        id_value="approval-run",
    )
    fake = FakeBeads()

    result = agnt.resolve_beads_approval_request(
        decision_bead="pi-decision.1",
        outcome="timed-out",
        answer="No answer before timeout.",
        run_bundle=bundle,
        beads_runner=fake,
    )

    assert result["blockerVisible"] is True
    assert not any(call[0] == "close" for call in fake.calls)
    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["status"] == "blocked"
    assert run_result["decisionRefs"] == ["pi-decision.1"]


def test_beads_ask_bridge_extension_registers_ticket_tools():
    path = Path("pi/agent/extensions/beads-ask-bridge.ts")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "ticket_question" in text
    assert "ticket_approval" in text
    assert "agnt" in text and "approvals" in text and "request" in text and "resolve" in text
    assert "ctx.hasUI" in text
