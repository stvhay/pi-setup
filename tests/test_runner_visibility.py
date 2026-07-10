from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib import gateway


def service_status_payload(root: Path) -> dict:
    return {
        "schemaVersion": 1,
        "apiVersion": 1,
        "status": "draining",
        "running": True,
        "paused": False,
        "draining": True,
        "acceptingNewWork": False,
        "schedulerEnabled": True,
        "schedulerAlive": False,
        "scheduler": {"lastTickCompletedAt": "2026-07-09T16:00:01Z", "lastTickOutcome": "completed"},
        "root": str(root),
        "heartbeatAt": "2026-07-09T16:00:00Z",
        "updatedAt": "2026-07-09T16:00:01Z",
        "leases": {
            "pi-session": {
                "leaseId": "pi-session",
                "client": "pi-tui",
                "expiresAt": "2026-07-09T16:05:00Z",
            }
        },
        "activeRuns": [
            {
                "bead": "pi-2m1.7",
                "slug": "surface-runner-status",
                "epicId": "pi-2m1",
                "runId": "runner-service-task7",
                "status": "running",
                "model": "openai-codex/gpt-5.6-sol",
                "thinkingLevel": "high",
                "context": {"used": 50000, "limit": 200000, "percent": 25.0},
                "cost": {"usd": 1.23, "source": "metrics"},
                "bundle": ".pi/runs/runner-service-task7",
                "blockers": [],
                "writeSet": ["pi/agent/bin/agnt_lib/gateway.py"],
            }
        ],
        "budget": {"mode": "placeholder", "limitsEnforced": False, "remainingUsd": None},
        "service": {
            "schemaVersion": 1,
            "apiVersion": 1,
            "baseUrl": "http://127.0.0.1:12345",
            "tokenPath": str(root / ".pi" / "runner" / "token"),
            "token": "<redacted>",
            "secret": "<redacted>",
        },
        "lock": {"pid": 12345},
    }


def test_gateway_runner_status_uses_rest_client_and_stable_visibility_shape(tmp_path):
    payload = service_status_payload(tmp_path)

    with patch.dict(gateway._runner_status_gateway.__globals__, {"runner_client_status": lambda root=None: payload}):
        result = gateway.ticket_gateway({"operation": "runner_status", "root": str(tmp_path)})

    runner = result["runner"]
    assert result["operation"] == "runner_status"
    assert runner["service"]["state"] == "present"
    assert runner["status"] == "draining"
    assert runner["running"] is True
    assert runner["draining"] is True
    assert runner["acceptingNewWork"] is False
    assert runner["schedulerEnabled"] is True
    assert runner["schedulerAlive"] is False
    assert runner["scheduler"] == {"lastTickCompletedAt": "2026-07-09T16:00:01Z", "lastTickOutcome": "completed"}
    assert runner["heartbeatAt"] == "2026-07-09T16:00:00Z"
    assert runner["leaseCount"] == 1
    assert runner["activeCount"] == 1
    assert runner["activeRuns"] == [
        {
            "bead": "pi-2m1.7",
            "slug": "surface-runner-status",
            "epicId": "pi-2m1",
            "runId": "runner-service-task7",
            "status": "running",
            "model": "openai-codex/gpt-5.6-sol",
            "thinkingLevel": "high",
            "context": {"used": 50000, "limit": 200000, "percent": 25.0},
            "cost": {"usd": 1.23, "source": "metrics"},
            "bundle": ".pi/runs/runner-service-task7",
            "blockers": [],
        }
    ]
    assert runner["firstActive"] == runner["activeRuns"][0]
    assert runner["budget"] == {"mode": "placeholder", "limitsEnforced": False, "remainingUsd": None}
    assert runner["service"]["metadata"]["token"] == "<redacted>"
    assert runner["service"]["metadata"]["secret"] == "<redacted>"
    assert "secret-token" not in json.dumps(runner)
    assert "writeSet" not in json.dumps(runner)


def test_gateway_runner_status_reports_absent_service_without_legacy_idle_shape(tmp_path):
    from agnt_lib.runner_client import RunnerClientError

    missing = {"schemaVersion": 1, "status": "not-running", "running": False, "connected": False, "suggestedAction": "agnt work daemon start --json"}
    with patch.dict(
        gateway._runner_status_gateway.__globals__,
        {"runner_client_status": lambda root=None: (_ for _ in ()).throw(RunnerClientError("missing", payload=missing))},
    ):
        result = gateway.ticket_gateway({"operation": "runner_status", "root": str(tmp_path)})

    runner = result["runner"]
    assert runner["service"]["state"] == "absent"
    assert runner["status"] == "not-running"
    assert runner["running"] is False
    assert runner["activeRuns"] == []
    assert runner["activeCount"] == 0
    assert runner["leaseCount"] == 0
    assert runner["suggestedAction"] == "agnt work daemon start --json"


def test_ticket_gateway_extension_summarizes_runner_status_without_dumping_json():
    text = Path("pi/agent/extensions/ticket-gateway.ts").read_text(encoding="utf-8")

    assert "summarizeRunnerStatus" in text
    assert "activeCount" in text
    assert "firstActive" in text
    assert "slice(0, 80)" in text or "slice(0, 60)" in text
    assert "JSON.stringify(result, null, 2).split" not in text


def test_orchestrator_extension_widget_mentions_model_context_and_cost():
    text = Path("pi/agent/extensions/orchestrator-service.ts").read_text(encoding="utf-8")

    assert "formatActiveRun" in text
    assert "thinkingLevel" in text
    assert "context" in text and "percent" in text
    assert "cost" in text and "usd" in text
    assert "firstActive" in text
    assert "ticket_gateway" in text
