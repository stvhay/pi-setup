from __future__ import annotations

import json
from unittest.mock import patch


def _closed_impl(bead_id: str) -> dict:
    return {
        "id": bead_id,
        "title": f"Implement {bead_id}",
        "issue_type": "task",
        "status": "closed",
        "closed_at": "2026-07-09T01:00:00Z",
        "labels": ["implementation", "agent-os"],
    }


def test_maintenance_due_report_derives_signals_and_suppresses_open_duplicates(agnt):
    beads = [
        _closed_impl("pi-1"),
        _closed_impl("pi-2"),
        _closed_impl("pi-3"),
        {
            "id": "pi-maint-open",
            "title": "Design review already open",
            "issue_type": "task",
            "status": "open",
            "labels": ["maintenance:design-review", "maintenance"],
        },
        {
            "id": "pi-human-1",
            "title": "Resolve human blocker",
            "issue_type": "task",
            "status": "open",
            "labels": ["human", "human-gate"],
        },
        {
            "id": "pi-human-2",
            "title": "Resolve another human blocker",
            "issue_type": "task",
            "status": "open",
            "labels": ["human", "human-gate"],
        },
    ]
    runs = [
        {"id": "run-failed", "status": "failed", "sessionRef": "pi-session-id:failed"},
        {"id": "run-blocked", "status": "blocked", "sessionRef": "pi-session-id:blocked"},
        {"id": "run-ok", "status": "succeeded", "sessionRef": "pi-session-id:ok"},
    ]
    health = {
        "summary": {"failureCount": 0, "warningCount": 2},
        "findings": [{"id": "orphaned-run-bead", "severity": "warning"}, {"id": "dirty-main-checkout", "severity": "warning"}],
    }
    context = {"summary": {"warningCount": 2}, "warnings": [{"id": "overlap"}, {"id": "stale"}]}

    report = agnt.maintenance_due_report(
        beads=beads,
        runs=runs,
        git_summary={"commitsSinceMaintenance": 6},
        health_report=health,
        context_health_report=context,
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

    due_modes = {item["mode"] for item in report["due"]}
    suppressed_modes = {item["mode"] for item in report["suppressed"]}
    assert "design-review" in suppressed_modes
    assert due_modes == {"architecture-review", "simplification", "workflow-retro", "context-health"}
    assert report["signals"]["failedOrBlockedRuns"] == 2


def test_improvement_review_due_uses_only_safe_eligible_session_count(agnt):
    report = agnt.maintenance_due_report(
        beads=[],
        runs=[],
        git_summary={"commitsSinceMaintenance": 0},
        health_report={"summary": {}},
        context_health_report={"summary": {}},
        improvement_review_report={"status": "ok", "eligibleSessions": 6},
        thresholds={
            "closedImplementationBeads": 99,
            "commits": 99,
            "failedOrBlockedRuns": 99,
            "humanBlockers": 99,
            "contextWarnings": 99,
            "healthWarnings": 99,
            "healthFailures": 99,
            "eligibleUnreviewedSessions": 5,
        },
    )

    assert [item["mode"] for item in report["due"]] == ["improvement-review"]
    assert report["signals"]["eligibleUnreviewedSessions"] == 6
    spec = agnt.maintenance_bead_specs(report)[0]
    assert spec["label"] == "maintenance:improvement-review"
    assert "Signals:" not in spec["description"]
    assert "Langfuse" not in spec["description"]
    assert "private" not in spec["description"].lower()
    assert json.loads(spec["metadata"])["pi"]["action"] == "review"


def test_improvement_review_failure_is_unknown_not_not_due(agnt):
    report = agnt.maintenance_due_report(
        beads=[],
        runs=[],
        git_summary={"commitsSinceMaintenance": 0},
        health_report={"summary": {}},
        context_health_report={"summary": {}},
        improvement_review_report={"status": "unavailable"},
    )

    assert report["signals"]["eligibleUnreviewedSessions"] is None
    assert "improvement-review" not in {item["mode"] for item in report["due"]}
    assert report["warnings"] == [
        "private improvement telemetry unavailable; improvement-review due state is unknown"
    ]


def test_incomplete_eligible_count_warns_when_below_threshold(agnt):
    report = agnt.maintenance_due_report(
        beads=[],
        runs=[],
        git_summary={"commitsSinceMaintenance": 0},
        health_report={"summary": {}},
        context_health_report={"summary": {}},
        improvement_review_report={"status": "ok", "eligibleSessions": 2, "lowerBound": True},
        thresholds={"eligibleUnreviewedSessions": 5},
    )

    assert "improvement-review" not in {item["mode"] for item in report["due"]}
    assert report["warnings"] == [
        "eligible unreviewed session count is incomplete; improvement-review due state may be understated"
    ]


def test_improvement_checkpoint_does_not_reset_other_maintenance_cadence(agnt):
    calls = []
    beads = [
        {
            "id": "pi-architecture",
            "status": "closed",
            "closed_at": "2026-07-20T00:00:00Z",
            "labels": ["maintenance:architecture-review"],
        },
        {
            "id": "pi-improvement",
            "status": "closed",
            "closed_at": "2026-07-25T00:00:00Z",
            "labels": ["maintenance:improvement-review"],
        },
    ]

    def git_summary(_root, *, since):
        calls.append(since)
        return {"commitsSinceMaintenance": 0}

    with patch.dict(agnt.maintenance_due_report.__globals__, {"git_commit_summary": git_summary}):
        agnt.maintenance_due_report(
            beads=beads,
            runs=[],
            health_report={"summary": {}},
            context_health_report={"summary": {}},
            improvement_review_report={"status": "ok", "eligibleSessions": 0},
        )

    assert calls[0].isoformat().replace("+00:00", "Z") == "2026-07-20T00:00:00Z"


def test_closed_legacy_lessons_checkpoint_bounds_improvement_review_query(agnt):
    calls = []

    def provider(**kwargs):
        calls.append(kwargs)
        return {"status": "ok", "eligibleSessions": 0}

    report = agnt.maintenance_due_report(
        beads=[{
            "id": "pi-legacy",
            "status": "closed",
            "closed_at": "2026-07-20T01:02:03Z",
            "labels": ["maintenance:lessons-harvest"],
        }],
        runs=[],
        git_summary={"commitsSinceMaintenance": 0},
        health_report={"summary": {}},
        context_health_report={"summary": {}},
        improvement_review_provider=provider,
    )

    assert calls[0]["since"] == "2026-07-20T01:02:03Z"
    assert report["lastImprovementReviewAt"] == "2026-07-20T01:02:03Z"
    assert all(item["label"] != "maintenance:lessons-harvest" for item in report["due"])


def test_read_only_maintenance_specs_use_a_dispatchable_review_action(agnt):
    report = {"due": [{"mode": "workflow-retro", "label": "maintenance:workflow-retro", "reason": "human blockers"}]}

    spec = agnt.maintenance_bead_specs(report)[0]
    metadata = json.loads(spec["metadata"])

    assert metadata["pi"]["action"] == "review"
    assert agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "report findings"})["status"] == "dispatchable"


