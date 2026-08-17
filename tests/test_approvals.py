from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest


def _fingerprint(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _request_fingerprint(approval: dict) -> str:
    identity = {
        key: approval[key]
        for key in ("kind", "targetBead", "question", "context", "options", "default", "preview")
    }
    if "grantFingerprint" in approval:
        identity["grantFingerprint"] = approval["grantFingerprint"]
    if "resolverBinding" in approval:
        identity["resolverBinding"] = approval["resolverBinding"]
    return _fingerprint(identity)


def _provenance_comment(source: str, payload: dict) -> str:
    envelope = {"schemaVersion": 1, "source": source, "payload": payload}
    return "agnt-provenance-v1 " + json.dumps(
        envelope, sort_keys=True, separators=(",", ":")
    )


RESOLVER_SECRET = "test-only-resolver-secret"


def resolver_binding(session_id: str = "pi-session-1", secret: str = RESOLVER_SECRET) -> dict:
    return {
        "sessionFingerprint": "sha256:" + hashlib.sha256(session_id.encode()).hexdigest(),
        "secretFingerprint": "sha256:" + hashlib.sha256(secret.encode()).hexdigest(),
    }


def human_ui_resolver(session_id: str = "pi-session-1", secret: str = RESOLVER_SECRET) -> dict:
    return {"kind": "human-ui", "sessionId": session_id, "secret": secret}


def private_resolver_proof(
    session_id: str = "pi-session-1",
    secret: str = RESOLVER_SECRET,
    tool_call_id: str = "call-approval",
    tool_name: str = "ticket_approval",
) -> dict:
    return {
        **human_ui_resolver(session_id, secret),
        "sessionFile": "/tmp/pi-session.jsonl",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
    }


class FakeBeads:
    def __init__(
        self,
        show_metadata: dict | None = None,
        history_metadata: dict | None = None,
        history_states: list[dict] | None = None,
        provenance_comments: list[str] | None = None,
    ):
        self.calls: list[list[str]] = []
        self.history_states = history_states or []
        self.show_metadata = show_metadata or {
            "pi": {"approval": approval_record(requestingRun="approval-run")}
        }
        self.history_metadata = history_metadata or self.show_metadata
        approval = self.history_metadata["pi"]["approval"]
        request_fingerprint = approval.get("requestFingerprint")
        default_comments = []
        if isinstance(request_fingerprint, str):
            request_payload = {
                "schemaVersion": 1,
                "kind": "approval-request",
                "requestFingerprint": request_fingerprint,
            }
            grant_fingerprint = approval.get("grantFingerprint")
            grant = approval.get("grant")
            if isinstance(grant_fingerprint, str) and isinstance(grant, dict):
                request_payload["grantFingerprint"] = grant_fingerprint
                request_payload["grantStatus"] = grant["revocation"]["status"]
            default_comments.append(
                _provenance_comment("agnt-approval", request_payload)
            )
        default_comments.extend(_provenance_comment("agnt-capability", {
            "schemaVersion": 1,
            "kind": "grant-state",
            **state,
        }) for state in self.history_states)
        self.provenance_comments = (
            list(provenance_comments)
            if provenance_comments is not None
            else default_comments
        )

    def __call__(self, args: list[str]):
        self.calls.append(list(args))
        if args[0] == "create":
            return 0, {"id": "pi-decision.1", "title": "Approve risky edit"}, ""
        if args[:2] == ["comments", "add"]:
            self.provenance_comments.append(args[3])
            return 0, {"issue_id": args[2], "text": args[3]}, ""
        if args[0] == "comments":
            return 0, [
                {"issue_id": args[1], "text": text}
                for text in self.provenance_comments
            ], ""
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


def capability_grant(**overrides) -> dict:
    grant = {
        "action": "edit",
        "effects": ["workspace.write"],
        "model": "openai/gpt-5",
        "thinking": "high",
        "toolset": ["read", "edit", "bash"],
        "contextPolicy": "task-scoped",
        "proof": {
            "required": ["tests", "diff"],
            "evidenceRefs": ["artifact:grant-proof"],
        },
        "rollout": {"maxActions": 1, "maxEffects": 1},
        "expiry": "2099-01-01T00:00:00Z",
    }
    grant.update(overrides)
    return grant


def approval_record(**overrides) -> dict:
    preview = approval_preview()
    approval = {
        "kind": "approval",
        "targetBead": "pi-work.1",
        "question": "Approve risky edit?",
        "context": "Implementation needs explicit approval before mutating code.",
        "options": ["approve", "reject"],
        "default": "reject",
        "preview": preview,
        "previewFingerprint": _fingerprint(preview),
        "resolverBinding": resolver_binding(),
        "status": "pending",
        **overrides,
    }
    approval["requestFingerprint"] = _request_fingerprint(approval)
    return approval


def test_capability_grant_is_exact_and_fingerprinted(agnt):
    grant = capability_grant()
    payload = agnt.approval_request_payload(
        kind="approval",
        target_bead="pi-work.1",
        question="Approve bounded edit?",
        context="Need one exact capability ceiling.",
        options=["approve", "reject"],
        default="reject",
        preview=approval_preview(),
        grant=grant,
    )

    approval = payload["metadata"]["pi"]["approval"]
    assert approval["grantFingerprint"] == agnt.capability_grant_fingerprint(grant)
    assert approval["grant"]["action"] == grant["action"]
    assert approval["grant"]["revocation"] == {
        "status": "pending",
        "reason": None,
        "at": None,
    }

    with pytest.raises(ValueError, match="capability grant"):
        agnt.approval_request_payload(
            kind="approval",
            target_bead="pi-work.1",
            question="Approve bounded edit?",
            context="Need one exact capability ceiling.",
            options=["approve", "reject"],
            default="reject",
            preview=approval_preview(),
            grant={**grant, "unexpected": True},
        )
    with pytest.raises(ValueError, match="requires an approval"):
        agnt.approval_request_payload(
            kind="question",
            selection_mode="single",
            target_bead="pi-work.1",
            question="Choose scope",
            context="Need preference.",
            options=["one", "two"],
            default="one",
            preview=approval_preview(),
            grant=grant,
        )


def test_approved_grant_becomes_active_and_reads_only_resolved_decision(agnt):
    grant = capability_grant()
    approval = approval_record(
        status="approved",
        resolver={"kind": "human-ui"},
        grant={**grant, "revocation": {"status": "pending", "reason": None, "at": None}},
        grantFingerprint=agnt.capability_grant_fingerprint(grant),
    )
    fake = FakeBeads(show_metadata={"pi": {"approval": approval}})

    result = agnt.resolve_capability_grant("pi-decision.1", beads_runner=fake)

    assert result["status"] == "active"
    assert result["allowedEffects"] == grant["effects"]
    assert result["grantFingerprint"] == agnt.capability_grant_fingerprint(grant)
    assert result["decisionBead"] == "pi-decision.1"
    assert not any(call[:2] == ["show", "pi-work.1"] for call in fake.calls)
    comment_call = next(call for call in fake.calls if call[:2] == ["comments", "add"])
    envelope = json.loads(comment_call[3].split(" ", 1)[1])
    assert envelope["source"] == "agnt-capability"
    assert envelope["payload"]["status"] == "active"
    update_index = next(i for i, call in enumerate(fake.calls) if call[0] == "update")
    assert fake.calls.index(comment_call) < update_index


def test_canonical_grant_resolver_returns_bounded_authority(agnt):  # Tests INV-14
    grant = capability_grant()
    approval = approval_record(
        status="approved",
        resolver={"kind": "human-ui"},
        grant={**grant, "revocation": {"status": "active", "reason": None, "at": None}},
        grantFingerprint=agnt.capability_grant_fingerprint(grant),
    )
    fake = FakeBeads(show_metadata={"pi": {"approval": approval}})

    result = agnt.resolve_canonical_capability_grant("pi-decision.1", beads_runner=fake)

    assert result["status"] == "active"
    assert result["decisionBead"] == "pi-decision.1"
    assert result["allowedEffects"] == grant["effects"]
    assert len([
        call for call in fake.calls
        if call[:2] in (["show", "pi-decision.1"], ["comments", "pi-decision.1"])
    ]) == 2


def test_canonical_grant_resolver_fails_closed_when_state_is_unavailable(agnt):  # Tests FAIL-12
    def unavailable(args):
        return 1, None, "Beads unavailable"

    result = agnt.resolve_canonical_capability_grant(
        "pi-decision.1", beads_runner=unavailable
    )

    assert result["status"] == "blocked"
    assert result["allowedEffects"] == []
    assert result["decisionBead"] == "pi-decision.1"


def test_revoked_grant_cannot_be_reapproved(agnt):
    grant = capability_grant()
    approval = approval_record(
        status="rejected",
        grant={**grant, "revocation": {"status": "revoked", "reason": "rejected", "at": "2026-08-14T18:00:00Z"}},
        grantFingerprint=agnt.capability_grant_fingerprint(grant),
    )

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            resolver=human_ui_resolver(),
            beads_runner=FakeBeads(show_metadata={"pi": {"approval": approval}}),
        )


