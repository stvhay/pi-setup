from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .core import die
from .runs import update_run_result
from .work import run_beads_json

VALID_KINDS = {"approval", "question"}
VALID_OUTCOMES = {"approved", "answered", "rejected", "cancelled", "timed-out"}
CLOSING_OUTCOMES = {"approved", "answered"}
BLOCKED_OUTCOMES = VALID_OUTCOMES - CLOSING_OUTCOMES
REQUIRED_PREVIEW_FIELDS = ["action", "scope", "consequences", "reversibility", "closeoutPath"]
BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]


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


def approval_request_payload(
    *,
    kind: str,
    target_bead: str,
    question: str,
    context: str,
    options: List[str],
    default: str | None,
    requesting_run: str | None,
    preview: Dict[str, Any],
    created_at: str | None = None,
) -> Dict[str, Any]:
    """Build the durable Beads decision payload for a human gate.

    The payload is intentionally plain JSON so the CLI, runner, and Pi extension
    can share one auditable representation. Approval previews include the
    informed-consent fields required by the approval-confirmation design.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(VALID_KINDS)}")
    target = _require_nonempty("target_bead", target_bead)
    prompt = _require_nonempty("question", question)
    body_context = _require_nonempty("context", context)
    choices = _normalize_options(options)
    chosen_default = default.strip() if isinstance(default, str) and default.strip() else choices[0]
    if chosen_default not in choices:
        raise ValueError("default must match one of the options")
    normalized_preview = _normalize_preview(preview)
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
        "requestingRun": requesting_run,
        "question": prompt,
        "context": body_context,
        "options": choices,
        "default": chosen_default,
        "preview": normalized_preview,
        "status": "pending",
        "createdAt": timestamp,
    }
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
        f"Requesting run: {requesting_run or 'unknown'}",
        f"Target bead: {target}",
        "",
        "Approval preview:",
        f"- Action: {normalized_preview['action']}",
        f"- Scope: {normalized_preview['scope']}",
        f"- Consequences: {normalized_preview['consequences']}",
        f"- Reversibility: {normalized_preview['reversibility']}",
        f"- Closeout path: {normalized_preview['closeoutPath']}",
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


def _require_beads_success(code: int, data: Any, err: str, action: str) -> Any:
    if code != 0:
        die(f"bd {action} failed: {err}", code or 1)
    return data


def _decision_id_from_create(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("id"), str) and data["id"]:
        return data["id"]
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("id"):
        return str(data[0]["id"])
    die("bd create did not return a decision id", 1)


def create_beads_approval_request(
    *,
    kind: str,
    target_bead: str,
    question: str,
    context: str,
    options: List[str],
    default: str | None = None,
    requesting_run: str | None = None,
    preview: Dict[str, Any],
    run_bundle: Path | None = None,
    beads_runner: BeadsRunner = run_beads_json,
) -> Dict[str, Any]:
    payload = approval_request_payload(
        kind=kind,
        target_bead=target_bead,
        question=question,
        context=context,
        options=options,
        default=default,
        requesting_run=requesting_run,
        preview=preview,
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
    created = _require_beads_success(code, data, err, "create approval request")
    decision_bead = _decision_id_from_create(created)

    dep_args = ["dep", decision_bead, "--blocks", target_bead]
    dep_code, dep_data, dep_err = beads_runner(dep_args)
    _require_beads_success(dep_code, dep_data, dep_err, "dep approval blocker")

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
    return approval


def resolve_beads_approval_request(
    *,
    decision_bead: str,
    outcome: str,
    answer: str | None = None,
    resolver: Dict[str, str] | None = None,
    run_bundle: Path | None = None,
    beads_runner: BeadsRunner = run_beads_json,
) -> Dict[str, Any]:
    decision = _require_nonempty("decision_bead", decision_bead)
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(VALID_OUTCOMES)}")
    if outcome in CLOSING_OUTCOMES:
        if not isinstance(resolver, dict) or resolver.get("kind") != "human-ui" or not isinstance(resolver.get("sessionId"), str) or not resolver["sessionId"].strip():
            raise ValueError("approved or answered outcomes require human-ui resolver provenance")
    answer_text = answer.strip() if isinstance(answer, str) and answer.strip() else outcome

    show_code, show_data, show_err = beads_runner(["show", decision])
    shown = _require_beads_success(show_code, show_data, show_err, "show approval request")
    metadata = _metadata_from_bead(shown)
    approval = _approval_from_metadata(metadata)
    kind = str(approval.get("kind") or "approval")
    approval.update({
        "status": outcome,
        "answer": answer_text,
        "resolvedAt": utc_now(),
    })
    if resolver is not None:
        approval["resolver"] = dict(resolver)

    note = f"Beads-backed {kind} resolved as {outcome}: {answer_text}"
    update_args = ["update", decision, "--metadata", _json_arg(metadata), "--append-notes", note]
    update_code, update_data, update_err = beads_runner(update_args)
    _require_beads_success(update_code, update_data, update_err, "update approval resolution")

    blocker_visible = outcome in BLOCKED_OUTCOMES
    target_update_result = None
    if kind == "approval" and outcome == "approved":
        target_bead = _require_nonempty("target_bead", approval.get("targetBead"))
        target_code, target_data, target_err = beads_runner(["show", target_bead])
        target = _require_beads_success(target_code, target_data, target_err, "show approval target")
        target_metadata = _metadata_from_bead(target)
        target_pi = target_metadata.setdefault("pi", {})
        if not isinstance(target_pi, dict):
            target_metadata["pi"] = target_pi = {}
        target_pi["approved"] = True
        target_pi["humanApproval"] = {
            "decisionBead": decision,
            "resolver": dict(resolver or {}),
        }
        target_update_code, target_update_data, target_update_err = beads_runner([
            "update", target_bead, "--metadata", _json_arg(target_metadata),
            "--append-notes", f"Human approval {decision} recorded with UI resolver provenance.",
        ])
        target_update_result = _require_beads_success(target_update_code, target_update_data, target_update_err, "update approval target")

    close_result = None
    if not blocker_visible:
        close_code, close_data, close_err = beads_runner(["close", decision, "--reason", note])
        close_result = _require_beads_success(close_code, close_data, close_err, "close approval request")

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
    request.add_argument("--target-bead", required=True)
    request.add_argument("--question", required=True)
    request.add_argument("--context", required=True)
    request.add_argument("--option", action="append", required=True)
    request.add_argument("--default")
    request.add_argument("--requesting-run")
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
    resolve.add_argument("--resolver-kind")
    resolve.add_argument("--resolver-session")
    resolve.add_argument("--run-bundle", type=Path)
    resolve.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "request":
            result = create_beads_approval_request(
                kind=args.kind,
                target_bead=args.target_bead,
                question=args.question,
                context=args.context,
                options=args.option,
                default=args.default,
                requesting_run=args.requesting_run,
                preview=_preview_from_args(args),
                run_bundle=args.run_bundle,
            )
        else:
            resolver = None
            if args.resolver_kind is not None or args.resolver_session is not None:
                resolver = {"kind": args.resolver_kind or "", "sessionId": args.resolver_session or ""}
            result = resolve_beads_approval_request(
                decision_bead=args.decision_bead,
                outcome=args.outcome,
                answer=args.answer,
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
    "cmd_approvals",
]
