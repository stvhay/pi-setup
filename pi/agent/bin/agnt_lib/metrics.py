from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import _agnt_common as common

from .core import VALID_OUTCOMES, split_target, utc_now
from .quality import FINDING_STATUSES, derive_core_metrics
from .review import load_review_document, review_annotation_fields
from .runtime_paths import resolve_runtime_directory

# Model facts and opportunity-cost rates live in catalog.json.
MAX_ARTIFACT_REFS = 16
MAX_ARTIFACT_REF_CHARS = 256
HANDOFF_STAGES = frozenset({
    "attempt",
    "preflight",
    "selection",
    "validation",
    "session-stage",
    "restart-request",
    "shutdown-exit",
    "process-replacement",
})
HANDOFF_RESULT_CLASSES = frozenset({"started", "succeeded", "failed", "cancelled", "attempted"})


def new_invocation_id() -> str:
    return str(uuid4())


def bounded_artifact_refs(refs: List[str] | None) -> List[str]:
    bounded: List[str] = []
    for value in refs or []:
        if not isinstance(value, str):
            continue
        path = Path(value)
        if not value or len(value) > MAX_ARTIFACT_REF_CHARS or path.is_absolute() or ".." in path.parts:
            continue
        bounded.append(value)
        if len(bounded) == MAX_ARTIFACT_REFS:
            break
    return bounded


def empty_usage() -> Dict[str, Any]:
    return {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "totalTokens": 0,
        "cost": {"input": 0.0, "output": 0.0, "cacheRead": 0.0, "cacheWrite": 0.0, "total": 0.0},
    }


def priced_usage(usage: Dict[str, Any], prices: Dict[str, float]) -> Dict[str, float]:
    estimated = {key: int(usage.get(key) or 0) * float(prices.get(key) or 0.0) / 1_000_000 for key in ("input", "output", "cacheRead", "cacheWrite")}
    estimated["total"] = sum(estimated.values())
    return estimated


def apply_assumed_cost(usage: Dict[str, Any] | None, target: str | None) -> Dict[str, Any] | None:
    if not isinstance(usage, dict) or not target:
        return usage
    cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else None
    if cost and float(cost.get("total") or 0.0) > 0:
        usage.setdefault("costSource", "provider-reported")
        return usage
    target_prices = common.opportunity_rates(target)
    if not target_prices:
        return usage
    estimated = priced_usage(usage, target_prices)
    usage["cost"] = estimated
    usage["costEstimated"] = True
    usage["costSource"] = "openrouter-assumed"
    usage["costPricing"] = {"unit": "USD_PER_MILLION_TOKENS", "source": "OpenRouter", "rates": target_prices}
    return usage


def add_usage(total: Dict[str, Any], usage: Dict[str, Any]) -> None:
    for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens"):
        total[key] += int(usage.get(key) or 0)
    cost = usage.get("cost") or {}
    for key in ("input", "output", "cacheRead", "cacheWrite", "total"):
        total["cost"][key] += float(cost.get(key) or 0.0)