def test_revoked_state_cannot_be_reset_to_pending(agnt):
    grant = capability_grant()
    approval = approval_record(
        status="approved",
        resolver={"kind": "human-ui"},
        grant={**grant, "revocation": {"status": "pending", "reason": None, "at": None}},
        grantFingerprint=agnt.capability_grant_fingerprint(grant),
    )
    fake = FakeBeads(
        show_metadata={"pi": {"approval": approval}},
        history_states=[{
            "grantFingerprint": agnt.capability_grant_fingerprint(grant),
            "status": "revoked",
        }],
    )

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_capability_grant("pi-decision.1", beads_runner=fake)


def test_fail12_missing_grant_state_comment_blocks_authority(agnt):  # Tests FAIL-12
    grant = capability_grant()
    approval = approval_record(
        status="approved",
        resolver={"kind": "human-ui"},
        grant={**grant, "revocation": {"status": "active", "reason": None, "at": None}},
        grantFingerprint=agnt.capability_grant_fingerprint(grant),
    )
    request_only = _provenance_comment("agnt-approval", {
        "schemaVersion": 1,
        "kind": "approval-request",
        "requestFingerprint": approval["requestFingerprint"],
    })
    fake = FakeBeads(
        show_metadata={"pi": {"approval": approval}},
        provenance_comments=[request_only],
    )

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_capability_grant("pi-decision.1", beads_runner=fake)


@pytest.mark.parametrize(
    "states",
    [
        [{"status": "revoked"}, {"status": "active"}],
        [{"status": "expired"}, {"status": "revoked"}],
    ],
)
def test_fail12_conflicting_grant_comment_history_blocks_authority(agnt, states):  # Tests FAIL-12
    grant = capability_grant()
    fingerprint = agnt.capability_grant_fingerprint(grant)
    approval = approval_record(
        status="approved",
        resolver={"kind": "human-ui"},
        grant={**grant, "revocation": {"status": "revoked", "reason": "stop", "at": "2026-08-17T00:00:00Z"}},
        grantFingerprint=fingerprint,
    )
    fake = FakeBeads(
        show_metadata={"pi": {"approval": approval}},
        history_states=[{"grantFingerprint": fingerprint, **state} for state in states],
    )

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_capability_grant("pi-decision.1", beads_runner=fake)


