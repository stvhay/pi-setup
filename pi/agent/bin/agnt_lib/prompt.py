from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import _agnt_common as common

from .core import ACTIONS, EVALS, ROOT

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


def cmd_prompt(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt prompt", description="Inventory tracked prompt and instruction files.")
    sub = parser.add_subparsers(dest="action")
    inv = sub.add_parser("inventory", help="list tracked prompt/instruction artifacts")
    inv.add_argument("--kind", help="filter by kind")
    inv.add_argument("--paths-only", action="store_true")
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
    parser.print_help(sys.stderr)
    return 2
