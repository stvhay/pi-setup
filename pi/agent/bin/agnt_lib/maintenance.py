from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple

from .context_health import context_health_report as build_context_health_report
from .health import work_health_report
from .runs import default_runs_dir

BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]

MAINTENANCE_MODES: Dict[str, Dict[str, Any]] = {
    "design-review": {
        "label": "maintenance:design-review",
        "title": "Maintenance: design review",
        "routingTask": "review",
        "role": "quality-reviewer",
        "action": "maintenance",
    },
    "architecture-review": {
        "label": "maintenance:architecture-review",
        "title": "Maintenance: architecture review",
        "routingTask": "review",
        "role": "quality-reviewer",
        "action": "maintenance",
    },
    "simplification": {
        "label": "maintenance:simplification",
        "title": "Maintenance: simplification/refactor proposal",
        "routingTask": "implementation",
        "role": "implementation-worker",
        "action": "implement",
    },
    "workflow-retro": {
        "label": "maintenance:workflow-retro",
        "title": "Maintenance: workflow retrospective",
        "routingTask": "review",
        "role": "planner",
        "action": "maintenance",
    },
    "context-health": {
        "label": "maintenance:context-health",
        "title": "Maintenance: context health review",
        "routingTask": "review",
        "role": "verifier",
        "action": "maintenance",
    },
    "lessons-harvest": {
        "label": "maintenance:lessons-harvest",
        "title": "Maintenance: lessons harvest",
        "routingTask": "research",
        "role": "planner",
        "action": "maintenance",
    },
}

