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


REVIEW_SOFT_SPEND_USD = 12.0
REVIEW_RESERVE_SPEND_USD = 18.0
REVIEW_HARD_CAP_USD = 20.0


def paid_review_spend(records: List[Dict[str, Any]], *, month: str | None = None) -> float:
    """Sum month-to-date marginal review spend without counting subscription
    opportunity-cost estimates. Duplicate records are counted once."""
    selected_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    seen: set[str] = set()
    total = 0.0
    for index, record in enumerate(records):
        if str(record.get("task") or "") != "review":
            continue
        if not str(record.get("startedAt") or "").startswith(selected_month):
            continue
        target = str(record.get("target") or "")
        usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
        venue = common.venue_info(target) or {}
        marginal = target.startswith("openrouter") or venue.get("billingClass") == "metered"
        if is_local_route_target(target) or not marginal:
            continue
        key = str(
            record.get("recordId")
            or record.get("sourceFile")
            or f"{index}:{record.get('startedAt')}:{target}"
        )
        if key in seen:
            continue
        seen.add(key)
        cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else {}
        total += float(cost.get("total") or 0.0)
    return total


def review_monthly_paid_spend() -> float:
    pending, _warnings = load_metric_records(metric_files(default_metrics_dir()))
    measured = paid_review_spend([*load_consolidated_records(), *pending])
    try:
        operator_floor = float(os.environ.get("AGNT_REVIEW_PAID_SPEND_USD") or 0.0)
    except ValueError:
        operator_floor = 0.0
    return max(measured, operator_floor)


def review_policy_targets(meta: Dict[str, Any], risk: str, paid_spend_usd: float) -> tuple[List[str], str]:
    if paid_spend_usd >= REVIEW_HARD_CAP_USD:
        targets = as_list(meta.get("hardCapReview"))
        state = "hard-cap"
    elif paid_spend_usd >= REVIEW_RESERVE_SPEND_USD:
        targets = as_list(meta.get("hardCapReview" if risk == "low" else "reserveReview"))
        state = "reserve"
    else:
        targets = as_list(meta.get(f"review{risk.title()}")) or as_list(meta.get("preferred"))
        state = "soft" if paid_spend_usd >= REVIEW_SOFT_SPEND_USD else "normal"
    return list(dict.fromkeys(targets)), state


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
REVIEW_POLICY_TIER_WEIGHT = 6_000


def choose_thinking_level(risk: str, budget: str, target: str, model_info: Dict[str, Any]) -> str:
    if not model_info.get("reasoning"):
        return "default"
    if risk == "high" or budget == "quality":
        generic = "high"
    elif budget == "cheap" and risk == "low":
        generic = "low"
    else:
        generic = "medium"
    level_map = model_info.get("thinkingLevelMap") if isinstance(model_info.get("thinkingLevelMap"), dict) else {}
    if generic not in level_map:
        return generic
    mapped = level_map[generic]
    if mapped is not None:
        return str(mapped)

    levels = ["minimal", "low", "medium", "high", "xhigh", "max"]
    desired = levels.index(generic)
    for level in levels[desired + 1 :] + list(reversed(levels[:desired])):
        fallback = level_map.get(level)
        if fallback is not None:
            return str(fallback)
    return generic


def diversity_group_for_target(target: str, info: Dict[str, Any] | None = None) -> str:
    if info and info.get("family"):
        return str(info["family"])
    return common.family_for_target(target) or target


def target_is_avoided(target: str, avoid: set[str]) -> bool:
    return target in avoid or any(target.startswith(pattern[:-1]) for pattern in avoid if pattern.endswith("*"))


def route_metric_adjustment(hint: Dict[str, int] | None) -> tuple[int, str | None]:
    if not hint or hint.get("invocations", 0) < ROUTE_DEMOTION_MIN_INVOCATIONS:
        return 0, None
    if hint.get("negative", 0) > hint.get("positive", 0):
        return 10_000, "negative outcome history"
    if hint.get("positive", 0) > hint.get("negative", 0):
        return -50, "positive outcome history"
    return 0, None


def score_candidate(
    *,
    task: str,
    risk: str,
    budget: str,
    target: str,
    info: Dict[str, Any],
    base_rank: int,
    preferred: bool,
    metrics_hint: Dict[str, int] | None,
) -> Dict[str, Any]:
    cost_key = route_cost_rank(target, info, budget)
    metric_adjustment, metric_reason = route_metric_adjustment(metrics_hint)
    if risk == "high" and task in {"orchestration", "implementation", "frontier-advisor"}:
        policy_score = (0 if preferred else 1_000) + base_rank
        policy_reason = "high-risk preferred ordering"
    elif task == "review" and budget == "cheap":
        policy_score = (0 if preferred else REVIEW_POLICY_TIER_WEIGHT) + cost_key[0] * 1_000 + base_rank
        policy_reason = "review policy then cheap cost-class ordering"
    elif budget in {"cheap", "quality"}:
        policy_score = cost_key[0] * 1_000 + base_rank
        policy_reason = f"{budget} budget cost-class ordering"
    else:
        policy_score = base_rank * 100 + cost_key[0]
        policy_reason = "task policy ordering"
    score = policy_score + metric_adjustment
    return {
        "target": target,
        "score": score,
        "scoreBreakdown": {
            "policyScore": policy_score,
            "baseRank": base_rank,
            "costRank": cost_key[0],
            "metricAdjustment": metric_adjustment,
        },
        "scoreReasons": [reason for reason in [policy_reason, metric_reason] if reason],
        "costSortKey": list(cost_key),
        "thinkingLevel": choose_thinking_level(risk, budget, target, info),
        "diversityGroup": diversity_group_for_target(target, info),
        "metricsHint": metrics_hint,
        "preferred": preferred,
    }


