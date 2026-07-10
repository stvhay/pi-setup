from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .core import ROOT, die
from .invoke import invoke_one, safe_target_name
from .metrics import default_metrics_dir, git_root, write_json
from .tasks import preferred_models

VALID_STATUSES = {"succeeded", "failed", "blocked", "needs-human", "superseded"}
VALID_SESSION_POLICIES = {"recorded", "no-session"}
VALID_MEMORY_POLICIES = {"auto", "active", "passive", "disabled"}
DEFAULT_ALLOWED_EFFECTS = ["read_workspace", "write_artifacts"]
WRITE_EFFECTS = {"edit_files", "write_workspace", "update_beads", "external_write", "push", "deploy", "delete_files"}
READ_ONLY_WORKER_TOOLS = ["read", "grep", "find", "ls"]
READ_COMMAND_WORKER_TOOLS = ["read", "bash", "grep", "find", "ls"]
WRITE_WORKER_TOOLS = ["read", "bash", "edit", "write", "grep", "find", "ls"]
UNRESOLVED_TOOL_CALL_MARKERS = ("<|tool_call>", "<tool_call|>")
READ_ONLY_TIMEOUT_SECONDS = 300
WRITE_TIMEOUT_SECONDS = 900


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    chars: List[str] = []
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {"-", "_", " ", ".", "/", ":"}:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "run"


def default_runs_dir() -> Path:
    return git_root() / ".pi" / "runs"


