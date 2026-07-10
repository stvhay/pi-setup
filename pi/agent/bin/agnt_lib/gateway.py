from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .approvals import create_beads_approval_request, resolve_beads_approval_request
from .core import die
from .orchestration import validate_bead_orchestration_metadata
from .runner_client import RunnerClientError, runner_client_status
from .runner_protocol import DEFAULT_BUDGET, active_run_summary, redact_service_metadata
from .runs import default_runs_dir
from .work import build_work_tree, normalize_bead, run_beads_json, run_refs_by_bead

VALID_OPERATIONS = {
    "list",
    "show",
    "tree",
    "create_draft",
    "request_approval",
    "resolve_blocker",
    "runner_status",
}
BANNED_KEYS = {"command", "cmd", "shell", "bash", "raw", "script", "subagent", "argv", "args"}
ISSUE_TYPES = {"bug", "feature", "task", "epic", "chore", "decision"}
BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]
TreeBuilder = Callable[..., Dict[str, Any]]

ALLOWED_KEYS = {
    "list": {"operation", "limit", "includeEpics", "runsDir"},
    "show": {"operation", "bead", "runsDir"},
    "tree": {"operation", "root", "epic", "runsDir"},
    "create_draft": {"operation", "title", "description", "issueType", "priority", "labels", "metadata", "parent", "acceptance"},
    "request_approval": {
        "operation",
        "targetBead",
        "target_bead",
        "question",
        "context",
        "options",
        "default",
        "requestingRun",
        "preview",
        "runBundle",
    },
    "resolve_blocker": {"operation", "decisionBead", "outcome", "answer", "runBundle"},
    "runner_status": {"operation", "root"},
}


