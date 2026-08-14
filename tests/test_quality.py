from __future__ import annotations

import json
import stat
import sys
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


def test_inv8_review_assignment_is_bounded_private_and_non_authorizing():  # Tests INV-8
    evidence_refs = [
        _shared_evidence_ref(ref=f"artifact:improvement-report-session-{index}")
        for index in range(2)
    ]
    kwargs = {
        "activity": "work-learning",
        "action": {
            "id": "review",
            "routingTask": "review",
            "outputContract": "findings-with-evidence",
        },
        "scope": {
            "kind": "improvement-session-cohort",
            "id": "report-0123456789abcdef",
            "itemCount": 2,
            "maxItems": 20,
        },
        "evidence_refs": evidence_refs,
        "rubric": {
            "path": "pi/agent/langfuse/improvement-review.md",
            "version": "v4",
        },
    }

    assignment = quality.build_review_assignment(**kwargs)

    assert assignment == quality.build_review_assignment(**kwargs)
    assert quality.validate_review_assignment(assignment) == assignment
    assert assignment["evidenceRefs"] == evidence_refs
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


def test_inv1_control_plan_has_exact_five_activity_contract():  # Tests INV-1
    plan = quality.load_control_plan()

    assert QUALITY_PLAN.is_file()
    assert set(plan) == {"schemaVersion", "policyVersion", "mode", "activities"}
    assert plan["schemaVersion"] == 1
    assert plan["mode"] in {"disabled", "observe"}
    assert [activity["id"] for activity in plan["activities"]] == ACTIVITY_IDS
    assert all(set(activity) == ACTIVITY_FIELDS for activity in plan["activities"])
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

    for invalid in (
        missing,
        unknown,
        bad_inputs,
        bad_trigger,
        bad_budget,
        bad_escalation,
        bad_retirement,
    ):
        with pytest.raises(ValueError, match="control plan"):
            quality.validate_control_plan(invalid)


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
