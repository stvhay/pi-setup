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
from .runs import create_run_bundle, invoke_run_bundle, load_yaml_json, update_run_result


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


def dispatch_plan(bead: Dict[str, Any], action_id: str | None, target: List[str]) -> Dict[str, Any]:
    action = action_id or infer_action(bead)
    _path, meta, _body = load_action(action)
    return {
        "bead": bead.get("id"),
        "title": bead.get("title"),
        "status": bead.get("status"),
        "action": meta.get("id") or action,
        "routingTask": meta.get("routingTask"),
        "skills": meta.get("skills") or [],
        "role": meta.get("defaultRole"),
        "allowedEffects": meta.get("allowedEffects") or [],
        "inputRefs": target,
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


def start_work(bead: Dict[str, Any], *, action_id: str | None, target: List[str], claim: bool, runs_dir: Path | None, id_value: str | None) -> Dict[str, Any]:
    dispatch = dispatch_plan(bead, action_id, target)
    bundle = create_run_bundle(
        action=str(dispatch["action"]),
        routing_task=str(dispatch["routingTask"]),
        input_refs=[str(item) for item in dispatch["inputRefs"]],
        skills=[str(item) for item in dispatch["skills"]],
        role=str(dispatch["role"]) if dispatch["role"] else None,
        bead=str(dispatch["bead"]) if dispatch["bead"] else None,
        allowed_effects=[str(item) for item in dispatch["allowedEffects"]],
        acceptance_criteria=normalize_acceptance_criteria(bead.get("acceptance_criteria") or bead.get("acceptanceCriteria")),
        output_contract=str(dispatch["outputContract"]),
        runs_dir=runs_dir,
        id_value=id_value,
    )
    bead_update: Dict[str, Any] | None = None
    if claim and dispatch.get("bead"):
        code, data, err = run_beads_json(["update", str(dispatch["bead"]), "--claim"])
        if code != 0:
            return {"bundle": str(bundle), "dispatch": dispatch, "beadUpdateError": err, "beadUpdateCode": code}
        bead_update = {"code": code, "result": data}
    return {"bundle": str(bundle), "invocation": str(bundle / "invocation.yaml"), "result": str(bundle / "result.yaml"), "dispatch": dispatch, "beadUpdate": bead_update}


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
) -> Dict[str, Any]:
    started = start_work(
        bead,
        action_id=action_id,
        target=target,
        claim=claim,
        runs_dir=runs_dir,
        id_value=id_value,
    )
    if started.get("beadUpdateError"):
        return {"started": started}
    bundle = Path(str(started["bundle"]))
    invoked = invoke_run_bundle(bundle, model=model, metrics_dir=metrics_dir)
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


def close_readiness_failures(result: Dict[str, Any], *, followup_checker=bead_followup_checker) -> List[str]:
    failures: List[str] = []
    if result.get("status") == "succeeded" and not result.get("evidence"):
        failures.append("succeeded bead closure requires at least one evidence entry")
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
    run.add_argument("--model")
    run.add_argument("--claim", action="store_true", help="mark the bead in_progress before invoking")
    run.add_argument("--close-bead", action="store_true", help="close bead only if invocation succeeds")
    run.add_argument("--runs-dir")
    run.add_argument("--metrics-dir")
    run.add_argument("--id")
    run.add_argument("--dry-run", action="store_true", help="show dispatch plan without invoking")
    audit = sub.add_parser("audit", help="audit Beads queue health against unresolved required-work signals")
    audit.add_argument("--json", action="store_true")
    audit.add_argument("--scan-root", action="append", default=[], help="file or directory to scan; defaults to docs, README, AGENTS, and .pi/runs")
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
        return 1 if result.get("beadUpdateError") else 0
    if args.command == "run":
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
        invoked = result.get("invoked") if isinstance(result, dict) else None
        return int(invoked.get("exitCode") or 0) if isinstance(invoked, dict) else 1
    if args.command == "audit":
        roots = [Path(item).expanduser() for item in args.scan_root] if args.scan_root else None
        report = work_audit_report(scan_roots=roots)
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
