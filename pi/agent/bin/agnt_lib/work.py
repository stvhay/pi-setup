from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from .actions import load_action
from .doctor import doctor_report
from .orchestration import validate_bead_orchestration_metadata
from .routing import select_model
from .runs import create_run_bundle, default_runs_dir, invoke_run_bundle, load_yaml_json, update_run_result
from .health import check_status_passed, work_health_report
from .maintenance import maintenance_create_beads, maintenance_due_report
from .runner_client import (
    RunnerClientError,
    daemon_serve,
    daemon_start,
    daemon_status,
    daemon_stop,
    runner_client_pause,
    runner_client_resume,
    runner_client_status,
    runner_client_tick,
)
from .worktree_policy import worktree_snapshot_for_bead


def beads_bin() -> str | None:
    return shutil.which("beads") or shutil.which("bd")


def run_beads_json(args: List[str]) -> tuple[int, Any, str]:
    exe = beads_bin()
    if not exe:
        return 127, None, "beads/bd executable not found"
    proc = subprocess.run([exe, *args, "--json"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return proc.returncode, None, proc.stderr
    try:
        return proc.returncode, json.loads(proc.stdout or "null"), proc.stderr
    except json.JSONDecodeError as exc:
        return 1, None, f"beads output was not JSON: {exc}"


def select_next_ready(items: Any) -> Dict[str, Any] | None:
    if not isinstance(items, list) or not items:
        return None
    work_items = [item for item in items if isinstance(item, dict) and item.get("issue_type") != "epic"]
    return (work_items or items)[0]


def normalize_bead(data: Any) -> Dict[str, Any] | None:
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data
    return None


def ref_id(ref: Any) -> str | None:
    if not isinstance(ref, dict):
        return None
    for key in ("id", "depends_on_id", "issue_id"):
        value = ref.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def ref_type(ref: Any) -> str:
    if not isinstance(ref, dict):
        return "blocks"
    value = ref.get("dependency_type") or ref.get("type")
    return str(value or "blocks")


def is_closed_status(value: Any) -> bool:
    return str(value or "").lower() == "closed"


def is_approval_like(node: Dict[str, Any] | None) -> bool:
    if not node:
        return False
    labels = {str(label) for label in node.get("labels") or []}
    # A plain "approval" label can describe feature work about approvals. Treat
    # durable human gates as decision beads or explicit human/human-gate labels.
    return node.get("type") == "decision" or bool(labels.intersection({"human", "human-gate"}))


def load_run_artifact(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


TERMINAL_RUN_STATUSES = {"succeeded", "failed", "blocked", "superseded"}


def run_refs_by_bead(runs_dir: Path | None = None) -> Dict[str, List[Dict[str, Any]]]:
    """Return run artifact references grouped by Beads id.

    This is intentionally read-only and tolerant of partial/old run bundles so a
    plan view never fails merely because one run artifact is stale or malformed.
    """
    root = runs_dir or default_runs_dir()
    refs: Dict[str, List[Dict[str, Any]]] = {}
    if not root.is_dir():
        return refs
    for bundle in sorted(path for path in root.iterdir() if path.is_dir()):
        invocation = load_run_artifact(bundle / "invocation.yaml")
        if not invocation:
            continue
        bead = invocation.get("bead")
        if not bead:
            continue
        result = load_run_artifact(bundle / "result.yaml") or {}
        status = str(result.get("status") or "unknown")
        active = not result.get("completedAt") and status not in TERMINAL_RUN_STATUSES
        refs.setdefault(str(bead), []).append({
            "id": str(invocation.get("id") or bundle.name),
            "bundle": str(bundle),
            "status": status,
            "active": active,
            "completedAt": result.get("completedAt"),
        })
    return refs


def fetch_bead(bead_id: str) -> tuple[Dict[str, Any] | None, str | None]:
    code, data, err = run_beads_json(["show", bead_id])
    if code != 0:
        return None, err or f"bd show {bead_id} failed"
    bead = normalize_bead(data)
    if not bead:
        return None, f"bd show {bead_id} returned no bead"
    return bead, None


def collect_ref_ids(bead: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in ("dependencies", "dependents"):
        for ref in bead.get(key) or []:
            rid = ref_id(ref)
            if rid and rid not in ids:
                ids.append(rid)
    return ids


def edge_key(edge: Dict[str, str]) -> tuple[str, str, str]:
    return edge["from"], edge["to"], edge["type"]


def normalized_node(bead: Dict[str, Any], run_refs: List[Dict[str, Any]]) -> Dict[str, Any]:
    dependencies = [ref_id(ref) for ref in bead.get("dependencies") or []]
    dependents = [ref_id(ref) for ref in bead.get("dependents") or []]
    validation = validate_bead_orchestration_metadata(bead)
    return {
        "id": bead.get("id"),
        "title": bead.get("title"),
        "type": bead.get("issue_type") or bead.get("type"),
        "status": bead.get("status"),
        "priority": bead.get("priority"),
        "labels": bead.get("labels") or [],
        "dependencies": [item for item in dependencies if item],
        "dependents": [item for item in dependents if item],
        "dependencyRefs": [
            {"id": rid, "type": ref_type(ref), "status": ref.get("status") if isinstance(ref, dict) else None}
            for ref in bead.get("dependencies") or []
            if (rid := ref_id(ref))
        ],
        "dependentRefs": [
            {"id": rid, "type": ref_type(ref), "status": ref.get("status") if isinstance(ref, dict) else None}
            for ref in bead.get("dependents") or []
            if (rid := ref_id(ref))
        ],
        "metadataValidation": {
            "status": validation.get("status"),
            "dispatchable": validation.get("dispatchable"),
            "failures": validation.get("failures") or [],
            "blockers": validation.get("blockers") or [],
            "humanActions": validation.get("humanActions") or [],
        },
        "runRefs": run_refs,
        "activeRunRefs": [ref for ref in run_refs if ref.get("active")],
        "approvalRefs": [],
        "blockerRefs": [],
    }


def build_work_tree(root_id: str, *, runs_dir: Path | None = None, max_depth: int = 50) -> Dict[str, Any]:
    """Build a durable Beads plan/dependency tree through the Beads CLI.

    The function uses `bd show --json` for every visited issue rather than
    reading `.beads/issues.jsonl` directly. The returned structure is stable JSON
    for later gateway/UI code and includes metadata validation and run refs.
    """
    run_refs = run_refs_by_bead(runs_dir)
    nodes: Dict[str, Dict[str, Any]] = {}
    raw_beads: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, str]] = []
    queue: List[tuple[str, int]] = [(root_id, 0)]
    seen = set()

    while queue:
        bead_id, depth = queue.pop(0)
        if bead_id in seen or depth > max_depth:
            continue
        seen.add(bead_id)
        bead, error = fetch_bead(bead_id)
        if error or bead is None:
            errors.append({"id": bead_id, "error": str(error)})
            continue
        bid = str(bead.get("id") or bead_id)
        raw_beads[bid] = bead
        nodes[bid] = normalized_node(bead, run_refs.get(bid, []))
        if depth < max_depth:
            for rid in collect_ref_ids(bead):
                if rid not in seen:
                    queue.append((rid, depth + 1))

    edges: List[Dict[str, str]] = []
    edge_keys: set[tuple[str, str, str]] = set()
    for bead_id, bead in raw_beads.items():
        for ref in bead.get("dependencies") or []:
            rid = ref_id(ref)
            if not rid:
                continue
            edge = {"from": rid, "to": bead_id, "type": ref_type(ref)}
            key = edge_key(edge)
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append(edge)
        for ref in bead.get("dependents") or []:
            rid = ref_id(ref)
            if not rid:
                continue
            edge = {"from": bead_id, "to": rid, "type": ref_type(ref)}
            key = edge_key(edge)
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append(edge)

    for node_id, node in nodes.items():
        related = node["dependencies"] + node["dependents"]
        node["approvalRefs"] = sorted({rid for rid in related if is_approval_like(nodes.get(rid))})
        blockers: List[str] = []
        for ref in node["dependencyRefs"]:
            rid = ref["id"]
            if ref["type"] == "parent-child":
                continue
            ref_status = ref.get("status") or (nodes.get(rid) or {}).get("status")
            if not is_closed_status(ref_status):
                blockers.append(rid)
        node["blockerRefs"] = sorted(set(blockers))

    return {
        "schemaVersion": 1,
        "root": root_id,
        "nodes": nodes,
        "edges": sorted(edges, key=lambda edge: (edge["from"], edge["to"], edge["type"])),
        "errors": errors,
        "summary": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "activeRunCount": sum(len(node["activeRunRefs"]) for node in nodes.values()),
            "blockedNodeCount": sum(1 for node in nodes.values() if node["blockerRefs"]),
            "invalidMetadataCount": sum(1 for node in nodes.values() if node["metadataValidation"]["status"] == "invalid"),
        },
    }


def render_work_tree_text(tree: Dict[str, Any]) -> str:
    nodes = tree.get("nodes") if isinstance(tree.get("nodes"), dict) else {}
    root = tree.get("root")
    lines = [f"Work tree: {root}"]
    for node_id in sorted(nodes):
        node = nodes[node_id]
        marker = "!" if node.get("blockerRefs") else "*" if node.get("activeRunRefs") else "-"
        lines.append(
            f"{marker} {node_id} [{node.get('type') or '?'} {node.get('status') or '?'} P{node.get('priority')}] "
            f"{node.get('title') or ''} metadata={node.get('metadataValidation', {}).get('status')}"
        )
        if node.get("blockerRefs"):
            lines.append(f"    blocked by: {', '.join(node['blockerRefs'])}")
        if node.get("approvalRefs"):
            lines.append(f"    approvals: {', '.join(node['approvalRefs'])}")
        if node.get("activeRunRefs"):
            lines.append("    active runs: " + ", ".join(str(ref.get("id")) for ref in node["activeRunRefs"]))
    if tree.get("errors"):
        lines.append("Errors:")
        lines.extend(f"- {item.get('id')}: {item.get('error')}" for item in tree["errors"])
    return "\n".join(lines)


def get_bead(bead_id: str | None) -> tuple[int, Dict[str, Any] | None, str]:
    if bead_id:
        code, data, err = run_beads_json(["show", bead_id])
        return code, normalize_bead(data), err
    code, data, err = run_beads_json(["ready"])
    if code != 0:
        return code, None, err
    return 0, select_next_ready(data), err


REQUIRED_WORK_PATTERNS = [
    re.compile(r"real usage evidence", re.IGNORECASE),
    re.compile(r"soak retrospective", re.IGNORECASE),
    re.compile(r"should be designed and tested after", re.IGNORECASE),
    re.compile(r"remaining integration work", re.IGNORECASE),
    re.compile(r"remain useful future refinements", re.IGNORECASE),
]


def iter_audit_files(scan_roots: List[Path]) -> List[Path]:
    files: List[Path] = []
    for root in scan_roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".json"}:
                    files.append(path)
    return files


