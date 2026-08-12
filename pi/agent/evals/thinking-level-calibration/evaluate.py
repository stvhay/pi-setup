#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "manifest.json"
EXPECTED_CASE_IDS = [
    "mechanical-inventory",
    "documentation",
    "formatting",
    "architecture",
    "implementation",
    "security",
    "final-verification",
]
sys.path.insert(0, str(HERE.parents[1] / "bin"))
from agnt_lib.routing import task_thinking_level  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def validate_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("schemaVersion") != 1 or spec.get("id") != "thinking-level-calibration":
        raise ValueError("manifest identity must be thinking-level-calibration schemaVersion 1")
    if spec.get("thinkingLevels") != ["low", "medium", "high", "xhigh"]:
        raise ValueError("thinking levels must be low, medium, high, xhigh")
    execution = spec.get("execution")
    if execution != {
        "mode": "one-shot",
        "maxProviderRequests": 1,
        "maxDurationMs": 180_000,
        "outputContract": "inline",
    }:
        raise ValueError("execution contract changed")
    thresholds = spec.get("thresholds")
    if thresholds != {"minLatencyReductionFraction": 0.1}:
        raise ValueError("latency threshold changed")
    cases = spec.get("cases")
    if not isinstance(cases, list) or [case.get("id") for case in cases if isinstance(case, dict)] != EXPECTED_CASE_IDS:
        raise ValueError("manifest requires exact seven-case suite")
    ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] in ids:
            raise ValueError("case IDs must be unique strings")
        ids.add(case["id"])
        features = case.get("features")
        if not isinstance(features, dict) or set(features) != {
            "phase", "effect_severity", "ambiguity", "novelty", "reversibility", "testability", "source_breadth"
        }:
            raise ValueError(f"incomplete features: {case['id']}")
        if task_thinking_level(**features) != case.get("proposedLevel"):
            raise ValueError(f"rubric mismatch: {case['id']}")
        prompt = HERE / str(case.get("prompt") or "")
        if not prompt.is_file() or case["id"] not in prompt.read_text(encoding="utf-8"):
            raise ValueError(f"missing or mismatched prompt: {case['id']}")
        if not isinstance(case.get("expectedResult"), str) or not isinstance(case.get("expectedFindings"), list):
            raise ValueError(f"incomplete expected result: {case['id']}")
    return spec


def task_text(case: dict[str, Any], _level: str) -> str:
    return (HERE / case["prompt"]).read_text(encoding="utf-8").strip()


def session_messages(path: Path) -> list[dict[str, Any]]:
    messages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        message = entry.get("message") if isinstance(entry, dict) else None
        if isinstance(message, dict):
            messages.append(message)
    return messages


def collect_records(session_path: Path, spec: dict[str, Any]) -> list[dict[str, Any]]:
    validate_manifest(spec)
    cases = {case["id"]: case for case in spec["cases"]}
    payload_cases = {task_text(case, "low"): case["id"] for case in spec["cases"]}
    calls: dict[str, list[tuple[int, dict[str, Any], str]]] = {}
    results: dict[str, list[Any]] = {}
    for message in session_messages(session_path):
        if message.get("role") == "assistant":
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "toolCall" or block.get("name") != "subagent":
                    continue
                arguments = block.get("arguments") if isinstance(block.get("arguments"), dict) else {}
                selected = []
                for child_index, task in enumerate(arguments.get("tasks") or []):
                    if not isinstance(task, dict):
                        continue
                    case_id = payload_cases.get(str(task.get("task") or ""))
                    if case_id and task.get("thinking") in spec["thinkingLevels"]:
                        selected.append((child_index, task, case_id))
                if selected:
                    calls[str(block.get("id"))] = selected
        elif message.get("role") == "toolResult" and message.get("toolName") == "subagent":
            details = message.get("details") if isinstance(message.get("details"), dict) else {}
            child_results = details.get("results")
            results[str(message.get("toolCallId"))] = child_results if isinstance(child_results, list) else []

    records = []
    for call_id, tasks in calls.items():
        child_results = results.get(call_id, [])
        for child_index, task, case_id in tasks:
            candidate = child_results[child_index] if child_index < len(child_results) else None
            result = candidate if isinstance(candidate, dict) else {}
            usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
            progress = result.get("progressSummary") if isinstance(result.get("progressSummary"), dict) else {}
            execution = result.get("execution") if isinstance(result.get("execution"), dict) else {}
            profile = execution.get("profile") if isinstance(execution.get("profile"), dict) else {}
            level = task.get("thinking")
            records.append({
                "caseId": case_id,
                "target": task.get("model"),
                "thinking": level,
                "effectiveThinking": profile.get("thinking"),
                "providerRequests": usage.get("turns"),
                "durationMs": progress.get("durationMs"),
                "outputTokens": usage.get("output"),
                "toolErrors": progress.get("toolErrors", 0),
                "exitCode": result.get("exitCode"),
                "response": result.get("finalOutput", ""),
                "taskPayloadValid": (
                    task["task"] == task_text(cases[case_id], str(level))
                    and result.get("task") == task["task"]
                ),
            })
    return sorted(records, key=lambda item: (item["caseId"], item["thinking"]))


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and not text[index + end:].strip():
            return value
    return {}


