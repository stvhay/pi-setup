from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .langfuse import DEFAULT_MAX_TRACES, LangfuseError, _client_from_env
from .metrics import git_root
from .runs import default_runs_dir

REVIEW_SCORE = "improvement_review_status"
WORK_LINK_SCORE = "improvement_work_item"
OUTCOME_SCORE = "improvement_task_outcome"
TASK_OUTCOMES = {"success", "partial", "failure", "unclear"}
REVIEW_POLICY_VERSION = "v1"
TOOL_PAYLOAD_BYTE_RULE = "pi-langfuse-1.5.7-dual-null-dual-26"
MAX_TRACES_PER_SESSION = 20
OBSERVATIONS_PER_TRACE = 500
SESSION_DECISIONS = {"no-action", "actions-created", "needs-human", "excluded"}
FINDING_CATEGORIES = {
    "coordination-error",
    "expected-error",
    "infrastructure",
    "model-mismatch",
    "prompt-targeting",
    "token-inefficiency",
    "tool-use-error",
    "unknown",
    "verification-gap",
}
ERROR_RELEVANCE = {"relevant", "contributing", "expected", "recovered", "infrastructure", "unknown"}
ERROR_CLASSES = ("expected", "recovered", "provider", "infrastructure", "agent", "unknown")
ERROR_SOURCES = ("tool", "provider", "process", "artifact", "evaluator", "unknown")
IMPACTS = {"none", "low", "medium", "high", "outcome-blocking", "unknown"}
ATTRIBUTIONS = {"agent", "prompt-system", "model", "tooling", "infrastructure", "user-input", "unknown"}
INTERVENTIONS = {"prompt", "code", "tool", "eval", "workflow", "routing", "monitor", "none", "unknown"}
TOP_DECISION_FIELDS = {"schemaVersion", "reportId", "reviewPolicyVersion", "reviewedAt", "sessions"}
SESSION_DECISION_FIELDS = {"sessionId", "decision", "findings"}
FINDING_FIELDS = {
    "findingId",
    "category",
    "errorRelevance",
    "impact",
    "attribution",
    "confidence",
    "evidenceRefs",
    "proposedIntervention",
    "public",
}
PUBLIC_FIELDS = {
    "title",
    "affectedPaths",
    "aggregate",
    "proposedIntervention",
    "acceptanceCriteria",
    "evaluationRequirement",
}
FINDING_ID = re.compile(r"finding-[a-f0-9]{12}\Z")
BEAD_ID = re.compile(r"[a-z][a-z0-9]*-[A-Za-z0-9._-]+\Z")
PROMOTION_STATE_FIELDS = {"schemaVersion", "findingId", "beadId", "creationPending", "linkRepairNeeded"}
PRIVATE_PUBLIC_TEXT = re.compile(
    r"\b[A-Za-z][A-Za-z0-9+.-]*://|www\.|\b(?:langfuse|session(?:id)?|trace(?:id)?|observation(?:id)?)\b|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|"
    r"\b(?:[A-Za-z]+[_ -]?)?hash\s*[:=]\s*[0-9a-f]{8,}\b|\b[0-9a-f]{16,}\b|"
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b(?:sk|pk)-[A-Za-z0-9_-]{8,}\b|"
    r"\b(?:api[_ -]?key|authorization|bearer|password|secret)\b|(?:^|[^A-Za-z0-9])(?:~?/|[A-Za-z]:\\)",
    re.IGNORECASE,
)


def improvement_dir() -> Path:
    return Path(os.environ.get("AGNT_IMPROVEMENT_DIR", Path.home() / ".pi" / "improvement")).expanduser()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _bytes(value: Any) -> int:
    if value is None:
        return 0
    text = value if isinstance(value, str) else _canonical(value)
    return len(text.encode())


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    return int(_number(value))


def _sum_trace_metadata(traces: list[dict[str, Any]], key: str) -> tuple[int, bool]:
    values = []
    for trace in traces:
        metadata = trace.get("metadata") or {}
        if isinstance(metadata, dict) and key in metadata:
            values.append(_int(metadata[key]))
    return sum(values), bool(values)


def _tool_payload_bytes(tools: list[dict[str, Any]]) -> tuple[int | None, int | None, dict[str, Any], str | None]:
    totals = {"inputBytes": 0, "outputBytes": 0}
    available = {"inputBytes": True, "outputBytes": True}
    matched = 0
    for tool in tools:
        metadata = tool.get("metadata") if isinstance(tool.get("metadata"), dict) else {}
        if (
            "input" in tool
            and tool["input"] is None
            and "output" in tool
            and tool["output"] is None
            and type(metadata.get("inputBytes")) is int
            and metadata["inputBytes"] == 26
            and type(metadata.get("outputBytes")) is int
            and metadata["outputBytes"] == 26
        ):
            matched += 1
        for key in totals:
            value = metadata.get(key)
            if type(value) is int and value >= 0:
                totals[key] += value
            else:
                available[key] = False

    if matched:
        input_bytes = output_bytes = None
        status = "inferred-unavailable"
        gap = "inferred-tool-payload-bytes"
    elif not tools:
        input_bytes = output_bytes = 0
        status = "not-observed"
        gap = None
    else:
        input_bytes = totals["inputBytes"] if available["inputBytes"] else None
        output_bytes = totals["outputBytes"] if available["outputBytes"] else None
        status = "available" if all(available.values()) else "unavailable"
        gap = None if status == "available" else "missing-tool-payload-bytes"

    return input_bytes, output_bytes, {
        "status": status,
        "rule": TOOL_PAYLOAD_BYTE_RULE,
        "matchedObservations": matched,
        "examinedObservations": len(tools),
    }, gap


