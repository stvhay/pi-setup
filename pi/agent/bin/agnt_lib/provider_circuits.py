from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from .runtime_paths import resolve_runtime_directory

REASONS = {"quota", "credit", "authentication", "availability"}
TTL_SECONDS = {
    "quota": 30 * 60,
    "credit": 30 * 60,
    "authentication": 15 * 60,
    "availability": 2 * 60,
}
MAX_TTL_SECONDS = 60 * 60
MAX_CIRCUITS = 64
MAX_ERROR_CHARS = 12_000
_PROVIDER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _parse_stamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _validate_provider(provider: str) -> str:
    if not _PROVIDER.fullmatch(provider):
        raise ValueError("provider venue must be a bounded provider id, not a target or path")
    return provider


def default_provider_circuit_state() -> Path:
    override = os.environ.get("AGNT_PROVIDER_CIRCUIT_DIR")
    directory = Path(override).expanduser() if override else resolve_runtime_directory(
        "provider-circuits",
        cwd=Path.home(),
    )
    return directory / "state.json"


def classify_provider_failure(message: object) -> str | None:
    text = str(message or "")[:MAX_ERROR_CHARS].lower()
    if not text:
        return None
    if re.search(r"\b(?:insufficient[_ -]?quota|quota (?:has been )?exceeded|monthly limit|key limit exceeded|usage limit exceeded)\b", text):
        return "quota"
    if re.search(r"\b(?:http\s*)?402\b|\binsufficient (?:credits?|credit balance)\b|\bcredit balance\b|\bavailable credits? can only cover\b|\bcan afford (?:only )?\d+ tokens\b", text):
        return "credit"
    if re.search(r"\b(?:http\s*)?401\b|\bunauthorized\b|\bauthentication failed\b|\b(?:invalid|missing|expired|revoked) (?:api[ _-]?key|token|credentials?)\b|\bno (?:api[ _-]?key|auth credentials?|credentials?)(?: found)?\b", text):
        return "authentication"
    if re.search(r"\b(?:http(?: status)?|status code|returned(?: http)?)\s*[:=]?\s*(?:502|503|504)\b|\b(?:502 bad gateway|503 service unavailable|504 gateway timeout)\b", text):
        return "availability"
    return None


def _state_path(path: Path | str | None) -> Path:
    return Path(path).expanduser() if path is not None else default_provider_circuit_state()


