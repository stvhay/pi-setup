from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .approvals import create_beads_approval_request
from .maintenance import maintenance_create_beads, maintenance_due_report
from .orchestration import READ_ONLY_ACTIONS, validate_bead_orchestration_metadata
from .runner_protocol import normalize_active_run_snapshot, normalize_budget_state, normalize_runner_state, read_runner_state, runner_paths, update_runner_state, utc_now
from .runs import update_run_result, write_yaml_json
from .worktree_policy import checkpoint_epic_worktree, worktree_snapshot_for_bead, write_conflict_for

BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]
RunnerStart = Callable[..., Dict[str, Any]]
BlockerCreator = Callable[..., Dict[str, Any]]
StatusProvider = Callable[[Path | str | None], Dict[str, Any]]
CheckpointHandler = Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Dict[str, Any]]

DEFAULT_CONCURRENCY = 1
DEFAULT_RETRY_LIMIT = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 60
TERMINAL_STATUSES = {"succeeded", "failed", "blocked", "superseded"}


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_scheduler_state(root: Path | str | None = None) -> Dict[str, Any]:
    state = read_runner_state(root)
    if not isinstance(state.get("attempts"), dict):
        state["attempts"] = {}
    return state


def save_scheduler_state(root: Path | str | None, state: Dict[str, Any], *, now: datetime | None = None) -> Dict[str, Any]:
    """Persist scheduler-owned fields without overwriting live service controls."""
    data = normalize_runner_state(state)
    if not isinstance(data.get("attempts"), dict):
        data["attempts"] = {}
    timestamp = _format_time(_coerce_now(now))

    def merge_scheduler_state(current: Dict[str, Any]) -> Dict[str, Any]:
        current["attempts"] = data["attempts"]
        current["activeRuns"] = data["activeRuns"]
        current["budget"] = data["budget"]
        # A scheduler budget guard may pause the runner; never replay a stale
        # false value that could clear an operator's concurrent pause.
        if data.get("paused"):
            current["paused"] = True
            current["acceptingNewWork"] = False
            for key in ("pauseReason", "pausedAt"):
                if data.get(key):
                    current[key] = data[key]
        current["updatedAt"] = timestamp
        return current

    return update_runner_state(root, merge_scheduler_state)


def _default_status_provider(root: Path | str | None = None) -> Dict[str, Any]:
    state = load_scheduler_state(root)
    return {
        "schemaVersion": 1,
        "status": "paused" if state.get("paused") else "idle",
        "running": False,
        "paused": bool(state.get("paused")),
        "root": str(Path(root).expanduser().resolve() if root is not None else Path.cwd()),
        "budget": state.get("budget"),
        "updatedAt": state.get("updatedAt"),
    }


def _default_beads_runner(args: List[str]) -> Tuple[int, Any, str]:
    from .work import run_beads_json

    return run_beads_json(args)