def estimate_tokens(text: str) -> int:
    # Crude but stable cross-provider estimate for routing analytics. Avoids
    # adding tokenizer dependencies to this lightweight helper.
    return max(1, (len(text) + 3) // 4) if text else 0


def empty_review_finding_stats() -> Dict[str, Any]:
    return {"total": 0, **{status: 0 for status in FINDING_STATUSES}, "bySeverity": {}}


def add_review_finding_stats(total: Dict[str, Any], value: Dict[str, Any]) -> None:
    for key in ("total", *FINDING_STATUSES):
        total[key] += int(value.get(key) or 0)
    severities = value.get("bySeverity") if isinstance(value.get("bySeverity"), dict) else {}
    for severity, count in severities.items():
        total["bySeverity"][str(severity)] = int(total["bySeverity"].get(str(severity)) or 0) + int(count or 0)


def record_id(started_at: str, target: str, task: str | None) -> str:
    raw = f"{started_at}|{target}|{task or ''}"
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def execution_outcome(code: int) -> str:
    if code == 0:
        return "succeeded"
    if code == 124:
        return "unavailable"
    return "failed"


def metrics_record(
    *,
    target: str,
    task: str | None,
    started_at: str,
    ended_at: str,
    elapsed_ms: int,
    code: int,
    prompt: str,
    out: str,
    err: str,
    usage: Dict[str, Any] | None,
    usage_source: str,
    invocation_id: str | None = None,
    parent_session_id: str | None = None,
    work_item: str | None = None,
    failure_class: str | None = None,
    provider_failure_class: str | None = None,
    artifact_refs: List[str] | None = None,
    risk_category: str | None = None,
    thinking_level: str | None = None,
    outcome: str = "unknown",
    human_override: bool = False,
    fallback_used: bool = False,
    invocation_mode: str = "agentic",
) -> Dict[str, Any]:
    provider, model = split_target(target)
    usage = apply_assumed_cost(usage, target)
    if outcome not in VALID_OUTCOMES:
        outcome = "unknown"
    return {
        "schemaVersion": 2,
        "invocationId": invocation_id or new_invocation_id(),
        "recordId": record_id(started_at, target, task),
        "parentSessionId": parent_session_id,
        "workItem": work_item,
        "startedAt": started_at,
        "endedAt": ended_at,
        "durationMs": elapsed_ms,
        "elapsedMs": elapsed_ms,
        "status": "succeeded" if code == 0 else "failed",
        "executionOutcome": execution_outcome(code),
        "failureClass": failure_class if code != 0 else None,
        "providerFailureClass": provider_failure_class if code != 0 else None,
        "artifactRefs": bounded_artifact_refs(artifact_refs),
        "task": task,
        "family": common.family_for_target(target),
        "riskCategory": risk_category,
        "thinkingLevel": thinking_level,
        "invocationMode": invocation_mode,
        "providerRequests": int(usage.get("providerRequests") or 0) if isinstance(usage, dict) else 0,
        "contextChars": len(prompt),
        "estimatedInputTokens": estimate_tokens(prompt),
        "outcome": outcome,
        "humanOverride": human_override,
        "fallbackUsed": fallback_used,
        "provider": provider,
        "model": model,
        "target": target,
        "exitCode": code,
        "usageSource": usage_source,
        "usage": usage,
        "responseChars": len(out),
        "stderrChars": len(err),
    }


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_root() -> Path:
    try:
        return Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(os.getcwd())


def default_metrics_dir() -> Path:
    return resolve_runtime_directory("metrics/invocations")


def default_consumed_metrics_dir() -> Path:
    return resolve_runtime_directory("metrics/consumed")


def default_metrics_output() -> Path:
    # Consolidated metrics are runtime state shared across projects: they feed
    # routing decisions everywhere, so they live in ~/.pi, not in any repo.
    value = os.environ.get("AGNT_METRICS_OUTPUT")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".pi" / "metrics" / "agent-invocations.jsonl"


def default_annotations_file() -> Path:
    return resolve_runtime_directory("metrics") / "annotations.jsonl"
def metric_files(metrics_dir: Path) -> List[Path]:
    return sorted(metrics_dir.glob("*.metrics.json")) if metrics_dir.is_dir() else []


def load_annotations(path: Path | None = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    annotations_file = path or default_annotations_file()
    annotations: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not annotations_file.is_file():
        return annotations, warnings
    for line_no, line in enumerate(annotations_file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"{annotations_file}:{line_no}: {exc}")
            continue
        if isinstance(data, dict):
            annotations.append(data)
        else:
            warnings.append(f"{annotations_file}:{line_no}: expected JSON object")
    return annotations, warnings


def annotation_matches(record: Dict[str, Any], annotation: Dict[str, Any]) -> bool:
    record_id_value = annotation.get("recordId")
    source_file = annotation.get("sourceFile")
    if record_id_value and record.get("recordId") == record_id_value:
        return True
    if source_file and record.get("sourceFile") == source_file:
        return True
    return False


def apply_annotations(records: List[Dict[str, Any]], annotations: List[Dict[str, Any]]) -> None:
    mutable_fields = {
        "outcome",
        "humanOverride",
        "fallbackUsed",
        "riskCategory",
        "thinkingLevel",
        "notes",
        "reviewId",
        "reviewScope",
        "reviewFindings",
        "reviewFindingStats",
    }
    for record in records:
        applied: List[Dict[str, Any]] = []
        for annotation in annotations:
            if not annotation_matches(record, annotation):
                continue
            updates = {key: annotation[key] for key in mutable_fields if key in annotation}
            if updates.get("outcome") and updates["outcome"] not in VALID_OUTCOMES:
                updates["outcome"] = "unknown"
            record.update(updates)
            applied.append({"annotatedAt": annotation.get("annotatedAt"), "updates": updates})
        if applied:
            record["annotations"] = applied


def load_metric_records(files: List[Path], *, include_annotations: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    records: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"{path}: {exc}")
            continue
        if isinstance(data, dict):
            if data.get("kind") == "handoff":
                data.setdefault("sourceFile", str(path))
                records.append(data)
                continue
            target = str(data.get("target") or f"{data.get('provider')}/{data.get('model')}")
            data["usage"] = apply_assumed_cost(data.get("usage"), target)
            data.setdefault("family", common.family_for_target(target))
            data.setdefault("sourceFile", str(path))
            data.setdefault("outcome", "unknown")
            data.setdefault("executionOutcome", "unknown")
            data.setdefault("outputContract", "unknown")
            data.setdefault("humanOverride", False)
            data.setdefault("fallbackUsed", False)
            records.append(data)
        else:
            warnings.append(f"{path}: expected JSON object")
    if include_annotations:
        annotations, annotation_warnings = load_annotations()
        warnings.extend(annotation_warnings)
        apply_annotations(records, annotations)
    return records, warnings


def compact_handoff_record(record: Dict[str, Any]) -> Dict[str, Any]:
    stage = record.get("stage")
    result_class = record.get("resultClass")
    try:
        duration_ms = max(0, int(record.get("durationMs") or 0))
    except (OverflowError, TypeError, ValueError):
        duration_ms = 0
    return {
        "schemaVersion": 2,
        "kind": "handoff",
        "stage": stage if stage in HANDOFF_STAGES else "unknown",
        "resultClass": result_class if result_class in HANDOFF_RESULT_CLASSES else "unknown",
        "durationMs": duration_ms,
    }


def summarize_handoffs(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "attempts": 0,
        "records": len(records),
        "durationMs": 0,
        "results": {},
        "byStage": {},
    }
    for raw in records:
        record = compact_handoff_record(raw)
        stage = record["stage"]
        result_class = record["resultClass"]
        duration_ms = record["durationMs"]
        if stage == "attempt":
            summary["attempts"] += 1
        summary["durationMs"] += duration_ms
        summary["results"][result_class] = summary["results"].get(result_class, 0) + 1
        item = summary["byStage"].setdefault(stage, {"records": 0, "durationMs": 0, "results": {}})
        item["records"] += 1
        item["durationMs"] += duration_ms
        item["results"][result_class] = item["results"].get(result_class, 0) + 1
    return summary


def usage_summary(records: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    total = empty_usage()
    seen = False
    for record in records:
        usage = record.get("usage")
        if isinstance(usage, dict):
            add_usage(total, usage)
            seen = True
    return total if seen else None


def summarize_metrics(
    records: List[Dict[str, Any]],
    *,
    quality_receipts: List[Dict[str, Any]] | None = None,
    quality_results: List[Dict[str, Any]] | None = None,
    quality_annotations: List[Dict[str, Any]] | None = None,
    quality_monitoring: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    handoff_records = [record for record in records if record.get("kind") == "handoff"]
    records = [record for record in records if record.get("kind") != "handoff"]
    by_model: Dict[str, Dict[str, Any]] = {}
    by_task: Dict[str, Dict[str, Any]] = {}
    exit_codes: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    outcome_counts: Dict[str, int] = {}
    execution_outcome_counts: Dict[str, int] = {}
    risk_counts: Dict[str, int] = {}
    thinking_counts: Dict[str, int] = {}
    review_scope_counts: Dict[str, int] = {}
    review_finding_counts = empty_review_finding_stats()
    kind_counts: Dict[str, int] = {}
    for record in [*records, *handoff_records]:
        kind = record.get("kind")
        if kind:
            kind_key = str(kind)
            kind_counts[kind_key] = kind_counts.get(kind_key, 0) + 1
    human_overrides = 0
    fallback_uses = 0
    context_chars = 0
    estimated_input_tokens = 0
    for record in records:
        target = str(record.get("target") or f"{record.get('provider')}/{record.get('model')}")
        task = str(record.get("task") or "unspecified")
        elapsed = int(record.get("elapsedMs") or 0)
        response_chars = int(record.get("responseChars") or 0)
        stderr_chars = int(record.get("stderrChars") or 0)
        exit_code = str(record.get("exitCode"))
        exit_codes[exit_code] = exit_codes.get(exit_code, 0) + 1
        status = record.get("status")
        if status:
            status_key = str(status)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
        outcome = str(record.get("outcome") or "unknown")
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        execution = str(record.get("executionOutcome") or "unknown")
        execution_outcome_counts[execution] = execution_outcome_counts.get(execution, 0) + 1
        risk = record.get("riskCategory")
        if risk:
            risk_key = str(risk)
            risk_counts[risk_key] = risk_counts.get(risk_key, 0) + 1
        thinking = record.get("thinkingLevel")
        if thinking:
            thinking_key = str(thinking)
            thinking_counts[thinking_key] = thinking_counts.get(thinking_key, 0) + 1
        review_scope = record.get("reviewScope")
        if review_scope:
            scope_key = str(review_scope)
            review_scope_counts[scope_key] = review_scope_counts.get(scope_key, 0) + 1
        review_stats = record.get("reviewFindingStats")
        if isinstance(review_stats, dict):
            add_review_finding_stats(review_finding_counts, review_stats)
        if record.get("humanOverride"):
            human_overrides += 1
        if record.get("fallbackUsed"):
            fallback_uses += 1
        context_chars += int(record.get("contextChars") or 0)
        estimated_input_tokens += int(record.get("estimatedInputTokens") or 0)
        for bucket, key in ((by_model, target), (by_task, task)):
            item = bucket.setdefault(
                key,
                {
                    "invocations": 0,
                    "elapsedMs": 0,
                    "responseChars": 0,
                    "stderrChars": 0,
                    "usage": empty_usage(),
                    "usageSeen": False,
                    "reviewFindings": empty_review_finding_stats(),
                },
            )
            item["invocations"] += 1
            item["elapsedMs"] += elapsed
            item["responseChars"] += response_chars
            item["stderrChars"] += stderr_chars
            if isinstance(review_stats, dict):
                add_review_finding_stats(item["reviewFindings"], review_stats)
            usage = record.get("usage")
            if isinstance(usage, dict):
                add_usage(item["usage"], usage)
                item["usageSeen"] = True
    for bucket in (by_model, by_task):
        for item in bucket.values():
            if not item.pop("usageSeen"):
                item["usage"] = None
            usage = item.get("usage")
            cost = float(((usage or {}).get("cost") or {}).get("total") or 0.0)
            confirmed = int(item["reviewFindings"].get("confirmed") or 0)
            item["confirmedFindingsPerUsd"] = confirmed / cost if cost > 0 else None
            item["reviewFindings"]["bySeverity"] = dict(sorted(item["reviewFindings"]["bySeverity"].items()))
    review_finding_counts["bySeverity"] = dict(sorted(review_finding_counts["bySeverity"].items()))
    return {
        "invocations": len(records),
        "elapsedMs": sum(int(record.get("elapsedMs") or 0) for record in records),
        "responseChars": sum(int(record.get("responseChars") or 0) for record in records),
        "stderrChars": sum(int(record.get("stderrChars") or 0) for record in records),
        "exitCodes": exit_codes,
        "statuses": status_counts,
        "executionOutcomes": execution_outcome_counts,
        "outcomes": outcome_counts,
        "riskCategories": risk_counts,
        "thinkingLevels": thinking_counts,
        "reviewScopes": review_scope_counts,
        "reviewFindings": review_finding_counts,
        "humanOverrides": human_overrides,
        "fallbackUses": fallback_uses,
        "contextChars": context_chars,
        "estimatedInputTokens": estimated_input_tokens,
        "kinds": kind_counts,
        "handoffs": summarize_handoffs(handoff_records),
        "usage": usage_summary(records),
        "byModel": by_model,
        "byTask": by_task,
        "qualityMetrics": derive_core_metrics(
            receipts=quality_receipts,
            results=[*records, *(quality_results or [])],
            annotations=quality_annotations,
            monitoring=quality_monitoring,
        ),
    }


def current_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def compact_metric_record(record: Dict[str, Any]) -> Dict[str, Any]:
    if record.get("kind") == "handoff":
        return compact_handoff_record(record)
    return {
        "schemaVersion": record.get("schemaVersion", 1),
        "invocationId": record.get("invocationId"),
        "recordId": record.get("recordId"),
        "parentSessionId": record.get("parentSessionId"),
        "childSessionId": record.get("childSessionId"),
        "workItem": record.get("workItem"),
        "startedAt": record.get("startedAt"),
        "endedAt": record.get("endedAt"),
        "durationMs": record.get("durationMs", record.get("elapsedMs")),
        "elapsedMs": record.get("elapsedMs"),
        "executionOutcome": record.get("executionOutcome", "unknown"),
        "failureClass": record.get("failureClass"),
        "providerFailureClass": record.get("providerFailureClass"),
        "terminationReason": record.get("terminationReason"),
        "terminationSource": record.get("terminationSource"),
        "terminationLimit": record.get("terminationLimit"),
        "terminationObserved": record.get("terminationObserved"),
        "terminationUsageState": record.get("terminationUsageState"),
        "effectiveMaxDurationMs": record.get("effectiveMaxDurationMs"),
        "artifactRefs": bounded_artifact_refs(record.get("artifactRefs")),
        "artifactStatus": record.get("artifactStatus"),
        "artifactFailureClass": record.get("artifactFailureClass"),
        "outputContract": record.get("outputContract", "unknown"),
        "childIndex": record.get("childIndex"),
        "task": record.get("task"),
        "riskCategory": record.get("riskCategory"),
        "thinkingLevel": record.get("thinkingLevel"),
        "invocationMode": record.get("invocationMode"),
        "providerRequests": record.get("providerRequests"),
        "contextChars": record.get("contextChars"),
        "estimatedInputTokens": record.get("estimatedInputTokens"),
        "outcome": record.get("outcome"),
        "humanOverride": record.get("humanOverride"),
        "fallbackUsed": record.get("fallbackUsed"),
        "annotations": record.get("annotations"),
        "reviewId": record.get("reviewId"),
        "reviewScope": record.get("reviewScope"),
        "reviewFindings": record.get("reviewFindings"),
        "reviewFindingStats": record.get("reviewFindingStats"),
        "provider": record.get("provider"),
        "model": record.get("model"),
        "target": record.get("target"),
        "family": record.get("family"),
        "exitCode": record.get("exitCode"),
        "usageSource": record.get("usageSource"),
        "usage": record.get("usage"),
        "responseChars": record.get("responseChars"),
        "stderrChars": record.get("stderrChars"),
        "kind": record.get("kind"),
        "status": record.get("status"),
    }


def write_metric_record(metrics_dir: Path, name: str, record: Dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = metrics_dir / f"{stamp}-{name}.metrics.json"
    write_json(path, record)
    return path


def move_consumed(files: List[Path], consumed_root: Path) -> Path:
    destination = consumed_root / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination.mkdir(parents=True, exist_ok=True)
    for path in files:
        if not path.exists():
            continue
        target = destination / path.name
        counter = 1
        while target.exists():
            target = destination / f"{path.stem}-{counter}{path.suffix}"
            counter += 1
        shutil.move(str(path), str(target))
    return destination


def resolve_metric_selector(selector: str, metrics_dir: Path) -> Tuple[Dict[str, Any] | None, Path | None, List[str]]:
    files = metric_files(metrics_dir)
    records, warnings = load_metric_records(files, include_annotations=False)
    if not records:
        return None, None, warnings
    if selector == "latest":
        latest_file = max(files, key=lambda path: path.stat().st_mtime)
        for record in records:
            if record.get("sourceFile") == str(latest_file):
                return record, latest_file, warnings
        return None, latest_file, warnings
    for record in records:
        if record.get("recordId") == selector or record.get("sourceFile") == selector:
            return record, Path(str(record.get("sourceFile"))), warnings
    matching_files = [path for path in files if path.name == selector]
    if matching_files:
        selected = matching_files[0]
        for record in records:
            if record.get("sourceFile") == str(selected):
                return record, selected, warnings
    return None, None, warnings


def append_annotation(path: Path, annotation: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(annotation, sort_keys=True) + "\n")
def cmd_metrics(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt metrics", description="Inspect and consolidate agnt invocation metrics.")
    sub = parser.add_subparsers(dest="action")
    for name in ("status", "consolidate", "reset", "prune", "annotate"):
        sub.add_parser(name)
    if not argv:
        parser.print_help()
        return 0
    action, rest = argv[0], argv[1:]
    if action in {"-h", "--help"}:
        parser.print_help()
        return 0
    if action == "status":
        p = argparse.ArgumentParser(prog="agnt metrics status")
        p.add_argument("--metrics-dir")
        args = p.parse_args(rest)
        metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
        files = metric_files(metrics_dir)
        records, warnings = load_metric_records(files)
        print(json.dumps({"metricsDir": str(metrics_dir), "pendingFiles": len(files), "loadedRecords": len(records), "warnings": warnings, "summary": summarize_metrics(records)}, indent=2, sort_keys=True))
        return 0 if not warnings else 1
    if action == "annotate":
        p = argparse.ArgumentParser(prog="agnt metrics annotate")
        p.add_argument("selector", nargs="?", default="latest", help="recordId, source file, basename, or 'latest'")
        p.add_argument("--metrics-dir")
        p.add_argument("--annotations-file")
        p.add_argument("--outcome", choices=sorted(VALID_OUTCOMES))
        p.add_argument("--risk-category")
        p.add_argument("--thinking-level")
        p.add_argument("--human-override", action=argparse.BooleanOptionalAction, default=None)
        p.add_argument("--fallback-used", action=argparse.BooleanOptionalAction, default=None)
        p.add_argument("--notes")
        p.add_argument("--findings-file", help="validated structured review findings JSON")
        args = p.parse_args(rest)
        for flag in ("human-override", "fallback-used"):
            if f"--{flag}" in rest and f"--no-{flag}" in rest:
                p.error(f"use only one of --{flag}/--no-{flag}")
        metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
        record, source_file, warnings = resolve_metric_selector(args.selector, metrics_dir)
        for warning in warnings:
            print(f"agnt metrics: {warning}", file=sys.stderr)
        if record is None:
            print(f"No metric record matched selector {args.selector!r} in {metrics_dir}", file=sys.stderr)
            return 1
        annotation: Dict[str, Any] = {
            "schemaVersion": 1,
            "annotatedAt": utc_now(),
            "recordId": record.get("recordId"),
            "sourceFile": str(source_file) if source_file else record.get("sourceFile"),
        }
        if args.outcome is not None:
            annotation["outcome"] = args.outcome
        if args.risk_category is not None:
            annotation["riskCategory"] = args.risk_category
        if args.thinking_level is not None:
            annotation["thinkingLevel"] = args.thinking_level
        if args.human_override is not None:
            annotation["humanOverride"] = args.human_override
        if args.fallback_used is not None:
            annotation["fallbackUsed"] = args.fallback_used
        if args.notes is not None:
            annotation["notes"] = args.notes
        if args.findings_file is not None:
            try:
                document = load_review_document(args.findings_file)
                annotation.update(
                    review_annotation_fields(
                        document,
                        expected_record_id=str(record.get("recordId") or "") or None,
                        expected_target=str(record.get("target") or "") or None,
                        expected_family=str(record.get("family") or "") or None,
                    )
                )
            except ValueError as exc:
                print(f"agnt metrics: {exc}", file=sys.stderr)
                return 1
        if len(annotation) <= 4:
            p.error("provide at least one annotation field")
        annotations_file = Path(args.annotations_file) if args.annotations_file else default_annotations_file()
        append_annotation(annotations_file, annotation)
        print(json.dumps({"annotationsFile": str(annotations_file), "annotation": annotation}, indent=2, sort_keys=True))
        return 0
    if action == "consolidate":
        p = argparse.ArgumentParser(prog="agnt metrics consolidate")
        p.add_argument("--metrics-dir")
        p.add_argument("--output")
        p.add_argument("--consumed-dir")
        p.add_argument("--stage", action="store_true")
        p.add_argument("--keep-raw", action="store_true")
        args = p.parse_args(rest)
        metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
        output = Path(args.output) if args.output else default_metrics_output()
        consumed_dir = Path(args.consumed_dir) if args.consumed_dir else default_consumed_metrics_dir()
        files = metric_files(metrics_dir)
        if not files:
            print(f"No pending metrics in {metrics_dir}")
            return 0
        records, warnings = load_metric_records(files)
        if warnings:
            for warning in warnings:
                print(f"agnt metrics: {warning}", file=sys.stderr)
        aggregate = {
            "schemaVersion": 1,
            "collectedAt": utc_now(),
            "sinceCommit": current_head(),
            "rawFileCount": len(files),
            "summary": summarize_metrics(records),
            "records": [compact_metric_record(record) for record in records],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(aggregate, sort_keys=True) + "\n")
        if args.stage:
            subprocess.run(["git", "add", str(output)], check=False)
        if not args.keep_raw:
            destination = move_consumed(files, consumed_dir)
            print(f"Consolidated {len(records)} metric records to {output}; consumed raw metrics: {destination}")
        else:
            print(f"Consolidated {len(records)} metric records to {output}; kept raw metrics in {metrics_dir}")
        return 0 if not warnings else 1
    if action == "reset":
        p = argparse.ArgumentParser(prog="agnt metrics reset")
        p.add_argument("--metrics-dir")
        args = p.parse_args(rest)
        metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
        files = metric_files(metrics_dir)
        for path in files:
            path.unlink()
        print(f"Removed {len(files)} pending metric files from {metrics_dir}")
        return 0
    if action == "prune":
        p = argparse.ArgumentParser(prog="agnt metrics prune")
        p.add_argument("--consumed-dir")
        args = p.parse_args(rest)
        consumed_dir = Path(args.consumed_dir) if args.consumed_dir else default_consumed_metrics_dir()
        if consumed_dir.is_dir():
            shutil.rmtree(consumed_dir)
            print(f"Removed consumed metrics directory {consumed_dir}")
        else:
            print(f"No consumed metrics directory at {consumed_dir}")
        return 0
    parser.print_help(sys.stderr)
    return 2