DEFAULT_THRESHOLDS = {
    "closedImplementationBeads": 5,
    "commits": 10,
    "failedOrBlockedRuns": 2,
    "humanBlockers": 2,
    "contextWarnings": 3,
    "healthWarnings": 3,
    "healthFailures": 1,
    "recordedSessions": 5,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_beads_runner(args: List[str]) -> Tuple[int, Any, str]:
    from .work import run_beads_json

    return run_beads_json(args)


def _labels(bead: Dict[str, Any]) -> set[str]:
    return {str(label) for label in bead.get("labels") or []}


def _is_closed(bead: Dict[str, Any]) -> bool:
    return str(bead.get("status") or "").lower() == "closed"


def _is_implementation(bead: Dict[str, Any]) -> bool:
    labels = _labels(bead)
    title = str(bead.get("title") or "").lower()
    if "implementation" in labels or "implement" in title:
        return True
    metadata = bead.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = None
    if isinstance(metadata, dict):
        pi_meta = metadata.get("pi")
        if isinstance(pi_meta, dict) and pi_meta.get("action") == "implement":
            return True
    return False


def _is_human_blocker(bead: Dict[str, Any]) -> bool:
    labels = _labels(bead)
    title = str(bead.get("title") or "").lower()
    return bool(labels.intersection({"human", "human-gate"})) or "human" in title or "approval" in labels or str(bead.get("issue_type") or "") == "decision"


def _maintenance_mode_from_labels(bead: Dict[str, Any]) -> str | None:
    for mode, config in MAINTENANCE_MODES.items():
        if config["label"] in _labels(bead):
            return mode
    return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def latest_closed_maintenance_time(beads: Iterable[Dict[str, Any]]) -> datetime | None:
    times: List[datetime] = []
    for bead in beads:
        if _maintenance_mode_from_labels(bead) and _is_closed(bead):
            stamp = _parse_time(bead.get("closed_at") or bead.get("closedAt"))
            if stamp:
                times.append(stamp)
    return max(times) if times else None


def open_maintenance_modes(beads: Iterable[Dict[str, Any]]) -> set[str]:
    modes: set[str] = set()
    for bead in beads:
        mode = _maintenance_mode_from_labels(bead)
        if mode and not _is_closed(bead):
            modes.add(mode)
    return modes


def collect_beads(beads_runner: BeadsRunner = default_beads_runner) -> Tuple[List[Dict[str, Any]], List[str]]:
    code, data, err = beads_runner(["list"])
    if code != 0:
        return [], [str(err or "bd list failed")]
    if not isinstance(data, list):
        return [], ["bd list returned non-list JSON"]
    return [item for item in data if isinstance(item, dict)], []


def git_commit_summary(root: Path | str | None = None, *, since: datetime | None = None) -> Dict[str, Any]:
    repo = Path(root).expanduser() if root is not None else Path.cwd()
    cmd = ["git", "-C", str(repo), "rev-list", "--count"]
    if since:
        cmd.append(f"--since={since.isoformat()}")
    cmd.append("HEAD")
    try:
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return {"commitsSinceMaintenance": 0, "error": str(exc)}
    if proc.returncode != 0:
        return {"commitsSinceMaintenance": 0, "error": proc.stderr.strip()}
    try:
        count = int((proc.stdout or "0").strip() or 0)
    except ValueError:
        count = 0
    return {"commitsSinceMaintenance": count, "since": since.isoformat().replace("+00:00", "Z") if since else None}


def _read_json(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def collect_runs(runs_dir: Path | str | None = None) -> List[Dict[str, Any]]:
    root = Path(runs_dir).expanduser() if runs_dir is not None else default_runs_dir()
    if not root.is_dir():
        return []
    runs: List[Dict[str, Any]] = []
    for bundle in sorted(path for path in root.iterdir() if path.is_dir()):
        invocation = _read_json(bundle / "invocation.yaml") or {}
        result = _read_json(bundle / "result.yaml") or {}
        runs.append({
            "id": str(invocation.get("id") or result.get("invocationId") or bundle.name),
            "bundle": str(bundle),
            "bead": invocation.get("bead"),
            "status": result.get("status"),
            "completedAt": result.get("completedAt"),
            "sessionRef": result.get("sessionRef"),
            "transcriptRef": result.get("transcriptRef"),
            "memorySummaryRef": result.get("memorySummaryRef"),
            "evidence": result.get("evidence") or [],
        })
    return runs


def _summary_count(report: Dict[str, Any] | None, key: str) -> int:
    summary = report.get("summary") if isinstance(report, dict) else None
    if isinstance(summary, dict):
        try:
            return int(summary.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _derive_signals(
    *,
    beads: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    git_summary: Dict[str, Any],
    health_report: Dict[str, Any] | None,
    context_health_report: Dict[str, Any] | None,
) -> Dict[str, int]:
    failed_or_blocked = sum(1 for run in runs if str(run.get("status") or "") in {"failed", "blocked"})
    return {
        "closedImplementationBeads": sum(1 for bead in beads if _is_closed(bead) and _is_implementation(bead)),
        "commitsSinceMaintenance": int(git_summary.get("commitsSinceMaintenance") or 0),
        "failedOrBlockedRuns": failed_or_blocked,
        "humanBlockers": sum(1 for bead in beads if not _is_closed(bead) and _is_human_blocker(bead)),
        "contextWarnings": _summary_count(context_health_report, "warningCount"),
        "healthWarnings": _summary_count(health_report, "warningCount"),
        "healthFailures": _summary_count(health_report, "failureCount"),
        "recordedSessions": sum(1 for run in runs if run.get("sessionRef") or run.get("transcriptRef")),
    }


def _due_item(mode: str, reason: str, signals: Dict[str, int]) -> Dict[str, Any]:
    config = MAINTENANCE_MODES[mode]
    return {
        "mode": mode,
        "label": config["label"],
        "title": config["title"],
        "reason": reason,
        "signals": dict(signals),
    }


def maintenance_due_report(
    *,
    beads: List[Dict[str, Any]] | None = None,
    runs: List[Dict[str, Any]] | None = None,
    git_summary: Dict[str, Any] | None = None,
    health_report: Dict[str, Any] | None = None,
    context_health_report: Dict[str, Any] | None = None,
    thresholds: Dict[str, int] | None = None,
    root: Path | str | None = None,
    runs_dir: Path | str | None = None,
    beads_runner: BeadsRunner = default_beads_runner,
) -> Dict[str, Any]:
    warnings: List[str] = []
    if beads is None:
        beads, bead_warnings = collect_beads(beads_runner)
        warnings.extend(bead_warnings)
    if runs is None:
        runs = collect_runs(runs_dir)
    last_maintenance = latest_closed_maintenance_time(beads)
    if git_summary is None:
        git_summary = git_commit_summary(root, since=last_maintenance)
    if health_report is None:
        health_report = work_health_report(root=root, runs_dir=runs_dir, include_beads=False)
    if context_health_report is None:
        context_health_report = build_context_health_report()
    active_modes = open_maintenance_modes(beads)
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    signals = _derive_signals(beads=beads, runs=runs, git_summary=git_summary, health_report=health_report, context_health_report=context_health_report)

    candidates: List[Dict[str, Any]] = []
    if signals["closedImplementationBeads"] >= limits["closedImplementationBeads"]:
        candidates.append(_due_item("design-review", "closed implementation work reached design-review threshold", signals))
    if signals["commitsSinceMaintenance"] >= limits["commits"]:
        candidates.append(_due_item("architecture-review", "commits since last maintenance reached architecture-review threshold", signals))
    if signals["failedOrBlockedRuns"] >= limits["failedOrBlockedRuns"] or signals["healthFailures"] >= limits["healthFailures"]:
        candidates.append(_due_item("simplification", "failed/blocked runs or health failures reached simplification threshold", signals))
    if signals["humanBlockers"] >= limits["humanBlockers"]:
        candidates.append(_due_item("workflow-retro", "repeated human blockers reached workflow retrospective threshold", signals))
    if signals["contextWarnings"] >= limits["contextWarnings"] or signals["healthWarnings"] >= limits["healthWarnings"]:
        candidates.append(_due_item("context-health", "context or health warnings reached review threshold", signals))
    if signals["recordedSessions"] >= limits["recordedSessions"]:
        candidates.append(_due_item("lessons-harvest", "recorded worker sessions reached lessons-harvest threshold", signals))

    due: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []
    for item in candidates:
        if item["mode"] in active_modes:
            suppressed.append({**item, "suppressedReason": "open maintenance bead already exists for this mode"})
        else:
            due.append(item)

    return {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "due": due,
        "suppressed": suppressed,
        "signals": signals,
        "thresholds": limits,
        "lastMaintenanceAt": last_maintenance.isoformat().replace("+00:00", "Z") if last_maintenance else None,
        "warnings": warnings,
    }


def _metadata_for_mode(mode: str) -> Dict[str, Any]:
    config = MAINTENANCE_MODES[mode]
    if mode == "simplification":
        return {
            "pi": {
                "action": "implement",
                "routingTask": "implementation",
                "role": "implementation-worker",
                "approved": False,
                "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
                "risk": "medium",
                "budget": "balanced",
                "modelPolicy": {"mode": "auto", "diversity": "normal", "avoidFamilies": []},
                "thinkingPolicy": "auto",
                "epicId": "maintenance",
                "worktreePolicy": "epic-worktree",
                "writeSet": ["TBD-by-approved-maintenance-plan"],
                "sessionPolicy": "recorded",
                "memoryPolicy": "auto",
                "closeout": {
                    "requiresEvidence": True,
                    "requiresResolvedApprovals": True,
                    "requiresFollowUpsReconciled": True,
                },
            }
        }
    return {
        "pi": {
            "action": config["action"],
            "routingTask": config["routingTask"],
            "role": config["role"],
            "allowedEffects": ["read_workspace", "write_artifacts"],
            "risk": "low",
            "budget": "cheap",
            "modelPolicy": {"mode": "auto", "diversity": "normal", "avoidFamilies": [], "localOk": True},
            "thinkingPolicy": "auto",
            "sessionPolicy": "recorded",
            "memoryPolicy": "auto",
        }
    }


def _description_for_due(item: Dict[str, Any], report: Dict[str, Any]) -> str:
    signals = report.get("signals") or item.get("signals") or {}
    return "\n".join([
        "Why:",
        "Autonomous maintenance is due based on durable project signals rather than hidden counters.",
        "",
        "What:",
        f"Run the {item['mode']} maintenance mode and record findings, evidence, and any follow-up Beads.",
        "",
        "Trigger:",
        str(item.get("reason") or "maintenance due"),
        "",
        "Signals:",
        json.dumps(signals, sort_keys=True),
        "",
        "Closeout:",
        "Record evidence in .pi/runs or Beads, reconcile follow-ups as Beads, and close this maintenance checkpoint when verified.",
    ])


def maintenance_bead_specs(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for item in report.get("due") or []:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "")
        if mode not in MAINTENANCE_MODES:
            continue
        config = MAINTENANCE_MODES[mode]
        metadata = _metadata_for_mode(mode)
        labels = sorted({"maintenance", "agent-os", "autonomous-orchestration", config["label"]})
        specs.append({
            "mode": mode,
            "label": config["label"],
            "title": config["title"],
            "issueType": "task",
            "priority": 2,
            "labels": labels,
            "description": _description_for_due(item, report),
            "acceptance": "Maintenance review is recorded with evidence; follow-up work is represented as Beads; closeout checks pass.",
            "metadata": json.dumps(metadata, sort_keys=True, separators=(",", ":")),
        })
    return specs


def _create_args(spec: Dict[str, Any]) -> List[str]:
    args = [
        "create",
        str(spec["title"]),
        "--type",
        str(spec.get("issueType") or "task"),
        "--priority",
        str(spec.get("priority") or 2),
        "--labels",
        ",".join(str(label) for label in spec.get("labels") or []),
        "--description",
        str(spec.get("description") or ""),
        "--acceptance",
        str(spec.get("acceptance") or ""),
        "--metadata",
        str(spec.get("metadata") or "{}"),
    ]
    return args


def maintenance_create_beads(
    report: Dict[str, Any],
    *,
    dry_run: bool = True,
    beads_runner: BeadsRunner = default_beads_runner,
) -> Dict[str, Any]:
    specs = maintenance_bead_specs(report)
    commands = [_create_args(spec) for spec in specs]
    if dry_run:
        return {"schemaVersion": 1, "dryRun": True, "beads": specs, "commands": commands, "created": []}
    created: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    for spec, args in zip(specs, commands):
        code, data, err = beads_runner(args)
        if code != 0:
            failures.append({"spec": spec, "code": code, "error": err})
        else:
            created.append({"spec": spec, "result": data})
    return {"schemaVersion": 1, "dryRun": False, "beads": specs, "commands": commands, "created": created, "failures": failures}


def lessons_harvest_plan(
    *,
    closed_beads: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    observational_memory_refs: List[str] | None = None,
) -> Dict[str, Any]:
    input_refs: List[str] = []
    for bead in closed_beads:
        bead_id = bead.get("id")
        if bead_id:
            input_refs.append(f"bead:{bead_id}")
    for run in runs:
        bundle = run.get("bundle") or run.get("id")
        if bundle:
            input_refs.append(f"run:{bundle}")
        for key in ("sessionRef", "transcriptRef", "memorySummaryRef"):
            value = run.get(key)
            if value:
                input_refs.append(str(value))
    input_refs.extend(str(ref) for ref in observational_memory_refs or [] if ref)
    seen: set[str] = set()
    compact_refs = [ref for ref in input_refs if not (ref in seen or seen.add(ref))]
    report = {"schemaVersion": 1, "due": [{"mode": "lessons-harvest", "label": MAINTENANCE_MODES["lessons-harvest"]["label"], "reason": "explicit lessons harvest"}], "signals": {}}
    spec = maintenance_bead_specs(report)[0]
    return {
        "schemaVersion": 1,
        "mode": "lessons-harvest",
        "inputRefs": compact_refs,
        "closedBeadCount": len(closed_beads),
        "runCount": len(runs),
        "observationalMemoryRefCount": len(observational_memory_refs or []),
        "bead": spec,
    }


__all__ = [
    "MAINTENANCE_MODES",
    "DEFAULT_THRESHOLDS",
    "maintenance_due_report",
    "maintenance_bead_specs",
    "maintenance_create_beads",
    "lessons_harvest_plan",
    "collect_beads",
    "collect_runs",
    "git_commit_summary",
]
