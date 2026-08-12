from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "pi/agent/evals/thinking-level-calibration"
MODULE_PATH = EVAL_DIR / "evaluate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("thinking_level_calibration", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest() -> dict:
    return json.loads((EVAL_DIR / "manifest.json").read_text(encoding="utf-8"))


def record(case_id: str, thinking: str, response: dict, **overrides) -> dict:
    value = {
        "caseId": case_id,
        "target": "openai-codex/gpt-5.6-sol",
        "thinking": thinking,
        "effectiveThinking": thinking,
        "providerRequests": 1,
        "durationMs": 1_000,
        "outputTokens": 100,
        "toolErrors": 0,
        "exitCode": 0,
        "response": json.dumps(response),
    }
    value.update(overrides)
    return value


def response(case: dict, *, result: str | None = None, findings: list[str] | None = None) -> dict:
    return {
        "schemaVersion": 1,
        "caseId": case["id"],
        "result": result if result is not None else case["expectedResult"],
        "findings": findings if findings is not None else case["expectedFindings"],
        "completed": True,
    }


def test_real_manifest_and_packets_validate():
    module = load_module()
    spec = module.validate_manifest(manifest())

    assert [case["id"] for case in spec["cases"]] == [
        "mechanical-inventory",
        "documentation",
        "formatting",
        "architecture",
        "implementation",
        "security",
        "final-verification",
    ]


def test_manifest_rejects_partial_calibration_suite():
    module = load_module()
    spec = manifest()
    spec["cases"] = spec["cases"][:-1]

    with pytest.raises(ValueError, match="exact seven-case suite"):
        module.validate_manifest(spec)


def test_visible_task_payload_is_identical_across_thinking_levels():
    module = load_module()
    case = manifest()["cases"][0]

    assert module.task_text(case, "low") == module.task_text(case, "xhigh")


def test_collect_correlates_identical_payloads_by_child_order(tmp_path):
    module = load_module()
    spec = manifest()
    case = spec["cases"][0]
    prompt = module.task_text(case, "low")
    tasks = [
        {
            "task": prompt,
            "model": spec["model"],
            "mode": "one-shot",
            "thinking": level,
            "limits": {"maxProviderRequests": 1, "maxDurationMs": 180_000},
            "outputContract": "inline",
        }
        for level in ("low", "xhigh")
    ]
    results = [
        {
            "task": prompt,
            "usage": {"turns": 1, "output": 10},
            "progressSummary": {"durationMs": 100},
            "execution": {"profile": {"thinking": effective}},
            "exitCode": 0,
            "finalOutput": json.dumps(response(case)),
        }
        for effective in ("xhigh", "low")
    ]
    session = tmp_path / "session.jsonl"
    session.write_text(
        "\n".join([
            json.dumps({"message": {"role": "assistant", "content": [{
                "type": "toolCall",
                "name": "subagent",
                "id": "call-1",
                "arguments": {"tasks": tasks},
            }]}}),
            json.dumps({"message": {
                "role": "toolResult",
                "toolName": "subagent",
                "toolCallId": "call-1",
                "details": {"results": results},
            }}),
        ]),
        encoding="utf-8",
    )

    records = module.collect_records(session, spec)

    assert [(item["thinking"], item["effectiveThinking"]) for item in records] == [
        ("low", "xhigh"),
        ("xhigh", "low"),
    ]


def test_score_reports_metrics_separately_and_exact_quality():
    module = load_module()
    spec = manifest()
    runs = [
        record(case["id"], level, response(case))
        for case in spec["cases"]
        for level in spec["thinkingLevels"]
    ]

    summary = module.score_records(runs, spec)
    low = summary["levels"]["low"]

    assert low["completionQuality"] == 1.0
    assert low["latencyMs"] == {"median": 1_000, "total": 7_000}
    assert low["outputTokens"] == 700
    assert low["toolErrors"] == 0
    assert low["reviewFindings"] == {"confirmed": 3, "reported": 3}
    assert low["validCompletions"] == 7
    assert summary["defaultChangeEligible"] is False


def test_default_change_gate_requires_measured_latency_reduction():
    module = load_module()
    spec = manifest()
    runs = [
        record(
            case["id"],
            level,
            response(case),
            durationMs=(
                800
                if case["proposedLevel"] in {"low", "medium"}
                and level == case["proposedLevel"]
                else 1_000
            ),
        )
        for case in spec["cases"]
        for level in spec["thinkingLevels"]
    ]

    summary = module.score_records(runs, spec)

    assert summary["defaultChangeEligible"] is True
    assert summary["defaultChangeGate"] == {
        "qualityParity": True,
        "candidateLatencyMs": 2_400.0,
        "baselineLatencyMs": 3_000.0,
        "observedLatencyRatio": 0.8,
        "requiredLatencyRatio": 0.9,
    }


def test_score_accepts_harness_thinking_prefix_before_json():
    module = load_module()
    spec = manifest()
    runs = []
    for case in spec["cases"]:
        for level in spec["thinkingLevels"]:
            raw = record(case["id"], level, response(case))
            raw["response"] = "[thinking] worker summary\n\n" + raw["response"]
            runs.append(raw)

    summary = module.score_records(runs, spec)

    assert summary["levels"]["low"]["completionQuality"] == 1.0


def test_score_rejects_missing_matrix_cell():
    module = load_module()
    spec = manifest()
    case = spec["cases"][0]
    runs = [record(case["id"], "low", response(case))]

    with pytest.raises(ValueError, match="complete case/thinking matrix"):
        module.score_records(runs, spec)


def test_lower_level_gate_requires_per_case_xhigh_parity():
    module = load_module()
    spec = manifest()
    runs = []
    for case in spec["cases"]:
        for level in spec["thinkingLevels"]:
            result = response(case)
            if case["id"] == "documentation" and level == "medium":
                result = response(case, result="wrong")
            runs.append(record(case["id"], level, result))

    summary = module.score_records(runs, spec)

    assert summary["lowerLevelEligibility"]["mechanical-inventory"]["eligible"] is True
    assert summary["lowerLevelEligibility"]["formatting"]["eligible"] is True
    assert summary["lowerLevelEligibility"]["documentation"] == {
        "candidate": "medium",
        "baseline": "xhigh",
        "candidateQuality": 0.0,
        "baselineQuality": 1.0,
        "eligible": False,
    }
    assert summary["defaultChangeEligible"] is False


def test_invalid_execution_counts_separately_from_completion_quality():
    module = load_module()
    spec = manifest()
    runs = []
    for case in spec["cases"]:
        for level in spec["thinkingLevels"]:
            overrides = {"toolErrors": 1, "exitCode": 1} if case["id"] == "security" and level == "low" else {}
            runs.append(record(case["id"], level, response(case), **overrides))

    summary = module.score_records(runs, spec)

    assert summary["levels"]["low"]["toolErrors"] == 1
    assert summary["levels"]["low"]["validCompletions"] == 6
    assert summary["levels"]["low"]["completionQuality"] == pytest.approx(6 / 7)