def test_expired_grant_is_revoked_without_expanding_ceiling(agnt):
    grant = capability_grant()
    grant["expiry"] = "2020-01-01T00:00:00Z"
    approval = approval_record(
        status="approved",
        resolver={"kind": "human-ui"},
        grant={**grant, "revocation": {"status": "active", "reason": None, "at": None}},
        grantFingerprint=agnt.capability_grant_fingerprint(grant),
    )
    fake = FakeBeads(show_metadata={"pi": {"approval": approval}})

    result = agnt.resolve_capability_grant("pi-decision.1", beads_runner=fake)

    assert result["status"] == "expired"
    assert result["allowedEffects"] == []
    update_call = next(call for call in fake.calls if call[:2] == ["update", "pi-decision.1"])
    updated = json.loads(update_call[update_call.index("--metadata") + 1])
    updated_grant = updated["pi"]["approval"]["grant"]
    assert updated_grant["effects"] == grant["effects"]
    assert updated_grant["revocation"]["status"] == "expired"
    comment_call = next(call for call in fake.calls if call[:2] == ["comments", "add"])
    envelope = json.loads(comment_call[3].split(" ", 1)[1])
    assert envelope["payload"]["status"] == "expired"


def test_changed_grant_requires_reissue(agnt):
    original = capability_grant()
    approval = approval_record(
        status="approved",
        resolver={"kind": "human-ui"},
        grant={**original, "revocation": {"status": "active", "reason": None, "at": None}},
        grantFingerprint=agnt.capability_grant_fingerprint(original),
    )
    changed = json.loads(json.dumps(approval))
    changed["grant"]["effects"] = ["workspace.write", "network.send"]
    changed["grantFingerprint"] = agnt.capability_grant_fingerprint(changed["grant"])
    fake = FakeBeads(
        show_metadata={"pi": {"approval": changed}},
        history_metadata={"pi": {"approval": approval}},
    )

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_capability_grant("pi-decision.1", beads_runner=fake)



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
    assert metadata["pi"]["approval"]["previewFingerprint"] == _fingerprint(approval_preview())
    assert metadata["pi"]["approval"]["requestFingerprint"] == _request_fingerprint(metadata["pi"]["approval"])
    provenance = fake.calls[1]
    assert provenance[:3] == ["comments", "add", "pi-decision.1"]
    prefix, encoded = provenance[3].split(" ", 1)
    assert prefix == "agnt-provenance-v1"
    assert json.loads(encoded) == {
        "schemaVersion": 1,
        "source": "agnt-approval",
        "payload": {
            "schemaVersion": 1,
            "kind": "approval-request",
            "requestFingerprint": metadata["pi"]["approval"]["requestFingerprint"],
        },
    }
    assert fake.calls[2] == ["dep", "pi-decision.1", "--blocks", "pi-work.1"]

    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["status"] == "needs-human"
    assert run_result["approvalRefs"] == ["pi-decision.1"]
    assert run_result["decisionRefs"] == ["pi-decision.1"]


def test_request_provenance_failure_never_blocks_target(agnt):
    fake = FakeBeads()
    original = fake.__call__

    def fail_comment(args: list[str]):
        if args[:2] == ["comments", "add"]:
            fake.calls.append(list(args))
            return 1, None, "comment write failed"
        return original(args)

    with pytest.raises(SystemExit):
        agnt.create_beads_approval_request(
            kind="approval",
            target_bead="pi-work.1",
            question="Approve risky edit?",
            context="Implementation needs explicit approval before mutating code.",
            options=["approve", "reject"],
            default="reject",
            preview=approval_preview(),
            beads_runner=fail_comment,
        )

    assert [call[0] for call in fake.calls] == ["create", "comments"]


def test_comment_provenance_ignores_notes_and_tolerates_exact_duplicates(agnt):
    approval = approval_record()
    fake = FakeBeads(show_metadata={"pi": {"approval": approval}})
    fake.provenance_comments.extend([
        "Ordinary human note.",
        fake.provenance_comments[0],
    ])

    result = agnt.resolve_beads_approval_request(
        decision_bead="pi-decision.1",
        outcome="approved",
        resolver=human_ui_resolver(),
        beads_runner=fake,
    )

    assert result["outcome"] == "approved"


@pytest.mark.parametrize("case", ["missing", "malformed", "conflicting", "foreign"])
def test_fail7_unverifiable_comment_provenance_requires_new_request(agnt, case):  # Tests FAIL-7
    approval = approval_record()
    fake = FakeBeads(show_metadata={"pi": {"approval": approval}})
    if case == "missing":
        fake.provenance_comments = []
    elif case == "malformed":
        fake.provenance_comments.append("agnt-provenance-v1 {")
    elif case == "conflicting":
        fake.provenance_comments.append(_provenance_comment("agnt-approval", {
            "schemaVersion": 1,
            "kind": "approval-request",
            "requestFingerprint": "sha256:" + "f" * 64,
        }))
    else:
        fake.provenance_comments.append(_provenance_comment("other", {
            "schemaVersion": 1,
            "kind": "approval-request",
            "requestFingerprint": approval["requestFingerprint"],
        }))

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            resolver=human_ui_resolver(),
            beads_runner=fake,
        )


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
        preview=approval_preview(),
        run_bundle=bundle,
        beads_runner=fake,
    )

    assert result["decisionBead"] == "pi-decision.1"
    create_call = fake.calls[0]
    metadata = json.loads(create_call[create_call.index("--metadata") + 1])
    assert metadata["pi"]["approval"]["selectionMode"] == "multi"
    assert metadata["pi"]["approval"]["customResponseAllowed"] is True
    assert "Selection mode: multi" in create_call[create_call.index("--description") + 1]
    assert "Custom response: available" in create_call[create_call.index("--description") + 1]
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
        "preview": approval_preview(),
    }

    with pytest.raises(ValueError, match="selection_mode is required"):
        agnt.approval_request_payload(**kwargs)

    with pytest.raises(ValueError, match="selection_mode is required"):
        agnt.create_beads_approval_request(**kwargs, beads_runner=FakeBeads())

    with pytest.raises(ValueError, match="selection_mode must be one of"):
        agnt.approval_request_payload(**kwargs, selection_mode="either")