def _require_object(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("ticket gateway payload must be an object")
    return payload


def _operation(payload: Dict[str, Any]) -> str:
    operation = payload.get("operation")
    if operation not in VALID_OPERATIONS:
        raise ValueError(f"operation must be one of {sorted(VALID_OPERATIONS)}")
    return str(operation)


def _scan_for_banned_keys(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in BANNED_KEYS:
                raise ValueError(f"shell-like gateway payload is not allowed: {path}.{key}")
            _scan_for_banned_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _scan_for_banned_keys(child, f"{path}[{i}]")


def validate_gateway_payload(payload: Any) -> str:
    data = _require_object(payload)
    _scan_for_banned_keys(data)
    operation = _operation(data)
    unknown = sorted(set(data) - ALLOWED_KEYS[operation])
    if unknown:
        raise ValueError(f"unsupported gateway field(s) for {operation}: {', '.join(unknown)}")
    return operation


def _require_string(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _require_target_bead(payload: Dict[str, Any]) -> str:
    """Accept the canonical wire key and legacy snake_case gateway payloads."""
    value = payload.get("targetBead", payload.get("target_bead"))
    if not isinstance(value, str) or not value.strip():
        raise ValueError("targetBead/target_bead is required")
    return value.strip()


def _optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("runBundle/runsDir must be a non-empty string when present")
    return Path(value)


def _runs_dir(payload: Dict[str, Any], runs_dir: Path | None) -> Path:
    return _optional_path(payload.get("runsDir")) or runs_dir or default_runs_dir()


def _normalize_labels(value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("labels must be a list of non-empty strings")
    return [item.strip() for item in value]


def _compact_item(bead: Dict[str, Any], *, runs_dir: Path | None = None) -> Dict[str, Any]:
    validation = validate_bead_orchestration_metadata(bead)
    item_id = str(bead.get("id") or "")
    runs = run_refs_by_bead(runs_dir or default_runs_dir()).get(item_id, []) if item_id else []
    return {
        "id": item_id,
        "title": bead.get("title"),
        "type": bead.get("issue_type") or bead.get("type"),
        "status": bead.get("status"),
        "priority": bead.get("priority"),
        "labels": bead.get("labels") or [],
        "metadataValidation": {
            "status": validation.get("status"),
            "dispatchable": validation.get("dispatchable"),
            "failures": validation.get("failures") or [],
            "blockers": validation.get("blockers") or [],
            "humanActions": validation.get("humanActions") or [],
        },
        "activeRunRefs": runs,
        "dependencies": bead.get("dependencies") or [],
        "dependents": bead.get("dependents") or [],
    }


def _require_beads_success(code: int, data: Any, err: str, action: str) -> Any:
    if code != 0:
        die(f"bd {action} failed: {err}", code or 1)
    return data


def _list_gateway(payload: Dict[str, Any], *, beads_runner: BeadsRunner, runs_dir: Path | None) -> Dict[str, Any]:
    code, data, err = beads_runner(["ready"])
    ready = _require_beads_success(code, data, err, "ready")
    items = [item for item in ready if isinstance(item, dict)] if isinstance(ready, list) else []
    if not bool(payload.get("includeEpics", True)):
        items = [item for item in items if item.get("issue_type") != "epic"]
    limit = payload.get("limit")
    if limit is not None:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        items = items[:limit]
    rd = _runs_dir(payload, runs_dir)
    return {"schemaVersion": 1, "operation": "list", "items": [_compact_item(item, runs_dir=rd) for item in items]}


def _show_gateway(payload: Dict[str, Any], *, beads_runner: BeadsRunner, runs_dir: Path | None) -> Dict[str, Any]:
    bead_id = _require_string(payload, "bead")
    code, data, err = beads_runner(["show", bead_id])
    bead = normalize_bead(_require_beads_success(code, data, err, "show"))
    if not bead:
        die(f"bead not found: {bead_id}", 1)
    return {"schemaVersion": 1, "operation": "show", "item": _compact_item(bead, runs_dir=_runs_dir(payload, runs_dir))}


def _tree_gateway(payload: Dict[str, Any], *, tree_builder: TreeBuilder, runs_dir: Path | None) -> Dict[str, Any]:
    root = payload.get("root") or payload.get("epic")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root or epic is required for tree")
    return {"schemaVersion": 1, "operation": "tree", "tree": tree_builder(root.strip(), runs_dir=_runs_dir(payload, runs_dir))}


def _create_draft_gateway(payload: Dict[str, Any], *, beads_runner: BeadsRunner) -> Dict[str, Any]:
    title = _require_string(payload, "title")
    description = _require_string(payload, "description")
    issue_type = str(payload.get("issueType") or "task")
    if issue_type not in ISSUE_TYPES:
        raise ValueError(f"issueType must be one of {sorted(ISSUE_TYPES)}")
    priority = payload.get("priority", 2)
    if not isinstance(priority, int) or not (0 <= priority <= 4):
        raise ValueError("priority must be an integer from 0 through 4")
    labels = sorted({"draft", "gateway", *_normalize_labels(payload.get("labels"))})
    args = [
        "create",
        title,
        "--type",
        issue_type,
        "--priority",
        str(priority),
        "--labels",
        ",".join(labels),
        "--description",
        description,
    ]
    if payload.get("acceptance") is not None:
        args.extend(["--acceptance", _require_string(payload, "acceptance")])
    if payload.get("parent") is not None:
        args.extend(["--parent", _require_string(payload, "parent")])
    metadata = payload.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object when present")
        pi_metadata = metadata.get("pi")
        if isinstance(pi_metadata, dict) and pi_metadata.get("approved") is True:
            raise ValueError("model gateway must not set metadata.pi.approved; resolve a human approval through the UI")
        args.extend(["--metadata", json.dumps(metadata, sort_keys=True, separators=(",", ":"))])
    code, data, err = beads_runner(args)
    created = _require_beads_success(code, data, err, "create draft")
    return {"schemaVersion": 1, "operation": "create_draft", "created": created}


def _request_approval_gateway(payload: Dict[str, Any], *, approval_creator: Callable[..., Dict[str, Any]]) -> Dict[str, Any]:
    result = approval_creator(
        kind="approval",
        target_bead=_require_target_bead(payload),
        question=_require_string(payload, "question"),
        context=_require_string(payload, "context"),
        options=payload.get("options"),
        default=payload.get("default"),
        requesting_run=payload.get("requestingRun"),
        preview=payload.get("preview"),
        run_bundle=_optional_path(payload.get("runBundle")),
    )
    return {"schemaVersion": 1, "operation": "request_approval", "approval": result}


def _resolve_blocker_gateway(payload: Dict[str, Any], *, approval_resolver: Callable[..., Dict[str, Any]]) -> Dict[str, Any]:
    outcome = _require_string(payload, "outcome")
    if outcome in {"approved", "answered"}:
        raise ValueError("model gateway cannot resolve approved or answered outcomes; use the human UI")
    result = approval_resolver(
        decision_bead=_require_string(payload, "decisionBead"),
        outcome=outcome,
        answer=payload.get("answer"),
        run_bundle=_optional_path(payload.get("runBundle")),
    )
    return {"schemaVersion": 1, "operation": "resolve_blocker", "resolution": result}


def _compact_lease(lease: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "leaseId": lease.get("leaseId"),
        "sessionId": lease.get("sessionId"),
        "client": lease.get("client"),
        "attachedAt": lease.get("attachedAt"),
        "lastSeenAt": lease.get("lastSeenAt"),
    }


def _normalize_runner_visibility(status: Dict[str, Any], *, service_state: str) -> Dict[str, Any]:
    leases_raw = status.get("leases") if isinstance(status.get("leases"), dict) else {}
    active_runs = [active_run_summary(item) for item in status.get("activeRuns") or [] if isinstance(item, dict)]
    budget = status.get("budget") if isinstance(status.get("budget"), dict) else dict(DEFAULT_BUDGET)
    service_metadata = status.get("service") if isinstance(status.get("service"), dict) else {}
    result = {
        "schemaVersion": 1,
        "status": status.get("status") or ("running" if status.get("running") else "not-running"),
        "running": bool(status.get("running")),
        "connected": bool(status.get("connected", service_state == "present")),
        "paused": bool(status.get("paused")),
        "draining": bool(status.get("draining")),
        "acceptingNewWork": bool(status.get("acceptingNewWork", False)),
        "schedulerEnabled": bool(status.get("schedulerEnabled", False)),
        "schedulerAlive": status.get("schedulerAlive") if isinstance(status.get("schedulerAlive"), bool) else None,
        "scheduler": status.get("scheduler") if isinstance(status.get("scheduler"), dict) else {},
        "root": status.get("root"),
        "heartbeatAt": status.get("heartbeatAt"),
        "updatedAt": status.get("updatedAt"),
        "leaseCount": len(leases_raw),
        "leases": [_compact_lease(lease) for lease in leases_raw.values() if isinstance(lease, dict)],
        "activeCount": len(active_runs),
        "activeRuns": active_runs,
        "firstActive": active_runs[0] if active_runs else None,
        "budget": budget,
        "service": {
            "state": service_state,
            "metadata": redact_service_metadata(service_metadata),
        },
    }
    if status.get("suggestedAction"):
        result["suggestedAction"] = status.get("suggestedAction")
    if status.get("detail"):
        result["detail"] = status.get("detail")
    return result


def _runner_status_gateway(payload: Dict[str, Any]) -> Dict[str, Any]:
    root = payload.get("root")
    if root is not None and not isinstance(root, str):
        raise ValueError("root must be a string when present")
    normalized_root = Path(root).expanduser() if root else None
    try:
        status = runner_client_status(root=normalized_root)
        runner = _normalize_runner_visibility(status, service_state="present")
    except RunnerClientError as exc:
        runner = _normalize_runner_visibility(exc.payload, service_state="absent")
    return {"schemaVersion": 1, "operation": "runner_status", "runner": runner}


def ticket_gateway(
    payload: Any,
    *,
    beads_runner: BeadsRunner = run_beads_json,
    tree_builder: TreeBuilder = build_work_tree,
    approval_creator: Callable[..., Dict[str, Any]] = create_beads_approval_request,
    approval_resolver: Callable[..., Dict[str, Any]] = resolve_beads_approval_request,
    runs_dir: Path | None = None,
) -> Dict[str, Any]:
    data = _require_object(payload)
    operation = validate_gateway_payload(data)
    if operation == "list":
        return _list_gateway(data, beads_runner=beads_runner, runs_dir=runs_dir)
    if operation == "show":
        return _show_gateway(data, beads_runner=beads_runner, runs_dir=runs_dir)
    if operation == "tree":
        return _tree_gateway(data, tree_builder=tree_builder, runs_dir=runs_dir)
    if operation == "create_draft":
        return _create_draft_gateway(data, beads_runner=beads_runner)
    if operation == "request_approval":
        return _request_approval_gateway(data, approval_creator=approval_creator)
    if operation == "resolve_blocker":
        return _resolve_blocker_gateway(data, approval_resolver=approval_resolver)
    if operation == "runner_status":
        return _runner_status_gateway(data)
    raise ValueError(f"unsupported operation: {operation}")


def _read_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.payload:
        text = args.payload
    elif args.payload_file:
        text = Path(args.payload_file).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        die("provide --payload, --payload-file, or JSON on stdin", 2)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        die(f"gateway payload JSON is invalid: {exc}", 2)
    if not isinstance(parsed, dict):
        die("gateway payload must be a JSON object", 2)
    return parsed


def cmd_gateway(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt gateway", description="Execute strict ticket gateway operations.")
    parser.add_argument("--payload", help="JSON object payload")
    parser.add_argument("--payload-file", help="Read JSON payload from file")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default)")
    args = parser.parse_args(argv)
    try:
        result = ticket_gateway(_read_payload(args))
    except ValueError as exc:
        die(str(exc), 2)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = ["ticket_gateway", "validate_gateway_payload", "cmd_gateway"]