def diverse_fanout(candidates: List[Dict[str, Any]], size: int, diversity: str) -> List[Dict[str, Any]]:
    if size <= 0:
        return []
    if diversity == "none":
        return candidates[:size]
    selected: List[Dict[str, Any]] = []
    groups: set[str] = set()
    for candidate in candidates:
        group = str(candidate.get("diversityGroup") or candidate["target"])
        if group in groups:
            continue
        selected.append(candidate)
        groups.add(group)
        if len(selected) >= size:
            return selected
    for candidate in candidates:
        if candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) >= size:
            break
    return selected


def selection_contract(candidate: Dict[str, Any], rejected: List[Dict[str, str]], reasons: List[str]) -> Dict[str, Any]:
    return {
        "target": candidate["target"],
        "thinkingLevel": candidate["thinkingLevel"],
        "reasons": [*reasons, *candidate.get("scoreReasons", [])],
        "rejected": rejected,
        "diversityGroup": candidate["diversityGroup"],
        "score": candidate["score"],
        "scoreBreakdown": candidate["scoreBreakdown"],
    }


def select_model(
    task: str,
    *,
    risk: str = "medium",
    budget: str = "balanced",
    context_tokens: int = 0,
    modality: str = "text",
    local_ok: bool = False,
    model_policy: Dict[str, Any] | None = None,
    fanout_size: int = 0,
    diversity: str | None = None,
    paid_review_spend_usd: float | None = None,
) -> Dict[str, Any]:
    meta, _body = task_meta(task)
    review_budget_state: str | None = None
    review_policy: List[str] = []
    if task == "review":
        if paid_review_spend_usd is None:
            paid_review_spend_usd = review_monthly_paid_spend()
        review_policy, review_budget_state = review_policy_targets(meta, risk, paid_review_spend_usd)
        preferred = review_policy
        qualified = [] if review_budget_state in {"reserve", "hard-cap"} else as_list(meta.get("qualified"))
        if review_budget_state in {"reserve", "hard-cap"}:
            local_ok = True
    else:
        preferred = as_list(meta.get("preferred"))
        qualified = as_list(meta.get("qualified"))
    avoid = set(as_list(meta.get("avoid")))
    policy = model_policy or {}
    avoid_families = {str(item) for item in as_list(policy.get("avoidFamilies"))}
    if isinstance(policy.get("localOk"), bool):
        local_ok = local_ok or bool(policy["localOk"])
    diversity = diversity or str(policy.get("diversity") or "normal")
    ordered: List[str] = []
    for target in [*preferred, *qualified]:
        if target not in ordered:
            ordered.append(target)

    info_by_target = configured_model_info()
    enabled = enabled_models()
    stats = route_metric_stats()
    reasons: List[str] = [f"task policy loaded from {task}"]
    if task == "review":
        reasons.append(
            f"review paid-spend gate: {review_budget_state} at ${float(paid_review_spend_usd or 0.0):.2f} month-to-date"
        )
    if enabled:
        reasons.append("filtered candidates by enabledModels from settings.json")
    if avoid_families:
        reasons.append(f"applied avoidFamilies policy: {', '.join(sorted(avoid_families))}")

    rejected: List[Dict[str, str]] = []
    scored: List[Dict[str, Any]] = []
    for base_rank, target in enumerate(ordered):
        info = info_by_target.get(target, {"target": target, "input": ["text"], "contextWindow": 0})
        group = diversity_group_for_target(target, info)
        if target_is_avoided(target, avoid):
            rejected.append({"target": target, "diversityGroup": group, "reason": "task avoid rule"})
            continue
        if enabled and target not in enabled:
            rejected.append({"target": target, "diversityGroup": group, "reason": "not enabled in settings.json"})
            continue
        if group in avoid_families:
            rejected.append({"target": target, "diversityGroup": group, "reason": "modelPolicy avoidFamilies rule"})
            continue
        if is_local_route_target(target) and not local_ok:
            rejected.append({"target": target, "diversityGroup": group, "reason": "local model requires --local-ok"})
            continue
        modalities = as_list(info.get("input")) or ["text"]
        if modality not in modalities:
            rejected.append({"target": target, "diversityGroup": group, "reason": f"missing modality {modality}"})
            continue
        context_window = int(info.get("contextWindow") or 0)
        if context_tokens and context_window and context_window < context_tokens:
            rejected.append({"target": target, "diversityGroup": group, "reason": f"context window {context_window} < {context_tokens}"})
            continue
        family = common.family_for_target(target) or target
        scored.append(score_candidate(
            task=task,
            risk=risk,
            budget=budget,
            target=target,
            info=info,
            base_rank=base_rank,
            preferred=target in preferred,
            metrics_hint=stats.get(family),
        ))

    if budget in {"cheap", "quality"}:
        reasons.append(f"{budget} budget sorted candidates by cost class")
    if risk == "high" and task in {"orchestration", "implementation", "frontier-advisor"}:
        reasons.append("high-risk control/editing task: preserved preferred frontier ordering")

    scored = sorted(scored, key=lambda item: (item["score"], item["costSortKey"], item["target"]))
    demoted = [item["target"] for item in scored if item["scoreBreakdown"].get("metricAdjustment", 0) >= 10_000]
    if demoted:
        reasons.append(
            "demoted for negative outcome history (rejected/verified-fail > accepted/verified-pass over "
            f">={ROUTE_DEMOTION_MIN_INVOCATIONS} invocations): {', '.join(demoted)}"
        )

    if not scored:
        reasons.append("no candidates satisfy hard constraints")
        return {
            "schemaVersion": 1,
            "task": task,
            "risk": risk,
            "budget": budget,
            "modality": modality,
            "contextTokens": context_tokens,
            "localOk": local_ok,
            "routeStatus": "no_candidate",
            "selected": None,
            "selection": None,
            "fallbacks": [],
            "thinkingLevel": None,
            "fanoutRecommended": False,
            "fanout": [],
            "candidateOrder": [],
            "candidateScores": [],
            "rejectedCandidates": rejected,
            "metricsHints": {},
            "monthlyPaidReviewSpendUsd": paid_review_spend_usd if task == "review" else None,
            "reviewBudgetState": review_budget_state,
            "reviewPolicyTargets": review_policy,
            "reasons": reasons,
            "invokeExample": None,
        }

    selected = scored[0]
    selection = selection_contract(selected, rejected, reasons)
    fanout_recommended = task == "review" or (risk == "high" and task in {"research", "frontier-advisor"})
    fanout_candidates = scored
    if task == "review":
        by_target = {item["target"]: item for item in scored}
        fanout_candidates = [by_target[target] for target in review_policy if target in by_target]
    fanout = [
        selection_contract(item, rejected, reasons)
        for item in diverse_fanout(fanout_candidates, fanout_size, diversity)
    ]
    return {
        "schemaVersion": 1,
        "task": task,
        "risk": risk,
        "budget": budget,
        "modality": modality,
        "contextTokens": context_tokens,
        "localOk": local_ok,
        "routeStatus": "selected",
        "selected": selected["target"],
        "selection": selection,
        "fallbacks": [item["target"] for item in scored[1:3]],
        "thinkingLevel": selected["thinkingLevel"],
        "fanoutRecommended": fanout_recommended,
        "fanout": fanout,
        "candidateOrder": [item["target"] for item in scored],
        "candidateScores": scored,
        "rejectedCandidates": rejected,
        "metricsHints": {item["target"]: item["metricsHint"] for item in scored if item.get("metricsHint")},
        "monthlyPaidReviewSpendUsd": paid_review_spend_usd if task == "review" else None,
        "reviewBudgetState": review_budget_state,
        "reviewPolicyTargets": review_policy,
        "reasons": reasons,
        "invokeExample": (
            f"agnt invoke {'--one-shot ' if task == 'review' else ''}--task {task} "
            f"--risk-category {risk} --thinking-level {selected['thinkingLevel']} "
            f"{selected['target']} <prompt-or-file>"
        ),
    }


def cmd_route(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt route", description="Recommend a model for a task using task policy, constraints, and metrics hints.")
    parser.add_argument("--task", required=True, help="task id from pi/agent/tasks")
    parser.add_argument("--risk", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--context-tokens", type=int, default=0)
    parser.add_argument("--modality", choices=["text", "image", "audio", "video"], default="text")
    parser.add_argument("--local-ok", action="store_true", help="allow local models in recommendations")
    parser.add_argument("--budget", choices=["cheap", "balanced", "quality"], default="balanced")
    parser.add_argument("--fanout-size", type=int, default=0, help="include N scored diverse fanout selections")
    parser.add_argument("--diversity", choices=["none", "normal", "high"], default="normal")
    parser.add_argument(
        "--monthly-paid-spend",
        type=float,
        help="override measured month-to-date marginal paid review spend in USD",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON (always on; kept for compatibility)")
    args = parser.parse_args(argv)

    result = select_model(
        args.task,
        risk=args.risk,
        budget=args.budget,
        context_tokens=args.context_tokens,
        modality=args.modality,
        local_ok=args.local_ok,
        fanout_size=args.fanout_size,
        diversity=args.diversity,
        paid_review_spend_usd=args.monthly_paid_spend,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("routeStatus") == "selected" else 1
