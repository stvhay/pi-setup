#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "manifest.json"
TASK_RE = re.compile(r"^([a-z0-9:-]+) packet=([a-z0-9-]+) repetition=([1-9][0-9]*)$")
FINDING_FIELDS = ("id", "severity", "category", "location", "claim", "failureScenario", "evidence", "status")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def validate_manifest(spec: dict[str, Any], base_dir: Path = HERE) -> dict[str, Any]:
    if spec.get("schemaVersion") != 1 or spec.get("id") != "review-routing-calibration":
        raise ValueError("manifest identity must be review-routing-calibration schemaVersion 1")
    if not isinstance(spec.get("taskPrefix"), str) or not re.fullmatch(r"review-calibration:v[1-9][0-9]*", spec["taskPrefix"]):
        raise ValueError("manifest requires a versioned review-calibration task prefix")
    models = spec.get("models")
    if not isinstance(models, list) or len(models) != 2:
        raise ValueError("manifest requires exactly two models")
    targets = [model.get("target") for model in models if isinstance(model, dict)]
    if len(set(targets)) != 2 or {model.get("role") for model in models} != {"incumbent", "candidate"}:
        raise ValueError("models require unique targets and incumbent/candidate roles")

    execution = spec.get("execution")
    expected_execution = {
        "mode": "one-shot",
        "thinking": "high",
        "maxProviderRequests": 1,
        "maxDurationMs": 180_000,
        "maxFindings": 2,
        "maxResponseChars": 6_000,
        "repetitions": 3,
        "outputContract": "inline",
        "tokenOrCostLimits": False,
    }
    if not isinstance(execution, dict) or any(execution.get(key) != value for key, value in expected_execution.items()):
        raise ValueError("execution bounds do not match the approved paired protocol")

    packets = spec.get("packets")
    if not isinstance(packets, list) or len(packets) != 4:
        raise ValueError("manifest requires two seeded packets and two clean controls")
    by_id: dict[str, dict[str, Any]] = {}
    for packet in packets:
        if not isinstance(packet, dict) or not isinstance(packet.get("id"), str) or packet["id"] in by_id:
            raise ValueError("packet IDs must be unique strings")
        if packet.get("kind") not in {"seeded", "clean"} or packet.get("scope") not in {"behavioral", "boundary"}:
            raise ValueError(f"invalid packet kind/scope: {packet.get('id')}")
        anchors = packet.get("anchors")
        expected = packet.get("expectedFindings")
        if not isinstance(anchors, list) or len(anchors) != len(set(anchors)) or not all(isinstance(item, str) for item in anchors):
            raise ValueError(f"invalid anchors: {packet['id']}")
        if not isinstance(expected, dict) or not set(expected).issubset(anchors):
            raise ValueError(f"invalid expected findings: {packet['id']}")
        for finding_id, rubric in expected.items():
            alternatives = rubric.get("semanticAlternatives") if isinstance(rubric, dict) else None
            if (not isinstance(alternatives, list) or len(alternatives) < 2
                    or any(not isinstance(terms, list) or not terms
                           or not all(isinstance(term, str) and term for term in terms)
                           for terms in alternatives)):
                raise ValueError(f"invalid semantic rubric: {packet['id']}:{finding_id}")
        if packet["kind"] == "clean" and expected:
            raise ValueError(f"clean packet has expected findings: {packet['id']}")
        prompt_path = base_dir / str(packet.get("prompt") or "")
        if not prompt_path.is_file():
            raise ValueError(f"missing packet prompt: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8")
        for anchor in anchors:
            if f"ANCHOR {anchor}" not in prompt:
                raise ValueError(f"packet {packet['id']} does not contain anchor {anchor}")
        if f'"reviewId": "{packet["id"]}"' not in prompt:
            raise ValueError(f"packet {packet['id']} does not constrain reviewId")
        by_id[packet["id"]] = packet
    for packet in packets:
        paired_id = packet.get("control") if packet["kind"] == "seeded" else packet.get("controlFor")
        paired = by_id.get(str(paired_id))
        if not paired or paired["scope"] != packet["scope"] or paired["kind"] == packet["kind"]:
            raise ValueError(f"packet {packet['id']} has invalid seeded/control pairing")

    thresholds = spec.get("thresholds")
    required_thresholds = {
        "minRecall",
        "minPrecision",
        "maxCleanRunFalsePositiveRate",
        "maxTimeoutRate",
        "minValidOutputRate",
        "maxRecallDeficit",
        "minLatencyAdjustedYieldRatio",
    }
    if not isinstance(thresholds, dict) or set(thresholds) != required_thresholds:
        raise ValueError("manifest thresholds are incomplete")
    if any(not isinstance(value, (int, float)) or value < 0 for value in thresholds.values()):
        raise ValueError("manifest thresholds must be non-negative numbers")
    return spec


