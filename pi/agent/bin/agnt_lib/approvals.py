from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import stat
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .core import die, require_beads_success
from .quality import (
    capability_grant_fingerprint,
    capability_grant_status,
    normalize_capability_grant,
    normalize_ticket_decision_result,
)
from .runs import update_run_result
from .work import run_beads_json

VALID_KINDS = {"approval", "question"}
VALID_OUTCOMES = {"approved", "answered", "rejected", "cancelled", "timed-out"}
SELECTION_MODES = {"single", "multi"}
CLOSING_OUTCOMES = {"approved", "answered"}
BLOCKED_OUTCOMES = VALID_OUTCOMES - CLOSING_OUTCOMES
REQUIRED_PREVIEW_FIELDS = ["action", "scope", "consequences", "reversibility", "closeoutPath"]
BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]
CANONICAL_GRANT_LOOKUP_LIMIT = 2
HUMAN_UI_RESOLVER_FD = 3
MAX_RESOLVER_PROOF_BYTES = 4096


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_nonempty(name: str, value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _normalize_options(options: List[str] | None) -> List[str]:
    normalized = [str(item).strip() for item in (options or []) if str(item).strip()]
    if not normalized:
        raise ValueError("options must contain at least one non-empty option")
    return normalized


def _normalize_preview(preview: Dict[str, Any] | None) -> Dict[str, str]:
    if not isinstance(preview, dict):
        raise ValueError("preview must be an object")
    normalized: Dict[str, str] = {}
    for key in REQUIRED_PREVIEW_FIELDS:
        value = preview.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"preview.{key} is required")
        normalized[key] = value.strip()
    return normalized


def _fingerprint(value: Dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _session_fingerprint(session_id: str) -> str:
    return "sha256:" + hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _resolver_binding(value: Any) -> Dict[str, str]:
    if (
        not isinstance(value, dict)
        or not {"kind", "sessionId", "secret"}.issubset(value)
        or value.get("kind") != "human-ui"
        or not isinstance(value.get("sessionId"), str)
        or not value["sessionId"].strip()
        or not isinstance(value.get("secret"), str)
        or not value["secret"].strip()
    ):
        raise ValueError("human-ui resolver proof is invalid")
    return {
        "sessionFingerprint": _session_fingerprint(value["sessionId"].strip()),
        "secretFingerprint": _session_fingerprint(value["secret"].strip()),
    }


def _stored_resolver_binding(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict) or set(value) != {
        "sessionFingerprint", "secretFingerprint"
    }:
        raise ValueError("human-ui resolver binding is invalid")
    for key in ("sessionFingerprint", "secretFingerprint"):
        fingerprint = value.get(key)
        if (
            not isinstance(fingerprint, str)
            or not fingerprint.startswith("sha256:")
            or len(fingerprint) != 71
            or any(char not in "0123456789abcdef" for char in fingerprint[7:])
        ):
            raise ValueError("human-ui resolver binding is invalid")
    return dict(value)


def _verify_pending_tool_call(proof: Dict[str, Any]) -> bool:
    session_file = proof.get("sessionFile")
    session_id = proof.get("sessionId")
    tool_call_id = proof.get("toolCallId")
    tool_name = proof.get("toolName")
    if (
        not isinstance(session_file, str)
        or not session_file.strip()
        or not isinstance(session_id, str)
        or not session_id.strip()
        or not isinstance(tool_call_id, str)
        or not tool_call_id.strip()
        or tool_name not in {
            "ticket_approval", "ticket_question", "ticket_decision_resolve"
        }
    ):
        return False
    try:
        entries: Dict[str, Dict[str, Any]] = {}
        header_session_id = None
        leaf_id = None
        with Path(session_file).open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    return False
                if entry.get("type") == "session":
                    header_session_id = entry.get("id")
                elif isinstance(entry.get("id"), str):
                    entries[entry["id"]] = entry
                    leaf_id = entry["id"]
    except (OSError, json.JSONDecodeError):
        return False
    if header_session_id != session_id or leaf_id is None:
        return False
    current = entries.get(leaf_id)
    while current is not None:
        message = current.get("message")
        if isinstance(message, dict):
            if (
                message.get("role") == "toolResult"
                and message.get("toolCallId") == tool_call_id
            ):
                return False
            if message.get("role") == "assistant" and isinstance(
                message.get("content"), list
            ):
                for item in message["content"]:
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "toolCall"
                        and item.get("id") == tool_call_id
                        and item.get("name") == tool_name
                    ):
                        return True
        parent_id = current.get("parentId")
        current = entries.get(parent_id) if isinstance(parent_id, str) else None
    return False