def _prepare_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise OSError("provider circuit parent is not a private directory")
    path.parent.chmod(0o700)


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    _prepare_parent(path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    if path.is_symlink() or lock_path.is_symlink():
        raise OSError("provider circuit state must not be a symlink")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    os.chmod(lock_path, 0o600)
    with os.fdopen(descriptor, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    values = data.get("circuits") if isinstance(data, dict) else None
    if not isinstance(values, list):
        return []
    circuits: list[dict[str, Any]] = []
    for value in values[:MAX_CIRCUITS]:
        if not isinstance(value, dict):
            continue
        provider = value.get("provider")
        reason = value.get("reason")
        opened = _parse_stamp(value.get("openedAt"))
        expires = _parse_stamp(value.get("expiresAt"))
        if not isinstance(provider, str) or not _PROVIDER.fullmatch(provider) or reason not in REASONS or not opened or not expires:
            continue
        circuits.append({
            "provider": provider,
            "reason": reason,
            "openedAt": _stamp(opened),
            "expiresAt": _stamp(expires),
        })
    return circuits


def _write(path: Path, circuits: list[dict[str, Any]]) -> None:
    payload = {"schemaVersion": 1, "circuits": sorted(circuits, key=lambda item: item["provider"])}
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def _active(circuits: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    return [item for item in circuits if (_parse_stamp(item.get("expiresAt")) or now) > now]


def _mutate(
    state_path: Path | str | None,
    now: datetime,
    change: Callable[[list[dict[str, Any]]], Any],
) -> Any:
    path = _state_path(state_path)
    with _locked(path):
        circuits = _active(_load(path), now)
        result = change(circuits)
        _write(path, circuits)
        return result


def active_provider_circuits(
    *,
    now: datetime | None = None,
    state_path: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    current = _utc(now)
    path = _state_path(state_path)
    if not path.exists() and not path.is_symlink():
        return {}
    with _locked(path):
        stored = _load(path)
        circuits = _active(stored, current)
        if len(circuits) != len(stored):
            _write(path, circuits)
        return {item["provider"]: dict(item) for item in sorted(circuits, key=lambda item: item["provider"])}


def open_provider_circuit(
    provider: str,
    reason: str,
    *,
    now: datetime | None = None,
    state_path: Path | str | None = None,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    provider = _validate_provider(provider)
    if reason not in REASONS:
        raise ValueError(f"unsupported provider failure class: {reason}")
    current = _utc(now)
    ttl = min(MAX_TTL_SECONDS, max(1, int(ttl_seconds or TTL_SECONDS[reason])))
    record = {
        "provider": provider,
        "reason": reason,
        "openedAt": _stamp(current),
        "expiresAt": _stamp(current + timedelta(seconds=ttl)),
    }

    def change(circuits: list[dict[str, Any]]) -> dict[str, Any]:
        circuits[:] = [item for item in circuits if item["provider"] != provider]
        if len(circuits) >= MAX_CIRCUITS:
            circuits.sort(key=lambda item: item["expiresAt"])
            del circuits[0]
        circuits.append(record)
        return dict(record)

    return _mutate(state_path, current, change)


def close_provider_circuit(
    provider: str,
    *,
    now: datetime | None = None,
    state_path: Path | str | None = None,
) -> bool:
    provider = _validate_provider(provider)
    current = _utc(now)
    path = _state_path(state_path)
    if not path.exists() and not path.is_symlink():
        return False
    with _locked(path):
        stored = _load(path)
        circuits = _active(stored, current)
        before = len(circuits)
        circuits = [item for item in circuits if item["provider"] != provider]
        closed = len(circuits) != before
        if closed or len(circuits) != len(stored):
            _write(path, circuits)
        return closed


def record_provider_result(
    provider: str,
    *,
    error: object = None,
    success: bool = False,
    now: datetime | None = None,
    state_path: Path | str | None = None,
) -> dict[str, Any]:
    provider = _validate_provider(provider)
    if success:
        return {"provider": provider, "closed": close_provider_circuit(provider, now=now, state_path=state_path)}
    classification = classify_provider_failure(error)
    if not classification:
        return {"provider": provider, "classification": None, "opened": False}
    circuit = open_provider_circuit(provider, classification, now=now, state_path=state_path)
    return {"provider": provider, "classification": classification, "opened": True, "circuit": circuit}


def cmd_provider_circuit(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt provider-circuit", description="Inspect or update bounded provider-venue circuits.")
    sub = parser.add_subparsers(dest="action")
    status = sub.add_parser("status")
    status.add_argument("--provider")
    record = sub.add_parser("record")
    record.add_argument("--provider", required=True)
    open_circuit = sub.add_parser("open")
    open_circuit.add_argument("--provider", required=True)
    open_circuit.add_argument("--reason", required=True, choices=sorted(REASONS))
    success = sub.add_parser("success")
    success.add_argument("--provider", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "status":
            circuits = active_provider_circuits()
            if args.provider:
                _validate_provider(args.provider)
                circuits = {args.provider: circuits[args.provider]} if args.provider in circuits else {}
            result = {"schemaVersion": 1, "circuits": circuits}
        elif args.action == "record":
            result = {"schemaVersion": 1, **record_provider_result(args.provider, error=sys.stdin.read(MAX_ERROR_CHARS + 1))}
        elif args.action == "open":
            result = {"schemaVersion": 1, "opened": True, "circuit": open_provider_circuit(args.provider, args.reason)}
        elif args.action == "success":
            result = {"schemaVersion": 1, **record_provider_result(args.provider, success=True)}
        else:
            parser.print_help()
            return 0
    except (OSError, ValueError) as exc:
        print(f"agnt provider-circuit: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
