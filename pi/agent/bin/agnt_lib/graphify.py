from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List

from .core import die

HOOK_NAMES = ["post-commit", "post-merge", "post-checkout"]
HOOK_BEGIN = "# BEGIN agnt graphify hook"
HOOK_END = "# END agnt graphify hook"
HOOK_BLOCK = f"""{HOOK_BEGIN}
(
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$repo_root" || exit 0
  command -v agnt >/dev/null 2>&1 || exit 0
  agnt graphify --no-hook-check update . >/tmp/agnt-graphify-update.log 2>&1 || true
) &
{HOOK_END}
"""

Runner = Callable[[List[str]], int]
Which = Callable[[str], str | None]


def git_root(repo: Path | None = None) -> Path | None:
    cwd = repo or Path.cwd()
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip())


def hooks_dir(repo_root: Path) -> Path:
    proc = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    configured = proc.stdout.strip() if proc.returncode == 0 else ""
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else repo_root / path
    return repo_root / ".git" / "hooks"


def hook_installed(path: Path) -> bool:
    return path.is_file() and HOOK_BEGIN in path.read_text(encoding="utf-8", errors="replace")


def graphify_hooks_installed(repo_root: Path) -> bool:
    directory = hooks_dir(repo_root)
    return all(hook_installed(directory / name) for name in HOOK_NAMES)


def install_graphify_hooks(repo_root: Path) -> None:
    directory = hooks_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        path = directory / name
        text = path.read_text(encoding="utf-8") if path.exists() else "#!/usr/bin/env bash\n"
        if HOOK_BEGIN in text and HOOK_END in text:
            text = re.sub(
                rf"{re.escape(HOOK_BEGIN)}.*?{re.escape(HOOK_END)}\n?",
                HOOK_BLOCK,
                text,
                flags=re.S,
            )
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "\n" + HOOK_BLOCK
        path.write_text(text, encoding="utf-8")
        path.chmod(path.stat().st_mode | 0o755)


def uninstall_graphify_hooks(repo_root: Path) -> None:
    directory = hooks_dir(repo_root)
    for name in HOOK_NAMES:
        path = directory / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            rf"\n?{re.escape(HOOK_BEGIN)}.*?{re.escape(HOOK_END)}\n?",
            "\n",
            text,
            flags=re.S,
        )
        path.write_text(text.rstrip() + "\n", encoding="utf-8")


def resolve_repo(value: str | None) -> Path:
    root = git_root(Path(value).expanduser() if value else None)
    if root is None:
        die("not inside a Git repository", 1)
    return root


def cmd_graphify_hooks(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt graphify hooks", description="Manage per-project Graphify refresh hooks.")
    parser.add_argument("action", choices=["install", "uninstall", "status"])
    parser.add_argument("--repo", help="Git repository to manage; defaults to current repository")
    args = parser.parse_args(argv)
    repo_root = resolve_repo(args.repo)

    if args.action == "install":
        install_graphify_hooks(repo_root)
        print(f"Installed Graphify hooks in {hooks_dir(repo_root)}")
        return 0
    if args.action == "uninstall":
        uninstall_graphify_hooks(repo_root)
        print(f"Removed Graphify hook blocks from {hooks_dir(repo_root)}")
        return 0

    installed = graphify_hooks_installed(repo_root)
    print(f"Graphify hooks: {'installed' if installed else 'not installed'}")
    print(f"Hooks path: {hooks_dir(repo_root)}")
    return 0 if installed else 1


def cmd_graphify(argv: List[str], *, runner: Runner, which: Which = shutil.which) -> int:
    if argv[:1] == ["hooks"]:
        return cmd_graphify_hooks(argv[1:])

    # Backward compatibility: accept the old no-op hook check flag, but never
    # install hooks implicitly. Hook installation is explicit via
    # `agnt graphify hooks install`.
    passthrough = [arg for arg in argv if arg != "--no-hook-check"]

    graphify_bin = which("graphify")
    if graphify_bin:
        return runner([graphify_bin, *passthrough])
    if which("uv"):
        return runner(["uv", "tool", "run", "--from", "graphifyy", "graphify", *passthrough])
    die("graphify CLI not found and uv is unavailable; install with `uv tool install graphifyy`", 1)