def default_audit_roots() -> List[Path]:
    cwd = Path.cwd()
    return [path for path in [cwd / "docs", cwd / "README.md", cwd / "AGENTS.md", cwd / ".pi" / "runs"] if path.exists()]


def scan_required_work_signals(scan_roots: List[Path]) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    for path in iter_audit_files(scan_roots):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in REQUIRED_WORK_PATTERNS:
                if pattern.search(line):
                    signals.append({"path": str(path), "line": line_no, "pattern": pattern.pattern, "text": line.strip()})
                    break
    return signals


def work_audit_report(scan_roots: List[Path] | None = None) -> Dict[str, Any]:
    status_code, status_data, status_err = run_beads_json(["status"])
    if status_code != 0 and "no beads database found" in str(status_err).lower() and Path(".beads/issues.jsonl").is_file():
        bootstrap_code, _bootstrap_data, bootstrap_err = run_beads_json(["bootstrap", "--yes"])
        if bootstrap_code == 0:
            status_code, status_data, status_err = run_beads_json(["status"])
        else:
            status_err = f"{status_err}; bootstrap failed: {bootstrap_err}"
    ready_code, ready_data, ready_err = run_beads_json(["ready"])
    failures: List[str] = []
    if status_code != 0:
        failures.append(f"beads status failed: {status_err}")
    if ready_code != 0:
        failures.append(f"beads ready failed: {ready_err}")
    summary = status_data.get("summary", {}) if isinstance(status_data, dict) else {}
    open_issues = int(summary.get("open_issues") or 0)
    deferred_issues = int(summary.get("deferred_issues") or 0)
    ready_issues = int(summary.get("ready_issues") or 0)
    signals = scan_required_work_signals(scan_roots or default_audit_roots())
    risks: List[Dict[str, Any]] = []
    if not failures and open_issues == 0 and deferred_issues == 0 and signals:
        risks.append({
            "kind": "empty-work-graph-with-required-work-signals",
            "message": "Beads has no open/deferred work, but docs/run artifacts mention future or remaining work that may need beads.",
            "signalCount": len(signals),
        })
    return {
        "schemaVersion": 1,
        "passed": not failures and not risks,
        "summary": {"openIssues": open_issues, "readyIssues": ready_issues, "deferredIssues": deferred_issues},
        "readyCount": len(ready_data) if isinstance(ready_data, list) else None,
        "signals": signals,
        "risks": risks,
        "failures": failures,
    }


