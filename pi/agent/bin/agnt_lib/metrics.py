from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import _agnt_common as common

from .core import ROOT, VALID_OUTCOMES, capture, die, split_target
from .review import load_review_document, review_annotation_fields

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Model facts (family/venue equivalence, opportunity-cost rates, GPU watt
# assumptions) live in catalog.json; these are last-resort code fallbacks.
FALLBACK_GPU_WATTS = 34.2
FALLBACK_ELECTRICITY_USD_PER_KWH = 0.1304


def empty_usage() -> Dict[str, Any]:
    return {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "totalTokens": 0,
        "cost": {"input": 0.0, "output": 0.0, "cacheRead": 0.0, "cacheWrite": 0.0, "total": 0.0},
    }


def openrouter_model_prices() -> Dict[str, Dict[str, float]]:
    prices: Dict[str, Dict[str, float]] = {}
    path = ROOT / "models.json"
    if not path.is_file():
        return prices
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return prices
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, dict):
        return prices
    for provider, config in providers.items():
        if not isinstance(config, dict):
            continue
        for model in config.get("models") or []:
            if not isinstance(model, dict) or not isinstance(model.get("cost"), dict):
                continue
            target = f"{provider}/{model.get('id')}"
            prices[target] = {key: float(model["cost"].get(key) or 0.0) for key in ("input", "output", "cacheRead", "cacheWrite")}
    return prices


def is_local_target(target: str) -> bool:
    provider = target.split("/", 1)[0]
    return provider in {"ollama", "olla-local"}


def priced_usage(usage: Dict[str, Any], prices: Dict[str, float]) -> Dict[str, float]:
    estimated = {key: int(usage.get(key) or 0) * float(prices.get(key) or 0.0) / 1_000_000 for key in ("input", "output", "cacheRead", "cacheWrite")}
    estimated["total"] = sum(estimated.values())
    return estimated


def local_gpu_watts(target: str) -> Tuple[float, str]:
    value = os.environ.get("AGNT_LOCAL_GPU_WATTS")
    if value:
        try:
            return float(value), "env:AGNT_LOCAL_GPU_WATTS"
        except ValueError:
            pass
    if os.environ.get("AGNT_USE_NVIDIA_SMI") == "1":
        try:
            out = capture(["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"])
            readings = [float(line.strip()) for line in out.splitlines() if line.strip()]
            if readings:
                return max(readings), "nvidia-smi-local-host"
        except (OSError, subprocess.CalledProcessError, ValueError):
            pass
    info = common.venue_info(target)
    if info and info.get("gpuWatts") is not None:
        return float(info["gpuWatts"]), "catalog-venue"
    provider = target.split("/", 1)[0]
    watts = common.provider_gpu_watts(provider)
    if watts is not None:
        return watts, f"catalog-provider-default:{provider}"
    return FALLBACK_GPU_WATTS, "assumed-local-gpu"


def electricity_usd_per_kwh() -> float:
    value = os.environ.get("AGNT_ELECTRICITY_USD_PER_KWH")
    if value:
        try:
            return float(value)
        except ValueError:
            pass
    catalog_value = common.default_electricity_usd_per_kwh()
    return catalog_value if catalog_value is not None else FALLBACK_ELECTRICITY_USD_PER_KWH


def apply_assumed_cost(usage: Dict[str, Any] | None, target: str | None, elapsed_ms: int | None = None) -> Dict[str, Any] | None:
    if not isinstance(usage, dict) or not target:
        return usage
    cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else None
    if cost and float(cost.get("total") or 0.0) > 0:
        usage.setdefault("costSource", "provider-reported")
        return usage
    prices = openrouter_model_prices()
    if is_local_target(target):
        usage.setdefault("cost", {"input": 0.0, "output": 0.0, "cacheRead": 0.0, "cacheWrite": 0.0, "total": 0.0})
        usage["costSource"] = "local-free"
        usage["costEstimated"] = False
        proxy = common.proxy_for_target(target)
        if proxy:
            proxy_target = proxy["target"]
            proxy_prices = prices.get(proxy_target)
            if proxy_prices:
                usage["opportunityCost"] = {
                    "source": "openrouter-proxy",
                    "proxyTarget": proxy_target,
                    "proxyQuality": proxy.get("quality"),
                    "unit": "USD_PER_MILLION_TOKENS",
                    "rates": proxy_prices,
                    "cost": priced_usage(usage, proxy_prices),
                }
        if elapsed_ms is not None:
            watts, watts_source = local_gpu_watts(target)
            kwh = (watts / 1000.0) * (max(elapsed_ms, 0) / 3_600_000.0)
            price = electricity_usd_per_kwh()
            usage["localCompute"] = {
                "source": "rough-gpu-marginal-estimate",
                "elapsedMs": elapsed_ms,
                "gpuWatts": watts,
                "gpuWattsSource": watts_source,
                "electricityUsdPerKwh": price,
                "estimatedEnergyKWh": kwh,
                "estimatedEnergyCostUsd": kwh * price,
            }
        return usage
    target_prices = prices.get(target) or common.opportunity_rates(target)
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
    return {
        "total": 0,
        "unverified": 0,
        "confirmed": 0,
        "refuted": 0,
        "unresolved": 0,
        "bySeverity": {},
    }


