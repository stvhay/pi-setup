from __future__ import annotations


def valid_review_metadata() -> dict:
    return {
        "pi": {
            "action": "review",
            "routingTask": "review",
            "role": "code-reviewer",
            "allowedEffects": ["read_workspace", "write_artifacts"],
            "risk": "low",
            "budget": "cheap",
            "modelPolicy": {"mode": "auto", "diversity": "normal", "avoidFamilies": []},
            "thinkingPolicy": "auto",
        }
    }


def valid_implement_metadata() -> dict:
    return {
        "pi": {
            "action": "implement",
            "routingTask": "implementation",
            "role": "implementation-worker",
            "approved": True,
            "humanApproval": {"decisionBead": "pi-approval.1", "resolver": {"kind": "human-ui", "sessionId": "pi-session-1"}},
            "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
            "risk": "medium",
            "budget": "balanced",
            "modelPolicy": {"mode": "auto", "diversity": "normal", "avoidFamilies": []},
            "thinkingPolicy": "auto",
            "epicId": "pi-6yg",
            "worktreePolicy": "epic-worktree",
            "writeSet": ["pi/agent/bin/agnt_lib/orchestration.py", "tests/test_orchestration.py"],
            "closeout": {
                "requiresEvidence": True,
                "requiresResolvedApprovals": True,
                "requiresFollowUpsReconciled": True,
            },
        }
    }


def test_valid_review_metadata_is_dispatchable(agnt):
    result = agnt.validate_orchestration_metadata(valid_review_metadata())

    assert result["status"] == "dispatchable"
    assert result["dispatchable"] is True
    assert result["normalized"]["action"] == "review"
    assert result["normalized"]["sessionPolicy"] == "recorded"
    assert result["normalized"]["memoryPolicy"] == "auto"
    assert result["failures"] == []


def test_valid_approved_implement_metadata_is_dispatchable(agnt):
    bead = {"acceptance_criteria": "Focused tests pass; project checks pass"}

    result = agnt.validate_orchestration_metadata(valid_implement_metadata(), bead=bead)

    assert result["status"] == "dispatchable"
    assert result["dispatchable"] is True
    assert result["normalized"]["action"] == "implement"
    assert result["normalized"]["approved"] is True
    assert result["normalized"]["writeSet"] == [
        "pi/agent/bin/agnt_lib/orchestration.py",
        "tests/test_orchestration.py",
    ]


def test_implement_continuation_checkpoint_metadata_is_normalized(agnt):
    metadata = valid_implement_metadata()
    metadata["pi"]["continuation"] = {
        "mode": "checkpoint",
        "predecessor": "pi-6yg.1",
        "approvalRef": "pi-5eu",
    }

    result = agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "ok"})

    assert result["dispatchable"] is True
    assert result["normalized"]["continuation"] == metadata["pi"]["continuation"]


def test_orchestration_reference_metadata_is_normalized(agnt):
    metadata = valid_review_metadata()
    metadata["pi"].update({
        "inputRefs": ["pi-input.1", "docs/evidence.md"],
        "approvalRefs": ["pi-approval.1"],
        "decisionRefs": ["pi-decision.1"],
    })

    result = agnt.validate_orchestration_metadata(metadata)

    assert result["dispatchable"] is True
    assert result["normalized"]["inputRefs"] == ["pi-input.1", "docs/evidence.md"]
    assert result["normalized"]["approvalRefs"] == ["pi-approval.1"]
    assert result["normalized"]["decisionRefs"] == ["pi-decision.1"]


def test_invalid_orchestration_reference_metadata_is_rejected(agnt):
    metadata = valid_review_metadata()
    metadata["pi"]["inputRefs"] = "pi-input.1"

    result = agnt.validate_orchestration_metadata(metadata)

    assert result["status"] == "invalid"
    assert any("inputRefs" in item for item in result["failures"])