def test_approval_request_binds_resolver_secret_without_persisting_it(agnt):
    payload = agnt.approval_request_payload(
        kind="approval",
        target_bead="pi-work.1",
        question="Approve?",
        context="Need approval.",
        options=["approve", "reject"],
        default="reject",
        preview=approval_preview(),
        resolver_binding=human_ui_resolver(),
    )

    approval = payload["metadata"]["pi"]["approval"]
    assert approval["resolverBinding"] == resolver_binding()
    assert RESOLVER_SECRET not in json.dumps(payload)
    assert approval["requestFingerprint"] == _request_fingerprint(approval)


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
            preview=preview,
        )


def test_requesting_run_input_is_removed(agnt):
    with pytest.raises(TypeError, match="requesting_run"):
        agnt.approval_request_payload(
            kind="approval",
            target_bead="pi-work.1",
            question="Approve?",
            context="Need approval.",
            options=["approve", "reject"],
            default="reject",
            requesting_run="obsolete-run",
            preview=approval_preview(),
        )


def test_approvals_request_help_omits_requesting_run(agnt, capsys):
    with pytest.raises(SystemExit) as exc:
        agnt.cmd_approvals(["request", "--help"])
    assert exc.value.code == 0
    assert "--requesting-run" not in capsys.readouterr().out


def test_cli_human_ui_resolution_rejects_forgeable_resolver_flags(agnt, monkeypatch):
    import agnt_lib.approvals as approvals

    monkeypatch.setenv("PI_SESSION_ID", "session-1")
    monkeypatch.setattr(
        approvals,
        "resolve_beads_approval_request",
        lambda **kwargs: pytest.fail("forged resolver reached approval resolution"),
    )

    with pytest.raises(SystemExit) as exc:
        agnt.cmd_approvals([
            "resolve", "pi-decision.1", "--outcome", "approved", "--json",
            "--resolver-kind", "human-ui", "--resolver-session", "session-1",
        ])
    assert exc.value.code == 2


def test_cli_human_ui_resolution_rejects_caller_created_socket(agnt, monkeypatch):
    import agnt_lib.approvals as approvals

    monkeypatch.setenv("AGNT_HUMAN_UI_RESOLVER_FD", "3")
    monkeypatch.setattr(
        approvals,
        "resolve_beads_approval_request",
        lambda **kwargs: pytest.fail("unbound socket reached approval resolution"),
    )
    reader, writer = socket.socketpair()
    writer.sendall(json.dumps(private_resolver_proof()).encode("utf-8"))
    writer.close()
    try:
        saved_fd = os.dup(3)
    except OSError:
        saved_fd = None
    os.dup2(reader.fileno(), 3)
    reader.close()
    try:
        with pytest.raises(SystemExit) as exc:
            agnt.cmd_approvals([
                "resolve", "pi-decision.1", "--outcome", "approved", "--json",
            ])
        assert exc.value.code == 2
    finally:
        if saved_fd is None:
            os.close(3)
        else:
            os.dup2(saved_fd, 3)
            os.close(saved_fd)


def test_tool_call_attestation_accepts_only_pending_active_call(tmp_path):
    import agnt_lib.approvals as approvals

    session_file = tmp_path / "session.jsonl"
    header = {"type": "session", "version": 3, "id": "pi-session-1", "cwd": str(tmp_path)}
    assistant = {
        "type": "message",
        "id": "assistant",
        "parentId": None,
        "message": {
            "role": "assistant",
            "content": [{
                "type": "toolCall",
                "id": "call-approval",
                "name": "ticket_approval",
                "arguments": {},
            }],
        },
    }
    session_file.write_text(
        "\n".join(json.dumps(item) for item in (header, assistant)) + "\n",
        encoding="utf-8",
    )
    proof = {**private_resolver_proof(), "sessionFile": str(session_file)}

    assert approvals._verify_pending_tool_call(proof) is True

    result = {
        "type": "message",
        "id": "result",
        "parentId": "assistant",
        "message": {
            "role": "toolResult",
            "toolCallId": "call-approval",
            "toolName": "ticket_approval",
            "content": [],
            "isError": False,
        },
    }
    with session_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result) + "\n")

    assert approvals._verify_pending_tool_call(proof) is False


