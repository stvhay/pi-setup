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
from .runner_protocol import DEFAULT_BUDGET, read_runner_state, normalize_runner_state, runner_paths, update_runner_state, utc_now as protocol_utc_now, write_runner_state
from .worktree_policy import worktree_snapshot_for_bead, write_conflict_for

BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]
RunnerStart = Callable[..., Dict[str, Any]]
BlockerCreator = Callable[..., Dict[str, Any]]


def utc_now() -> str:
    return protocol_utc_now()


def runner_dir(root: Path | str | None = None) -> Path:
    return runner_paths(root)["runnerDir"]


def state_path(root: Path | str | None = None) -> Path:
    return runner_paths(root)["statePath"]


def lock_path(root: Path | str | None = None) -> Path:
    return runner_paths(root)["lockPath"]


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
    return read_runner_state(root)


def save_runner_state(root: Path | str | None, state: Dict[str, Any]) -> Dict[str, Any]:
    saved = normalize_runner_state({"schemaVersion": 1, **state, "updatedAt": utc_now()})
    saved.setdefault("budget", dict(DEFAULT_BUDGET))
    return write_runner_state(root, saved)


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
        "budget": state.get("budget") or dict(DEFAULT_BUDGET),
        "updatedAt": state.get("updatedAt"),
    }


def runner_pause(root: Path | str | None = None, *, reason: str | None = None) -> Dict[str, Any]:
    def pause(state: Dict[str, Any]) -> Dict[str, Any]:
        state["paused"] = True
        state["acceptingNewWork"] = False
        state["pauseReason"] = reason or "paused by operator"
        state["pausedAt"] = utc_now()
        state["updatedAt"] = utc_now()
        return state

    saved = update_runner_state(root, pause)
    return {"schemaVersion": 1, "paused": True, "state": saved}


def runner_resume(root: Path | str | None = None) -> Dict[str, Any]:
    def resume(state: Dict[str, Any]) -> Dict[str, Any]:
        state["paused"] = False
        state["draining"] = False
        state["acceptingNewWork"] = True
        state.pop("pauseReason", None)
        state.pop("drainReason", None)
        state.pop("drainRequestedAt", None)
        state["resumedAt"] = utc_now()
        state["updatedAt"] = utc_now()
        return state

    saved = update_runner_state(root, resume)
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
    from .runner_scheduler import runner_scheduler_tick

    return runner_scheduler_tick(
        root=root,
        dry_run=dry_run,
        limit=limit,
        beads_runner=beads_runner,
        runner_start=runner_start,
        blocker_creator=blocker_creator,
        runs_dir=runs_dir,
        metrics_dir=metrics_dir,
        worktree_resolver=worktree_resolver,
        maintenance_due_provider=maintenance_due_provider,
        maintenance_creator=maintenance_creator,
        status_provider=runner_status,
    )

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