def _default_runner_start(bead: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    from .work import run_work

    return run_work(bead, **kwargs)


def _default_checkpoint_handler(worktree: Dict[str, Any], bead: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    return checkpoint_epic_worktree(
        worktree,
        bead_id=str(bead.get("id") or ""),
        write_set=list(normalized.get("writeSet") or []),
    )


def _is_runner_candidate(bead: Dict[str, Any]) -> bool:
    issue_type = str(bead.get("issue_type") or bead.get("type") or "").lower()
    if issue_type in {"epic", "decision"}:
        return False
    labels = {str(label) for label in bead.get("labels") or []}
    if labels.intersection({"human", "human-gate", "approval", "ask", "question"}):
        return False
    return True


def _ready_items(beads_runner: BeadsRunner) -> List[Dict[str, Any]]:
    code, data, err = beads_runner(["ready"])
    if code != 0:
        raise RuntimeError(err or "bd ready failed")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and _is_runner_candidate(item)]


def _has_pi_metadata(bead: Dict[str, Any]) -> bool:
    raw = bead.get("metadata")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return True
    if not isinstance(raw, dict):
        return False
    return isinstance(raw.get("pi"), dict)


def _validation_context(bead: Dict[str, Any], validation: Dict[str, Any]) -> str:
    parts = [
        f"Runner could not dispatch {bead.get('id')}: metadata status {validation.get('status')}.",
    ]
    for key in ("failures", "humanActions", "blockers"):
        values = validation.get(key) or []
        if values:
            parts.append(f"{key}: " + "; ".join(str(item) for item in values))
    return "\n".join(parts)


def _blocker_preview(bead: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, str]:
    return {
        "action": f"Resolve runner dispatch blocker for {bead.get('id')}",
        "scope": "Beads metadata and approval state for this work item only.",
        "consequences": f"Work remains blocked until metadata status is dispatchable; current status is {validation.get('status')}.",
        "reversibility": "The blocker is a Beads decision record and can be resolved or superseded with an auditable note.",
        "closeoutPath": "Fix metadata or record approval, then resolve the blocker and rerun the runner tick.",
    }


def _session_refs(run_id: str | None, bead_id: str | None, action: str | None) -> Dict[str, str | None]:
    if not run_id:
        return {"sessionId": None, "sessionRef": None, "transcriptRef": None, "sessionName": None}
    safe_id = str(run_id).replace("/", "-").replace(":", "-")
    session_id = f"run-{safe_id}"
    return {
        "sessionId": session_id,
        "sessionRef": f"pi-session-id:{session_id}",
        "transcriptRef": f"pi-session-transcript:{session_id}",
        "sessionName": f"run:{run_id} bead:{bead_id or 'unknown'} action:{action or 'unknown'}",
    }


def _active_writes_from_state(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    active_writes: List[Dict[str, Any]] = []
    for item in state.get("activeRuns") or []:
        if not isinstance(item, dict):
            continue
        write_set = item.get("writeSet") or item.get("write_set") or []
        if write_set:
            active_writes.append({"bead": item.get("bead"), "epicId": item.get("epicId"), "writeSet": write_set})
    return active_writes


def _active_beads(state: Dict[str, Any]) -> set[str]:
    return {str(item.get("bead")) for item in state.get("activeRuns") or [] if isinstance(item, dict) and item.get("bead")}


def _concurrency(state: Dict[str, Any], limit: int) -> int:
    raw = state.get("concurrency", DEFAULT_CONCURRENCY)
    value = raw if isinstance(raw, int) and raw > 0 else DEFAULT_CONCURRENCY
    return max(1, min(limit, value))


def _retry_limit(state: Dict[str, Any]) -> int:
    raw = state.get("retryLimit", DEFAULT_RETRY_LIMIT)
    return raw if isinstance(raw, int) and raw >= 0 else DEFAULT_RETRY_LIMIT


def _retry_backoff(state: Dict[str, Any]) -> int:
    raw = state.get("retryBackoffSeconds", DEFAULT_RETRY_BACKOFF_SECONDS)
    return raw if isinstance(raw, int) and raw > 0 else DEFAULT_RETRY_BACKOFF_SECONDS


def _retry_gate(state: Dict[str, Any], bead_id: str, now: datetime) -> Dict[str, Any] | None:
    attempts = state.get("attempts") if isinstance(state.get("attempts"), dict) else {}
    attempt = attempts.get(bead_id) if isinstance(attempts.get(bead_id), dict) else None
    if not attempt:
        return None
    count = int(attempt.get("count") or 0)
    if count >= _retry_limit(state):
        return {"action": "retry_exhausted", "attempt": attempt, "retryLimit": _retry_limit(state)}
    next_at = _parse_time(attempt.get("nextEligibleAt"))
    if next_at and now < next_at:
        return {"action": "retry_deferred", "attempt": attempt, "nextEligibleAt": attempt.get("nextEligibleAt")}
    return None


def _record_failure_attempt(root: Path | str | None, state: Dict[str, Any], bead_id: str, error: str, now: datetime) -> Dict[str, Any]:
    attempts = dict(state.get("attempts") or {})
    previous = attempts.get(bead_id) if isinstance(attempts.get(bead_id), dict) else {}
    count = int(previous.get("count") or 0) + 1
    next_at = now + timedelta(seconds=_retry_backoff(state) * count)
    attempts[bead_id] = {
        "count": count,
        "lastError": error,
        "lastFailedAt": _format_time(now),
        "nextEligibleAt": _format_time(next_at),
    }
    state["attempts"] = attempts
    return save_scheduler_state(root, state, now=now)


def _clear_attempt(root: Path | str | None, state: Dict[str, Any], bead_id: str, now: datetime) -> Dict[str, Any]:
    attempts = dict(state.get("attempts") or {})
    if bead_id in attempts:
        attempts.pop(bead_id, None)
        state["attempts"] = attempts
        return save_scheduler_state(root, state, now=now)
    return state


def _active_snapshot_path(root: Path | str | None, run_id: str) -> Path:
    safe = run_id.replace("/", "-").replace(":", "-")
    return runner_paths(root)["activeDir"] / f"{safe}.json"


def _record_active_run(
    root: Path | str | None,
    state: Dict[str, Any],
    *,
    bead: Dict[str, Any],
    validation: Dict[str, Any],
    run_id: str,
    status: str,
    now: datetime,
) -> Dict[str, Any]:
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    bundle_path = runner_paths(root)["runnerDir"].parent / "runs" / run_id
    snapshot = normalize_active_run_snapshot(
        {
            "bead": str(bead.get("id") or ""),
            "title": bead.get("title"),
            "epicId": normalized.get("epicId"),
            "runId": run_id,
            "status": status,
            "startedAt": _format_time(now),
            "writeSet": normalized.get("writeSet") or [],
            "bundle": str(bundle_path),
            "liveLogPath": str(bundle_path / "live" / "session.jsonl"),
            "liveStatusPath": str(bundle_path / "live" / "status.json"),
            "lessonsPath": str(bundle_path / "artifacts" / "lessons.md"),
            "handoffPath": str(bundle_path / "artifacts" / "handoff.md"),
            "blockers": [],
        }
    )
    path = _active_snapshot_path(root, run_id)
    _write_json(path, snapshot)
    active = [item for item in state.get("activeRuns") or [] if isinstance(item, dict) and item.get("runId") != run_id]
    active.append(snapshot)
    state["activeRuns"] = active
    return save_scheduler_state(root, state, now=now)


def _clear_active_run(root: Path | str | None, state: Dict[str, Any], run_id: str, now: datetime) -> Dict[str, Any]:
    try:
        _active_snapshot_path(root, run_id).unlink()
    except FileNotFoundError:
        pass
    active = [item for item in state.get("activeRuns") or [] if not (isinstance(item, dict) and item.get("runId") == run_id)]
    state["activeRuns"] = active
    return save_scheduler_state(root, state, now=now)


def _record_checkpoint_evidence(bundle: Path | None, checkpoint: Dict[str, Any] | None) -> None:
    if bundle is None or not checkpoint or not checkpoint.get("ok"):
        return
    artifact = bundle / "artifacts" / "checkpoint.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _write_json(artifact, checkpoint)
    invocation_path = bundle / "invocation.yaml"
    invocation = _artifact_json(invocation_path)
    if invocation:
        invocation["continuationCheckpoint"] = checkpoint
        write_yaml_json(invocation_path, invocation)
    approval_ref = checkpoint.get("approvalRef")
    update_run_result(
        bundle,
        evidence=["artifacts/checkpoint.json"],
        artifacts=["artifacts/checkpoint.json"],
        approval_refs=[approval_ref] if isinstance(approval_ref, str) and approval_ref else None,
    )


def _maybe_update_run_result(bundle: Any, started: Dict[str, Any], refs: Dict[str, str | None]) -> None:
    if not bundle:
        return
    invoked = started.get("invoked") if isinstance(started, dict) else None
    result_data = invoked.get("result") if isinstance(invoked, dict) and isinstance(invoked.get("result"), dict) else None
    if not result_data:
        return
    update_run_result(
        Path(str(bundle)),
        status=str(result_data.get("status") or "succeeded"),
        summary=str(result_data.get("summary") or "Runner invocation recorded session refs."),
        session_ref=refs["sessionRef"],
        transcript_ref=refs["transcriptRef"],
    )


def _budget_block_reason(state: Dict[str, Any]) -> str | None:
    budget = normalize_budget_state(state.get("budget") if isinstance(state.get("budget"), dict) else None)
    state["budget"] = budget
    if not budget.get("limitsEnforced"):
        return None
    remaining = budget.get("remainingUsd")
    if isinstance(remaining, (int, float)) and remaining <= 0:
        return "budget-exhausted"
    max_run = budget.get("maxRunUsd")
    if isinstance(remaining, (int, float)) and isinstance(max_run, (int, float)) and remaining < max_run:
        return "budget-run-limit-exceeds-remaining"
    if "budget-limits-missing" in (budget.get("warnings") or []):
        return "budget-limits-missing"
    return None


def _budget_preview(bead_id: str, reason: str, budget: Dict[str, Any]) -> Dict[str, str]:
    return {
        "action": f"Resolve runner budget blocker for {bead_id}",
        "scope": "Runner budget state and dispatch policy for new work only; active work is not killed.",
        "consequences": f"No new runner work starts while budget reason {reason} remains active. Remaining USD: {budget.get('remainingUsd')}",
        "reversibility": "Adjust or acknowledge budget state, then resume the runner and rerun scheduling.",
        "closeoutPath": "Budget state allows dispatch or an operator records an explicit decision.",
    }


def _block_for_budget(
    root: Path | str | None,
    state: Dict[str, Any],
    *,
    base: Dict[str, Any],
    dry_run: bool,
    blocker_creator: BlockerCreator,
    now: datetime,
    reason: str,
) -> Dict[str, Any]:
    budget = normalize_budget_state({**state.get("budget", {}), "blockedReason": reason})
    state["budget"] = budget
    context = f"Runner budget blocks new dispatch for {base.get('bead')}: {reason}."
    if dry_run:
        return {**base, "action": "would_block_budget", "context": context, "budget": budget}
    state["paused"] = True
    state["acceptingNewWork"] = False
    state["pauseReason"] = reason
    state["pausedAt"] = _format_time(now)
    state["budget"] = budget
    save_scheduler_state(root, state, now=now)
    blocker = blocker_creator(
        kind="question",
        target_bead=str(base.get("bead") or ""),
        question=f"Resolve runner budget blocker for {base.get('bead')}",
        context=context,
        options=["resolved", "defer"],
        default="defer",
        requesting_run=None,
        preview=_budget_preview(str(base.get("bead") or ""), reason, budget),
        run_bundle=None,
    )
    return {**base, "action": "blocked_budget", "context": context, "budget": budget, "blocker": blocker}


def _resource_unknown(run_id: str | None = None) -> Dict[str, Any]:
    return {
        "runId": run_id,
        "model": None,
        "thinkingLevel": None,
        "context": {"used": None, "limit": None, "percent": None, "source": "unknown"},
        "cost": {"usd": None, "source": "unknown"},
    }


def _artifact_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _number_or_none(value: Any) -> float | int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _run_resource_summary(bundle: Path | None, *, run_id: str) -> Dict[str, Any]:
    resources = _resource_unknown(run_id)
    if bundle is None:
        return resources
    invocation = _artifact_json(bundle / "invocation.yaml")
    result = _artifact_json(bundle / "result.yaml")
    model_selection = invocation.get("modelSelection") if isinstance(invocation.get("modelSelection"), dict) else {}
    resources["model"] = invocation.get("selectedModel") or invocation.get("model") or model_selection.get("selected")
    resources["thinkingLevel"] = invocation.get("thinkingLevel") or model_selection.get("thinkingLevel")

    metrics_ref = result.get("metricsRef")
    metrics = _artifact_json(bundle / str(metrics_ref)) if isinstance(metrics_ref, str) and metrics_ref else {}
    usage = metrics.get("usage") if isinstance(metrics.get("usage"), dict) else {}
    cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else {}
    cost_total = _number_or_none(cost.get("total"))
    if cost_total is not None:
        resources["cost"] = {"usd": round(float(cost_total), 6), "source": "metrics"}
    token_total = usage.get("totalTokens")
    if token_total is None:
        token_total = metrics.get("estimatedInputTokens")
    token_value = _number_or_none(token_total)
    if token_value is not None:
        resources["context"] = {"used": int(token_value), "limit": None, "percent": None, "source": "metrics"}
    if not resources.get("model") and metrics.get("target"):
        resources["model"] = metrics.get("target")
    if not resources.get("thinkingLevel") and metrics.get("thinkingLevel"):
        resources["thinkingLevel"] = metrics.get("thinkingLevel")
    return resources


def _apply_resource_usage(root: Path | str | None, state: Dict[str, Any], resources: Dict[str, Any], *, now: datetime) -> Dict[str, Any]:
    budget = normalize_budget_state(state.get("budget") if isinstance(state.get("budget"), dict) else None)
    cost = resources.get("cost") if isinstance(resources.get("cost"), dict) else {}
    usd = cost.get("usd")
    if isinstance(usd, (int, float)) and not isinstance(usd, bool):
        budget["spentUsd"] = round(float(budget.get("spentUsd") or 0.0) + float(usd), 6)
        budget["cost"] = {"usd": budget["spentUsd"], "source": cost.get("source") or "metrics"}
    context = resources.get("context") if isinstance(resources.get("context"), dict) else {}
    if context.get("used") is not None or context.get("percent") is not None:
        budget["context"] = dict(context)
    budget["lastRun"] = resources
    state["budget"] = normalize_budget_state(budget)
    return save_scheduler_state(root, state, now=now)


def runner_scheduler_tick(
    *,
    root: Path | str | None = None,
    dry_run: bool = True,
    limit: int = 1,
    beads_runner: BeadsRunner = _default_beads_runner,
    runner_start: RunnerStart = _default_runner_start,
    blocker_creator: BlockerCreator = create_beads_approval_request,
    runs_dir: Path | None = None,
    metrics_dir: Path | None = None,
    worktree_resolver: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]] = worktree_snapshot_for_bead,
    checkpoint_handler: CheckpointHandler = _default_checkpoint_handler,
    maintenance_due_provider: Callable[..., Dict[str, Any]] = maintenance_due_report,
    maintenance_creator: Callable[..., Dict[str, Any]] = maintenance_create_beads,
    status_provider: StatusProvider = _default_status_provider,
    now: datetime | None = None,
) -> Dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be positive")
    timestamp = _coerce_now(now)
    state = load_scheduler_state(root)
    status = status_provider(root)
    if status.get("paused") or state.get("paused"):
        return {"schemaVersion": 1, "dryRun": dry_run, "status": status, "actions": [], "skippedReason": "runner paused"}
    if state.get("draining"):
        return {"schemaVersion": 1, "dryRun": dry_run, "status": status, "actions": [], "skippedReason": "runner draining"}

    items = _ready_items(beads_runner)
    actions: List[Dict[str, Any]] = []
    if not items:
        due_report = maintenance_due_provider(root=root, runs_dir=runs_dir, beads_runner=beads_runner)
        if due_report.get("due"):
            if dry_run:
                maintenance = maintenance_creator(due_report, dry_run=True, beads_runner=beads_runner)
                actions.append({"action": "would_create_maintenance", "maintenance": maintenance, "due": due_report})
            else:
                maintenance = maintenance_creator(due_report, dry_run=False, beads_runner=beads_runner)
                actions.append({"action": "created_maintenance", "maintenance": maintenance, "due": due_report})
        return {"schemaVersion": 1, "dryRun": dry_run, "status": status, "actions": actions}

    active_writes = _active_writes_from_state(state)
    active_beads = _active_beads(state)
    max_concurrency = _concurrency(state, limit)
    occupied_slots = len(state.get("activeRuns") or [])

    for bead in items:
        validation = validate_bead_orchestration_metadata(bead)
        normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
        bead_id = str(bead.get("id") or "")
        action = str(normalized.get("action") or "")
        base = {
            "bead": bead_id,
            "title": bead.get("title"),
            "validationStatus": validation.get("status"),
            "sessionPolicy": normalized.get("sessionPolicy") or "recorded",
            "memoryPolicy": normalized.get("memoryPolicy") or "auto",
        }
        if bead_id in active_beads:
            actions.append({**base, "action": "already_active", "context": f"{bead_id} already has an active runner slot"})
            continue
        if not _has_pi_metadata(bead):
            actions.append({**base, "action": "skipped_unmanaged", "context": f"{bead_id} has no metadata.pi dispatch contract"})
            continue
        retry = _retry_gate(state, bead_id, timestamp)
        if retry:
            actions.append({**base, **retry})
            continue
        if validation.get("status") == "needs-human" and not validation.get("blockers"):
            context = _validation_context(bead, validation)
            actions.append({**base, "action": "awaiting_approval", "context": context})
            continue
        if validation.get("status") != "dispatchable":
            context = _validation_context(bead, validation)
            if dry_run:
                actions.append({**base, "action": "would_block", "context": context})
                continue
            blocker = blocker_creator(
                kind="question",
                target_bead=bead_id,
                question=f"Resolve runner dispatch blocker for {bead_id}",
                context=context,
                options=["resolved", "defer"],
                default="defer",
                requesting_run=None,
                preview=_blocker_preview(bead, validation),
                run_bundle=None,
            )
            actions.append({**base, "action": "blocked", "context": context, "blocker": blocker})
            continue

        budget_reason = _budget_block_reason(state)
        if budget_reason:
            actions.append(
                _block_for_budget(
                    root,
                    state,
                    base=base,
                    dry_run=dry_run,
                    blocker_creator=blocker_creator,
                    now=timestamp,
                    reason=budget_reason,
                )
            )
            continue

        worktree = worktree_resolver(bead, validation)
        checkpoint = None
        if worktree.get("status") == "checkpoint-required":
            context = f"Runner could not dispatch {bead_id}: approved continuation checkpoint is required."
            if dry_run:
                actions.append({**base, "action": "would_checkpoint", "context": context, "worktree": worktree})
                continue
            checkpoint = checkpoint_handler(worktree, bead, validation)
            if not checkpoint.get("ok"):
                error = str(checkpoint.get("reason") or "continuation checkpoint failed")
                state = _record_failure_attempt(root, state, bead_id, error, timestamp)
                actions.append({**base, "action": "checkpoint_failed", "error": error, "worktree": worktree, "checkpoint": checkpoint})
                continue
            worktree = worktree_resolver(bead, validation)
        if not bool(worktree.get("dispatchable", False)):
            context = f"Runner could not dispatch {bead_id}: worktree status {worktree.get('status')}. {worktree.get('reason') or ''}".strip()
            if dry_run:
                actions.append({**base, "action": "would_block", "context": context, "worktree": worktree})
                continue
            blocker = blocker_creator(
                kind="question",
                target_bead=bead_id,
                question=f"Resolve runner worktree blocker for {bead_id}",
                context=context,
                options=["resolved", "defer"],
                default="defer",
                requesting_run=None,
                preview=_blocker_preview(bead, {"status": worktree.get("status"), "blockers": [context]}),
                run_bundle=None,
            )
            actions.append({**base, "action": "blocked", "context": context, "worktree": worktree, "blocker": blocker})
            continue

        conflict = write_conflict_for(bead, validation, active_writes)
        if conflict:
            context = f"Runner serialized overlapping writeSet in epic {conflict.get('epicId')}: {', '.join(conflict.get('overlap') or [])}"
            if dry_run:
                actions.append({**base, "action": "would_add_dependency", "context": context, "worktree": worktree, **conflict})
                continue
            dep_code, dep_data, dep_err = beads_runner(["dep", str(conflict.get("blockedBy")), "--blocks", bead_id])
            if dep_code != 0:
                actions.append({**base, "action": "dependency_failed", "context": dep_err, "worktree": worktree, **conflict})
            else:
                actions.append({**base, "action": "dependency_added", "dependency": dep_data, "context": context, "worktree": worktree, **conflict})
            continue

        if occupied_slots >= max_concurrency:
            actions.append({**base, "action": "deferred_concurrency", "context": f"runner concurrency limit reached ({max_concurrency})"})
            break

        if dry_run:
            actions.append({**base, "action": "would_start", "dispatch": normalized, "session": _session_refs("dry-run", bead_id, action), "worktree": worktree})
            occupied_slots += 1
            if normalized.get("action") == "implement":
                active_writes.append({"bead": bead_id, "epicId": normalized.get("epicId"), "writeSet": normalized.get("writeSet") or []})
            continue

        run_id = f"runner-{bead_id}-{timestamp.strftime('%Y%m%d%H%M%S')}"
        refs = _session_refs(run_id, bead_id, action)
        state = _record_active_run(root, state, bead=bead, validation=validation, run_id=run_id, status="running", now=timestamp)
        occupied_slots += 1
        active_beads.add(bead_id)
        if normalized.get("action") == "implement":
            active_writes.append({"bead": bead_id, "epicId": normalized.get("epicId"), "writeSet": normalized.get("writeSet") or []})
        try:
            started = runner_start(
                bead,
                action_id=action or None,
                target=[],
                claim=True,
                close_bead=action in READ_ONLY_ACTIONS,
                model=None,
                runs_dir=runs_dir,
                id_value=run_id,
                metrics_dir=metrics_dir,
                record_session=True,
                session_id=refs["sessionId"],
                session_name=refs["sessionName"],
            )
        except Exception as exc:  # runner infrastructure failure, not terminal worker result
            state = _clear_active_run(root, state, run_id, timestamp)
            state = _record_failure_attempt(root, state, bead_id, str(exc), timestamp)
            actions.append({**base, "action": "start_failed", "error": str(exc), "worktree": worktree})
            continue
        finally:
            if _active_snapshot_path(root, run_id).exists():
                state = _clear_active_run(root, state, run_id, timestamp)

        if isinstance(started, dict) and isinstance(started.get("error"), str) and started["error"].strip():
            error = started["error"].strip()
            state = _record_failure_attempt(root, state, bead_id, error, timestamp)
            actions.append({**base, "action": "start_failed", "error": error, "result": started, "worktree": worktree})
            continue

        bundle = None
        if isinstance(started, dict) and isinstance(started.get("started"), dict):
            bundle = started["started"].get("bundle")
        elif isinstance(started, dict) and isinstance(started.get("bundle"), str):
            bundle = started.get("bundle")
        bundle_path = Path(str(bundle)) if bundle else None
        _record_checkpoint_evidence(bundle_path, checkpoint)
        _maybe_update_run_result(bundle, started if isinstance(started, dict) else {}, refs)
        resources = _run_resource_summary(bundle_path, run_id=run_id)
        state = _apply_resource_usage(root, state, resources, now=timestamp)
        invoked = started.get("invoked") if isinstance(started, dict) and isinstance(started.get("invoked"), dict) else {}
        exit_code = invoked.get("exitCode")
        if isinstance(exit_code, int) and exit_code != 0:
            semantic_outcome = str(invoked.get("semanticOutcome") or "invalid")
            result_data = invoked.get("result") if isinstance(invoked.get("result"), dict) else {}
            summary = str(result_data.get("summary") or f"worker invocation exited {exit_code}")
            error = f"{summary} Semantic outcome: {semantic_outcome}."
            state = _record_failure_attempt(root, state, bead_id, error, timestamp)
            context = (
                f"Runner worker failed for {bead_id}: {error} "
                f"Inspect run bundle {bundle or 'unavailable'}. Create a fresh retry execution bead or explicitly close out the failure."
            )
            blocker = blocker_creator(
                kind="question",
                target_bead=bead_id,
                question=f"Resolve failed runner attempt for {bead_id}",
                context=context,
                options=["create a fresh retry task", "accept failure and close out", "defer"],
                default="defer",
                requesting_run=run_id,
                preview={
                    "action": f"Resolve failed runner attempt for {bead_id}",
                    "scope": f"Only the failed attempt {run_id} and its target Bead; no automatic source or runner-state mutation.",
                    "consequences": "The failed Bead remains open and blocked until a human chooses retry or closeout.",
                    "reversibility": "The decision can defer; a retry requires a fresh execution bead or an audited requeue action.",
                    "closeoutPath": "Inspect the cited run bundle, then create a fresh retry or explicitly close the failed work.",
                },
                run_bundle=None,
            )
            decision_bead = blocker.get("decisionBead") if isinstance(blocker, dict) else None
            if bundle_path is not None and isinstance(decision_bead, str) and decision_bead:
                update_run_result(bundle_path, decision_refs=[decision_bead])
            actions.append({
                **base,
                "action": "worker_failed",
                "error": error,
                "semanticOutcome": semantic_outcome,
                "result": started,
                "resources": resources,
                "worktree": worktree,
                "checkpoint": checkpoint,
                "blocker": blocker,
            })
            continue
        state = _clear_attempt(root, state, bead_id, timestamp)
        actions.append({**base, "action": "started", "result": started, "resources": resources, "worktree": worktree, "checkpoint": checkpoint})

    return {"schemaVersion": 1, "dryRun": dry_run, "status": status, "actions": actions}


__all__ = ["runner_scheduler_tick", "load_scheduler_state", "save_scheduler_state"]
