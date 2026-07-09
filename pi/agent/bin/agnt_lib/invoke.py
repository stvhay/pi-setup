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

from .core import VALID_OUTCOMES, die, split_target
from .doctor import doctor_report
from .tasks import list_models, preferred_models
from .metrics import add_usage, default_metrics_dir, empty_usage, metrics_record, utc_now, write_json

def read_prompt(parts: List[str]) -> str:
    if parts:
        chunks: List[str] = []
        for part in parts:
            path_text = part[1:] if part.startswith("@") else part
            path = Path(path_text).expanduser()
            if path.is_file() and (part.startswith("@") or len(parts) == 1 or part == parts[-1]):
                chunks.append(path.read_text(encoding="utf-8"))
            else:
                chunks.append(part)
        return "\n\n".join(chunk for chunk in chunks if chunk)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""
def assistant_text(message: Dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: List[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            chunks.append(str(block.get("text") or ""))
    return "".join(chunks)


def parse_pi_json_output(stdout: str) -> Tuple[str, Dict[str, Any] | None, str]:
    texts: List[str] = []
    message_end_usages: List[Dict[str, Any]] = []
    turn_end_usages: List[Dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") not in {"message_end", "turn_end"}:
            continue
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        usage = message.get("usage")
        if event.get("type") == "message_end":
            text = assistant_text(message)
            if text:
                texts.append(text)
            if isinstance(usage, dict):
                message_end_usages.append(usage)
        elif isinstance(usage, dict):
            turn_end_usages.append(usage)

    usages = message_end_usages or turn_end_usages
    if not usages:
        return "".join(texts), None, "unavailable"
    usage_total = empty_usage()
    for usage in usages:
        add_usage(usage_total, usage)
    return "".join(texts), usage_total, ("message_end" if message_end_usages else "turn_end")


def safe_target_name(target: str) -> str:
    return target.replace("/", "__").replace(":", "_")
def invoke_one(
    target: str,
    prompt: str,
    *,
    metrics: bool = True,
    task: str | None = None,
    risk_category: str | None = None,
    thinking_level: str | None = None,
    outcome: str = "unknown",
    human_override: bool = False,
    fallback_used: bool = False,
    record_session: bool = False,
    session_id: str | None = None,
    session_name: str | None = None,
) -> Tuple[int, str, str, Dict[str, Any] | None]:
    provider, model = split_target(target)
    started_at = utc_now()
    started = time.monotonic()
    session_args: List[str] = []
    if record_session:
        if session_id:
            session_args.extend(["--session-id", session_id])
        if session_name:
            session_args.extend(["--name", session_name])
    else:
        session_args.append("--no-session")
    if metrics:
        proc = subprocess.run(
            ["pi", "--mode", "json", *session_args, "--provider", provider, "--model", model, prompt],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, usage, usage_source = parse_pi_json_output(proc.stdout)
    else:
        proc = subprocess.run(
            ["pi", "--print", *session_args, "--provider", provider, "--model", model, prompt],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, usage, usage_source = proc.stdout, None, "not_requested"
    ended_at = utc_now()
    elapsed_ms = int((time.monotonic() - started) * 1000)
    record = None
    if metrics:
        record = metrics_record(
            target=target,
            task=task,
            started_at=started_at,
            ended_at=ended_at,
            elapsed_ms=elapsed_ms,
            code=proc.returncode,
            prompt=prompt,
            out=out,
            err=proc.stderr,
            usage=usage,
            usage_source=usage_source,
            risk_category=risk_category,
            thinking_level=thinking_level,
            outcome=outcome,
            human_override=human_override,
            fallback_used=fallback_used,
        )
    return proc.returncode, out, proc.stderr, record


def cmd_invoke(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt invoke", description="Invoke Pi peer models.")
    parser.add_argument("--task", help="task routing hint")
    parser.add_argument("--list", nargs="?", const="", metavar="TASK", help="list models for TASK or all tasks")
    parser.add_argument("--fanout", action="store_true", help="run one or more models in parallel")
    parser.add_argument("--no-metrics", action="store_true", help="disable default wall-clock, token, and cost metrics capture")
    parser.add_argument("--metrics", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--metrics-dir", help="raw metrics output directory")
    parser.add_argument("--risk-category", help="risk/category label to store in metrics")
    parser.add_argument("--thinking-level", help="thinking level label to store in metrics")
    parser.add_argument("--outcome", choices=sorted(VALID_OUTCOMES), default="unknown", help="initial outcome label for metrics")
    parser.add_argument("--human-override", action="store_true", help="mark metrics as involving a human override")
    parser.add_argument("--fallback-used", action="store_true", help="mark metrics as involving a fallback")
    parser.add_argument("--preflight", action="store_true", help="run agnt doctor invocation preflight before calling models")
    parser.add_argument("-o", "--output", help="output directory for fanout")
    parser.add_argument("items", nargs="*", help="provider/model plus prompt/file, or fanout pairs")
    args = parser.parse_args(argv)

    if args.list is not None:
        return list_models(args.list or args.task)
    if not args.items:
        parser.print_help(sys.stderr)
        return 2

    use_metrics = not args.no_metrics

    if args.preflight:
        report = doctor_report(check_names=["command.pi", "provider.env", "catalog.parse"])
        if report.get("failures"):
            print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
            return 1
        if report.get("warnings"):
            print("agnt invoke preflight warnings:", file=sys.stderr)
            for warning in report.get("warnings") or []:
                print(f"- {warning.get('id')}: {warning.get('message')}", file=sys.stderr)

    if not args.fanout:
        target = args.items[0]
        prompt = read_prompt(args.items[1:])
        code, out, err, record = invoke_one(
            target,
            prompt,
            metrics=use_metrics,
            task=args.task,
            risk_category=args.risk_category,
            thinking_level=args.thinking_level,
            outcome=args.outcome,
            human_override=args.human_override,
            fallback_used=args.fallback_used,
        )
        if use_metrics and record is not None:
            metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            write_json(metrics_dir / f"{stamp}-{safe_target_name(target)}.metrics.json", record)
        if err:
            print(err, file=sys.stderr, end="")
        print(out, end="")
        return code

    out_dir = Path(args.output or f".pi/peer-runs/{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs: List[Tuple[str, str]] = []
    items = args.items
    if "/" not in items[0]:
        prompt = read_prompt(items)
        pairs = [(target, prompt) for target in preferred_models(args.task)]
    elif len(items) == 1 or (len(items) > 1 and not Path(items[1].removeprefix("@")).expanduser().is_file() and "/" not in items[1]):
        prompt = read_prompt(items[1:]) if len(items) > 1 else read_prompt([])
        pairs = [(items[0], prompt)]
    else:
        if len(items) % 2 != 0:
            die("fanout multi-model form requires provider/model filename pairs")
        for i in range(0, len(items), 2):
            target = items[i]
            path = Path(items[i + 1].removeprefix("@")).expanduser()
            if not path.is_file():
                die(f"prompt file not found: {path}", 1)
            pairs.append((target, path.read_text(encoding="utf-8")))

    (out_dir / "targets.txt").write_text("\n".join(target for target, _ in pairs) + "\n", encoding="utf-8")
    status = 0
    records: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(pairs)) as pool:
        futures = {
            pool.submit(
                invoke_one,
                target,
                prompt,
                metrics=use_metrics,
                task=args.task,
                risk_category=args.risk_category,
                thinking_level=args.thinking_level,
                outcome=args.outcome,
                human_override=args.human_override,
                fallback_used=args.fallback_used,
            ): target
            for target, prompt in pairs
        }
        for fut in as_completed(futures):
            target = futures[fut]
            safe = safe_target_name(target)
            code, out, err, record = fut.result()
            (out_dir / f"{safe}.md").write_text(out, encoding="utf-8")
            (out_dir / f"{safe}.err").write_text(err, encoding="utf-8")
            if use_metrics and record is not None:
                records.append(record)
                write_json(out_dir / f"{safe}.metrics.json", record)
                metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
                write_json(metrics_dir / f"{stamp}-{safe}.metrics.json", record)
            if code != 0:
                status = code
    if use_metrics:
        summary: Dict[str, Any] = {
            "schemaVersion": 1,
            "targets": [record["target"] for record in records],
            "invocations": records,
            "totalElapsedMs": sum(int(record.get("elapsedMs") or 0) for record in records),
            "totalUsage": empty_usage(),
        }
        usage_seen = False
        for record in records:
            usage = record.get("usage")
            if isinstance(usage, dict):
                add_usage(summary["totalUsage"], usage)
                usage_seen = True
        if not usage_seen:
            summary["totalUsage"] = None
        write_json(out_dir / "metrics.summary.json", summary)
    print(f"peer outputs: {out_dir}")
    return status
