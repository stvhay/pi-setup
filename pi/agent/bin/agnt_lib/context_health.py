from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

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


def _scan_text_for_failures(text: str, rel_path: str) -> List[Dict[str, Any]]:
    """Scan a single text body for stale terms and gate weakening.

    ``rel_path`` is the label used in failure records so callers can attribute
    findings to a real file even when scanning content fed via stdin (for
    example, the projected post-edit state of a guidance file).
    """
    failures: List[Dict[str, Any]] = []
    for term, replacement in STALE_TERMS.items():
        if term in text:
            failures.append({"kind": "stale-term", "path": rel_path, "term": term, "replacement": replacement})
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in GATE_WEAKENING_PATTERNS]
    for line_no, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if "do not" in lowered or "don't" in lowered or "must not" in lowered:
            continue
        for pattern in compiled:
            if pattern.search(line):
                failures.append({"kind": "gate-weakening", "path": rel_path, "line": line_no, "pattern": pattern.pattern, "text": line.strip()})
    return failures


def scan_stale_terms() -> List[Dict[str, Any]]:
    return [
        failure
        for path in active_context_files()
        for failure in _scan_text_for_failures(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
        if failure["kind"] == "stale-term"
    ]


def scan_gate_weakening() -> List[Dict[str, Any]]:
    return [
        failure
        for path in active_context_files()
        for failure in _scan_text_for_failures(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
        if failure["kind"] == "gate-weakening"
    ]


def scan_content(text: str, rel_path: str) -> List[Dict[str, Any]]:
    """Public per-file scan used by the ``--stdin``/``--file`` modes.

    Returns failures only (stale terms + gate weakening). Cross-file checks
    such as skill-size and description overlap are not applicable to a single
    arbitrary file and are intentionally excluded here.
    """
    return _scan_text_for_failures(text, rel_path)


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


def content_health_report(text: str, rel_path: str) -> Dict[str, Any]:
    """Health report for a single file body (e.g. projected post-edit state).

    Runs the per-file failure checks (stale terms + gate weakening) only.
    Cross-file structural checks are not applicable.
    """
    failures = scan_content(text, rel_path)
    return {
        "schemaVersion": 1,
        "passed": not failures,
        "failures": failures,
        "warnings": [],
        "summary": {"failureCount": len(failures), "warningCount": 0},
    }


def cmd_context_health(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt context-health", description="Check active Pi context for stale terms, gate weakening, and entropy signals.")
    parser.add_argument("--max-skill-lines", type=int, default=220)
    parser.add_argument("--overlap-threshold", type=float, default=0.65)
    parser.add_argument("--strict", action="store_true", help="exit nonzero when failures are found")
    scan_group = parser.add_argument_group("per-file scan", "scan a single file body instead of the active context (used by the guidance-edit guard)")
    scan_source = scan_group.add_mutually_exclusive_group()
    scan_source.add_argument("--stdin", action="store_true", help="read file content from stdin and scan it")
    scan_source.add_argument("--file", metavar="PATH", help="scan the contents of this file instead of the active context")
    scan_group.add_argument("--path", metavar="LABEL", default="<stdin>", help="label to attribute findings to in the report (default: <stdin>)")
    args = parser.parse_args(argv)

    if args.stdin or args.file:
        if args.stdin:
            text = sys.stdin.read()
        else:
            file_path = Path(args.file)
            if not file_path.is_file():
                print(json.dumps({"schemaVersion": 1, "passed": False, "failures": [{"kind": "missing-file", "path": args.file}], "warnings": [], "summary": {"failureCount": 1, "warningCount": 0}}, indent=2, sort_keys=True))
                return 1 if args.strict else 0
            text = file_path.read_text(encoding="utf-8")
        report = content_health_report(text, args.path)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if args.strict and report["failures"] else 0

    report = context_health_report(max_skill_lines=args.max_skill_lines, overlap_threshold=args.overlap_threshold)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report["failures"] else 0
