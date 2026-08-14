from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .runtime_paths import resolve_runtime_directory

BEAD_ID = re.compile(r"[a-z][a-z0-9]*-[A-Za-z0-9._-]+\Z")
OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
EVIDENCE_REF = re.compile(
    r"(?:artifact|invocation|observation|result|run|trace):[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z"
)
SENSITIVE_REF = re.compile(
    r"(?:api.?key|authorization|bearer|password|secret|token|gh[pousr]_|github_pat_|glpat-|xox[baprs]-|npm_|pypi-|[sp]k-|AKIA[0-9A-Z]{16})",
    re.IGNORECASE,
)
JWT_REF = re.compile(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\Z")
TASK_OUTCOMES = frozenset({"success", "partial", "failure", "unclear"})
LEDGER_NAME = "ledger.jsonl"
MAX_EVIDENCE_REFS = 16
MAX_LEDGER_BYTES = 16 * 1024 * 1024


class SessionWorkItemConflict(ValueError):
    pass


class SessionOutcomeUnavailable(ValueError):
    pass


class SessionUnassigned(ValueError):
    pass


def current_session_id() -> str:
    session_id = os.environ.get("PI_SESSION_ID")
    if session_id:
        return _session_id(session_id)
    session_file = os.environ.get("PI_SESSION_FILE")
    if not session_file:
        raise ValueError("current Pi session is unavailable")
    return _session_id(Path(session_file).stem)


def _session_id(value: Any) -> str:
    if not isinstance(value, str) or not OPAQUE_ID.fullmatch(value):
        raise ValueError("current Pi session is unavailable")
    return value


def _bead_id(value: Any) -> str:
    if not isinstance(value, str) or not BEAD_ID.fullmatch(value):
        raise ValueError("bead ID is malformed")
    return value


def _evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_EVIDENCE_REFS:
        raise ValueError("evidence references are invalid")
    for ref in value:
        body = ref.partition(":")[2] if isinstance(ref, str) else ""
        if (
            not isinstance(ref, str)
            or not EVIDENCE_REF.fullmatch(ref)
            or SENSITIVE_REF.search(ref)
            or JWT_REF.fullmatch(body)
        ):
            raise ValueError("evidence reference is unsafe")
    return value


def _captured_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _quality_directory(directory: str | os.PathLike[str] | None = None) -> Path:
    path = Path(directory).expanduser() if directory is not None else resolve_runtime_directory("quality")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise OSError("quality runtime path is not a directory")
    path.chmod(0o700)
    return path


@contextmanager
def _locked_ledger(
    directory: str | os.PathLike[str] | None,
    *,
    exclusive: bool,
) -> Iterator[tuple[int | None, Path]]:
    root = _quality_directory(directory)
    path = root / LEDGER_NAME
    flags = (os.O_RDWR | os.O_CREAT | os.O_APPEND) if exclusive else os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if exclusive:
            raise
        yield None, root
        return
    try:
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode) or (not exclusive and stat.S_IMODE(mode) != 0o600):
            raise OSError("quality ledger is not a private regular file")
        if exclusive:
            os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield fd, root
    finally:
        os.close(fd)


