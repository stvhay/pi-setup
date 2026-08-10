from __future__ import annotations

import shutil
from typing import Callable, List

from .core import die


def cmd_graphify(
    argv: List[str],
    *,
    runner: Callable[[List[str]], int],
    which: Callable[[str], str | None] = shutil.which,
) -> int:
    """Run Graphify through its installed binary or uv tool fallback."""
    graphify = which("graphify")
    if graphify:
        return runner([graphify, *argv])
    if which("uv"):
        return runner(["uv", "tool", "run", "--from", "graphifyy", "graphify", *argv])
    die("Graphify is unavailable. Install `graphifyy` or use an environment with `uv`.", 1)