def parse_completion(record: dict[str, Any], case: dict[str, Any], execution: dict[str, Any]) -> tuple[bool, int, int]:
    valid_execution = (
        record.get("target") == "openai-codex/gpt-5.6-sol"
        and record.get("thinking") == record.get("effectiveThinking")
        and record.get("providerRequests") == execution["maxProviderRequests"]
        and isinstance(record.get("durationMs"), (int, float))
        and 0 < record["durationMs"] <= execution["maxDurationMs"]
        and isinstance(record.get("outputTokens"), int)
        and record["outputTokens"] >= 0
        and record.get("toolErrors") == 0
        and record.get("exitCode") == 0
        and record.get("taskPayloadValid", True)
    )
    value = extract_json_object(str(record.get("response") or ""))
    findings = value.get("findings") if isinstance(value, dict) and isinstance(value.get("findings"), list) else []
    expected = case["expectedFindings"]
    confirmed = len(set(findings) & set(expected))
    valid_output = value == {
        "schemaVersion": 1,
        "caseId": case["id"],
        "result": case["expectedResult"],
        "findings": expected,
        "completed": True,
    }
    return valid_execution and valid_output, len(findings), confirmed


def score_records(records: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(spec)
    cases = {case["id"]: case for case in spec["cases"]}
    levels = spec["thinkingLevels"]
    keyed: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("caseId")), str(record.get("thinking")))
        if key in keyed or key[0] not in cases or key[1] not in levels:
            raise ValueError("records contain duplicate or unknown case/thinking cell")
        keyed[key] = record
    expected = {(case_id, level) for case_id in cases for level in levels}
    if set(keyed) != expected:
        raise ValueError("records must contain complete case/thinking matrix")

    outcomes: dict[tuple[str, str], bool] = {}
    level_summaries = {}
    for level in levels:
        durations = []
        output_tokens = tool_errors = reported = confirmed = valid = 0
        for case_id, case in cases.items():
            record = keyed[(case_id, level)]
            quality, finding_count, confirmed_count = parse_completion(record, case, spec["execution"])
            outcomes[(case_id, level)] = quality
            valid += int(quality)
            durations.append(float(record["durationMs"]))
            output_tokens += int(record["outputTokens"])
            tool_errors += int(record["toolErrors"])
            reported += finding_count
            confirmed += confirmed_count
        level_summaries[level] = {
            "completionQuality": valid / len(cases),
            "validCompletions": valid,
            "latencyMs": {"median": statistics.median(durations), "total": sum(durations)},
            "outputTokens": output_tokens,
            "toolErrors": tool_errors,
            "reviewFindings": {"confirmed": confirmed, "reported": reported},
        }

    eligibility = {}
    candidate_latency = baseline_latency = 0.0
    for case_id, case in cases.items():
        candidate = case["proposedLevel"]
        if candidate not in {"low", "medium"}:
            continue
        candidate_quality = float(outcomes[(case_id, candidate)])
        baseline_quality = float(outcomes[(case_id, "xhigh")])
        eligibility[case_id] = {
            "candidate": candidate,
            "baseline": "xhigh",
            "candidateQuality": candidate_quality,
            "baselineQuality": baseline_quality,
            "eligible": candidate_quality == baseline_quality == 1.0,
        }
        candidate_latency += float(keyed[(case_id, candidate)]["durationMs"])
        baseline_latency += float(keyed[(case_id, "xhigh")]["durationMs"])
    quality_parity = bool(eligibility) and all(item["eligible"] for item in eligibility.values())
    required_ratio = 1.0 - float(spec["thresholds"]["minLatencyReductionFraction"])
    observed_ratio = candidate_latency / baseline_latency if baseline_latency else float("inf")
    default_gate = {
        "qualityParity": quality_parity,
        "candidateLatencyMs": candidate_latency,
        "baselineLatencyMs": baseline_latency,
        "observedLatencyRatio": observed_ratio,
        "requiredLatencyRatio": required_ratio,
    }
    return {
        "schemaVersion": 1,
        "id": spec["id"],
        "levels": level_summaries,
        "lowerLevelEligibility": eligibility,
        "defaultChangeGate": default_gate,
        "defaultChangeEligible": quality_parity and observed_ratio <= required_ratio,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    collect = sub.add_parser("collect")
    collect.add_argument("--session", type=Path, required=True)
    collect.add_argument("--output", type=Path, required=True)
    score = sub.add_parser("score")
    score.add_argument("--runs", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    spec = validate_manifest(read_json(DEFAULT_MANIFEST))
    if args.command == "validate":
        print(json.dumps({"id": spec["id"], "cases": len(spec["cases"]), "status": "valid"}, sort_keys=True))
    elif args.command == "collect":
        write_json(args.output, collect_records(args.session, spec))
    else:
        write_json(args.output, score_records(read_json(args.runs), spec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
