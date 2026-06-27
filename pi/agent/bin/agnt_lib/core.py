from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent.parent
BIN = ROOT / "bin"
TASKS = ROOT / "tasks"
EVALS = ROOT / "evals"
PROMPT_PATTERNS = ROOT / "prompt-patterns"
ACTIONS = ROOT / "actions"

VALID_OUTCOMES = {"unknown", "accepted", "rejected", "verified-pass", "verified-fail", "escalated"}


def die(message: str, code: int = 2) -> None:
    print(f"agnt: {message}", file=sys.stderr)
    raise SystemExit(code)


def run(argv: List[str]) -> int:
    return subprocess.call(argv)


def capture(argv: List[str]) -> str:
    return subprocess.check_output(argv, text=True)


def split_target(target: str) -> tuple[str, str]:
    if "/" not in target:
        die(f"model must be provider/model: {target}")
    provider, model = target.split("/", 1)
    if not provider or not model:
        die(f"model must be provider/model: {target}")
    return provider, model
