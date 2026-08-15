from __future__ import annotations

import io
import json
import stat
import sys
import threading
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib import quality

QUALITY_PLAN = BIN.parent / "quality" / "control-plan.json"
ACTIVITY_FIELDS = {
    "id",
    "source",
    "inputs",
    "trigger",
    "owner",
    "method",
    "output",
    "receiver",
    "acceptanceRule",
    "evidence",
    "budget",
    "escalation",
    "retirementCondition",
}
ACTIVITY_IDS = [
    "capture",
    "work-learning",
    "architecture-coherence",
    "capability-calibration",
    "quality-system-review",
]


def beads_ok(args):
    return 0, {"id": args[1]}, ""


def test_local_invocation_and_result_are_authoritative_and_private(tmp_path):
    linked = quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    recorded = quality.capture_session_outcome(
        "session-1",
        "pi-work.1",
        "success",
        beads_runner=beads_ok,
        directory=tmp_path,
    )

    assert linked == {"schemaVersion": 1, "status": "linked", "beadId": "pi-work.1"}
    assert recorded == {
        "schemaVersion": 1,
        "status": "recorded",
        "beadId": "pi-work.1",
        "outcome": "success",
    }
    assert quality.session_work_item("session-1", directory=tmp_path) == "pi-work.1"
    assert quality.session_handoff_source("session-1", directory=tmp_path) == {
        "beadId": "pi-work.1",
        "outcome": "success",
    }

    ledger = tmp_path / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [row["recordType"] for row in rows] == ["invocation", "result"]
    assert all(set(row) <= {
        "schemaVersion", "recordType", "sessionId", "beadId", "outcome", "evidenceRefs", "capturedAt"
    } for row in rows)
    assert stat.S_IMODE(ledger.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    serialized = ledger.read_text(encoding="utf-8")
    for private in ("prompt", "response", "secret", str(tmp_path.resolve())):
        assert private not in serialized


def test_ledger_appends_without_replacing_or_duplicating_records(tmp_path):
    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    ledger = tmp_path / "ledger.jsonl"
    inode = ledger.stat().st_ino
    first = ledger.read_bytes()

    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    assert ledger.read_bytes() == first

    quality.capture_session_outcome(
        "session-1", "pi-work.1", "success", beads_runner=beads_ok, directory=tmp_path
    )
    assert ledger.stat().st_ino == inode
    assert ledger.read_bytes().startswith(first)
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2
    assert list(tmp_path.glob("*.tmp")) == []


def test_concurrent_capture_keeps_complete_json_lines(tmp_path):
    def capture(index):
        quality.capture_session_link(
            f"session-{index}",
            f"pi-work.{index}",
            beads_runner=beads_ok,
            directory=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(capture, range(20)))

    rows = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert len(rows) == 20
    assert {row["sessionId"] for row in rows} == {f"session-{index}" for index in range(20)}


def test_same_session_rejects_another_bead_before_append(tmp_path):
    quality.capture_session_link(
        "session-1", "pi-first.1", beads_runner=beads_ok, directory=tmp_path
    )
    ledger = tmp_path / "ledger.jsonl"
    before = ledger.read_bytes()

    with pytest.raises(quality.SessionWorkItemConflict, match="another work item"):
        quality.capture_session_link(
            "session-1", "pi-second.1", beads_runner=beads_ok, directory=tmp_path
        )

    assert ledger.read_bytes() == before


def test_missing_and_malformed_local_authority_fail_closed(tmp_path):
    with pytest.raises(quality.SessionUnassigned, match="no linked work item"):
        quality.session_handoff_source("session-1", directory=tmp_path)
    assert not (tmp_path / "ledger.jsonl").exists()

    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    with pytest.raises(quality.SessionOutcomeUnavailable, match="unavailable"):
        quality.session_handoff_source("session-1", directory=tmp_path)

    with (tmp_path / "ledger.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"schemaVersion":1,"recordType":"invocation","sessionId":"session-bad"}\n')
    with pytest.raises(ValueError, match="ledger row"):
        quality.session_work_item("session-1", directory=tmp_path)


def test_capture_rejects_unknown_fields_and_unsafe_evidence(tmp_path):
    base = {
        "schemaVersion": 1,
        "recordType": "invocation",
        "sessionId": "session-1",
        "beadId": "pi-work.1",
        "evidenceRefs": ["trace:abc-123"],
    }
    assert quality.capture(base, beads_runner=beads_ok, directory=tmp_path)["status"] == "linked"

    with pytest.raises(ValueError, match="unknown fields"):
        quality.capture({**base, "prompt": "private body"}, beads_runner=beads_ok, directory=tmp_path)

    for unsafe in (
        "/tmp/private",
        "https://private.example",
        "https:private.example",
        "password" + ":private",
        "s" + "k-privatecredentialvalue",
        "eyJ" + "header123.payload123.signature123",
        "trace:" + "eyJ" + "header123.payload123.signature123",
        "trace:" + "s" + "k-privatecredentialvalue",
        "opaque-reference",
    ):
        with pytest.raises(ValueError, match="evidence"):
            quality.capture(
                {**base, "sessionId": f"session-{len(unsafe)}", "evidenceRefs": [unsafe]},
                beads_runner=beads_ok,
                directory=tmp_path,
            )


@pytest.mark.parametrize("bead_data", [None, {}, {"id": "pi-other.1"}, []])
def test_capture_rejects_malformed_bead_readback_before_append(tmp_path, bead_data):
    with pytest.raises(ValueError, match="could not load work item"):
        quality.capture_session_link(
            "session-1",
            "pi-work.1",
            beads_runner=lambda _args: (0, bead_data, ""),
            directory=tmp_path,
        )

    assert not (tmp_path / "ledger.jsonl").exists()


def test_runtime_env_cannot_redirect_ledger_inside_repository(monkeypatch, tmp_path):
    redirected = tmp_path / "repo-owned"
    resolved = tmp_path / "resolved-private"
    monkeypatch.setenv("AGNT_QUALITY_DIR", str(redirected))
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: resolved)

    quality.capture_session_link("session-1", "pi-work.1", beads_runner=beads_ok)

    assert (resolved / "ledger.jsonl").is_file()
    assert not redirected.exists()


def test_short_append_rolls_back_incomplete_row(monkeypatch, tmp_path):
    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    ledger = tmp_path / "ledger.jsonl"
    before = ledger.read_bytes()
    real_write = quality.os.write

    def short_write(fd, data):
        return real_write(fd, data[:10])

    monkeypatch.setattr(quality.os, "write", short_write)
    with pytest.raises(OSError, match="incomplete"):
        quality.capture_session_outcome(
            "session-1",
            "pi-work.1",
            "success",
            beads_runner=beads_ok,
            directory=tmp_path,
        )

    assert ledger.read_bytes() == before
    assert quality.session_work_item("session-1", directory=tmp_path) == "pi-work.1"


def test_capture_result_requires_exact_schema_and_supported_outcome(tmp_path):
    payload = {
        "schemaVersion": 1,
        "recordType": "result",
        "sessionId": "session-1",
        "beadId": "pi-work.1",
        "outcome": "success",
        "evidenceRefs": [],
    }
    with pytest.raises(quality.SessionUnassigned, match="no linked work item"):
        quality.capture(payload, beads_runner=beads_ok, directory=tmp_path)

    quality.capture(
        {
            "schemaVersion": 1,
            "recordType": "invocation",
            "sessionId": "session-1",
            "beadId": "pi-work.1",
            "evidenceRefs": [],
        },
        beads_runner=beads_ok,
        directory=tmp_path,
    )
    assert quality.capture(payload, beads_runner=beads_ok, directory=tmp_path)["status"] == "recorded"

    with pytest.raises(ValueError, match="outcome"):
        quality.capture(
            {**payload, "sessionId": "session-2", "outcome": "excellent"},
            beads_runner=beads_ok,
            directory=tmp_path,
        )


def test_capture_cli_accepts_only_validated_json(monkeypatch, tmp_path, capsys):
    payload = {
        "schemaVersion": 1,
        "recordType": "invocation",
        "sessionId": "session-private",
        "beadId": "pi-work.1",
        "evidenceRefs": [],
    }
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: tmp_path)
    monkeypatch.setattr(quality, "_beads", beads_ok)

    assert quality.cmd_quality(["capture", "--payload", json.dumps(payload), "--json"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "linked"
    assert "session-private" not in output

    assert quality.cmd_quality([
        "capture",
        "--payload",
        json.dumps({**payload, "prompt": "private body"}),
        "--json",
    ]) == 2
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "schemaVersion": 1,
        "status": "error",
        "error": "quality capture failed",
    }
    assert "private body" not in output


def _shared_evidence_ref(**overrides):
    return {
        "ref": "artifact:review-123",
        "source": "review",
        "availability": "available",
        "provenance": "review:review-123",
        "integrity": "verified",
        "sensitivity": "private",
        "retention": "work-item",
        **overrides,
    }


def _shared_finding(**overrides):
    evidence_ref = _shared_evidence_ref()
    return {
        "schemaVersion": 1,
        "id": "F-001",
        "activity": "code-review",
        "source": "review",
        "category": "behavior-preservation",
        "severity": "important",
        "claim": "Retry path is skipped.",
        "status": "confirmed",
        "evidenceRefs": [evidence_ref],
        "verification": {"method": "inspection", "evidenceRefs": [evidence_ref]},
        "proposedIntervention": "Restore retry before returning.",
        **overrides,
    }


def test_shared_finding_and_evidence_ref_validate_common_contract():  # Tests INV-6
    evidence_ref = _shared_evidence_ref()
    finding = _shared_finding(domainLocation="src/example.py:42")

    assert quality.validate_evidence_ref(evidence_ref) == evidence_ref
    assert quality.validate_finding(finding) == finding

    for field, invalid in (
        ("availability", "sometimes"),
        ("provenance", "private provenance body"),
        ("integrity", "trusted"),
        ("sensitivity", "secret"),
        ("retention", "forever"),
        ("ref", "/tmp/raw-private-evidence"),
    ):
        with pytest.raises(ValueError, match="evidence reference"):
            quality.validate_evidence_ref(_shared_evidence_ref(**{field: invalid}))

    with pytest.raises(ValueError, match="verification"):
        quality.validate_finding(_shared_finding(verification=None))
    with pytest.raises(ValueError, match="intervention"):
        quality.validate_finding(_shared_finding(proposedIntervention=""))


def test_public_finding_rejects_copied_raw_private_evidence():  # Tests FAIL-4
    core = _shared_finding()

    assert quality.validate_finding(core, public=True) == core
    with pytest.raises(ValueError, match="public finding"):
        quality.validate_finding({**core, "evidence": "copied private tool payload"}, public=True)
    with pytest.raises(ValueError, match="evidence reference"):
        quality.validate_evidence_ref({**_shared_evidence_ref(), "content": "raw payload"})


def _review_assignment():
    evidence_refs = [
        _shared_evidence_ref(ref=f"artifact:improvement-report-session-{index}")
        for index in range(2)
    ]
    return quality.build_review_assignment(
        activity="work-learning",
        action={
            "id": "review",
            "routingTask": "review",
            "outputContract": "findings-with-evidence",
        },
        scope={
            "kind": "improvement-session-cohort",
            "id": "report-0123456789abcdef",
            "itemCount": 2,
            "maxItems": 20,
        },
        evidence_refs=evidence_refs,
        rubric={
            "path": "pi/agent/langfuse/improvement-review.md",
            "version": "v4",
        },
    )


def test_inv8_review_assignment_is_bounded_private_and_non_authorizing():  # Tests INV-8
    assignment = _review_assignment()

    assert assignment == _review_assignment()
    assert quality.validate_review_assignment(assignment) == assignment
    assert assignment["evidenceRefs"] == [
        _shared_evidence_ref(ref=f"artifact:improvement-report-session-{index}")
        for index in range(2)
    ]
    assert assignment["privacyConstraints"] == {
        "evidenceSensitivity": "private",
        "allowedReviewerClasses": [
            "human",
            "local-self-hosted",
            "explicitly-authorized-provider",
        ],
        "providerAccess": "explicit-approval-required",
        "rawEvidenceExport": False,
    }
    assert assignment["modelConstraints"] == {
        "routingTask": "review",
        "capability": "demonstrated-required",
    }
    assert assignment["outputContract"] == {
        "name": "findings-with-evidence",
        "schemaVersion": 1,
        "requiredFields": [
            "assignmentId",
            "reviewStatus",
            "route",
            "gaps",
            "sessions",
        ],
    }
    assert assignment["stopRules"] == {
        "maxAttempts": 1,
        "timeoutSeconds": 900,
        "onUnavailable": "route-human",
        "onTimeout": "route-human",
        "onPrivacyUncertain": "route-human",
        "onSchemaInvalid": "route-human",
    }
    assert assignment["authority"] == {"status": "none", "allowedEffects": []}

    elevated = deepcopy(assignment)
    elevated["authority"]["allowedEffects"] = ["update_beads"]
    with pytest.raises(ValueError, match="review assignment"):
        quality.validate_review_assignment(elevated)


def test_inv9_assigned_agent_review_result_is_typed_evidence_only():  # Tests INV-9
    assignment = _review_assignment()
    result = quality.normalize_assigned_review_result(
        assignment,
        {
            "schemaVersion": 1,
            "assignmentId": assignment["assignmentId"],
            "reviewStatus": "completed",
            "route": "none",
            "gaps": [],
            "sessions": [{"sessionId": "private-session", "findings": []}],
            "reportId": "report-0123456789abcdef",
            "reviewPolicyVersion": "v4",
            "reviewedAt": "2026-08-14T00:00:00Z",
            "attempt": 1,
        },
    )

    assert result == {
        "schemaVersion": 1,
        "resultType": "evidence",
        "category": "review",
        "source": "assigned-agent",
        "assignmentId": assignment["assignmentId"],
        "status": "completed",
        "evidenceRefs": assignment["evidenceRefs"],
        "authority": {"status": "none", "allowedEffects": []},
    }
    with pytest.raises(ValueError, match="assigned review result fields"):
        quality.normalize_assigned_review_result(
            assignment,
            {
                "schemaVersion": 1,
                "assignmentId": assignment["assignmentId"],
                "reviewStatus": "completed",
                "route": "none",
                "gaps": [],
                "sessions": [],
                "accepted": True,
            },
        )


def test_inv9_transient_ask_result_is_session_constraint_not_acceptance():  # Tests INV-9
    result = quality.normalize_ask_result({
        "id": "deploy?",
        "question": "Which surface first?",
        "options": ["CLI", "Extension"],
        "selectionMode": "single",
        "selectedOptions": ["CLI"],
    })

    assert result == {
        "schemaVersion": 1,
        "resultType": "constraint",
        "category": "answer",
        "source": "ask",
        "retention": "session",
        "questionId": "deploy?",
        "status": "answered",
        "selectedOptions": ["CLI"],
        "authority": {"status": "none", "allowedEffects": []},
    }
    assert result["category"] not in {"acceptance", "authorization"}

    with pytest.raises(ValueError, match="selected options"):
        quality.normalize_ask_result({
            "id": "surface",
            "question": "Which surface first?",
            "options": ["CLI", "Extension"],
            "selectionMode": "single",
            "selectedOptions": ["Other"],
        })


def test_inv9_quality_cli_normalizes_ask_results_without_persistence(
    monkeypatch, tmp_path, capsys
):  # Tests INV-9
    payload = [{
        "id": "surface",
        "question": "Which surface first?",
        "options": ["CLI", "Extension"],
        "selectionMode": "single",
        "selectedOptions": ["CLI"],
    }]
    monkeypatch.setattr(quality.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: tmp_path)

    assert quality.cmd_quality(["normalize-ask", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["results"][0]["category"] == "answer"
    assert result["results"][0]["retention"] == "session"
    assert list(tmp_path.iterdir()) == []


def _langfuse_annotation_import():
    return {
        "queue_id": "queue-quality",
        "queue": {
            "id": "queue-quality",
            "name": "Quality review",
            "description": None,
            "scoreConfigIds": ["config-quality"],
            "createdAt": "2026-08-14T00:00:00Z",
            "updatedAt": "2026-08-14T00:01:00Z",
        },
        "items": [{
            "id": "item-1",
            "queueId": "queue-quality",
            "objectId": "trace-private",
            "objectType": "TRACE",
            "status": "COMPLETED",
            "completedAt": "2026-08-14T00:02:00Z",
            "createdAt": "2026-08-14T00:00:00Z",
            "updatedAt": "2026-08-14T00:02:00Z",
        }],
        "scores": [{
            "id": "score-quality",
            "projectId": "project-private",
            "name": "quality",
            "value": 0.8,
            "dataType": "NUMERIC",
            "source": "ANNOTATION",
            "timestamp": "2026-08-14T00:02:00Z",
            "environment": "default",
            "createdAt": "2026-08-14T00:02:00Z",
            "updatedAt": "2026-08-14T00:02:00Z",
            "comment": "private reviewer comment",
            "configId": "config-quality",
            "metadata": {},
            "authorUserId": "reviewer-private",
            "queueId": "queue-quality",
            "subject": {"kind": "trace", "id": "trace-private"},
        }, {
            "id": "score-correction",
            "projectId": "project-private",
            "name": "output",
            "value": "private corrected output",
            "dataType": "CORRECTION",
            "source": "ANNOTATION",
            "timestamp": "2026-08-14T00:03:00Z",
            "environment": "default",
            "createdAt": "2026-08-14T00:03:00Z",
            "updatedAt": "2026-08-14T00:03:00Z",
            "comment": None,
            "configId": None,
            "metadata": {},
            "authorUserId": "reviewer-private",
            "queueId": "queue-quality",
            "subject": {"kind": "trace", "id": "trace-private"},
        }],
        "score_configs": [{
            "id": "config-quality",
            "name": "quality",
            "createdAt": "2026-08-14T00:00:00Z",
            "updatedAt": "2026-08-14T00:00:00Z",
            "projectId": "project-private",
            "dataType": "NUMERIC",
            "isArchived": False,
            "minValue": 0,
            "maxValue": 1,
            "categories": None,
            "description": "private rubric",
        }],
        "completeness": {
            "queue": True,
            "items": True,
            "scores": True,
            "scoreConfigs": True,
        },
        "gaps": [],
    }


def test_inv10_langfuse_annotations_are_bounded_review_evidence_only():  # Tests INV-10
    result = quality.normalize_langfuse_annotation_result(**_langfuse_annotation_import())

    assert result["category"] == "review"
    assert result["source"] == "langfuse-annotation-queue"
    assert result["status"] == "completed"
    assert result["reviewers"][0].startswith("langfuse-user-")
    assert result["rubric"] == {
        "scoreConfigs": [{
            "ref": result["rubric"]["scoreConfigs"][0]["ref"],
            "dataType": "NUMERIC",
        }],
        "complete": True,
    }
    assert result["scope"] == {
        "queueRef": result["scope"]["queueRef"],
        "itemCount": 1,
        "completedItems": 1,
        "objectTypes": ["trace"],
        "maxItems": 16,
    }
    assert [record["kinds"] for record in result["annotations"]] == [
        ["score", "comment"],
        ["corrected-output"],
    ]
    assert len(result["evidenceRefs"]) == 2
    assert result["completeness"]["complete"] is True
    assert result["gaps"] == []
    assert result["authority"] == {"status": "none", "allowedEffects": []}
    encoded = json.dumps(result)
    for private in (
        "private reviewer comment",
        "private corrected output",
        "trace-private",
        "reviewer-private",
        "project-private",
    ):
        assert private not in encoded
    assert result["category"] not in {"annotation", "acceptance", "authorization"}


def test_fail8_langfuse_annotation_partiality_and_authority_claims_fail_closed():  # Tests FAIL-8
    partial = _langfuse_annotation_import()
    partial["items"][0]["status"] = "PENDING"
    partial["items"][0]["completedAt"] = None
    partial["scores"] = []
    partial["completeness"]["items"] = False
    partial["gaps"] = ["item-limit"]

    result = quality.normalize_langfuse_annotation_result(**partial)

    assert result["status"] == "partial"
    assert result["evidenceRefs"] == []
    assert result["completeness"]["complete"] is False
    assert result["gaps"] == ["item-limit", "pending-items"]
    assert result["authority"] == {"status": "none", "allowedEffects": []}

    claimed = _langfuse_annotation_import()
    claimed["scores"][0]["accepted"] = True
    with pytest.raises(ValueError, match="authority"):
        quality.normalize_langfuse_annotation_result(**claimed)


def _external_human_result(source="editor"):
    result = {
        "schemaVersion": 1,
        "source": source,
        "artifact": {
            "path": ".pi/quality-results/review-123.json",
            "sensitivity": "private",
        },
        "scope": {"kind": "review-assignment", "id": "review-123"},
        "category": "review",
        "status": "completed",
        "evidenceRefs": [_shared_evidence_ref(source="editor")],
        "provenance": {
            "adapter": "nvim",
            "actor": "human",
            "sessionRef": "invocation:session-123",
        },
        "gaps": [],
        "resumptionPath": None,
    }
    if source == "takeover":
        result.update({
            "artifact": {
                "path": ".pi/quality-results/takeover-123.json",
                "sensitivity": "private",
            },
            "category": "execution",
            "status": "partial",
            "evidenceRefs": [_shared_evidence_ref(source="betterwright", availability="partial")],
            "provenance": {
                "adapter": "betterwright",
                "actor": "human",
                "sessionRef": "invocation:session-123",
            },
            "gaps": ["takeover-incomplete"],
            "resumptionPath": ".pi/takeovers/session-123.json",
        })
    return result


def test_inv11_editor_and_takeover_results_preserve_external_evidence_state():  # Tests INV-11
    editor = quality.normalize_external_result(_external_human_result())
    takeover = quality.normalize_external_result(_external_human_result("takeover"))

    assert editor == {
        **_external_human_result(),
        "resultType": "evidence",
        "authority": {"status": "none", "allowedEffects": []},
    }
    assert takeover["category"] == "execution"
    assert takeover["status"] == "partial"
    assert takeover["gaps"] == ["takeover-incomplete"]
    assert takeover["resumptionPath"] == ".pi/takeovers/session-123.json"
    assert takeover["authority"] == {"status": "none", "allowedEffects": []}
    assert takeover["category"] not in {"acceptance", "authorization"}

    for status in ("partial", "lost", "uncertain"):
        interrupted = _external_human_result("takeover")
        interrupted["status"] = status
        interrupted["gaps"] = [f"takeover-{status}"]
        normalized = quality.normalize_external_result(interrupted)
        assert normalized["status"] == status
        assert normalized["resumptionPath"] == ".pi/takeovers/session-123.json"


def test_fail9_external_result_rejects_unsafe_or_authorizing_artifacts():  # Tests FAIL-9
    for path in (
        "/tmp/result.json",
        "../private/result.json",
        "safe/../../private/result.json",
        "~/.pi/private/result.json",
    ):
        invalid = _external_human_result()
        invalid["artifact"]["path"] = path
        with pytest.raises(ValueError, match="path"):
            quality.normalize_external_result(invalid)

    public_leak = _external_human_result()
    public_leak["artifact"]["sensitivity"] = "public"
    with pytest.raises(ValueError, match="sensitivity"):
        quality.normalize_external_result(public_leak)

    claimed = _external_human_result()
    claimed["provenance"]["authorization"] = {"status": "approved"}
    with pytest.raises(ValueError, match="authority"):
        quality.normalize_external_result(claimed)

    raw = _external_human_result()
    raw["rawEvidence"] = "private editor contents"
    with pytest.raises(ValueError, match="fields"):
        quality.normalize_external_result(raw)

    nested = None
    for _ in range(600):
        nested = [nested]
    raw["rawEvidence"] = nested
    with pytest.raises(ValueError, match="fields"):
        quality.normalize_external_result(raw)

    missing_resume = _external_human_result("takeover")
    missing_resume["resumptionPath"] = None
    with pytest.raises(ValueError, match="resumption"):
        quality.normalize_external_result(missing_resume)

    malformed_types = []
    for field in ("source", "status"):
        malformed = _external_human_result()
        malformed[field] = []
        malformed_types.append(malformed)
    for container, field in (("artifact", "sensitivity"), ("provenance", "adapter")):
        malformed = _external_human_result()
        malformed[container][field] = []
        malformed_types.append(malformed)
    malformed = _external_human_result()
    malformed["gaps"] = [[]]
    malformed_types.append(malformed)
    for malformed in malformed_types:
        with pytest.raises(ValueError):
            quality.normalize_external_result(malformed)


def test_inv11_quality_cli_normalizes_external_result_without_persistence(
    monkeypatch, tmp_path, capsys
):  # Tests INV-11
    monkeypatch.setattr(quality.sys, "stdin", io.StringIO(json.dumps(_external_human_result())))
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: tmp_path)

    assert quality.cmd_quality(["normalize-result", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source"] == "editor"
    assert result["resultType"] == "evidence"
    assert list(tmp_path.iterdir()) == []


def test_inv1_control_plan_has_exact_five_activity_contract():  # Tests INV-1
    plan = quality.load_control_plan()

    assert QUALITY_PLAN.is_file()
    assert set(plan) == {
        "schemaVersion",
        "policyVersion",
        "mode",
        "riskPolicy",
        "activities",
        "metrics",
    }
    assert plan["schemaVersion"] == 1
    assert plan["mode"] in {"disabled", "observe"}
    assert plan["riskPolicy"]["version"] == "risk-v1"
    assert [activity["id"] for activity in plan["activities"]] == ACTIVITY_IDS
    assert all(set(activity) == ACTIVITY_FIELDS for activity in plan["activities"])
    assert len(plan["metrics"]) == 12
    assert quality.validate_control_plan(plan) == plan


def test_fail1_control_plan_rejects_missing_unknown_and_invalid_fields():  # Tests FAIL-1
    plan = quality.load_control_plan()
    missing = deepcopy(plan)
    missing["activities"][0].pop("source")
    unknown = deepcopy(plan)
    unknown["activities"][0]["schedule"] = "daily"
    bad_inputs = deepcopy(plan)
    bad_inputs["activities"][0]["inputs"] = []
    bad_trigger = deepcopy(plan)
    bad_trigger["activities"][0]["trigger"] = ""
    bad_budget = deepcopy(plan)
    bad_budget["activities"][0]["budget"] = {"unit": "invocation-share", "limitPercent": 101}
    bad_escalation = deepcopy(plan)
    bad_escalation["activities"][0]["escalation"] = ""
    bad_retirement = deepcopy(plan)
    bad_retirement["activities"][0]["retirementCondition"] = ""
    bad_risk_policy = deepcopy(plan)
    bad_risk_policy["riskPolicy"]["resourceCeilings"]["normal"]["maxPercent"] = 11
    too_many_metrics = deepcopy(plan)
    too_many_metrics["metrics"].append(deepcopy(plan["metrics"][0]))
    bad_metric = deepcopy(plan)
    bad_metric["metrics"][0].pop("decision")

    for invalid in (
        missing,
        unknown,
        bad_inputs,
        bad_trigger,
        bad_budget,
        bad_escalation,
        bad_retirement,
        bad_risk_policy,
        too_many_metrics,
        bad_metric,
    ):
        with pytest.raises(ValueError, match="control plan"):
            quality.validate_control_plan(invalid)


def test_inv12_core_metrics_are_decision_linked_and_bounded():  # Tests INV-12
    plan = quality.load_control_plan()
    assert [metric["id"] for metric in plan["metrics"]] == list(quality.CORE_METRIC_IDS)
    assert all(
        set(metric) == quality.CORE_METRIC_FIELDS
        and all(isinstance(metric[field], str) and metric[field] for field in quality.CORE_METRIC_FIELDS - {"id"})
        for metric in plan["metrics"]
    )


def test_inv12_unknown_and_lower_bound_metrics_cannot_count_as_success():  # Tests INV-12
    report = quality.derive_core_metrics(
        results=[
            {"id": "r-1", "outcome": "accepted", "evidenceState": "lower-bound"},
            {"id": "r-2", "outcome": "unknown", "evidenceState": "unknown"},
        ],
        monitoring=[{"status": "recurrent", "evidenceState": "lower-bound"}],
    )

    assert report["metricCount"] == 12
    assert report["metrics"]["accepted-outcome-rate"]["state"] == "lower-bound"
    assert report["metrics"]["accepted-outcome-rate"]["decisionEligible"] is False
    assert report["metrics"]["recurrence-escape-rate"]["state"] == "lower-bound"
    assert report["metrics"]["recurrence-escape-rate"]["decisionEligible"] is False


def test_inv12_zero_tolerance_metrics_require_complete_evidence():  # Tests INV-12
    report = quality.derive_core_metrics(results=[{"id": "r-1"}])

    for metric_id in ("privacy-violation-count", "unauthorized-mutation-count"):
        metric = report["metrics"][metric_id]
        assert metric["state"] == "unknown"
        assert metric["decisionEligible"] is False


def _risk_request(**overrides):
    request = {
        "failureProbability": "possible",
        "consequence": "medium",
        "benefit": "high",
        "informationValue": "medium",
        "resourceCost": "low",
        "reversibility": "bounded",
        "uncertainty": "low",
        "hardGuards": {
            "safety": "pass",
            "authority": "pass",
            "privacy": "pass",
            "correctness": "pass",
        },
        "requestedMode": "observe",
        "resourceSharePercent": 7,
    }
    request.update(overrides)
    return request


def test_inv13_risk_assessment_reports_components_and_normal_ceiling():  # Tests INV-13
    assessment = quality.assess_risk(_risk_request())

    assert assessment["schemaVersion"] == 1
    assert assessment["decisionTreeVersion"] == "risk-v1"
    assert assessment["expectedLoss"] == 0.25
    assert assessment["expectedBenefit"] == 1.25
    assert assessment["expectedUtility"] == 0.9
    assert assessment["reversibility"] == "bounded"
    assert assessment["uncertainty"] == {"band": "low", "value": 0.1}
    assert assessment["guards"] == {
        "status": "pass",
        "failed": [],
        "unknown": [],
    }
    assert assessment["resourceBudget"] == {
        "class": "normal",
        "minPercent": 5,
        "maxPercent": 10,
        "requestedPercent": 7,
        "status": "within",
    }
    assert assessment["decision"] == "observe"
    assert assessment["route"] == "none"


def test_fail11_hard_guard_blocks_positive_utility():  # Tests FAIL-11
    assessment = quality.assess_risk(_risk_request(
        failureProbability="rare",
        consequence="critical",
        benefit="high",
        informationValue="high",
        hardGuards={
            "safety": "pass",
            "authority": "pass",
            "privacy": "fail",
            "correctness": "pass",
        },
    ))

    assert assessment["expectedUtility"] > 0
    assert assessment["guards"]["status"] == "blocked"
    assert assessment["guards"]["failed"] == ["privacy"]
    assert assessment["decision"] == "disabled"
    assert assessment["route"] == "human"

    irreversible = quality.assess_risk(_risk_request(
        requestedMode="autonomous",
        reversibility="irreversible",
    ))
    assert irreversible["decision"] == "human"
    assert irreversible["reason"] == "irreversible-effect"


def test_inv13_high_consequence_ceiling_and_unknown_budget_fail_closed():  # Tests INV-13
    canary = {
        "hypothesis": "A bounded review catches one known regression.",
        "evidenceRefs": ["artifact:canary-evidence"],
        "stopRule": "Stop after first privacy or correctness gap.",
        "errorBudget": {"maxFailures": 1},
    }
    assessment = quality.assess_risk(_risk_request(
        consequence="high",
        requestedMode="canary",
        resourceSharePercent=20,
        canary=canary,
    ))
    assert assessment["resourceBudget"]["maxPercent"] == 20
    assert assessment["resourceBudget"]["status"] == "within"
    assert assessment["decision"] == "canary"

    unknown = quality.assess_risk(_risk_request(
        requestedMode="autonomous",
        resourceSharePercent=None,
    ))
    assert unknown["resourceBudget"]["status"] == "unknown"
    assert unknown["decision"] == "human"
    assert unknown["route"] == "human"


def _capability_grant():
    return {
        "action": "edit",
        "effects": ["workspace.write"],
        "model": "openai/gpt-5",
        "thinking": "high",
        "toolset": ["read", "edit", "bash"],
        "contextPolicy": "task-scoped",
        "proof": {"required": ["tests"], "evidenceRefs": ["artifact:grant-proof"]},
        "rollout": {"maxActions": 1, "maxEffects": 1},
        "expiry": "2099-01-01T00:00:00Z",
    }


def test_inv14_capability_grant_fingerprint_excludes_only_mutable_state():  # Tests INV-14
    grant = quality.normalize_capability_grant(_capability_grant(), require_future=True)
    active = {**grant, "revocation": {"status": "active", "reason": None, "at": None}}

    assert grant["schemaVersion"] == 1
    assert quality.capability_grant_fingerprint(grant) == quality.capability_grant_fingerprint(active)
    assert quality.capability_grant_status(active) == "active"

    with pytest.raises(ValueError, match="capability grant"):
        quality.normalize_capability_grant({**_capability_grant(), "rollout": {"maxActions": 0, "maxEffects": 1}})


def test_fail12_expired_capability_grant_is_not_active():  # Tests FAIL-12
    grant = _capability_grant()
    grant["expiry"] = "2020-01-01T00:00:00Z"
    grant["revocation"] = {"status": "active", "reason": None, "at": None}

    assert quality.capability_grant_status(grant) == "expired"
    with pytest.raises(ValueError, match="capability grant fields"):
        quality.normalize_capability_grant({**grant, "conditions": ["if tests pass"]})


def test_fail11_canary_requires_learning_contract_and_ceiling():  # Tests FAIL-11
    with pytest.raises(ValueError, match="canary"):
        quality.assess_risk(_risk_request(
            consequence="high",
            requestedMode="canary",
            resourceSharePercent=20,
        ))

    canary = {
        "hypothesis": "A bounded review catches one known regression.",
        "evidenceRefs": ["artifact:canary-evidence"],
        "stopRule": "Stop after first privacy or correctness gap.",
        "errorBudget": {"maxFailures": 1},
    }
    with pytest.raises(ValueError, match="ceiling"):
        quality.assess_risk(_risk_request(
            consequence="medium",
            requestedMode="canary",
            resourceSharePercent=11,
            canary=canary,
        ))
    with pytest.raises(ValueError, match="canary"):
        quality.assess_risk(_risk_request(
            consequence="high",
            requestedMode="canary",
            resourceSharePercent=20,
            reversibility="irreversible",
            canary=canary,
        ))
    with pytest.raises(ValueError, match="evidence"):
        quality.assess_risk(_risk_request(
            consequence="high",
            requestedMode="canary",
            resourceSharePercent=20,
            canary={**canary, "evidenceRefs": []},
        ))


def _snapshot(*, triggered=True, gaps=None):
    return {
        "schemaVersion": 1,
        "triggered": triggered,
        "evidenceRefs": ["run:quality-1"],
        "gaps": list(gaps or []),
        "signals": {"settledResults": 3},
    }


def test_inv2_assessment_is_deterministic_and_emits_at_most_one_packet(tmp_path):  # Tests INV-2
    first = quality.assess(_snapshot(), "work-learning", directory=tmp_path)
    second = quality.assess(_snapshot(), "work-learning", directory=tmp_path)

    assert first == second
    assert first["mode"] == "observe"
    assert first["authority"] == {"status": "unknown", "allowedEffects": []}
    assert isinstance(first["workPacket"], dict)
    assert first["workPacket"]["allowedEffects"] == []
    assert first["workPacket"]["labels"] == ["quality:work-learning"]
    assert first["receiptId"] == first["dedupeKey"]
    receipts = (tmp_path / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(receipts) == 1
    assert json.loads(receipts[0]) == first


def _closed_impl(bead_id):
    return {
        "id": bead_id,
        "title": f"Implement {bead_id}",
        "issue_type": "task",
        "status": "closed",
        "closed_at": "2026-07-09T01:00:00Z",
        "labels": ["implementation"],
    }


def test_inv5_durable_activity_snapshots_map_signals_and_suppress_legacy_duplicates():  # Tests INV-5
    beads = [
        _closed_impl("pi-1"),
        _closed_impl("pi-2"),
        _closed_impl("pi-3"),
        {
            "id": "pi-coherence-open",
            "title": "Legacy context review",
            "issue_type": "task",
            "status": "open",
            "labels": ["maintenance:context-health"],
        },
        {
            "id": "pi-human-1",
            "title": "Human blocker",
            "issue_type": "decision",
            "status": "open",
            "labels": ["human"],
        },
        {
            "id": "pi-human-2",
            "title": "Another human blocker",
            "issue_type": "decision",
            "status": "open",
            "labels": ["human"],
        },
    ]
    snapshots = quality.durable_activity_snapshots(
        beads=beads,
        runs=[{"status": "failed"}, {"status": "blocked"}],
        git_summary={"commitsSinceQualityReview": 6},
        health_report={"summary": {"warningCount": 2, "failureCount": 0}},
        context_health_report={"summary": {"warningCount": 2}},
        improvement_review_report={"status": "ok", "eligibleSessions": 0},
        thresholds={
            "closedImplementationBeads": 3,
            "commits": 5,
            "failedOrBlockedRuns": 2,
            "humanBlockers": 2,
            "contextWarnings": 1,
            "healthWarnings": 1,
        },
    )

    assert list(snapshots) == ACTIVITY_IDS
    assert snapshots["work-learning"]["triggered"] is True
    coherence = snapshots["architecture-coherence"]
    assert coherence["triggered"] is False
    assert coherence["signals"]["duplicateSuppressed"] is True
    assert set(coherence["signals"]["triggeredSignals"]) == {
        "closedImplementationBeads",
        "commitsSinceQualityReview",
        "failedOrBlockedRuns",
        "contextWarnings",
        "healthWarnings",
    }
    assert coherence["signals"]["activityLabel"] == "quality:architecture-coherence"
    assert all(
        snapshot["signals"]["activityLabel"] == f"quality:{activity}"
        for activity, snapshot in snapshots.items()
    )
    assert all(
        "maintenance:" not in json.dumps(snapshot, sort_keys=True)
        for snapshot in snapshots.values()
    )


@pytest.mark.parametrize(
    ("label", "activity"),
    [
        ("maintenance:design-review", "architecture-coherence"),
        ("maintenance:architecture-review", "architecture-coherence"),
        ("maintenance:simplification", "architecture-coherence"),
        ("maintenance:workflow-retro", "work-learning"),
        ("maintenance:context-health", "architecture-coherence"),
        ("maintenance:improvement-review", "work-learning"),
        ("maintenance:lessons-harvest", "work-learning"),
    ],
)
def test_legacy_maintenance_labels_are_read_compatible_only(label, activity):
    bead = {"status": "open", "labels": [label]}

    assert quality.open_quality_activities([bead]) == {activity}


def test_durable_work_learning_preserves_lower_bound_and_unknown_evidence():
    base = {
        "beads": [],
        "runs": [],
        "git_summary": {"commitsSinceQualityReview": 0},
        "health_report": {"summary": {}},
        "context_health_report": {"summary": {}},
        "thresholds": {"eligibleUnreviewedSessions": 5},
    }

    lower_bound = quality.durable_activity_snapshots(
        **base,
        improvement_review_report={
            "status": "ok",
            "eligibleSessions": 2,
            "lowerBound": True,
        },
    )["work-learning"]
    unknown = quality.durable_activity_snapshots(
        **base,
        improvement_review_report={"status": "unavailable"},
    )["work-learning"]

    assert lower_bound["triggered"] is False
    assert lower_bound["signals"]["eligibleUnreviewedSessions"] == 2
    assert lower_bound["gaps"] == ["eligible-sessions-lower-bound"]
    assert unknown["triggered"] is False
    assert unknown["signals"]["eligibleUnreviewedSessions"] is None
    assert unknown["gaps"] == ["eligible-sessions-unknown"]


def test_legacy_checkpoints_bound_git_and_eligible_session_queries():
    calls = {"git": [], "improvement": []}
    beads = [
        {
            "status": "closed",
            "closed_at": "2026-07-20T00:00:00Z",
            "labels": ["maintenance:architecture-review"],
        },
        {
            "status": "closed",
            "closed_at": "2026-07-25T00:00:00Z",
            "labels": ["maintenance:improvement-review"],
        },
    ]

    def git_provider(_root, *, since):
        calls["git"].append(since)
        return {"commitsSinceQualityReview": 0}

    def improvement_provider(**kwargs):
        calls["improvement"].append(kwargs)
        return {"status": "ok", "eligibleSessions": 0}

    quality.durable_activity_snapshots(
        beads=beads,
        runs=[],
        health_report={"summary": {}},
        context_health_report={"summary": {}},
        git_summary_provider=git_provider,
        improvement_review_provider=improvement_provider,
    )

    assert calls["git"][0].isoformat().replace("+00:00", "Z") == "2026-07-20T00:00:00Z"
    assert calls["improvement"][0]["since"] == "2026-07-25T00:00:00Z"


def test_fail2_assessment_rejects_malformed_snapshot_and_unsafe_evidence(tmp_path):  # Tests FAIL-2
    with pytest.raises(ValueError, match="snapshot"):
        quality.assess({**_snapshot(), "rawPrompt": "private"}, "capture", directory=tmp_path)
    with pytest.raises(ValueError, match="evidence"):
        quality.assess(
            {**_snapshot(), "evidenceRefs": ["https://private.example"]},
            "capture",
            directory=tmp_path,
        )
    with pytest.raises(ValueError, match="activity"):
        quality.assess(_snapshot(), "unknown-activity", directory=tmp_path)


def test_inv3_apply_is_private_observe_only_and_idempotent(tmp_path):  # Tests INV-3
    receipt = quality.assess(_snapshot(gaps=["review-context-unavailable"]), "work-learning", directory=tmp_path)

    first = quality.apply(receipt["receiptId"], directory=tmp_path)
    second = quality.apply(receipt["receiptId"], directory=tmp_path)

    assert first == second
    assert first == {
        "schemaVersion": 1,
        "status": "observed",
        "receiptId": receipt["receiptId"],
        "activity": "work-learning",
        "authority": {"status": "unknown", "allowedEffects": []},
        "assignmentRef": f"artifact:quality-assignment-{receipt['receiptId']}",
    }
    assert len((tmp_path / "applications.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assignments = list((tmp_path / "assignments").glob("*.json"))
    assert len(assignments) == 1
    assert json.loads(assignments[0].read_text(encoding="utf-8")) == receipt["workPacket"]


def test_inv4_disabled_and_stale_policy_cannot_create_assignment(tmp_path):  # Tests INV-4
    plan = quality.load_control_plan()
    disabled = deepcopy(plan)
    disabled["mode"] = "disabled"
    policy_path = tmp_path / "control-plan.json"
    policy_path.write_text(json.dumps(disabled), encoding="utf-8")

    receipt = quality.assess(_snapshot(), "capture", directory=tmp_path, plan_path=policy_path)
    assert receipt["mode"] == "disabled"
    assert receipt["workPacket"] is None
    assert quality.apply(receipt["receiptId"], directory=tmp_path, plan_path=policy_path)["status"] == "disabled"
    assert not (tmp_path / "assignments").exists()

    current = deepcopy(plan)
    policy_path.write_text(json.dumps(current), encoding="utf-8")
    stale = quality.assess(_snapshot(), "capture", directory=tmp_path, plan_path=policy_path)
    current["policyVersion"] = f'{plan["policyVersion"]}-changed'
    policy_path.write_text(json.dumps(current), encoding="utf-8")
    blocked = quality.apply(stale["receiptId"], directory=tmp_path, plan_path=policy_path)
    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "policy-mismatch"
    assert not (tmp_path / "assignments").exists()


def test_fail3_non_triggered_receipt_cannot_smuggle_assignment(tmp_path):  # Tests FAIL-3
    packet = quality.assess(_snapshot(), "capture", directory=tmp_path)["workPacket"]
    receipt = quality.assess(_snapshot(triggered=False), "capture", directory=tmp_path)
    tampered = {**receipt, "workPacket": packet}
    core = {key: value for key, value in tampered.items() if key not in {"receiptId", "dedupeKey"}}
    tampered_id = "quality-" + quality._fingerprint(core).partition(":")[2]
    tampered.update({"receiptId": tampered_id, "dedupeKey": tampered_id})
    with (tmp_path / "receipts.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(ValueError, match="receipt"):
        quality.apply(tampered_id, directory=tmp_path)
    assert not (tmp_path / "assignments").exists()


def test_fail3_apply_rejects_missing_receipt(tmp_path):  # Tests FAIL-3
    with pytest.raises(ValueError, match="receipt"):
        quality.apply("missing-receipt", directory=tmp_path)


def test_fail3_status_rejects_inconsistent_application(tmp_path):  # Tests FAIL-3
    application = {
        "schemaVersion": 1,
        "status": "observed",
        "receiptId": "quality-receipt",
        "activity": "capture",
        "authority": {"status": "unknown", "allowedEffects": []},
        "assignmentRef": None,
    }
    path = tmp_path / "applications.jsonl"
    path.write_text(json.dumps(application) + "\n", encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(ValueError, match="application"):
        quality.quality_status(directory=tmp_path)


def test_quality_assess_apply_status_cli_contract(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: tmp_path)
    snapshot = json.dumps(_snapshot())

    assert quality.cmd_quality([
        "assess",
        "--activity",
        "architecture-coherence",
        "--snapshot",
        snapshot,
        "--json",
    ]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["activity"] == "architecture-coherence"

    assert quality.cmd_quality(["apply", "--receipt", receipt["receiptId"], "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "observed"

    assert quality.cmd_quality(["status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status == {
        "schemaVersion": 1,
        "status": "ok",
        "mode": "observe",
        "policyVersion": receipt["policyVersion"],
        "policyFingerprint": receipt["policyFingerprint"],
        "receipts": 1,
        "applications": 1,
        "assignments": 1,
    }

    assert quality.cmd_quality([
        "assess",
        "--activity",
        "unknown-activity",
        "--snapshot",
        snapshot,
        "--json",
    ]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "schemaVersion": 1,
        "status": "error",
        "error": "quality assess failed",
    }


def test_quality_assess_cli_collects_durable_activity_snapshot(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: tmp_path)
    monkeypatch.setattr(
        quality,
        "durable_activity_snapshots",
        lambda **_kwargs: {
            activity: _snapshot(triggered=activity == "work-learning")
            for activity in ACTIVITY_IDS
        },
    )

    assert quality.cmd_quality([
        "assess",
        "--activity",
        "work-learning",
        "--collect",
        "--no-beads",
        "--json",
    ]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["activity"] == "work-learning"
    assert receipt["workPacket"]["labels"] == ["quality:work-learning"]


def test_quality_assess_collect_rejects_unknown_activity_with_sanitized_error(
    monkeypatch, tmp_path, capsys
):  # Tests FAIL-2
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: tmp_path)
    monkeypatch.setattr(
        quality,
        "durable_activity_snapshots",
        lambda **_kwargs: {activity: _snapshot() for activity in ACTIVITY_IDS},
    )

    assert quality.cmd_quality([
        "assess",
        "--activity",
        "unknown-activity",
        "--collect",
        "--json",
    ]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "schemaVersion": 1,
        "status": "error",
        "error": "quality assess failed",
    }


def _canary_plan(tmp_path):
    plan = deepcopy(quality.load_control_plan())
    plan["mode"] = "canary"
    plan["policyVersion"] = "canary-v1"
    path = tmp_path / "control-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _canary_request():
    return {
        **_risk_request(
            requestedMode="canary",
            resourceSharePercent=7,
        ),
        "canary": {
            "hypothesis": "A bounded effect preserves the reviewed invariant.",
            "evidenceRefs": ["artifact:canary-proof"],
            "stopRule": "Stop on any missing proof or critical failure.",
            "errorBudget": {"maxFailures": 1},
        },
    }


def _canary_authority():
    grant = _capability_grant()
    return {
        "decisionBead": "pi-grant.1",
        "grantFingerprint": quality.capability_grant_fingerprint(grant),
        "allowedEffects": list(grant["effects"]),
    }, grant


def _canary_snapshot():
    authority, _grant = _canary_authority()
    return {
        **_snapshot(),
        "evidenceRefs": ["artifact:canary-proof", "artifact:grant-proof"],
        "gaps": [],
        "riskRequest": _canary_request(),
        "authority": authority,
        "target": {
            "kind": "quality-target",
            "id": "target-1",
            "fingerprint": "sha256:" + "1" * 64,
        },
        "effect": {
            "action": "edit",
            "effects": ["workspace.write"],
            "reversibility": "bounded",
        },
    }


def _canary_resolver(_decision):
    _authority, grant = _canary_authority()
    return {
        "schemaVersion": 1,
        "decisionBead": "pi-grant.1",
        "status": "active",
        "grant": {**grant, "revocation": {"status": "active", "reason": None, "at": None}},
        "grantFingerprint": quality.capability_grant_fingerprint(grant),
        "resolver": {"kind": "human-ui"},
        "allowedEffects": list(grant["effects"]),
    }


def test_inv15_canary_revalidates_grant_target_and_dispatches_once(tmp_path):  # Tests INV-15
    receipt = quality.assess(
        _canary_snapshot(),
        "work-learning",
        directory=tmp_path,
        plan_path=_canary_plan(tmp_path),
    )
    dispatched = []
    revoked = []

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=_canary_plan(tmp_path),
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda packet: dispatched.append(packet) or {
            "status": "succeeded",
            "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
            "effects": ["workspace.write"],
            "proof": ["tests"],
            "targetFingerprint": "sha256:" + "1" * 64,
        },
        revoke_grant=lambda decision, reason: revoked.append((decision, reason)),
    )

    assert result["status"] == "applied"
    assert result["receiptId"] == receipt["receiptId"]
    assert len(dispatched) == 1
    assert revoked == []
    claims = (tmp_path / quality.CLAIMS_NAME).read_text(encoding="utf-8").splitlines()
    assert [json.loads(row)["state"] for row in claims] == ["claimed", "dispatched"]


def test_inv15_concurrent_canary_apply_consumes_one_allowance(tmp_path):  # Tests INV-15
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(
        _canary_snapshot(),
        "work-learning",
        directory=tmp_path,
        plan_path=plan_path,
    )
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def dispatch(_packet):
        calls.append("dispatch")
        entered.set()
        release.wait(timeout=2)
        return {
            "status": "succeeded",
            "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
            "effects": ["workspace.write"],
            "proof": ["tests"],
            "targetFingerprint": "sha256:" + "1" * 64,
        }

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            quality.apply,
            receipt["receiptId"],
            directory=tmp_path,
            plan_path=plan_path,
            grant_resolver=_canary_resolver,
            target_resolver=lambda target: target,
            dispatcher=dispatch,
        )
        assert entered.wait(timeout=2)
        second = pool.submit(
            quality.apply,
            receipt["receiptId"],
            directory=tmp_path,
            plan_path=plan_path,
            grant_resolver=_canary_resolver,
            target_resolver=lambda target: target,
            dispatcher=dispatch,
        )
        assert second.result(timeout=2)["reason"] in {"claim-uncertain", "grant-uncertain"}
        release.set()
        assert first.result(timeout=2)["status"] == "applied"

    assert calls == ["dispatch"]


def test_fail13_canary_unknown_result_revokes_grant(tmp_path):  # Tests FAIL-13
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(
        _canary_snapshot(),
        "work-learning",
        directory=tmp_path,
        plan_path=plan_path,
    )
    revoked = []

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda _packet: {"status": "unknown", "evidenceRefs": []},
        revoke_grant=lambda decision, reason: revoked.append((decision, reason)),
    )

    assert result["status"] == "revoked"
    assert result["reason"] == "unknown-result"
    assert revoked == [("pi-grant.1", "unknown-result")]


def test_fail13_canary_critical_signal_revokes_even_on_success_status(tmp_path):  # Tests FAIL-13
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(_canary_snapshot(), "work-learning", directory=tmp_path, plan_path=plan_path)
    revoked = []

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda _packet: {
            "status": "succeeded",
            "failureClass": "correctness",
            "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
            "proof": ["tests"],
            "effects": ["workspace.write"],
            "targetFingerprint": "sha256:" + "1" * 64,
        },
        revoke_grant=lambda decision, reason: revoked.append((decision, reason)),
    )

    assert result["status"] == "revoked"
    assert result["reason"] == "critical-failure"
    assert revoked == [("pi-grant.1", "critical-failure")]


def test_inv15_canary_error_budget_blocks_before_dispatch(tmp_path):  # Tests INV-15
    plan_path = _canary_plan(tmp_path)
    snapshot = _canary_snapshot()
    snapshot["riskRequest"]["canary"]["errorBudget"] = {"maxFailures": 0}
    receipt = quality.assess(snapshot, "work-learning", directory=tmp_path, plan_path=plan_path)
    dispatched = []

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda packet: dispatched.append(packet),
    )

    assert result["reason"] == "error-budget-exhausted"
    assert dispatched == []


def test_inv15_canary_noncritical_failure_does_not_revoke_grant(tmp_path):  # Tests INV-15
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(
        _canary_snapshot(),
        "work-learning",
        directory=tmp_path,
        plan_path=plan_path,
    )
    revoked = []

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda _packet: {
            "status": "failed",
            "failureClass": "process",
            "evidenceRefs": [],
        },
        revoke_grant=lambda decision, reason: revoked.append((decision, reason)),
    )

    assert result == {
        "schemaVersion": 1,
        "status": "failed",
        "receiptId": receipt["receiptId"],
        "reason": "effect-failure",
    }
    assert revoked == []


def test_inv15_claim_dispatch_settle_passes_explicit_token_and_releases_lock(tmp_path):  # Tests INV-15
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(_canary_snapshot(), "work-learning", directory=tmp_path, plan_path=plan_path)
    proof = {
        "status": "succeeded",
        "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
        "effects": ["workspace.write"],
        "proof": ["tests"],
        "targetFingerprint": "sha256:" + "1" * 64,
    }
    seen = []

    def dispatcher(packet, claim_token):
        seen.append((packet, claim_token))
        settled = quality.settle(claim_token, proof, directory=tmp_path)
        assert settled["status"] == "applied"
        return proof

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=dispatcher,
    )

    assert result["status"] == "applied"
    assert seen[0][0] == receipt["workPacket"]
    assert seen[0][1]["receiptId"] == receipt["receiptId"]
    assert seen[0][1]["claimId"]
    assert seen[0][1]["policyFingerprint"] == receipt["policyFingerprint"]
    rows = [json.loads(line) for line in (tmp_path / quality.CLAIMS_NAME).read_text().splitlines()]
    assert [row["state"] for row in rows] == ["claimed", "dispatched"]
    assert rows[0]["claimId"] == seen[0][1]["claimId"]


def test_inv15_concurrent_same_grant_claims_reserve_one_allowance(tmp_path):  # Tests INV-15
    plan_path = _canary_plan(tmp_path)
    first_receipt = quality.assess(_canary_snapshot(), "work-learning", directory=tmp_path, plan_path=plan_path)
    second_snapshot = _canary_snapshot()
    second_snapshot["evidenceRefs"] = ["artifact:canary-proof", "artifact:grant-proof", "run:quality-2"]
    second_receipt = quality.assess(second_snapshot, "work-learning", directory=tmp_path, plan_path=plan_path)
    entered = threading.Event()
    release = threading.Event()
    proof = {
        "status": "succeeded",
        "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
        "effects": ["workspace.write"],
        "proof": ["tests"],
        "targetFingerprint": "sha256:" + "1" * 64,
    }

    def dispatcher(_packet):
        entered.set()
        release.wait(timeout=2)
        return proof

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            quality.apply,
            first_receipt["receiptId"],
            directory=tmp_path,
            plan_path=plan_path,
            grant_resolver=_canary_resolver,
            target_resolver=lambda target: target,
            dispatcher=dispatcher,
        )
        assert entered.wait(timeout=2)
        second = pool.submit(
            quality.apply,
            second_receipt["receiptId"],
            directory=tmp_path,
            plan_path=plan_path,
            grant_resolver=_canary_resolver,
            target_resolver=lambda target: target,
            dispatcher=lambda _packet: pytest.fail("same grant must not dispatch concurrently"),
        )
        assert second.result(timeout=2)["reason"] == "grant-uncertain"
        release.set()
        assert first.result(timeout=2)["status"] == "applied"

    rows = [json.loads(line) for line in (tmp_path / quality.CLAIMS_NAME).read_text().splitlines()]
    assert len(rows) == 2
    assert [row["state"] for row in rows] == ["claimed", "dispatched"]


def test_fail13_dispatch_exception_settles_uncertain_and_blocks_retry(tmp_path):  # Tests FAIL-13
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(_canary_snapshot(), "work-learning", directory=tmp_path, plan_path=plan_path)
    calls = []

    def failing_dispatcher(_packet):
        calls.append("dispatch")
        raise TimeoutError("adapter timed out")

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=failing_dispatcher,
    )

    assert result == {
        "schemaVersion": 1,
        "status": "blocked",
        "receiptId": receipt["receiptId"],
        "reason": "claim-uncertain",
    }
    rows = [json.loads(line) for line in (tmp_path / quality.CLAIMS_NAME).read_text().splitlines()]
    assert [row["state"] for row in rows] == ["claimed", "uncertain"]
    retry = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda _packet: calls.append("retry"),
    )
    assert retry["reason"] == "claim-uncertain"
    assert calls == ["dispatch"]


def test_fail13_settlement_rejects_forged_claim_context(tmp_path):  # Tests FAIL-13
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(_canary_snapshot(), "work-learning", directory=tmp_path, plan_path=plan_path)
    proof = {
        "status": "succeeded",
        "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
        "effects": ["workspace.write"],
        "proof": ["tests"],
        "targetFingerprint": "sha256:" + "1" * 64,
    }

    def dispatcher(_packet, claim_token):
        forged = {**claim_token, "effects": ["workspace.delete"]}
        with pytest.raises(ValueError, match="unavailable or conflicts"):
            quality.settle(forged, proof, directory=tmp_path)
        return proof

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=dispatcher,
    )

    assert result["status"] == "applied"
    rows = [json.loads(line) for line in (tmp_path / quality.CLAIMS_NAME).read_text().splitlines()]
    assert rows[-1]["state"] == "dispatched"
    assert rows[-1]["effectSet"] == ["workspace.write"]


def test_fail13_settlement_downgrades_unknown_dispatched_state_to_uncertain(tmp_path):  # Tests FAIL-13
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(_canary_snapshot(), "work-learning", directory=tmp_path, plan_path=plan_path)
    proof = {
        "status": "succeeded",
        "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
        "effects": ["workspace.write"],
        "proof": ["tests"],
        "targetFingerprint": "sha256:" + "1" * 64,
    }

    def dispatcher(_packet, claim_token):
        settled = quality.settle(
            claim_token,
            {"status": "unknown", "evidenceRefs": []},
            directory=tmp_path,
            state="dispatched",
        )
        assert settled["reason"] == "claim-uncertain"
        return proof

    result = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=dispatcher,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "claim-uncertain"
    rows = [json.loads(line) for line in (tmp_path / quality.CLAIMS_NAME).read_text().splitlines()]
    assert rows[-1]["state"] == "uncertain"


def test_inv15_settlement_is_idempotent_after_terminal_state(tmp_path):  # Tests INV-15
    plan_path = _canary_plan(tmp_path)
    receipt = quality.assess(_canary_snapshot(), "work-learning", directory=tmp_path, plan_path=plan_path)
    proof = {
        "status": "succeeded",
        "evidenceRefs": ["result:canary", "artifact:canary-proof", "artifact:grant-proof"],
        "effects": ["workspace.write"],
        "proof": ["tests"],
        "targetFingerprint": "sha256:" + "1" * 64,
    }
    calls = []

    first = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda _packet: calls.append("dispatch") or proof,
    )
    second = quality.apply(
        receipt["receiptId"],
        directory=tmp_path,
        plan_path=plan_path,
        grant_resolver=_canary_resolver,
        target_resolver=lambda target: target,
        dispatcher=lambda _packet: calls.append("retry") or proof,
    )

    assert first["status"] == second["status"] == "applied"
    assert calls == ["dispatch"]
    rows = (tmp_path / quality.CLAIMS_NAME).read_text().splitlines()
    assert len(rows) == 2