def test_cli_human_ui_resolution_accepts_private_fd_proof(agnt, monkeypatch, capsys):
    import agnt_lib.approvals as approvals

    monkeypatch.setenv("AGNT_HUMAN_UI_RESOLVER_FD", "3")
    monkeypatch.setattr(approvals, "_private_fd_peer_pid", lambda _fd: os.getppid())
    monkeypatch.setattr(approvals, "_verify_pending_tool_call", lambda _proof: True)
    captured = {}
    monkeypatch.setattr(
        approvals,
        "resolve_beads_approval_request",
        lambda **kwargs: captured.update(kwargs) or {
            "decisionBead": kwargs["decision_bead"],
            "outcome": kwargs["outcome"],
        },
    )
    reader, writer = socket.socketpair()
    writer.sendall(json.dumps(private_resolver_proof(
        session_id="session-private",
        secret="private-secret",
    )).encode("utf-8"))
    writer.close()
    try:
        saved_fd = os.dup(3)
    except OSError:
        saved_fd = None
    os.dup2(reader.fileno(), 3)
    reader.close()
    try:
        assert agnt.cmd_approvals([
            "resolve", "pi-decision.1", "--outcome", "approved", "--json",
        ]) == 0
    finally:
        if saved_fd is None:
            os.close(3)
        else:
            os.dup2(saved_fd, 3)
            os.close(saved_fd)

    assert captured["resolver"] == private_resolver_proof(
        session_id="session-private",
        secret="private-secret",
    )
    assert json.loads(capsys.readouterr().out)["outcome"] == "approved"


def test_resolve_approved_decision_rejects_forged_request_secret(agnt):
    with pytest.raises(ValueError, match="resolver binding"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            resolver=human_ui_resolver(secret="forged"),
            beads_runner=FakeBeads(),
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
        resolver=human_ui_resolver(),
        run_bundle=bundle,
        beads_runner=fake,
    )

    assert result["decisionBead"] == "pi-decision.1"
    assert result["outcome"] == "approved"
    assert result["blockerVisible"] is False
    assert result["qualityResult"] == {
        "schemaVersion": 1,
        "resultType": "constraint",
        "category": "authorization",
        "source": "ticket-approval",
        "retention": "durable",
        "decisionBead": "pi-decision.1",
        "targetBead": "pi-work.1",
        "status": "approved",
        "evidenceRefs": [{
            "ref": "result:ticket-pi-decision.1",
            "source": "beads-decision",
            "availability": "available",
            "provenance": "ticket:pi-decision.1",
            "integrity": "verified",
            "sensitivity": "internal",
            "retention": "durable",
        }],
        "authority": {"status": "none", "allowedEffects": []},
    }
    update_call = next(call for call in fake.calls if call[0] == "update")
    updated_metadata = json.loads(update_call[update_call.index("--metadata") + 1])
    assert updated_metadata["pi"]["approval"]["status"] == "approved"
    assert updated_metadata["pi"]["approval"]["answer"] == "Approved for the stated write set."
    assert updated_metadata["pi"]["approval"]["resolver"] == {"kind": "human-ui"}
    assert updated_metadata["pi"]["approval"]["resolverSessionFingerprint"] == (
        "sha256:" + hashlib.sha256(b"pi-session-1").hexdigest()
    )
    assert updated_metadata["pi"]["approval"]["qualityResult"] == result["qualityResult"]
    assert "requestingRun" not in updated_metadata["pi"]["approval"]
    assert result["targetUpdateResult"] is None
    assert not any(call[:2] == ["update", "pi-work.1"] for call in fake.calls)
    assert "pi-session-1" not in json.dumps(fake.calls)
    assert any(call[:2] == ["close", "pi-decision.1"] for call in fake.calls)
    run_result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
    assert run_result["status"] == "succeeded"
    assert run_result["approvalRefs"] == ["pi-decision.1"]
    assert run_result["decisionRefs"] == ["pi-decision.1"]


def test_fail7_changed_approval_preview_requires_new_request(agnt):  # Tests FAIL-7
    metadata = {"pi": {"approval": approval_record()}}
    metadata["pi"]["approval"]["preview"]["scope"] = "Expanded write set"
    fake = FakeBeads(show_metadata=metadata)

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            resolver=human_ui_resolver(),
            beads_runner=fake,
        )

    assert fake.calls == [["show", "pi-decision.1"]]


def test_fail7_recomputed_fingerprint_still_requires_new_request(agnt):  # Tests FAIL-7
    original = {"pi": {"approval": approval_record()}}
    changed = json.loads(json.dumps(original))
    changed_preview = {**approval_preview(), "scope": "Expanded write set"}
    changed["pi"]["approval"]["preview"] = changed_preview
    changed["pi"]["approval"]["previewFingerprint"] = _fingerprint(changed_preview)
    changed["pi"]["approval"]["requestFingerprint"] = _request_fingerprint(
        changed["pi"]["approval"]
    )
    fake = FakeBeads(show_metadata=changed, history_metadata=original)

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            resolver=human_ui_resolver(),
            beads_runner=fake,
        )

    assert fake.calls == [
        ["show", "pi-decision.1"],
        ["comments", "pi-decision.1"],
    ]


def test_fail7_retargeted_approval_requires_new_request(agnt):  # Tests FAIL-7
    original = {"pi": {"approval": approval_record()}}
    changed = json.loads(json.dumps(original))
    changed["pi"]["approval"]["targetBead"] = "pi-substituted.1"
    changed["pi"]["approval"]["requestFingerprint"] = _request_fingerprint(
        changed["pi"]["approval"]
    )
    fake = FakeBeads(show_metadata=changed, history_metadata=original)

    with pytest.raises(ValueError, match="new approval request"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            resolver=human_ui_resolver(),
            beads_runner=fake,
        )

    assert not any(call[:2] == ["update", "pi-substituted.1"] for call in fake.calls)


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
        resolver=human_ui_resolver(),
        beads_runner=list_shaped_show,
    )

    assert result["targetUpdateResult"] is None
    assert not any(call[:2] == ["update", "pi-work.1"] for call in fake.calls)
    decision_update = next(call for call in fake.calls if call[:2] == ["update", "pi-decision.1"])
    updated_metadata = json.loads(decision_update[decision_update.index("--metadata") + 1])
    assert updated_metadata["pi"]["approval"]["targetBead"] == "pi-work.1"
    assert updated_metadata["pi"]["approval"]["status"] == "approved"


