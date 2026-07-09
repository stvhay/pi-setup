from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .approvals import create_beads_approval_request
from .orchestration import validate_bead_orchestration_metadata
from .runs import default_runs_dir, update_run_result
from .maintenance import maintenance_create_beads, maintenance_due_report
from .worktree_policy import worktree_snapshot_for_bead, write_conflict_for

BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]
RunnerStart = Callable[..., Dict[str, Any]]
BlockerCreator = Callable[..., Dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def runner_dir(root: Path | str | None = None) -> Path:
    base = Path(root).expanduser() if root is not None else Path.cwd()
    return base / ".pi" / "runner"


def state_path(root: Path | str | None = None) -> Path:
    return runner_dir(root) / "state.json"


def lock_path(root: Path | str | None = None) -> Path:
    return runner_dir(root) / "lock.json"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pid_running(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def load_runner_state(root: Path | str | None = None) -> Dict[str, Any]:
    state = _read_json(state_path(root))
    state.setdefault("schemaVersion", 1)
    state.setdefault("paused", False)
    state.setdefault("budget", {"mode": "placeholder", "limitsEnforced": False})
    return state


def save_runner_state(root: Path | str | None, state: Dict[str, Any]) -> Dict[str, Any]:
    state = {"schemaVersion": 1, **state, "updatedAt": utc_now()}
    state.setdefault("budget", {"mode": "placeholder", "limitsEnforced": False})
    _write_json(state_path(root), state)
    return state


def runner_status(root: Path | str | None = None) -> Dict[str, Any]:
    state = load_runner_state(root)
    lock = _read_json(lock_path(root))
    running = _pid_running(lock.get("pid"))
    paused = bool(state.get("paused"))
    status = "running" if running else "paused" if paused else "idle"
    if lock and not running:
        status = "stale" if not paused else "paused"
    return {
        "schemaVersion": 1,
        "status": status,
        "running": running,
        "paused": paused,
        "root": str(Path(root).expanduser() if root is not None else Path.cwd()),
        "statePath": str(state_path(root)),
        "lockPath": str(lock_path(root)),
        "lock": lock or None,
        "budget": state.get("budget") or {"mode": "placeholder", "limitsEnforced": False},
        "updatedAt": state.get("updatedAt"),
    }


def runner_pause(root: Path | str | None = None, *, reason: str | None = None) -> Dict[str, Any]:
    state = load_runner_state(root)
    state["paused"] = True
    state["pauseReason"] = reason or "paused by operator"
    state["pausedAt"] = utc_now()
    saved = save_runner_state(root, state)
    return {"schemaVersion": 1, "paused": True, "state": saved}


def runner_resume(root: Path | str | None = None) -> Dict[str, Any]:
    state = load_runner_state(root)
    state["paused"] = False
    state.pop("pauseReason", None)
    state["resumedAt"] = utc_now()
    saved = save_runner_state(root, state)
    return {"schemaVersion": 1, "paused": False, "state": saved}


def acquire_runner_lock(root: Path | str | None = None, *, owner: str = "agnt-runner") -> Dict[str, Any]:
    path = lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_json(path)
    if existing and _pid_running(existing.get("pid")):
        return {"schemaVersion": 1, "acquired": False, "existing": existing, "lockPath": str(path)}
    if existing:
        try:
            path.unlink()
        except OSError:
            pass
    lock = {"schemaVersion": 1, "owner": owner, "pid": os.getpid(), "startedAt": utc_now(), "root": str(Path(root).expanduser() if root is not None else Path.cwd())}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return {"schemaVersion": 1, "acquired": False, "existing": _read_json(path), "lockPath": str(path)}
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(lock, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return {"schemaVersion": 1, "acquired": True, "lock": lock, "lockPath": str(path)}


def release_runner_lock(root: Path | str | None = None, *, owner: str | None = None) -> Dict[str, Any]:
    path = lock_path(root)
    existing = _read_json(path)
    if not existing:
        return {"schemaVersion": 1, "released": False, "reason": "no lock", "lockPath": str(path)}
    if owner and existing.get("owner") != owner:
        return {"schemaVersion": 1, "released": False, "reason": "owner mismatch", "existing": existing, "lockPath": str(path)}
    try:
        path.unlink()
    except OSError as exc:
        return {"schemaVersion": 1, "released": False, "reason": str(exc), "existing": existing, "lockPath": str(path)}
    return {"schemaVersion": 1, "released": True, "lockPath": str(path)}


def _default_beads_runner(args: List[str]) -> Tuple[int, Any, str]:
    from .work import run_beads_json

    return run_beads_json(args)


def _default_runner_start(bead: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    from .work import run_work

    return run_work(bead, **kwargs)


def _ready_items(beads_runner: BeadsRunner) -> List[Dict[str, Any]]:
    code, data, err = beads_runner(["ready"])
    if code != 0:
        raise RuntimeError(err or "bd ready failed")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get("issue_type") != "epic"]


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


def runner_tick(
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
    maintenance_due_provider: Callable[..., Dict[str, Any]] = maintenance_due_report,
    maintenance_creator: Callable[..., Dict[str, Any]] = maintenance_create_beads,
) -> Dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be positive")
    status = runner_status(root)
    if status.get("paused"):
        return {"schemaVersion": 1, "dryRun": dry_run, "status": status, "actions": [], "skippedReason": "runner paused"}

    items = _ready_items(beads_runner)[:limit]
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
    active_writes: List[Dict[str, Any]] = []
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
        if validation.get("status") == "dispatchable":
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
            if dry_run:
                actions.append({**base, "action": "would_start", "dispatch": normalized, "session": _session_refs("dry-run", bead_id, action), "worktree": worktree})
                if normalized.get("action") == "implement":
                    active_writes.append({"bead": bead_id, "epicId": normalized.get("epicId"), "writeSet": normalized.get("writeSet") or []})
                continue
            run_id = f"runner-{bead_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            refs = _session_refs(run_id, bead_id, action)
            started = runner_start(
                bead,
                action_id=None,
                target=[],
                claim=True,
                close_bead=False,
                model=None,
                runs_dir=runs_dir,
                id_value=run_id,
                metrics_dir=metrics_dir,
                record_session=True,
                session_id=refs["sessionId"],
                session_name=refs["sessionName"],
            )
            bundle = None
            if isinstance(started.get("started"), dict):
                bundle = started["started"].get("bundle")
            elif isinstance(started.get("bundle"), str):
                bundle = started.get("bundle")
            if bundle:
                result_data = None
                invoked = started.get("invoked") if isinstance(started, dict) else None
                if isinstance(invoked, dict) and isinstance(invoked.get("result"), dict):
                    result_data = invoked["result"]
                if result_data:
                    update_run_result(
                        Path(str(bundle)),
                        status=str(result_data.get("status") or "succeeded"),
                        summary=str(result_data.get("summary") or "Runner invocation recorded session refs."),
                        session_ref=refs["sessionRef"],
                        transcript_ref=refs["transcriptRef"],
                    )
            actions.append({**base, "action": "started", "result": started, "worktree": worktree})
            if normalized.get("action") == "implement":
                active_writes.append({"bead": bead_id, "epicId": normalized.get("epicId"), "writeSet": normalized.get("writeSet") or []})
        else:
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
    return {"schemaVersion": 1, "dryRun": dry_run, "status": status, "actions": actions}


def runner_loop(
    *,
    root: Path | str | None = None,
    interval: float = 30.0,
    max_ticks: int | None = None,
    dry_run: bool = False,
    limit: int = 1,
) -> Dict[str, Any]:
    lock = acquire_runner_lock(root, owner="agnt-runner")
    if not lock.get("acquired"):
        return {"schemaVersion": 1, "started": False, "lock": lock, "ticks": []}
    ticks: List[Dict[str, Any]] = []
    try:
        count = 0
        while max_ticks is None or count < max_ticks:
            tick = runner_tick(root=root, dry_run=dry_run, limit=limit)
            ticks.append(tick)
            count += 1
            if max_ticks is not None and count >= max_ticks:
                break
            time.sleep(max(1.0, interval))
    finally:
        release_runner_lock(root, owner="agnt-runner")
    return {"schemaVersion": 1, "started": True, "lock": lock, "ticks": ticks}


__all__ = [
    "runner_status",
    "runner_pause",
    "runner_resume",
    "runner_tick",
    "runner_loop",
    "acquire_runner_lock",
    "release_runner_lock",
    "load_runner_state",
    "save_runner_state",
]