def _validate_row(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("quality ledger row must be an object")
    record_type = value.get("recordType")
    fields = {"schemaVersion", "recordType", "sessionId", "beadId", "evidenceRefs", "capturedAt"}
    if record_type == "result":
        fields.add("outcome")
    if set(value) != fields:
        raise ValueError("quality ledger row fields are invalid")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("quality ledger row schema is invalid")
    if record_type not in {"invocation", "result"}:
        raise ValueError("quality ledger row type is invalid")
    _session_id(value.get("sessionId"))
    _bead_id(value.get("beadId"))
    _evidence_refs(value.get("evidenceRefs"))
    captured_at = value.get("capturedAt")
    if not isinstance(captured_at, str) or not captured_at.endswith("Z"):
        raise ValueError("quality ledger row timestamp is invalid")
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("quality ledger row timestamp is invalid") from exc
    if record_type == "result" and value.get("outcome") not in TASK_OUTCOMES:
        raise ValueError("quality ledger row outcome is invalid")
    return value


def _session_state(rows: list[dict[str, Any]], session_id: str) -> tuple[str | None, str | None]:
    bead_id = None
    outcome = None
    linked = False
    for row in rows:
        if row["sessionId"] != session_id:
            continue
        if bead_id is None:
            bead_id = row["beadId"]
        elif row["beadId"] != bead_id:
            raise ValueError("quality ledger session ownership conflicts")
        if row["recordType"] == "invocation":
            linked = True
            continue
        if not linked:
            raise ValueError("quality ledger result has no invocation")
        if outcome is None:
            outcome = row["outcome"]
        elif row["outcome"] != outcome:
            raise ValueError("quality ledger session outcome conflicts")
    return bead_id, outcome


def _read_rows(fd: int) -> list[dict[str, Any]]:
    size = os.fstat(fd).st_size
    if size > MAX_LEDGER_BYTES:
        raise ValueError("quality ledger exceeds bounded size")
    os.lseek(fd, 0, os.SEEK_SET)
    data = os.read(fd, size)
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise ValueError("quality ledger row is incomplete")
    try:
        rows = [_validate_row(json.loads(line)) for line in data.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("quality ledger row is invalid") from exc
    for session_id in {row["sessionId"] for row in rows}:
        _session_state(rows, session_id)
    return rows


def _append_row(fd: int, root: Path, row: dict[str, Any]) -> None:
    encoded = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    original_size = os.fstat(fd).st_size
    if len(encoded) > 4096 or original_size + len(encoded) > MAX_LEDGER_BYTES:
        raise ValueError("quality ledger row exceeds bounded size")
    try:
        written = os.write(fd, encoded)
        if written != len(encoded):
            raise OSError("quality ledger append was incomplete")
    except OSError:
        os.ftruncate(fd, original_size)
        os.fsync(fd)
        raise
    os.fsync(fd)
    directory_fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _validate_bead(bead_id: str, beads_runner: Any) -> None:
    result = beads_runner(["show", bead_id])
    data = result[1] if isinstance(result, tuple) and len(result) > 1 and result[0] == 0 else None
    if isinstance(data, list):
        data = data[0] if len(data) == 1 else None
    if not isinstance(data, dict) or data.get("id") != bead_id:
        raise ValueError("could not load work item")


def _record_matches(row: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(row.get(key) == value for key, value in expected.items())


def capture_session_link(
    session_id: str,
    bead_id: str,
    *,
    beads_runner: Any,
    directory: str | os.PathLike[str] | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    session_id = _session_id(session_id)
    bead_id = _bead_id(bead_id)
    refs = _evidence_refs(evidence_refs or [])
    _validate_bead(bead_id, beads_runner)
    expected = {
        "recordType": "invocation",
        "sessionId": session_id,
        "beadId": bead_id,
        "evidenceRefs": refs,
    }
    with _locked_ledger(directory, exclusive=True) as (fd, root):
        assert fd is not None
        rows = _read_rows(fd)
        owner, _outcome = _session_state(rows, session_id)
        if owner is not None and owner != bead_id:
            raise SessionWorkItemConflict(
                "current Pi session belongs to another work item; use handoff_bead or the /new human fallback and retry"
            )
        if not any(_record_matches(row, expected) for row in rows):
            _append_row(fd, root, {"schemaVersion": 1, **expected, "capturedAt": _captured_at()})
    return {"schemaVersion": 1, "status": "linked", "beadId": bead_id}


def capture_session_outcome(
    session_id: str,
    bead_id: str,
    outcome: str,
    *,
    beads_runner: Any,
    directory: str | os.PathLike[str] | None = None,
    evidence_refs: list[str] | None = None,
    require_link: bool = True,
) -> dict[str, Any]:
    session_id = _session_id(session_id)
    bead_id = _bead_id(bead_id)
    if outcome not in TASK_OUTCOMES:
        raise ValueError("task outcome is unsupported")
    refs = _evidence_refs(evidence_refs or [])
    _validate_bead(bead_id, beads_runner)
    with _locked_ledger(directory, exclusive=True) as (fd, root):
        assert fd is not None
        rows = _read_rows(fd)
        owner, recorded = _session_state(rows, session_id)
        if owner is not None and owner != bead_id:
            raise SessionWorkItemConflict(
                "current Pi session belongs to another work item; use handoff_bead or the /new human fallback and retry"
            )
        if recorded is not None and recorded != outcome:
            raise SessionWorkItemConflict("current Pi session already has another final outcome")
        if owner is None and require_link:
            raise SessionUnassigned("current Pi session has no linked work item")
        if owner is None:
            invocation = {
                "schemaVersion": 1,
                "recordType": "invocation",
                "sessionId": session_id,
                "beadId": bead_id,
                "evidenceRefs": [],
                "capturedAt": _captured_at(),
            }
            _append_row(fd, root, invocation)
        expected = {
            "recordType": "result",
            "sessionId": session_id,
            "beadId": bead_id,
            "outcome": outcome,
            "evidenceRefs": refs,
        }
        if not any(_record_matches(row, expected) for row in rows):
            _append_row(fd, root, {"schemaVersion": 1, **expected, "capturedAt": _captured_at()})
    return {"schemaVersion": 1, "status": "recorded", "beadId": bead_id, "outcome": outcome}


def session_work_item(
    session_id: str,
    *,
    directory: str | os.PathLike[str] | None = None,
) -> str | None:
    session_id = _session_id(session_id)
    with _locked_ledger(directory, exclusive=False) as (fd, _root):
        owner, _outcome = _session_state(_read_rows(fd) if fd is not None else [], session_id)
    return owner


def session_handoff_source(
    session_id: str,
    *,
    directory: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    session_id = _session_id(session_id)
    with _locked_ledger(directory, exclusive=False) as (fd, _root):
        owner, outcome = _session_state(_read_rows(fd) if fd is not None else [], session_id)
    if owner is None:
        raise SessionUnassigned("current Pi session has no linked work item")
    if outcome is None:
        raise SessionOutcomeUnavailable("current Pi session closeout outcome is unavailable")
    return {"beadId": owner, "outcome": outcome}


def current_session_work_item(session_id: str) -> str | None:
    return session_work_item(session_id)


def current_session_handoff_source(session_id: str) -> dict[str, str]:
    return session_handoff_source(session_id)


def current_session_closeout_source(session_id: str) -> dict[str, str]:
    return session_handoff_source(session_id)


def _validate_capture_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("quality capture payload must be an object")
    record_type = value.get("recordType")
    fields = {"schemaVersion", "recordType", "sessionId", "beadId", "evidenceRefs"}
    if record_type == "result":
        fields.add("outcome")
    unknown = set(value) - fields
    missing = fields - set(value)
    if unknown:
        raise ValueError(f"quality capture has unknown fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"quality capture is missing fields: {sorted(missing)}")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("quality capture schema is invalid")
    if record_type not in {"invocation", "result"}:
        raise ValueError("quality capture record type is unsupported")
    _session_id(value.get("sessionId"))
    _bead_id(value.get("beadId"))
    _evidence_refs(value.get("evidenceRefs"))
    if record_type == "result" and value.get("outcome") not in TASK_OUTCOMES:
        raise ValueError("quality capture outcome is unsupported")
    return value


def capture(
    payload: Any,
    *,
    beads_runner: Any,
    directory: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    payload = _validate_capture_payload(payload)
    kwargs = {
        "beads_runner": beads_runner,
        "directory": directory,
        "evidence_refs": payload["evidenceRefs"],
    }
    if payload["recordType"] == "invocation":
        return capture_session_link(payload["sessionId"], payload["beadId"], **kwargs)
    return capture_session_outcome(
        payload["sessionId"], payload["beadId"], payload["outcome"], **kwargs
    )


def _beads(args: list[str]) -> tuple[int, Any, str]:
    from .work import run_beads_json

    return run_beads_json(args)


def cmd_quality(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt quality", description="Capture private quality facts.")
    sub = parser.add_subparsers(dest="action")
    capture_cmd = sub.add_parser("capture", help="append a validated invocation or result fact")
    capture_cmd.add_argument("--payload", help="JSON capture payload; defaults to stdin")
    capture_cmd.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.action != "capture":
        parser.print_help()
        return 0
    try:
        raw = args.payload if args.payload is not None else sys.stdin.read()
        result = capture(json.loads(raw), beads_runner=_beads)
    except (json.JSONDecodeError, OSError, ValueError):
        print(json.dumps({"schemaVersion": 1, "status": "error", "error": "quality capture failed"}))
        return 2
    print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
    return 0
