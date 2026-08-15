from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

ROOT = Path(__file__).resolve().parent.parent.parent
BIN = ROOT / "bin"
TASKS = ROOT / "tasks"
EVALS = ROOT / "evals"
ACTIONS = ROOT / "actions"

VALID_OUTCOMES = {"unknown", "accepted", "rejected", "verified-pass", "verified-fail", "escalated"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def die(message: str, code: int = 2) -> None:
    print(f"agnt: {message}", file=sys.stderr)
    raise SystemExit(code)


def require_beads_success(code: int, data: Any, err: str, action: str) -> Any:
    if code != 0:
        die(f"bd {action} failed: {err}", code or 1)
    return data


def run(argv: List[str]) -> int:
    return subprocess.call(argv)


def split_target(target: str) -> tuple[str, str]:
    if "/" not in target:
        die(f"model must be provider/model: {target}")
    provider, model = target.split("/", 1)
    if not provider or not model:
        die(f"model must be provider/model: {target}")
    return provider, model
