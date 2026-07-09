from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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


def create_run_bundle(
    *,
    action: str,
    routing_task: str,
    input_refs: List[str] | None = None,
    skills: List[str] | None = None,
    role: str | None = None,
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
    runs_dir: Path | None = None,
    id_value: str | None = None,
) -> Path:
    rid = id_value or run_id(action, bead)
    bundle = (runs_dir or default_runs_dir()) / rid
    artifacts = bundle / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    invocation = {
        "schemaVersion": 1,
        "id": rid,
        "bead": bead,
        "action": action,
        "routingTask": routing_task,
        "inputRefs": input_refs or [],
        "skills": skills or [],
        "role": role,
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
        "createdAt": utc_now(),
    }
    result = {
        "schemaVersion": 1,
        "invocationId": rid,
        "status": "needs-human",
        "summary": "Invocation artifact created; worker has not run yet.",
        "evidence": [],
        "artifacts": [str(artifacts.relative_to(bundle))],
        "followUps": [],
        "metricsRef": None,
        "sessionRef": None,
        "transcriptRef": None,
        "memorySummaryRef": None,
        "approvalRefs": [],
        "decisionRefs": [],
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
        "",
        "Input refs:",
    ]
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


def invoke_run_bundle(
    bundle: Path,
    *,
    model: str | None = None,
    metrics: bool = True,
    metrics_dir: Path | None = None,
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
    code, out, err, record = invoke_one(
        target,
        prompt,
        metrics=metrics,
        task=str(invocation.get("routingTask") or ""),
        risk_category="run-artifact",
        outcome="unknown",
    )
    safe = safe_target_name(target)
    response_path = artifacts_dir / f"{safe}.response.md"
    stderr_path = artifacts_dir / f"{safe}.stderr.txt"
    response_path.write_text(out, encoding="utf-8")
    stderr_path.write_text(err, encoding="utf-8")
    metrics_ref = None
    artifact_paths = [
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
    status = "succeeded" if code == 0 else "failed"
    evidence = [f"invoke {target} exited {code}"]
    if out.strip():
        evidence.append(f"response written to {relative_to_bundle(bundle, response_path)}")
    if err.strip():
        evidence.append(f"stderr written to {relative_to_bundle(bundle, stderr_path)}")
    result = update_run_result(
        bundle,
        status=status,
        summary=f"Invoked {target}; exit code {code}.",
        evidence=evidence,
        artifacts=artifact_paths,
        metrics_ref=metrics_ref,
    )
    return {
        "target": target,
        "exitCode": code,
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
    if status:
        if status not in VALID_STATUSES:
            die(f"invalid status {status}; expected one of {sorted(VALID_STATUSES)}", 2)
        result["status"] = status
    if summary is not None:
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
    if completed or (status in {"succeeded", "failed", "blocked", "superseded"}):
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
    failures.extend(_optional_object_failures("invocation", invocation, ["ticketMetadata", "worktree", "dispatchPolicy", "modelSelection"]))
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