def parse_task_header(task: Any, prefix: str) -> tuple[str, int] | None:
    if not isinstance(task, str):
        return None
    first_line = task.splitlines()[0] if task.splitlines() else ""
    match = TASK_RE.fullmatch(first_line)
    return (match.group(2), int(match.group(3))) if match and match.group(1) == prefix else None


def expected_task_text(spec: dict[str, Any], packet_id: str, repetition: int) -> str | None:
    packet = next((item for item in spec["packets"] if item["id"] == packet_id), None)
    if packet is None:
        return None
    prompt = (HERE / packet["prompt"]).read_text(encoding="utf-8").strip()
    return f"{spec['taskPrefix']} packet={packet_id} repetition={repetition}\n\n{prompt}"


def session_messages(path: Path) -> list[dict[str, Any]]:
    messages = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid session JSON at line {line_number}: {error}") from error
        message = entry.get("message") if isinstance(entry, dict) else None
        if isinstance(message, dict):
            messages.append(message)
    return messages


def valid_duration(value: Any, max_duration_ms: int) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 < value <= max_duration_ms
    )


def dimension_errors(task: dict[str, Any], result: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    execution = spec["execution"]
    errors = []
    target = task.get("model")
    allowed_targets = {model["target"] for model in spec["models"]}
    if target not in allowed_targets:
        errors.append("target")
    if task.get("mode") != execution["mode"]:
        errors.append("mode")
    if task.get("thinking") != execution["thinking"]:
        errors.append("thinking")
    limits = task.get("limits") if isinstance(task.get("limits"), dict) else {}
    if limits.get("maxProviderRequests") != execution["maxProviderRequests"]:
        errors.append("maxProviderRequests")
    if limits.get("maxDurationMs") != execution["maxDurationMs"]:
        errors.append("maxDurationMs")
    if limits.get("maxTotalTokens") is not None or limits.get("maxCostUsd") is not None:
        errors.append("tokenOrCostLimit")
    if task.get("outputContract") != execution["outputContract"]:
        errors.append("outputContract")
    expected_provider, expected_model = target.split("/", 1) if isinstance(target, str) and "/" in target else (None, target)
    if result.get("provider") != expected_provider:
        errors.append("observedProvider")
    if result.get("model") not in {target, expected_model}:
        errors.append("observedModel")
    effective = result.get("execution") if isinstance(result.get("execution"), dict) else {}
    profile = effective.get("profile") if isinstance(effective.get("profile"), dict) else {}
    effective_limits = effective.get("limits") if isinstance(effective.get("limits"), dict) else {}
    if profile.get("mode") != execution["mode"]:
        errors.append("effectiveMode")
    if profile.get("thinking") != execution["thinking"]:
        errors.append("effectiveThinking")
    if effective_limits != {
        "maxProviderRequests": execution["maxProviderRequests"],
        "maxDurationMs": execution["maxDurationMs"],
    }:
        errors.append("effectiveLimits")
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    if usage.get("turns") != execution["maxProviderRequests"]:
        errors.append("providerRequests")
    progress = result.get("progressSummary") if isinstance(result.get("progressSummary"), dict) else {}
    if not valid_duration(progress.get("durationMs"), execution["maxDurationMs"]):
        errors.append("durationMs")
    return errors


def collect_records(session_path: Path, spec: dict[str, Any]) -> list[dict[str, Any]]:
    validate_manifest(spec, HERE)
    calls: dict[str, list[dict[str, Any]]] = {}
    results: dict[str, list[dict[str, Any]]] = {}
    for message in session_messages(session_path):
        if message.get("role") == "assistant":
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "toolCall" or block.get("name") != "subagent":
                    continue
                arguments = block.get("arguments") if isinstance(block.get("arguments"), dict) else {}
                tasks = arguments.get("tasks") if isinstance(arguments.get("tasks"), list) else []
                selected = [task for task in tasks if isinstance(task, dict)
                            and parse_task_header(task.get("task"), spec["taskPrefix"])]
                if selected:
                    calls[str(block.get("id"))] = selected
        elif message.get("role") == "toolResult" and message.get("toolName") == "subagent":
            details = message.get("details") if isinstance(message.get("details"), dict) else {}
            child_results = details.get("results") if isinstance(details.get("results"), list) else []
            results[str(message.get("toolCallId"))] = [item for item in child_results if isinstance(item, dict)]

    records = []
    for tool_call_id, tasks in calls.items():
        unmatched_results = list(results.get(tool_call_id, []))
        for index, task in enumerate(tasks):
            header = parse_task_header(task.get("task"), spec["taskPrefix"])
            if not header:
                continue
            packet_id, repetition = header
            target = task.get("model")
            expected_model = target.split("/", 1)[1] if isinstance(target, str) and "/" in target else target
            matches = [result for result in unmatched_results
                       if result.get("task") == task.get("task") and result.get("model") in {target, expected_model}]
            result = matches[0] if len(matches) == 1 else {}
            if result:
                unmatched_results.remove(result)
            errors = dimension_errors(task, result, spec)
            if task.get("task") != expected_task_text(spec, packet_id, repetition):
                errors.append("taskPayload")
            if len(matches) != 1:
                errors.append("resultCorrelation")
            progress = result.get("progressSummary") if isinstance(result.get("progressSummary"), dict) else {}
            usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
            termination = result.get("termination") if isinstance(result.get("termination"), dict) else {}
            response = result.get("finalOutput") if isinstance(result.get("finalOutput"), str) else ""
            limits = task.get("limits") if isinstance(task.get("limits"), dict) else {}
            effective = result.get("execution") if isinstance(result.get("execution"), dict) else {}
            profile = effective.get("profile") if isinstance(effective.get("profile"), dict) else {}
            effective_limits = effective.get("limits") if isinstance(effective.get("limits"), dict) else {}
            task_text = str(task.get("task") or "")
            records.append({
                "toolCallId": tool_call_id,
                "childIndex": index,
                "taskHash": hashlib.sha256(task_text.encode("utf-8")).hexdigest(),
                "packetId": packet_id,
                "repetition": repetition,
                "target": target,
                "requestedModel": target,
                "observedProvider": result.get("provider"),
                "observedModel": result.get("model"),
                "mode": task.get("mode"),
                "thinking": task.get("thinking"),
                "effectiveMode": profile.get("mode"),
                "effectiveThinking": profile.get("thinking"),
                "effectiveLimits": effective_limits,
                "maxProviderRequests": limits.get("maxProviderRequests"),
                "maxDurationMs": limits.get("maxDurationMs"),
                "hasTokenOrCostLimit": limits.get("maxTotalTokens") is not None or limits.get("maxCostUsd") is not None,
                "outputContract": task.get("outputContract"),
                "providerRequests": usage.get("turns"),
                "durationMs": progress.get("durationMs"),
                "exitCode": result.get("exitCode"),
                "terminationReason": termination.get("reason"),
                "response": response,
                "responseChars": len(response),
                "childSessionId": result.get("childSessionId"),
                "dimensionsValid": not errors,
                "dimensionErrors": sorted(set(errors)),
            })
    return sorted(records, key=lambda item: (item["packetId"], item["repetition"], str(item["target"])))


def extract_json_object(response: str) -> dict[str, Any] | None:
    text = response.strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        remainder = text[index + end:].strip()
        if isinstance(value, dict) and remainder in {"", "```"}:
            return value
    return None


def validate_output(response: str, packet: dict[str, Any], execution: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors = []
    if len(response) > execution["maxResponseChars"]:
        errors.append("responseChars")
    value = extract_json_object(response)
    if value is None:
        return [], [*errors, "json"]
    if value.get("schemaVersion") != 1:
        errors.append("schemaVersion")
    if value.get("reviewId") != packet["id"]:
        errors.append("reviewId")
    if value.get("scope") != packet["scope"]:
        errors.append("scope")
    reviewer = value.get("reviewer") if isinstance(value.get("reviewer"), dict) else {}
    if reviewer != {"target": "calibration-candidate", "family": "codex"}:
        errors.append("reviewer")
    findings = value.get("findings")
    if not isinstance(findings, list):
        return [], [*errors, "findings"]
    if len(findings) > execution["maxFindings"]:
        errors.append("maxFindings")
    valid_findings = []
    for finding in findings:
        if not isinstance(finding, dict) or any(not isinstance(finding.get(field), str) or not finding[field] for field in FINDING_FIELDS):
            errors.append("findingShape")
            continue
        if finding["severity"] not in {"critical", "important"} or finding["status"] != "unverified":
            errors.append("findingValues")
        valid_findings.append(finding)
    finding_ids = [finding["id"] for finding in valid_findings]
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("duplicateFindingId")
    return valid_findings, sorted(set(errors))


def verify_finding(finding: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    finding_id = finding["id"]
    rubric = packet["expectedFindings"].get(finding_id)
    searchable = " ".join(str(finding.get(field) or "") for field in
                          ("claim", "failureScenario", "evidence")).lower()
    alternatives = rubric.get("semanticAlternatives", []) if isinstance(rubric, dict) else []
    matched = next((terms for terms in alternatives
                    if all(term.lower() in searchable for term in terms)), None)
    confirmed = matched is not None
    return {
        "findingId": finding_id,
        "status": "confirmed" if confirmed else "refuted",
        "method": "private-semantic-rubric",
        "evidence": (
            "matched a private semantic alternative" if confirmed
            else "finding did not match a seeded private semantic rubric"
        ),
        "durationMs": (time.perf_counter() - started) * 1000,
    }


def paired_execution_valid(records: list[dict[str, Any]], spec: dict[str, Any]) -> bool:
    targets = {model["target"] for model in spec["models"]}
    expected_keys = {
        (packet["id"], repetition)
        for packet in spec["packets"]
        for repetition in range(1, spec["execution"]["repetitions"] + 1)
    }
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for record in records:
        key = (str(record.get("packetId")), int(record.get("repetition") or 0))
        groups.setdefault(key, []).append(record)
    if set(groups) != expected_keys or len(records) != len(expected_keys) * len(targets):
        return False
    for group in groups.values():
        if len(group) != len(targets) or {record.get("target") for record in group} != targets:
            return False
        if len({record.get("toolCallId") for record in group}) != 1:
            return False
        if len({record.get("taskHash") for record in group}) != 1:
            return False
        if not all(record.get("dimensionsValid") for record in group):
            return False
        if not all(valid_duration(record.get("durationMs"), spec["execution"]["maxDurationMs"]) for record in group):
            return False
    return True


def percentile(values: list[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)])


def score_records(records: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(spec, HERE)
    packets = {packet["id"]: packet for packet in spec["packets"]}
    execution = spec["execution"]
    repetitions = execution["repetitions"]
    expected_runs = len(packets) * repetitions
    model_results: dict[str, Any] = {}
    verification_records: list[dict[str, Any]] = []
    total_checks = 0
    pairing_valid = paired_execution_valid(records, spec)

    for model in spec["models"]:
        target = model["target"]
        actual = [record for record in records if record.get("target") == target]
        by_key: dict[tuple[str, int], dict[str, Any]] = {}
        duplicates = 0
        for record in actual:
            key = (str(record.get("packetId")), int(record.get("repetition") or 0))
            if key in by_key:
                duplicates += 1
            else:
                by_key[key] = record

        confirmed_unique = set()
        verified_hits = 0
        false_positives = 0
        clean_fp_runs = 0
        valid_outputs = 0
        invalid_outputs = 0
        invalid_dimensions = 0
        timeouts = 0
        durations = []
        expected_opportunities = 0
        verification_checks = 0

        for packet in spec["packets"]:
            expected_ids = set(packet["expectedFindings"])
            for repetition in range(1, repetitions + 1):
                expected_opportunities += len(expected_ids)
                record = by_key.get((packet["id"], repetition))
                if record is None:
                    invalid_outputs += 1
                    continue
                duration = record.get("durationMs")
                if isinstance(duration, (int, float)) and duration >= 0:
                    durations.append(int(duration))
                timeout = record.get("exitCode") == 124 or record.get("terminationReason") == "time-limit"
                if timeout:
                    timeouts += 1
                if not record.get("dimensionsValid"):
                    invalid_dimensions += 1
                findings, output_errors = validate_output(str(record.get("response") or ""), packet, execution)
                completed = record.get("exitCode") == 0 and record.get("terminationReason") == "completed"
                valid = bool(record.get("dimensionsValid")) and completed and not output_errors
                if not valid:
                    invalid_outputs += 1
                    continue
                valid_outputs += 1
                verification_checks += len(findings)
                total_checks += len(findings)
                run_has_false_positive = False
                for finding in findings:
                    verification = {
                        "target": target,
                        "packetId": packet["id"],
                        "repetition": repetition,
                        **verify_finding(finding, packet),
                    }
                    verification_records.append(verification)
                    if verification["status"] == "confirmed":
                        verified_hits += 1
                        confirmed_unique.add(f"{packet['id']}:{finding['id']}")
                    else:
                        false_positives += 1
                        run_has_false_positive = True
                if packet["kind"] == "clean" and run_has_false_positive:
                    clean_fp_runs += 1

        run_count = expected_runs
        missing_runs = max(0, expected_runs - len(by_key))
        recall = verified_hits / expected_opportunities if expected_opportunities else 1.0
        precision = verified_hits / (verified_hits + false_positives) if verified_hits + false_positives else 1.0
        clean_run_count = sum(1 for packet in spec["packets"] if packet["kind"] == "clean") * repetitions
        clean_fp_rate = clean_fp_runs / clean_run_count if clean_run_count else 0.0
        timeout_rate = timeouts / run_count if run_count else 0.0
        valid_output_rate = valid_outputs / run_count if run_count else 0.0
        total_duration_ms = sum(durations)
        yield_per_minute = verified_hits / (total_duration_ms / 60_000) if total_duration_ms > 0 else 0.0
        thresholds = spec["thresholds"]
        floor = (
            recall >= thresholds["minRecall"]
            and precision >= thresholds["minPrecision"]
            and clean_fp_rate <= thresholds["maxCleanRunFalsePositiveRate"]
            and timeout_rate <= thresholds["maxTimeoutRate"]
            and valid_output_rate >= thresholds["minValidOutputRate"]
        )
        model_results[target] = {
            "role": model["role"],
            "expectedRuns": run_count,
            "recordedRuns": len(by_key),
            "missingRuns": missing_runs,
            "duplicateRuns": duplicates,
            "validOutputs": valid_outputs,
            "invalidOutputs": invalid_outputs,
            "invalidDimensions": invalid_dimensions,
            "timeouts": timeouts,
            "timeoutRate": timeout_rate,
            "medianLatencyMs": statistics.median(durations) if durations else 0.0,
            "p95LatencyMs": percentile(durations, 0.95),
            "totalLatencyMs": total_duration_ms,
            "confirmedUniqueFindings": len(confirmed_unique),
            "confirmedFindingIds": sorted(confirmed_unique),
            "expectedFindingOpportunities": expected_opportunities,
            "verifiedFindingOpportunities": verified_hits,
            "falsePositives": false_positives,
            "cleanRunFalsePositiveRate": clean_fp_rate,
            "precision": precision,
            "recall": recall,
            "validOutputRate": valid_output_rate,
            "verificationChecks": verification_checks,
            "latencyAdjustedYieldPerMinute": yield_per_minute,
            "qualityFloorPassed": floor,
        }

    incumbent = next(model for model in spec["models"] if model["role"] == "incumbent")
    candidate = next(model for model in spec["models"] if model["role"] == "candidate")
    terra = model_results[incumbent["target"]]
    luna = model_results[candidate["target"]]
    thresholds = spec["thresholds"]
    failed_gates = []
    if not pairing_valid:
        failed_gates.append("pairedExecution")
    if not terra["qualityFloorPassed"]:
        failed_gates.append("incumbentQualityFloor")
    if not luna["qualityFloorPassed"]:
        failed_gates.append("candidateQualityFloor")
    if terra["recall"] - luna["recall"] > thresholds["maxRecallDeficit"]:
        failed_gates.append("recallDeficit")
    ratio = (
        luna["latencyAdjustedYieldPerMinute"] / terra["latencyAdjustedYieldPerMinute"]
        if terra["latencyAdjustedYieldPerMinute"] > 0 else 0.0
    )
    if ratio < thresholds["minLatencyAdjustedYieldRatio"]:
        failed_gates.append("latencyAdjustedYield")
    promote = not failed_gates
    verification_duration_ms = sum(record["durationMs"] for record in verification_records)
    return {
        "schemaVersion": 1,
        "evalId": spec["id"],
        "models": model_results,
        "pairedExecutionValid": pairing_valid,
        "verification": {
            "checks": total_checks,
            "durationMs": verification_duration_ms,
            "records": verification_records,
        },
        "decision": {
            "promoteLunaForBoundedReview": promote,
            "failedGates": failed_gates,
            "latencyAdjustedYieldRatio": ratio,
            "boundedReviewPrimary": candidate["target"] if promote else incumbent["target"],
            "highRiskRoutingChanged": False,
        },
    }


def load_manifest(path: Path) -> dict[str, Any]:
    spec = read_json(path)
    if not isinstance(spec, dict):
        raise ValueError("manifest must be a JSON object")
    return validate_manifest(spec, path.parent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect and score native subagent review calibration runs.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--session", type=Path, default=Path(os.environ.get("PI_SESSION_FILE", "")))
    collect_parser.add_argument("--output", type=Path, required=True)
    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--runs", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        spec = load_manifest(args.manifest)
        if args.command == "validate":
            print(json.dumps({"schemaVersion": 1, "id": spec["id"], "valid": True}, indent=2, sort_keys=True))
        elif args.command == "collect":
            records = collect_records(args.session, spec)
            write_json(args.output, {"schemaVersion": 1, "evalId": spec["id"], "runs": records})
            print(json.dumps({"output": str(args.output), "runs": len(records)}, indent=2, sort_keys=True))
        elif args.command == "score":
            value = read_json(args.runs)
            records = value.get("runs") if isinstance(value, dict) else None
            if not isinstance(records, list):
                raise ValueError("runs file must contain a runs array")
            summary = score_records(records, spec)
            write_json(args.output, summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"review calibration failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