def add_review_finding_stats(total: Dict[str, Any], value: Dict[str, Any]) -> None:
    for key in ("total", "unverified", "confirmed", "refuted", "unresolved"):
        total[key] += int(value.get(key) or 0)
    severities = value.get("bySeverity") if isinstance(value.get("bySeverity"), dict) else {}
    for severity, count in severities.items():
        total["bySeverity"][str(severity)] = int(total["bySeverity"].get(str(severity)) or 0) + int(count or 0)


def record_id(started_at: str, target: str, task: str | None) -> str:
    raw = f"{started_at}|{target}|{task or ''}"
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


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
    risk_category: str | None = None,
    thinking_level: str | None = None,
    outcome: str = "unknown",
    human_override: bool = False,
    fallback_used: bool = False,
    invocation_mode: str = "agentic",
) -> Dict[str, Any]:
    provider, model = split_target(target)
    usage = apply_assumed_cost(usage, target, elapsed_ms)
    if outcome not in VALID_OUTCOMES:
        outcome = "unknown"
    return {
        "schemaVersion": 1,
        "recordId": record_id(started_at, target, task),
        "startedAt": started_at,
        "endedAt": ended_at,
        "elapsedMs": elapsed_ms,
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
        return Path(capture(["git", "rev-parse", "--show-toplevel"]).strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(os.getcwd())


def default_metrics_dir() -> Path:
    return git_root() / ".pi" / "metrics" / "invocations"


def default_consumed_metrics_dir() -> Path:
    return git_root() / ".pi" / "metrics" / "consumed"


def default_metrics_output() -> Path:
    # Consolidated metrics are runtime state shared across projects: they feed
    # routing decisions everywhere, so they live in ~/.pi, not in any repo.
    value = os.environ.get("AGNT_METRICS_OUTPUT")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".pi" / "metrics" / "agent-invocations.jsonl"


def default_annotations_file() -> Path:
    return git_root() / ".pi" / "metrics" / "annotations.jsonl"
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
            target = str(data.get("target") or f"{data.get('provider')}/{data.get('model')}")
            data["usage"] = apply_assumed_cost(data.get("usage"), target, int(data.get("elapsedMs") or 0))
            data.setdefault("family", common.family_for_target(target))
            data.setdefault("sourceFile", str(path))
            data.setdefault("outcome", "unknown")
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


def usage_summary(records: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    total = empty_usage()
    seen = False
    for record in records:
        usage = record.get("usage")
        if isinstance(usage, dict):
            add_usage(total, usage)
            seen = True
    return total if seen else None


def summarize_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_model: Dict[str, Dict[str, Any]] = {}
    by_task: Dict[str, Dict[str, Any]] = {}
    exit_codes: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    outcome_counts: Dict[str, int] = {}
    risk_counts: Dict[str, int] = {}
    thinking_counts: Dict[str, int] = {}
    review_scope_counts: Dict[str, int] = {}
    review_finding_counts = empty_review_finding_stats()
    benchmark_counts: Dict[str, int] = {}
    kind_counts: Dict[str, int] = {}
    human_overrides = 0
    fallback_uses = 0
    context_chars = 0
    estimated_input_tokens = 0
    verification = {"passed": 0, "failed": 0, "commands": 0}
    rework_cycles = 0
    benchmark_elapsed_ms = 0
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
        benchmark = record.get("benchmark")
        if benchmark:
            benchmark_key = str(benchmark)
            benchmark_counts[benchmark_key] = benchmark_counts.get(benchmark_key, 0) + 1
        kind = record.get("kind")
        if kind:
            kind_key = str(kind)
            kind_counts[kind_key] = kind_counts.get(kind_key, 0) + 1
        rework_cycles += int(record.get("reworkCycles") or 0)
        benchmark_elapsed_ms += int(record.get("benchmarkElapsedMs") or 0)
        for check in record.get("verification") or []:
            if isinstance(check, dict):
                verification["commands"] += 1
                if check.get("passed"):
                    verification["passed"] += 1
                else:
                    verification["failed"] += 1
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
        "outcomes": outcome_counts,
        "riskCategories": risk_counts,
        "thinkingLevels": thinking_counts,
        "reviewScopes": review_scope_counts,
        "reviewFindings": review_finding_counts,
        "humanOverrides": human_overrides,
        "fallbackUses": fallback_uses,
        "contextChars": context_chars,
        "estimatedInputTokens": estimated_input_tokens,
        "benchmarks": benchmark_counts,
        "kinds": kind_counts,
        "verification": verification,
        "reworkCycles": rework_cycles,
        "benchmarkElapsedMs": benchmark_elapsed_ms,
        "usage": usage_summary(records),
        "byModel": by_model,
        "byTask": by_task,
    }


def current_head() -> str | None:
    try:
        return capture(["git", "rev-parse", "HEAD"]).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def compact_metric_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "recordId": record.get("recordId"),
        "startedAt": record.get("startedAt"),
        "endedAt": record.get("endedAt"),
        "elapsedMs": record.get("elapsedMs"),
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
        "benchmark": record.get("benchmark"),
        "benchmarkedTarget": record.get("benchmarkedTarget"),
        "reworkCycles": record.get("reworkCycles"),
        "verification": record.get("verification"),
        "codeQuality": record.get("codeQuality"),
        "benchmarkElapsedMs": record.get("benchmarkElapsedMs"),
    }


def session_dir_name(cwd: Path) -> str:
    return "--" + str(cwd.resolve()).strip("/").replace("/", "-") + "--"


def session_dirs_for_cwd(cwd: Path) -> List[Path]:
    base = Path.home() / ".pi" / "agent" / "sessions"
    names = [session_dir_name(cwd)]
    try:
        names.append(session_dir_name(git_root()))
    except Exception:
        pass
    dirs: List[Path] = []
    for name in names:
        path = base / name
        if path.is_dir() and path not in dirs:
            dirs.append(path)
    return dirs


def latest_session_file(cwd: Path) -> Path | None:
    files: List[Path] = []
    for directory in session_dirs_for_cwd(cwd):
        files.extend(directory.glob("*.jsonl"))
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def session_import_state_path() -> Path:
    return git_root() / ".pi" / "metrics" / "session-import-state.json"


def load_session_import_state() -> Dict[str, Any]:
    path = session_import_state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_session_import_state(state: Dict[str, Any]) -> None:
    write_json(session_import_state_path(), state)


def parse_pi_session_file(path: Path, since_timestamp: str | None = None) -> Tuple[Dict[str, Any], str | None, int]:
    usage = empty_usage()
    usage_seen = False
    by_model: Dict[str, Dict[str, Any]] = {}
    assistant_messages = 0
    last_timestamp = since_timestamp
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = entry.get("timestamp")
        if since_timestamp and timestamp and timestamp <= since_timestamp:
            continue
        message = entry.get("message") if entry.get("type") == "message" else None
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        assistant_messages += 1
        last_timestamp = timestamp or last_timestamp
        msg_usage = message.get("usage")
        provider = str(message.get("provider") or "unknown")
        model = str(message.get("model") or "unknown")
        target = f"{provider}/{model}"
        bucket = by_model.setdefault(target, {"assistantMessages": 0, "usage": empty_usage(), "usageSeen": False})
        bucket["assistantMessages"] += 1
        if isinstance(msg_usage, dict):
            msg_usage = apply_assumed_cost(dict(msg_usage), target) or msg_usage
            add_usage(usage, msg_usage)
            add_usage(bucket["usage"], msg_usage)
            usage_seen = True
            bucket["usageSeen"] = True
    for bucket in by_model.values():
        if not bucket.pop("usageSeen"):
            bucket["usage"] = None
    return {"usage": usage if usage_seen else None, "assistantMessages": assistant_messages, "byModel": by_model}, last_timestamp, assistant_messages


def write_metric_record(metrics_dir: Path, name: str, record: Dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = metrics_dir / f"{stamp}-{name}.metrics.json"
    write_json(path, record)
    return path


def run_check(command: List[str]) -> Dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        "command": command,
        "exitCode": proc.returncode,
        "passed": proc.returncode == 0,
        "elapsedMs": int((time.monotonic() - started) * 1000),
        "stdoutTail": proc.stdout[-1000:],
        "stderrTail": proc.stderr[-1000:],
    }


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
    for name in ("status", "consolidate", "reset", "prune", "import-session", "annotate"):
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
    if action == "import-session":
        p = argparse.ArgumentParser(prog="agnt metrics import-session")
        p.add_argument("--latest", action="store_true", help="import the latest Pi session for cwd")
        p.add_argument("--session-file", help="explicit session JSONL file")
        p.add_argument("--cwd", default=os.getcwd(), help="cwd used to locate latest session")
        p.add_argument("--kind", default="orchestration", help="metric kind label")
        p.add_argument("--metrics-dir")
        p.add_argument("--no-dedupe", action="store_true", help="import whole session without updating dedupe state")
        args = p.parse_args(rest)
        if not args.latest and not args.session_file:
            p.error("use --latest or --session-file")
        session_file = Path(args.session_file).expanduser() if args.session_file else latest_session_file(Path(args.cwd))
        if not session_file or not session_file.is_file():
            print("No session file found")
            return 0
        state = load_session_import_state()
        key = str(session_file.resolve())
        since = None if args.no_dedupe else state.get(key, {}).get("lastTimestamp")
        parsed, last_timestamp, count = parse_pi_session_file(session_file, since)
        if count == 0:
            print(f"No new assistant messages in {session_file}")
            return 0
        record = {
            "schemaVersion": 1,
            "kind": args.kind,
            "task": args.kind,
            "status": "observed",
            "startedAt": since,
            "endedAt": last_timestamp,
            "elapsedMs": 0,
            "target": "main-session",
            "provider": "pi-session",
            "model": "mixed",
            "exitCode": 0,
            "usageSource": "session-jsonl",
            "usage": parsed["usage"],
            "responseChars": 0,
            "stderrChars": 0,
            "sessionFile": str(session_file),
            "assistantMessages": parsed["assistantMessages"],
            "byModel": parsed["byModel"],
        }
        metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
        out = write_metric_record(metrics_dir, "session", record)
        if not args.no_dedupe and last_timestamp:
            state[key] = {"lastTimestamp": last_timestamp, "importedAt": utc_now()}
            save_session_import_state(state)
        print(f"Imported {count} assistant messages from {session_file} to {out}")
        return 0
    if action == "annotate":
        p = argparse.ArgumentParser(prog="agnt metrics annotate")
        p.add_argument("selector", nargs="?", default="latest", help="recordId, source file, basename, or 'latest'")
        p.add_argument("--metrics-dir")
        p.add_argument("--annotations-file")
        p.add_argument("--outcome", choices=sorted(VALID_OUTCOMES))
        p.add_argument("--risk-category")
        p.add_argument("--thinking-level")
        p.add_argument("--human-override", action="store_true")
        p.add_argument("--no-human-override", action="store_true")
        p.add_argument("--fallback-used", action="store_true")
        p.add_argument("--no-fallback-used", action="store_true")
        p.add_argument("--notes")
        p.add_argument("--findings-file", help="validated structured review findings JSON")
        args = p.parse_args(rest)
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
        if args.human_override and args.no_human_override:
            p.error("use only one of --human-override/--no-human-override")
        if args.human_override:
            annotation["humanOverride"] = True
        if args.no_human_override:
            annotation["humanOverride"] = False
        if args.fallback_used and args.no_fallback_used:
            p.error("use only one of --fallback-used/--no-fallback-used")
        if args.fallback_used:
            annotation["fallbackUsed"] = True
        if args.no_fallback_used:
            annotation["fallbackUsed"] = False
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
