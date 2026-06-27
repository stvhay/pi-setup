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

from .core import ROOT, die
from .metrics import default_metrics_dir, default_metrics_output, load_metric_records, metric_files
from .tasks import as_list, task_meta

def enabled_models() -> set[str]:
    settings_path = ROOT / "settings.json"
    if not settings_path.is_file():
        return set()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    values = data.get("enabledModels") if isinstance(data, dict) else None
    return {str(value) for value in values} if isinstance(values, list) else set()


def configured_model_info() -> Dict[str, Dict[str, Any]]:
    info: Dict[str, Dict[str, Any]] = {}
    models_path = ROOT / "models.json"
    if models_path.is_file():
        try:
            data = json.loads(models_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        providers = data.get("providers") if isinstance(data, dict) else None
        if isinstance(providers, dict):
            for provider, provider_data in providers.items():
                models = provider_data.get("models") if isinstance(provider_data, dict) else None
                if not isinstance(models, list):
                    continue
                for item in models:
                    if not isinstance(item, dict) or not item.get("id"):
                        continue
                    target = f"{provider}/{item['id']}"
                    info[target] = dict(item)
                    info[target]["target"] = target
                    info[target]["provider"] = provider
    for family_id, family in (common.load_catalog().get("families") or {}).items():
        for venue in (family.get("venues") or []) if isinstance(family, dict) else []:
            if not isinstance(venue, dict) or not venue.get("target"):
                continue
            target = str(venue["target"])
            merged = {**venue, **info.get(target, {})}
            merged.setdefault("target", target)
            merged["family"] = family_id
            info[target] = merged
    return info


def is_local_route_target(target: str) -> bool:
    return target.startswith("ollama/") or target.startswith("olla-local/")


def route_cost_rank(target: str, info: Dict[str, Any], budget: str) -> Tuple[int, str]:
    cost_class = str(info.get("costClass") or "")
    costs = info.get("cost") if isinstance(info.get("cost"), dict) else {}
    total_rate = float(costs.get("input") or 0.0) + float(costs.get("output") or 0.0)
    if budget == "quality":
        quality_rank = 0 if cost_class == "frontier" else 1 if cost_class == "balanced" else 2 if cost_class == "cheap" else 3
        return quality_rank, target
    if cost_class == "local" or is_local_route_target(target):
        return 0, target
    if cost_class == "cheap":
        return 1, target
    if total_rate > 0:
        return 2, f"{total_rate:012.6f}:{target}"
    if cost_class == "balanced":
        return 3, target
    if cost_class == "frontier":
        return 4, target
    return 5, target


def load_consolidated_records(path: Path | None = None) -> List[Dict[str, Any]]:
    """Compact records from the global consolidated store (one aggregate per line)."""
    output = path or default_metrics_output()
    records: List[Dict[str, Any]] = []
    if not output.is_file():
        return records
    for line in output.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            for record in data.get("records") or []:
                if isinstance(record, dict):
                    records.append(record)
    return records


def stats_family(record: Dict[str, Any]) -> str:
    target = str(record.get("target") or "")
    return str(record.get("family") or "") or common.family_for_target(target) or target


def route_metric_stats() -> Dict[str, Dict[str, int]]:
    """Outcome history aggregated by model family, so evidence gathered on one
    venue (e.g. local Ollama) informs routing to every venue of the same weights.
    Reads the durable global store plus this project's pending records."""
    pending, _warnings = load_metric_records(metric_files(default_metrics_dir()))
    stats: Dict[str, Dict[str, int]] = {}
    for record in [*load_consolidated_records(), *pending]:
        family = stats_family(record)
        if not family:
            continue
        bucket = stats.setdefault(family, {"positive": 0, "negative": 0, "escalated": 0, "invocations": 0})
        bucket["invocations"] += 1
        outcome = str(record.get("outcome") or "unknown")
        if outcome in {"accepted", "verified-pass"}:
            bucket["positive"] += 1
        elif outcome in {"rejected", "verified-fail"}:
            bucket["negative"] += 1
        elif outcome == "escalated":
            bucket["escalated"] += 1
    return stats


ROUTE_DEMOTION_MIN_INVOCATIONS = 5


def choose_thinking_level(risk: str, budget: str, target: str, model_info: Dict[str, Any]) -> str:
    if not model_info.get("reasoning"):
        return "default"
    if risk == "high" or budget == "quality":
        return "high"
    if budget == "cheap" and risk == "low":
        return "low"
    return "medium"


def cmd_route(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt route", description="Recommend a model for a task using task policy, constraints, and metrics hints.")
    parser.add_argument("--task", required=True, help="task id from pi/agent/tasks")
    parser.add_argument("--risk", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--context-tokens", type=int, default=0)
    parser.add_argument("--modality", choices=["text", "image", "audio", "video"], default="text")
    parser.add_argument("--local-ok", action="store_true", help="allow local models in recommendations")
    parser.add_argument("--budget", choices=["cheap", "balanced", "quality"], default="balanced")
    parser.add_argument("--json", action="store_true", help="emit JSON (always on; kept for compatibility)")
    args = parser.parse_args(argv)

    meta, _body = task_meta(args.task)
    preferred = as_list(meta.get("preferred"))
    qualified = as_list(meta.get("qualified"))
    avoid = set(as_list(meta.get("avoid")))
    ordered = []
    for target in [*preferred, *qualified]:
        if target not in ordered:
            ordered.append(target)

    info_by_target = configured_model_info()
    enabled = enabled_models()
    reasons: List[str] = [f"task policy loaded from {args.task}"]
    if enabled:
        reasons.append("filtered candidates by enabledModels from settings.json")
    filtered: List[str] = []
    rejected: List[Dict[str, str]] = []
    for target in ordered:
        info = info_by_target.get(target, {"target": target, "input": ["text"], "contextWindow": 0})
        if target in avoid or any(target.startswith(pattern[:-1]) for pattern in avoid if pattern.endswith("*")):
            rejected.append({"target": target, "reason": "task avoid rule"})
            continue
        if enabled and target not in enabled:
            rejected.append({"target": target, "reason": "not enabled in settings.json"})
            continue
        if is_local_route_target(target) and not args.local_ok:
            rejected.append({"target": target, "reason": "local model requires --local-ok"})
            continue
        modalities = as_list(info.get("input")) or ["text"]
        if args.modality not in modalities:
            rejected.append({"target": target, "reason": f"missing modality {args.modality}"})
            continue
        context_window = int(info.get("contextWindow") or 0)
        if args.context_tokens and context_window and context_window < args.context_tokens:
            rejected.append({"target": target, "reason": f"context window {context_window} < {args.context_tokens}"})
            continue
        filtered.append(target)

    if not filtered:
        reasons.append("no candidates satisfy hard constraints")
        result = {
            "schemaVersion": 1,
            "task": args.task,
            "risk": args.risk,
            "budget": args.budget,
            "modality": args.modality,
            "contextTokens": args.context_tokens,
            "localOk": args.local_ok,
            "routeStatus": "no_candidate",
            "selected": None,
            "fallbacks": [],
            "thinkingLevel": None,
            "fanoutRecommended": False,
            "candidateOrder": [],
            "rejectedCandidates": rejected,
            "metricsHints": {},
            "reasons": reasons,
            "invokeExample": None,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    if args.risk == "high" and args.task in {"orchestration", "implementation", "frontier-advisor"}:
        high_priority = [target for target in filtered if target in preferred]
        if high_priority:
            filtered = high_priority + [target for target in filtered if target not in high_priority]
            reasons.append("high-risk control/editing task: preserved preferred frontier ordering")
    elif args.budget in {"cheap", "quality"}:
        filtered = sorted(filtered, key=lambda target: route_cost_rank(target, info_by_target.get(target, {}), args.budget))
        reasons.append(f"{args.budget} budget sorted candidates by cost class")

    stats = route_metric_stats()

    def hint_for(target: str) -> Dict[str, int] | None:
        return stats.get(common.family_for_target(target) or target)

    # Observed-outcome feedback: demote candidates whose family has a clearly
    # negative track record. Evidence beats static preference, transparently.
    demoted = [
        target
        for target in filtered
        if (hint := hint_for(target))
        and hint["invocations"] >= ROUTE_DEMOTION_MIN_INVOCATIONS
        and hint["negative"] > hint["positive"]
    ]
    if demoted and len(demoted) < len(filtered):
        filtered = [target for target in filtered if target not in demoted] + demoted
        reasons.append(
            "demoted for negative outcome history (rejected/verified-fail > accepted/verified-pass over "
            f">={ROUTE_DEMOTION_MIN_INVOCATIONS} invocations): {', '.join(demoted)}"
        )

    selected = filtered[0]
    fallback = filtered[1:3]
    selected_info = info_by_target.get(selected, {"target": selected})
    thinking = choose_thinking_level(args.risk, args.budget, selected, selected_info)
    fanout = args.task == "review" or (args.risk == "high" and args.task in {"research", "frontier-advisor"})
    result = {
        "schemaVersion": 1,
        "task": args.task,
        "risk": args.risk,
        "budget": args.budget,
        "modality": args.modality,
        "contextTokens": args.context_tokens,
        "localOk": args.local_ok,
        "routeStatus": "selected",
        "selected": selected,
        "fallbacks": fallback,
        "thinkingLevel": thinking,
        "fanoutRecommended": fanout,
        "candidateOrder": filtered,
        "rejectedCandidates": rejected,
        "metricsHints": {target: hint for target in filtered if (hint := hint_for(target))},
        "reasons": reasons,
        "invokeExample": f"agnt invoke --task {args.task} --risk-category {args.risk} --thinking-level {thinking} {selected} <prompt-or-file>",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
