from __future__ import annotations

import json
import os
import subprocess
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
    assert "requestingRun" not in metadata["pi"]["approval"]
    assert "approval-run" not in create_call[create_call.index("--description") + 1]
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
        selection_mode="multi",
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
    create_call = fake.calls[0]
    metadata = json.loads(create_call[create_call.index("--metadata") + 1])
    assert metadata["pi"]["approval"]["selectionMode"] == "multi"
    assert "Selection mode: multi" in create_call[create_call.index("--description") + 1]
    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["decisionRefs"] == ["pi-decision.1"]
    assert run_result["approvalRefs"] == []


def test_question_selection_mode_is_required_and_validated(agnt):
    kwargs = {
        "kind": "question",
        "target_bead": "pi-work.2",
        "question": "Which implementation surface first?",
        "context": "Need a durable human preference before proceeding.",
        "options": ["CLI core", "Pi extension"],
        "default": "CLI core",
        "requesting_run": None,
        "preview": approval_preview(),
    }

    with pytest.raises(ValueError, match="selection_mode is required"):
        agnt.approval_request_payload(**kwargs)

    with pytest.raises(ValueError, match="selection_mode is required"):
        agnt.create_beads_approval_request(**kwargs, beads_runner=FakeBeads())

    with pytest.raises(ValueError, match="selection_mode must be one of"):
        agnt.approval_request_payload(**kwargs, selection_mode="either")


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
        resolver={"kind": "human-ui", "sessionId": "pi-session-1"},
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
    assert updated_metadata["pi"]["approval"]["resolver"] == {"kind": "human-ui"}
    assert "requestingRun" not in updated_metadata["pi"]["approval"]
    target_update = next(call for call in fake.calls if call[:2] == ["update", "pi-work.1"])
    target_metadata = json.loads(target_update[target_update.index("--metadata") + 1])
    assert target_metadata["pi"]["humanApproval"] == {
        "decisionBead": "pi-decision.1",
        "resolver": {"kind": "human-ui"},
    }
    assert "pi-session-1" not in json.dumps(fake.calls)
    assert any(call[:2] == ["close", "pi-decision.1"] for call in fake.calls)
    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["status"] == "succeeded"
    assert run_result["approvalRefs"] == ["pi-decision.1"]
    assert run_result["decisionRefs"] == ["pi-decision.1"]


def test_resolve_approved_decision_accepts_bd_show_list_shape_and_preserves_target(agnt):
    fake = FakeBeads()
    original = fake.__call__

    def list_shaped_show(args: list[str]):
        code, data, err = original(args)
        if args[0] == "show":
            return code, [data], err
        return code, data, err

    result = agnt.resolve_beads_approval_request(
        decision_bead="pi-decision.1",
        outcome="approved",
        answer="Approved through the human UI.",
        resolver={"kind": "human-ui", "sessionId": "pi-session-1"},
        beads_runner=list_shaped_show,
    )

    assert result["targetUpdateResult"] == {"id": "pi-work.1"}
    decision_update = next(call for call in fake.calls if call[:2] == ["update", "pi-decision.1"])
    updated_metadata = json.loads(decision_update[decision_update.index("--metadata") + 1])
    assert updated_metadata["pi"]["approval"]["targetBead"] == "pi-work.1"
    assert updated_metadata["pi"]["approval"]["status"] == "approved"


def test_legacy_question_resolution_defaults_to_single_selection_mode(agnt):
    fake = FakeBeads(show_metadata={
        "pi": {
            "approval": {
                "kind": "question",
                "targetBead": "pi-work.2",
                "status": "pending",
            }
        }
    })

    result = agnt.resolve_beads_approval_request(
        decision_bead="pi-decision.1",
        outcome="answered",
        answer="CLI core",
        resolver={"kind": "human-ui", "sessionId": "pi-session-1"},
        beads_runner=fake,
    )

    assert result["metadata"]["pi"]["approval"]["selectionMode"] == "single"
    update_call = next(call for call in fake.calls if call[0] == "update")
    updated_metadata = json.loads(update_call[update_call.index("--metadata") + 1])
    assert updated_metadata["pi"]["approval"]["selectionMode"] == "single"


def test_question_cannot_approve_and_approval_cannot_answer(agnt):
    resolver = {"kind": "human-ui", "sessionId": "pi-session-1"}
    question = FakeBeads(show_metadata={"pi": {"approval": {"kind": "question", "targetBead": "pi-work.2"}}})
    with pytest.raises(ValueError, match="question decisions cannot resolve as approved"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            answer="approve",
            resolver=resolver,
            beads_runner=question,
        )

    with pytest.raises(ValueError, match="approval decisions cannot resolve as answered"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="answered",
            answer="approve",
            resolver=resolver,
            beads_runner=FakeBeads(),
        )


def test_approved_resolution_requires_human_ui_provenance(agnt):
    with pytest.raises(ValueError, match="human-ui resolver provenance"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            answer="Not enough: no human UI provenance.",
            beads_runner=FakeBeads(),
        )


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