@pytest.mark.parametrize(
    ("selection_mode", "selected_options", "custom_input", "expected_answer"),
    [
        ("multi", ["CLI core", "Pi extension"], "Start with docs", "[CLI core, Pi extension] + Other: Start with docs"),
        ("multi", [], None, "[]"),
        ("single", [], "Typed alternative", "Other: Typed alternative"),
    ],
)
def test_custom_response_resolution_persists_structured_question_answer(
    agnt,
    selection_mode,
    selected_options,
    custom_input,
    expected_answer,
):
    fake = FakeBeads(show_metadata={
        "pi": {
            "approval": {
                "kind": "question",
                "targetBead": "pi-work.2",
                "status": "pending",
                "selectionMode": selection_mode,
                "options": ["CLI core", "Pi extension"],
                "resolverBinding": resolver_binding(),
            }
        }
    })

    result = agnt.resolve_beads_approval_request(
        decision_bead="pi-decision.1",
        outcome="answered",
        selected_options=selected_options,
        custom_input=custom_input,
        resolver=human_ui_resolver(),
        beads_runner=fake,
    )

    approval = result["metadata"]["pi"]["approval"]
    assert approval["selectedOptions"] == selected_options
    assert result["qualityResult"]["category"] == "answer"
    assert result["qualityResult"]["source"] == "ticket-question"
    assert result["qualityResult"]["authority"] == {"status": "none", "allowedEffects": []}
    assert result["qualityResult"]["category"] != "acceptance"
    if custom_input is None:
        assert "customInput" not in approval
    else:
        assert approval["customInput"] == custom_input
    assert approval["answer"] == expected_answer


def test_empty_custom_response_and_approval_custom_text_are_rejected(agnt):
    resolver = human_ui_resolver()
    question = FakeBeads(show_metadata={
        "pi": {
            "approval": {
                "kind": "question",
                "targetBead": "pi-work.2",
                "selectionMode": "single",
                "options": ["CLI core"],
            }
        }
    })
    with pytest.raises(ValueError, match="custom_input cannot be empty"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="answered",
            selected_options=[],
            custom_input="   ",
            resolver=resolver,
            beads_runner=question,
        )
    with pytest.raises(ValueError, match="one selected option or one custom response"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="answered",
            selected_options=["CLI core"],
            custom_input="Other",
            resolver=resolver,
            beads_runner=question,
        )

    with pytest.raises(ValueError, match="structured answers are only valid for answered questions"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="approved",
            custom_input="approve",
            resolver=resolver,
            beads_runner=FakeBeads(),
        )
    with pytest.raises(ValueError, match="custom_input must be a string"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="answered",
            custom_input=123,
            resolver=resolver,
            beads_runner=question,
        )
    with pytest.raises(ValueError, match="selected_options must be a list"):
        agnt.resolve_beads_approval_request(
            decision_bead="pi-decision.1",
            outcome="answered",
            selected_options="CLI core",
            resolver=resolver,
            beads_runner=question,
        )


def test_legacy_question_resolution_defaults_to_single_selection_mode(agnt):
    fake = FakeBeads(show_metadata={
        "pi": {
            "approval": {
                "kind": "question",
                "targetBead": "pi-work.2",
                "status": "pending",
                "resolverBinding": resolver_binding(),
            }
        }
    })

    result = agnt.resolve_beads_approval_request(
        decision_bead="pi-decision.1",
        outcome="answered",
        answer="CLI core",
        resolver=human_ui_resolver(),
        beads_runner=fake,
    )

    assert result["metadata"]["pi"]["approval"]["selectionMode"] == "single"
    update_call = next(call for call in fake.calls if call[0] == "update")
    updated_metadata = json.loads(update_call[update_call.index("--metadata") + 1])
    assert updated_metadata["pi"]["approval"]["selectionMode"] == "single"


def test_question_cannot_approve_and_approval_cannot_answer(agnt):
    resolver = human_ui_resolver()
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
        human_approval = pi.get("human" + "Approval")
        if (
            isinstance(approval, dict)
            and ("requestingRun" in approval or "sessionId" in (approval.get("resolver") or {}))
        ) or (
            isinstance(human_approval, dict)
            and "sessionId" in (human_approval.get("resolver") or {})
        ):
            unsafe.append(issue.get("id"))
    assert unsafe == []


def test_beads_question_bridge_preserves_custom_response_multi_selection_and_cancellation(tmp_path):
    agent_dir = tmp_path / "agent"
    bin_dir = agent_dir / "bin"
    bin_dir.mkdir(parents=True)
    calls = tmp_path / "agnt-calls.txt"
    agnt = bin_dir / "agnt"
    agnt.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_AGNT_CALLS"
if [ "$2" = request ]; then
  if [ "${AGNT_HUMAN_UI_RESOLVER_FD:-}" = 3 ]; then cat <&3 >/dev/null; fi
  printf '%s\\n' '{"decisionBead":"pi-decision.1"}'
