from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bundle(agnt, runs_dir: Path, run_id: str, *, bead: str = "pi-task.1") -> Path:
    return agnt.create_run_bundle(
        action="implement",
        routing_task="implementation",
        bead=bead,
        selected_model="ollama/gemma4:31b",
        runs_dir=runs_dir,
        id_value=run_id,
    )


def _ref_resolver(statuses: dict[str, str | None]):
    def resolve(ref: str) -> dict:
        status = statuses.get(ref)
        if status is None:
            return {"id": ref, "exists": False, "status": None, "error": "not found"}
        return {"id": ref, "exists": True, "status": status}

    return resolve


def _finding_ids(report: dict) -> set[str]:
    return {str(item["id"]) for item in report["findings"]}


def test_work_health_report_detects_closeout_blockers(agnt, tmp_path):
    bundle = _bundle(agnt, tmp_path, "closeout-blockers")
    result_path = bundle / "result.yaml"
    result = _read_json(result_path)
    result.update(
        {
            "status": "succeeded",
            "summary": "Worker used raw bash/bd bypass to close work.",
            "evidence": [],
            "approvalRefs": ["pi-approval.1"],
            "decisionRefs": ["pi-decision.1"],
            "healthChecks": [{"name": "pytest", "status": "failed"}],
            "closeoutChecks": [{"name": "followups", "status": "pending"}],
            "completedAt": "2026-07-09T01:00:00Z",
        }
    )
    _write_json(result_path, result)

    report = agnt.work_health_report(
        root=tmp_path,
        runs_dir=tmp_path,
        ref_resolver=_ref_resolver({"pi-task.1": "open", "pi-approval.1": "open", "pi-decision.1": "closed"}),
        status_runner=lambda _path: (0, "", ""),
    )

    assert report["passed"] is False
    assert report["summary"]["failureCount"] >= 5
    assert {
        "missing-verification-evidence",
        "unresolved-approval-ref",
        "failed-health-check",
        "failed-closeout-check",
        "raw-tool-bypass-marker",
    }.issubset(_finding_ids(report))


def test_work_health_report_detects_orphaned_stale_dirty_runs(agnt, tmp_path):
    old = datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc)
    worktree = tmp_path / "wt"
    worktree.mkdir()
    bundle = _bundle(agnt, tmp_path, "stale-dirty", bead="pi-missing.1")
    invocation_path = bundle / "invocation.yaml"
    invocation = _read_json(invocation_path)
    invocation["createdAt"] = old.isoformat().replace("+00:00", "Z")
    invocation["worktree"] = {"policy": "epic-worktree", "path": str(worktree), "status": "ready", "dispatchable": True}
    _write_json(invocation_path, invocation)
    result_path = bundle / "result.yaml"
    result = _read_json(result_path)
    result.update({"status": "needs-human", "sessionRef": "pi-session-id:old", "completedAt": None})
    _write_json(result_path, result)

    report = agnt.work_health_report(
        root=tmp_path,
        runs_dir=tmp_path,
        ref_resolver=_ref_resolver({}),
        status_runner=lambda _path: (0, " M changed.py\n", ""),
        now=old + timedelta(hours=3),
        stale_after_hours=1,
    )

    assert report["passed"] is False
    assert {"orphaned-run-bead", "stale-active-session", "dirty-worktree"}.issubset(_finding_ids(report))


def test_work_health_report_happy_path_passes(agnt, tmp_path):
    bundle = _bundle(agnt, tmp_path, "happy", bead="pi-task.1")
    result_path = bundle / "result.yaml"
    result = _read_json(result_path)
    result.update(
        {
            "status": "succeeded",
            "summary": "Verified safely.",
            "evidence": ["pytest tests/test_health.py -> PASS"],
            "approvalRefs": ["pi-approval.1"],
            "decisionRefs": ["pi-decision.1"],
            "healthChecks": [{"name": "pytest", "status": "passed"}],
            "closeoutChecks": [{"name": "followups", "status": "passed"}],
            "followUps": ["pi-followup.1"],
            "completedAt": "2026-07-09T01:00:00Z",
        }
    )
    _write_json(result_path, result)

    report = agnt.work_health_report(
        root=tmp_path,
        runs_dir=tmp_path,
        ref_resolver=_ref_resolver(
            {
                "pi-task.1": "closed",
                "pi-approval.1": "closed",
                "pi-decision.1": "closed",
                "pi-followup.1": "open",
            }
        ),
        status_runner=lambda _path: (0, "", ""),
    )

    assert report["passed"] is True
    assert report["findings"] == []
    assert report["summary"]["runCount"] == 1


def test_close_readiness_blocks_failed_checks_and_unresolved_approvals(agnt):
    result = {
        "status": "succeeded",
        "evidence": ["pytest -> PASS"],
        "followUps": ["pi-followup.1"],
        "approvalRefs": ["pi-approval.1"],
        "decisionRefs": ["pi-decision.1"],
        "healthChecks": [{"name": "pytest", "status": "failed"}],
        "closeoutChecks": [{"name": "human decision", "status": "pending"}],
    }

    failures = agnt.close_readiness_failures(
        result,
        followup_checker=lambda bead_id: (bead_id == "pi-followup.1", None),
        ref_checker=lambda ref: (ref == "pi-decision.1", "not closed"),
    )

    assert any("healthChecks" in item for item in failures)
    assert any("closeoutChecks" in item for item in failures)
    assert any("pi-approval.1" in item for item in failures)


def test_work_health_report_detects_stale_runner_runtime_state(agnt, tmp_path):
    old = datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc)
    runner_dir = tmp_path / ".pi" / "runner"
    active_dir = runner_dir / "active"
    active_dir.mkdir(parents=True)
    _write_json(
        runner_dir / "state.json",
        {
            "schemaVersion": 1,
            "running": True,
            "heartbeatAt": old.isoformat().replace("+00:00", "Z"),
            "activeRuns": [{"bead": "pi-task.1", "runId": "run-old", "status": "running"}],
        },
    )
    _write_json(
        active_dir / "run-old.json",
        {
            "schemaVersion": 1,
            "bead": "pi-task.1",
            "runId": "run-old",
            "status": "running",
            "startedAt": old.isoformat().replace("+00:00", "Z"),
        },
    )

    report = agnt.work_health_report(
        root=tmp_path,
        runs_dir=tmp_path / "runs",
        ref_resolver=_ref_resolver({"pi-task.1": "open"}),
        status_runner=lambda _path: (0, "", ""),
        now=old + timedelta(hours=2),
        stale_after_hours=1,
        include_beads=False,
    )

    assert report["passed"] is False
    assert {"stale-runner-heartbeat", "stale-active-run-snapshot"}.issubset(_finding_ids(report))


def test_work_health_cli_json_returns_nonzero_for_failures(agnt, tmp_path, capsys):
    report = {
        "schemaVersion": 1,
        "passed": False,
        "summary": {"failureCount": 1, "warningCount": 0, "infoCount": 0},
        "findings": [{"id": "missing-verification-evidence", "severity": "failure", "message": "missing evidence"}],
    }

    with patch.dict(agnt.cmd_work.__globals__, {"work_health_report": lambda **_kwargs: report}):
        rc = agnt.cmd_work(["health", "--json", "--runs-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert rc == 1
    assert json.loads(captured.out)["findings"][0]["id"] == "missing-verification-evidence"


def test_check_pi_config_runs_work_health():
    script = Path("scripts/check-pi-config.sh").read_text(encoding="utf-8")

    assert "work health --json" in script
