from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import _agnt_common as common

from .core import ROOT, die
from .runs import create_run_bundle

ACTIONS = ROOT / "actions"
TASKS = ROOT / "tasks"
SKILLS = ROOT / "skills"
ROLES = ROOT / "AGENTS.d" / "roles"
WRITE_EFFECTS = {"edit_files", "write_workspace", "update_beads", "external_write", "push", "deploy", "delete_files"}


def action_files() -> List[Path]:
    return sorted(ACTIONS.glob("*.md")) if ACTIONS.is_dir() else []


def load_action(path_or_id: str) -> tuple[Path, Dict[str, Any], str]:
    candidate = Path(path_or_id).expanduser()
    if not candidate.is_file():
        candidate = ACTIONS / f"{path_or_id}.md"
    if not candidate.is_file():
        die(f"action template not found: {path_or_id}", 1)
    meta, body = common.parse_frontmatter_file(candidate)
    return candidate, meta, body


def action_inventory_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in action_files():
        meta, _body = common.parse_frontmatter_file(path)
        rows.append({
            "id": meta.get("id") or path.stem,
            "path": str(path.relative_to(ROOT)),
            "summary": meta.get("summary"),
            "routingTask": meta.get("routingTask"),
            "skills": meta.get("skills") or [],
            "defaultRole": meta.get("defaultRole"),
            "allowedEffects": meta.get("allowedEffects") or [],
        })
    return rows


def role_meta(role_id: str) -> Dict[str, Any] | None:
    path = ROLES / f"{role_id}.md"
    if not path.is_file():
        return None
    meta, _body = common.parse_frontmatter_file(path)
    return meta


def validate_action_meta(path: Path, meta: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    action_id = meta.get("id") or path.stem
    if action_id != path.stem:
        failures.append(f"{path}: id must match filename")
    task = meta.get("routingTask")
    if not task:
        failures.append(f"{path}: missing routingTask")
    elif not (TASKS / f"{task}.md").is_file():
        failures.append(f"{path}: missing routing task {task}")
    skills = meta.get("skills") or []
    if not isinstance(skills, list):
        failures.append(f"{path}: skills must be a list")
        skills = []
    for skill in skills:
        if not (SKILLS / str(skill) / "SKILL.md").is_file():
            failures.append(f"{path}: missing skill {skill}")
    effects = meta.get("allowedEffects") or []
    if not isinstance(effects, list) or not effects:
        failures.append(f"{path}: allowedEffects must be a non-empty list")
        effects = []
    role = meta.get("defaultRole")
    if role:
        role_info = role_meta(str(role))
        if role_info is None:
            failures.append(f"{path}: missing role {role}")
        elif role_info.get("writeAccess") is False and WRITE_EFFECTS.intersection(str(effect) for effect in effects):
            failures.append(f"{path}: read-only role {role} cannot use write effects {sorted(WRITE_EFFECTS.intersection(str(effect) for effect in effects))}")
    if not meta.get("outputContract"):
        failures.append(f"{path}: missing outputContract")
    return failures


def validate_all_actions() -> List[str]:
    failures: List[str] = []
    for path in action_files():
        meta, _body = common.parse_frontmatter_file(path)
        failures.extend(validate_action_meta(path, meta))
    return failures


def cmd_action(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt action", description="List, validate, and render prompt/action templates into invocation artifacts.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="list action templates")
    sub.add_parser("validate", help="validate action template references")
    render = sub.add_parser("render", help="render an action template into a run invocation bundle")
    render.add_argument("action_id")
    render.add_argument("--target", action="append", default=[], help="input reference/target; may be repeated")
    render.add_argument("--bead")
    render.add_argument("--model")
    render.add_argument("--role", help="override default role")
    render.add_argument("--runs-dir")
    render.add_argument("--id")
    render.add_argument("--dry-run", action="store_true", help="print planned invocation without writing files")
    render.add_argument("--json", action="store_true")
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.command == "list":
        print(json.dumps({"schemaVersion": 1, "actions": action_inventory_rows()}, indent=2, sort_keys=True))
        return 0
    if args.command == "validate":
        failures = validate_all_actions()
        print(json.dumps({"schemaVersion": 1, "passed": not failures, "failures": failures}, indent=2, sort_keys=True))
        return 0 if not failures else 1
    if args.command == "render":
        path, meta, _body = load_action(args.action_id)
        failures = validate_action_meta(path, meta)
        if failures:
            print(json.dumps({"schemaVersion": 1, "passed": False, "failures": failures}, indent=2, sort_keys=True), file=sys.stderr)
            return 1
        invocation = {
            "action": meta.get("id") or path.stem,
            "routingTask": meta["routingTask"],
            "inputRefs": args.target,
            "skills": meta.get("skills") or [],
            "role": args.role or meta.get("defaultRole"),
            "bead": args.bead,
            "model": args.model,
            "allowedEffects": meta.get("allowedEffects") or [],
            "acceptanceCriteria": [],
            "outputContract": meta.get("outputContract"),
        }
        if args.dry_run:
            print(json.dumps({"schemaVersion": 1, "dryRun": True, "invocation": invocation}, indent=2, sort_keys=True))
            return 0
        bundle = create_run_bundle(
            action=str(invocation["action"]),
            routing_task=str(invocation["routingTask"]),
            input_refs=[str(item) for item in invocation["inputRefs"]],
            skills=[str(item) for item in invocation["skills"]],
            role=str(invocation["role"]) if invocation["role"] else None,
            bead=str(invocation["bead"]) if invocation["bead"] else None,
            model=str(invocation["model"]) if invocation["model"] else None,
            allowed_effects=[str(item) for item in invocation["allowedEffects"]],
            acceptance_criteria=[],
            output_contract=str(invocation["outputContract"]),
            runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else None,
            id_value=args.id,
        )
        result = {"schemaVersion": 1, "bundle": str(bundle), "invocation": str(bundle / "invocation.yaml")}
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else str(bundle))
        return 0
    parser.print_help(sys.stderr)
    return 2
