from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List

import fcntl

API_VERSION = 1
SCHEMA_VERSION = 1
class RunnerStateCorruptionError(RuntimeError):
    """Raised rather than silently replacing an invalid persisted runner state."""


DEFAULT_BUDGET = {
    "mode": "placeholder",
    "limitsEnforced": False,
    "maxSessionUsd": None,
    "maxRunUsd": None,
    "spentUsd": None,
    "remainingUsd": None,
    "cost": {"usd": None, "source": "unknown"},
    "context": {"used": None, "limit": None, "percent": None, "source": "unknown"},
    "warnings": ["cost-unknown", "context-unknown"],
}
_ACTIVE_SUMMARY_KEYS = [
    "bead",
    "slug",
    "epicId",
    "runId",
    "status",
    "model",
    "thinkingLevel",
    "context",
    "cost",
    "bundle",
    "liveLogPath",
    "liveStatusPath",
    "lessonsPath",
    "handoffPath",
    "blockers",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_root(root: Path | str | None = None) -> Path:
    return (Path(root).expanduser() if root is not None else Path.cwd()).resolve()


def runner_dir(root: Path | str | None = None) -> Path:
    return normalize_root(root) / ".pi" / "runner"


def runner_paths(root: Path | str | None = None) -> Dict[str, Path]:
    base = runner_dir(root)
    return {
        "runnerDir": base,
        "servicePath": base / "service.json",
        "tokenPath": base / "token",
        "statePath": base / "state.json",
        "stateGuardPath": base / "state.lock",
        "lockPath": base / "lock.json",
        "eventsPath": base / "events.jsonl",
        "activeDir": base / "active",
    }


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_runner_state(root: Path | str | None = None) -> Dict[str, Any]:
    """Read state without treating a corrupt existing document as empty."""
    path = runner_paths(root)["statePath"]
    if not path.exists():
        return normalize_runner_state({})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerStateCorruptionError(f"invalid runner state at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RunnerStateCorruptionError(f"invalid runner state at {path}: expected JSON object")
    return normalize_runner_state(data)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@contextmanager
def runner_state_guard(root: Path | str | None = None) -> Iterator[None]:
    """Serialize cross-process state read-modify-write transactions.

    The guard is separate from the service ownership lock. It releases
    automatically if its process exits and is held only for a state
    transaction, never for model invocation.
    """
    path = runner_paths(root)["stateGuardPath"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_runner_state(root: Path | str | None, state: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically replace the shared runner state file.

    State readers see either the prior complete JSON document or the next one,
    never a partially-written file after a process interruption.
    """
    path = runner_paths(root)["statePath"]
    path.parent.mkdir(parents=True, exist_ok=True)
    data = normalize_runner_state(state)
    with runner_state_guard(root):
        _write_runner_state_unlocked(path, data)
    return data


def _write_runner_state_unlocked(path: Path, data: Dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def update_runner_state(
    root: Path | str | None,
    update: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply one serialized state transition to the latest persisted state."""
    path = runner_paths(root)["statePath"]
    with runner_state_guard(root):
        current = read_runner_state(root)
        updated = normalize_runner_state(update(current))
        _write_runner_state_unlocked(path, updated)
    return updated


def service_metadata_path(root: Path | str | None = None) -> Path:
    return runner_paths(root)["servicePath"]


def load_service_metadata(root: Path | str | None = None) -> Dict[str, Any]:
    return _read_json(service_metadata_path(root))


def save_service_metadata(root: Path | str | None, metadata: Dict[str, Any]) -> Dict[str, Any]:
    paths = runner_paths(root)
    data = dict(metadata)
    data.pop("token", None)
    data.setdefault("schemaVersion", SCHEMA_VERSION)
    data.setdefault("apiVersion", API_VERSION)
    data["root"] = str(normalize_root(root))
    data.setdefault("tokenPath", str(paths["tokenPath"]))
    data.setdefault("servicePath", str(paths["servicePath"]))
    _write_json(paths["servicePath"], data)
    return data


def redact_service_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}
    for key, value in metadata.items():
        lowered = key.lower()
        if key == "tokenPath":
            redacted[key] = value
        elif "token" in lowered or "secret" in lowered or "password" in lowered:
            redacted[key] = "<redacted>" if value else value
        else:
            redacted[key] = value
    return redacted


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _default_budget() -> Dict[str, Any]:
    return copy.deepcopy(DEFAULT_BUDGET)


def normalize_budget_state(budget: Dict[str, Any] | None = None) -> Dict[str, Any]:
    raw = dict(budget or {}) if isinstance(budget, dict) else {}
    data = _default_budget()
    data.update(raw)

    max_session = _float_or_none(raw.get("maxSessionUsd"))
    max_run = _float_or_none(raw.get("maxRunUsd"))
    spent = _float_or_none(raw.get("spentUsd"))
    remaining_raw = _float_or_none(raw.get("remainingUsd"))
    limits_enforced = bool(raw.get("limitsEnforced"))

    data["limitsEnforced"] = limits_enforced
    data["maxSessionUsd"] = max_session
    data["maxRunUsd"] = max_run
    data["spentUsd"] = spent
    if raw.get("mode"):
        data["mode"] = str(raw.get("mode"))
    else:
        data["mode"] = "configured" if limits_enforced or max_session is not None or max_run is not None else "placeholder"

    if max_session is not None:
        remaining = round(max(max_session - (spent or 0.0), 0.0), 6)
    else:
        remaining = remaining_raw
    data["remainingUsd"] = remaining

    cost = _normalize_cost(raw.get("cost"))
    if cost.get("usd") is None and spent is not None:
        cost = {"usd": spent, "source": str(raw.get("costSource") or "budget-state")}
    data["cost"] = cost

    context = _normalize_context(raw.get("context"))
    context["source"] = str((raw.get("context") or {}).get("source") or "unknown") if isinstance(raw.get("context"), dict) else "unknown"
    data["context"] = context

    warnings = [str(item) for item in raw.get("warnings") or [] if str(item)] if isinstance(raw.get("warnings"), list) else []
    if data["cost"].get("usd") is None:
        warnings.append("cost-unknown")
    if data["context"].get("used") is None and data["context"].get("percent") is None:
        warnings.append("context-unknown")
    if limits_enforced and max_session is None and max_run is None:
        warnings.append("budget-limits-missing")
    if limits_enforced and remaining is not None and remaining <= 0:
        warnings.append("budget-exhausted")
        data.setdefault("blockedReason", "budget-exhausted")
    data["warnings"] = sorted(set(warnings))
    return data


def normalize_runner_state(state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = dict(state or {})
    data["schemaVersion"] = SCHEMA_VERSION
    data.setdefault("paused", False)
    data.setdefault("draining", False)
    raw_leases = data.get("leases")
    if not isinstance(raw_leases, dict):
        data["leases"] = {}
    else:
        # Migrate earlier TTL-shaped lease records on every state read/write.
        data["leases"] = {
            str(lease_id): normalize_lease({**lease, "leaseId": lease.get("leaseId") or lease_id})
            for lease_id, lease in raw_leases.items()
            if isinstance(lease, dict)
        }
    if not isinstance(data.get("activeRuns"), list):
        data["activeRuns"] = []
    data["budget"] = normalize_budget_state(data.get("budget") if isinstance(data.get("budget"), dict) else None)
    if "acceptingNewWork" not in data:
        data["acceptingNewWork"] = not bool(data.get("paused")) and not bool(data.get("draining"))
    return data


def normalize_lease(payload: Dict[str, Any], *, now: str | None = None) -> Dict[str, Any]:
    """Normalize a connected-client record without a TTL lifecycle watchdog."""
    session_id = str(payload.get("sessionId") or payload.get("leaseId") or "").strip()
    client = str(payload.get("client") or "unknown").strip() or "unknown"
    lease_id = str(payload.get("leaseId") or session_id or client).strip()
    attached = _parse_utc(now or payload.get("attachedAt"))
    observed = _parse_utc(payload.get("lastSeenAt")) if payload.get("lastSeenAt") else attached
    return {
        "schemaVersion": SCHEMA_VERSION,
        "leaseId": lease_id,
        "sessionId": session_id or lease_id,
        "client": client,
        "attachedAt": _format_utc(attached),
        "lastSeenAt": _format_utc(observed),
    }


def _slug(text: str, *, max_words: int = 6) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:max_words]) or "work"


def _normalize_context(raw: Any) -> Dict[str, Any]:
    context = dict(raw) if isinstance(raw, dict) else {}
    used = context.get("used")
    limit = context.get("limit")
    percent = context.get("percent")
    if percent is None and isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
        percent = round((float(used) / float(limit)) * 100.0, 2)
    return {"used": used, "limit": limit, "percent": percent}


def _normalize_cost(raw: Any) -> Dict[str, Any]:
    cost = dict(raw) if isinstance(raw, dict) else {}
    return {"usd": cost.get("usd"), "source": cost.get("source") or "unknown"}


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def normalize_active_run_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(snapshot)
    title = str(data.get("title") or data.get("slug") or data.get("bead") or "work")
    data["schemaVersion"] = SCHEMA_VERSION
    data.setdefault("status", "unknown")
    data["slug"] = str(data.get("slug") or _slug(title))
    data["context"] = _normalize_context(data.get("context"))
    data["cost"] = _normalize_cost(data.get("cost"))
    data["blockers"] = _string_list(data.get("blockers"))
    return data


def active_run_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_active_run_snapshot(snapshot)
    summary = {key: normalized.get(key) for key in _ACTIVE_SUMMARY_KEYS}
    for optional in ("liveLogPath", "liveStatusPath", "lessonsPath", "handoffPath"):
        if summary.get(optional) is None:
            summary.pop(optional, None)
    return summary


def _event_lines(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def append_runner_event(root: Path | str | None, event: Dict[str, Any], *, now: str | None = None) -> Dict[str, Any]:
    path = runner_paths(root)["eventsPath"]
    lines = _event_lines(path)
    offset = len(lines)
    row = {"schemaVersion": SCHEMA_VERSION, **dict(event), "offset": offset, "timestamp": now or utc_now()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def read_runner_events(root: Path | str | None, *, since: int = 0, limit: int | None = None) -> Dict[str, Any]:
    path = runner_paths(root)["eventsPath"]
    lines = _event_lines(path)
    start = max(0, int(since or 0))
    selected = lines[start:]
    if limit is not None:
        selected = selected[: max(0, int(limit))]
    events: List[Dict[str, Any]] = []
    for line in selected:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return {"schemaVersion": SCHEMA_VERSION, "events": events, "nextOffset": len(lines)}


__all__ = [
    "API_VERSION",
    "DEFAULT_BUDGET",
    "active_run_summary",
    "append_runner_event",
    "load_service_metadata",
    "normalize_active_run_snapshot",
    "normalize_budget_state",
    "normalize_lease",
    "normalize_root",
    "normalize_runner_state",
    "read_runner_events",
    "redact_service_metadata",
    "runner_dir",
    "runner_paths",
    "save_service_metadata",
    "service_metadata_path",
    "utc_now",
]