else
  if [ "${AGNT_HUMAN_UI_RESOLVER_FD:-}" = 3 ]; then cat <&3 >/dev/null; fi
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
      const extensionInstance = loaded.extensions[0];
      const tool = extensionInstance.tools.get("ticket_question").definition;
      const resolveTool = extensionInstance.tools.get("ticket_decision_resolve").definition;
      assert.equal(typeof extensionInstance.handlers.get("session_start")?.[0], "function", JSON.stringify([...extensionInstance.handlers.keys()]));
      await extensionInstance.handlers.get("session_start")[0]({{ reason: "startup" }}, {{
        cwd: process.cwd(),
        mode: "tui",
        hasUI: true,
        ui: {{}},
        sessionManager: {{
          getSessionId: () => "session-1",
          getSessionFile: () => "/tmp/session-1.jsonl",
        }},
      }});
      assert(tool.parameters.required.includes("selectionMode"));
      assert.equal("requestingRun" in tool.parameters.properties, false);
      await assert.rejects(() => resolveTool.execute("unsafe", {{
        decisionBead: "pi-decision.unsafe",
        outcome: "approved",
        customInput: "approve",
      }}, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{ confirm: async () => assert.fail("custom text reached approval confirmation") }},
      }}), /cannot approve an action/);
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
      const choiceIndexes = [0, 1, 0, 0];
      const customInputs = ["   ", "custom durable"];
      const warnings = [];
      const result = await tool.execute("call", params, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{
          select: async (_title, options) => options[choiceIndexes.shift()],
          input: async () => customInputs.shift(),
          notify: (message, level) => warnings.push([message, level]),
        }},
        sessionManager: {{
          getSessionId: () => "session-1",
          getSessionFile: () => "/tmp/session-1.jsonl",
        }},
      }});
      assert.match(result.content[0].text, /answered/);
      assert.deepEqual(warnings, [["Custom response cannot be empty.", "warning"]]);

      const cancelled = await tool.execute("cancel", params, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{ select: async () => undefined }},
        sessionManager: {{
          getSessionId: () => "session-1",
          getSessionFile: () => "/tmp/session-1.jsonl",
        }},
      }});
      assert.match(cancelled.content[0].text, /cancelled/);

      const empty = await tool.execute("empty", params, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{ select: async (_title, options) => options[1] }},
        sessionManager: {{
          getSessionId: () => "session-1",
          getSessionFile: () => "/tmp/session-1.jsonl",
        }},
      }});
      assert.match(empty.content[0].text, /answered/);

      const singleParams = {{ ...params, question: "Choose another", options: ["A", "B"], selectionMode: "single" }};
      const singleInputs = ["", "typed alternative"];
      const singleWarnings = [];
      const single = await tool.execute("single", singleParams, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{
          select: async (_title, options) => options.at(-1),
          input: async () => singleInputs.shift(),
          notify: (message, level) => singleWarnings.push([message, level]),
        }},
        sessionManager: {{
          getSessionId: () => "session-1",
          getSessionFile: () => "/tmp/session-1.jsonl",
        }},
      }});
      assert.match(single.content[0].text, /answered/);
      assert.deepEqual(singleWarnings, [["Custom response cannot be empty.", "warning"]]);

      const declined = await resolveTool.execute("declined", {{
        decisionBead: "pi-decision.declined",
        outcome: "answered",
        selectedOptions: ["A"],
        customInput: "typed",
      }}, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        mode: "tui",
        hasUI: true,
        ui: {{ confirm: async () => false }},
        sessionManager: {{
          getSessionId: () => "session-1",
          getSessionFile: () => "/tmp/session-1.jsonl",
        }},
      }});
      assert.match(declined.content[0].text, /cancelled/);

      const collisionLabel = "Other… (type a custom response)";
      const collision = await tool.execute("collision", {{ ...params,
        question: "Choose literal Other",
        options: [collisionLabel],
        selectionMode: "single",
      }}, undefined, undefined, {{
        cwd: {str(tmp_path)!r},
        hasUI: true,
        ui: {{
          select: async (_title, options) => options[0],
          input: async () => assert.fail("predefined option was mistaken for custom input"),
        }},
        sessionManager: {{
          getSessionId: () => "session-1",
          getSessionFile: () => "/tmp/session-1.jsonl",
        }},
      }});
      assert.match(collision.content[0].text, /answered/);
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
    (
        request,
        resolve,
        cancel_request,
        cancel_resolve,
        empty_request,
        empty_resolve,
        single_request,
        single_resolve,
        declined_resolve,
        collision_request,
        collision_resolve,
    ) = calls.read_text(encoding="utf-8").splitlines()
    assert "--selection-mode multi" in request
    assert "--outcome answered" in resolve
    assert "--structured-answer" in resolve
    assert "--selected-option A" in resolve and "--selected-option C" in resolve
    assert "--custom-input custom durable" in resolve
    assert "--selection-mode multi" in cancel_request
    assert "--outcome cancelled" in cancel_resolve
    assert "--answer Cancelled in Pi UI" in cancel_resolve
    assert "--selection-mode multi" in empty_request
    assert "--outcome answered" in empty_resolve
    assert "--structured-answer" in empty_resolve
    assert "--selected-option" not in empty_resolve and "--custom-input" not in empty_resolve
    assert "--selection-mode single" in single_request
    assert "--outcome answered" in single_resolve
    assert "--structured-answer" in single_resolve
    assert "--custom-input typed alternative" in single_resolve
    assert "--selected-option" not in single_resolve
    assert "--outcome cancelled" in declined_resolve
    assert "--selected-option" not in declined_resolve and "--custom-input" not in declined_resolve
    assert "--selection-mode single" in collision_request
    assert "--selected-option Other… (type a custom response)" in collision_resolve
    assert "--custom-input" not in collision_resolve