def run_id(action: str, bead: str | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = slugify(bead or action)
    return f"{stamp}-{suffix}"


def write_yaml_json(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON content to a .yaml file.

    JSON is a valid YAML subset and keeps this helper dependency-free while
    preserving the architecture's invocation.yaml/result.yaml filenames.
    """
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _deduplicated_refs(*groups: List[str] | None) -> List[str]:
    refs: List[str] = []
    for group in groups:
        for value in group or []:
            if isinstance(value, str) and value and value not in refs:
                refs.append(value)
    return refs


def create_run_bundle(
    *,
    action: str,
    routing_task: str,
    input_refs: List[str] | None = None,
    skills: List[str] | None = None,
    role: str | None = None,
    requested_skills: List[str] | None = None,
    requested_role: str | None = None,
    override_reason: str | None = None,
    bead: str | None = None,
    model: str | None = None,
    selected_model: str | None = None,
    thinking_level: str | None = None,
    model_selection: Dict[str, Any] | None = None,
    ticket_metadata: Dict[str, Any] | None = None,
    ephemeral_todo_seed: List[Dict[str, Any]] | None = None,
    worktree: Dict[str, Any] | None = None,
    dispatch_policy: Dict[str, Any] | None = None,
    session_policy: str | None = None,
    memory_policy: str | None = None,
    allowed_effects: List[str] | None = None,
    acceptance_criteria: List[str] | None = None,
    output_contract: str | None = None,
    approval_refs: List[str] | None = None,
    decision_refs: List[str] | None = None,
    human_approval: Dict[str, Any] | None = None,
    continuation: Dict[str, Any] | None = None,
    runs_dir: Path | None = None,
    id_value: str | None = None,
) -> Path:
    rid = id_value or run_id(action, bead)
    bundle = (runs_dir or default_runs_dir()) / rid
    artifacts = bundle / "artifacts"
    live = bundle / "live"
    artifacts.mkdir(parents=True, exist_ok=True)
    live.mkdir(parents=True, exist_ok=True)
    session_log = live / "session.jsonl"
    live_status = live / "status.json"
    lessons_path = artifacts / "lessons.md"
    handoff_path = artifacts / "handoff.md"
    normalized_input_refs = _deduplicated_refs(input_refs)
    human_decision_ref = human_approval.get("decisionBead") if isinstance(human_approval, dict) else None
    continuation_approval_ref = continuation.get("approvalRef") if isinstance(continuation, dict) else None
    normalized_approval_refs = _deduplicated_refs(
        approval_refs,
        [human_decision_ref] if isinstance(human_decision_ref, str) else None,
        [continuation_approval_ref] if isinstance(continuation_approval_ref, str) else None,
    )
    normalized_decision_refs = _deduplicated_refs(decision_refs)
    provenance = {
        "schemaVersion": 1,
        "bead": bead,
        "inputRefs": normalized_input_refs,
        "approvalRefs": normalized_approval_refs,
        "decisionRefs": normalized_decision_refs,
        "humanApproval": copy.deepcopy(human_approval),
        "continuation": copy.deepcopy(continuation),
        "requestedWorkerContext": {
            "role": requested_role,
            "skills": list(requested_skills or []),
        },
        "effectiveWorkerContext": {
            "role": role,
            "skills": list(skills or []),
        },
        "overrideReason": override_reason,
        "selectedModel": selected_model or model,
        "thinkingLevel": thinking_level,
        "modelSelection": copy.deepcopy(model_selection),
        "allowedEffects": list(allowed_effects or DEFAULT_ALLOWED_EFFECTS),
        "worktree": copy.deepcopy(worktree),
    }
    invocation = {
        "schemaVersion": 1,
        "id": rid,
        "bead": bead,
        "action": action,
        "routingTask": routing_task,
        "inputRefs": normalized_input_refs,
        "skills": skills or [],
        "role": role,
        "requestedSkills": requested_skills or [],
        "requestedRole": requested_role,
        "effectiveSkills": skills or [],
        "effectiveRole": role,
        "overrideReason": override_reason,
        "model": model or selected_model,
        "selectedModel": selected_model or model,
        "thinkingLevel": thinking_level,
        "modelSelection": model_selection,
        "ticketMetadata": ticket_metadata,
        "ephemeralTodoSeed": ephemeral_todo_seed or [],
        "worktree": worktree,
        "dispatchPolicy": dispatch_policy,
        "sessionPolicy": session_policy or "recorded",
        "memoryPolicy": memory_policy or "auto",
        "allowedEffects": allowed_effects or list(DEFAULT_ALLOWED_EFFECTS),
        "acceptanceCriteria": acceptance_criteria or [],
        "outputContract": output_contract,
        "provenance": provenance,
        "createdAt": utc_now(),
    }
    session_log.write_text(json.dumps({"timestamp": utc_now(), "phase": "created", "runId": rid, "event": "run_bundle_created"}, sort_keys=True) + "\n", encoding="utf-8")
    write_yaml_json(
        live_status,
        {
            "schemaVersion": 1,
            "runId": rid,
            "phase": "created",
            "lastActivityAt": utc_now(),
            "currentModel": selected_model or model,
            "currentTool": None,
            "timeoutDeadlineAt": None,
            "liveLogPath": str(session_log.relative_to(bundle)),
            "lessonsPath": str(lessons_path.relative_to(bundle)),
            "handoffPath": str(handoff_path.relative_to(bundle)),
        },
    )
    lessons_path.write_text("# Lessons\n\nNo lessons reported yet.\n", encoding="utf-8")
    handoff_path.write_text("# Handoff\n\nRun bundle created; worker has not run yet.\n", encoding="utf-8")
    initial_artifacts = [
        str(artifacts.relative_to(bundle)),
        str(session_log.relative_to(bundle)),
        str(live_status.relative_to(bundle)),
        str(lessons_path.relative_to(bundle)),
        str(handoff_path.relative_to(bundle)),
    ]
    result = {
        "schemaVersion": 1,
        "invocationId": rid,
        "status": "needs-human",
        "summary": "Invocation artifact created; worker has not run yet.",
        "evidence": [],
        "artifacts": initial_artifacts,
        "followUps": [],
        "metricsRef": None,
        "sessionRef": None,
        "transcriptRef": None,
        "memorySummaryRef": None,
        "approvalRefs": list(normalized_approval_refs),
        "decisionRefs": list(normalized_decision_refs),
        "healthChecks": [],
        "closeoutChecks": [],
        "completedAt": None,
    }
    write_yaml_json(bundle / "invocation.yaml", invocation)
    write_yaml_json(bundle / "result.yaml", result)
    return bundle


def load_yaml_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"invalid JSON/YAML artifact {path}: {exc}", 1)
    if not isinstance(data, dict):
        die(f"artifact must be an object: {path}", 1)
    return data


def relative_to_bundle(bundle: Path, path: Path) -> str:
    try:
        return str(path.relative_to(bundle))
    except ValueError:
        return str(path)


def append_live_event(bundle: Path, event: Dict[str, Any]) -> None:
    live = bundle / "live"
    live.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": utc_now(), **event}
    with (live / "session.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def write_live_status(bundle: Path, **updates: Any) -> Dict[str, Any]:
    live = bundle / "live"
    live.mkdir(parents=True, exist_ok=True)
    path = live / "status.json"
    current = load_yaml_json(path) if path.exists() else {"schemaVersion": 1, "runId": bundle.name}
    current.update(updates)
    current["schemaVersion"] = 1
    current.setdefault("runId", bundle.name)
    current["lastActivityAt"] = utc_now()
    current.setdefault("liveLogPath", "live/session.jsonl")
    current.setdefault("lessonsPath", "artifacts/lessons.md")
    current.setdefault("handoffPath", "artifacts/handoff.md")
    write_yaml_json(path, current)
    return current


def write_handoff(bundle: Path, *, status: str, summary: str, evidence: List[str] | None = None) -> None:
    handoff = bundle / "artifacts" / "handoff.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Handoff", "", f"Status: {status}", f"Summary: {summary}"]
    if evidence:
        lines.extend(["", "Evidence:"])
        lines.extend(f"- {item}" for item in evidence)
    lines.append("")
    handoff.write_text("\n".join(lines), encoding="utf-8")


def render_invocation_prompt(invocation: Dict[str, Any]) -> str:
    lines = [
        "You are executing a Pi invocation artifact.",
        "",
        f"Action: {invocation.get('action')}",
        f"Routing task: {invocation.get('routingTask')}",
        f"Bead: {invocation.get('bead')}",
        f"Role: {invocation.get('role')}",
        f"Selected model: {invocation.get('selectedModel') or invocation.get('model')}",
        f"Thinking level: {invocation.get('thinkingLevel') or 'default'}",
        f"Session policy: {invocation.get('sessionPolicy') or 'recorded'}",
        f"Memory policy: {invocation.get('memoryPolicy') or 'auto'}",
        f"Skills: {', '.join(str(item) for item in invocation.get('skills') or []) or 'none'}",
        f"Allowed effects: {', '.join(str(item) for item in invocation.get('allowedEffects') or []) or 'none'}",
        f"Output contract: {invocation.get('outputContract')}",
    ]
    ticket = invocation.get("ticketMetadata") if isinstance(invocation.get("ticketMetadata"), dict) else {}
    if ticket:
        lines.extend(["", "Ticket:"])
        title = ticket.get("title")
        description = ticket.get("description")
        if title:
            lines.append(f"Title: {title}")
        if description:
            lines.extend(["Description:", str(description).strip()])
    lines.extend([
        "",
        "Input refs:",
    ])
    refs = invocation.get("inputRefs") or []
    if refs:
        lines.extend(f"- {ref}" for ref in refs)
    else:
        lines.append("- none")
    criteria = invocation.get("acceptanceCriteria") or []
    if criteria:
        lines.extend(["", "Acceptance criteria:"])
        lines.extend(f"- {item}" for item in criteria)
    todos = invocation.get("ephemeralTodoSeed") or []
    if todos:
        lines.extend(["", "Ephemeral todo seed:"])
        for todo in todos:
            if isinstance(todo, dict):
                lines.append(f"- {todo.get('title') or todo.get('source') or todo}")
            else:
                lines.append(f"- {todo}")
    lines.extend([
        "",
        "Archimedes todos are transient; durable outcomes must be recorded in Beads and run evidence.",
        "Promote important observational-memory findings into Beads or .pi/runs before relying on them for closeout.",
        "Follow project instructions and any referenced skills/roles. Stay within allowed effects.",
        "Return a concise result with evidence and any follow-up work needed.",
        "Include an explicit line-level terminal marker: `OK: <reason/evidence>` or `ERROR: <reason/evidence>`.",
        "Do not emit both terminal markers; missing or ambiguous markers are treated as failure.",
    ])
    return "\n".join(lines) + "\n"


def choose_invocation_model(invocation: Dict[str, Any], override: str | None) -> str:
    if override:
        return override
    model = invocation.get("selectedModel") or invocation.get("model")
    if model:
        return str(model)
    task = str(invocation.get("routingTask") or "cheap-peer")
    models = preferred_models(task)
    if not models:
        die(f"no preferred models for routing task: {task}", 1)
    return models[0]


def invocation_needs_write_tools(invocation: Dict[str, Any]) -> bool:
    action = str(invocation.get("action") or "")
    allowed = {str(item) for item in invocation.get("allowedEffects") or []}
    return action == "implement" or bool(allowed.intersection(WRITE_EFFECTS))


def invocation_needs_command_tools(invocation: Dict[str, Any]) -> bool:
    if invocation_needs_write_tools(invocation):
        return False
    action = str(invocation.get("action") or "")
    if action == "verify":
        return True
    contract = str(invocation.get("outputContract") or "")
    if contract == "verification-review":
        return True
    criteria = "\n".join(str(item) for item in invocation.get("acceptanceCriteria") or [])
    command_markers = ("pytest", "npm test", "go test", "cargo test", "bash", " shell ", " command")
    return any(marker in criteria for marker in command_markers)


def invocation_worker_cwd(invocation: Dict[str, Any]) -> str | None:
    if not invocation_needs_write_tools(invocation):
        return None
    worktree = invocation.get("worktree") if isinstance(invocation.get("worktree"), dict) else {}
    path = worktree.get("path") if isinstance(worktree, dict) else None
    if not isinstance(path, str) or not path:
        die("implementation invocation requires worktree.path", 1)
    resolved = Path(path).expanduser()
    if not resolved.is_dir():
        die(f"implementation invocation worktree does not exist: {resolved}", 1)
    return str(resolved)


def invocation_pi_args(invocation: Dict[str, Any]) -> List[str]:
    if invocation_needs_write_tools(invocation):
        tools = WRITE_WORKER_TOOLS
    elif invocation_needs_command_tools(invocation):
        tools = READ_COMMAND_WORKER_TOOLS
    else:
        tools = READ_ONLY_WORKER_TOOLS
    return ["--no-extensions", "--tools", ",".join(tools)]


def contains_unresolved_tool_call(output: str) -> bool:
    return any(marker in output for marker in UNRESOLVED_TOOL_CALL_MARKERS)


def _terminal_marker(line: str) -> str | None:
    value = line.strip()
    while value.startswith("#"):
        value = value[1:].lstrip()
    for wrapper in ("**", "__"):
        if value.startswith(wrapper) and value.endswith(wrapper) and len(value) > len(wrapper) * 2:
            value = value[len(wrapper):-len(wrapper)].strip()
    upper = value.upper()
    if upper.startswith("VERDICT:"):
        upper = upper.split(":", 1)[1].strip()
    for marker in ("OK", "ERROR"):
        if upper == marker:
            return marker.lower()
        if any(upper.startswith(marker + separator) for separator in (":", " —", " -")):
            return marker.lower()
        if any(upper.endswith(separator + marker) for separator in (" — ", " - ")):
            return marker.lower()
    return None


def terminal_response_outcome(output: str) -> str:
    markers = [marker for line in output.splitlines() if (marker := _terminal_marker(line))]
    if not markers:
        return "missing"
    if len(set(markers)) != 1:
        return "ambiguous"
    return markers[-1]


def invocation_timeout_seconds(invocation: Dict[str, Any]) -> int:
    return WRITE_TIMEOUT_SECONDS if invocation_needs_write_tools(invocation) else READ_ONLY_TIMEOUT_SECONDS


def invoke_run_bundle(
    bundle: Path,
    *,
    model: str | None = None,
    metrics: bool = True,
    metrics_dir: Path | None = None,
    record_session: bool = False,
    session_id: str | None = None,
    session_name: str | None = None,
) -> Dict[str, Any]:
    failures = validate_run_bundle(bundle)
    if failures:
        die("invalid run bundle: " + "; ".join(failures), 1)
    invocation = load_yaml_json(bundle / "invocation.yaml")
    target = choose_invocation_model(invocation, model)
    artifacts_dir = bundle / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    prompt = render_invocation_prompt(invocation)
    prompt_path = artifacts_dir / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    timeout_seconds = invocation_timeout_seconds(invocation)
    timeout_deadline = (datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)).isoformat().replace("+00:00", "Z")
    pi_args = invocation_pi_args(invocation)
    append_live_event(bundle, {"event": "worker_invocation_started", "phase": "running", "model": target, "timeoutSeconds": timeout_seconds})
    write_live_status(
        bundle,
        phase="running",
        currentModel=target,
        currentTool="pi",
        timeoutSeconds=timeout_seconds,
        timeoutDeadlineAt=timeout_deadline,
        piArgs=pi_args,
    )
    code, out, err, record = invoke_one(
        target,
        prompt,
        metrics=metrics,
        task=str(invocation.get("routingTask") or ""),
        risk_category="run-artifact",
        outcome="unknown",
        record_session=record_session,
        session_id=session_id,
        session_name=session_name,
        cwd=invocation_worker_cwd(invocation),
        pi_args=pi_args,
        timeout_seconds=timeout_seconds,
    )
    unresolved_tool_call = code == 0 and contains_unresolved_tool_call(out)
    empty_terminal_response = code == 0 and not out.strip()
    semantic_outcome = terminal_response_outcome(out) if out.strip() else "missing"
    invalid_terminal_response = code == 0 and semantic_outcome != "ok"
    effective_code = 2 if unresolved_tool_call or empty_terminal_response or invalid_terminal_response else code
    safe = safe_target_name(target)
    response_path = artifacts_dir / f"{safe}.response.md"
    stderr_path = artifacts_dir / f"{safe}.stderr.txt"
    response_path.write_text(out, encoding="utf-8")
    stderr_path.write_text(err, encoding="utf-8")
    metrics_ref = None
    artifact_paths = [
        "live/session.jsonl",
        "live/status.json",
        "artifacts/lessons.md",
        "artifacts/handoff.md",
        relative_to_bundle(bundle, prompt_path),
        relative_to_bundle(bundle, response_path),
        relative_to_bundle(bundle, stderr_path),
    ]
    if metrics and record is not None:
        metrics_path = artifacts_dir / f"{safe}.metrics.json"
        write_json(metrics_path, record)
        metrics_ref = relative_to_bundle(bundle, metrics_path)
        artifact_paths.append(metrics_ref)
        central_dir = metrics_dir or default_metrics_dir()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        write_json(central_dir / f"{stamp}-{safe}.metrics.json", record)
    status = "succeeded" if effective_code == 0 else "failed"
    evidence = [f"invoke {target} exited {code}"]
    summary = f"Invoked {target}; exit code {code}."
    if unresolved_tool_call:
        evidence.append("response contained unresolved tool call markup")
        summary = f"Invoked {target}; response contained unresolved tool call markup."
    elif empty_terminal_response:
        evidence.append("worker produced an empty terminal response")
        summary = f"Invoked {target}; worker produced an empty terminal response."
    elif semantic_outcome == "error":
        evidence.append("worker semantic outcome was ERROR")
        summary = f"Invoked {target}; worker produced an explicit ERROR terminal response."
    elif semantic_outcome == "missing":
        evidence.append("worker response lacked an explicit OK or ERROR terminal marker")
        summary = f"Invoked {target}; worker response lacked an explicit terminal marker."
    elif semantic_outcome == "ambiguous":
        evidence.append("worker response contained conflicting OK and ERROR terminal markers")
        summary = f"Invoked {target}; worker response contained ambiguous terminal markers."
    if out.strip():
        evidence.append(f"response written to {relative_to_bundle(bundle, response_path)}")
    if err.strip():
        evidence.append(f"stderr written to {relative_to_bundle(bundle, stderr_path)}")
    evidence.append("live status written to live/status.json")
    evidence.append("handoff written to artifacts/handoff.md")
    if code == 124:
        evidence.append("worker timed out; inspect live/session.jsonl and artifacts/handoff.md for partial progress")
    append_live_event(bundle, {"event": "worker_invocation_completed", "phase": status, "model": target, "exitCode": code, "effectiveExitCode": effective_code, "semanticOutcome": semantic_outcome})
    write_live_status(bundle, phase=status, currentModel=target, currentTool=None, exitCode=code, effectiveExitCode=effective_code, semanticOutcome=semantic_outcome)
    write_handoff(bundle, status=status, summary=summary, evidence=evidence)
    result = update_run_result(
        bundle,
        status=status,
        summary=summary,
        evidence=evidence,
        artifacts=artifact_paths,
        metrics_ref=metrics_ref,
        session_ref=f"pi-session-id:{session_id}" if record_session and session_id else None,
        transcript_ref=f"pi-session-transcript:{session_id}" if record_session and session_id else None,
    )
    return {
        "target": target,
        "exitCode": effective_code,
        "semanticOutcome": semantic_outcome,
        "response": str(response_path),
        "stderr": str(stderr_path),
        "metricsRef": metrics_ref,
        "result": result,
    }


def update_run_result(
    bundle: Path,
    *,
    status: str | None = None,
    summary: str | None = None,
    evidence: List[str] | None = None,
    artifacts: List[str] | None = None,
    follow_ups: List[str] | None = None,
    metrics_ref: str | None = None,
    session_ref: str | None = None,
    transcript_ref: str | None = None,
    memory_summary_ref: str | None = None,
    approval_refs: List[str] | None = None,
    decision_refs: List[str] | None = None,
    health_checks: List[Dict[str, Any]] | None = None,
    closeout_checks: List[Dict[str, Any]] | None = None,
    completed: bool = False,
) -> Dict[str, Any]:
    result_path = bundle / "result.yaml"
    if not result_path.is_file():
        die(f"missing result artifact: {result_path}", 1)
    result = load_yaml_json(result_path)
    preserve_failed_terminal = result.get("status") == "failed" and status is not None and status != "failed"
    if status:
        if status not in VALID_STATUSES:
            die(f"invalid status {status}; expected one of {sorted(VALID_STATUSES)}", 2)
        if not preserve_failed_terminal:
            result["status"] = status
    if summary is not None and not preserve_failed_terminal:
        result["summary"] = summary
    if evidence:
        result.setdefault("evidence", [])
        if not isinstance(result["evidence"], list):
            die(f"result evidence must be a list: {result_path}", 1)
        result["evidence"].extend(evidence)
    if artifacts:
        result.setdefault("artifacts", [])
        if not isinstance(result["artifacts"], list):
            die(f"result artifacts must be a list: {result_path}", 1)
        for artifact in artifacts:
            if artifact not in result["artifacts"]:
                result["artifacts"].append(artifact)
    if follow_ups:
        result.setdefault("followUps", [])
        if not isinstance(result["followUps"], list):
            die(f"result followUps must be a list: {result_path}", 1)
        result["followUps"].extend(follow_ups)
    if metrics_ref is not None:
        result["metricsRef"] = metrics_ref
    if session_ref is not None:
        result["sessionRef"] = session_ref
    if transcript_ref is not None:
        result["transcriptRef"] = transcript_ref
    if memory_summary_ref is not None:
        result["memorySummaryRef"] = memory_summary_ref
    for key, values in (("approvalRefs", approval_refs), ("decisionRefs", decision_refs)):
        if values:
            result.setdefault(key, [])
            if not isinstance(result[key], list):
                die(f"result {key} must be a list: {result_path}", 1)
            for value in values:
                if value not in result[key]:
                    result[key].append(value)
    for key, checks in (("healthChecks", health_checks), ("closeoutChecks", closeout_checks)):
        if checks:
            result.setdefault(key, [])
            if not isinstance(result[key], list):
                die(f"result {key} must be a list: {result_path}", 1)
            result[key].extend(checks)
    if completed or (not preserve_failed_terminal and status in {"succeeded", "failed", "blocked", "superseded"}):
        result["completedAt"] = utc_now()
    write_yaml_json(result_path, result)
    return result


def _optional_object_failures(owner: str, data: Dict[str, Any], keys: List[str]) -> List[str]:
    failures: List[str] = []
    for key in keys:
        if key in data and data[key] is not None and not isinstance(data[key], dict):
            failures.append(f"{owner} {key} must be an object when present")
    return failures


def _optional_list_failures(owner: str, data: Dict[str, Any], keys: List[str]) -> List[str]:
    failures: List[str] = []
    for key in keys:
        if key in data and data[key] is not None and not isinstance(data[key], list):
            failures.append(f"{owner} {key} must be a list when present")
    return failures


def _optional_string_failures(owner: str, data: Dict[str, Any], keys: List[str]) -> List[str]:
    failures: List[str] = []
    for key in keys:
        if key in data and data[key] is not None and not isinstance(data[key], str):
            failures.append(f"{owner} {key} must be a string when present")
    return failures


def validate_run_bundle(bundle: Path, *, followup_checker: Callable[[str], Tuple[bool, str | None]] | None = None) -> List[str]:
    failures: List[str] = []
    invocation_path = bundle / "invocation.yaml"
    result_path = bundle / "result.yaml"
    if not invocation_path.is_file():
        failures.append(f"missing {invocation_path}")
        return failures
    if not result_path.is_file():
        failures.append(f"missing {result_path}")
        return failures
    invocation = load_yaml_json(invocation_path)
    result = load_yaml_json(result_path)
    required_invocation = ["schemaVersion", "id", "action", "routingTask", "allowedEffects", "createdAt"]
    for key in required_invocation:
        if key not in invocation:
            failures.append(f"invocation missing {key}")
    if invocation.get("schemaVersion") != 1:
        failures.append("invocation schemaVersion must be 1")
    if not isinstance(invocation.get("allowedEffects"), list):
        failures.append("invocation allowedEffects must be a list")
    failures.extend(_optional_object_failures("invocation", invocation, ["ticketMetadata", "worktree", "dispatchPolicy", "modelSelection", "provenance"]))
    failures.extend(_optional_list_failures("invocation", invocation, ["ephemeralTodoSeed"]))
    failures.extend(_optional_string_failures("invocation", invocation, ["selectedModel", "thinkingLevel", "sessionPolicy", "memoryPolicy"]))
    if invocation.get("sessionPolicy") is not None and invocation.get("sessionPolicy") not in VALID_SESSION_POLICIES:
        failures.append(f"invocation sessionPolicy must be one of {sorted(VALID_SESSION_POLICIES)}")
    if invocation.get("memoryPolicy") is not None and invocation.get("memoryPolicy") not in VALID_MEMORY_POLICIES:
        failures.append(f"invocation memoryPolicy must be one of {sorted(VALID_MEMORY_POLICIES)}")
    if result.get("schemaVersion") != 1:
        failures.append("result schemaVersion must be 1")
    if result.get("invocationId") != invocation.get("id"):
        failures.append("result invocationId must match invocation id")
    status = result.get("status")
    if status not in VALID_STATUSES:
        failures.append(f"result status must be one of {sorted(VALID_STATUSES)}")
    failures.extend(_optional_string_failures("result", result, ["sessionRef", "transcriptRef", "memorySummaryRef"]))
    failures.extend(_optional_list_failures("result", result, ["approvalRefs", "decisionRefs", "healthChecks", "closeoutChecks"]))
    follow_ups = result.get("followUps")
    if not isinstance(follow_ups, list):
        failures.append("result followUps must be a list")
    elif followup_checker is not None:
        for follow_up in follow_ups:
            ok, detail = followup_checker(str(follow_up))
            if not ok:
                suffix = f": {detail}" if detail else ""
                failures.append(f"result followUp does not resolve to a bead: {follow_up}{suffix}")
    return failures


def parse_check_arg(value: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        if "=" in value:
            name, status = value.split("=", 1)
            return {"name": name, "status": status}
        return {"name": value, "status": "unknown"}
    if not isinstance(parsed, dict):
        die(f"check argument must be a JSON object or name=status: {value}", 2)
    return parsed


def bead_exists_checker(bead_id: str) -> Tuple[bool, str | None]:
    exe = shutil.which("beads") or shutil.which("bd")
    if not exe:
        return False, "beads/bd executable not found"
    proc = subprocess.run([exe, "show", bead_id, "--json"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return False, (proc.stderr or "not found").strip()
    return True, None


def cmd_runs(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt runs", description="Create and validate inspectable invocation/result run artifacts.")
    sub = parser.add_subparsers(dest="command")
    create = sub.add_parser("create", help="create a run bundle with invocation/result artifacts")
    create.add_argument("--action", required=True)
    create.add_argument("--routing-task", required=True)
    create.add_argument("--input-ref", action="append", default=[])
    create.add_argument("--skill", action="append", default=[])
    create.add_argument("--role")
    create.add_argument("--bead")
    create.add_argument("--model")
    create.add_argument("--session-policy", choices=sorted(VALID_SESSION_POLICIES), default="recorded")
    create.add_argument("--memory-policy", choices=sorted(VALID_MEMORY_POLICIES), default="auto")
    create.add_argument("--allowed-effect", action="append", default=[])
    create.add_argument("--acceptance", action="append", default=[])
    create.add_argument("--output-contract")
    create.add_argument("--runs-dir")
    create.add_argument("--id")
    create.add_argument("--json", action="store_true")
    validate = sub.add_parser("validate", help="validate a run bundle")
    validate.add_argument("bundle")
    validate.add_argument("--require-followups-exist", action="store_true", help="fail if result followUps do not resolve to Beads")
    update = sub.add_parser("update", help="update a run bundle result artifact")
    update.add_argument("bundle")
    update.add_argument("--status", choices=sorted(VALID_STATUSES))
    update.add_argument("--summary")
    update.add_argument("--evidence", action="append", default=[])
    update.add_argument("--artifact", action="append", default=[])
    update.add_argument("--follow-up", action="append", default=[])
    update.add_argument("--metrics-ref")
    update.add_argument("--session-ref")
    update.add_argument("--transcript-ref")
    update.add_argument("--memory-summary-ref")
    update.add_argument("--approval-ref", action="append", default=[])
    update.add_argument("--decision-ref", action="append", default=[])
    update.add_argument("--health-check", action="append", default=[], help="JSON object or name=status check")
    update.add_argument("--closeout-check", action="append", default=[], help="JSON object or name=status check")
    update.add_argument("--completed", action="store_true")
    invoke = sub.add_parser("invoke", help="invoke a model from invocation.yaml and write output/metrics into result.yaml")
    invoke.add_argument("bundle")
    invoke.add_argument("--model", help="manual provider/model override for direct run invocation; work/runner dispatch uses policy-selected models")
    invoke.add_argument("--no-metrics", action="store_true")
    invoke.add_argument("--metrics-dir")
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.command == "create":
        bundle = create_run_bundle(
            action=args.action,
            routing_task=args.routing_task,
            input_refs=args.input_ref,
            skills=args.skill,
            role=args.role,
            bead=args.bead,
            model=args.model,
            session_policy=args.session_policy,
            memory_policy=args.memory_policy,
            allowed_effects=args.allowed_effect or None,
            acceptance_criteria=args.acceptance,
            output_contract=args.output_contract,
            runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else None,
            id_value=args.id,
        )
        result = {"schemaVersion": 1, "bundle": str(bundle), "invocation": str(bundle / "invocation.yaml"), "result": str(bundle / "result.yaml")}
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else str(bundle))
        return 0
    if args.command == "validate":
        followup_checker = None
        if args.require_followups_exist:
            followup_checker = bead_exists_checker
        failures = validate_run_bundle(Path(args.bundle).expanduser(), followup_checker=followup_checker)
        print(json.dumps({"schemaVersion": 1, "passed": not failures, "failures": failures}, indent=2, sort_keys=True))
        return 0 if not failures else 1
    if args.command == "update":
        result = update_run_result(
            Path(args.bundle).expanduser(),
            status=args.status,
            summary=args.summary,
            evidence=args.evidence,
            artifacts=args.artifact,
            follow_ups=args.follow_up,
            metrics_ref=args.metrics_ref,
            session_ref=args.session_ref,
            transcript_ref=args.transcript_ref,
            memory_summary_ref=args.memory_summary_ref,
            approval_refs=args.approval_ref,
            decision_refs=args.decision_ref,
            health_checks=[parse_check_arg(item) for item in args.health_check],
            closeout_checks=[parse_check_arg(item) for item in args.closeout_check],
            completed=args.completed,
        )
        print(json.dumps({"schemaVersion": 1, "result": result}, indent=2, sort_keys=True))
        failures = validate_run_bundle(Path(args.bundle).expanduser())
        return 0 if not failures else 1
    if args.command == "invoke":
        result = invoke_run_bundle(
            Path(args.bundle).expanduser(),
            model=args.model,
            metrics=not args.no_metrics,
            metrics_dir=Path(args.metrics_dir).expanduser() if args.metrics_dir else None,
        )
        print(json.dumps({"schemaVersion": 1, **result}, indent=2, sort_keys=True))
        return int(result.get("exitCode") or 0)
    parser.print_help(sys.stderr)
    return 2