def test_tracked_beads_have_public_safe_approval_provenance():
    unsafe = []
    for line in Path(".beads/issues.jsonl").read_text(encoding="utf-8").splitlines():
        issue = json.loads(line)
        metadata = issue.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata.strip() else {}
        pi = metadata.get("pi") if isinstance(metadata, dict) else None
        if not isinstance(pi, dict):
            continue
        approval = pi.get("approval")
        human_approval = pi.get("humanApproval")
        if (
            isinstance(approval, dict)
            and ("requestingRun" in approval or "sessionId" in (approval.get("resolver") or {}))
        ) or (
            isinstance(human_approval, dict)
            and "sessionId" in (human_approval.get("resolver") or {})
        ):
            unsafe.append(issue.get("id"))
    assert unsafe == []


def test_beads_question_bridge_preserves_multi_selection_and_cancellation(tmp_path):
    agent_dir = tmp_path / "agent"
    bin_dir = agent_dir / "bin"
    bin_dir.mkdir(parents=True)
    calls = tmp_path / "agnt-calls.txt"
    agnt = bin_dir / "agnt"
    agnt.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_AGNT_CALLS"
if [ "$2" = request ]; then
  printf '%s\\n' '{"decisionBead":"pi-decision.1"}'
else
  printf '%s\\n' '{"blockerVisible":false}'
fi
""",
        encoding="utf-8",
    )
    agnt.chmod(0o755)
    extension = Path("pi/agent/extensions/beads-ask-bridge.ts").resolve()
    script = f"""
      import assert from "node:assert/strict";
      import {{ dirname, resolve }} from "node:path";
      import {{ fileURLToPath, pathToFileURL }} from "node:url";
      const piEntry = fileURLToPath(import.meta.resolve("@earendil-works/pi-coding-agent"));
      const loader = await import(pathToFileURL(resolve(dirname(piEntry), "core/extensions/loader.js")).href);
      const loaded = await loader.loadExtensions([{str(extension)!r}], process.cwd());
      assert.deepEqual(loaded.errors, []);
      const tool = loaded.extensions[0].tools.get("ticket_question").definition;
      assert(tool.parameters.required.includes("selectionMode"));
      const params = {{
        targetBead: "pi-work.2",
        question: "Choose components",
        context: "Need durable selection.",
        options: ["A", "B", "C"],
        selectionMode: "multi",
        preview: {{
          action: "Choose components",
          scope: "Selection only",
          consequences: "Records answer",
          reversibility: "Can ask again",
          closeoutPath: "Resolve decision",
        }},
      }};
      const choices = [true, false, true];
      const result = await tool.execute("call", params, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{ select: async (_title, options) => choices.shift() ? options[0] : options[1] }},
        sessionManager: {{ getSessionId: () => "session-1" }},
      }});
      assert.match(result.content[0].text, /answered/);

      const cancelled = await tool.execute("cancel", params, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{ select: async () => undefined }},
        sessionManager: {{ getSessionId: () => "session-1" }},
      }});
      assert.match(cancelled.content[0].text, /cancelled/);

      const empty = await tool.execute("empty", params, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{ select: async (_title, options) => options[1] }},
        sessionManager: {{ getSessionId: () => "session-1" }},
      }});
      assert.match(empty.content[0].text, /answered/);
    """
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PI_CODING_AGENT_DIR": str(agent_dir),
            "FAKE_AGNT_CALLS": str(calls),
        },
    )
    request, resolve, cancel_request, cancel_resolve, empty_request, empty_resolve = calls.read_text(encoding="utf-8").splitlines()
    assert "--selection-mode multi" in request
    assert "--outcome answered" in resolve
    assert "--answer Answered in Pi UI: [A, C]" in resolve
    assert "--selection-mode multi" in cancel_request
    assert "--outcome cancelled" in cancel_resolve
    assert "--answer Cancelled in Pi UI" in cancel_resolve
    assert "--selection-mode multi" in empty_request
    assert "--outcome answered" in empty_resolve
    assert "--answer Answered in Pi UI: []" in empty_resolve


def test_beads_ask_bridge_extension_registers_ticket_tools():
    path = Path("pi/agent/extensions/beads-ask-bridge.ts")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "ticket_question" in text
    assert "ticket_approval" in text
    assert "agnt" in text and "approvals" in text and "request" in text and "resolve" in text
    assert "ctx.hasUI" in text
    assert "ui.select" in text
    assert "Approved in Pi UI" in text
    assert "Answered in Pi UI" in text
    assert "Human confirmation required" in text
    assert "decision resolution requires an interactive human UI" in text
    assert 'selectionMode: StringEnum(["single", "multi"] as const)' in text
    assert 'args.push("--selection-mode", params.selectionMode)' in text
    approval_tool = text.split('name: "ticket_approval"', 1)[1].split('name: "ticket_decision_resolve"', 1)[0]
    assert "ctx.ui.confirm" in approval_tool
    assert "ctx.ui.input" not in approval_tool