def test_beads_ask_bridge_binds_dialog_and_private_proof_to_extension_session(tmp_path):
    agent_dir = tmp_path / "agent"
    bin_dir = agent_dir / "bin"
    bin_dir.mkdir(parents=True)
    calls = tmp_path / "agnt-calls.txt"
    proof = tmp_path / "resolver-proof.json"
    agnt = bin_dir / "agnt"
    agnt.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_AGNT_CALLS"
if [ "$2" = request ]; then
  if [ "${AGNT_HUMAN_UI_RESOLVER_FD:-}" = 3 ]; then cat <&3 >/dev/null; fi
  printf '%s\\n' '{"decisionBead":"pi-decision.1"}'
else
  if ! cat <&3 > "$FAKE_RESOLVER_PROOF" 2>/dev/null; then
    printf '%s\\n' 'missing' > "$FAKE_RESOLVER_PROOF"
  fi
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
      const first = await loader.loadExtensions([{str(extension)!r}], process.cwd());
      const second = await loader.loadExtensions([{str(extension)!r}], process.cwd());
      assert.deepEqual(first.errors, []);
      assert.deepEqual(second.errors, []);
      const firstExtension = first.extensions[0];
      const secondExtension = second.extensions[0];
      const firstTool = firstExtension.tools.get("ticket_approval").definition;
      const secondTool = secondExtension.tools.get("ticket_approval").definition;
      const secondResolveTool = secondExtension.tools.get("ticket_decision_resolve").definition;
      const confirmations = [];
      const context = (sessionId) => ({{
        cwd: {str(tmp_path)!r},
        mode: "tui",
        hasUI: true,
        ui: {{ confirm: async () => {{ confirmations.push(sessionId); return true; }} }},
        sessionManager: {{
          getSessionId: () => sessionId,
          getSessionFile: () => `/tmp/${{sessionId}}.jsonl`,
        }},
      }});
      assert.equal(typeof firstExtension.handlers.get("session_start")?.[0], "function", JSON.stringify([...firstExtension.handlers.keys()]));
      assert.equal(typeof secondExtension.handlers.get("session_start")?.[0], "function", JSON.stringify([...secondExtension.handlers.keys()]));
      await firstExtension.handlers.get("session_start")[0]({{ reason: "startup" }}, context("session-1"));
      await secondExtension.handlers.get("session_start")[0]({{ reason: "startup" }}, context("session-2"));
      const params = {{
        targetBead: "pi-work.1",
        question: "Approve exact action?",
        context: "Need durable approval.",
        options: ["approve", "reject"],
        promptUser: true,
        preview: {{
          action: "Exact action",
          scope: "Named files only",
          consequences: "One bounded mutation",
          reversibility: "Revert commit",
          closeoutPath: "Verify and close",
        }},
      }};
      const staleFirst = await firstTool.execute("stale-first", params, undefined, undefined, context("session-2"));
      const staleSecond = await secondTool.execute("stale-second", params, undefined, undefined, context("session-1"));
      assert.match(staleFirst.content[0].text, /blocker remains visible/);
      assert.match(staleSecond.content[0].text, /blocker remains visible/);
      await assert.rejects(() => secondResolveTool.execute("stale-resolve", {{
        decisionBead: "pi-decision.1",
        outcome: "approved",
      }}, undefined, undefined, context("session-1")), /bound to this Pi session/);
      assert.deepEqual(confirmations, []);
      const switchingContext = context("session-2");
      switchingContext.ui.confirm = async () => {{
        confirmations.push("session-2-switch");
        await secondExtension.handlers.get("session_shutdown")[0]({{ reason: "new" }}, switchingContext);
        return true;
      }};
      const switched = await secondTool.execute("switched", params, undefined, undefined, switchingContext);
      assert.match(switched.content[0].text, /blocker remains visible/);
      assert.deepEqual(confirmations, ["session-2-switch"]);
      confirmations.length = 0;
      await secondExtension.handlers.get("session_start")[0]({{ reason: "startup" }}, context("session-2"));
      const approved = await secondTool.execute("approved", params, undefined, undefined, context("session-2"));
      assert.match(approved.content[0].text, /approved/);
      assert.deepEqual(confirmations, ["session-2"]);
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
            "FAKE_RESOLVER_PROOF": str(proof),
        },
    )
    resolver_proof = json.loads(proof.read_text(encoding="utf-8"))
    resolver_secret = resolver_proof.pop("secret")
    assert len(resolver_secret) >= 32
    assert resolver_secret not in calls.read_text(encoding="utf-8")
    assert resolver_proof == {
        "kind": "human-ui",
        "sessionId": "session-2",
        "sessionFile": "/tmp/session-2.jsonl",
        "toolCallId": "approved",
        "toolName": "ticket_approval",
    }
    resolve_call = calls.read_text(encoding="utf-8").splitlines()[-1]
    assert "--resolver-kind" not in resolve_call
    assert "--resolver-session" not in resolve_call


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
    assert 'args.push("--selected-option", option)' in text
    assert 'args.push("--custom-input", params.customInput)' in text
    assert "Custom response cannot be empty." in text
    assert "Human confirmation required" in text
    assert "decision resolution requires an interactive human UI" in text
    assert 'selectionMode: StringEnum(["single", "multi"] as const)' in text
    assert 'args.push("--selection-mode", params.selectionMode)' in text
    assert "CapabilityGrantSchema" in text
    assert "grant: Type.Optional(CapabilityGrantSchema)" in text
    assert 'args.push("--grant", JSON.stringify(params.grant))' in text
    assert "Proof evidence:" in text
    approval_tool = text.split('name: "ticket_approval"', 1)[1].split('name: "ticket_decision_resolve"', 1)[0]
    assert "ctx.ui.confirm" in approval_tool
    assert "ctx.ui.input" not in approval_tool
