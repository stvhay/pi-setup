from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .actions import assignment_action_contract
from .langfuse import DEFAULT_MAX_TRACES, MAX_PAGE_SIZE, LangfuseError, _client_from_env
from .metrics import git_root
from .quality import (
    BEAD_ID,
    FINDING_CORE_FIELDS,
    MAX_LANGFUSE_ANNOTATION_ITEMS,
    MAX_REVIEW_ASSIGNMENT_ITEMS,
    TASK_OUTCOMES,
    SessionWorkItemConflict,
    build_review_assignment,
    capture_session_link,
    capture_session_outcome,
    current_session_id,
    latest_work_item_result,
    normalize_assigned_review_result,
    normalize_langfuse_annotation_result,
    quality_work_target,
    revoke_correction_grant,
    validate_evidence_ref,
    validate_finding,
    validate_public_work,
)
from .runs import default_runs_dir

REVIEW_SCORE = "improvement_review_status"
WORK_LINK_SCORE = "improvement_work_item"
OUTCOME_SCORE = "improvement_task_outcome"
REVIEW_POLICY_VERSION = "v4"
TOOL_PAYLOAD_BYTE_RULE = "pi-langfuse-1.5.7-dual-null-dual-26"
TOOL_PAYLOAD_BYTE_V1_RULE = "pi-langfuse-tool-payload-bytes-v1"
TOOL_PAYLOAD_BYTE_MIXED_RULE = "pi-langfuse-tool-payload-bytes-v1+legacy"
MAX_TRACES_PER_SESSION = 20
OBSERVATIONS_PER_TRACE = 500
SCORES_PER_QUERY = 100
SETTLEMENT_LAG_SECONDS = 300
COHORT_OUTCOMES = ("success", "partial", "failure", "unclear", "unknown")
CHILD_TRACE_MODES = ("agentic", "one-shot", "unknown")
CHILD_TRACE_AVAILABILITY = (
    "available",
    "expected-unavailable",
    "missing",
    "ambiguous",
    "incomplete",
    "unknown",
)
PROJECTION_MODES = {"agentic", "one-shot"}
PROJECTION_THINKING_LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh", "default"}
PROJECTION_OUTPUT_CONTRACTS = {"inline", "artifact", "status-only", "pass-no-findings"}
PROJECTION_ROUTING_TASK = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
PROJECTION_ATTRIBUTION_FIELDS = {
    "modelDimensionsStatus",
    "provider",
    "model",
    "target",
    "thinkingLevel",
    "routingTask",
    "outputContract",
    "workerElapsedStatus",
}
LIMIT_TERMINATION_REASONS = (
    "request-limit",
    "tool-limit",
    "token-limit",
    "output-limit",
    "cost-limit",
    "time-limit",
    "idle-limit",
)
PAYLOAD_BYTE_STATUSES = ("available", "inferred-unavailable", "not-observed", "unavailable")
COHORT_CAPTURE_GAPS = (
    "no-generations",
    "missing-usage",
    "missing-provider",
    "invalid-provider",
    "missing-model",
    "invalid-model",
    "missing-outcome",
    "mismatched-work-item-outcome",
    "inferred-tool-payload-bytes",
    "missing-tool-payload-bytes",
    "trace-limit",
    "observation-limit",
    "score-limit",
    "missing-child-trace",
    "ambiguous-child-trace",
    "incomplete-child-trace",
    "unknown-child-trace",
    "invalid-child-trace-declaration",
)
SESSION_DECISIONS = {"no-action", "actions-created", "needs-human", "excluded"}
V1_FINDING_CATEGORIES = {
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
FINDING_CATEGORIES = V1_FINDING_CATEGORIES | {"security-boundary"}
FINDING_CATEGORIES_BY_POLICY = {
    "v1": V1_FINDING_CATEGORIES,
    "v2": FINDING_CATEGORIES,
    "v3": FINDING_CATEGORIES,
    REVIEW_POLICY_VERSION: FINDING_CATEGORIES,
}
ERROR_RELEVANCE = {"relevant", "contributing", "expected", "recovered", "infrastructure", "unknown"}
ERROR_CLASSES = ("expected", "recovered", "provider", "infrastructure", "agent", "unknown")
ERROR_SOURCES = ("tool", "provider", "process", "artifact", "evaluator", "unknown")
IMPACTS = {"none", "low", "medium", "high", "outcome-blocking", "unknown"}
ATTRIBUTIONS = {"agent", "prompt-system", "model", "tooling", "infrastructure", "user-input", "unknown"}
INTERVENTIONS = {"prompt", "code", "tool", "eval", "workflow", "routing", "monitor", "none", "unknown"}
EVIDENCE_STAGES = {"event", "incident", "pattern", "change", "unknown"}
TOP_DECISION_FIELDS = {"schemaVersion", "reportId", "reviewPolicyVersion", "reviewedAt", "sessions"}
CURRENT_REVIEW_RESULT_FIELDS = TOP_DECISION_FIELDS | {
    "assignmentId",
    "reviewStatus",
    "route",
    "gaps",
    "attempt",
}
REVIEW_STATUS_GAPS = {
    "unavailable": "reviewer-unavailable",
    "timed-out": "review-timed-out",
    "privacy-uncertain": "review-private-unsafe",
    "schema-invalid": "review-result-schema-invalid",
}
SESSION_DECISION_FIELDS = {"sessionId", "decision", "findings"}
LEGACY_FINDING_FIELDS = {
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
IMPROVEMENT_FINDING_EXTENSIONS = {
    "errorRelevance",
    "attribution",
    "confidence",
    "evidenceStage",
    "interventionType",
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
IMPROVEMENT_FINDING_ID = re.compile(r"finding-[a-f0-9]{12}\Z")
PROMOTION_STATE_FIELDS = {"schemaVersion", "findingId", "beadId", "creationPending", "linkRepairNeeded"}
MONITORED_PROMOTION_STATE_FIELDS = PROMOTION_STATE_FIELDS | {"monitoring"}
LEGACY_MONITORING_FIELDS = {
    "status",
    "cohortKey",
    "minimumSamples",
    "implementedAt",
    "sampleIds",
    "recurrentFindingIds",
}
MONITORING_FIELDS = LEGACY_MONITORING_FIELDS | {"cohortDimensions", "followUpTarget"}
MONITORING_DIMENSION_FIELDS = {
    "task",
    "risk",
    "contextShape",
    "role",
    "models",
    "promptHash",
    "policyFingerprint",
    "effects",
}
MONITORING_STATUSES = {"promoted", "monitoring", "validated", "recurrent"}
MONITORING_MINIMUM_SAMPLES = 5
SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")
SHA256_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")
COHORT_DIMENSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+:/-]{0,127}\Z")
COHORT_CREDENTIAL_PREFIX = re.compile(r"(?:gh[pousr]_|github_pat_|glpat-|xox[baprs]-|npm_|pypi-)", re.IGNORECASE)
PRIVATE_PUBLIC_TEXT = re.compile(
    r"\b[A-Za-z][A-Za-z0-9+.-]*://|www\.|\b(?:langfuse|session(?:id)?|trace(?:id)?|observation(?:id)?)\b|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|"
    r"\b(?:[A-Za-z]+[_ -]?)?hash\s*[:=]\s*[0-9a-f]{8,}\b|\b[0-9a-f]{16,}\b|"
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b(?:sk|pk)-[A-Za-z0-9_-]{8,}\b|"
    r"\b(?:api[_ -]?key|authorization|bearer|password|secret)\b|(?:^|[^A-Za-z0-9])(?:~?/|[A-Za-z]:\\)",
    re.IGNORECASE,
)


class PrivateReviewUnsafe(ValueError):
    pass


def _unavailable_langfuse_annotation_evidence(queue_id: str) -> dict[str, Any]:
    return normalize_langfuse_annotation_result(
        queue_id=queue_id,
        queue=None,
        items=[],
        scores=[],
        score_configs=[],
        completeness={
            "queue": False,
            "items": False,
            "scores": False,
            "scoreConfigs": False,
        },
        gaps=[
            "items-unavailable",
            "queue-unavailable",
            "score-configs-unavailable",
            "scores-unavailable",
        ],
    )


def import_langfuse_annotation_evidence(
    client: Any,
    queue_id: str,
    *,
    limit: int = MAX_LANGFUSE_ANNOTATION_ITEMS,
) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= MAX_LANGFUSE_ANNOTATION_ITEMS:
        raise ValueError("Langfuse annotation limit is invalid")
    if client is None:
        return _unavailable_langfuse_annotation_evidence(queue_id)
    try:
        queue = client.get_annotation_queue(queue_id)
    except LangfuseError:
        return _unavailable_langfuse_annotation_evidence(queue_id)

    gaps = []
    completeness = {"queue": True, "items": False, "scores": False, "scoreConfigs": False}
    try:
        item_result = client.list_annotation_queue_items(queue_id, limit=limit)
        items = item_result["items"]
        completeness["items"] = item_result["complete"] is True
        if not completeness["items"]:
            gaps.append("item-limit")
    except (KeyError, LangfuseError, TypeError):
        items = []
        gaps.append("items-unavailable")

    try:
        score_result = client.list_annotation_scores(queue_id, limit=limit)
        scores = score_result["scores"]
        completeness["scores"] = score_result["complete"] is True
        if not completeness["scores"]:
            gaps.append("score-limit")
    except (KeyError, LangfuseError, TypeError):
        scores = []
        gaps.append("scores-unavailable")

    config_ids = queue.get("scoreConfigIds") if isinstance(queue, dict) else None
    score_configs = []
    if isinstance(config_ids, list):
        if len(config_ids) > limit:
            gaps.append("score-config-limit")
        config_failed = False
        for config_id in config_ids[:limit]:
            try:
                score_configs.append(client.get_score_config(config_id))
            except LangfuseError:
                config_failed = True
        if config_failed:
            gaps.append("score-configs-unavailable")
        completeness["scoreConfigs"] = len(config_ids) <= limit and not config_failed
    else:
        gaps.append("score-configs-unavailable")

    return normalize_langfuse_annotation_result(
        queue_id=queue_id,
        queue=queue,
        items=items,
        scores=scores,
        score_configs=score_configs,
        completeness=completeness,
        gaps=gaps,
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


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    return int(_number(value))


def _usage_details(generation: dict[str, Any]) -> dict[str, Any] | None:
    primary = generation.get("usageDetails")
    if isinstance(primary, dict):
        return primary
    fallback = generation.get("usage")
    return fallback if isinstance(fallback, dict) else None


def _usage_count(usage: dict[str, Any] | None, key: str) -> int | None:
    value = usage.get(key) if usage is not None else None
    if type(value) not in {int, float} or not math.isfinite(value) or value < 0 or int(value) != value:
        return None
    return int(value)


def _cohort_dimension(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFKC", value).strip()
    if (
        not COHORT_DIMENSION.fullmatch(text)
        or COHORT_CREDENTIAL_PREFIX.search(text)
        or PRIVATE_PUBLIC_TEXT.search(text)
    ):
        return None
    return text


def _enabled_model_targets(repository_root: Path) -> set[str]:
    try:
        settings = json.loads((repository_root / "pi" / "agent" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    values = settings.get("enabledModels") if isinstance(settings, dict) else None
    if not isinstance(values, list):
        return set()
    targets = set()
    for value in values:
        target = _cohort_dimension(value)
        if target is None or "/" not in target:
            continue
        provider, model = target.split("/", 1)
        if _cohort_dimension(provider) and _cohort_dimension(model):
            targets.add(target)
    return targets


def _cohort_dimension_allowlists(repository_root: Path) -> tuple[set[str], set[str]]:
    providers: set[str] = set()
    models: set[str] = set()
    for target in _enabled_model_targets(repository_root):
        provider, model = target.split("/", 1)
        providers.add(provider)
        models.update((model, target))
    return providers, models


def _cohort_billing_classes(repository_root: Path) -> dict[str, str]:
    enabled = _enabled_model_targets(repository_root)
    try:
        catalog = json.loads((repository_root / "pi" / "agent" / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(catalog, dict) or catalog.get("schemaVersion") != 1:
        return {}
    families = catalog.get("families")
    if not isinstance(families, dict):
        return {}
    candidates: dict[str, set[str]] = {}
    for family in families.values():
        venues = family.get("venues") if isinstance(family, dict) else None
        if not isinstance(venues, list):
            continue
        for venue in venues:
            if not isinstance(venue, dict):
                continue
            target = _cohort_dimension(venue.get("target"))
            billing_class = venue.get("billingClass")
            if target in enabled and billing_class in {"subscription", "metered"}:
                candidates.setdefault(target, set()).add(billing_class)
    return {
        target: next(iter(values))
        for target, values in candidates.items()
        if len(values) == 1
    }


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
    matched = versioned = truncated = 0
    for tool in tools:
        metadata = tool.get("metadata") if isinstance(tool.get("metadata"), dict) else {}
        if "toolPayloadBytesVersion" in metadata:
            versioned += 1
            if type(metadata.get("toolPayloadBytesVersion")) is not int or metadata["toolPayloadBytesVersion"] != 1:
                available = dict.fromkeys(available, False)
                continue
            for direction, key in (("input", "inputBytes"), ("output", "outputBytes")):
                state = metadata.get(f"{direction}BytesState")
                value = metadata.get(key)
                if state == "absent":
                    continue
                if state in {"available", "truncated"} and type(value) is int and value >= 0:
                    totals[key] += value
                    truncated += int(state == "truncated")
                else:
                    available[key] = False
            continue
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

    legacy = len(tools) - versioned
    rule = TOOL_PAYLOAD_BYTE_MIXED_RULE if versioned and legacy else (
        TOOL_PAYLOAD_BYTE_V1_RULE if versioned else TOOL_PAYLOAD_BYTE_RULE
    )
    result = {
        "status": status,
        "rule": rule,
        "matchedObservations": matched,
        "examinedObservations": len(tools),
    }
    if versioned:
        result.update(versionedObservations=versioned, truncatedPayloads=truncated)
    return input_bytes, output_bytes, result, gap


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


def _child_trace_health(
    observations: list[dict[str, Any]],
    roots_by_session: dict[str, list[dict[str, Any]]],
    *,
    discovery_complete: bool,
    discovery_since: str | None = None,
    discovery_until: str | None = None,
) -> dict[str, Any]:
    modes = Counter({key: 0 for key in CHILD_TRACE_MODES})
    availability = Counter({key: 0 for key in CHILD_TRACE_AVAILABILITY})
    mismatches = 0
    projections = 0
    for observation in observations:
        if observation.get("name") != "subagent-result":
            continue
        projections += 1
        metadata = observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
        raw_mode = metadata.get("effectiveMode")
        mode = raw_mode if raw_mode in {"agentic", "one-shot"} else "unknown"
        modes[mode] += 1
        child_id = metadata.get("childSessionId")
        if not isinstance(child_id, str) or not child_id or len(child_id) > 200:
            child_id = None
        declared = metadata.get("childTraceAvailability")
        expected = (
            "expected-unavailable" if mode == "one-shot"
            else "expected-available" if mode == "agentic" and child_id
            else "unknown"
        )
        if declared not in {"expected-available", "expected-unavailable", "unknown"}:
            declared = "unknown"
        if declared != expected:
            mismatches += 1
            availability["unknown"] += 1
            continue
        roots = roots_by_session.get(child_id, []) if child_id else []
        root_metadata = roots[0].get("metadata") if len(roots) == 1 else None
        in_window = child_id is not None and _session_starts_within(
            child_id,
            discovery_since,
            discovery_until,
        )
        if len(roots) > 1:
            availability["ambiguous"] += 1
        elif roots and isinstance(root_metadata, dict) and (
            root_metadata.get("completed") is True or root_metadata.get("cancelled") is True
        ):
            availability["available"] += 1
        elif roots:
            availability["incomplete"] += 1
        elif discovery_complete and mode == "one-shot" and in_window:
            availability["expected-unavailable"] += 1
        elif (
            discovery_complete
            and mode == "agentic"
            and in_window
            and metadata.get("executionOutcome") == "succeeded"
        ):
            availability["missing"] += 1
        else:
            availability["unknown"] += 1
    return {
        "schemaVersion": 1,
        "projections": projections,
        "byMode": {key: modes[key] for key in CHILD_TRACE_MODES},
        "byAvailability": {key: availability[key] for key in CHILD_TRACE_AVAILABILITY},
        "declarationMismatches": mismatches,
    }


def _limit_termination_health(observations: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = Counter({key: 0 for key in LIMIT_TERMINATION_REASONS})
    projections = observed = complete = 0
    for observation in observations:
        if observation.get("name") != "subagent-result":
            continue
        projections += 1
        metadata = observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
        reason = metadata.get("terminationReason")
        if not isinstance(reason, str) or reason not in reasons:
            continue
        observed += 1
        reasons[reason] += 1
        source = metadata.get("terminationSource")
        limit = metadata.get("terminationLimit")
        measured = metadata.get("terminationObserved")
        usage_state = metadata.get("terminationUsageState")
        if (
            _nonempty_text(source)
            and type(limit) in {int, float}
            and math.isfinite(limit)
            and limit >= 0
            and type(measured) in {int, float}
            and math.isfinite(measured)
            and measured >= 0
            and usage_state in {"complete", "partial"}
        ):
            complete += 1
    return {
        "projections": projections,
        "observed": observed,
        "completeEvidence": complete,
        "incompleteEvidence": observed - complete,
        "byReason": {key: reasons[key] for key in LIMIT_TERMINATION_REASONS},
    }


def _projection_attribution(
    metadata: dict[str, Any],
    *,
    allowed_providers: set[str],
    allowed_models: set[str],
) -> dict[str, Any]:
    if not PROJECTION_ATTRIBUTION_FIELDS.intersection(metadata):
        return {}

    raw_status = metadata.get("modelDimensionsStatus")
    raw_provider = metadata.get("provider")
    raw_model = metadata.get("model")
    raw_target = metadata.get("target")
    provider = _cohort_dimension(raw_provider)
    model = _cohort_dimension(raw_model)
    target = _cohort_dimension(raw_target)
    syntactic_model_available = (
        raw_status == "available"
        and provider is not None
        and model is not None
        and target == f"{provider}/{model}"
    )
    model_available = (
        syntactic_model_available
        and provider in allowed_providers
        and model in allowed_models
        and target in allowed_models
    )
    model_unavailable = (
        raw_status in {"unavailable", "unavailable-named-agent"}
        and all(value in (None, "") for value in (raw_provider, raw_model, raw_target))
    )
    if model_available:
        result: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "target": target,
            "modelDimensionsStatus": "available",
        }
    elif model_unavailable:
        result = {
            "provider": None,
            "model": None,
            "target": None,
            "modelDimensionsStatus": raw_status,
        }
    elif syntactic_model_available:
        result = {
            "provider": None,
            "model": None,
            "target": None,
            "modelDimensionsStatus": "unavailable",
            "modelDimensionsReason": "unconfigured",
        }
    else:
        result = {
            "provider": None,
            "model": None,
            "target": None,
            "modelDimensionsStatus": "unavailable",
            "modelDimensionsReason": "invalid",
        }

    routing_task = metadata.get("routingTask")
    routing_available = (
        isinstance(routing_task, str)
        and PROJECTION_ROUTING_TASK.fullmatch(routing_task) is not None
        and _cohort_dimension(routing_task) is not None
    )
    result.update({
        "routingTask": routing_task if routing_available else None,
        "routingTaskStatus": "available" if routing_available else "unavailable",
    })

    mode = metadata.get("effectiveMode")
    result.update({
        "effectiveMode": mode if mode in PROJECTION_MODES else "unknown",
        "effectiveModeStatus": "available" if mode in PROJECTION_MODES else "unavailable",
    })

    thinking = metadata.get("thinkingLevel")
    thinking_available = thinking in PROJECTION_THINKING_LEVELS
    result.update({
        "thinkingLevel": thinking if thinking_available else None,
        "thinkingLevelStatus": "available" if thinking_available else "unavailable",
    })

    contract = metadata.get("outputContract")
    contract_available = contract in PROJECTION_OUTPUT_CONTRACTS
    result.update({
        "outputContract": contract if contract_available else "unknown",
        "outputContractStatus": "available" if contract_available else "unavailable",
    })

    elapsed = metadata.get("workerElapsedMs")
    elapsed_valid = type(elapsed) is int and elapsed >= 0
    elapsed_source = metadata.get("workerElapsedSource")
    elapsed_status = metadata.get("workerElapsedStatus")
    timing_available = elapsed_valid and (
        (elapsed_status == "available" and elapsed_source == "progress-summary")
        or (elapsed_status == "fallback" and elapsed_source == "parent-wall")
    )
    result.update({
        "workerElapsedMs": elapsed if timing_available else None,
        "workerElapsedSource": elapsed_source if timing_available else None,
        "workerElapsedStatus": elapsed_status if timing_available else "unavailable",
    })
    return result


def _projection_records(
    observations: list[dict[str, Any]],
    *,
    allowed_providers: set[str],
    allowed_models: set[str],
) -> list[dict[str, Any]]:
    records = []
    for observation in observations:
        if observation.get("name") != "subagent-result":
            continue
        metadata = observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
        record: dict[str, Any] = {}
        for source, target in (
            ("id", "observationId"),
            ("traceId", "traceId"),
            ("parentObservationId", "parentObservationId"),
        ):
            value = observation.get(source)
            if isinstance(value, str) and 0 < len(value) <= 200:
                record[target] = value
        for key in ("invocationId", "childSessionId"):
            value = metadata.get(key)
            if isinstance(value, str) and 0 < len(value) <= 200:
                record[key] = value
        index = metadata.get("index")
        if type(index) is int and index >= 0:
            record["index"] = index
        mode = metadata.get("effectiveMode")
        if mode in {"agentic", "one-shot", "unknown"}:
            record["effectiveMode"] = mode
        availability = metadata.get("childTraceAvailability")
        if availability in {"expected-available", "expected-unavailable", "unknown"}:
            record["childTraceAvailability"] = availability
        record.update(_projection_attribution(
            metadata,
            allowed_providers=allowed_providers,
            allowed_models=allowed_models,
        ))
        for key in ("startTime", "endTime"):
            value = observation.get(key)
            if isinstance(value, str) and 0 < len(value) <= 64:
                record[key] = value
        latency = observation.get("latency")
        if type(latency) in {int, float} and math.isfinite(latency) and latency >= 0:
            record["captureLatencySeconds"] = float(latency)
        records.append(record)
    return records


def _generation_billing_class(generation: dict[str, Any], billing_classes: dict[str, str]) -> str:
    metadata = generation.get("metadata") if isinstance(generation.get("metadata"), dict) else {}

    def dimensions(*values: Any, subscription_suffix: bool = False) -> set[str] | None:
        normalized = set()
        for raw in values:
            if raw in (None, ""):
                continue
            value = _cohort_dimension(raw)
            if value is None:
                return None
            normalized.add(value.removesuffix("-subscription") if subscription_suffix else value)
        return normalized

    providers = dimensions(generation.get("provider"), metadata.get("provider"))
    models = dimensions(generation.get("model"), metadata.get("model"), subscription_suffix=True)
    if providers is None or models is None or len(providers) != 1 or len(models) != 1:
        return "unknown"
    provider = next(iter(providers))
    model = next(iter(models))
    target = model if model.startswith(f"{provider}/") else f"{provider}/{model}"
    return billing_classes.get(target, "unknown")


def _generation_price_known(generation: dict[str, Any], billing_class: str) -> bool:
    if billing_class == "subscription":
        return True
    values = []
    for key in ("calculatedTotalCost", "totalPrice"):
        if key not in generation or generation[key] is None:
            continue
        value = generation[key]
        if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
            return False
        values.append(value)
    if not values:
        return False
    if any(values):
        return True
    usage = _usage_details(generation)
    counts = [_usage_count(usage, key) for key in ("input", "cacheRead", "output")]
    return all(value == 0 for value in counts)


def _features(
    traces: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    *,
    child_trace_roots: dict[str, list[dict[str, Any]]] | None = None,
    trace_discovery_complete: bool = False,
    trace_discovery_since: str | None = None,
    trace_discovery_until: str | None = None,
    billing_classes: dict[str, str] | None = None,
    allowed_providers: set[str] | None = None,
    allowed_models: set[str] | None = None,
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

    token_totals = {"freshInput": 0, "cacheRead": 0, "output": 0}
    token_available = {key: True for key in token_totals}
    cost = marginal_cost = 0.0
    billing_counts = Counter({key: 0 for key in ("subscription", "metered", "unknown")})
    unknown_cost_generations = 0
    instruction_bytes = tool_bytes = input_bytes = 0
    prompt_parts = []
    providers = set()
    models = set()
    missing_usage = False
    invalid_provider = False
    invalid_model = False

    def add_provider(raw: Any) -> None:
        nonlocal invalid_provider
        if raw is None or raw == "":
            return
        if provider := _cohort_dimension(raw):
            providers.add(provider)
        else:
            invalid_provider = True

    def add_model(raw: Any, *, preserve: bool = False) -> None:
        nonlocal invalid_model
        if raw is None or raw == "":
            return
        if preserve:
            models.add(str(raw))
        if model := _cohort_dimension(raw):
            models.add(model)
        else:
            invalid_model = True

    for generation in generations:
        usage = _usage_details(generation)
        for source, target in (("input", "freshInput"), ("cacheRead", "cacheRead"), ("output", "output")):
            value = _usage_count(usage, source)
            if value is None:
                token_available[target] = False
                missing_usage = True
            else:
                token_totals[target] += value
        nominal = _number(generation.get("calculatedTotalCost") or generation.get("totalPrice"))
        cost += nominal
        billing_class = _generation_billing_class(generation, billing_classes or {})
        billing_counts[billing_class] += 1
        if billing_class == "unknown" or not _generation_price_known(generation, billing_class):
            unknown_cost_generations += 1
        elif billing_class == "metered":
            marginal_cost += nominal
        metadata = generation.get("metadata") if isinstance(generation.get("metadata"), dict) else {}
        for raw_provider in (generation.get("provider"), metadata.get("provider")):
            add_provider(raw_provider)
        add_model(generation.get("model"), preserve=True)
        add_model(metadata.get("model"))
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
        metadata = trace.get("metadata") if isinstance(trace.get("metadata"), dict) else {}
        add_provider(metadata.get("provider"))
        add_model(metadata.get("model"), preserve=True)
    for observation in observations:
        metadata = observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
        add_provider(metadata.get("provider"))
        add_model(metadata.get("model"))

    tool_input_bytes, tool_output_bytes, tool_payload_metadata, tool_payload_gap = _tool_payload_bytes(tools)
    child_trace_health = _child_trace_health(
        observations,
        child_trace_roots or {},
        discovery_complete=trace_discovery_complete,
        discovery_since=trace_discovery_since,
        discovery_until=trace_discovery_until,
    )
    signatures = Counter()
    evaluator_timeouts = 0
    for observation in observations:
        metadata = observation.get("metadata") or {}
        is_error = bool((isinstance(metadata, dict) and metadata.get("isError")) or observation.get("level") == "ERROR")
        if is_error:
            signatures[_hash(observation.get("statusMessage") or observation.get("output") or observation.get("name"))] += 1
            if "evaluator" in str(observation.get("name") or "").lower():
                evaluator_timeouts += 1

    projections = _projection_records(
        observations,
        allowed_providers=allowed_providers or set(),
        allowed_models=allowed_models or set(),
    )
    projections_by_observation: dict[str, list[dict[str, Any]]] = {}
    for projection in projections:
        projection["evaluatorLinkStatus"] = "unavailable"
        observation_id = projection.get("observationId")
        if isinstance(observation_id, str):
            projections_by_observation.setdefault(observation_id, []).append(projection)

    def projection_link(score: dict[str, Any]) -> tuple[str, str | None, list[dict[str, Any]]]:
        candidates = set()
        observation_id = score.get("observationId")
        if isinstance(observation_id, str) and 0 < len(observation_id) <= 200:
            candidates.add(observation_id)
        subject = score.get("subject")
        if isinstance(subject, dict) and subject.get("kind") == "observation":
            subject_id = subject.get("id")
            if isinstance(subject_id, str) and 0 < len(subject_id) <= 200:
                candidates.add(subject_id)
        if len(candidates) != 1:
            return ("ambiguous" if len(candidates) > 1 else "unavailable", None, [])
        linked_id = next(iter(candidates))
        matches = projections_by_observation.get(linked_id, [])
        if len(matches) == 1:
            return "linked", linked_id, matches
        return ("ambiguous" if len(matches) > 1 else "unavailable", None, matches)

    evaluator_outcomes = []
    explicit_candidates = []
    apparent_candidates = []
    for index, score in enumerate(scores):
        score_name = str(score.get("name") or "")
        if score.get("source") != "EVAL" and "outcome" not in score_name.lower():
            continue
        item = {key: score.get(key) for key in ("name", "value", "dataType", "source") if score.get(key) is not None}
        if projections:
            link_status, linked_id, matches = projection_link(score)
            item["projectionLinkStatus"] = link_status
            if linked_id is not None:
                item["projectionObservationId"] = linked_id
            for projection in matches:
                if link_status == "ambiguous" or projection["evaluatorLinkStatus"] != "ambiguous":
                    projection["evaluatorLinkStatus"] = link_status
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
    if not providers:
        capture_gaps.append("missing-provider")
    if invalid_provider:
        capture_gaps.append("invalid-provider")
    if not models:
        capture_gaps.append("missing-model")
    if invalid_model:
        capture_gaps.append("invalid-model")
    if final_outcome == "unknown":
        capture_gaps.append("missing-outcome")
    if tool_payload_gap:
        capture_gaps.append(tool_payload_gap)
    for state, gap in (
        ("missing", "missing-child-trace"),
        ("ambiguous", "ambiguous-child-trace"),
        ("incomplete", "incomplete-child-trace"),
        ("unknown", "unknown-child-trace"),
    ):
        if child_trace_health["byAvailability"][state]:
            capture_gaps.append(gap)
    if child_trace_health["declarationMismatches"]:
        capture_gaps.append("invalid-child-trace-declaration")

    release_available = any(
        _nonempty_text(trace.get("release"))
        or (
            isinstance(trace.get("metadata"), dict)
            and _nonempty_text(trace["metadata"].get("release"))
        )
        for trace in traces
    )
    source_revision_available = any(
        isinstance(trace.get("metadata"), dict)
        and any(
            _nonempty_text(trace["metadata"].get(key))
            for key in ("vcs.ref.head.revision", "git_commit")
        )
        for trace in traces
    )

    return {
        "executionOutcome": execution_outcome,
        "apparentOutcome": apparent_outcome,
        "finalOutcome": final_outcome,
        "finalOutcomeSource": final_outcome_source,
        "toolCalls": tool_calls,
        "toolErrors": tool_errors,
        "turns": turns,
        "latencySeconds": sum(_number(trace.get("latency")) for trace in traces),
        "tokens": {
            key: value if token_available[key] or not generations else None
            for key, value in token_totals.items()
        },
        "cost": round(cost, 10),
        "costAccounting": {
            "schemaVersion": 1,
            "nominalUsd": round(cost, 10),
            "marginalUsd": round(marginal_cost, 10)
            if generations and unknown_cost_generations == 0 else None,
            "observedGenerations": len(generations),
            "unknownGenerations": unknown_cost_generations,
            "byBillingClass": {key: billing_counts[key] for key in ("subscription", "metered", "unknown")},
        },
        "payloadBytes": {
            "instructions": instruction_bytes,
            "tools": tool_bytes,
            "input": input_bytes,
            "toolInput": tool_input_bytes,
            "toolOutput": tool_output_bytes,
        },
        "payloadByteMetadata": {"toolIo": tool_payload_metadata},
        "providers": sorted(providers),
        "models": sorted(models),
        "promptHash": _hash(prompt_parts),
        "evaluatorOutcomes": evaluator_outcomes,
        "evaluatorTimeouts": evaluator_timeouts,
        "errorSignatures": [{"hash": key, "count": count} for key, count in sorted(signatures.items())],
        "toolErrorSignals": _tool_error_signals(observations),
        "errorTaxonomy": _error_taxonomy(observations),
        "childTraceHealth": child_trace_health,
        "projections": projections,
        "provenanceCoverage": {
            "releaseAvailable": release_available,
            "sourceRevisionAvailable": source_revision_available,
        },
        "limitTerminations": _limit_termination_health(observations),
        "captureGaps": capture_gaps,
    }


def _cohort_costs(features: list[dict[str, Any]], *, cohort_lower_bound: bool) -> dict[str, Any]:
    nominal = marginal = 0.0
    known_sessions = unknown_sessions = nonzero_sessions = observed_generations = 0
    billing_counts = Counter({key: 0 for key in ("subscription", "metered", "unknown")})
    for feature in features:
        accounting = feature.get("costAccounting") if isinstance(feature.get("costAccounting"), dict) else {}
        raw_nominal = accounting.get("nominalUsd", feature.get("cost"))
        if type(raw_nominal) in {int, float} and raw_nominal >= 0:
            nominal += float(raw_nominal)
        observed = accounting.get("observedGenerations")
        unknown = accounting.get("unknownGenerations")
        marginal_value = accounting.get("marginalUsd")
        complete = (
            accounting.get("schemaVersion") == 1
            and type(observed) is int
            and observed > 0
            and type(unknown) is int
            and unknown == 0
            and type(marginal_value) in {int, float}
            and marginal_value >= 0
        )
        if complete:
            known_sessions += 1
            marginal += float(marginal_value)
            nonzero_sessions += int(marginal_value > 0)
        else:
            unknown_sessions += 1
        if type(observed) is int and observed >= 0:
            observed_generations += observed
        values = accounting.get("byBillingClass") if isinstance(accounting.get("byBillingClass"), dict) else {}
        for key in billing_counts:
            value = values.get(key)
            if type(value) is int and value >= 0:
                billing_counts[key] += value
    return {
        "schemaVersion": 1,
        "nominalUsd": round(nominal, 10),
        "marginalUsd": round(marginal, 10),
        "marginalLowerBound": cohort_lower_bound or unknown_sessions > 0,
        "knownMarginalSessions": known_sessions,
        "unknownMarginalSessions": unknown_sessions,
        "nonzeroMarginalSessions": nonzero_sessions,
        "observedGenerations": observed_generations,
        "byBillingClass": {key: billing_counts[key] for key in ("subscription", "metered", "unknown")},
    }


def _cohort_health(
    sessions: list[dict[str, Any]],
    *,
    trace_discovery: dict[str, Any],
    scan_limit: int,
    eligible_session_count: int,
    allowed_providers: set[str],
    allowed_models: set[str],
) -> dict[str, Any]:
    features = [item.get("features") if isinstance(item.get("features"), dict) else {} for item in sessions]
    outcomes = Counter({key: 0 for key in COHORT_OUTCOMES})

    def outcome(feature: dict[str, Any]) -> str:
        value = feature.get("finalOutcome")
        return value if value in COHORT_OUTCOMES else "unknown"

    def dimension_outcomes(
        field: str,
        label_field: str,
        invalid_gap: str,
        allowlist: set[str],
    ) -> tuple[list[dict[str, Any]], int]:
        rows: dict[str, Counter[str]] = {}
        unknown = 0
        for feature in features:
            raw_values = feature.get(field)
            values = raw_values if isinstance(raw_values, list) else []
            labels = sorted({
                label
                for value in values
                if (label := _cohort_dimension(value)) and label in allowlist
            })
            gaps = feature.get("captureGaps") if isinstance(feature.get("captureGaps"), list) else []
            invalid = any(
                value not in (None, "")
                and ((label := _cohort_dimension(value)) is None or label not in allowlist)
                for value in values
            )
            if not labels or invalid or invalid_gap in gaps:
                unknown += 1
            for label in labels:
                counts = rows.setdefault(label, Counter({key: 0 for key in COHORT_OUTCOMES}))
                counts[outcome(feature)] += 1
        return [
            {
                label_field: label,
                "sessions": sum(rows[label].values()),
                "outcomes": {key: rows[label][key] for key in COHORT_OUTCOMES},
            }
            for label in sorted(rows)
        ], unknown

    for feature in features:
        outcomes[outcome(feature)] += 1
    provider_outcomes, unknown_provider_sessions = dimension_outcomes(
        "providers", "provider", "invalid-provider", allowed_providers
    )
    model_outcomes, unknown_model_sessions = dimension_outcomes(
        "models", "model", "invalid-model", allowed_models
    )

    evaluator_records = 0
    evaluator_timeouts = 0
    sessions_with_outcomes = 0
    sessions_with_timeouts = 0
    error_scalars = (
        "rawErrorObservationCount",
        "unclassifiedRawErrorObservationCount",
        "classifiedSignals",
        "actionableSignals",
        "nonActionableSignals",
        "unknownSignals",
    )
    errors: dict[str, Any] = {key: 0 for key in error_scalars}
    errors["byClass"] = {key: 0 for key in ERROR_CLASSES}
    errors["bySource"] = {key: 0 for key in ERROR_SOURCES}
    errors["outcomeBlocking"] = {key: 0 for key in ("true", "false", "unknown")}
    capture_gaps = {key: 0 for key in COHORT_CAPTURE_GAPS}
    child_trace_modes = Counter({key: 0 for key in CHILD_TRACE_MODES})
    child_trace_availability = Counter({key: 0 for key in CHILD_TRACE_AVAILABILITY})
    child_trace_projections = 0
    child_trace_declaration_mismatches = 0

    for feature in features:
        raw_outcomes = feature.get("evaluatorOutcomes")
        records = raw_outcomes if isinstance(raw_outcomes, list) else []
        evaluator_records += len(records)
        sessions_with_outcomes += int(bool(records))
        timeouts = max(0, _int(feature.get("evaluatorTimeouts")))
        evaluator_timeouts += timeouts
        sessions_with_timeouts += int(timeouts > 0)

        taxonomy = feature.get("errorTaxonomy") if isinstance(feature.get("errorTaxonomy"), dict) else {}
        for key in error_scalars:
            errors[key] += max(0, _int(taxonomy.get(key)))
        for group, keys in (
            ("byClass", ERROR_CLASSES),
            ("bySource", ERROR_SOURCES),
            ("outcomeBlocking", ("true", "false", "unknown")),
        ):
            values = taxonomy.get(group) if isinstance(taxonomy.get(group), dict) else {}
            for key in keys:
                errors[group][key] += max(0, _int(values.get(key)))

        gaps = feature.get("captureGaps") if isinstance(feature.get("captureGaps"), list) else []
        for gap in set(gaps):
            if gap in capture_gaps:
                capture_gaps[gap] += 1

        child_traces = feature.get("childTraceHealth") if isinstance(feature.get("childTraceHealth"), dict) else {}
        child_trace_projections += max(0, _int(child_traces.get("projections")))
        child_trace_declaration_mismatches += max(0, _int(child_traces.get("declarationMismatches")))
        for field, target, keys in (
            ("byMode", child_trace_modes, CHILD_TRACE_MODES),
            ("byAvailability", child_trace_availability, CHILD_TRACE_AVAILABILITY),
        ):
            values = child_traces.get(field) if isinstance(child_traces.get(field), dict) else {}
            for key in keys:
                target[key] += max(0, _int(values.get(key)))

    lifecycle_outcomes = Counter({key: 0 for key in ("succeeded", "failed", "unavailable", "unknown")})
    usage_coverage = {
        key: {"availableSessions": 0, "missingSessions": 0, "zeroSessions": 0}
        for key in ("freshInput", "cacheRead", "output")
    }
    provenance_coverage = {
        key: {"availableSessions": 0, "missingSessions": 0}
        for key in ("release", "sourceRevision")
    }
    payload_statuses = Counter({key: 0 for key in PAYLOAD_BYTE_STATUSES})
    tool_input_zero = tool_output_zero = 0
    limit_terminations = {
        "projections": 0,
        "observed": 0,
        "completeEvidence": 0,
        "incompleteEvidence": 0,
        "byReason": Counter({key: 0 for key in LIMIT_TERMINATION_REASONS}),
    }
    for feature in features:
        execution = feature.get("executionOutcome")
        lifecycle_outcomes[execution if execution in lifecycle_outcomes else "unknown"] += 1
        gaps = feature.get("captureGaps") if isinstance(feature.get("captureGaps"), list) else []
        tokens = feature.get("tokens") if isinstance(feature.get("tokens"), dict) else {}
        for key, counts in usage_coverage.items():
            value = tokens.get(key)
            available = "no-generations" not in gaps and type(value) is int and value >= 0
            counts["availableSessions" if available else "missingSessions"] += 1
            counts["zeroSessions"] += int(available and value == 0)
        provenance = feature.get("provenanceCoverage") if isinstance(feature.get("provenanceCoverage"), dict) else {}
        for key, source_key in (("release", "releaseAvailable"), ("sourceRevision", "sourceRevisionAvailable")):
            provenance_coverage[key]["availableSessions" if provenance.get(source_key) is True else "missingSessions"] += 1
        payload_metadata = feature.get("payloadByteMetadata") if isinstance(feature.get("payloadByteMetadata"), dict) else {}
        tool_io = payload_metadata.get("toolIo") if isinstance(payload_metadata.get("toolIo"), dict) else {}
        status = tool_io.get("status")
        payload_statuses[status if status in payload_statuses else "unavailable"] += 1
        payload_bytes = feature.get("payloadBytes") if isinstance(feature.get("payloadBytes"), dict) else {}
        tool_input_zero += int(status == "available" and payload_bytes.get("toolInput") == 0)
        tool_output_zero += int(status == "available" and payload_bytes.get("toolOutput") == 0)
        termination = feature.get("limitTerminations") if isinstance(feature.get("limitTerminations"), dict) else {}
        for key in ("projections", "observed", "completeEvidence", "incompleteEvidence"):
            limit_terminations[key] += max(0, _int(termination.get(key)))
        reasons = termination.get("byReason") if isinstance(termination.get("byReason"), dict) else {}
        for key in LIMIT_TERMINATION_REASONS:
            limit_terminations["byReason"][key] += max(0, _int(reasons.get(key)))

    continuation = trace_discovery.get("continuation") if isinstance(trace_discovery.get("continuation"), dict) else {}
    discovery_complete = trace_discovery.get("complete") is True
    discovery_has_more = continuation.get("hasMore") is True
    eligible_available = max(len(sessions), _int(eligible_session_count))
    session_limit_reached = eligible_available > len(sessions)
    lower_bound = (
        not discovery_complete
        or trace_discovery.get("sessionClassificationComplete", True) is not True
        or session_limit_reached
        or capture_gaps["trace-limit"] > 0
        or capture_gaps["observation-limit"] > 0
        or capture_gaps["score-limit"] > 0
    )
    return {
        "schemaVersion": 1,
        "observedSessions": len(sessions),
        "outcomes": {key: outcomes[key] for key in COHORT_OUTCOMES},
        "providerOutcomes": provider_outcomes,
        "unknownProviderSessions": unknown_provider_sessions,
        "modelOutcomes": model_outcomes,
        "unknownModelSessions": unknown_model_sessions,
        "costs": _cohort_costs(features, cohort_lower_bound=lower_bound),
        "lifecycleCoverage": {
            "availableSessions": len(features) - lifecycle_outcomes["unknown"],
            "missingSessions": lifecycle_outcomes["unknown"],
            "byExecutionOutcome": {key: lifecycle_outcomes[key] for key in lifecycle_outcomes},
        },
        "usageCoverage": usage_coverage,
        "provenanceCoverage": provenance_coverage,
        "payloadByteCoverage": {
            "byStatus": {key: payload_statuses[key] for key in PAYLOAD_BYTE_STATUSES},
            "toolInputZeroSessions": tool_input_zero,
            "toolOutputZeroSessions": tool_output_zero,
        },
        "limitTerminations": {
            **{key: limit_terminations[key] for key in ("projections", "observed", "completeEvidence", "incompleteEvidence")},
            "byReason": {key: limit_terminations["byReason"][key] for key in LIMIT_TERMINATION_REASONS},
        },
        "evaluatorCoverage": {
            "sessionsWithOutcomes": sessions_with_outcomes,
            "sessionsWithoutOutcomes": len(sessions) - sessions_with_outcomes,
            "outcomeRecords": evaluator_records,
            "sessionsWithTimeouts": sessions_with_timeouts,
            "timeouts": evaluator_timeouts,
        },
        "childTraces": {
            "schemaVersion": 1,
            "projections": child_trace_projections,
            "byMode": {key: child_trace_modes[key] for key in CHILD_TRACE_MODES},
            "byAvailability": {key: child_trace_availability[key] for key in CHILD_TRACE_AVAILABILITY},
            "declarationMismatches": child_trace_declaration_mismatches,
        },
        "errors": errors,
        "captureGaps": capture_gaps,
        "completeness": {
            "eligibleSessionsAvailable": eligible_available,
            "traceDiscoveryComplete": discovery_complete,
            "traceDiscoveryHasMore": discovery_has_more,
            "sessionLimitReached": session_limit_reached,
            "lowerBound": lower_bound,
        },
        "limits": {
            "scanSessions": scan_limit,
            "discoveryTraces": max(0, _int(trace_discovery.get("maxTraces"))),
            "discoveryPageSize": MAX_PAGE_SIZE,
            "tracesPerSession": MAX_TRACES_PER_SESSION,
            "observationsPerTrace": OBSERVATIONS_PER_TRACE,
            "scoresPerQuery": SCORES_PER_QUERY,
        },
    }


def _run_context_shape(invocation: dict[str, Any]) -> str | None:
    shape: dict[str, Any] = {}
    for field in ("sessionPolicy", "memoryPolicy", "outputContract"):
        value = invocation.get(field)
        if dimension := _cohort_dimension(value):
            shape[field] = dimension
    skills = invocation.get("effectiveSkills")
    if isinstance(skills, list):
        normalized = sorted({item for item in (_cohort_dimension(value) for value in skills) if item})
        if normalized:
            shape["skills"] = normalized
    refs = invocation.get("inputRefs")
    if isinstance(refs, list):
        kinds = sorted({
            value.partition(":")[0]
            for value in refs
            if isinstance(value, str) and ":" in value and _cohort_dimension(value.partition(":")[0])
        })
        if kinds:
            shape["inputKinds"] = kinds
    return _hash(shape) if shape else None


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
                correlation = {
                    "status": "linked",
                    "runId": run_id,
                    "beadId": invocation.get("bead"),
                    "bundle": str(bundle),
                }
                dispatch_policy = invocation.get("dispatchPolicy")
                provenance = invocation.get("provenance")
                claim_context = provenance.get("claimContext") if isinstance(provenance, dict) else None
                policy_fingerprint = (
                    claim_context.get("policyFingerprint")
                    if isinstance(claim_context, dict)
                    else None
                )
                effects = invocation.get("allowedEffects")
                normalized_effects = (
                    sorted({
                        item for item in (_cohort_dimension(value) for value in effects)
                        if item
                    })
                    if isinstance(effects, list)
                    else []
                )
                dimensions = {
                    "routingTask": invocation.get("routingTask"),
                    "role": invocation.get("effectiveRole") or invocation.get("role"),
                    "risk": dispatch_policy.get("risk") if isinstance(dispatch_policy, dict) else None,
                    "startedAt": invocation.get("createdAt"),
                    "contextShape": _run_context_shape(invocation),
                    "model": invocation.get("selectedModel") or invocation.get("model"),
                    "policyFingerprint": (
                        policy_fingerprint
                        if isinstance(policy_fingerprint, str) and SHA256_REF.fullmatch(policy_fingerprint)
                        else None
                    ),
                }
                correlation.update({
                    key: value
                    for key, value in dimensions.items()
                    if isinstance(value, str) and value
                })
                if isinstance(effects, list) and normalized_effects and len(normalized_effects) == len(effects):
                    correlation["effects"] = normalized_effects
                return correlation
    return _score_work_correlation(session_id, scores or [])


def _score_work_correlation(session_id: str, scores: list[dict[str, Any]]) -> dict[str, Any]:
    canonical_scores = _canonical_score_rows(scores, _work_link_score_id(session_id))
    owners = set()
    for score in canonical_scores:
        metadata = score.get("metadata")
        bead_id = metadata.get("beadId") if isinstance(metadata, dict) else None
        if score.get("value") != "linked" or not isinstance(bead_id, str) or not BEAD_ID.fullmatch(bead_id):
            return {"status": "unlinked"}
        owners.add(bead_id)
    if len(owners) == 1:
        return {"status": "linked", "beadId": next(iter(owners))}
    return {"status": "unlinked"}


def _correlated_outcome_scores(
    session_id: str,
    correlation: dict[str, Any],
    scores: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    expected = correlation.get("beadId") if correlation.get("status") == "linked" else None
    accepted = []
    mismatched = False
    for score in _canonical_score_rows(scores, _outcome_score_id(session_id)):
        metadata = score.get("metadata")
        owner = metadata.get("beadId") if isinstance(metadata, dict) else None
        if not isinstance(expected, str) or owner != expected:
            mismatched = True
            continue
        accepted.append(score if score.get("name") else {**score, "name": OUTCOME_SCORE})
    return accepted, mismatched


def _work_link_score_id(session_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:agnt:improvement-work-item:{session_id}"))


def _outcome_score_id(session_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:agnt:improvement-task-outcome:{session_id}"))


def _canonical_score_rows(rows: list[dict[str, Any]], score_id: str) -> list[dict[str, Any]]:
    identified = [row for row in rows if isinstance(row.get("id"), str)]
    return [row for row in identified if row["id"] == score_id] if identified else rows


def _project_session_link(client: Any, *, session_id: str, bead_id: str) -> None:
    client.put_session_score(
        score_id=_work_link_score_id(session_id),
        session_id=session_id,
        name=WORK_LINK_SCORE,
        value="linked",
        data_type="CATEGORICAL",
        metadata={"schemaVersion": 1, "beadId": bead_id},
    )


def _project_session_outcome(
    client: Any,
    *,
    session_id: str,
    bead_id: str,
    outcome: str,
) -> None:
    _project_session_link(client, session_id=session_id, bead_id=bead_id)
    client.put_session_score(
        score_id=_outcome_score_id(session_id),
        session_id=session_id,
        name=OUTCOME_SCORE,
        value=outcome,
        data_type="CATEGORICAL",
        metadata={"schemaVersion": 1, "beadId": bead_id},
    )


def _best_effort_projection(summary: dict[str, Any], project: Any) -> dict[str, Any]:
    try:
        project(_client_from_env())
    except Exception:
        return {**summary, "evidenceGaps": ["langfuse-projection-unavailable"]}
    return summary


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


def _write_review_assignment(output_dir: Path, assignment: dict[str, Any]) -> Path:
    return _write_private_json(
        output_dir,
        f"review-assignment-{assignment['assignmentId']}.json",
        assignment,
    )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _require_fields(
    value: Any,
    fields: set[str],
    name: str,
    *,
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    unknown = set(value) - fields - (optional or set())
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
            if isinstance(value, list):
                if not part.isdigit():
                    raise ValueError
                value = value[int(part)]
            else:
                value = value[part]
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


def _improvement_evidence_ref(packet: dict[str, Any], session_index: int) -> dict[str, Any]:
    report_id = packet.get("reportId")
    return validate_evidence_ref({
        "ref": f"artifact:improvement-{report_id}-session-{session_index}",
        "source": "improvement-scan",
        "availability": "available",
        "provenance": f"improvement:{report_id}:session-{session_index}",
        "integrity": "verified",
        "sensitivity": "private",
        "retention": "cohort",
    })


def _outcome_proof(features: dict[str, Any], evidence_ref: dict[str, Any]) -> dict[str, Any]:
    outcome = features.get("finalOutcome")
    source = features.get("finalOutcomeSource")
    status = "available"
    reason = outcome
    if outcome == "unclear":
        status = "unavailable"
        terminations = features.get("limitTerminations")
        by_reason = terminations.get("byReason") if isinstance(terminations, dict) else {}
        reason = next(
            (key for key in LIMIT_TERMINATION_REASONS if _int(by_reason.get(key)) > 0),
            "execution-unavailable",
        )
    elif outcome == "unknown" or source == "unknown":
        status = "unavailable"
        source = "capture-gap"
        gaps = features.get("captureGaps") if isinstance(features.get("captureGaps"), list) else []
        reason = "missing-outcome" if "missing-outcome" in gaps else "outcome-unknown"
    return {
        "status": status,
        "source": source,
        "reason": reason,
        "integrity": evidence_ref["integrity"],
        "evidenceRef": evidence_ref,
    }


def _packet_evidence_refs(packet: dict[str, Any]) -> list[dict[str, Any]]:
    if packet.get("schemaVersion") not in {1, 2, 3}:
        raise ValueError("private packet schemaVersion is unsupported")
    sessions = packet.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("private packet sessions are invalid")
    refs = []
    for index, session in enumerate(sessions):
        if not isinstance(session, dict):
            raise ValueError("private packet sessions are invalid")
        expected = _improvement_evidence_ref(packet, index)
        if packet["schemaVersion"] == 3 and session.get("evidenceRef") != expected:
            raise ValueError("private packet evidence reference is invalid")
        refs.append(expected)
    return refs


def review_assignment(packet: dict[str, Any]) -> dict[str, Any]:
    if (
        packet.get("schemaVersion") != 3
        or packet.get("scan", {}).get("reviewPolicyVersion") != REVIEW_POLICY_VERSION
    ):
        raise ValueError("review assignment requires a current private packet")
    refs = _packet_evidence_refs(packet)
    if not refs or len(refs) > MAX_REVIEW_ASSIGNMENT_ITEMS:
        raise ValueError("review assignment session scope is invalid")
    return build_review_assignment(
        activity="work-learning",
        action=assignment_action_contract("review"),
        scope={
            "kind": "improvement-session-cohort",
            "id": packet.get("reportId"),
            "itemCount": len(refs),
            "maxItems": MAX_REVIEW_ASSIGNMENT_ITEMS,
        },
        evidence_refs=refs,
        rubric={
            "path": "pi/agent/langfuse/improvement-review.md",
            "version": REVIEW_POLICY_VERSION,
        },
    )


def review_gap_result(packet: dict[str, Any], review_status: str) -> dict[str, Any]:
    gap = REVIEW_STATUS_GAPS.get(review_status)
    if gap is None:
        raise ValueError("review status is unsupported")
    assignment = review_assignment(packet)
    return {
        "schemaVersion": 1,
        "assignmentId": assignment["assignmentId"],
        "reviewStatus": review_status,
        "route": "human",
        "gaps": [gap],
        "attempt": 1,
        "reportId": packet["reportId"],
        "reviewPolicyVersion": REVIEW_POLICY_VERSION,
        "reviewedAt": packet["createdAt"],
        "sessions": [],
    }


def _legacy_improvement_finding(
    packet: dict[str, Any],
    raw_finding: Any,
    *,
    packet_refs: list[dict[str, Any]],
    name: str,
) -> dict[str, Any]:
    finding = _require_fields(
        raw_finding,
        LEGACY_FINDING_FIELDS,
        name,
        optional={"relatedFindingId"},
    )
    if not isinstance(finding["findingId"], str) or not IMPROVEMENT_FINDING_ID.fullmatch(finding["findingId"]):
        raise ValueError("findingId must match finding-<12 lowercase hex>")
    evidence_refs = []
    for pointer in _require_strings(finding["evidenceRefs"], "evidenceRefs"):
        _pointer(packet, pointer)
        try:
            session_index = int(pointer.split("/", 3)[2])
            evidence_ref = packet_refs[session_index]
        except (IndexError, ValueError) as exc:
            raise ValueError("evidence reference must point inside packet sessions") from exc
        if evidence_ref not in evidence_refs:
            evidence_refs.append(evidence_ref)
    public = _require_fields(finding["public"], PUBLIC_FIELDS, "public")
    return {
        "schemaVersion": 1,
        "id": finding["findingId"],
        "activity": "work-learning",
        "source": "improvement-review",
        "category": finding["category"],
        "severity": finding["impact"],
        "claim": public["aggregate"],
        "status": "confirmed",
        "evidenceRefs": evidence_refs,
        "verification": {"method": "inspection", "evidenceRefs": evidence_refs},
        "proposedIntervention": public["proposedIntervention"],
        "errorRelevance": finding["errorRelevance"],
        "attribution": finding["attribution"],
        "confidence": finding["confidence"],
        "evidenceStage": "unknown",
        "interventionType": finding["proposedIntervention"],
        "public": public,
        **(
            {"relatedFindingId": finding["relatedFindingId"]}
            if "relatedFindingId" in finding
            else {}
        ),
    }


def _validate_improvement_finding(
    finding: dict[str, Any],
    *,
    finding_categories: set[str],
    packet_refs: list[dict[str, Any]],
    private_strings: set[str],
) -> dict[str, Any]:
    validate_finding(finding)
    finding_id = finding["id"]
    if not isinstance(finding_id, str) or not IMPROVEMENT_FINDING_ID.fullmatch(finding_id):
        raise ValueError("finding id must match finding-<12 lowercase hex>")
    if finding["activity"] != "work-learning" or finding["source"] != "improvement-review":
        raise ValueError("improvement finding activity and source are invalid")
    _require_choice(finding["category"], finding_categories, "category")
    _require_choice(finding["severity"], IMPACTS, "severity")
    _require_choice(finding["errorRelevance"], ERROR_RELEVANCE, "errorRelevance")
    _require_choice(finding["attribution"], ATTRIBUTIONS, "attribution")
    _require_choice(finding["evidenceStage"], EVIDENCE_STAGES, "evidenceStage")
    _require_choice(finding["interventionType"], INTERVENTIONS, "interventionType")
    confidence = finding["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if any(ref not in packet_refs for ref in finding["evidenceRefs"]):
        raise PrivateReviewUnsafe("improvement finding must cite private packet evidence")
    related_finding_id = finding.get("relatedFindingId")
    if related_finding_id is not None and (
        not isinstance(related_finding_id, str)
        or not IMPROVEMENT_FINDING_ID.fullmatch(related_finding_id)
        or related_finding_id == finding_id
    ):
        raise ValueError("relatedFindingId must identify a different monitored finding")
    public = _require_fields(finding["public"], PUBLIC_FIELDS, "public")
    _require_strings(public["affectedPaths"], "public.affectedPaths")
    _require_strings(public["acceptanceCriteria"], "public.acceptanceCriteria")
    for name in ("title", "aggregate", "proposedIntervention", "evaluationRequirement"):
        if not isinstance(public[name], str) or not public[name].strip():
            raise ValueError(f"public.{name} must be non-empty")
    if finding["proposedIntervention"] != public["proposedIntervention"]:
        raise ValueError("public and private proposed interventions do not match")
    for text in _public_strings(public):
        normalized = _normalized_text(text)
        if any(private in normalized for private in private_strings):
            raise PrivateReviewUnsafe("public summary contains copied private packet text")
    return finding


def validate_decisions(packet: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    policy_version = decisions.get("reviewPolicyVersion") if isinstance(decisions, dict) else None
    current = policy_version == REVIEW_POLICY_VERSION
    _require_fields(
        decisions,
        CURRENT_REVIEW_RESULT_FIELDS if current else TOP_DECISION_FIELDS,
        "decisions",
    )
    if decisions["schemaVersion"] != 1:
        raise ValueError("unsupported decision schemaVersion")
    if decisions["reportId"] != packet.get("reportId"):
        raise ValueError("decision reportId does not match packet")
    if policy_version != packet.get("scan", {}).get("reviewPolicyVersion"):
        raise ValueError("decision reviewPolicyVersion does not match packet")
    finding_categories = FINDING_CATEGORIES_BY_POLICY.get(policy_version)
    if finding_categories is None:
        raise ValueError("decision reviewPolicyVersion is unsupported")
    if not isinstance(decisions["reviewedAt"], str):
        raise ValueError("reviewedAt must be an ISO timestamp")
    try:
        datetime.fromisoformat(decisions["reviewedAt"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewedAt must be an ISO timestamp") from exc
    if not isinstance(decisions["sessions"], list):
        raise ValueError("sessions must be a list")

    if current:
        assignment = review_assignment(packet)
        if decisions["assignmentId"] != assignment["assignmentId"]:
            raise ValueError("decision assignmentId does not match packet")
        if decisions["attempt"] != 1 or type(decisions["attempt"]) is not int:
            raise ValueError("review attempt is invalid")
        review_status = decisions["reviewStatus"]
        if review_status == "completed":
            if decisions["route"] != "none" or decisions["gaps"] != []:
                raise ValueError("completed review route or gaps are invalid")
        else:
            expected_gap = REVIEW_STATUS_GAPS.get(review_status)
            if (
                expected_gap is None
                or decisions["route"] != "human"
                or decisions["gaps"] != [expected_gap]
                or decisions["sessions"] != []
            ):
                raise ValueError("incomplete review result is invalid")
            return decisions

    packet_sessions = {
        item.get("sessionId"): item
        for item in packet.get("sessions", [])
        if isinstance(item, dict) and isinstance(item.get("sessionId"), str)
    }
    packet_refs = _packet_evidence_refs(packet)
    private_strings = _packet_strings(packet)
    seen_sessions: set[str] = set()
    seen_findings: set[str] = set()
    normalized_sessions = []
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
        normalized_findings = []
        for finding_index, raw_finding in enumerate(session["findings"]):
            name = f"findings[{finding_index}]"
            if isinstance(raw_finding, dict) and "findingId" in raw_finding:
                if policy_version not in {"v1", "v2"}:
                    raise ValueError("current review policy requires shared findings")
                finding = _legacy_improvement_finding(
                    packet,
                    raw_finding,
                    packet_refs=packet_refs,
                    name=name,
                )
            else:
                finding = _require_fields(
                    raw_finding,
                    set(FINDING_CORE_FIELDS) | IMPROVEMENT_FINDING_EXTENSIONS,
                    name,
                    optional={"relatedFindingId"},
                )
            finding = _validate_improvement_finding(
                finding,
                finding_categories=finding_categories,
                packet_refs=packet_refs,
                private_strings=private_strings,
            )
            if finding["id"] in seen_findings:
                raise ValueError("finding id must be unique")
            seen_findings.add(finding["id"])
            normalized_findings.append(finding)
        normalized_sessions.append({**session, "findings": normalized_findings})
    if current and seen_sessions != set(packet_sessions):
        raise ValueError("current review must cover the exact assigned session scope")
    return {**decisions, "sessions": normalized_sessions}


def _review_score_id(session_id: str, policy_version: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:agnt:improvement-review:{policy_version}:{session_id}"))


def review_sessions(
    client: Any,
    packet: dict[str, Any],
    decisions: dict[str, Any],
    *,
    apply: bool = False,
    state_dir: Path | None = None,
    beads_runner: Any = None,
    tracked_paths: set[str] | None = None,
    correction_revoker: Any = None,
) -> dict[str, Any]:
    current = packet.get("scan", {}).get("reviewPolicyVersion") == REVIEW_POLICY_VERSION
    try:
        validated = validate_decisions(packet, decisions)
    except PrivateReviewUnsafe:
        if not current:
            raise
        validated = review_gap_result(packet, "privacy-uncertain")
    except ValueError:
        if not current:
            raise
        validated = review_gap_result(packet, "schema-invalid")
    if current and validated["reviewStatus"] != "completed":
        return {
            "schemaVersion": 1,
            "status": "needs-human",
            "reviewStatus": validated["reviewStatus"],
            "route": validated["route"],
            "gaps": validated["gaps"],
            "reviewedSessions": 0,
            "findings": 0,
            "scoresWritten": 0,
        }
    findings = sum(len(session["findings"]) for session in validated["sessions"])
    monitoring_enabled = apply and (state_dir is not None or beads_runner is not None)
    if monitoring_enabled:
        if state_dir is None or beads_runner is None:
            raise ValueError("monitoring update requires private state and Beads access")
        _update_monitoring_states(
            packet,
            validated,
            state_dir=state_dir,
            beads_runner=beads_runner,
            persist=False,
            tracked_paths=tracked_paths,
            correction_revoker=correction_revoker,
        )
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
                    "findingIds": [finding["id"] for finding in session["findings"]],
                    "beadIds": _promoted_bead_ids(session, state_dir) if state_dir else [],
                },
            )
            written += 1
    summary = {
        "schemaVersion": 1,
        "status": "applied" if apply else "preview",
        "reviewedSessions": len(validated["sessions"]),
        "findings": findings,
        "scoresWritten": written,
    }
    if current:
        summary["qualityResult"] = normalize_assigned_review_result(
            review_assignment(packet), validated
        )
    if monitoring_enabled:
        monitoring_result = _update_monitoring_states(
            packet,
            validated,
            state_dir=state_dir,
            beads_runner=beads_runner,
            tracked_paths=tracked_paths,
            correction_revoker=correction_revoker,
        )
        summary["monitoring"] = monitoring_result["counts"]
        if monitoring_result["followUp"] is not None:
            summary["followUp"] = monitoring_result["followUp"]
        if monitoring_result["grantRevoked"]:
            summary["grantRevoked"] = True
    return summary


def _safe_public_text(value: str, name: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    if not text or any(not character.isprintable() for character in text) or PRIVATE_PUBLIC_TEXT.search(text):
        raise ValueError(f"public {name} contains private or unsafe text")
    return text


def _public_bead(
    packet: dict[str, Any],
    decisions: dict[str, Any],
    finding_id: str,
    tracked_paths: set[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validated = validate_decisions(packet, decisions)
    match = None
    owner = None
    for session in validated["sessions"]:
        for finding in session["findings"]:
            if finding["id"] == finding_id:
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
    }, owner, validated)


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


def _monitoring_cohort_dimensions(session: dict[str, Any]) -> dict[str, Any]:
    correlation = session.get("correlation") if isinstance(session.get("correlation"), dict) else {}
    features = session.get("features") if isinstance(session.get("features"), dict) else {}
    dimensions: dict[str, Any] = {}
    for source, target in (("routingTask", "task"), ("risk", "risk"), ("role", "role")):
        if value := _cohort_dimension(correlation.get(source)):
            dimensions[target] = value
    for source, target, pattern in (
        ("contextShape", "contextShape", SHA256_HEX),
        ("promptHash", "promptHash", SHA256_HEX),
        ("policyFingerprint", "policyFingerprint", SHA256_REF),
    ):
        owner = features if source == "promptHash" else correlation
        value = owner.get(source)
        if isinstance(value, str) and pattern.fullmatch(value):
            dimensions[target] = value
    models = features.get("models") if isinstance(features.get("models"), list) else []
    if model := _cohort_dimension(correlation.get("model")):
        models = [*models, model]
    normalized_models = sorted({
        value for value in (_cohort_dimension(model) for model in models) if value
    })
    if normalized_models:
        dimensions["models"] = normalized_models
    effects = correlation.get("effects")
    normalized_effects = (
        sorted({value for value in (_cohort_dimension(effect) for effect in effects) if value})
        if isinstance(effects, list)
        else []
    )
    if isinstance(effects, list) and normalized_effects and len(normalized_effects) == len(effects):
        dimensions["effects"] = normalized_effects
    return dimensions


def _monitoring_cohort_key(session: dict[str, Any]) -> str | None:
    dimensions = _monitoring_cohort_dimensions(session)
    return _hash(dimensions) if dimensions else None


def _new_monitoring_state(packet: dict[str, Any], owner: dict[str, Any]) -> dict[str, Any]:
    source = next(
        (
            session
            for session in packet.get("sessions", [])
            if isinstance(session, dict) and session.get("sessionId") == owner.get("sessionId")
        ),
        {},
    )
    dimensions = _monitoring_cohort_dimensions(source)
    return {
        "status": "promoted",
        "cohortKey": _hash(dimensions) if dimensions else None,
        "cohortDimensions": dimensions or None,
        "minimumSamples": MONITORING_MINIMUM_SAMPLES,
        "implementedAt": None,
        "sampleIds": [],
        "recurrentFindingIds": [],
        "followUpTarget": None,
    }


def _promotion_state_path(state_dir: Path, finding_id: str) -> Path:
    return state_dir / f"promotion-{finding_id}.json"


def _valid_monitoring_dimensions(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict) or not value or not set(value).issubset(MONITORING_DIMENSION_FIELDS):
        return False
    for key in ("task", "risk", "role"):
        if key in value and _cohort_dimension(value[key]) != value[key]:
            return False
    for key in ("contextShape", "promptHash"):
        if key in value and (
            not isinstance(value[key], str)
            or not SHA256_HEX.fullmatch(value[key])
        ):
            return False
    if "policyFingerprint" in value and (
        not isinstance(value["policyFingerprint"], str)
        or not SHA256_REF.fullmatch(value["policyFingerprint"])
    ):
        return False
    for key in ("models", "effects"):
        items = value.get(key)
        if key in value and (
            not isinstance(items, list)
            or not items
            or any(not isinstance(item, str) for item in items)
            or items != sorted(items)
            or len(items) != len(set(items))
            or any(_cohort_dimension(item) != item for item in items)
        ):
            return False
    return True


def _valid_monitoring_state(value: Any, *, legacy: bool = False) -> bool:
    expected = LEGACY_MONITORING_FIELDS if legacy else MONITORING_FIELDS
    if not isinstance(value, dict) or set(value) != expected:
        return False
    implemented_at = value.get("implementedAt")
    if implemented_at is not None:
        if not isinstance(implemented_at, str):
            return False
        try:
            datetime.fromisoformat(implemented_at.replace("Z", "+00:00"))
        except ValueError:
            return False
    sample_ids = value.get("sampleIds")
    recurrent_ids = value.get("recurrentFindingIds")
    cohort_key = value.get("cohortKey")
    follow_up = value.get("followUpTarget") if not legacy else None
    return (
        value.get("status") in MONITORING_STATUSES
        and (cohort_key is None or isinstance(cohort_key, str) and bool(SHA256_HEX.fullmatch(cohort_key)))
        and (legacy or _valid_monitoring_dimensions(value.get("cohortDimensions")))
        and (legacy or follow_up is None or isinstance(follow_up, str) and bool(BEAD_ID.fullmatch(follow_up)))
        and type(value.get("minimumSamples")) is int
        and value["minimumSamples"] > 0
        and isinstance(sample_ids, list)
        and len(sample_ids) == len(set(sample_ids))
        and all(isinstance(item, str) and SHA256_HEX.fullmatch(item) for item in sample_ids)
        and isinstance(recurrent_ids, list)
        and len(recurrent_ids) == len(set(recurrent_ids))
        and all(isinstance(item, str) and IMPROVEMENT_FINDING_ID.fullmatch(item) for item in recurrent_ids)
    )


def _load_promotion_state(path: Path, finding_id: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("private promotion state is invalid") from exc
    common_valid = (
        isinstance(value, dict)
        and value.get("findingId") == finding_id
        and isinstance(value.get("beadId"), str)
        and bool(BEAD_ID.fullmatch(value["beadId"]))
        and isinstance(value.get("creationPending"), bool)
        and isinstance(value.get("linkRepairNeeded"), bool)
    )
    schema_version = value.get("schemaVersion") if isinstance(value, dict) else None
    valid = common_valid and (
        (schema_version == 1 and set(value) == PROMOTION_STATE_FIELDS)
        or (
            schema_version in {2, 3}
            and set(value) == MONITORED_PROMOTION_STATE_FIELDS
            and _valid_monitoring_state(value.get("monitoring"), legacy=schema_version == 2)
        )
    )
    if not valid:
        raise ValueError("private promotion state is invalid")
    return value


def _promoted_bead_ids(session: dict[str, Any], state_dir: Path) -> list[str]:
    bead_ids = []
    for finding in session["findings"]:
        finding_id = finding["id"]
        state = _load_promotion_state(_promotion_state_path(state_dir, finding_id), finding_id)
        if state and not state["creationPending"]:
            bead_ids.append(state["beadId"])
    return sorted(set(bead_ids))


def _monitored_promotion_states(state_dir: Path) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    if not state_dir.is_dir():
        return states
    for path in sorted(state_dir.glob("promotion-finding-*.json")):
        finding_id = path.stem.removeprefix("promotion-")
        if not IMPROVEMENT_FINDING_ID.fullmatch(finding_id):
            raise ValueError("private promotion state is invalid")
        state = _load_promotion_state(path, finding_id)
        if state and state.get("schemaVersion") in {2, 3} and not state["creationPending"]:
            states[finding_id] = state
    return states


def _bead_record(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list) and data:
        data = data[0]
    return data if isinstance(data, dict) else None


def _closed_boundary(bead: dict[str, Any]) -> tuple[str, datetime] | None:
    if str(bead.get("status") or "").lower() != "closed":
        return None
    value = bead.get("closed_at") or bead.get("closedAt")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _monitoring_session_time(session: dict[str, Any]) -> datetime | None:
    started = _session_start(str(session.get("sessionId") or ""))
    if started is not None:
        return started
    correlation = session.get("correlation") if isinstance(session.get("correlation"), dict) else {}
    value = correlation.get("startedAt")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _correction_boundary(bead: dict[str, Any], result: Any) -> tuple[str, datetime] | None:
    closed = _closed_boundary(bead)
    if closed is None or not isinstance(result, dict) or result.get("beadId") != bead.get("id"):
        return None
    if result.get("outcome") != "success" or not isinstance(result.get("capturedAt"), str):
        return None
    try:
        result_time = datetime.fromisoformat(result["capturedAt"].replace("Z", "+00:00"))
    except ValueError:
        return None
    if result_time.tzinfo is None:
        result_time = result_time.replace(tzinfo=timezone.utc)
    boundary_time = max(closed[1], result_time.astimezone(timezone.utc))
    return boundary_time.isoformat().replace("+00:00", "Z"), boundary_time


def _complete_monitoring_evidence(packet: dict[str, Any], session: dict[str, Any]) -> bool:
    features = session.get("features") if isinstance(session.get("features"), dict) else {}
    gaps = features.get("captureGaps")
    scan = packet.get("scan") if isinstance(packet.get("scan"), dict) else {}
    health = scan.get("cohortHealth") if isinstance(scan.get("cohortHealth"), dict) else {}
    completeness = health.get("completeness") if isinstance(health.get("completeness"), dict) else {}
    return gaps == [] and completeness.get("lowerBound") is False


def _monitoring_matches(session: dict[str, Any], monitoring: dict[str, Any]) -> bool:
    expected = monitoring.get("cohortDimensions")
    if isinstance(expected, dict) and expected:
        observed = _monitoring_cohort_dimensions(session)
        return all(observed.get(key) == value for key, value in expected.items())
    return (
        monitoring["cohortKey"] is not None
        and _monitoring_cohort_key(session) == monitoring["cohortKey"]
    )


def _upgrade_promotion_state(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("schemaVersion") != 2:
        return state
    return {
        **state,
        "schemaVersion": 3,
        "monitoring": {
            **state["monitoring"],
            "cohortDimensions": None,
            "followUpTarget": None,
        },
    }


def _recurrent_follow_up(
    packet: dict[str, Any],
    decisions: dict[str, Any],
    related_findings: list[dict[str, Any]],
    tracked_paths: set[str],
) -> dict[str, Any]:
    finding = min(related_findings, key=lambda item: item["id"])
    bead, _owner, _validated = _public_bead(
        packet,
        decisions,
        finding["id"],
        tracked_paths,
    )
    work = validate_public_work({
        "title": bead["title"],
        "description": bead["description"],
        "acceptance": bead["acceptance"],
        "labels": ["continuous-improvement", bead["category"], "quality:work-learning"],
    })
    return {"work": work, "target": quality_work_target(work)}


def _update_monitoring_states(
    packet: dict[str, Any],
    decisions: dict[str, Any],
    *,
    state_dir: Path,
    beads_runner: Any,
    persist: bool = True,
    tracked_paths: set[str] | None = None,
    correction_revoker: Any = None,
) -> dict[str, Any]:
    states = _monitored_promotion_states(state_dir)
    related_ids = {
        finding["relatedFindingId"]
        for session in decisions["sessions"]
        for finding in session["findings"]
        if isinstance(finding.get("relatedFindingId"), str)
    }
    unknown_related = related_ids - set(states)
    if unknown_related:
        raise ValueError("relatedFindingId does not match monitored private state")
    if related_ids and tracked_paths is None:
        tracked_paths = _git_tracked_paths(git_root())
    packet_sessions = {
        session.get("sessionId"): session
        for session in packet.get("sessions", [])
        if isinstance(session, dict) and isinstance(session.get("sessionId"), str)
    }
    counts = {"monitoring": 0, "validated": 0, "recurrent": 0}
    follow_up = None
    grant_revoked = False
    for finding_id, initial_state in states.items():
        lock = _promotion_lock(state_dir, finding_id) if persist else nullcontext()
        with lock:
            state = _upgrade_promotion_state(initial_state)
            if persist:
                current = _load_promotion_state(_promotion_state_path(state_dir, finding_id), finding_id)
                if current is None or current.get("schemaVersion") not in {2, 3} or current["creationPending"]:
                    continue
                state = _upgrade_promotion_state(current)
            before = _canonical(state)
            code, data, _error = beads_runner(["show", state["beadId"]])
            bead = _bead_record(data) if code == 0 else None
            result = latest_work_item_result(state["beadId"]) if bead else None
            boundary = _correction_boundary(bead, result) if bead else None
            monitoring = state["monitoring"]
            if finding_id in related_ids and not boundary:
                raise ValueError("related finding implementation boundary is unavailable")
            recurrent_findings: list[dict[str, Any]] = []
            was_recurrent = monitoring["status"] == "recurrent"
            if boundary:
                boundary_text, boundary_time = boundary
                monitoring["implementedAt"] = monitoring["implementedAt"] or boundary_text
                if monitoring["status"] == "promoted":
                    monitoring["status"] = "monitoring"
                for decision_session in decisions["sessions"]:
                    packet_session = packet_sessions[decision_session["sessionId"]]
                    started = _monitoring_session_time(packet_session)
                    related_findings = [
                        finding
                        for finding in decision_session["findings"]
                        if finding.get("relatedFindingId") == finding_id
                    ]
                    matched = (
                        started is not None
                        and started > boundary_time
                        and _complete_monitoring_evidence(packet, packet_session)
                        and _monitoring_matches(packet_session, monitoring)
                    )
                    if related_findings and decision_session["decision"] != "actions-created":
                        raise ValueError("related finding requires an actions-created decision")
                    if related_findings and not matched:
                        raise ValueError("related finding is outside matched post-change cohort")
                    if not matched:
                        continue
                    if related_findings:
                        recurrent_findings.extend(related_findings)
                        monitoring["recurrentFindingIds"] = sorted({
                            *monitoring["recurrentFindingIds"],
                            *(finding["id"] for finding in related_findings),
                        })
                    elif decision_session["decision"] in {"no-action", "actions-created"}:
                        monitoring["sampleIds"] = sorted({
                            *monitoring["sampleIds"],
                            _hash({"sessionId": decision_session["sessionId"]}),
                        })
                if monitoring["recurrentFindingIds"]:
                    monitoring["status"] = "recurrent"
                elif len(monitoring["sampleIds"]) >= monitoring["minimumSamples"]:
                    monitoring["status"] = "validated"
            became_recurrent = not was_recurrent and monitoring["status"] == "recurrent"
            candidate_follow_up = None
            if became_recurrent and monitoring["followUpTarget"] is None:
                assert tracked_paths is not None
                candidate_follow_up = _recurrent_follow_up(
                    packet,
                    decisions,
                    recurrent_findings,
                    tracked_paths,
                )
            if persist and became_recurrent:
                revoked = (correction_revoker or revoke_correction_grant)(state["beadId"])
                grant_revoked = grant_revoked or revoked is not None
                if candidate_follow_up is not None and follow_up is None:
                    follow_up = candidate_follow_up
                    monitoring["followUpTarget"] = candidate_follow_up["target"]["id"]
            if persist and _canonical(state) != before:
                _write_private_json(state_dir, _promotion_state_path(state_dir, finding_id).name, state)
            if monitoring["status"] in counts:
                counts[monitoring["status"]] += 1
    return {"counts": counts, "followUp": follow_up, "grantRevoked": grant_revoked}


def _monitoring_projection(
    sessions: list[dict[str, Any]],
    *,
    state_dir: Path,
    beads_runner: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    counts = {"promoted": 0, "monitoring": 0, "validated": 0, "recurrent": 0, "matchedSessions": 0}
    for finding_id, raw_state in _monitored_promotion_states(state_dir).items():
        state = _upgrade_promotion_state(raw_state)
        monitoring = state["monitoring"]
        status = monitoring["status"]
        boundary = None
        if beads_runner is not None:
            code, data, _error = beads_runner(["show", state["beadId"]])
            bead = _bead_record(data) if code == 0 else None
            result = latest_work_item_result(state["beadId"]) if bead else None
            boundary = _correction_boundary(bead, result) if bead else None
            if boundary and status == "promoted":
                status = "monitoring"
        matched = []
        if boundary:
            _boundary_text, boundary_time = boundary
            for index, session in enumerate(sessions):
                started = _monitoring_session_time(session)
                if (
                    started is not None
                    and started > boundary_time
                    and _monitoring_matches(session, monitoring)
                ):
                    matched.append(index)
        counts[status] += 1
        counts["matchedSessions"] += len(matched)
        rows.append({
            "findingId": finding_id,
            "status": status,
            "matchedSessionIndexes": matched,
            "minimumSamples": monitoring["minimumSamples"],
            "reviewedSamples": len(monitoring["sampleIds"]),
        })
    return rows, counts


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
            "findingIds": [finding["id"] for finding in session["findings"]],
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
    monitoring: dict[str, Any],
    approval: Any,
    approval_preview: dict[str, str],
    beads_runner: Any,
) -> dict[str, Any]:
    state_path = _promotion_state_path(state_dir, finding_id)
    state = _load_promotion_state(state_path, finding_id)
    if state and state.get("schemaVersion") == 1:
        state = {**state, "schemaVersion": 3, "monitoring": monitoring}
        _write_private_json(state_dir, state_path.name, state)
    elif state and state.get("schemaVersion") == 2:
        state = _upgrade_promotion_state(state)
        _write_private_json(state_dir, state_path.name, state)
    if state and state["creationPending"] and not _repair_creation(beads_runner, state_dir, state_path, state):
        return {"schemaVersion": 1, "status": "creation-repair-needed", "created": False}
    if state and not state["linkRepairNeeded"]:
        return {"schemaVersion": 1, "status": "already-promoted", "beadId": state["beadId"], "created": False}
    created_now = False
    if state is None:
        if not _has_exact_human_approval(approval, approval_preview):
            raise ValueError("promotion apply requires exact human approval")
        state = {
            "schemaVersion": 3,
            "findingId": finding_id,
            "beadId": _new_bead_id(),
            "creationPending": True,
            "linkRepairNeeded": True,
            "monitoring": monitoring,
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
        finding_id_value = finding["id"]
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
    if not IMPROVEMENT_FINDING_ID.fullmatch(finding_id):
        raise ValueError("finding id is malformed")
    if _inside(state_dir, repository_root):
        raise ValueError("private promotion state must be outside repository")
    bead, session, validated = _public_bead(packet, decisions, finding_id, tracked_paths)
    monitoring = _new_monitoring_state(packet, session)
    approval_preview = _promotion_approval_preview(bead)
    if not apply:
        work = {key: bead[key] for key in ("title", "description", "acceptance", "labels")}
        return {
            "schemaVersion": 1,
            "status": "preview",
            "bead": bead,
            "work": work,
            "approvalPreview": approval_preview,
        }
    with _promotion_lock(state_dir, finding_id):
        return _apply_promotion(
            client,
            validated,
            finding_id=finding_id,
            state_dir=state_dir,
            bead=bead,
            session=session,
            monitoring=monitoring,
            approval=approval,
            approval_preview=approval_preview,
            beads_runner=beads_runner,
        )


def _session_start(session_id: str) -> datetime | None:
    try:
        return datetime.strptime(session_id.split("_", 1)[0], "%Y-%m-%dT%H-%M-%S-%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            session_uuid = uuid.UUID(session_id)
            if session_uuid.version != 7:
                return None
            milliseconds = session_uuid.int >> 80
            return datetime.fromtimestamp(milliseconds // 1000, tz=timezone.utc).replace(
                microsecond=(milliseconds % 1000) * 1000
            )
        except (ValueError, OverflowError, OSError):
            return None


def _session_starts_within(session_id: str, since: str | None, until: str | None) -> bool:
    if since is None and until is None:
        return True
    started = _session_start(session_id)
    if started is None:
        return False
    try:
        lower = datetime.fromisoformat(since.replace("Z", "+00:00")) if since else None
        upper = datetime.fromisoformat(until.replace("Z", "+00:00")) if until else None
    except ValueError:
        return False
    return (lower is None or started >= lower) and (upper is None or started <= upper)


def _session_score_since(session_id: str, fallback: str) -> str:
    started = _session_start(session_id)
    try:
        fallback_time = datetime.fromisoformat(fallback.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if started is None or started >= fallback_time:
        return fallback
    return started.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_current_review(scores: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(score.get("metadata"), dict)
        and score["metadata"].get("reviewPolicyVersion") == REVIEW_POLICY_VERSION
        for score in scores
    )


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _settled_window(
    since: str,
    until: str,
    observed_at: str | datetime | None = None,
) -> tuple[str, str, dict[str, Any]]:
    lower = _parse_utc(since)
    requested = _parse_utc(until)
    observed = _parse_utc(observed_at) if isinstance(observed_at, str) else observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    observed = observed.astimezone(timezone.utc)
    watermark = min(requested, observed - timedelta(seconds=SETTLEMENT_LAG_SECONDS))
    if lower >= watermark:
        raise ValueError("scan has no settled time window")
    read_until = min(observed, watermark + timedelta(seconds=SETTLEMENT_LAG_SECONDS))
    watermark_text = _iso_utc(watermark)
    read_until_text = _iso_utc(read_until)
    return watermark_text, read_until_text, {
        "schemaVersion": 1,
        "requestedUntil": _iso_utc(requested),
        "watermark": watermark_text,
        "readUntil": read_until_text,
        "lagSeconds": SETTLEMENT_LAG_SECONDS,
        "activeWindowExcluded": watermark < requested,
    }


def _trace_is_settled(trace: dict[str, Any], watermark: str) -> bool:
    timestamp = trace.get("timestamp")
    if not isinstance(timestamp, str):
        return True
    try:
        return _parse_utc(timestamp) <= _parse_utc(watermark)
    except ValueError:
        return True


def _review_eligibility(
    client: Any,
    *,
    since: str,
    until: str,
    cohort_until: str,
    max_traces: int,
    recheck: bool = False,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, bool],
    dict[str, bool],
    dict[str, list[dict[str, Any]]],
    set[str],
    dict[str, Any],
]:
    discovery = client.list_traces_with_metadata(
        from_timestamp=since,
        to_timestamp=until,
        max_traces=max_traces,
    )
    traces = discovery["traces"]
    all_groups: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        session_id = trace.get("sessionId")
        if isinstance(session_id, str) and session_id and _trace_is_settled(trace, cohort_until):
            all_groups.setdefault(session_id, []).append(trace)
    for session_traces in all_groups.values():
        session_traces.sort(
            key=lambda trace: (str(trace.get("timestamp") or ""), str(trace.get("id") or "")),
            reverse=True,
        )

    observation_cache: dict[str, list[dict[str, Any]]] = {}
    observation_limits: set[str] = set()
    unclassified_projection_traces: set[str] = set()
    child_session_ids: set[str] = set()
    for trace in traces:
        if trace.get("name") != "subagent-result":
            continue
        trace_id = trace.get("id")
        parent_session_id = trace.get("sessionId")
        if not isinstance(trace_id, str) or not trace_id:
            continue
        rows = client.list_observations(
            from_start_time=since,
            to_start_time=until,
            trace_id=trace_id,
            limit=OBSERVATIONS_PER_TRACE + 1,
        )
        if len(rows) > OBSERVATIONS_PER_TRACE:
            observation_limits.add(trace_id)
        observation_cache[trace_id] = rows[:OBSERVATIONS_PER_TRACE]
        declarations = [
            observation
            for observation in observation_cache[trace_id]
            if observation.get("name") == "subagent-result"
        ]
        if not declarations:
            unclassified_projection_traces.add(trace_id)
        for observation in declarations:
            metadata = observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
            mode = metadata.get("effectiveMode")
            declared = metadata.get("childTraceAvailability")
            child_id = metadata.get("childSessionId")
            valid_child = isinstance(child_id, str) and 0 < len(child_id) <= 200 and child_id != parent_session_id
            if mode == "agentic" and declared == "expected-available" and valid_child:
                child_session_ids.add(child_id)
            elif mode != "one-shot" or declared != "expected-unavailable":
                unclassified_projection_traces.add(trace_id)

    excluded = child_session_ids.intersection(all_groups)
    groups = {session_id: items for session_id, items in all_groups.items() if session_id not in excluded}
    review_cache: dict[str, bool] = {}
    review_scores_truncated: dict[str, bool] = {}
    for session_id in groups:
        scores = [] if recheck else client.list_scores(
            from_timestamp=_session_score_since(session_id, since),
            to_timestamp=until,
            session_id=session_id,
            name=REVIEW_SCORE,
            limit=SCORES_PER_QUERY + 1,
        )
        review_scores_truncated[session_id] = len(scores) > SCORES_PER_QUERY
        review_cache[session_id] = _is_current_review(scores[:SCORES_PER_QUERY])
    classification = {
        "rootSessions": len(groups),
        "childSessionsExcluded": len(excluded),
        "unclassifiedProjectionTraces": len(unclassified_projection_traces),
        "complete": (
            discovery.get("complete") is True
            and not observation_limits
            and not unclassified_projection_traces
        ),
    }
    return (
        discovery,
        traces,
        groups,
        review_cache,
        review_scores_truncated,
        observation_cache,
        observation_limits,
        classification,
    )


def eligible_unreviewed_session_summary(
    client: Any,
    *,
    since: str,
    until: str,
    max_traces: int = DEFAULT_MAX_TRACES,
    observed_at: str | datetime | None = None,
) -> dict[str, Any]:
    settled_until, read_until, settlement = _settled_window(since, until, observed_at)
    discovery, _traces, groups, review_cache, truncated, _cache, limits, classification = _review_eligibility(
        client,
        since=since,
        until=read_until,
        cohort_until=settled_until,
        max_traces=max_traces,
    )
    eligible = sum(not review_cache[session_id] for session_id in groups)
    return {
        "schemaVersion": 1,
        "status": "ok",
        "candidateSessions": len(groups),
        "eligibleSessions": eligible,
        "reviewedSessionsSkipped": len(groups) - eligible,
        "childSessionsExcluded": classification["childSessionsExcluded"],
        "unclassifiedProjectionTraces": classification["unclassifiedProjectionTraces"],
        "sessionClassificationComplete": classification["complete"],
        "settlementLagSeconds": settlement["lagSeconds"],
        "activeWindowExcluded": settlement["activeWindowExcluded"],
        "traceDiscoveryComplete": discovery.get("complete") is True,
        "lowerBound": not classification["complete"] or bool(limits) or any(truncated.values()),
    }


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
    beads_runner: Any = None,
    observed_at: str | datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not 1 <= limit <= MAX_REVIEW_ASSIGNMENT_ITEMS:
        raise ValueError("scan limit must be between 1 and 20")
    if not since or not until:
        raise ValueError("scan requires time bounds")
    if _inside(output_dir, repository_root):
        raise ValueError("improvement directory must be outside repository")

    settled_until, read_until, settlement = _settled_window(since, until, observed_at)
    (
        discovery,
        traces,
        groups,
        review_cache,
        review_scores_truncated,
        observation_cache,
        prefetch_observation_limits,
        classification,
    ) = _review_eligibility(
        client,
        since=since,
        until=read_until,
        cohort_until=settled_until,
        max_traces=max_traces,
        recheck=recheck,
    )
    attributable = sum(
        isinstance(trace.get("sessionId"), str) and bool(trace.get("sessionId"))
        for trace in traces
    )
    trace_discovery = {
        "totalAvailable": discovery.get("totalAvailable"),
        "scanned": len(traces),
        "maxTraces": max_traces,
        "attributable": attributable,
        "unattributed": len(traces) - attributable,
        "rootSessions": classification["rootSessions"],
        "childSessionsExcluded": classification["childSessionsExcluded"],
        "unclassifiedProjectionTraces": classification["unclassifiedProjectionTraces"],
        "sessionClassificationComplete": classification["complete"],
        "complete": discovery["complete"],
        "continuation": discovery["continuation"],
    }
    child_trace_roots: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        session_id = trace.get("sessionId")
        if trace.get("name") == "pi-agent" and isinstance(session_id, str) and session_id:
            child_trace_roots.setdefault(session_id, []).append(trace)
    eligible_groups = sorted(
        ((session_id, items) for session_id, items in groups.items() if not review_cache[session_id]),
        key=lambda item: (str(item[1][0].get("timestamp") or ""), item[0]),
        reverse=True,
    )
    billing_classes = _cohort_billing_classes(repository_root)
    allowed_providers, allowed_models = _cohort_dimension_allowlists(repository_root)

    sessions = []
    for session_id, session_traces in eligible_groups[:limit]:
        selected_traces = session_traces[:MAX_TRACES_PER_SESSION]
        observations = []
        trace_scores = []
        observations_truncated = False
        scores_truncated = review_scores_truncated[session_id]
        for trace in selected_traces:
            trace_id = str(trace["id"])
            if trace_id in observation_cache:
                rows = observation_cache[trace_id]
                observations_truncated = observations_truncated or trace_id in prefetch_observation_limits
            else:
                rows = client.list_observations(
                    from_start_time=since,
                    to_start_time=read_until,
                    trace_id=trace_id,
                    limit=OBSERVATIONS_PER_TRACE + 1,
                )
                observations_truncated = observations_truncated or len(rows) > OBSERVATIONS_PER_TRACE
            observations.extend(rows[:OBSERVATIONS_PER_TRACE])
            rows = client.list_scores(
                from_timestamp=since,
                to_timestamp=read_until,
                trace_id=trace_id,
                limit=SCORES_PER_QUERY + 1,
            )
            scores_truncated = scores_truncated or len(rows) > SCORES_PER_QUERY
            trace_scores.extend(rows[:SCORES_PER_QUERY])
        score_since = _session_score_since(session_id, since)
        link_score_rows = client.list_scores(
            from_timestamp=score_since,
            to_timestamp=read_until,
            session_id=session_id,
            name=WORK_LINK_SCORE,
            limit=SCORES_PER_QUERY + 1,
        )
        outcome_score_rows = client.list_scores(
            from_timestamp=score_since,
            to_timestamp=read_until,
            session_id=session_id,
            name=OUTCOME_SCORE,
            limit=SCORES_PER_QUERY + 1,
        )
        scores_truncated = scores_truncated or any(
            len(rows) > SCORES_PER_QUERY for rows in (link_score_rows, outcome_score_rows)
        )
        link_scores = link_score_rows[:SCORES_PER_QUERY]
        outcome_scores = outcome_score_rows[:SCORES_PER_QUERY]
        correlation = _correlate(session_id, runs_dir, link_scores)
        correlated_outcomes, outcome_mismatch = _correlated_outcome_scores(
            session_id, correlation, outcome_scores
        )
        features = _features(
            selected_traces,
            observations,
            [
                *(score for score in trace_scores if score.get("name") != OUTCOME_SCORE),
                *correlated_outcomes,
            ],
            child_trace_roots=child_trace_roots,
            trace_discovery_complete=trace_discovery["complete"] is True,
            trace_discovery_since=since,
            trace_discovery_until=settled_until,
            billing_classes=billing_classes,
            allowed_providers=allowed_providers,
            allowed_models=allowed_models,
        )
        if outcome_mismatch:
            features["captureGaps"].append("mismatched-work-item-outcome")
        if len(session_traces) > len(selected_traces):
            features["captureGaps"].append("trace-limit")
        if observations_truncated:
            features["captureGaps"].append("observation-limit")
        if scores_truncated:
            features["captureGaps"].append("score-limit")
        sessions.append({
            "sessionId": session_id,
            "traceIds": [str(trace["id"]) for trace in selected_traces],
            "correlation": correlation,
            "features": features,
        })

    cohort_health = _cohort_health(
        sessions,
        trace_discovery=trace_discovery,
        scan_limit=limit,
        eligible_session_count=len(eligible_groups),
        allowed_providers=allowed_providers,
        allowed_models=allowed_models,
    )
    monitoring, monitoring_summary = _monitoring_projection(
        sessions,
        state_dir=output_dir,
        beads_runner=beads_runner,
    )
    report_id = _hash({"since": since, "until": settled_until, "sessions": [item["sessionId"] for item in sessions]})[:16]
    packet = {
        "schemaVersion": 3,
        "reportId": report_id,
        "createdAt": settled_until,
        "scan": {
            "since": since,
            "until": settled_until,
            "settlement": settlement,
            "limit": limit,
            "recheck": recheck,
            "reviewPolicyVersion": REVIEW_POLICY_VERSION,
            "traceDiscovery": trace_discovery,
            "cohortHealth": cohort_health,
        },
        "sessions": sessions,
        "monitoring": monitoring,
    }
    for index, session in enumerate(sessions):
        evidence_ref = _improvement_evidence_ref(packet, index)
        session["evidenceRef"] = evidence_ref
        session["outcomeProof"] = _outcome_proof(session["features"], evidence_ref)
    assignment = review_assignment(packet) if sessions else None
    assignment_ref = (
        f"artifact:review-assignment-{assignment['assignmentId']}"
        if assignment is not None
        else None
    )
    summary = {
        "schemaVersion": 1,
        "status": "ok",
        "scannedTraces": len(traces),
        "traceDiscovery": trace_discovery,
        "settlement": {
            "lagSeconds": settlement["lagSeconds"],
            "activeWindowExcluded": settlement["activeWindowExcluded"],
        },
        "cohortHealth": cohort_health,
        "monitoring": monitoring_summary,
        "candidateSessions": len(groups),
        "eligibleSessions": len(sessions),
        "reviewedSessionsSkipped": sum(review_cache.get(session_id, False) for session_id in groups),
        "unlinkedSessions": sum(item["correlation"]["status"] == "unlinked" for item in sessions),
        "reportWritten": not dry_run,
        "reportPath": None,
        "assignmentWritten": assignment is not None and not dry_run,
        "assignmentRef": assignment_ref,
    }
    if not dry_run:
        if assignment is not None:
            _write_review_assignment(output_dir, assignment)
        _write_packet(output_dir, packet)
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


def link_current_session(bead_id: str) -> dict[str, Any]:
    session_id = current_session_id()
    summary = capture_session_link(
        session_id,
        bead_id,
        beads_runner=_beads,
    )
    return _best_effort_projection(
        summary,
        lambda client: _project_session_link(client, session_id=session_id, bead_id=bead_id),
    )


def _record_current_session_outcome(
    bead_id: str,
    outcome: str,
    *,
    require_link: bool,
) -> dict[str, Any]:
    session_id = current_session_id()
    summary = capture_session_outcome(
        session_id,
        bead_id,
        outcome,
        beads_runner=_beads,
        require_link=require_link,
    )
    return _best_effort_projection(
        summary,
        lambda client: _project_session_outcome(
            client,
            session_id=session_id,
            bead_id=bead_id,
            outcome=outcome,
        ),
    )


def record_current_session_outcome(bead_id: str, outcome: str) -> dict[str, Any]:
    return _record_current_session_outcome(bead_id, outcome, require_link=False)


def record_current_session_closeout(bead_id: str, outcome: str) -> dict[str, Any]:
    return _record_current_session_outcome(bead_id, outcome, require_link=True)


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
    if not 1 <= limit <= MAX_REVIEW_ASSIGNMENT_ITEMS:
        raise argparse.ArgumentTypeError("limit must be between 1 and 20")
    return limit


def _max_traces(value: str) -> int:
    limit = int(value)
    if limit < 1:
        raise argparse.ArgumentTypeError("max traces must be positive")
    return limit


def _report_session_work_item_conflict(*, target_bead: str, json_output: bool) -> int:
    if json_output:
        print(json.dumps({
            "schemaVersion": 1,
            "status": "error",
            "error": "session belongs to another work item",
            "recovery": {
                "action": "start-fresh-session",
                "handoffTool": {
                    "name": "handoff_bead",
                    "arguments": {"targetBead": target_bead},
                },
                "humanFallback": {"command": "/new"},
            },
        }))
    else:
        print(
            "Current Pi session belongs to another work item. "
            f"Call handoff_bead with targetBead={target_bead}; "
            "if the tool is unavailable, run /new, then retry.",
            file=sys.stderr,
        )
    return 2


def cmd_improve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt improve", description="Review private Langfuse telemetry safely.")
    sub = parser.add_subparsers(dest="action")
    scan = sub.add_parser("scan", help="write a bounded private review packet")
    scan.add_argument("--since", type=_timestamp)
    scan.add_argument("--until", type=_timestamp)
    scan.add_argument("--limit", type=_scan_limit, default=20)
    scan.add_argument("--max-traces", type=_max_traces, default=DEFAULT_MAX_TRACES)
    scan.add_argument("--recheck", action="store_true")
    scan.add_argument("--dry-run", action="store_true")
    scan.add_argument("--json", action="store_true")
    annotations = sub.add_parser(
        "annotations", help="import bounded Langfuse annotation queue evidence"
    )
    annotations.add_argument("queue")
    annotations.add_argument("--json", action="store_true")
    link = sub.add_parser("link", help="link the current private session to a public work item")
    link.add_argument("bead")
    link.add_argument("--json", action="store_true")
    outcome = sub.add_parser("outcome", help="record a linked final outcome for the current private session")
    outcome.add_argument("bead")
    outcome.add_argument("outcome", choices=sorted(TASK_OUTCOMES))
    outcome.add_argument("--json", action="store_true")
    review = sub.add_parser("review", help="validate an assignment-bound private review result and optionally mark sessions")
    review.add_argument("report", type=Path)
    review.add_argument("result", type=Path)
    review.add_argument("--apply", action="store_true")
    review.add_argument("--json", action="store_true")
    promote = sub.add_parser("promote", help="render one public-safe import packet for quality apply")
    promote.add_argument("report", type=Path)
    promote.add_argument("result", type=Path)
    promote.add_argument("--finding", required=True)
    promote.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "annotations":
        try:
            try:
                client = _client_from_env()
            except ValueError:
                client = None
            summary = import_langfuse_annotation_evidence(client, args.queue)
        except (LangfuseError, ValueError):
            if args.json:
                print(json.dumps({
                    "schemaVersion": 1,
                    "status": "error",
                    "error": "annotation import failed",
                }))
            else:
                print("Annotation import failed.", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(
                f"Annotation evidence: {summary['status']}; "
                f"references: {len(summary['evidenceRefs'])}"
            )
        return 0
    if args.action == "outcome":
        try:
            summary = record_current_session_outcome(args.bead, args.outcome)
        except SessionWorkItemConflict:
            return _report_session_work_item_conflict(target_bead=args.bead, json_output=args.json)
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
        except SessionWorkItemConflict:
            return _report_session_work_item_conflict(target_bead=args.bead, json_output=args.json)
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
            summary = promote_finding(
                None,
                _load_private_object(args.report, repository_root),
                _load_private_object(args.result, repository_root),
                finding_id=args.finding,
                state_dir=improvement_dir(),
                repository_root=repository_root,
                tracked_paths=_git_tracked_paths(repository_root),
                apply=False,
                beads_runner=_beads,
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            if args.json:
                print(json.dumps({"schemaVersion": 1, "status": "error", "error": "improvement promotion failed"}))
            else:
                print("Improvement promotion failed.", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(render_public_bead(summary["bead"]))
        return 0
    if args.action == "review":
        try:
            repository_root = git_root()
            packet = _load_private_object(args.report, repository_root)
            decisions = _load_private_object(args.result, repository_root)
            summary = review_sessions(None, packet, decisions)
            if args.apply and summary["status"] != "needs-human":
                summary = review_sessions(
                    _client_from_env(),
                    packet,
                    decisions,
                    apply=True,
                    state_dir=improvement_dir(),
                    beads_runner=_beads,
                )
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
    until = args.until or now.isoformat().replace("+00:00", "Z")
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
            beads_runner=_beads,
            observed_at=now,
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
        print(f"Eligible sessions: {summary['eligibleSessions']}; report written: {summary['reportWritten']}")
    return 0


__all__ = [
    "cmd_improve",
    "eligible_unreviewed_session_summary",
    "import_langfuse_annotation_evidence",
    "improvement_dir",
    "scan_sessions",
]