def infer_action(bead: Dict[str, Any]) -> str:
    labels = set(str(label) for label in bead.get("labels") or [])
    title = str(bead.get("title") or "").lower()
    if "implementation" in labels or "implement" in title:
        return "implement"
    if "research" in labels:
        return "research"
    if "planning" in labels or "plan" in title:
        return "plan"
    if "deployment" in labels or "finish" in title:
        return "finish"
    if "docs" in labels or "documentation" in labels:
        return "review"
    if "tests" in labels or "context-health" in labels:
        return "verify"
    if "prompts" in labels or "actions" in labels:
        return "review"
    if "artifacts" in labels or "schema" in labels:
        return "review"
    if "review" in title:
        return "review"
    return "review"


def _deduplicated_strings(*groups: Any) -> List[str]:
    result: List[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for value in group:
            if isinstance(value, str) and value and value not in result:
                result.append(value)
    return result


def dispatch_plan(bead: Dict[str, Any], action_id: str | None, target: List[str]) -> Dict[str, Any]:
    validation = validate_bead_orchestration_metadata(bead)
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    metadata_action = normalized.get("action") if isinstance(normalized.get("action"), str) else None
    action_mismatch = bool(action_id and metadata_action and action_id != metadata_action)
    action = action_id or metadata_action or infer_action(bead)
    _path, meta, _body = load_action(action)
    requested_role = normalized.get("role") if isinstance(normalized.get("role"), str) else None
    requested_skills = normalized.get("skills") if isinstance(normalized.get("skills"), list) else []
    effective_role = meta.get("defaultRole")
    effective_skills = meta.get("skills") or []
    overrides_requested_context = (requested_role is not None and requested_role != effective_role) or (requested_skills and requested_skills != effective_skills)
    return {
        "bead": bead.get("id"),
        "title": bead.get("title"),
        "status": bead.get("status"),
        "action": meta.get("id") or action,
        "dispatchError": f"explicit action {action_id!r} does not match metadata.pi.action {metadata_action!r}" if action_mismatch else None,
        "routingTask": meta.get("routingTask"),
        "skills": effective_skills,
        "role": effective_role,
        "requestedSkills": requested_skills,
        "requestedRole": requested_role,
        "overrideReason": "action-template defaults override requested worker context" if overrides_requested_context else None,
        "allowedEffects": meta.get("allowedEffects") or [],
        "inputRefs": _deduplicated_strings(normalized.get("inputRefs"), target),
        "outputContract": meta.get("outputContract"),
        "dryRunCommand": [
            "agnt",
            "action",
            "render",
            str(meta.get("id") or action),
            "--bead",
            str(bead.get("id")),
            *sum((["--target", item] for item in target), []),
            "--dry-run",
        ],
    }


def normalize_acceptance_criteria(value: Any) -> List[str]:
    if isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = re.split(r"[;\n]+", str(value or ""))
    return [item.strip() for item in raw_items if item.strip()]


def selection_policy_from_bead(bead: Dict[str, Any], validation: Dict[str, Any] | None = None) -> Dict[str, Any]:
    validation = validation or validate_bead_orchestration_metadata(bead)
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    model_policy = normalized.get("modelPolicy") if isinstance(normalized.get("modelPolicy"), dict) else {}
    return {
        "risk": normalized.get("risk") or "medium",
        "budget": normalized.get("budget") or "balanced",
        "modelPolicy": model_policy,
        "localOk": bool(model_policy.get("localOk", False)),
        "diversity": str(model_policy.get("diversity") or "normal"),
        "sessionPolicy": normalized.get("sessionPolicy") or "recorded",
        "memoryPolicy": normalized.get("memoryPolicy") or "auto",
        "closeout": normalized.get("closeout") or {},
    }


def ticket_metadata_snapshot(bead: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": bead.get("id"),
        "title": bead.get("title"),
        "description": bead.get("description"),
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
    }


def ephemeral_todo_seed(bead: Dict[str, Any], dispatch: Dict[str, Any], target: List[str]) -> List[Dict[str, Any]]:
    seed = [{"title": str(bead.get("title") or dispatch.get("title") or "Work item"), "source": str(bead.get("id") or dispatch.get("bead") or "") }]
    for item in target:
        seed.append({"title": f"Inspect {item}", "source": item})
    return seed


def dispatch_policy_snapshot(dispatch: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action": dispatch.get("action"),
        "routingTask": dispatch.get("routingTask"),
        "role": dispatch.get("role"),
        "requestedRole": dispatch.get("requestedRole"),
        "requestedSkills": dispatch.get("requestedSkills") or [],
        "overrideReason": dispatch.get("overrideReason"),
        "allowedEffects": dispatch.get("allowedEffects") or [],
        "risk": policy.get("risk"),
        "budget": policy.get("budget"),
        "modelPolicy": policy.get("modelPolicy") or {},
        "sessionPolicy": policy.get("sessionPolicy") or "recorded",
        "memoryPolicy": policy.get("memoryPolicy") or "auto",
        "closeout": policy.get("closeout") or {},
    }


def start_work(bead: Dict[str, Any], *, action_id: str | None, target: List[str], claim: bool, runs_dir: Path | None, id_value: str | None) -> Dict[str, Any]:
    dispatch = dispatch_plan(bead, action_id, target)
    validation = validate_bead_orchestration_metadata(bead)
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    if dispatch.get("dispatchError"):
        return {"dispatch": dispatch, "validation": validation, "dispatchError": str(dispatch["dispatchError"])}
    if dispatch.get("action") == "implement" and (normalized.get("action") != "implement" or not validation.get("dispatchable")):
        return {
            "dispatch": dispatch,
            "validation": validation,
            "dispatchError": "implement dispatch requires dispatchable implementation metadata with recorded human approval provenance",
        }
    policy = selection_policy_from_bead(bead, validation)
    model_selection = select_model(
        str(dispatch["routingTask"]),
        risk=str(policy["risk"]),
        budget=str(policy["budget"]),
        local_ok=bool(policy["localOk"]),
        model_policy=policy["modelPolicy"],
        diversity=str(policy["diversity"]),
    )
    if model_selection.get("routeStatus") != "selected":
        return {"dispatch": dispatch, "modelSelection": model_selection, "modelSelectionError": "no policy-compatible model candidate"}
    selection = model_selection["selection"]
    worktree_snapshot = worktree_snapshot_for_bead(bead, validation)
    bundle = create_run_bundle(
        action=str(dispatch["action"]),
        routing_task=str(dispatch["routingTask"]),
        input_refs=[str(item) for item in dispatch["inputRefs"]],
        skills=[str(item) for item in dispatch["skills"]],
        role=str(dispatch["role"]) if dispatch["role"] else None,
        requested_skills=[str(item) for item in dispatch.get("requestedSkills") or []],
        requested_role=str(dispatch["requestedRole"]) if dispatch.get("requestedRole") else None,
        override_reason=str(dispatch["overrideReason"]) if dispatch.get("overrideReason") else None,
        bead=str(dispatch["bead"]) if dispatch["bead"] else None,
        selected_model=str(selection["target"]),
        thinking_level=str(selection["thinkingLevel"]),
        model_selection=selection,
        ticket_metadata=ticket_metadata_snapshot(bead, validation),
        ephemeral_todo_seed=ephemeral_todo_seed(bead, dispatch, target),
        worktree=worktree_snapshot,
        dispatch_policy=dispatch_policy_snapshot(dispatch, policy),
        session_policy=str(policy.get("sessionPolicy") or "recorded"),
        memory_policy=str(policy.get("memoryPolicy") or "auto"),
        allowed_effects=[str(item) for item in dispatch["allowedEffects"]],
        acceptance_criteria=normalize_acceptance_criteria(bead.get("acceptance_criteria") or bead.get("acceptanceCriteria")),
        output_contract=str(dispatch["outputContract"]),
        approval_refs=[str(item) for item in normalized.get("approvalRefs") or []],
        decision_refs=[str(item) for item in normalized.get("decisionRefs") or []],
        human_approval=normalized.get("humanApproval") if isinstance(normalized.get("humanApproval"), dict) else None,
        continuation=normalized.get("continuation") if isinstance(normalized.get("continuation"), dict) else None,
        runs_dir=runs_dir,
        id_value=id_value,
    )
    bead_update: Dict[str, Any] | None = None
    if claim and dispatch.get("bead"):
        code, data, err = run_beads_json(["update", str(dispatch["bead"]), "--claim"])
        if code != 0:
            return {"bundle": str(bundle), "dispatch": dispatch, "modelSelection": model_selection, "beadUpdateError": err, "beadUpdateCode": code}
        bead_update = {"code": code, "result": data}
    return {"bundle": str(bundle), "invocation": str(bundle / "invocation.yaml"), "result": str(bundle / "result.yaml"), "dispatch": dispatch, "modelSelection": model_selection, "beadUpdate": bead_update}


def run_work(
    bead: Dict[str, Any],
    *,
    action_id: str | None,
    target: List[str],
    claim: bool,
    close_bead: bool,
    model: str | None,
    runs_dir: Path | None,
    id_value: str | None,
    metrics_dir: Path | None = None,
    record_session: bool = False,
    session_id: str | None = None,
    session_name: str | None = None,
) -> Dict[str, Any]:
    if model:
        return {"modelOverrideError": "agnt work run uses policy-selected models; pass risk/budget/local/modelPolicy constraints instead of a direct model override"}
    started = start_work(
        bead,
        action_id=action_id,
        target=target,
        claim=claim,
        runs_dir=runs_dir,
        id_value=id_value,
    )
    if started.get("beadUpdateError") or started.get("dispatchError") or started.get("modelSelectionError"):
        return {"started": started, **({"dispatchError": started["dispatchError"]} if started.get("dispatchError") else {})}
    bundle = Path(str(started["bundle"]))
    invoked = invoke_run_bundle(
        bundle,
        model=None,
        metrics_dir=metrics_dir,
        record_session=record_session,
        session_id=session_id,
        session_name=session_name,
    )
    closed = None
    if close_bead and invoked.get("exitCode") == 0:
        summary = str(invoked.get("result", {}).get("summary") or "Run succeeded")
        closed = finish_work(
            bundle,
            status="succeeded",
            summary=summary,
            evidence=[],
            artifacts=[],
            follow_ups=[],
            metrics_ref=str(invoked.get("metricsRef")) if invoked.get("metricsRef") else None,
            close_bead=True,
        )
    return {"started": started, "invoked": invoked, "closed": closed}


def bead_followup_checker(bead_id: str) -> tuple[bool, str | None]:
    code, _data, err = run_beads_json(["show", bead_id])
    if code != 0:
        return False, (err or "not found").strip()
    return True, None


def bead_ref_closed_checker(bead_id: str) -> tuple[bool, str | None]:
    code, data, err = run_beads_json(["show", bead_id])
    if code != 0:
        return False, (err or "not found").strip()
    bead = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
    if not isinstance(bead, dict):
        return False, "not found"
    if str(bead.get("status") or "").lower() != "closed":
        return False, f"status is {bead.get('status') or 'unknown'}"
    return True, None


def _result_check_failures(result: Dict[str, Any], key: str) -> List[str]:
    value = result.get(key) or []
    if not isinstance(value, list):
        return [f"result {key} must be a list"]
    failures: List[str] = []
    for check in value:
        if not isinstance(check, dict):
            failures.append(f"result {key} entry must be an object")
            continue
        if not check_status_passed(check.get("status")):
            failures.append(f"result {key} entry {check.get('name') or '<unnamed>'} is not passed: {check.get('status')}")
    return failures


def close_readiness_failures(
    result: Dict[str, Any],
    *,
    followup_checker=bead_followup_checker,
    ref_checker=bead_ref_closed_checker,
) -> List[str]:
    failures: List[str] = []
    if result.get("status") == "succeeded" and not result.get("evidence"):
        failures.append("succeeded bead closure requires at least one evidence entry")
    for key in ("healthChecks", "closeoutChecks"):
        failures.extend(_result_check_failures(result, key))
    for key in ("approvalRefs", "decisionRefs"):
        refs = result.get(key) or []
        if not isinstance(refs, list):
            failures.append(f"result {key} must be a list")
            continue
        for ref in refs:
            ok, detail = ref_checker(str(ref))
            if not ok:
                suffix = f": {detail}" if detail else ""
                failures.append(f"{key} bead is unresolved: {ref}{suffix}")
    follow_ups = result.get("followUps") or []
    if not isinstance(follow_ups, list):
        failures.append("result followUps must be a list")
        return failures
    for follow_up in follow_ups:
        ok, detail = followup_checker(str(follow_up))
        if not ok:
            suffix = f": {detail}" if detail else ""
            failures.append(f"follow-up bead is unresolved: {follow_up}{suffix}")
    return failures


def finish_work(bundle: Path, *, status: str, summary: str, evidence: List[str], artifacts: List[str], follow_ups: List[str], metrics_ref: str | None, close_bead: bool) -> Dict[str, Any]:
    result = update_run_result(
        bundle,
        status=status,
        summary=summary,
        evidence=evidence,
        artifacts=artifacts,
        follow_ups=follow_ups,
        metrics_ref=metrics_ref,
    )
    close_result: Dict[str, Any] | None = None
    if close_bead:
        if status != "succeeded":
            return {"result": result, "closeError": "--close-bead requires --status succeeded"}
        readiness_failures = close_readiness_failures(result)
        if readiness_failures:
            return {"result": result, "closeError": "; ".join(readiness_failures)}
        invocation = load_yaml_json(bundle / "invocation.yaml")
        bead_id = invocation.get("bead")
        if not bead_id:
            return {"result": result, "closeError": "invocation has no bead"}
        reason = summary or f"Run {invocation.get('id')} succeeded"
        code, data, err = run_beads_json(["close", str(bead_id), "--reason", reason])
        close_result = {"code": code, "result": data, "error": err if code else None}
    return {"result": result, "beadClose": close_result}


def _runner_symbol(name: str):
    value = globals().get(name)
    if value is not None:
        return value
    from . import runner as runner_mod

    value = getattr(runner_mod, name)
    globals()[name] = value
    return value


def cmd_work(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt work", description="Inspect beads-backed ready work and construct gated dispatch/run artifacts.")
    sub = parser.add_subparsers(dest="command")
    next_cmd = sub.add_parser("next", help="show the next ready bead")
    next_cmd.add_argument("--json", action="store_true")
    plan = sub.add_parser("plan", help="construct a dry-run dispatch plan for a bead")
    plan.add_argument("bead_id", nargs="?", help="bead id; defaults to first ready non-epic bead")
    plan.add_argument("--action")
    plan.add_argument("--target", action="append", default=[])
    plan.add_argument("--dry-run", action="store_true", help="required; this command does not dispatch workers")
    tree = sub.add_parser("tree", help="show a Beads plan/dependency tree with metadata validation and run refs")
    tree.add_argument("bead_id", nargs="?", help="root bead id; defaults to first ready non-epic bead")
    tree.add_argument("--epic", help="root epic id; alias for bead_id when viewing an epic")
    tree.add_argument("--json", action="store_true")
    tree.add_argument("--max-depth", type=int, default=50)
    tree.add_argument("--runs-dir")
    start = sub.add_parser("start", help="create a run bundle for a bead/action, optionally claiming the bead")
    start.add_argument("bead_id", nargs="?", help="bead id; defaults to first ready non-epic bead")
    start.add_argument("--action")
    start.add_argument("--target", action="append", default=[])
    start.add_argument("--claim", action="store_true", help="also mark the bead in_progress")
    start.add_argument("--runs-dir")
    start.add_argument("--id")
    start.add_argument("--dry-run", action="store_true", help="print plan without writing artifacts or mutating beads")
    run = sub.add_parser("run", help="start work, invoke a worker from the run artifact, and optionally close the bead")
    run.add_argument("bead_id", nargs="?", help="bead id; defaults to first ready non-epic bead")
    run.add_argument("--action")
    run.add_argument("--target", action="append", default=[])
    run.add_argument("--model", help="rejected for work dispatch; use routing policy constraints instead")
    run.add_argument("--claim", action="store_true", help="mark the bead in_progress before invoking")
    run.add_argument("--close-bead", action="store_true", help="close bead only if invocation succeeds")
    run.add_argument("--runs-dir")
    run.add_argument("--metrics-dir")
    run.add_argument("--preflight", action="store_true", help="run agnt doctor dispatch preflight before invoking the worker")
    run.add_argument("--id")
    run.add_argument("--dry-run", action="store_true", help="show dispatch plan without invoking")
    runner = sub.add_parser("runner", help="manage the project singleton work runner")
    runner_sub = runner.add_subparsers(dest="runner_command", required=True)
    runner_status_cmd = runner_sub.add_parser("status", help="show runner singleton status")
    runner_status_cmd.add_argument("--root")
    runner_status_cmd.add_argument("--json", action="store_true")
    runner_pause_cmd = runner_sub.add_parser("pause", help="pause accepting new runner work")
    runner_pause_cmd.add_argument("--root")
    runner_pause_cmd.add_argument("--reason")
    runner_pause_cmd.add_argument("--json", action="store_true")
    runner_resume_cmd = runner_sub.add_parser("resume", help="resume accepting runner work")
    runner_resume_cmd.add_argument("--root")
    runner_resume_cmd.add_argument("--json", action="store_true")
    runner_tick_cmd = runner_sub.add_parser("tick", help="process one bounded runner tick")
    runner_tick_cmd.add_argument("--root")
    runner_tick_cmd.add_argument("--dry-run", action="store_true", help="explain actions without starting/blocking work")
    runner_tick_cmd.add_argument("--json", action="store_true")
    runner_tick_cmd.add_argument("--limit", type=int, default=1)
    runner_tick_cmd.add_argument("--runs-dir")
    runner_tick_cmd.add_argument("--metrics-dir")
    daemon = sub.add_parser("daemon", help="manage the project-local runner service lifecycle")
    daemon_sub = daemon.add_subparsers(dest="daemon_command", required=True)
    daemon_status_cmd = daemon_sub.add_parser("status", help="show project-local runner service status")
    daemon_status_cmd.add_argument("--root")
    daemon_status_cmd.add_argument("--json", action="store_true")
    daemon_start_cmd = daemon_sub.add_parser("start", help="start the project-local runner service")
    daemon_start_cmd.add_argument("--root")
    daemon_start_cmd.add_argument("--host", default="127.0.0.1")
    daemon_start_cmd.add_argument("--port", type=int, default=0)
    daemon_start_cmd.add_argument("--concurrency", type=int)
    daemon_start_cmd.add_argument("--interval", type=float)
    daemon_start_cmd.add_argument("--json", action="store_true")
    daemon_stop_cmd = daemon_sub.add_parser("stop", help="drain or force-stop the project-local runner service")
    daemon_stop_cmd.add_argument("--root")
    daemon_stop_cmd.add_argument("--drain", action="store_true", help="request graceful drain; this is the default")
    daemon_stop_cmd.add_argument("--force", action="store_true", help="force service shutdown through the service API")
    daemon_stop_cmd.add_argument("--reason")
    daemon_stop_cmd.add_argument("--json", action="store_true")
    daemon_serve_cmd = daemon_sub.add_parser("serve", help=argparse.SUPPRESS)
    daemon_serve_cmd.add_argument("--root")
    daemon_serve_cmd.add_argument("--host", default="127.0.0.1")
    daemon_serve_cmd.add_argument("--port", type=int, default=0)
    daemon_serve_cmd.add_argument("--concurrency", type=int)
    daemon_serve_cmd.add_argument("--interval", type=float)
    daemon_serve_cmd.add_argument("--json", action="store_true")
    loop = sub.add_parser("loop", help="deprecated; use agnt work daemon start")
    loop.add_argument("--root")
    loop.add_argument("--interval", type=float, default=30.0)
    loop.add_argument("--max-ticks", type=int, default=None)
    loop.add_argument("--limit", type=int, default=1)
    loop.add_argument("--dry-run", action="store_true")
    loop.add_argument("--json", action="store_true")
    audit = sub.add_parser("audit", help="audit Beads queue health against unresolved required-work signals")
    audit.add_argument("--json", action="store_true")
    audit.add_argument("--scan-root", action="append", default=[], help="file or directory to scan; defaults to docs, README, AGENTS, and .pi/runs")
    health = sub.add_parser("health", help="run read-only rail-guard checks over runs, runner state, Beads refs, and worktrees")
    health.add_argument("--json", action="store_true")
    health.add_argument("--root")
    health.add_argument("--runs-dir")
    health.add_argument("--stale-after-hours", type=float, default=24.0)
    health.add_argument("--strict-checkout", action="store_true", help="treat dirty current checkout as a failure instead of a warning")
    health.add_argument("--no-beads", action="store_true", help="skip bd blocked inspection; run artifact refs are still resolved")
    maintenance = sub.add_parser("maintenance", help="inspect and create self-improvement maintenance checkpoints")
    maintenance_sub = maintenance.add_subparsers(dest="maintenance_command", required=True)
    maintenance_due = maintenance_sub.add_parser("due", help="show maintenance modes due from durable project signals")
    maintenance_due.add_argument("--json", action="store_true")
    maintenance_due.add_argument("--root")
    maintenance_due.add_argument("--runs-dir")
    maintenance_due.add_argument("--no-beads", action="store_true", help="do not inspect Beads list; useful for isolated tests")
    maintenance_create = maintenance_sub.add_parser("create-beads", help="create or preview maintenance checkpoint Beads")
    maintenance_create.add_argument("--dry-run", action="store_true", help="preview bead specs without mutating Beads")
    maintenance_create.add_argument("--apply", action="store_true", help="explicitly create Beads; never implied")
    maintenance_create.add_argument("--json", action="store_true")
    maintenance_create.add_argument("--root")
    maintenance_create.add_argument("--runs-dir")
    maintenance_create.add_argument("--no-beads", action="store_true", help="compute due report without Beads list before preview")
    finish = sub.add_parser("finish", help="update a run result and optionally close its bead")
    finish.add_argument("bundle")
    finish.add_argument("--status", required=True, choices=["succeeded", "failed", "blocked", "needs-human", "superseded"])
    finish.add_argument("--summary", required=True)
    finish.add_argument("--evidence", action="append", default=[])
    finish.add_argument("--artifact", action="append", default=[])
    finish.add_argument("--follow-up", action="append", default=[])
    finish.add_argument("--metrics-ref")
    finish.add_argument("--close-bead", action="store_true", help="close the invocation bead; requires succeeded status")
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.command == "next":
        code, data, err = run_beads_json(["ready"])
        if code != 0:
            print(err, file=sys.stderr)
            return code
        item = select_next_ready(data)
        result = {"schemaVersion": 1, "item": item}
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else (json.dumps(item, indent=2, sort_keys=True) if item else "No ready work"))
        return 0
    if args.command == "plan":
        if not args.dry_run:
            print("agnt work plan is dry-run only; pass --dry-run", file=sys.stderr)
            return 2
        code, bead, err = get_bead(args.bead_id)
        if code != 0:
            print(err, file=sys.stderr)
            return code
        if not bead:
            print("No bead found", file=sys.stderr)
            return 1
        print(json.dumps({"schemaVersion": 1, "dryRun": True, "dispatch": dispatch_plan(bead, args.action, args.target)}, indent=2, sort_keys=True))
        return 0
    if args.command == "tree":
        root_id = args.epic or args.bead_id
        if not root_id:
            code, bead, err = get_bead(None)
            if code != 0:
                print(err, file=sys.stderr)
                return code
            if not bead or not bead.get("id"):
                print("No bead found", file=sys.stderr)
                return 1
            root_id = str(bead["id"])
        tree_result = build_work_tree(
            str(root_id),
            runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else default_runs_dir(),
            max_depth=args.max_depth,
        )
        output = {"schemaVersion": 1, "tree": tree_result}
        print(json.dumps(output, indent=2, sort_keys=True) if args.json else render_work_tree_text(tree_result))
        return 1 if tree_result.get("errors") else 0
    if args.command == "start":
        code, bead, err = get_bead(args.bead_id)
        if code != 0:
            print(err, file=sys.stderr)
            return code
        if not bead:
            print("No bead found", file=sys.stderr)
            return 1
        if args.dry_run:
            print(json.dumps({"schemaVersion": 1, "dryRun": True, "dispatch": dispatch_plan(bead, args.action, args.target), "wouldClaim": args.claim}, indent=2, sort_keys=True))
            return 0
        result = start_work(
            bead,
            action_id=args.action,
            target=args.target,
            claim=args.claim,
            runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else None,
            id_value=args.id,
        )
        print(json.dumps({"schemaVersion": 1, **result}, indent=2, sort_keys=True))
        return 1 if result.get("beadUpdateError") or result.get("dispatchError") or result.get("modelSelectionError") else 0
    if args.command == "run":
        if args.model:
            print(json.dumps({
                "schemaVersion": 1,
                "modelOverrideError": "agnt work run uses policy-selected models; pass risk/budget/local/modelPolicy constraints instead of a direct model override",
            }, indent=2, sort_keys=True))
            return 2
        if args.preflight:
            report = doctor_report(check_names=["command.pi", "command.bd", "provider.env", "catalog.parse"])
            if report.get("failures"):
                print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
                return 1
            if report.get("warnings"):
                print("agnt work preflight warnings:", file=sys.stderr)
                for warning in report.get("warnings") or []:
                    print(f"- {warning.get('id')}: {warning.get('message')}", file=sys.stderr)
        code, bead, err = get_bead(args.bead_id)
        if code != 0:
            print(err, file=sys.stderr)
            return code
        if not bead:
            print("No bead found", file=sys.stderr)
            return 1
        if args.dry_run:
            print(json.dumps({"schemaVersion": 1, "dryRun": True, "dispatch": dispatch_plan(bead, args.action, args.target), "wouldClaim": args.claim, "wouldCloseBead": args.close_bead, "model": args.model}, indent=2, sort_keys=True))
            return 0
        result = run_work(
            bead,
            action_id=args.action,
            target=args.target,
            claim=args.claim,
            close_bead=args.close_bead,
            model=args.model,
            runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else None,
            id_value=args.id,
            metrics_dir=Path(args.metrics_dir).expanduser() if args.metrics_dir else None,
        )
        print(json.dumps({"schemaVersion": 1, **result}, indent=2, sort_keys=True))
        if result.get("modelOverrideError") or result.get("modelSelectionError"):
            return 2
        invoked = result.get("invoked") if isinstance(result, dict) else None
        return int(invoked.get("exitCode") or 0) if isinstance(invoked, dict) else 1
    if args.command == "runner":
        root = Path(args.root).expanduser() if getattr(args, "root", None) else None
        try:
            if args.runner_command == "status":
                result = runner_client_status(root=root)
            elif args.runner_command == "pause":
                result = runner_client_pause(root=root, reason=args.reason)
            elif args.runner_command == "resume":
                result = runner_client_resume(root=root)
            elif args.runner_command == "tick":
                result = runner_client_tick(
                    root=root,
                    dry_run=args.dry_run,
                    limit=args.limit,
                    runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else None,
                    metrics_dir=Path(args.metrics_dir).expanduser() if args.metrics_dir else None,
                )
            else:
                parser.print_help(sys.stderr)
                return 2
        except RunnerClientError as exc:
            print(json.dumps(exc.payload, indent=2, sort_keys=True))
            return 2
        print(json.dumps(result, indent=2, sort_keys=True) if getattr(args, "json", False) else json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "daemon":
        root = Path(args.root).expanduser() if getattr(args, "root", None) else None
        if args.daemon_command == "status":
            result = daemon_status(root=root)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.daemon_command == "start":
            result = daemon_start(root=root, host=args.host, port=args.port, concurrency=args.concurrency, interval=args.interval)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("started") or result.get("alreadyRunning") else 1
        if args.daemon_command == "stop":
            if args.drain and args.force:
                print("choose either --drain or --force, not both", file=sys.stderr)
                return 2
            result = daemon_stop(root=root, drain=not args.force, force=args.force, reason=args.reason)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("draining") or result.get("stopping") else 1
        if args.daemon_command == "serve":
            result = daemon_serve(root=root, host=args.host, port=args.port, concurrency=args.concurrency, interval=args.interval)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("served") else 1
        parser.print_help(sys.stderr)
        return 2
    if args.command == "loop":
        result = {
            "schemaVersion": 1,
            "deprecated": True,
            "error": "agnt work loop has been replaced by the project-local runner service lifecycle",
            "suggestedAction": "agnt work daemon start --json",
        }
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
        return 2
    if args.command == "audit":
        roots = [Path(item).expanduser() for item in args.scan_root] if args.scan_root else None
        report = work_audit_report(scan_roots=roots)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print("PASS" if report["passed"] else "FAIL")
            print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1
    if args.command == "maintenance":
        root_arg = Path(args.root).expanduser() if getattr(args, "root", None) else None
        runs_arg = Path(args.runs_dir).expanduser() if getattr(args, "runs_dir", None) else None
        if args.maintenance_command == "due":
            report = maintenance_due_report(
                root=root_arg,
                runs_dir=runs_arg,
                beads=[] if args.no_beads else None,
            )
            print(json.dumps(report, indent=2, sort_keys=True) if args.json else json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.maintenance_command == "create-beads":
            if args.apply and args.dry_run:
                print("choose either --dry-run or --apply, not both", file=sys.stderr)
                return 2
            if not args.apply and not args.dry_run:
                print("agnt work maintenance create-beads is dry-run by default; pass --dry-run or explicit --apply", file=sys.stderr)
                return 2
            report = maintenance_due_report(
                root=root_arg,
                runs_dir=runs_arg,
                beads=[] if args.no_beads else None,
            )
            result = maintenance_create_beads(report, dry_run=not args.apply)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
            return 0 if not result.get("failures") else 1
    if args.command == "health":
        report = work_health_report(
            root=Path(args.root).expanduser() if args.root else None,
            runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else None,
            stale_after_hours=args.stale_after_hours,
            strict_checkout=args.strict_checkout,
            include_beads=not args.no_beads,
        )
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print("PASS" if report["passed"] else "FAIL")
            print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1
    if args.command == "finish":
        result = finish_work(
            Path(args.bundle).expanduser(),
            status=args.status,
            summary=args.summary,
            evidence=args.evidence,
            artifacts=args.artifact,
            follow_ups=args.follow_up,
            metrics_ref=args.metrics_ref,
            close_bead=args.close_bead,
        )
        print(json.dumps({"schemaVersion": 1, **result}, indent=2, sort_keys=True))
        if result.get("closeError"):
            return 2
        close = result.get("beadClose")
        return int(close.get("code") or 0) if isinstance(close, dict) else 0
    parser.print_help(sys.stderr)
    return 2
