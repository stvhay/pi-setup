"""Re-present pending decisions without replacing their canonical request.

The Pi boundary supplies existing process-bound human-UI proof. This service
stores only resolver hashes; rebinding neither answers a question nor activates
an exact grant. Original Beads metadata/comments remain immutable history.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Iterator

from .authority import _identifier, fingerprint


MAX_BYTES = 4 * 1024 * 1024


def binding_root() -> Path:
    from .work_lifecycle import runtime_store

    return runtime_store().root / "decision-bindings"


def _path(decision: str) -> Path:
    _identifier(decision)
    return binding_root() / (hashlib.sha256(decision.encode()).hexdigest() + ".json")


def _read(path: Path, decision: str) -> dict[str, Any] | None:
    from .approvals import _stored_resolver_binding

    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("decision binding path is unsafe")
    if not path.exists():
        return None
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > MAX_BYTES):
        raise ValueError("invalid private decision binding")
    envelope = json.loads(path.read_text())
    if not isinstance(envelope, dict) or set(envelope) != {"record", "fingerprint"}:
        raise ValueError("invalid decision binding envelope")
    record = envelope["record"]
    if (not isinstance(record, dict) or set(record) != {
        "schemaVersion", "decision", "requestFingerprint", "selectionMode", "bindings",
    } or envelope["fingerprint"] != fingerprint(record)
            or record["schemaVersion"] != 1 or record["decision"] != decision
            or record["selectionMode"] not in (None, "single", "multi")
            or not isinstance(record["bindings"], list) or not record["bindings"]):
        raise ValueError("invalid decision binding record")
    for item in record["bindings"]:
        if not isinstance(item, dict) or set(item) != {"binding", "at"} or not isinstance(item["at"], str):
            raise ValueError("invalid decision binding history")
        _stored_resolver_binding(item["binding"])
    return record


@contextmanager
def _locked(decision: str) -> Iterator[tuple[Path, dict[str, Any] | None]]:
    path = _path(decision)
    root = path.parent
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError("decision binding path is unsafe")
    root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("decision binding root must be owner-private")
    fd = os.open(path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield path, _read(path, decision)
    finally:
        os.close(fd)


def _write(path: Path, record: dict[str, Any]) -> None:
    data = json.dumps({"record": record, "fingerprint": fingerprint(record)}, sort_keys=True).encode() + b"\n"
    if len(data) > MAX_BYTES:
        raise ValueError("decision binding history capacity exceeded")
    fd, temporary = tempfile.mkstemp(prefix=".binding-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def require_current_owner(target: str, session: str) -> None:
    from . import quality
    from .work_lifecycle import runtime_store

    if quality.session_work_item(session) != target:
        raise ValueError("decision recovery requires current target ownership")
    owner = runtime_store().owner(target)
    if owner is not None:
        if owner["session"] != session or owner["phase"] != "active":
            raise ValueError("decision recovery execution ownership is unavailable")
    elif any(other != session and outcome is None
             for other, outcome in quality.work_item_attempts(target).items()):
        raise ValueError("legacy decision ownership requires reconciliation")


def pending_decision(decision: str, *, beads_runner: Any) -> dict[str, Any]:
    from .approvals import (
        _approval_from_metadata, _grant_from_approval, _metadata_from_bead,
        _require_unchanged_approval_preview, capability_grant_status, require_beads_success,
    )

    _identifier(decision)
    code, data, error = beads_runner(["show", decision])
    shown = require_beads_success(code, data, error, "read pending decision")
    approval = _approval_from_metadata(_metadata_from_bead(shown))
    if approval.get("status") != "pending":
        raise ValueError("only pending decisions can recover their UI binding")
    _require_unchanged_approval_preview(decision, approval, beads_runner)
    grant = _grant_from_approval(approval)
    if grant is not None and (grant["revocation"]["status"] != "pending"
                              or capability_grant_status(grant) in {"expired", "revoked"}):
        raise ValueError("exact grant is no longer pending and valid")
    if approval.get("kind") == "question" and approval.get("customResponseAllowed", True) is not True:
        raise ValueError("question custom response policy requires clarification")
    return approval


def _request_view(decision: str, approval: dict[str, Any]) -> dict[str, Any]:
    request = {key: copy.deepcopy(approval[key]) for key in (
        "kind", "targetBead", "question", "context", "options", "default", "preview", "selectionMode", "grant",
    ) if key in approval}
    return {"schemaVersion": 1, "status": "pending", "decisionBead": decision,
            "requestFingerprint": approval["requestFingerprint"], "request": request,
            "legacySelectionModeRequired": (approval["kind"] == "question" and approval.get("requestVersion", 1) == 1
                                             and current_binding(decision, approval) is None)}


def recovery_context(decision: str, *, resolver: dict[str, Any], beads_runner: Any) -> dict[str, Any]:
    from .approvals import _resolver_binding

    _resolver_binding(resolver)
    approval = pending_decision(decision, beads_runner=beads_runner)
    require_current_owner(approval["targetBead"], resolver["sessionId"])
    return _request_view(decision, approval)


def rebind_pending_decision(decision: str, *, resolver: dict[str, Any], beads_runner: Any,
                            legacy_selection_mode: str | None = None) -> dict[str, Any]:
    from .approvals import _resolver_binding, utc_now

    binding = _resolver_binding(resolver)
    with _locked(decision) as (path, previous):
        approval = pending_decision(decision, beads_runner=beads_runner)
        require_current_owner(approval["targetBead"], resolver["sessionId"])
        mode = approval.get("selectionMode") if approval["kind"] == "question" else None
        if approval["kind"] == "question":
            if mode not in ("single", "multi"):
                raise ValueError("question selection mode is invalid")
            verified_mode = (previous is not None and previous["requestFingerprint"] == approval["requestFingerprint"]
                             and previous["selectionMode"] == mode)
            if approval.get("requestVersion", 1) == 1 and not verified_mode and legacy_selection_mode != mode:
                raise ValueError("legacy question selection mode requires fresh human verification")
        # The original request fingerprint includes its original resolver. Do
        # not replace it or manufacture a second provenance/request identity.
        if previous and previous["requestFingerprint"] != approval["requestFingerprint"]:
            raise ValueError("decision request identity changed")
        record = copy.deepcopy(previous) if previous else {
            "schemaVersion": 1, "decision": decision,
            "requestFingerprint": approval["requestFingerprint"], "selectionMode": mode, "bindings": [],
        }
        if record["selectionMode"] != mode:
            raise ValueError("rebound question selection mode changed")
        if not record["bindings"] or record["bindings"][-1]["binding"] != binding:
            record["bindings"].append({"binding": binding, "at": utc_now()})
            _write(path, record)
    return _request_view(decision, approval)


def current_binding(decision: str, approval: dict[str, Any]) -> dict[str, str] | None:
    # The reader never creates or imports an override for legacy resolution.
    # Atomic replacement exposes one complete record, never a partial write.
    record = _read(_path(decision), decision)
    if record is None:
        return None
    if record["requestFingerprint"] != approval.get("requestFingerprint"):
        raise ValueError("rebound decision request identity changed")
    mode = approval.get("selectionMode") if approval.get("kind") == "question" else None
    if record["selectionMode"] != mode:
        raise ValueError("rebound question selection mode changed")
    if approval.get("kind") == "question" and approval.get("customResponseAllowed", True) is not True:
        raise ValueError("rebound question custom response policy changed")
    return copy.deepcopy(record["bindings"][-1]["binding"])
