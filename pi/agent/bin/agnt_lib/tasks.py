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

from .core import TASKS, die

def parse_frontmatter(path: Path) -> Tuple[Dict[str, object], str]:
    return common.parse_frontmatter_file(path)


def task_files() -> List[Path]:
    if not TASKS.is_dir():
        return []
    return sorted(TASKS.glob("*.md"))


def task_rows() -> List[Tuple[str, Dict[str, object], str]]:
    rows = []
    for path in task_files():
        meta, body = parse_frontmatter(path)
        tid = str(meta.get("id", path.stem))
        rows.append((tid, meta, body))
    return rows


def as_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def cmd_tasks(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt tasks", description="List task routing hints.")
    parser.add_argument("--models", action="store_true", help="include preferred and qualified models")
    args = parser.parse_args(argv)
    rows = task_rows()
    if not rows:
        print("No tasks found.")
        return 0
    if args.models:
        print("| Task | Summary | Preferred | Qualified |")
        print("|---|---|---|---|")
        for tid, meta, _body in rows:
            summary = str(meta.get("summary", "")).replace("|", "\\|")
            preferred = ", ".join(as_list(meta.get("preferred"))).replace("|", "\\|")
            qualified = ", ".join(as_list(meta.get("qualified"))).replace("|", "\\|")
            print(f"| {tid} | {summary} | {preferred} | {qualified} |")
    else:
        print("| Task | Summary |")
        print("|---|---|")
        for tid, meta, _body in rows:
            summary = str(meta.get("summary", "")).replace("|", "\\|")
            print(f"| {tid} | {summary} |")
    return 0
def preferred_models(task: str | None) -> List[str]:
    selected = task or "review"
    for tid, meta, _body in task_rows():
        if tid == selected:
            models = as_list(meta.get("preferred"))
            if models:
                return models
    return ["olla-cloud/gpt-4.1-mini", "olla-cloud/gemini-flash"]


def list_models(task: str | None) -> int:
    rows = task_rows()
    if task:
        rows = [row for row in rows if row[0] == task]
        if not rows:
            die(f"unknown task: {task}", 1)
    for tid, meta, _body in rows:
        print(f"# {tid}")
        for label in ("preferred", "qualified", "avoid"):
            models = as_list(meta.get(label))
            if models:
                print(f"{label}:")
                for model in models:
                    print(f"- {model}")
        print()
    return 0


def task_meta(task: str) -> Tuple[Dict[str, object], str]:
    for tid, meta, body in task_rows():
        if tid == task:
            return meta, body
    die(f"unknown task: {task}", 1)