def _private_fd_peer_pid(fd: int) -> int | None:
    try:
        duplicate = os.dup(fd)
        with socket.socket(fileno=duplicate) as channel:
            if sys.platform == "darwin":
                return struct.unpack("i", channel.getsockopt(0, 2, 4))[0]
            if sys.platform.startswith("linux") and hasattr(socket, "SO_PEERCRED"):
                size = struct.calcsize("3i")
                return struct.unpack(
                    "3i", channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
                )[0]
    except OSError:
        return None
    return None


def _resolver_from_private_fd() -> Dict[str, str] | None:
    if os.environ.get("AGNT_HUMAN_UI_RESOLVER_FD") != str(HUMAN_UI_RESOLVER_FD):
        return None
    try:
        mode = os.fstat(HUMAN_UI_RESOLVER_FD).st_mode
        if (
            not stat.S_ISSOCK(mode)
            or _private_fd_peer_pid(HUMAN_UI_RESOLVER_FD) != os.getppid()
        ):
            return None
        chunks = []
        size = 0
        while True:
            chunk = os.read(HUMAN_UI_RESOLVER_FD, MAX_RESOLVER_PROOF_BYTES + 1 - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_RESOLVER_PROOF_BYTES:
                raise ValueError("human-ui resolver proof is too large")
    except OSError:
        return None
    if not chunks:
        return None
    try:
        value = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("human-ui resolver proof is invalid") from exc
    if not isinstance(value, dict) or set(value) != {
        "kind", "sessionId", "secret", "sessionFile", "toolCallId", "toolName"
    }:
        raise ValueError("human-ui resolver proof is invalid")
    _resolver_binding(value)
    if not _verify_pending_tool_call(value):
        return None
    return {
        key: value[key].strip()
        for key in (
            "kind", "sessionId", "secret", "sessionFile", "toolCallId", "toolName"
        )
    }


def _request_fingerprint(approval: Dict[str, Any]) -> str:
    kind = approval.get("kind")
    if kind not in VALID_KINDS:
        raise ValueError("approval request kind is invalid")
    target = _require_nonempty("target_bead", approval.get("targetBead"))
    question = _require_nonempty("question", approval.get("question"))
    context = _require_nonempty("context", approval.get("context"))
    options = _normalize_options(approval.get("options"))
    default = _require_nonempty("default", approval.get("default"))
    if default not in options:
        raise ValueError("approval request default is invalid")
    identity = {
        "kind": kind,
        "targetBead": target,
        "question": question,
        "context": context,
        "options": options,
        "default": default,
        "preview": _normalize_preview(approval.get("preview")),
    }
    if "grantFingerprint" in approval:
        identity["grantFingerprint"] = _require_nonempty(
            "grant_fingerprint", approval.get("grantFingerprint")
        )
    if "resolverBinding" in approval:
        identity["resolverBinding"] = _stored_resolver_binding(
            approval.get("resolverBinding")
        )
    return _fingerprint(identity)


def _provenance_request_fingerprints(value: Any) -> set[str]:
    if isinstance(value, list):
        return set().union(*(_provenance_request_fingerprints(item) for item in value), set())
    if not isinstance(value, dict):
        return set()
    found = set()
    if value.get("source") == "agnt-approval":
        payload = value.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = None
        if (
            isinstance(payload, dict)
            and payload.get("schemaVersion") == 1
            and payload.get("kind") == "approval-request"
            and isinstance(payload.get("requestFingerprint"), str)
        ):
            found.add(payload["requestFingerprint"])
    return found.union(*(_provenance_request_fingerprints(item) for item in value.values()), set())


def _provenance_grant_states(value: Any) -> list[tuple[str, str]]:
    if isinstance(value, list):
        states: list[tuple[str, str]] = []
        for item in value:
            states.extend(_provenance_grant_states(item))
        return states
    if not isinstance(value, dict):
        return []
    payload = value.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = None
    states: list[tuple[str, str]] = []
    if isinstance(payload, dict) and payload.get("schemaVersion") == 1:
        kind = payload.get("kind")
        fingerprint = payload.get("grantFingerprint")
        status = payload.get("status")
        if kind == "approval-request":
            status = payload.get("grantStatus")
        if isinstance(fingerprint, str) and isinstance(status, str):
            states.append((fingerprint, status))
    for item in value.values():
        states.extend(_provenance_grant_states(item))
    return states


def _record_grant_state(
    decision_bead: str,
    grant: Dict[str, Any],
    beads_runner: BeadsRunner,
) -> None:
    code, data, err = beads_runner([
        "provenance", "record",
        "--issue", decision_bead,
        "--kind", "cut",
        "--source", "agnt-capability",
        "--at", utc_now(),
        "--payload", _json_arg({
            "schemaVersion": 1,
            "kind": "grant-state",
            "grantFingerprint": capability_grant_fingerprint(grant),
            "status": grant["revocation"]["status"],
        }),
    ])
    require_beads_success(code, data, err, "record capability grant state")


def _require_unchanged_approval_preview(
    decision_bead: str,
    approval: Dict[str, Any],
    beads_runner: BeadsRunner,
) -> None:
    grant_fingerprint = None
    current_grant_status = None
    try:
        preview_fingerprint = _fingerprint(_normalize_preview(approval.get("preview")))
        request_fingerprint = _request_fingerprint(approval)
    except ValueError as exc:
        raise ValueError("approval preview changed; create a new approval request") from exc
    if "grant" in approval:
        try:
            grant = normalize_capability_grant(approval.get("grant"))
            grant_fingerprint = capability_grant_fingerprint(grant)
        except ValueError as exc:
            raise ValueError("approval preview changed; create a new approval request") from exc
        if approval.get("grantFingerprint") != grant_fingerprint:
            raise ValueError("approval preview changed; create a new approval request")
        current_grant_status = grant["revocation"]["status"]
    if (
        approval.get("previewFingerprint") != preview_fingerprint
        or approval.get("requestFingerprint") != request_fingerprint
    ):
        raise ValueError("approval preview changed; create a new approval request")
    code, data, err = beads_runner(["provenance", "log", decision_bead, "--kind", "cut"])
    provenance = require_beads_success(code, data, err, "read approval provenance")
    if _provenance_request_fingerprints(provenance) != {request_fingerprint}:
        raise ValueError("approval preview changed; create a new approval request")
    if grant_fingerprint is not None:
        states = _provenance_grant_states(provenance)
        state_rank = {"pending": 0, "active": 1, "revoked": 2, "expired": 2}
        highest_state = -1
        terminal_state = None
        for fingerprint, status in states:
            if fingerprint != grant_fingerprint:
                raise ValueError("approval grant changed; create a new approval request")
            if status not in state_rank:
                raise ValueError("approval grant state changed; create a new approval request")
            highest_state = max(highest_state, state_rank[status])
            if status in {"revoked", "expired"}:
                terminal_state = status
        if state_rank.get(current_grant_status, -1) < highest_state:
            raise ValueError("approval grant state changed; create a new approval request")
        if terminal_state is not None and terminal_state != current_grant_status:
            raise ValueError("approval grant state changed; create a new approval request")


def approval_request_payload(
    *,
    kind: str,
    selection_mode: str | None = None,
    target_bead: str,
    question: str,
    context: str,
    options: List[str],
    default: str | None,
    preview: Dict[str, Any],
    grant: Dict[str, Any] | None = None,
    resolver_binding: Dict[str, str] | None = None,
    created_at: str | None = None,
) -> Dict[str, Any]:
    """Build the durable Beads decision payload for a human gate.

    The payload is intentionally plain JSON so the CLI and Pi extension
    can share one auditable representation. Approval previews include the
    informed-consent fields required by the approval-confirmation design.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(VALID_KINDS)}")
    normalized_selection_mode = None
    if kind == "question":
        normalized_selection_mode = _require_nonempty("selection_mode", selection_mode)
        if normalized_selection_mode not in SELECTION_MODES:
            raise ValueError(f"selection_mode must be one of {sorted(SELECTION_MODES)}")
    target = _require_nonempty("target_bead", target_bead)
    prompt = _require_nonempty("question", question)
    body_context = _require_nonempty("context", context)
    choices = _normalize_options(options)
    chosen_default = default.strip() if isinstance(default, str) and default.strip() else choices[0]
    if chosen_default not in choices:
        raise ValueError("default must match one of the options")
    normalized_preview = _normalize_preview(preview)
    grant_input = grant if grant is not None else preview.get("grant")
    normalized_grant = None
    if grant_input is not None:
        if kind != "approval":
            raise ValueError("capability grant requires an approval")
        normalized_grant = normalize_capability_grant(grant_input, require_future=True)
    timestamp = created_at or utc_now()

    labels = ["beads-backed", "human", "human-gate", "ask", kind]
    if kind == "approval":
        labels.append("approval")
    else:
        labels.append("question")

    approval = {
        "schemaVersion": 1,
        "kind": kind,
        "targetBead": target,
        "question": prompt,
        "context": body_context,
        "options": choices,
        "default": chosen_default,
        "preview": normalized_preview,
        "previewFingerprint": _fingerprint(normalized_preview),
        "status": "pending",
        "createdAt": timestamp,
    }
    if normalized_grant is not None:
        approval["grant"] = normalized_grant
        approval["grantFingerprint"] = capability_grant_fingerprint(normalized_grant)
    if normalized_selection_mode is not None:
        approval["selectionMode"] = normalized_selection_mode
        approval["customResponseAllowed"] = True
    if resolver_binding is not None:
        approval["resolverBinding"] = _resolver_binding(resolver_binding)
    approval["requestFingerprint"] = _request_fingerprint(approval)
    metadata = {"pi": {"approval": approval}}
    description = "\n".join([
        f"Beads-backed {kind} request.",
        "",
        f"Question: {prompt}",
        "",
        "Context:",
        body_context,
        "",
        "Options:",
        *[f"- {item}" for item in choices],
        "",
        f"Requested default: {chosen_default}",
        *([f"Selection mode: {normalized_selection_mode}", "Custom response: available"] if normalized_selection_mode else []),
        f"Target bead: {target}",
        "",
        "Approval preview:",
        f"- Action: {normalized_preview['action']}",
        f"- Scope: {normalized_preview['scope']}",
        f"- Consequences: {normalized_preview['consequences']}",
        f"- Reversibility: {normalized_preview['reversibility']}",
        f"- Closeout path: {normalized_preview['closeoutPath']}",
        *([
            "",
            "Capability grant:",
            f"- Action: {normalized_grant['action']}",
            f"- Effects: {', '.join(normalized_grant['effects'])}",
            f"- Model: {normalized_grant['model']}",
            f"- Thinking: {normalized_grant['thinking']}",
            f"- Toolset: {', '.join(normalized_grant['toolset'])}",
            f"- Context policy: {normalized_grant['contextPolicy']}",
            f"- Proof: {', '.join(normalized_grant['proof']['required'])}",
            f"- Proof evidence: {', '.join(normalized_grant['proof']['evidenceRefs'])}",
            f"- Rollout ceiling: {normalized_grant['rollout']['maxActions']} actions / {normalized_grant['rollout']['maxEffects']} effects",
            f"- Expiry: {normalized_grant['expiry']}",
        ] if normalized_grant else []),
    ])
    return {
        "title": prompt,
        "type": "decision",
        "priority": "2",
        "labels": labels,
        "description": description,
        "metadata": metadata,
    }


def _json_arg(value: Dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _decision_id_from_create(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("id"), str) and data["id"]:
        return data["id"]
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("id"):
        return str(data[0]["id"])
    die("bd create did not return a decision id", 1)


def create_beads_approval_request(
    *,
    kind: str,
    selection_mode: str | None = None,
    target_bead: str,
    question: str,
    context: str,
    options: List[str],
    default: str | None = None,
    preview: Dict[str, Any],
    grant: Dict[str, Any] | None = None,
    resolver_binding: Dict[str, str] | None = None,
    run_bundle: Path | None = None,
    beads_runner: BeadsRunner = run_beads_json,
) -> Dict[str, Any]:
    payload = approval_request_payload(
        kind=kind,
        selection_mode=selection_mode,
        target_bead=target_bead,
        question=question,
        context=context,
        options=options,
        default=default,
        preview=preview,
        grant=grant,
        resolver_binding=resolver_binding,
    )
    metadata_arg = _json_arg(payload["metadata"])
    labels_arg = ",".join(payload["labels"])
    create_args = [
        "create",
        str(payload["title"]),
        "--type",
        str(payload["type"]),
        "--priority",
        str(payload["priority"]),
        "--labels",
        labels_arg,
        "--description",
        str(payload["description"]),
        "--metadata",
        metadata_arg,
    ]
    code, data, err = beads_runner(create_args)
    created = require_beads_success(code, data, err, "create approval request")
    decision_bead = _decision_id_from_create(created)

    dep_args = ["dep", decision_bead, "--blocks", target_bead]
    dep_code, dep_data, dep_err = beads_runner(dep_args)
    require_beads_success(dep_code, dep_data, dep_err, "dep approval blocker")

    approval = payload["metadata"]["pi"]["approval"]
    provenance_payload = {
        "schemaVersion": 1,
        "kind": "approval-request",
        "requestFingerprint": approval["requestFingerprint"],
    }
    if "grantFingerprint" in approval:
        provenance_payload["grantFingerprint"] = approval["grantFingerprint"]
        provenance_payload["grantStatus"] = approval["grant"]["revocation"]["status"]
    provenance_code, provenance_data, provenance_err = beads_runner([
        "provenance", "record",
        "--issue", decision_bead,
        "--kind", "cut",
        "--source", "agnt-approval",
        "--at", approval["createdAt"],
        "--payload", _json_arg(provenance_payload),
    ])
    require_beads_success(
        provenance_code, provenance_data, provenance_err, "record approval provenance"
    )

    run_result = None
    if run_bundle is not None:
        run_result = update_run_result(
            run_bundle,
            status="needs-human",
            summary=f"Waiting for Beads-backed {kind}: {decision_bead}",
            approval_refs=[decision_bead] if kind == "approval" else [],
            decision_refs=[decision_bead],
        )

    return {
        "schemaVersion": 1,
        "decisionBead": decision_bead,
        "targetBead": target_bead,
        "kind": kind,
        "blockerCreated": True,
        "metadata": payload["metadata"],
        "runResult": run_result,
    }


def _metadata_from_bead(data: Any) -> Dict[str, Any]:
    raw: Any = {}
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        raw = data.get("metadata") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            raw = {}
    return raw if isinstance(raw, dict) else {}


def _approval_from_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    pi = metadata.setdefault("pi", {})
    if not isinstance(pi, dict):
        metadata["pi"] = pi = {}
    approval = pi.setdefault("approval", {})
    if not isinstance(approval, dict):
        pi["approval"] = approval = {}
    if approval.get("kind") == "question" and "selectionMode" not in approval:
        approval["selectionMode"] = "single"
    return approval


def _grant_from_approval(approval: Dict[str, Any]) -> Dict[str, Any] | None:
    if "grant" not in approval:
        return None
    try:
        grant = normalize_capability_grant(approval.get("grant"))
    except ValueError as exc:
        raise ValueError("capability grant is invalid; create a new approval request") from exc
    if approval.get("grantFingerprint") != capability_grant_fingerprint(grant):
        raise ValueError("capability grant changed; create a new approval request")
    return grant


def _write_grant_state(
    metadata: Dict[str, Any],
    approval: Dict[str, Any],
    grant: Dict[str, Any],
    *,
    status: str,
    reason: str | None,
    at: str | None,
) -> None:
    original_fingerprint = capability_grant_fingerprint(grant)
    grant["revocation"] = {"status": status, "reason": reason, "at": at}
    if capability_grant_fingerprint(grant) != original_fingerprint:
        raise ValueError("capability grant state would expand its ceiling")
    approval["grant"] = grant
    metadata.setdefault("pi", {})["approval"] = approval


def resolve_capability_grant(
    decision_bead: str,
    *,
    beads_runner: BeadsRunner = run_beads_json,
) -> Dict[str, Any]:
    decision = _require_nonempty("decision_bead", decision_bead)
    show_code, show_data, show_err = beads_runner(["show", decision])
    shown = require_beads_success(show_code, show_data, show_err, "show capability grant")
    metadata = _metadata_from_bead(shown)
    approval = _approval_from_metadata(metadata)
    if approval.get("kind") != "approval":
        raise ValueError("capability grant decision is not an approval")
    grant = _grant_from_approval(approval)
    if grant is None:
        return {
            "schemaVersion": 1,
            "decisionBead": decision,
            "status": "missing",
            "allowedEffects": [],
        }
    if approval.get("status") != "approved" or approval.get("resolver") != {"kind": "human-ui"}:
        return {
            "schemaVersion": 1,
            "decisionBead": decision,
            "targetBead": approval.get("targetBead"),
            "status": "blocked",
            "grant": grant,
            "grantFingerprint": capability_grant_fingerprint(grant),
            "resolver": approval.get("resolver"),
            "allowedEffects": [],
        }
    _require_unchanged_approval_preview(decision, approval, beads_runner)
    state = capability_grant_status(grant)
    automatic_update = False
    note = ""
    if grant["revocation"]["status"] == "pending":
        active_grant = dict(grant)
        active_grant["revocation"] = {"status": "active", "reason": None, "at": None}
        state = capability_grant_status(active_grant)
        grant = active_grant
        _write_grant_state(
            metadata,
            approval,
            grant,
            status="active",
            reason=None,
            at=None,
        )
        automatic_update = True
        note = "Capability grant activated from resolved human approval."
    if state == "expired" and grant["revocation"]["status"] == "active":
        _write_grant_state(
            metadata,
            approval,
            grant,
            status="expired",
            reason="expiry",
            at=utc_now(),
        )
        automatic_update = True
        note = "Capability grant expired automatically."
    if automatic_update:
        _record_grant_state(decision, grant, beads_runner)
        update_code, update_data, update_err = beads_runner([
            "update", decision, "--metadata", _json_arg(metadata),
            "--append-notes", note,
        ])
        require_beads_success(update_code, update_data, update_err, "update capability grant state")
    allowed_effects = list(grant["effects"]) if state == "active" else []
    return {
        "schemaVersion": 1,
        "decisionBead": decision,
        "targetBead": approval.get("targetBead"),
        "status": state,
        "grant": grant,
        "grantFingerprint": capability_grant_fingerprint(grant),
        "resolver": approval.get("resolver"),
        "allowedEffects": allowed_effects,
    }


def resolve_canonical_capability_grant(
    decision_bead: str,
    *,
    beads_runner: BeadsRunner = run_beads_json,
) -> Dict[str, Any]:
    """Resolve one exact grant with bounded Beads reads and no fail-open path."""
    decision = _require_nonempty("decision_bead", decision_bead)
    lookup_count = 0

    def bounded_runner(args: List[str]) -> Tuple[int, Any, str]:
        nonlocal lookup_count
        if args and args[0] == "show":
            lookup_count += 1
        elif args[:2] == ["provenance", "log"]:
            lookup_count += 1
        if lookup_count > CANONICAL_GRANT_LOOKUP_LIMIT:
            raise ValueError("capability grant lookup bound exceeded")
        return beads_runner(args)

    try:
        resolved = resolve_capability_grant(decision, beads_runner=bounded_runner)
        if not isinstance(resolved, dict) or resolved.get("decisionBead") != decision:
            raise ValueError("capability grant decision is invalid")
        status = resolved.get("status")
        if status not in {"active", "blocked", "missing", "expired", "revoked"}:
            raise ValueError("capability grant status is invalid")
        allowed_effects = resolved.get("allowedEffects")
        if not isinstance(allowed_effects, list) or not all(
            isinstance(effect, str) and effect.strip() for effect in allowed_effects
        ):
            raise ValueError("capability grant effects are invalid")
        grant = resolved.get("grant")
        if grant is not None:
            normalized_grant = normalize_capability_grant(grant)
            fingerprint = capability_grant_fingerprint(normalized_grant)
            if resolved.get("grantFingerprint") != fingerprint:
                raise ValueError("capability grant fingerprint is invalid")
            if status == "active":
                if resolved.get("resolver") != {"kind": "human-ui"}:
                    raise ValueError("capability grant human UI provenance is invalid")
                if capability_grant_status(normalized_grant) != "active":
                    raise ValueError("capability grant is not active")
                if allowed_effects != normalized_grant["effects"]:
                    raise ValueError("capability grant effects do not match resolved state")
            elif allowed_effects:
                raise ValueError("blocked capability grant cannot allow effects")
        elif allowed_effects:
            raise ValueError("missing capability grant cannot allow effects")
        return resolved
    except (ValueError, SystemExit):
        return {
            "schemaVersion": 1,
            "decisionBead": decision,
            "status": "blocked",
            "allowedEffects": [],
        }


def revoke_capability_grant(
    decision_bead: str,
    reason: str,
    *,
    beads_runner: BeadsRunner = run_beads_json,
) -> Dict[str, Any]:
    revoke_reason = _require_nonempty("reason", reason)
    decision = _require_nonempty("decision_bead", decision_bead)
    show_code, show_data, show_err = beads_runner(["show", decision])
    shown = require_beads_success(show_code, show_data, show_err, "show capability grant")
    metadata = _metadata_from_bead(shown)
    approval = _approval_from_metadata(metadata)
    grant = _grant_from_approval(approval)
    if grant is None or approval.get("status") != "approved" or approval.get("resolver") != {"kind": "human-ui"}:
        raise ValueError("capability grant is not active")
    _require_unchanged_approval_preview(decision, approval, beads_runner)
    if grant["revocation"]["status"] not in {"revoked", "expired"}:
        _write_grant_state(
            metadata,
            approval,
            grant,
            status="revoked",
            reason=revoke_reason,
            at=utc_now(),
        )
        _record_grant_state(decision, grant, beads_runner)
        update_code, update_data, update_err = beads_runner([
            "update", decision, "--metadata", _json_arg(metadata),
            "--append-notes", f"Capability grant revoked: {revoke_reason}",
        ])
        require_beads_success(update_code, update_data, update_err, "revoke capability grant")
    return resolve_capability_grant(decision, beads_runner=beads_runner)


def resolve_beads_approval_request(
    *,
    decision_bead: str,
    outcome: str,
    answer: str | None = None,
    selected_options: List[str] | None = None,
    custom_input: str | None = None,
    structured_answer: bool = False,
    resolver: Dict[str, str] | None = None,
    run_bundle: Path | None = None,
    beads_runner: BeadsRunner = run_beads_json,
) -> Dict[str, Any]:
    decision = _require_nonempty("decision_bead", decision_bead)
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(VALID_OUTCOMES)}")
    answer_text = answer.strip() if isinstance(answer, str) and answer.strip() else outcome

    show_code, show_data, show_err = beads_runner(["show", decision])
    shown = require_beads_success(show_code, show_data, show_err, "show approval request")
    metadata = _metadata_from_bead(shown)
    approval = _approval_from_metadata(metadata)
    kind = str(approval.get("kind") or "approval")
    if kind == "question" and outcome == "approved":
        raise ValueError("question decisions cannot resolve as approved")
    if kind == "approval" and outcome == "answered":
        raise ValueError("approval decisions cannot resolve as answered")
    grant = _grant_from_approval(approval) if kind == "approval" else None
    if kind == "approval" and outcome == "approved":
        if grant is not None and grant["revocation"]["status"] in {"revoked", "expired"}:
            raise ValueError("capability grant is no longer active; create a new approval request")
        _require_unchanged_approval_preview(decision, approval, beads_runner)

    structured_answer = structured_answer or selected_options is not None or custom_input is not None
    if structured_answer:
        if kind != "question" or outcome != "answered":
            raise ValueError("structured answers are only valid for answered questions")
        if selected_options is not None and not isinstance(selected_options, list):
            raise ValueError("selected_options must be a list")
        if custom_input is not None and not isinstance(custom_input, str):
            raise ValueError("custom_input must be a string")
        raw_choices = approval.get("options")
        if not isinstance(raw_choices, list):
            raise ValueError("question options are unavailable")
        choices = [str(item) for item in raw_choices]
        selected: List[str] = []
        for raw in selected_options or []:
            if not isinstance(raw, str):
                raise ValueError("selected_options must contain strings")
            value = raw.strip()
            if not value:
                raise ValueError("selected_options cannot contain empty values")
            if value not in choices:
                raise ValueError("selected_options must match question options")
            if value not in selected:
                selected.append(value)
        custom = None
        if custom_input is not None:
            custom = custom_input.strip()
            if not custom:
                raise ValueError("custom_input cannot be empty")
        selection_mode = str(approval.get("selectionMode") or "single")
        if selection_mode not in SELECTION_MODES:
            raise ValueError("question selection mode is invalid")
        if selection_mode == "single" and (len(selected) > 1 or (selected and custom) or (not selected and not custom)):
            raise ValueError("single-select questions accept one selected option or one custom response")
        selected_text = f"[{', '.join(selected)}]" if selection_mode == "multi" else (selected[0] if selected else "")
        if selected and custom:
            answer_text = f"{selected_text} + Other: {custom}"
        elif custom:
            answer_text = f"Other: {custom}"
        else:
            answer_text = selected_text
        approval["selectedOptions"] = selected
        if custom:
            approval["customInput"] = custom
        else:
            approval.pop("customInput", None)

    resolver_session_fingerprint = None
    if outcome in CLOSING_OUTCOMES:
        if not isinstance(resolver, dict):
            raise ValueError("approved or answered outcomes require human-ui resolver provenance")
        try:
            expected_binding = _stored_resolver_binding(
                approval.get("resolverBinding")
            )
            actual_binding = _resolver_binding(resolver)
        except ValueError as exc:
            raise ValueError(
                "human-ui resolver binding is unavailable; create a new approval request"
            ) from exc
        if actual_binding != expected_binding:
            raise ValueError("human-ui resolver binding does not match approval request")
        resolver_session_fingerprint = actual_binding["sessionFingerprint"]
    approval.pop("requestingRun", None)
    approval.update({
        "status": outcome,
        "answer": answer_text,
        "resolvedAt": utc_now(),
    })
    if resolver is not None:
        approval["resolver"] = {"kind": resolver["kind"]}
        approval["resolverSessionFingerprint"] = resolver_session_fingerprint
    if grant is not None:
        if outcome == "approved":
            resolved_grant = dict(grant)
            resolved_grant["revocation"] = {"status": "active", "reason": None, "at": None}
            if capability_grant_status(resolved_grant) != "active":
                raise ValueError("capability grant is expired; create a new approval request")
            _write_grant_state(
                metadata,
                approval,
                resolved_grant,
                status="active",
                reason=None,
                at=None,
            )
        else:
            _write_grant_state(
                metadata,
                approval,
                grant,
                status="revoked",
                reason=f"resolution:{outcome}",
                at=utc_now(),
            )
    quality_result = normalize_ticket_decision_result(decision, approval)
    approval["qualityResult"] = quality_result

    note = f"Beads-backed {kind} resolved as {outcome}: {answer_text}"
    update_args = ["update", decision, "--metadata", _json_arg(metadata), "--append-notes", note]
    if grant is not None:
        _record_grant_state(decision, grant, beads_runner)
    update_code, update_data, update_err = beads_runner(update_args)
    require_beads_success(update_code, update_data, update_err, "update approval resolution")

    blocker_visible = outcome in BLOCKED_OUTCOMES
    target_update_result = None

    close_result = None
    if not blocker_visible:
        close_code, close_data, close_err = beads_runner(["close", decision, "--reason", note])
        close_result = require_beads_success(close_code, close_data, close_err, "close approval request")

    run_result = None
    if run_bundle is not None:
        run_result = update_run_result(
            run_bundle,
            status="succeeded" if not blocker_visible else "blocked",
            summary=note,
            approval_refs=[decision] if kind == "approval" else [],
            decision_refs=[decision],
        )

    return {
        "schemaVersion": 1,
        "decisionBead": decision,
        "kind": kind,
        "outcome": outcome,
        "blockerVisible": blocker_visible,
        "qualityResult": quality_result,
        "metadata": metadata,
        "closeResult": close_result,
        "targetUpdateResult": target_update_result,
        "runResult": run_result,
    }


def _preview_from_args(args: argparse.Namespace) -> Dict[str, str]:
    return {
        "action": args.preview_action,
        "scope": args.preview_scope,
        "consequences": args.preview_consequences,
        "reversibility": args.preview_reversibility,
        "closeoutPath": args.preview_closeout_path,
    }


def cmd_approvals(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt approvals", description="Create and resolve Beads-backed questions/approval gates.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    request = sub.add_parser("request", help="create a durable decision bead and blocker")
    request.add_argument("--kind", choices=sorted(VALID_KINDS), required=True)
    request.add_argument("--selection-mode", choices=sorted(SELECTION_MODES))
    request.add_argument("--target-bead", required=True)
    request.add_argument("--question", required=True)
    request.add_argument("--context", required=True)
    request.add_argument("--option", action="append", required=True)
    request.add_argument("--default")
    request.add_argument("--grant", help="exact capability grant JSON")
    request.add_argument("--run-bundle", type=Path)
    request.add_argument("--preview-action", required=True)
    request.add_argument("--preview-scope", required=True)
    request.add_argument("--preview-consequences", required=True)
    request.add_argument("--preview-reversibility", required=True)
    request.add_argument("--preview-closeout-path", required=True)
    request.add_argument("--json", action="store_true")

    resolve = sub.add_parser("resolve", help="record a durable answer/rejection/timeout")
    resolve.add_argument("decision_bead")
    resolve.add_argument("--outcome", choices=sorted(VALID_OUTCOMES), required=True)
    resolve.add_argument("--answer")
    resolve.add_argument("--selected-option", action="append")
    resolve.add_argument("--custom-input")
    resolve.add_argument("--structured-answer", action="store_true")
    resolve.add_argument("--resolver-kind")
    resolve.add_argument("--resolver-session")
    resolve.add_argument("--run-bundle", type=Path)
    resolve.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "request":
            if args.kind == "question" and args.selection_mode is None:
                raise ValueError("selection_mode is required")
            grant = None
            if args.grant is not None:
                try:
                    grant = json.loads(args.grant)
                except json.JSONDecodeError as exc:
                    raise ValueError("grant must be valid JSON") from exc
                if not isinstance(grant, dict):
                    raise ValueError("grant must be a JSON object")
            result = create_beads_approval_request(
                kind=args.kind,
                selection_mode=args.selection_mode,
                target_bead=args.target_bead,
                question=args.question,
                context=args.context,
                options=args.option,
                default=args.default,
                preview=_preview_from_args(args),
                grant=grant,
                resolver_binding=_resolver_from_private_fd(),
                run_bundle=args.run_bundle,
            )
        else:
            if args.resolver_kind is not None or args.resolver_session is not None:
                raise ValueError("human-ui resolver CLI flags are not accepted")
            resolver = (
                _resolver_from_private_fd()
                if args.outcome in CLOSING_OUTCOMES
                else None
            )
            if args.outcome in CLOSING_OUTCOMES and resolver is None:
                raise ValueError(
                    "approved or answered outcomes require process-bound human-ui resolver provenance"
                )
            result = resolve_beads_approval_request(
                decision_bead=args.decision_bead,
                outcome=args.outcome,
                answer=args.answer,
                selected_options=args.selected_option,
                custom_input=args.custom_input,
                structured_answer=args.structured_answer,
                resolver=resolver,
                run_bundle=args.run_bundle,
            )
    except ValueError as exc:
        die(str(exc), 2)

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result['decisionBead']} {result.get('outcome') or result.get('kind')}")
    return 0


__all__ = [
    "approval_request_payload",
    "create_beads_approval_request",
    "resolve_beads_approval_request",
    "resolve_capability_grant",
    "resolve_canonical_capability_grant",
    "revoke_capability_grant",
    "cmd_approvals",
]
