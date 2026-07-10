from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

StatusRunner = Callable[[str], Tuple[int, str, str]]
GitRunner = Callable[[List[str], str], Tuple[int, str, str]]


def slugify(value: str, *, max_len: int = 64) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:max_len].strip("-") or "epic"


def epic_worktree_spec(epic_id: str, title: str | None = None, *, repo_root: Path | str | None = None) -> Dict[str, Any]:
    if not epic_id or not isinstance(epic_id, str):
        raise ValueError("epic_id is required")
    root = Path(repo_root).expanduser() if repo_root is not None else Path.cwd()
    epic_slug = slugify(epic_id)
    title_slug = slugify(title or "") if title else ""
    suffix = f"-{title_slug}" if title_slug and title_slug != epic_slug else ""
    name = f"{epic_slug}{suffix}"
    return {
        "schemaVersion": 1,
        "policy": "epic-worktree",
        "epicId": epic_id,
        "branch": f"epic/{name}",
        "path": str(root / ".worktrees" / "epic" / name),
        "requiresCreationApproval": True,
    }


def parse_worktree_porcelain(text: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                entries.append(current)
            current = {"path": value}
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key == "HEAD":
            current["head"] = value
    if current:
        entries.append(current)
    return entries


def list_git_worktrees(*, repo_root: Path | str | None = None) -> List[Dict[str, str]]:
    cwd = Path(repo_root).expanduser() if repo_root is not None else Path.cwd()
    proc = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return []
    return parse_worktree_porcelain(proc.stdout)


def default_status_runner(path: str) -> Tuple[int, str, str]:
    proc = subprocess.run(["git", "-C", path, "status", "--short"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout, proc.stderr


def default_git_runner(args: List[str], cwd: str) -> Tuple[int, str, str]:
    proc = subprocess.run(["git", "-C", cwd, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout, proc.stderr


def _safe_write_paths(write_set: List[str]) -> List[str] | None:
    paths: List[str] = []
    for item in write_set:
        if not isinstance(item, str) or not item:
            return None
        normalized = os.path.normpath(item)
        if os.path.isabs(item) or normalized == ".." or normalized.startswith(f"..{os.sep}"):
            return None
        paths.append(normalized)
    return paths or None


def _dirty_paths(status: str) -> List[str]:
    paths: List[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[-1]
        if path:
            paths.append(os.path.normpath(path))
    return paths


def _is_scoped_path(path: str, write_paths: List[str]) -> bool:
    return any(path == allowed or path.startswith(f"{allowed}{os.sep}") for allowed in write_paths)


def checkpoint_epic_worktree(
    worktree: Dict[str, Any],
    *,
    bead_id: str,
    write_set: List[str],
    git_runner: GitRunner = default_git_runner,
) -> Dict[str, Any]:
    """Create one local, scoped continuation checkpoint in an approved epic worktree."""
    continuation = worktree.get("continuation") if isinstance(worktree.get("continuation"), dict) else {}
    path = str(worktree.get("path") or "")
    predecessor = continuation.get("predecessor")
    approval_ref = continuation.get("approvalRef")
    write_paths = _safe_write_paths(write_set)
    if worktree.get("status") != "checkpoint-required" or not path or not isinstance(predecessor, str) or not predecessor or not isinstance(approval_ref, str) or not approval_ref:
        return {"ok": False, "reason": "worktree is not an approved checkpoint continuation"}
    if not write_paths:
        return {"ok": False, "reason": "unsafe or empty continuation writeSet"}

    status_code, dirty_status, status_err = git_runner(["status", "--short", "--untracked-files=all"], path)
    if status_code != 0:
        return {"ok": False, "reason": f"could not inspect worktree status: {status_err or status_code}"}
    dirty_paths = _dirty_paths(dirty_status)
    if not dirty_paths or any(not _is_scoped_path(item, write_paths) for item in dirty_paths):
        return {"ok": False, "reason": "dirty worktree changes are outside the approved continuation writeSet", "dirtyStatus": dirty_status}

    baseline_code, baseline_out, baseline_err = git_runner(["rev-parse", "HEAD"], path)
    if baseline_code != 0:
        return {"ok": False, "reason": f"could not read checkpoint baseline: {baseline_err or baseline_code}"}
    baseline_sha = baseline_out.strip()
    add_code, _add_out, add_err = git_runner(["add", "--", *write_paths], path)
    if add_code != 0:
        return {"ok": False, "reason": f"could not stage continuation checkpoint: {add_err or add_code}", "baselineSha": baseline_sha}
    diff_code, _diff_out, diff_err = git_runner(["diff", "--cached", "--quiet"], path)
    if diff_code == 0:
        return {"ok": False, "reason": "continuation checkpoint has no staged changes", "baselineSha": baseline_sha}
    if diff_code != 1:
        return {"ok": False, "reason": f"could not inspect staged checkpoint: {diff_err or diff_code}", "baselineSha": baseline_sha}
    stat_code, diff_stat, stat_err = git_runner(["diff", "--cached", "--stat"], path)
    if stat_code != 0:
        return {"ok": False, "reason": f"could not capture staged checkpoint diff: {stat_err or stat_code}", "baselineSha": baseline_sha}
    message = f"runner checkpoint {predecessor} before {bead_id}"
    commit_code, _commit_out, commit_err = git_runner(["commit", "-m", message], path)
    if commit_code != 0:
        return {"ok": False, "reason": f"could not create local continuation checkpoint: {commit_err or commit_code}", "baselineSha": baseline_sha}
    head_code, head_out, head_err = git_runner(["rev-parse", "HEAD"], path)
    if head_code != 0:
        return {"ok": False, "reason": f"could not read checkpoint SHA: {head_err or head_code}", "baselineSha": baseline_sha}
    after_code, status_after, after_err = git_runner(["status", "--short", "--untracked-files=all"], path)
    if after_code != 0:
        return {"ok": False, "reason": f"could not inspect checkpoint status: {after_err or after_code}", "baselineSha": baseline_sha}
    return {
        "ok": True,
        "path": path,
        "branch": worktree.get("branch"),
        "baselineSha": baseline_sha,
        "checkpointSha": head_out.strip(),
        "statusBefore": dirty_status,
        "statusAfter": status_after,
        "diffStat": diff_stat,
        "writeSet": write_paths,
        "predecessor": predecessor,
        "approvalRef": approval_ref,
        "message": message,
    }


def resolve_epic_worktree(
    spec: Dict[str, Any],
    *,
    worktrees: List[Dict[str, str]] | None = None,
    status_runner: StatusRunner = default_status_runner,
    continuation: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    expected_path = str(Path(str(spec.get("path"))).expanduser())
    expected_branch = str(spec.get("branch") or "")
    entries = worktrees if worktrees is not None else list_git_worktrees(repo_root=Path.cwd())
    match = next((item for item in entries if str(Path(item.get("path", "")).expanduser()) == expected_path), None)
    base = {"schemaVersion": 1, **spec, "dispatchable": False}
    if not match:
        return {**base, "status": "needs-approval", "reason": "epic worktree does not exist; explicit approval is required before creating it"}
    branch = str(match.get("branch") or "")
    if branch in {"main", "master"}:
        return {**base, "status": "blocked", "reason": f"epic worktree is on protected branch {branch}", "actualBranch": branch}
    if branch and branch != expected_branch:
        return {**base, "status": "blocked", "reason": f"epic worktree branch {branch} does not match expected {expected_branch}", "actualBranch": branch}
    code, out, err = status_runner(expected_path)
    if code != 0:
        return {**base, "status": "blocked", "reason": f"could not inspect worktree status: {err or code}", "actualBranch": branch}
    if out.strip():
        if isinstance(continuation, dict) and continuation.get("mode") == "checkpoint" and isinstance(continuation.get("predecessor"), str) and continuation.get("predecessor") and isinstance(continuation.get("approvalRef"), str) and continuation.get("approvalRef"):
            return {
                **base,
                "status": "checkpoint-required",
                "reason": "epic worktree is dirty and requires its approved continuation checkpoint",
                "actualBranch": branch,
                "dirtyStatus": out,
                "continuation": dict(continuation),
            }
        return {**base, "status": "blocked", "reason": "epic worktree is dirty", "actualBranch": branch, "dirtyStatus": out}
    return {**base, "status": "ready", "dispatchable": True, "reason": "epic worktree exists on expected clean branch", "actualBranch": branch}


def worktree_snapshot_for_bead(bead: Dict[str, Any], validation: Dict[str, Any], *, repo_root: Path | str | None = None) -> Dict[str, Any]:
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    policy = normalized.get("worktreePolicy") or "none"
    if normalized.get("action") != "implement" or policy == "none":
        root = Path(repo_root).expanduser() if repo_root is not None else Path.cwd()
        return {"schemaVersion": 1, "policy": "none", "status": "ready", "dispatchable": True, "path": str(root)}
    epic_id = normalized.get("epicId")
    if policy != "epic-worktree" or not isinstance(epic_id, str) or not epic_id:
        return {"schemaVersion": 1, "policy": policy, "status": "blocked", "dispatchable": False, "reason": "implementation work requires a valid epic-worktree policy and epicId"}
    title = str(bead.get("epicTitle") or bead.get("parentTitle") or "")
    spec = epic_worktree_spec(epic_id, title, repo_root=repo_root)
    continuation = normalized.get("continuation") if isinstance(normalized.get("continuation"), dict) else None
    return resolve_epic_worktree(spec, continuation=continuation)


def write_sets_overlap(first: List[str], second: List[str]) -> List[str]:
    left = {os.path.normpath(item) for item in first if item}
    right = {os.path.normpath(item) for item in second if item}
    return sorted(left.intersection(right))


def write_conflict_for(
    bead: Dict[str, Any],
    validation: Dict[str, Any],
    active: List[Dict[str, Any]],
) -> Dict[str, Any] | None:
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    if normalized.get("action") != "implement":
        return None
    epic_id = normalized.get("epicId")
    write_set = normalized.get("writeSet") or []
    for item in active:
        if item.get("epicId") != epic_id:
            continue
        overlap = write_sets_overlap(write_set, item.get("writeSet") or [])
        if overlap:
            return {"blockedBy": item.get("bead"), "overlap": overlap, "epicId": epic_id}
    return None


__all__ = [
    "epic_worktree_spec",
    "resolve_epic_worktree",
    "checkpoint_epic_worktree",
    "parse_worktree_porcelain",
    "list_git_worktrees",
    "worktree_snapshot_for_bead",
    "write_sets_overlap",
    "write_conflict_for",
]