def _tool_error_signals(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals = []
    for observation in observations:
        metadata = observation.get("metadata")
        raw_signals = metadata.get("toolErrorSignals") if isinstance(metadata, dict) else None
        if not isinstance(raw_signals, list):
            continue
        for raw in raw_signals:
            if not isinstance(raw, dict):
                continue
            tool_name = raw.get("toolName")
            input_hash = raw.get("inputHash")
            classification = raw.get("classification")
            if (
                not isinstance(tool_name, str)
                or not isinstance(input_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", input_hash)
                or classification not in {"infrastructure", "recovered", "unknown"}
            ):
                continue
            signal = {
                "toolName": tool_name,
                "inputHash": input_hash,
                "count": _int(raw.get("count")),
                "cancelled": bool(raw.get("cancelled")),
                "timedOut": bool(raw.get("timedOut")),
                "classification": classification,
            }
            if isinstance(raw.get("exitCode"), int):
                signal["exitCode"] = raw["exitCode"]
            signals.append(signal)
    return signals


def _error_taxonomy(observations: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = Counter({key: 0 for key in ERROR_CLASSES})
    by_source = Counter({key: 0 for key in ERROR_SOURCES})
    blocking = Counter({"true": 0, "false": 0, "unknown": 0})
    actionable = non_actionable = unknown = 0

    def record(error_class: str, source: str, outcome_blocking: bool | None, count: int = 1) -> None:
        nonlocal actionable, non_actionable, unknown
        if count < 1:
            return
        by_class[error_class] += count
        by_source[source] += count
        blocking["true" if outcome_blocking is True else "false" if outcome_blocking is False else "unknown"] += count
        if error_class in {"expected", "recovered"}:
            non_actionable += count
        elif error_class == "unknown":
            unknown += count
        else:
            actionable += count

    for signal in _tool_error_signals(observations):
        error_class = signal["classification"]
        record(error_class, "tool", None, max(0, _int(signal.get("count"))))

    raw_error_count = 0
    unclassified_raw_error_count = 0
    for observation in observations:
        metadata = observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
        is_error = bool(metadata.get("isError") or observation.get("level") == "ERROR")
        raw_error_count += int(is_error)

        explicit_class = metadata.get("errorClass")
        artifact_failure = metadata.get("artifactFailureClass")
        has_artifact_failure = isinstance(artifact_failure, str) and bool(artifact_failure)
        error_class = explicit_class if explicit_class in ERROR_CLASSES else None
        if error_class is None and (
            metadata.get("providerFailureClass") in {"quota", "credit", "authentication", "availability"}
            or metadata.get("failureClass") == "provider"
        ):
            error_class = "provider"
        if error_class is None and (
            has_artifact_failure
            or metadata.get("failureClass") == "timeout"
            or metadata.get("timedOut") is True
        ):
            error_class = "infrastructure"
        if error_class is None and (
            metadata.get("failureClass") == "process"
            or (
                observation.get("name") == "subagent-result"
                and metadata.get("executionOutcome") == "failed"
                and type(metadata.get("exitCode")) is int
                and metadata["exitCode"] != 0
            )
        ):
            error_class = "agent"
        if error_class is None and is_error and "evaluator" in str(observation.get("name") or "").lower():
            error_class = "infrastructure"
        if error_class is None and is_error and observation.get("type") != "TOOL":
            error_class = "unknown"
        if error_class is None:
            unclassified_raw_error_count += int(is_error)
            continue

        explicit_source = metadata.get("errorSource")
        if explicit_source in ERROR_SOURCES:
            source = explicit_source
        elif error_class == "provider":
            source = "provider"
        elif has_artifact_failure:
            source = "artifact"
        elif "evaluator" in str(observation.get("name") or "").lower():
            source = "evaluator"
        elif observation.get("type") == "TOOL":
            source = "tool"
        elif error_class == "agent" or metadata.get("failureClass") == "timeout":
            source = "process"
        else:
            source = "unknown"

        explicit_blocking = metadata.get("outcomeBlocking")
        outcome_blocking = explicit_blocking if type(explicit_blocking) is bool else None
        if observation.get("name") == "interactive-result" and metadata.get("executionOutcome") == "failed":
            outcome_blocking = True
        record(error_class, source, outcome_blocking)

    classified = sum(by_class.values())
    return {
        "schemaVersion": 1,
        "rawErrorObservationCount": raw_error_count,
        "unclassifiedRawErrorObservationCount": unclassified_raw_error_count,
        "classifiedSignals": classified,
        "actionableSignals": actionable,
        "nonActionableSignals": non_actionable,
        "unknownSignals": unknown,
        "byClass": {key: by_class[key] for key in ERROR_CLASSES},
        "bySource": {key: by_source[key] for key in ERROR_SOURCES},
        "outcomeBlocking": {key: blocking[key] for key in ("true", "false", "unknown")},
    }


def _features(
    traces: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    scores: list[dict[str, Any]],
) -> dict[str, Any]:
    generations = [item for item in observations if item.get("type") == "GENERATION"]
    tools = [item for item in observations if item.get("type") == "TOOL"]
    tool_calls, has_tool_calls = _sum_trace_metadata(traces, "tool_call_count")
    tool_errors, has_tool_errors = _sum_trace_metadata(traces, "total_tool_errors")
    turns, has_turns = _sum_trace_metadata(traces, "turn_count")
    if not has_tool_calls:
        tool_calls = len(tools)
    if not has_tool_errors:
        tool_errors = sum(
            bool((item.get("metadata") if isinstance(item.get("metadata"), dict) else {}).get("isError") or item.get("level") == "ERROR")
            for item in tools
        )
    if not has_turns:
        turns = sum(item.get("name") == "turn" for item in observations)

    fresh_input = cache_read = output = 0
    cost = 0.0
    instruction_bytes = tool_bytes = input_bytes = 0
    prompt_parts = []
    models = set()
    missing_usage = False
    for generation in generations:
        usage = generation.get("usageDetails") or generation.get("usage") or {}
        input_tokens = _int(usage.get("input"))
        cached = _int(usage.get("cacheRead"))
        fresh_input += input_tokens
        cache_read += cached
        output += _int(usage.get("output"))
        missing_usage = missing_usage or not bool(usage)
        cost += _number(generation.get("calculatedTotalCost") or generation.get("totalPrice"))
        if generation.get("model"):
            models.add(str(generation["model"]))
        request = generation.get("input")
        if isinstance(request, dict):
            instructions = request.get("instructions")
            request_tools = request.get("tools")
            request_input = request.get("input")
            instruction_bytes += _bytes(instructions)
            tool_bytes += _bytes(request_tools)
            input_bytes += _bytes(request_input)
            prompt_parts.append({"instructions": instructions, "tools": request_tools})
        else:
            input_bytes += _bytes(request)

    for trace in traces:
        metadata = trace.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("model"):
            models.add(str(metadata["model"]))

    tool_input_bytes, tool_output_bytes, tool_payload_metadata, tool_payload_gap = _tool_payload_bytes(tools)
    signatures = Counter()
    evaluator_timeouts = 0
    for observation in observations:
        metadata = observation.get("metadata") or {}
        is_error = bool((isinstance(metadata, dict) and metadata.get("isError")) or observation.get("level") == "ERROR")
        if is_error:
            signatures[_hash(observation.get("statusMessage") or observation.get("output") or observation.get("name"))] += 1
            if "evaluator" in str(observation.get("name") or "").lower():
                evaluator_timeouts += 1

    evaluator_outcomes = []
    explicit_candidates = []
    apparent_candidates = []
    for index, score in enumerate(scores):
        score_name = str(score.get("name") or "")
        if score.get("source") != "EVAL" and "outcome" not in score_name.lower():
            continue
        item = {key: score.get(key) for key in ("name", "value", "dataType", "source") if score.get(key) is not None}
        evaluator_outcomes.append(item)
        timestamp = str(score.get("timestamp") or score.get("createdAt") or "")
        candidate = (timestamp, index, score.get("value"))
        if score_name == OUTCOME_SCORE and score.get("value") in TASK_OUTCOMES:
            explicit_candidates.append(candidate)
        elif "outcome" in score_name.lower() and score.get("value") in TASK_OUTCOMES:
            apparent_candidates.append(candidate)
    explicit_outcome: Any = max(explicit_candidates, default=("", -1, "unknown"))[2]
    apparent_outcome: Any = max(apparent_candidates, default=("", -1, "unknown"))[2]

    execution_candidates = []
    for index, observation in enumerate(observations):
        if observation.get("name") != "interactive-result":
            continue
        metadata = observation.get("metadata") or {}
        candidate = metadata.get("executionOutcome") if isinstance(metadata, dict) else None
        timestamp = str(observation.get("startTime") or observation.get("createdAt") or "")
        execution_candidates.append((
            timestamp,
            index,
            candidate if candidate in {"succeeded", "failed", "unavailable"} else "unknown",
        ))
    execution_outcome: Any = max(execution_candidates, default=("", -1, "unknown"))[2]

    semantic_candidates = []
    for index, trace in enumerate(traces):
        metadata = trace.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("semanticOutcome") in TASK_OUTCOMES:
            timestamp = str(trace.get("timestamp") or trace.get("createdAt") or "")
            semantic_candidates.append((timestamp, index, metadata["semanticOutcome"]))
    semantic_outcome: Any = max(semantic_candidates, default=("", -1, "unknown"))[2]

    if explicit_outcome != "unknown":
        final_outcome, final_outcome_source = explicit_outcome, "explicit"
    elif execution_outcome == "failed":
        final_outcome, final_outcome_source = "failure", "execution"
    elif execution_outcome == "unavailable":
        final_outcome, final_outcome_source = "unclear", "execution"
    elif apparent_outcome != "unknown":
        final_outcome, final_outcome_source = apparent_outcome, "apparent"
    elif semantic_outcome != "unknown":
        final_outcome, final_outcome_source = semantic_outcome, "semantic"
    else:
        final_outcome, final_outcome_source = "unknown", "unknown"

    capture_gaps = []
    if not generations:
        capture_gaps.append("no-generations")
    if missing_usage:
        capture_gaps.append("missing-usage")
    if not models:
        capture_gaps.append("missing-model")
    if final_outcome == "unknown":
        capture_gaps.append("missing-outcome")
    if tool_payload_gap:
        capture_gaps.append(tool_payload_gap)

    return {
        "executionOutcome": execution_outcome,
        "apparentOutcome": apparent_outcome,
        "finalOutcome": final_outcome,
        "finalOutcomeSource": final_outcome_source,
        "toolCalls": tool_calls,
        "toolErrors": tool_errors,
        "turns": turns,
        "latencySeconds": sum(_number(trace.get("latency")) for trace in traces),
        "tokens": {"freshInput": fresh_input, "cacheRead": cache_read, "output": output},
        "cost": round(cost, 10),
        "payloadBytes": {
            "instructions": instruction_bytes,
            "tools": tool_bytes,
            "input": input_bytes,
            "toolInput": tool_input_bytes,
            "toolOutput": tool_output_bytes,
        },
        "payloadByteMetadata": {"toolIo": tool_payload_metadata},
        "models": sorted(models),
        "promptHash": _hash(prompt_parts),
        "evaluatorOutcomes": evaluator_outcomes,
        "evaluatorTimeouts": evaluator_timeouts,
        "errorSignatures": [{"hash": key, "count": count} for key, count in sorted(signatures.items())],
        "toolErrorSignals": _tool_error_signals(observations),
        "errorTaxonomy": _error_taxonomy(observations),
        "captureGaps": capture_gaps,
    }


def _correlate(session_id: str, runs_dir: Path, scores: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if session_id.startswith("run-"):
        run_id = session_id[4:]
        if run_id and run_id not in {".", ".."} and "/" not in run_id and "\\" not in run_id:
            bundle = runs_dir / run_id
            try:
                invocation = json.loads((bundle / "invocation.yaml").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                invocation = None
            if isinstance(invocation, dict) and invocation.get("id") == run_id:
                return {
                    "status": "linked",
                    "runId": run_id,
                    "beadId": invocation.get("bead"),
                    "bundle": str(bundle),
                }
    for score in scores or []:
        metadata = score.get("metadata")
        bead_id = metadata.get("beadId") if isinstance(metadata, dict) else None
        if score.get("value") == "linked" and isinstance(bead_id, str) and BEAD_ID.fullmatch(bead_id):
            return {"status": "linked", "beadId": bead_id}
    return {"status": "unlinked"}


def _work_link_score_id(session_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:agnt:improvement-work-item:{session_id}"))


def _outcome_score_id(session_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:agnt:improvement-task-outcome:{session_id}"))


def link_session(client: Any, *, session_id: str, bead_id: str, beads_runner: Any) -> dict[str, Any]:
    if not session_id or len(session_id) > 200:
        raise ValueError("current Pi session is unavailable")
    if not BEAD_ID.fullmatch(bead_id):
        raise ValueError("bead ID is malformed")
    code, _data, _error = beads_runner(["show", bead_id])
    if code != 0:
        raise ValueError("could not load work item")
    client.put_session_score(
        score_id=_work_link_score_id(session_id),
        session_id=session_id,
        name=WORK_LINK_SCORE,
        value="linked",
        data_type="CATEGORICAL",
        metadata={"schemaVersion": 1, "beadId": bead_id},
    )
    return {"schemaVersion": 1, "status": "linked", "beadId": bead_id}


def record_session_outcome(
    client: Any,
    *,
    session_id: str,
    bead_id: str,
    outcome: str,
    beads_runner: Any,
) -> dict[str, Any]:
    if outcome not in TASK_OUTCOMES:
        raise ValueError("task outcome is unsupported")
    link_session(client, session_id=session_id, bead_id=bead_id, beads_runner=beads_runner)
    client.put_session_score(
        score_id=_outcome_score_id(session_id),
        session_id=session_id,
        name=OUTCOME_SCORE,
        value=outcome,
        data_type="CATEGORICAL",
        metadata={"schemaVersion": 1, "beadId": bead_id},
    )
    return {"schemaVersion": 1, "status": "recorded", "beadId": bead_id, "outcome": outcome}


def _write_private_json(output_dir: Path, filename: str, value: dict[str, Any]) -> Path:
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_dir.chmod(0o700)
    target = output_dir / filename
    fd, temporary = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=".tmp", dir=output_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
        directory_fd = os.open(output_dir, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise
    return target


def _write_packet(output_dir: Path, packet: dict[str, Any]) -> Path:
    return _write_private_json(output_dir, f"scan-{packet['reportId']}.json", packet)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _require_fields(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    unknown = set(value) - fields
    missing = fields - set(value)
    if unknown:
        raise ValueError(f"{name} has unknown fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"{name} is missing fields: {sorted(missing)}")
    return value


def _require_choice(value: Any, choices: set[str], name: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{name} is unsupported")
    return value


def _require_strings(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must be a non-empty string list")
    return value


def _pointer(packet: dict[str, Any], pointer: str) -> Any:
    if not pointer.startswith("/sessions/"):
        raise ValueError("evidence reference must point inside packet sessions")
    value: Any = packet
    try:
        for raw_part in pointer[1:].split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("evidence reference does not exist in packet") from exc
    return value


def _normalized_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _packet_strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {_normalized_text(value)} if len(value) >= 8 else set()
    if isinstance(value, list):
        return set().union(*(_packet_strings(item) for item in value), set())
    if isinstance(value, dict):
        return set().union(*(_packet_strings(item) for item in value.values()), set())
    return set()


def _public_strings(public: dict[str, Any]) -> list[str]:
    return [
        public["title"],
        public["aggregate"],
        public["proposedIntervention"],
        public["evaluationRequirement"],
        *public["affectedPaths"],
        *public["acceptanceCriteria"],
    ]


def validate_decisions(packet: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    _require_fields(decisions, TOP_DECISION_FIELDS, "decisions")
    if decisions["schemaVersion"] != 1:
        raise ValueError("unsupported decision schemaVersion")
    if decisions["reportId"] != packet.get("reportId"):
        raise ValueError("decision reportId does not match packet")
    if decisions["reviewPolicyVersion"] != packet.get("scan", {}).get("reviewPolicyVersion"):
        raise ValueError("decision reviewPolicyVersion does not match packet")
    if not isinstance(decisions["reviewedAt"], str):
        raise ValueError("reviewedAt must be an ISO timestamp")
    try:
        datetime.fromisoformat(decisions["reviewedAt"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewedAt must be an ISO timestamp") from exc
    if not isinstance(decisions["sessions"], list):
        raise ValueError("sessions must be a list")

    packet_sessions = {
        item.get("sessionId"): item
        for item in packet.get("sessions", [])
        if isinstance(item, dict) and isinstance(item.get("sessionId"), str)
    }
    private_strings = _packet_strings(packet)
    seen_sessions: set[str] = set()
    seen_findings: set[str] = set()
    for index, raw_session in enumerate(decisions["sessions"]):
        session = _require_fields(raw_session, SESSION_DECISION_FIELDS, f"sessions[{index}]")
        session_id = session["sessionId"]
        if session_id not in packet_sessions or session_id in seen_sessions:
            raise ValueError("sessionId must uniquely match the private packet")
        seen_sessions.add(session_id)
        decision = _require_choice(session["decision"], SESSION_DECISIONS, "decision")
        if not isinstance(session["findings"], list):
            raise ValueError("findings must be a list")
        if decision == "actions-created" and not session["findings"]:
            raise ValueError("actions-created decisions require findings")
        for finding_index, raw_finding in enumerate(session["findings"]):
            finding = _require_fields(raw_finding, FINDING_FIELDS, f"findings[{finding_index}]")
            finding_id = finding["findingId"]
            if not isinstance(finding_id, str) or not FINDING_ID.fullmatch(finding_id) or finding_id in seen_findings:
                raise ValueError("findingId must be unique and match finding-<12 lowercase hex>")
            seen_findings.add(finding_id)
            _require_choice(finding["category"], FINDING_CATEGORIES, "category")
            _require_choice(finding["errorRelevance"], ERROR_RELEVANCE, "errorRelevance")
            _require_choice(finding["impact"], IMPACTS, "impact")
            _require_choice(finding["attribution"], ATTRIBUTIONS, "attribution")
            _require_choice(finding["proposedIntervention"], INTERVENTIONS, "proposedIntervention")
            confidence = finding["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ValueError("confidence must be between 0 and 1")
            for evidence_ref in _require_strings(finding["evidenceRefs"], "evidenceRefs"):
                _pointer(packet, evidence_ref)
            public = _require_fields(finding["public"], PUBLIC_FIELDS, "public")
            _require_strings(public["affectedPaths"], "public.affectedPaths")
            _require_strings(public["acceptanceCriteria"], "public.acceptanceCriteria")
            for name in ("title", "aggregate", "proposedIntervention", "evaluationRequirement"):
                if not isinstance(public[name], str) or not public[name].strip():
                    raise ValueError(f"public.{name} must be non-empty")
            for text in _public_strings(public):
                normalized = _normalized_text(text)
                if any(private in normalized for private in private_strings):
                    raise ValueError("public summary contains copied private packet text")
    return decisions


def _review_score_id(session_id: str, policy_version: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:agnt:improvement-review:{policy_version}:{session_id}"))


def review_sessions(
    client: Any,
    packet: dict[str, Any],
    decisions: dict[str, Any],
    *,
    apply: bool = False,
) -> dict[str, Any]:
    validated = validate_decisions(packet, decisions)
    findings = sum(len(session["findings"]) for session in validated["sessions"])
    written = 0
    if apply:
        for session in validated["sessions"]:
            client.put_session_score(
                score_id=_review_score_id(session["sessionId"], validated["reviewPolicyVersion"]),
                session_id=session["sessionId"],
                name=REVIEW_SCORE,
                value=session["decision"],
                data_type="CATEGORICAL",
                metadata={
                    "schemaVersion": 1,
                    "reviewPolicyVersion": validated["reviewPolicyVersion"],
                    "reviewedAt": validated["reviewedAt"],
                    "findingIds": [finding["findingId"] for finding in session["findings"]],
                    "beadIds": [],
                },
            )
            written += 1
    return {
        "schemaVersion": 1,
        "status": "applied" if apply else "preview",
        "reviewedSessions": len(validated["sessions"]),
        "findings": findings,
        "scoresWritten": written,
    }


def _safe_public_text(value: str, name: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    if not text or any(not character.isprintable() for character in text) or PRIVATE_PUBLIC_TEXT.search(text):
        raise ValueError(f"public {name} contains private or unsafe text")
    return text


def _public_bead(packet: dict[str, Any], decisions: dict[str, Any], finding_id: str, tracked_paths: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_decisions(packet, decisions)
    match = None
    owner = None
    for session in decisions["sessions"]:
        for finding in session["findings"]:
            if finding["findingId"] == finding_id:
                match, owner = finding, session
    if match is None or owner is None:
        raise ValueError("findingId does not exist in decisions")
    if match["category"] == "unknown":
        raise ValueError("public promotion requires a known category")
    public = match["public"]
    paths = public["affectedPaths"]
    for path in paths:
        if (
            any(not character.isprintable() for character in path)
            or path.startswith(("/", "~"))
            or "\\" in path
            or ".." in Path(path).parts
            or path not in tracked_paths
        ):
            raise ValueError("public affectedPaths must be tracked relative paths")
    title = _safe_public_text(public["title"], "title")
    aggregate = _safe_public_text(public["aggregate"], "aggregate")
    intervention = _safe_public_text(public["proposedIntervention"], "proposedIntervention")
    evaluation = _safe_public_text(public["evaluationRequirement"], "evaluationRequirement")
    criteria = [_safe_public_text(item, "acceptanceCriteria") for item in public["acceptanceCriteria"]]
    category = match["category"]
    path_lines = "\n".join(f"- {path}" for path in paths)
    description = (
        f"Category: {category}\n\n"
        f"Affected tracked paths:\n{path_lines}\n\n"
        f"Sanitized aggregate: {aggregate}\n\n"
        f"Proposed intervention: {intervention}\n\n"
        f"Evaluation requirement: {evaluation}"
    )
    return ({
        "title": title,
        "category": category,
        "affectedPaths": paths,
        "description": description,
        "acceptance": "\n".join(f"- {item}" for item in criteria),
        "labels": ["continuous-improvement", category, "human-approved"],
    }, owner)


def render_public_bead(bead: dict[str, Any]) -> str:
    return (
        f"Title: {bead['title']}\n"
        f"Type: task\n"
        f"Priority: 2\n"
        f"Labels: {', '.join(bead['labels'])}\n\n"
        f"Description:\n{bead['description']}\n\n"
        f"Acceptance criteria:\n{bead['acceptance']}"
    )


def _promotion_approval_preview(bead: dict[str, Any]) -> dict[str, str]:
    return {
        "action": "Create one public continuous-improvement Bead.",
        "scope": "Creates one Bead with this exact public content:\n\n" + render_public_bead(bead),
        "consequences": "Creates committed public work metadata; no prompt, policy, or code changes occur.",
        "reversibility": "Bead may be closed, but committed history remains.",
        "closeoutPath": "Create Bead, store its public ID in private review state, and verify private linkage.",
    }


def _approval_metadata(approval: Any) -> dict[str, Any]:
    if isinstance(approval, list) and approval:
        approval = approval[0]
    raw = approval.get("metadata") if isinstance(approval, dict) else None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, dict) or not isinstance(raw.get("pi"), dict):
        return {}
    value = raw["pi"].get("approval")
    return value if isinstance(value, dict) else {}


def _has_exact_human_approval(approval: Any, expected: dict[str, str]) -> bool:
    value = _approval_metadata(approval)
    resolver = value.get("resolver")
    return (
        value.get("kind") == "approval"
        and value.get("status") == "approved"
        and resolver == {"kind": "human-ui"}
        and value.get("preview") == expected
    )


def _created_bead_id(data: Any) -> str:
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict) and isinstance(data.get("id"), str) and data["id"]:
        return data["id"]
    raise RuntimeError("Bead creation did not return an ID")


def _promotion_state_path(state_dir: Path, finding_id: str) -> Path:
    return state_dir / f"promotion-{finding_id}.json"


def _load_promotion_state(path: Path, finding_id: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("private promotion state is invalid") from exc
    valid = (
        isinstance(value, dict)
        and set(value) == PROMOTION_STATE_FIELDS
        and value.get("schemaVersion") == 1
        and value.get("findingId") == finding_id
        and isinstance(value.get("beadId"), str)
        and bool(BEAD_ID.fullmatch(value["beadId"]))
        and isinstance(value.get("creationPending"), bool)
        and isinstance(value.get("linkRepairNeeded"), bool)
    )
    if not valid:
        raise ValueError("private promotion state is invalid")
    return value


@contextmanager
def _promotion_lock(state_dir: Path, finding_id: str):
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_dir.chmod(0o700)
    descriptor = os.open(state_dir / f".{finding_id}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _new_bead_id() -> str:
    return f"pi-{secrets.token_hex(4)}"


def _write_review_marker(client: Any, decisions: dict[str, Any], session: dict[str, Any], bead_ids: list[str]) -> None:
    client.put_session_score(
        score_id=_review_score_id(session["sessionId"], decisions["reviewPolicyVersion"]),
        session_id=session["sessionId"],
        name=REVIEW_SCORE,
        value=session["decision"],
        data_type="CATEGORICAL",
        metadata={
            "schemaVersion": 1,
            "reviewPolicyVersion": decisions["reviewPolicyVersion"],
            "reviewedAt": decisions["reviewedAt"],
            "findingIds": [finding["findingId"] for finding in session["findings"]],
            "beadIds": sorted(set(bead_ids)),
        },
    )


def _create_bead(beads_runner: Any, bead: dict[str, Any], bead_id: str) -> None:
    args = [
        "create", bead["title"],
        "--id", bead_id,
        "--type", "task",
        "--priority", "2",
        "--labels", ",".join(bead["labels"]),
        "--description", bead["description"],
        "--acceptance", bead["acceptance"],
    ]
    code, data, _ = beads_runner(args)
    if code != 0:
        raise RuntimeError("Bead creation failed")
    if _created_bead_id(data) != bead_id:
        raise RuntimeError("Bead creation returned an unexpected ID")


def _repair_creation(beads_runner: Any, state_dir: Path, state_path: Path, state: dict[str, Any]) -> bool:
    code, data, _ = beads_runner(["show", state["beadId"]])
    if code != 0:
        return False
    try:
        shown_id = _created_bead_id(data)
    except RuntimeError:
        return False
    if shown_id != state["beadId"]:
        return False
    state["creationPending"] = False
    _write_private_json(state_dir, state_path.name, state)
    return True


def _apply_promotion(
    client: Any,
    decisions: dict[str, Any],
    *,
    finding_id: str,
    state_dir: Path,
    bead: dict[str, Any],
    session: dict[str, Any],
    approval: Any,
    approval_preview: dict[str, str],
    beads_runner: Any,
) -> dict[str, Any]:
    state_path = _promotion_state_path(state_dir, finding_id)
    state = _load_promotion_state(state_path, finding_id)
    if state and state["creationPending"] and not _repair_creation(beads_runner, state_dir, state_path, state):
        return {"schemaVersion": 1, "status": "creation-repair-needed", "created": False}
    if state and not state["linkRepairNeeded"]:
        return {"schemaVersion": 1, "status": "already-promoted", "beadId": state["beadId"], "created": False}
    created_now = False
    if state is None:
        if not _has_exact_human_approval(approval, approval_preview):
            raise ValueError("promotion apply requires exact human approval")
        state = {
            "schemaVersion": 1,
            "findingId": finding_id,
            "beadId": _new_bead_id(),
            "creationPending": True,
            "linkRepairNeeded": True,
        }
        _write_private_json(state_dir, state_path.name, state)
        _create_bead(beads_runner, bead, state["beadId"])
        state["creationPending"] = False
        _write_private_json(state_dir, state_path.name, state)
        created_now = True

    if client is None:
        raise ValueError("promotion apply requires Langfuse client")
    bead_ids = []
    for finding in session["findings"]:
        finding_id_value = finding["findingId"]
        finding_state = _load_promotion_state(_promotion_state_path(state_dir, finding_id_value), finding_id_value)
        if finding_state and not finding_state["creationPending"]:
            bead_ids.append(finding_state["beadId"])
    try:
        _write_review_marker(client, decisions, session, bead_ids)
    except LangfuseError:
        return {
            "schemaVersion": 1,
            "status": "link-repair-needed",
            "beadId": state["beadId"],
            "created": created_now,
        }
    state["linkRepairNeeded"] = False
    _write_private_json(state_dir, state_path.name, state)
    return {
        "schemaVersion": 1,
        "status": "promoted",
        "beadId": state["beadId"],
        "created": created_now,
    }


def promote_finding(
    client: Any,
    packet: dict[str, Any],
    decisions: dict[str, Any],
    *,
    finding_id: str,
    state_dir: Path,
    repository_root: Path,
    tracked_paths: set[str],
    apply: bool = False,
    approval: Any = None,
    beads_runner: Any,
) -> dict[str, Any]:
    if not FINDING_ID.fullmatch(finding_id):
        raise ValueError("findingId is malformed")
    if _inside(state_dir, repository_root):
        raise ValueError("private promotion state must be outside repository")
    bead, session = _public_bead(packet, decisions, finding_id, tracked_paths)
    approval_preview = _promotion_approval_preview(bead)
    if not apply:
        return {"schemaVersion": 1, "status": "preview", "bead": bead, "approvalPreview": approval_preview}
    with _promotion_lock(state_dir, finding_id):
        return _apply_promotion(
            client,
            decisions,
            finding_id=finding_id,
            state_dir=state_dir,
            bead=bead,
            session=session,
            approval=approval,
            approval_preview=approval_preview,
            beads_runner=beads_runner,
        )


def _session_score_since(session_id: str, fallback: str) -> str:
    prefix = session_id.split("_", 1)[0]
    try:
        started = datetime.strptime(prefix, "%Y-%m-%dT%H-%M-%S-%fZ").replace(tzinfo=timezone.utc)
        fallback_time = datetime.fromisoformat(fallback.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if started >= fallback_time:
        return fallback
    return started.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_current_review(scores: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(score.get("metadata"), dict)
        and score["metadata"].get("reviewPolicyVersion") == REVIEW_POLICY_VERSION
        for score in scores
    )


def scan_sessions(
    client: Any,
    *,
    since: str,
    until: str,
    limit: int,
    output_dir: Path,
    runs_dir: Path,
    repository_root: Path,
    max_traces: int = DEFAULT_MAX_TRACES,
    recheck: bool = False,
    dry_run: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if limit < 1:
        raise ValueError("scan limit must be positive")
    if not since or not until:
        raise ValueError("scan requires time bounds")
    if _inside(output_dir, repository_root):
        raise ValueError("improvement directory must be outside repository")

    discovery = client.list_traces_with_metadata(
        from_timestamp=since,
        to_timestamp=until,
        max_traces=max_traces,
    )
    traces = discovery["traces"]
    groups: dict[str, list[dict[str, Any]]] = {}
    attributable = 0
    for trace in traces:
        session_id = trace.get("sessionId")
        if isinstance(session_id, str) and session_id:
            attributable += 1
            groups.setdefault(session_id, []).append(trace)
    trace_discovery = {
        "totalAvailable": discovery.get("totalAvailable"),
        "scanned": len(traces),
        "maxTraces": max_traces,
        "attributable": attributable,
        "unattributed": len(traces) - attributable,
        "complete": discovery["complete"],
        "continuation": discovery["continuation"],
    }
    review_cache: dict[str, bool] = {}
    for session_id in groups:
        scores = [] if recheck else client.list_scores(
            from_timestamp=_session_score_since(session_id, since),
            to_timestamp=until,
            session_id=session_id,
            name=REVIEW_SCORE,
            limit=100,
        )
        review_cache[session_id] = _is_current_review(scores)
    eligible_groups = [(session_id, items) for session_id, items in groups.items() if not review_cache[session_id]]

    sessions = []
    for session_id, session_traces in eligible_groups[:limit]:
        selected_traces = session_traces[:MAX_TRACES_PER_SESSION]
        observations = []
        trace_scores = []
        observations_truncated = False
        for trace in selected_traces:
            rows = client.list_observations(
                from_start_time=since,
                to_start_time=until,
                trace_id=str(trace["id"]),
                limit=OBSERVATIONS_PER_TRACE + 1,
            )
            observations_truncated = observations_truncated or len(rows) > OBSERVATIONS_PER_TRACE
            observations.extend(rows[:OBSERVATIONS_PER_TRACE])
            trace_scores.extend(client.list_scores(
                from_timestamp=since,
                to_timestamp=until,
                trace_id=str(trace["id"]),
                limit=100,
            ))
        score_since = _session_score_since(session_id, since)
        link_scores = client.list_scores(
            from_timestamp=score_since,
            to_timestamp=until,
            session_id=session_id,
            name=WORK_LINK_SCORE,
            limit=100,
        )
        outcome_scores = client.list_scores(
            from_timestamp=score_since,
            to_timestamp=until,
            session_id=session_id,
            name=OUTCOME_SCORE,
            limit=100,
        )
        correlation = _correlate(session_id, runs_dir, link_scores)
        features = _features(selected_traces, observations, [*trace_scores, *outcome_scores])
        if len(session_traces) > len(selected_traces):
            features["captureGaps"].append("trace-limit")
        if observations_truncated:
            features["captureGaps"].append("observation-limit")
        sessions.append({
            "sessionId": session_id,
            "traceIds": [str(trace["id"]) for trace in selected_traces],
            "correlation": correlation,
            "features": features,
        })

    report_id = _hash({"since": since, "until": until, "sessions": [item["sessionId"] for item in sessions]})[:16]
    packet = {
        "schemaVersion": 2,
        "reportId": report_id,
        "createdAt": until,
        "scan": {
            "since": since,
            "until": until,
            "limit": limit,
            "recheck": recheck,
            "reviewPolicyVersion": REVIEW_POLICY_VERSION,
            "traceDiscovery": trace_discovery,
        },
        "sessions": sessions,
    }
    summary = {
        "schemaVersion": 1,
        "status": "ok",
        "scannedTraces": len(traces),
        "traceDiscovery": trace_discovery,
        "candidateSessions": len(groups),
        "eligibleSessions": len(sessions),
        "reviewedSessionsSkipped": sum(review_cache.get(session_id, False) for session_id in groups),
        "unlinkedSessions": sum(item["correlation"]["status"] == "unlinked" for item in sessions),
        "reportWritten": not dry_run,
        "reportPath": None,
    }
    if not dry_run:
        summary["reportPath"] = str(_write_packet(output_dir, packet))
    return summary, packet


def _git_tracked_paths(repository_root: Path) -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ValueError("could not list tracked paths")
    return {item.decode("utf-8") for item in completed.stdout.split(b"\0") if item}


def _beads(args: list[str]) -> tuple[int, Any, str]:
    from .work import run_beads_json

    return run_beads_json(args)


def current_session_id() -> str:
    session_file = os.environ.get("PI_SESSION_FILE")
    session_id = Path(session_file).stem if session_file else os.environ.get("PI_SESSION_ID")
    if not session_id:
        raise ValueError("current Pi session is unavailable")
    return session_id


def link_current_session(bead_id: str) -> dict[str, Any]:
    return link_session(
        _client_from_env(),
        session_id=current_session_id(),
        bead_id=bead_id,
        beads_runner=_beads,
    )


def _load_private_object(path: Path, repository_root: Path) -> dict[str, Any]:
    if _inside(path, repository_root):
        raise ValueError("improvement review files must be outside repository")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("improvement review file must contain an object")
    return value


def _timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _scan_limit(value: str) -> int:
    limit = int(value)
    if not 1 <= limit <= 50:
        raise argparse.ArgumentTypeError("limit must be between 1 and 50")
    return limit


def _max_traces(value: str) -> int:
    limit = int(value)
    if limit < 1:
        raise argparse.ArgumentTypeError("max traces must be positive")
    return limit


def cmd_improve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt improve", description="Review private Langfuse telemetry safely.")
    sub = parser.add_subparsers(dest="action")
    scan = sub.add_parser("scan", help="write a bounded private review packet")
    scan.add_argument("--since", type=_timestamp)
    scan.add_argument("--limit", type=_scan_limit, default=20)
    scan.add_argument("--max-traces", type=_max_traces, default=DEFAULT_MAX_TRACES)
    scan.add_argument("--recheck", action="store_true")
    scan.add_argument("--dry-run", action="store_true")
    scan.add_argument("--json", action="store_true")
    link = sub.add_parser("link", help="link the current private session to a public work item")
    link.add_argument("bead")
    link.add_argument("--json", action="store_true")
    outcome = sub.add_parser("outcome", help="record a linked final outcome for the current private session")
    outcome.add_argument("bead")
    outcome.add_argument("outcome", choices=sorted(TASK_OUTCOMES))
    outcome.add_argument("--json", action="store_true")
    review = sub.add_parser("review", help="validate private review decisions and optionally mark sessions")
    review.add_argument("report", type=Path)
    review.add_argument("decisions", type=Path)
    review.add_argument("--apply", action="store_true")
    review.add_argument("--json", action="store_true")
    promote = sub.add_parser("promote", help="preview or create one public-safe improvement Bead")
    promote.add_argument("report", type=Path)
    promote.add_argument("decisions", type=Path)
    promote.add_argument("--finding", required=True)
    promote.add_argument("--apply", action="store_true")
    promote.add_argument("--approval")
    promote.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "outcome":
        try:
            session_file = os.environ.get("PI_SESSION_FILE")
            if not session_file:
                raise ValueError("current Pi session is unavailable")
            summary = record_session_outcome(
                _client_from_env(),
                session_id=Path(session_file).stem,
                bead_id=args.bead,
                outcome=args.outcome,
                beads_runner=_beads,
            )
        except (LangfuseError, OSError, ValueError):
            if args.json:
                print(json.dumps({"schemaVersion": 1, "status": "error", "error": "improvement outcome failed"}))
            else:
                print("Improvement outcome failed.", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(f"Recorded {summary['outcome']} for {summary['beadId']}.")
        return 0
    if args.action == "link":
        try:
            summary = link_current_session(args.bead)
        except (LangfuseError, OSError, ValueError):
            if args.json:
                print(json.dumps({"schemaVersion": 1, "status": "error", "error": "improvement link failed"}))
            else:
                print("Improvement link failed.", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(f"Linked current private session to {summary['beadId']}.")
        return 0
    if args.action == "promote":
        try:
            repository_root = git_root()
            packet = _load_private_object(args.report, repository_root)
            decisions = _load_private_object(args.decisions, repository_root)
            approval = None
            if args.apply:
                if not args.approval:
                    raise ValueError("promotion apply requires approval")
                code, approval, _ = _beads(["show", args.approval])
                if code != 0:
                    raise ValueError("could not load promotion approval")
            summary = promote_finding(
                _client_from_env() if args.apply else None,
                packet,
                decisions,
                finding_id=args.finding,
                state_dir=improvement_dir(),
                repository_root=repository_root,
                tracked_paths=_git_tracked_paths(repository_root),
                apply=args.apply,
                approval=approval,
                beads_runner=_beads,
            )
        except (LangfuseError, OSError, RuntimeError, ValueError, json.JSONDecodeError):
            if args.json:
                print(json.dumps({"schemaVersion": 1, "status": "error", "error": "improvement promotion failed"}))
            else:
                print("Improvement promotion failed.", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        elif summary["status"] == "preview":
            print(render_public_bead(summary["bead"]))
        else:
            print(f"Promotion status: {summary['status']}; Bead: {summary.get('beadId', 'none')}")
        return 3 if summary["status"] == "link-repair-needed" else 0
    if args.action == "review":
        try:
            repository_root = git_root()
            packet = _load_private_object(args.report, repository_root)
            decisions = _load_private_object(args.decisions, repository_root)
            summary = review_sessions(_client_from_env() if args.apply else None, packet, decisions, apply=args.apply)
        except (LangfuseError, OSError, ValueError, json.JSONDecodeError):
            if args.json:
                print(json.dumps({"schemaVersion": 1, "status": "error", "error": "improvement review failed"}))
            else:
                print("Improvement review failed.", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(f"Reviewed sessions: {summary['reviewedSessions']}; status: {summary['status']}")
        return 0
    if args.action != "scan":
        parser.print_help()
        return 0

    now = datetime.now(timezone.utc).replace(microsecond=0)
    until = now.isoformat().replace("+00:00", "Z")
    since = args.since or (now - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    try:
        summary, _ = scan_sessions(
            _client_from_env(),
            since=since,
            until=until,
            limit=args.limit,
            output_dir=improvement_dir(),
            runs_dir=default_runs_dir(),
            repository_root=git_root(),
            max_traces=args.max_traces,
            recheck=args.recheck,
            dry_run=args.dry_run,
        )
    except (LangfuseError, OSError, ValueError):
        if args.json:
            print(json.dumps({"schemaVersion": 1, "status": "error", "error": "improvement scan failed"}))
        else:
            print("Improvement scan failed.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"Eligible sessions: {summary['eligibleSessions']}; report: {summary['reportPath'] or 'not written'}")
    return 0


__all__ = ["cmd_improve", "improvement_dir", "scan_sessions"]
