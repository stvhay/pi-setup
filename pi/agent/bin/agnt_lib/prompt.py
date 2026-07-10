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

from .core import ACTIONS, EVALS, PROMPT_PATTERNS, ROOT, die
from .evals import cmd_eval, split_models
from .metrics import utc_now

def slugify(value: str) -> str:
    chars: List[str] = []
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {"-", "_", " ", ".", "/"}:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "prompt-pattern"


def prompt_inventory_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    candidates: List[Tuple[str, Path]] = []
    for rel in ("AGENTS.md", "SOUL.md"):
        path = ROOT / rel
        if path.is_file():
            candidates.append(("root", path))
    candidates.extend(("skill", path) for path in sorted((ROOT / "skills").glob("*/SKILL.md")))
    candidates.extend(("model-supplement", path) for path in sorted(ROOT.glob("**/*.d/models/**/*.md")))
    candidates.extend(("role-supplement", path) for path in sorted(ROOT.glob("**/*.d/roles/*.md")))
    candidates.extend(("action-template", path) for path in sorted(ACTIONS.glob("*.md")))
    candidates.extend(("eval-prompt", path) for path in sorted(EVALS.glob("*/prompt.md")))
    seen: set[Path] = set()
    for kind, path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _body = common.parse_frontmatter_file(path) if text.startswith("---\n") else ({}, text)
        rows.append({
            "kind": kind,
            "path": str(path.relative_to(ROOT)),
            "bytes": len(text.encode("utf-8")),
            "lines": text.count("\n") + (1 if text else 0),
            "id": meta.get("id") or meta.get("name") or path.parent.name,
            "summary": meta.get("summary") or meta.get("description"),
        })
    return rows


def write_pattern_note(*, name: str, source_url: str, source_license: str, pattern: str, rewrite: str, notes: str | None) -> Path:
    path = PROMPT_PATTERNS / f"{slugify(name)}.md"
    if path.exists():
        die(f"pattern note already exists: {path}", 1)
    content = f"""---
name: {name}
sourceUrl: {source_url}
sourceLicense: {source_license}
copiedPromptText: false
createdAt: {utc_now()}
---

# {name}

## Adopted pattern

{pattern}

## Pi-specific rewrite

{rewrite}

## Provenance and license notes

- Source URL: {source_url}
- Source license: {source_license}
- Copied prompt text: no
- Use this note as a design reference only; do not paste external prompt text into Pi instructions.
"""
    if notes:
        content += f"\n## Additional notes\n\n{notes}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def cmd_prompt(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt prompt", description="Prompt inventory, eval helpers, and provenance-safe pattern notes.")
    sub = parser.add_subparsers(dest="action")
    inv = sub.add_parser("inventory", help="list tracked prompt/instruction artifacts")
    inv.add_argument("--kind", help="filter by kind")
    inv.add_argument("--paths-only", action="store_true")
    peval = sub.add_parser("eval", help="run a prompt-related eval via agnt eval")
    peval.add_argument("eval_id", help="eval id or path")
    peval.add_argument("--dry-run", action="store_true")
    peval.add_argument("--models", help="space- or comma-separated provider/model list")
    peval.add_argument("-o", "--output", help="output directory")
    note = sub.add_parser("import-pattern-note", help="write a rewritten external prompt-pattern note without copying prompt text")
    note.add_argument("--name", required=True)
    note.add_argument("--source-url", required=True)
    note.add_argument("--source-license", required=True)
    note.add_argument("--pattern", required=True, help="short description of the pattern to adopt")
    note.add_argument("--rewrite", required=True, help="original Pi-specific rewrite, not copied prompt text")
    note.add_argument("--notes")
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.action == "inventory":
        rows = prompt_inventory_rows()
        if args.kind:
            rows = [row for row in rows if row.get("kind") == args.kind]
        if args.paths_only:
            for row in rows:
                print(row["path"])
        else:
            print(json.dumps({"schemaVersion": 1, "count": len(rows), "prompts": rows}, indent=2, sort_keys=True))
        return 0
    if args.action == "eval":
        forwarded = ["run", args.eval_id]
        if args.dry_run:
            forwarded.append("--dry-run")
        if args.models:
            forwarded.extend(["--models", args.models])
        if args.output:
            forwarded.extend(["--output", args.output])
        return cmd_eval(forwarded)
    if args.action == "import-pattern-note":
        path = write_pattern_note(name=args.name, source_url=args.source_url, source_license=args.source_license, pattern=args.pattern, rewrite=args.rewrite, notes=args.notes)
        print(json.dumps({"schemaVersion": 1, "path": str(path), "copiedPromptText": False}, indent=2, sort_keys=True))
        return 0
    parser.print_help(sys.stderr)
    return 2
