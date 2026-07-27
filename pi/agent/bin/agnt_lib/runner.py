from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict

from .runner_protocol import DEFAULT_BUDGET, read_runner_state, normalize_runner_state, runner_paths, update_runner_state, utc_now as protocol_utc_now, write_runner_state


def utc_now() -> str:
    return protocol_utc_now()


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


def runner_tick(
    *,
    root: Path | str | None = None,
    dry_run: bool = True,
    limit: int = 1,
    beads_runner: Callable[..., Any] | None = None,
    runner_start: Callable[..., Dict[str, Any]] | None = None,
    blocker_creator: Callable[..., Dict[str, Any]] | None = None,
    runs_dir: Path | None = None,
    metrics_dir: Path | None = None,
    worktree_resolver: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]] | None = None,
    maintenance_due_provider: Callable[..., Dict[str, Any]] | None = None,
    maintenance_creator: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    from .runner_scheduler import runner_scheduler_tick

    options = {
        "beads_runner": beads_runner,
        "runner_start": runner_start,
        "blocker_creator": blocker_creator,
        "worktree_resolver": worktree_resolver,
        "maintenance_due_provider": maintenance_due_provider,
        "maintenance_creator": maintenance_creator,
    }
    return runner_scheduler_tick(
        root=root,
        dry_run=dry_run,
        limit=limit,
        runs_dir=runs_dir,
        metrics_dir=metrics_dir,
        status_provider=runner_status,
        **{key: value for key, value in options.items() if value is not None},
    )
__all__ = [
    "runner_status",
    "runner_pause",
    "runner_resume",
    "runner_tick",
    "acquire_runner_lock",
    "release_runner_lock",
    "load_runner_state",
    "save_runner_state",
]
