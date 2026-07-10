from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib import runner_protocol as rp
from agnt_lib.runner import save_runner_state
from agnt_lib.runner_scheduler import runner_scheduler_tick

VALID_REVIEW_META = {
    "pi": {
        "action": "review",
        "routingTask": "review",
        "allowedEffects": ["read_workspace", "write_artifacts"],
        "modelPolicy": {"mode": "auto"},
        "sessionPolicy": "recorded",
        "memoryPolicy": "auto",
    }
}


def _ready(*items: dict):
    def fake_beads(args):
        if args == ["ready"]:
            return 0, list(items), ""
        raise AssertionError(args)

    return fake_beads


def _review_bead(bead_id: str) -> dict:
    return {"id": bead_id, "title": f"Review {bead_id}", "issue_type": "task", "status": "open", "metadata": json.dumps(VALID_REVIEW_META)}


def _write_run_bundle(bundle: Path, *, selected_model: str = "openai-codex/gpt-5.6-sol", thinking_level: str = "high", cost: float | None = 0.42, tokens: int | None = 12345) -> None:
    artifacts = bundle / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (bundle / "invocation.yaml").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "id": bundle.name,
                "selectedModel": selected_model,
                "thinkingLevel": thinking_level,
                "modelSelection": {"selected": selected_model, "thinkingLevel": thinking_level},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metrics_ref = None
    if cost is not None or tokens is not None:
        metrics_ref = "artifacts/model.metrics.json"
        (bundle / metrics_ref).write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "target": selected_model,
                    "thinkingLevel": thinking_level,
                    "usageSource": "test-metrics",
                    "usage": {
                        "totalTokens": tokens,
                        "cost": {"total": cost},
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
    (bundle / "result.yaml").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "status": "succeeded",
                "metricsRef": metrics_ref,
                "completedAt": "2026-07-09T12:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_budget_normalization_reports_unknown_usage_without_enforcement():
    budget = rp.normalize_budget_state({})

    assert budget["mode"] == "placeholder"
    assert budget["limitsEnforced"] is False
    assert budget["spentUsd"] is None
    assert budget["remainingUsd"] is None
    assert budget["cost"] == {"usd": None, "source": "unknown"}
    assert budget["context"] == {"used": None, "limit": None, "percent": None, "source": "unknown"}
    assert "cost-unknown" in budget["warnings"]
    assert "context-unknown" in budget["warnings"]


def test_budget_normalization_computes_configured_remaining_limit():
    budget = rp.normalize_budget_state({"limitsEnforced": True, "maxSessionUsd": 2.5, "maxRunUsd": 0.75, "spentUsd": 1.25})

    assert budget["mode"] == "configured"
    assert budget["limitsEnforced"] is True
    assert budget["maxSessionUsd"] == 2.5
    assert budget["maxRunUsd"] == 0.75
    assert budget["spentUsd"] == 1.25
    assert budget["remainingUsd"] == 1.25
    assert "budget-exhausted" not in budget["warnings"]


def test_scheduler_blocks_new_dispatch_and_pauses_when_enforced_budget_exhausted(tmp_path):
    save_runner_state(tmp_path, {"budget": {"limitsEnforced": True, "maxSessionUsd": 1.0, "spentUsd": 1.0}})
    started = []
    blockers = []

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-budget.1")),
        runner_start=lambda bead, **kwargs: started.append(bead),
        blocker_creator=lambda **kwargs: blockers.append(kwargs) or {"decisionBead": "pi-budget-blocker.1"},
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        now=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
    )

    assert started == []
    assert result["actions"][0]["action"] == "blocked_budget"
    assert result["actions"][0]["budget"]["remainingUsd"] == 0.0
    assert blockers[0]["target_bead"] == "pi-budget.1"
    assert "budget" in blockers[0]["question"].lower()
    state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
    assert state["paused"] is True
    assert state["acceptingNewWork"] is False
    assert state["pauseReason"] == "budget-exhausted"
    assert state["budget"]["blockedReason"] == "budget-exhausted"


def test_scheduler_surfaces_cost_context_from_run_metrics_without_model_override(tmp_path):
    save_runner_state(tmp_path, {"budget": {"limitsEnforced": True, "maxSessionUsd": 10.0, "spentUsd": 0.0}})
    seen_kwargs = []

    def fake_start(bead, **kwargs):
        seen_kwargs.append(kwargs)
        bundle = tmp_path / ".pi" / "runs" / kwargs["id_value"]
        _write_run_bundle(bundle, selected_model="openai-codex/gpt-5.6-sol", thinking_level="high", cost=0.42, tokens=12345)
        return {"started": {"bundle": str(bundle), "dispatch": {"bead": bead["id"]}}, "invoked": {"result": {"status": "succeeded"}}}

    result = runner_scheduler_tick(
        root=tmp_path,
        dry_run=False,
        limit=1,
        beads_runner=_ready(_review_bead("pi-budget.2")),
        runner_start=fake_start,
        maintenance_due_provider=lambda **_kwargs: {"due": False},
        now=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
    )

    assert seen_kwargs[0]["model"] is None
    resources = result["actions"][0]["resources"]
    assert resources["model"] == "openai-codex/gpt-5.6-sol"
    assert resources["thinkingLevel"] == "high"
    assert resources["cost"] == {"usd": 0.42, "source": "metrics"}
    assert resources["context"] == {"used": 12345, "limit": None, "percent": None, "source": "metrics"}
    state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
    assert state["budget"]["spentUsd"] == 0.42
    assert state["budget"]["remainingUsd"] == 9.58
    assert state["budget"]["lastRun"]["runId"].startswith("runner-pi-budget.2-")
    assert state["budget"]["lastRun"]["cost"] == {"usd": 0.42, "source": "metrics"}
