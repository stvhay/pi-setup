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

from .core import die
from .invoke import invoke_one

def pong_prompt(path: Path) -> str:
    return f"""You are running a fresh-context implementation benchmark. Implement a basic terminal Pong game as a single Python file at exactly:

{path}

Requirements:
- Use only Python standard library. Prefer curses for TUI.
- Colored display when terminal supports color, graceful monochrome fallback.
- Controls: Up/Down arrow keys and w/s fallback move the left paddle; q quits.
- Right paddle is simple AI.
- Include non-interactive verification modes:
  - --self-test: run logic assertions and exit 0 on success.
  - --headless --demo-frames N: simulate N frames without curses and exit 0.
- Handle terminals that are too small with a readable message.
- Do not modify files outside {path.parent}.
- After writing the file, run verification and return concise results.
"""


def pong_fix_prompt(path: Path, failures: List[Dict[str, Any]]) -> str:
    return f"""Debug and fix the Pong implementation at exactly:

{path}

Current verification failures:
{json.dumps(failures, indent=2)}

Constraints:
- Modify only {path}.
- Keep it single-file and stdlib-only.
- Preserve arrow key and w/s controls, q quit, color curses TUI, --self-test, and --headless --demo-frames N.
- Find root cause before changing code.

After fixing, run py_compile, --self-test, and --headless --demo-frames 20. Return concise results.
"""


def verify_pong(path: Path) -> List[Dict[str, Any]]:
    return [
        run_check(["python3", "-m", "py_compile", str(path)]),
        run_check(["python3", str(path), "--self-test"]),
        run_check(["python3", str(path), "--headless", "--demo-frames", "20"]),
    ]


def cmd_benchmark(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt benchmark", description="Run reproducible agent benchmarks.")
    sub = parser.add_subparsers(dest="benchmark")
    sub.add_parser("pong")
    if not argv:
        parser.print_help()
        return 0
    benchmark, rest = argv[0], argv[1:]
    if benchmark in {"-h", "--help"}:
        parser.print_help()
        return 0
    if benchmark != "pong":
        parser.print_help(sys.stderr)
        return 2
    p = argparse.ArgumentParser(prog="agnt benchmark pong")
    p.add_argument("--model", required=True, help="provider/model to benchmark")
    p.add_argument("--max-fix-cycles", type=int, default=1)
    p.add_argument("--work-dir", help="directory for benchmark artifact")
    p.add_argument("--metrics-dir")
    args = p.parse_args(rest)
    target = args.model
    work_dir = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix="agnt-pong-benchmark-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    pong_path = work_dir / "pong.py"
    metrics_dir = Path(args.metrics_dir) if args.metrics_dir else default_metrics_dir()
    started_at = utc_now()
    started = time.monotonic()
    rework = 0
    code, out, err, record = invoke_one(target, pong_prompt(pong_path), metrics=True, task="implementation")
    (work_dir / "implementation.md").write_text(out, encoding="utf-8")
    if err:
        (work_dir / "implementation.err").write_text(err, encoding="utf-8")
    if record:
        write_metric_record(metrics_dir, safe_target_name(target), record)
    checks = verify_pong(pong_path) if pong_path.exists() else [{"command": ["test", "-f", str(pong_path)], "exitCode": 1, "passed": False, "elapsedMs": 0, "stdoutTail": "", "stderrTail": "missing pong.py"}]
    while any(not check["passed"] for check in checks) and rework < args.max_fix_cycles:
        rework += 1
        code, out, err, record = invoke_one(target, pong_fix_prompt(pong_path, checks), metrics=True, task="implementation")
        (work_dir / f"fix-{rework}.md").write_text(out, encoding="utf-8")
        if err:
            (work_dir / f"fix-{rework}.err").write_text(err, encoding="utf-8")
        if record:
            write_metric_record(metrics_dir, safe_target_name(target), record)
        checks = verify_pong(pong_path) if pong_path.exists() else checks
    status = "pass" if all(check["passed"] for check in checks) else "fail"
    loc = 0
    if pong_path.exists():
        loc = len(pong_path.read_text(encoding="utf-8").splitlines())
    outcome = {
        "schemaVersion": 1,
        "kind": "benchmark",
        "benchmark": "pong-implementation",
        "task": "benchmark-outcome",
        "status": status,
        "startedAt": started_at,
        "endedAt": utc_now(),
        "elapsedMs": 0,
        "benchmarkElapsedMs": int((time.monotonic() - started) * 1000),
        "provider": "benchmark",
        "model": "pong-implementation",
        "target": "benchmark/pong-implementation",
        "benchmarkedTarget": target,
        "exitCode": 0 if status == "pass" else 1,
        "usageSource": "benchmark-outcome",
        "usage": None,
        "responseChars": 0,
        "stderrChars": 0,
        "reworkCycles": rework,
        "verification": checks,
        "artifact": str(pong_path),
        "codeQuality": {"loc": loc, "stdlibOnly": True},
    }
    out_path = write_metric_record(metrics_dir, "benchmark-pong", outcome)
    print(json.dumps({"status": status, "workDir": str(work_dir), "artifact": str(pong_path), "reworkCycles": rework, "verification": checks, "metrics": str(out_path)}, indent=2))
    return 0 if status == "pass" else 1