def test_maintenance_create_beads_dry_run_outputs_specs_and_approval_gates_refactors(agnt):
    report = {
        "schemaVersion": 1,
        "due": [
            {"mode": "workflow-retro", "label": "maintenance:workflow-retro", "reason": "closed implementation threshold"},
            {"mode": "simplification", "label": "maintenance:simplification", "reason": "failed runs threshold"},
        ],
        "signals": {"closedImplementationBeads": 4, "failedOrBlockedRuns": 2},
    }
    calls = []

    result = agnt.maintenance_create_beads(report, dry_run=True, beads_runner=lambda args: calls.append(args) or (0, {}, ""))

    assert result["dryRun"] is True
    assert calls == []
    assert [spec["label"] for spec in result["beads"]] == ["maintenance:workflow-retro", "maintenance:simplification"]
    simplify = result["beads"][1]
    metadata = json.loads(simplify["metadata"])
    assert metadata["pi"]["action"] == "implement"
    assert metadata["pi"]["approved"] is False
    validation = agnt.validate_orchestration_metadata(metadata, bead={"acceptance_criteria": "approval required"})
    assert validation["status"] == "needs-human"


def test_work_maintenance_cli_due_and_create_beads_json(agnt, tmp_path, capsys):
    report = {
        "schemaVersion": 1,
        "due": [{"mode": "context-health", "label": "maintenance:context-health", "reason": "warnings"}],
        "suppressed": [],
        "signals": {"contextWarnings": 2},
    }
    created = {"schemaVersion": 1, "dryRun": True, "beads": [{"title": "Maintenance: context-health"}], "commands": []}

    with patch.dict(agnt.cmd_work.__globals__, {
        "maintenance_due_report": lambda **_kwargs: report,
        "maintenance_create_beads": lambda report, dry_run, **_kwargs: created,
    }):
        assert agnt.cmd_work(["maintenance", "due", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["due"][0]["mode"] == "context-health"
        assert agnt.cmd_work(["maintenance", "create-beads", "--dry-run", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["beads"][0]["title"] == "Maintenance: context-health"


def test_runner_tick_surfaces_due_maintenance_before_idle(agnt, tmp_path):
    def fake_beads(args):
        assert args == ["ready"]
        return 0, [], ""

    report = {
        "schemaVersion": 1,
        "due": [{"mode": "workflow-retro", "label": "maintenance:workflow-retro", "reason": "closed work"}],
        "suppressed": [],
        "signals": {"closedImplementationBeads": 3},
    }
    created = {"schemaVersion": 1, "dryRun": True, "beads": [{"title": "Maintenance: workflow-retro"}]}

    result = agnt.runner_tick(
        root=tmp_path,
        dry_run=True,
        beads_runner=fake_beads,
        maintenance_due_provider=lambda **_kwargs: report,
        maintenance_creator=lambda due_report, dry_run, **_kwargs: created,
    )

    assert result["actions"][0]["action"] == "would_create_maintenance"
    assert result["actions"][0]["maintenance"]["beads"][0]["title"] == "Maintenance: workflow-retro"
