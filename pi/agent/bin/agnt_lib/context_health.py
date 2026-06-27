from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import _agnt_common as common

from .core import ROOT

LARGE_SKILL_ALLOWLIST = {
    "code-simplification",
    "codify-subsystem",
    "design-principles",
    "executing-plans",
    "failure-choreography",
    "finishing-a-development-branch",
    "heilmeier-catechism",
    "layer-theme",
    "project-init",
    "requesting-code-review",
    "retrospective",
    "skill-creator",
    "stamp-cast",
    "stamp-stpa",
    "stamp-stpa-sec",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "writing-plans",
}

OVERLAP_ALLOWLIST = {
    tuple(sorted(pair))
    for pair in [
        ("stamp-stpa", "stamp-stpa-sec"),
        ("stamp-base", "stamp-cast"),
        ("ux-design-agent", "ux-writing"),
    ]
}

STALE_TERMS = {
    "pi-plans-dir": "Use `agnt plans-dir` instead.",
    "pi-peer": "Use `agnt invoke` instead.",
    "pi-fanout": "Use `agnt invoke --fanout` instead.",
    "automatically installs project-local Graphify refresh hooks": "Graphify hooks are explicit/approval-gated.",
}

GATE_WEAKENING_PATTERNS = [
    r"ignore (all )?(previous|above) instructions",
    r"bypass (the )?approval",
    r"skip (all )?verification",
    r"no need to (ask|request) approval",
    r"override (safety|security|git) (rules|gates|policy)",
    r"without explicit approval.*(push|deploy|delete|reset|merge)",
]


def active_context_files() -> List[Path]:
    files: List[Path] = []
    files.extend([ROOT / "AGENTS.md", ROOT / "SOUL.md"])
    files.extend(sorted((ROOT / "skills").glob("*/SKILL.md")))
    files.extend(sorted((ROOT / "AGENTS.d" / "roles").glob("*.md")))
    files.extend(sorted((ROOT / "AGENTS.d" / "models").glob("**/*.md")))
    files.extend(sorted((ROOT / "actions").glob("*.md")))
    return [path for path in files if path.is_file()]


def word_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 3}


def skill_descriptions() -> Dict[str, str]:
    rows: Dict[str, str] = {}
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        meta, _body = common.parse_frontmatter_file(path)
        rows[path.parent.name] = str(meta.get("description") or "")
    return rows


def scan_large_skills(max_lines: int) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        skill = path.parent.name
        if lines > max_lines and skill not in LARGE_SKILL_ALLOWLIST:
            warnings.append({"kind": "large-skill", "path": str(path.relative_to(ROOT)), "lines": lines, "limit": max_lines})
    return warnings


def scan_overlapping_skill_descriptions(threshold: float) -> List[Dict[str, Any]]:
    descriptions = skill_descriptions()
    names = sorted(descriptions)
    warnings: List[Dict[str, Any]] = []
    for i, left in enumerate(names):
        left_tokens = word_tokens(descriptions[left])
        if not left_tokens:
            continue
        for right in names[i + 1 :]:
            pair = tuple(sorted((left, right)))
            if pair in OVERLAP_ALLOWLIST:
                continue
            right_tokens = word_tokens(descriptions[right])
            if not right_tokens:
                continue
            union = left_tokens | right_tokens
            score = len(left_tokens & right_tokens) / len(union) if union else 0.0
            if score >= threshold:
                warnings.append({"kind": "skill-description-overlap", "skills": [left, right], "score": round(score, 3)})
    return warnings


def scan_stale_terms() -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    for path in active_context_files():
        text = path.read_text(encoding="utf-8")
        for term, replacement in STALE_TERMS.items():
            if term in text:
                failures.append({"kind": "stale-term", "path": str(path.relative_to(ROOT)), "term": term, "replacement": replacement})
    return failures


def scan_gate_weakening() -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in GATE_WEAKENING_PATTERNS]
    for path in active_context_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if "do not" in lowered or "don't" in lowered or "must not" in lowered:
                continue
            for pattern in compiled:
                if pattern.search(line):
                    failures.append({"kind": "gate-weakening", "path": str(path.relative_to(ROOT)), "line": line_no, "pattern": pattern.pattern, "text": line.strip()})
    return failures


def context_health_report(*, max_skill_lines: int = 220, overlap_threshold: float = 0.65) -> Dict[str, Any]:
    warnings: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    warnings.extend(scan_large_skills(max_skill_lines))
    warnings.extend(scan_overlapping_skill_descriptions(overlap_threshold))
    failures.extend(scan_stale_terms())
    failures.extend(scan_gate_weakening())
    return {
        "schemaVersion": 1,
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "summary": {"failureCount": len(failures), "warningCount": len(warnings)},
    }


def cmd_context_health(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt context-health", description="Check active Pi context for stale terms, gate weakening, and entropy signals.")
    parser.add_argument("--max-skill-lines", type=int, default=220)
    parser.add_argument("--overlap-threshold", type=float, default=0.65)
    parser.add_argument("--strict", action="store_true", help="exit nonzero when failures are found")
    args = parser.parse_args(argv)
    report = context_health_report(max_skill_lines=args.max_skill_lines, overlap_threshold=args.overlap_threshold)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report["failures"] else 0
