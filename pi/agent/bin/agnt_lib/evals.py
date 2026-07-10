from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import _agnt_common as common

from .core import BIN, EVALS, ROOT, die
from .invoke import invoke_one, safe_target_name
from .metrics import git_root, write_json, write_metric_record
from .routing import cmd_route
from .tasks import preferred_models

def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "item"


def eval_files() -> List[Path]:
    return sorted(EVALS.glob("*/eval.json")) if EVALS.is_dir() else []


def load_eval(path_or_id: str) -> Tuple[Path, Dict[str, Any]]:
    candidate = Path(path_or_id).expanduser()
    if candidate.is_dir():
        candidate = candidate / "eval.json"
    elif not candidate.is_file():
        candidate = EVALS / path_or_id / "eval.json"
    if not candidate.is_file():
        die(f"eval not found: {path_or_id}", 1)
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"invalid eval JSON {candidate}: {exc}", 1)
    if not isinstance(data, dict):
        die(f"eval must be a JSON object: {candidate}", 1)
    return candidate, data


def split_models(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(",", " ").split() if item.strip()]


def default_eval_output_dir(eval_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return git_root() / ".pi" / "eval-runs" / f"{stamp}-{eval_id}"


def assert_eval_fields(case_name: str, result: Dict[str, Any], assertions: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    for key, expected in assertions.items():
        actual = result.get(key)
        if expected is True:
            if not actual:
                failures.append(f"{case_name}: expected truthy {key}")
        elif expected is False:
            if actual:
                failures.append(f"{case_name}: expected falsey {key}")
        elif actual != expected:
            failures.append(f"{case_name}: expected {key}={expected!r}, got {actual!r}")
    return failures


def run_route_eval(eval_path: Path, spec: Dict[str, Any], out_dir: Path, dry_run: bool) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    failures: List[str] = []
    for case in spec.get("cases") or []:
        if not isinstance(case, dict):
            failures.append("route case must be an object")
            continue
        name = str(case.get("name") or f"case-{len(results) + 1}")
        args = [str(item) for item in (case.get("args") or [])]
        case_result: Dict[str, Any] = {"name": name, "args": args, "dryRun": dry_run}
        if dry_run:
            case_result["plannedCommand"] = ["agnt", "route", *args]
        else:
            proc = subprocess.run([sys.executable, str(BIN / "agnt"), "route", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            case_result["exitCode"] = proc.returncode
            case_result["stderr"] = proc.stderr[-2000:]
            try:
                routed = json.loads(proc.stdout)
            except json.JSONDecodeError:
                routed = {"rawStdout": proc.stdout[-2000:]}
                failures.append(f"{name}: route output was not JSON")
            case_result["result"] = routed
            assertions = dict(case.get("assert")) if isinstance(case.get("assert"), dict) else {}
            expected_exit = assertions.pop("exitCode", 0)
            if proc.returncode != expected_exit:
                failures.append(f"{name}: expected route exit {expected_exit}, got {proc.returncode}")
            failures.extend(assert_eval_fields(name, routed, assertions))
        results.append(case_result)
    return {"evalPath": str(eval_path), "kind": "route", "results": results, "failures": failures}


def run_instructions_eval(eval_path: Path, spec: Dict[str, Any], out_dir: Path, dry_run: bool) -> Dict[str, Any]:
    root_value = spec.get("root")
    root = ROOT / str(root_value) if root_value else None
    results: List[Dict[str, Any]] = []
    failures: List[str] = []
    for case in spec.get("cases") or []:
        if not isinstance(case, dict):
            failures.append("instructions case must be an object")
            continue
        name = str(case.get("name") or f"case-{len(results) + 1}")
        args = [str(item) for item in (case.get("args") or [])]
        case_result: Dict[str, Any] = {"name": name, "args": args, "dryRun": dry_run}
        command = [sys.executable, str(BIN / "agnt"), "instructions", *([str(root)] if root else []), *args]
        if dry_run:
            case_result["plannedCommand"] = ["agnt", "instructions", *([str(root)] if root else []), *args]
        else:
            proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out_file = out_dir / f"{slugify(name)}.md"
            err_file = out_dir / f"{slugify(name)}.err"
            out_file.write_text(proc.stdout, encoding="utf-8")
            err_file.write_text(proc.stderr, encoding="utf-8")
            case_result.update({"exitCode": proc.returncode, "outputFile": str(out_file), "stderrFile": str(err_file), "responseChars": len(proc.stdout), "stderrChars": len(proc.stderr)})
            if proc.returncode != 0:
                failures.append(f"{name}: instructions exited {proc.returncode}")
            for needle in case.get("contains") or []:
                if str(needle) not in proc.stdout:
                    failures.append(f"{name}: missing expected text {needle!r}")
        results.append(case_result)
    return {"evalPath": str(eval_path), "kind": "instructions", "results": results, "failures": failures}


def run_invoke_eval(eval_path: Path, spec: Dict[str, Any], out_dir: Path, dry_run: bool, models: List[str]) -> Dict[str, Any]:
    eval_dir = eval_path.parent
    prompt_file = eval_dir / str(spec.get("prompt") or "prompt.md")
    if not prompt_file.is_file():
        return {"evalPath": str(eval_path), "kind": "invoke", "results": [], "failures": [f"missing prompt file: {prompt_file}"]}
    prompt = prompt_file.read_text(encoding="utf-8")
    task = str(spec.get("task") or "cheap-peer")
    targets = models or [str(item) for item in (spec.get("defaultModels") or [])]
    if not targets:
        targets = preferred_models(task)
    assertions = spec.get("assert") if isinstance(spec.get("assert"), dict) else {}
    results: List[Dict[str, Any]] = []
    failures: List[str] = []
    metrics_dir = out_dir / "metrics"
    for target in targets:
        safe = safe_target_name(target)
        case_result: Dict[str, Any] = {"target": target, "task": task, "dryRun": dry_run}
        if dry_run:
            case_result["plannedCommand"] = ["agnt", "invoke", "--task", task, "--metrics-dir", str(metrics_dir), target, str(prompt_file)]
        else:
            code, out, err, record = invoke_one(target, prompt, metrics=True, task=task, risk_category="eval", outcome="unknown")
            (out_dir / f"{safe}.md").write_text(out, encoding="utf-8")
            (out_dir / f"{safe}.err").write_text(err, encoding="utf-8")
            if record is not None:
                write_metric_record(metrics_dir, safe, record)
            case_result.update({"exitCode": code, "outputFile": str(out_dir / f"{safe}.md"), "stderrFile": str(out_dir / f"{safe}.err"), "responseChars": len(out), "stderrChars": len(err)})
            if code != 0:
                failures.append(f"{target}: invoke exited {code}")
            if assertions.get("nonEmptyOutput") and not out.strip():
                failures.append(f"{target}: expected non-empty output")
        results.append(case_result)
    return {"evalPath": str(eval_path), "kind": "invoke", "results": results, "failures": failures}


def cmd_eval(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt eval", description="Run filesystem-defined agnt evals.")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("list", help="list evals")
    run_parser = sub.add_parser("run", help="run one eval")
    run_parser.add_argument("eval_id", help="eval id or path")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--models", help="space- or comma-separated provider/model list for invoke evals")
    run_parser.add_argument("-o", "--output", help="output directory")
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.action == "list":
        rows = []
        for path in eval_files():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            rows.append({"id": data.get("id") or path.parent.name, "kind": data.get("kind"), "summary": data.get("summary"), "path": str(path)})
        print(json.dumps({"schemaVersion": 1, "evals": rows}, indent=2, sort_keys=True))
        return 0
    if args.action == "run":
        eval_path, spec = load_eval(args.eval_id)
        eval_id = str(spec.get("id") or eval_path.parent.name)
        out_dir = Path(args.output) if args.output else default_eval_output_dir(eval_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        kind = str(spec.get("kind") or "")
        if kind == "route":
            result = run_route_eval(eval_path, spec, out_dir, args.dry_run)
        elif kind == "instructions":
            result = run_instructions_eval(eval_path, spec, out_dir, args.dry_run)
        elif kind == "invoke":
            result = run_invoke_eval(eval_path, spec, out_dir, args.dry_run, split_models(args.models))
        else:
            result = {"evalPath": str(eval_path), "kind": kind, "results": [], "failures": [f"unsupported eval kind: {kind}"]}
        result.update({"schemaVersion": 1, "id": eval_id, "summary": spec.get("summary"), "dryRun": args.dry_run, "outputDir": str(out_dir), "passed": not result.get("failures")})
        write_json(out_dir / "result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 1
    parser.print_help(sys.stderr)
    return 2