def test_implement_with_caller_supplied_approval_without_human_provenance_needs_human(agnt):
    metadata = valid_implement_metadata()
    metadata["pi"].pop("humanApproval")

    result = agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "ok"})

    assert result["status"] == "needs-human"
    assert result["dispatchable"] is False
    assert any("humanApproval" in item for item in result["humanActions"])


def test_implement_without_approval_needs_human(agnt):
    metadata = valid_implement_metadata()
    metadata["pi"]["approved"] = False

    result = agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "ok"})

    assert result["status"] == "needs-human"
    assert result["dispatchable"] is False
    assert any("approved" in item for item in result["humanActions"])


def test_missing_pi_metadata_is_blocked_without_crashing(agnt):
    result = agnt.validate_orchestration_metadata({})

    assert result["status"] == "blocked"
    assert result["dispatchable"] is False
    assert any("metadata.pi" in item for item in result["blockers"])


def test_unknown_action_is_invalid(agnt):
    metadata = valid_review_metadata()
    metadata["pi"]["action"] = "shell"

    result = agnt.validate_orchestration_metadata(metadata)

    assert result["status"] == "invalid"
    assert result["dispatchable"] is False
    assert any("unknown action" in item for item in result["failures"])


def test_implement_missing_write_set_is_blocked(agnt):
    metadata = valid_implement_metadata()
    metadata["pi"].pop("writeSet")

    result = agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "ok"})

    assert result["status"] == "blocked"
    assert result["dispatchable"] is False
    assert any("writeSet" in item for item in result["blockers"])


def test_direct_model_override_is_invalid(agnt):
    metadata = valid_review_metadata()
    metadata["pi"]["model"] = "openai-codex/gpt-5.6-sol"

    result = agnt.validate_orchestration_metadata(metadata)

    assert result["status"] == "invalid"
    assert result["dispatchable"] is False
    assert any("model override" in item for item in result["failures"])


def test_model_policy_target_override_is_invalid(agnt):
    metadata = valid_review_metadata()
    metadata["pi"]["modelPolicy"]["target"] = "openai-codex/gpt-5.6-sol"

    result = agnt.validate_orchestration_metadata(metadata)

    assert result["status"] == "invalid"
    assert result["dispatchable"] is False
    assert any("model override" in item for item in result["failures"])


def test_invalid_status_takes_precedence_over_human_gate(agnt):
    metadata = valid_implement_metadata()
    metadata["pi"]["approved"] = False
    metadata["pi"]["modelPolicy"]["target"] = "openai-codex/gpt-5.6-sol"

    result = agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "ok"})

    assert result["status"] == "invalid"
    assert result["dispatchable"] is False
    assert any("model override" in item for item in result["failures"])
    assert any("approved" in item for item in result["humanActions"])


def test_implement_missing_closeout_is_blocked(agnt):
    metadata = valid_implement_metadata()
    metadata["pi"].pop("closeout")

    result = agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "ok"})

    assert result["status"] == "blocked"
    assert result["dispatchable"] is False
    assert any("closeout" in item for item in result["blockers"])


def test_unknown_allowed_effect_is_invalid(agnt):
    metadata = valid_review_metadata()
    metadata["pi"]["allowedEffects"].append("raw_bash")

    result = agnt.validate_orchestration_metadata(metadata)

    assert result["status"] == "invalid"
    assert result["dispatchable"] is False
    assert any("allowedEffects" in item for item in result["failures"])


def test_validate_bead_orchestration_metadata_reads_json_metadata_string(agnt):
    import json

    bead = {
        "id": "pi-123",
        "metadata": json.dumps(valid_review_metadata()),
    }

    result = agnt.validate_bead_orchestration_metadata(bead)

    assert result["status"] == "dispatchable"
    assert result["bead"] == "pi-123"
    assert result["normalized"]["action"] == "review"


def test_malformed_bead_metadata_is_invalid(agnt):
    bead = {"id": "pi-123", "metadata": "{not json"}

    result = agnt.validate_bead_orchestration_metadata(bead)

    assert result["status"] == "invalid"
    assert result["dispatchable"] is False
    assert any("metadata JSON" in item for item in result["failures"])
