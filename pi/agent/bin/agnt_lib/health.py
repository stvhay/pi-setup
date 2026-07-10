from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .runs import default_runs_dir
from .runner_protocol import runner_paths
from .worktree_policy import list_git_worktrees

StatusRunner = Callable[[str], Tuple[int, str, str]]
RefResolver = Callable[[str], Dict[str, Any]]
BeadsRunner = Callable[[List[str]], Tuple[int, Any, str]]

TERMINAL_RUN_STATUSES = {"succeeded", "failed", "blocked", "superseded"}
PASS_CHECK_STATUSES = {"pass", "passed", "ok", "success", "succeeded", "skip", "skipped", "not-applicable", "not_applicable"}
RAW_TOOL_PATTERNS = [
    re.compile(r"\braw\s+(bash|bd|beads|subagent|tool)\b", re.IGNORECASE),
    re.compile(r"\b(bypass(?:ed|ing)?|circumvent(?:ed|ing)?)\b.*\b(approval|gateway|beads|closeout|runner)\b", re.IGNORECASE),
    re.compile(r"\b(bash|bd|beads)\s+bypass\b", re.IGNORECASE),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_json_object(path: Path) -> Tuple[Dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON/YAML artifact: {exc}"
    if not isinstance(data, dict):
        return None, "artifact must be an object"
    return data, None


def _finding(
    finding_id: str,
    severity: str,
    message: str,
    *,
    category: str,
    run_id: str | None = None,
    bundle: Path | None = None,
    ref: str | None = None,
    path: str | None = None,
    detail: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {"id": finding_id, "severity": severity, "category": category, "message": message}
    if run_id:
        item["run"] = run_id
    if bundle:
        item["bundle"] = str(bundle)
    if ref:
        item["ref"] = ref
    if path:
        item["path"] = path
    if detail:
        item["detail"] = detail
    return item


def _is_closed(status: Any) -> bool:
    return str(status or "").lower() == "closed"


def check_status_passed(value: Any) -> bool:
    return str(value or "").strip().lower() in PASS_CHECK_STATUSES


def default_status_runner(path: str) -> Tuple[int, str, str]:
    proc = subprocess.run(["git", "-C", path, "status", "--short"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout, proc.stderr


def default_beads_runner(args: List[str]) -> Tuple[int, Any, str]:
    from .work import run_beads_json

    return run_beads_json(args)


def default_ref_resolver(ref: str) -> Dict[str, Any]:
    code, data, err = default_beads_runner(["show", ref])
    if code != 0:
        return {"id": ref, "exists": False, "status": None, "error": (err or "not found").strip()}
    bead = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
    if not isinstance(bead, dict):
        return {"id": ref, "exists": False, "status": None, "error": "no bead returned"}
    return {"id": ref, "exists": True, "status": bead.get("status"), "type": bead.get("issue_type") or bead.get("type")}


def iter_run_bundles(runs_dir: Path | None = None) -> List[Path]:
    root = runs_dir or default_runs_dir()
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def _text_values(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        values: List[str] = []
        for item in value:
            values.extend(_text_values(item))
        return values
    if isinstance(value, dict):
        values: List[str] = []
        for item in value.values():
            values.extend(_text_values(item))
        return values
    return []


def _append_raw_tool_findings(findings: List[Dict[str, Any]], *, run_id: str, bundle: Path, result: Dict[str, Any]) -> None:
    for text in _text_values({"summary": result.get("summary"), "evidence": result.get("evidence"), "artifacts": result.get("artifacts")}):
        for pattern in RAW_TOOL_PATTERNS:
            if pattern.search(text):
                findings.append(_finding(
                    "raw-tool-bypass-marker",
                    "failure",
                    "run evidence/result text contains a raw-tool or bypass marker that must be reconciled before closeout",
                    category="closeout",
                    run_id=run_id,
                    bundle=bundle,
                    detail={"pattern": pattern.pattern, "text": text[:240]},
                ))
                return


def _append_check_findings(findings: List[Dict[str, Any]], *, run_id: str, bundle: Path, key: str, result: Dict[str, Any]) -> None:
    value = result.get(key) or []
    if not isinstance(value, list):
        findings.append(_finding(
            f"invalid-{key}",
            "failure",
            f"result {key} must be a list",
            category="run-artifact",
            run_id=run_id,
            bundle=bundle,
        ))
        return
    finding_id = "failed-health-check" if key == "healthChecks" else "failed-closeout-check"
    for check in value:
        if not isinstance(check, dict):
            findings.append(_finding(
                finding_id,
                "failure",
                f"{key} entry must be an object with a passing status",
                category="closeout",
                run_id=run_id,
                bundle=bundle,
                detail={"check": check},
            ))
            continue
        if not check_status_passed(check.get("status")):
            findings.append(_finding(
                finding_id,
                "failure",
                f"{key} entry {check.get('name') or '<unnamed>'} is not passed: {check.get('status')}",
                category="closeout",
                run_id=run_id,
                bundle=bundle,
                detail={"check": check},
            ))


def _append_ref_findings(
    findings: List[Dict[str, Any]],
    *,
    run_id: str,
    bundle: Path,
    key: str,
    result: Dict[str, Any],
    ref_resolver: RefResolver,
    unresolved_severity: str = "failure",
) -> None:
    refs = result.get(key) or []
    if not isinstance(refs, list):
        findings.append(_finding(
            f"invalid-{key}",
            "failure",
            f"result {key} must be a list",
            category="run-artifact",
            run_id=run_id,
            bundle=bundle,
        ))
        return
    finding_id = "unresolved-approval-ref" if key == "approvalRefs" else "unresolved-decision-ref"
    for ref in refs:
        ref_id = str(ref)
        resolved = ref_resolver(ref_id)
        if not resolved.get("exists") or not _is_closed(resolved.get("status")):
            findings.append(_finding(
                finding_id,
                unresolved_severity,
                f"{key} reference {ref_id} is not resolved/closed",
                category="beads",
                run_id=run_id,
                bundle=bundle,
                ref=ref_id,
                detail=resolved,
            ))


def _append_followup_findings(
    findings: List[Dict[str, Any]],
    *,
    run_id: str,
    bundle: Path,
    result: Dict[str, Any],
    ref_resolver: RefResolver,
    unresolved_severity: str = "failure",
) -> None:
    refs = result.get("followUps") or []
    if not isinstance(refs, list):
        findings.append(_finding(
            "invalid-followups",
            "failure",
            "result followUps must be a list",
            category="run-artifact",
            run_id=run_id,
            bundle=bundle,
        ))
        return
    for ref in refs:
        ref_id = str(ref)
        resolved = ref_resolver(ref_id)
        if not resolved.get("exists"):
            findings.append(_finding(
                "unresolved-followup-ref",
                unresolved_severity,
                f"follow-up reference {ref_id} does not resolve to a Beads issue",
                category="beads",
                run_id=run_id,
                bundle=bundle,
                ref=ref_id,
                detail=resolved,
            ))


def _append_worktree_findings(
    findings: List[Dict[str, Any]],
    *,
    run_id: str | None,
    bundle: Path | None,
    worktree: Dict[str, Any],
    status_runner: StatusRunner,
    seen_paths: set[str],
) -> None:
    policy = str(worktree.get("policy") or "none")
    path_value = worktree.get("path")
    if policy == "none" or not isinstance(path_value, str) or not path_value:
        return
    path = str(Path(path_value).expanduser())
    if path in seen_paths:
        return
    seen_paths.add(path)
    if not Path(path).exists():
        findings.append(_finding(
            "missing-worktree",
            "failure",
            f"recorded worktree path does not exist: {path}",
            category="worktree",
            run_id=run_id,
            bundle=bundle,
            path=path,
        ))
        return
    code, out, err = status_runner(path)
    if code != 0:
        findings.append(_finding(
            "worktree-status-failed",
            "warning",
            f"could not inspect worktree status for {path}: {err or code}",
            category="worktree",
            run_id=run_id,
            bundle=bundle,
            path=path,
        ))
        return
    if out.strip():
        findings.append(_finding(
            "dirty-worktree",
            "failure",
            f"recorded worktree has uncommitted changes: {path}",
            category="worktree",
            run_id=run_id,
            bundle=bundle,
            path=path,
            detail={"status": out},
        ))


def scan_run_bundle_health(
    bundle: Path,
    *,
    ref_resolver: RefResolver,
    status_runner: StatusRunner,
    now: datetime,
    stale_after: timedelta,
    seen_worktree_paths: set[str] | None = None,
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    invocation, inv_error = _read_json_object(bundle / "invocation.yaml")
    result, result_error = _read_json_object(bundle / "result.yaml")
    if inv_error:
        findings.append(_finding("invalid-run-artifact", "failure", f"invalid invocation artifact: {inv_error}", category="run-artifact", bundle=bundle))
    if result_error:
        findings.append(_finding("invalid-run-artifact", "failure", f"invalid result artifact: {result_error}", category="run-artifact", bundle=bundle))
    if not invocation or not result:
        return findings

    run_id = str(invocation.get("id") or bundle.name)
    bead = invocation.get("bead")
    status = str(result.get("status") or "")
    legacy_completed = "sessionPolicy" not in invocation and bool(result.get("completedAt")) and status in TERMINAL_RUN_STATUSES
    unresolved_ref_severity = "warning" if legacy_completed else "failure"

    if bead:
        bead_ref = str(bead)
        resolved = ref_resolver(bead_ref)
        if not resolved.get("exists"):
            findings.append(_finding(
                "orphaned-run-bead",
                unresolved_ref_severity,
                f"run references Beads issue {bead_ref}, but it cannot be resolved",
                category="beads",
                run_id=run_id,
                bundle=bundle,
                ref=bead_ref,
                detail=resolved,
            ))
        elif _is_closed(resolved.get("status")) and not result.get("completedAt") and str(result.get("status") or "") not in TERMINAL_RUN_STATUSES:
            findings.append(_finding(
                "active-run-closed-bead",
                "failure",
                f"run is still active but referenced bead {bead_ref} is closed",
                category="beads",
                run_id=run_id,
                bundle=bundle,
                ref=bead_ref,
                detail=resolved,
            ))

    if result.get("status") == "succeeded" and not result.get("evidence"):
        findings.append(_finding(
            "missing-verification-evidence",
            "failure",
            "succeeded run is missing verification evidence",
            category="closeout",
            run_id=run_id,
            bundle=bundle,
        ))

    _append_ref_findings(findings, run_id=run_id, bundle=bundle, key="approvalRefs", result=result, ref_resolver=ref_resolver, unresolved_severity=unresolved_ref_severity)
    _append_ref_findings(findings, run_id=run_id, bundle=bundle, key="decisionRefs", result=result, ref_resolver=ref_resolver, unresolved_severity=unresolved_ref_severity)
    _append_followup_findings(findings, run_id=run_id, bundle=bundle, result=result, ref_resolver=ref_resolver, unresolved_severity=unresolved_ref_severity)
    _append_check_findings(findings, run_id=run_id, bundle=bundle, key="healthChecks", result=result)
    _append_check_findings(findings, run_id=run_id, bundle=bundle, key="closeoutChecks", result=result)
    _append_raw_tool_findings(findings, run_id=run_id, bundle=bundle, result=result)

    completed = result.get("completedAt")
    created_at = _parse_time(invocation.get("createdAt"))
    active = not completed and status not in TERMINAL_RUN_STATUSES
    if active and result.get("sessionRef") and created_at and now - created_at > stale_after:
        findings.append(_finding(
            "stale-active-session",
            "failure",
            f"active recorded session is older than {stale_after}",
            category="session",
            run_id=run_id,
            bundle=bundle,
            detail={"createdAt": invocation.get("createdAt"), "sessionRef": result.get("sessionRef")},
        ))

    worktree = invocation.get("worktree")
    if isinstance(worktree, dict):
        _append_worktree_findings(
            findings,
            run_id=run_id,
            bundle=bundle,
            worktree=worktree,
            status_runner=status_runner,
            seen_paths=seen_worktree_paths if seen_worktree_paths is not None else set(),
        )
    return findings


def _append_current_checkout_finding(findings: List[Dict[str, Any]], *, root: Path, status_runner: StatusRunner, strict: bool) -> None:
    if not root.exists():
        return
    code, out, err = status_runner(str(root))
    if code != 0:
        findings.append(_finding(
            "checkout-status-failed",
            "warning",
            f"could not inspect current checkout status: {err or code}",
            category="git",
            path=str(root),
        ))
    elif out.strip():
        findings.append(_finding(
            "dirty-main-checkout",
            "failure" if strict else "warning",
            "current checkout has uncommitted changes; closeout should happen from a clean tree",
            category="git",
            path=str(root),
            detail={"status": out},
        ))


def _append_known_epic_worktree_findings(findings: List[Dict[str, Any]], *, root: Path, status_runner: StatusRunner, seen_paths: set[str]) -> None:
    epic_root = root / ".worktrees" / "epic"
    if epic_root.is_dir():
        for path in sorted(item for item in epic_root.iterdir() if item.is_dir()):
            _append_worktree_findings(
                findings,
                run_id=None,
                bundle=None,
                worktree={"policy": "epic-worktree", "path": str(path)},
                status_runner=status_runner,
                seen_paths=seen_paths,
            )
    for item in list_git_worktrees(repo_root=root):
        path = item.get("path")
        branch = item.get("branch") or ""
        if isinstance(path, str) and ("/.worktrees/epic/" in path or branch.startswith("epic/")):
            _append_worktree_findings(
                findings,
                run_id=None,
                bundle=None,
                worktree={"policy": "epic-worktree", "path": path},
                status_runner=status_runner,
                seen_paths=seen_paths,
            )


def _append_runner_findings(findings: List[Dict[str, Any]], *, root: Path, now: datetime, stale_after: timedelta) -> None:
    try:
        from .runner import runner_status

        status = runner_status(root)
    except Exception as exc:  # pragma: no cover - defensive around optional runtime state
        findings.append(_finding("runner-status-failed", "warning", f"could not inspect runner status: {exc}", category="runner"))
        return
    if status.get("status") == "stale":
        findings.append(_finding(
            "stale-runner-lock",
            "failure",
            "runner lock exists but its process is not running",
            category="runner",
            path=str(status.get("lockPath")),
            detail=status,
        ))

    paths = runner_paths(root)
    state, state_error = _read_json_object(paths["statePath"])
    if state_error and paths["statePath"].exists():
        findings.append(_finding(
            "invalid-runner-state",
            "failure",
            f"runner state is invalid: {state_error}",
            category="runner",
            path=str(paths["statePath"]),
        ))
    if state:
        heartbeat = _parse_time(state.get("heartbeatAt"))
        if state.get("running") and heartbeat and now - heartbeat > stale_after:
            findings.append(_finding(
                "stale-runner-heartbeat",
                "failure",
                f"runner heartbeat is older than {stale_after}",
                category="runner",
                path=str(paths["statePath"]),
                detail={"heartbeatAt": state.get("heartbeatAt"), "ageSeconds": int((now - heartbeat).total_seconds())},
            ))

    active_dir = paths["activeDir"]
    if active_dir.is_dir():
        for snapshot_path in sorted(active_dir.glob("*.json")):
            snapshot, snapshot_error = _read_json_object(snapshot_path)
            if snapshot_error:
                findings.append(_finding(
                    "invalid-active-run-snapshot",
                    "failure",
                    f"active run snapshot is invalid: {snapshot_error}",
                    category="runner",
                    path=str(snapshot_path),
                ))
                continue
            if not snapshot:
                continue
            started_at = _parse_time(snapshot.get("startedAt"))
            if started_at and now - started_at > stale_after:
                findings.append(_finding(
                    "stale-active-run-snapshot",
                    "failure",
                    f"active run snapshot is older than {stale_after}",
                    category="runner",
                    run_id=str(snapshot.get("runId") or snapshot_path.stem),
                    ref=str(snapshot.get("bead")) if snapshot.get("bead") else None,
                    path=str(snapshot_path),
                    detail={"startedAt": snapshot.get("startedAt"), "ageSeconds": int((now - started_at).total_seconds())},
                ))


def _append_blocked_bead_findings(findings: List[Dict[str, Any]], *, beads_runner: BeadsRunner) -> None:
    code, data, err = beads_runner(["blocked"])
    if code != 0:
        message = str(err or "").strip()
        if "unknown command" in message.lower():
            return
        findings.append(_finding("blocked-beads-check-failed", "warning", f"could not inspect blocked beads: {message or code}", category="beads"))
        return
    if not isinstance(data, list):
        return
    for bead in data:
        if not isinstance(bead, dict):
            continue
        dependencies = bead.get("dependencies") or bead.get("blockers") or []
        human = bead.get("human") or bead.get("humanActions") or []
        if str(bead.get("status") or "") == "blocked" and not dependencies and not human:
            findings.append(_finding(
                "blocked-bead-without-visible-blocker",
                "failure",
                f"blocked bead {bead.get('id')} has no visible dependency or human blocker",
                category="beads",
                ref=str(bead.get("id") or ""),
                detail={"bead": bead},
            ))


def work_health_report(
    *,
    root: Path | str | None = None,
    runs_dir: Path | str | None = None,
    ref_resolver: RefResolver = default_ref_resolver,
    status_runner: StatusRunner = default_status_runner,
    beads_runner: BeadsRunner = default_beads_runner,
    now: datetime | None = None,
    stale_after_hours: int | float = 24,
    strict_checkout: bool = False,
    include_beads: bool = True,
) -> Dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else Path.cwd()
    run_root = Path(runs_dir).expanduser() if runs_dir is not None else default_runs_dir()
    timestamp = now or utc_now()
    stale_after = timedelta(hours=float(stale_after_hours))
    findings: List[Dict[str, Any]] = []
    seen_worktrees: set[str] = set()

    _append_current_checkout_finding(findings, root=repo_root, status_runner=status_runner, strict=strict_checkout)
    _append_known_epic_worktree_findings(findings, root=repo_root, status_runner=status_runner, seen_paths=seen_worktrees)
    _append_runner_findings(findings, root=repo_root, now=timestamp, stale_after=stale_after)

    bundles = iter_run_bundles(run_root)
    for bundle in bundles:
        findings.extend(scan_run_bundle_health(
            bundle,
            ref_resolver=ref_resolver,
            status_runner=status_runner,
            now=timestamp,
            stale_after=stale_after,
            seen_worktree_paths=seen_worktrees,
        ))

    if include_beads:
        _append_blocked_bead_findings(findings, beads_runner=beads_runner)

    counts = {"failure": 0, "warning": 0, "info": 0}
    for finding in findings:
        severity = str(finding.get("severity") or "info")
        counts[severity] = counts.get(severity, 0) + 1
    summary = {
        "runCount": len(bundles),
        "failureCount": counts.get("failure", 0),
        "warningCount": counts.get("warning", 0),
        "infoCount": counts.get("info", 0),
        "runsDir": str(run_root),
        "root": str(repo_root),
        "staleAfterHours": float(stale_after_hours),
    }
    return {
        "schemaVersion": 1,
        "passed": summary["failureCount"] == 0,
        "summary": summary,
        "findings": sorted(findings, key=lambda item: (str(item.get("severity")), str(item.get("id")), str(item.get("run", "")), str(item.get("ref", "")))),
    }


__all__ = [
    "work_health_report",
    "scan_run_bundle_health",
    "iter_run_bundles",
    "check_status_passed",
    "default_ref_resolver",
]
