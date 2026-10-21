from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

StatusRunner = Callable[[str], Tuple[int, str, str]]


def slugify(value: str, *, max_len: int = 64) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
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


def resolve_epic_worktree(
    spec: Dict[str, Any],
    *,
    worktrees: List[Dict[str, str]] | None = None,
    status_runner: StatusRunner = default_status_runner,
    creation_approval: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    expected_path = str(Path(str(spec.get("path"))).expanduser())
    expected_branch = str(spec.get("branch") or "")
    entries = worktrees if worktrees is not None else list_git_worktrees(repo_root=Path.cwd())
    match = next((item for item in entries if str(Path(item.get("path", "")).expanduser()) == expected_path), None)
    base = {"schemaVersion": 1, **spec, "dispatchable": False}
    if not match:
        approval_ref = creation_approval.get("decisionBead") if isinstance(creation_approval, dict) and creation_approval.get("resolver") == {"kind": "human-ui"} else None
        if isinstance(approval_ref, str) and approval_ref.strip():
            return {
                **base,
                "status": "needs-creation",
                "requiresCreationApproval": False,
                "creationAuthorized": True,
                "approvalRef": approval_ref.strip(),
                "reason": "initial implementation approval authorizes exact worktree creation without another approval; deterministic creation checks remain required",
            }
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
        return {**base, "status": "blocked", "reason": "epic worktree is dirty", "actualBranch": branch, "dirtyStatus": out}
    return {**base, "status": "ready", "dispatchable": True, "reason": "epic worktree exists on expected clean branch", "actualBranch": branch}


def worktree_snapshot_for_bead(
    bead: Dict[str, Any],
    validation: Dict[str, Any],
    *,
    repo_root: Path | str | None = None,
    worktrees: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
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
    authority = normalized.get("authority") if isinstance(normalized.get("authority"), dict) else None
    return resolve_epic_worktree(
        spec,
        worktrees=worktrees,
        creation_approval=authority if authority and authority.get("status") == "active" else None,
    )


def _isolation_git(cwd: Path, *args: str, lease_fds: tuple[int, ...] = ()) -> subprocess.CompletedProcess[str]:
    # Do not set core.worktree/--work-tree here: Git's nested checkout must use
    # the new worktree, never inherit the source checkout as its write target.
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
         "-c", "commit.gpgSign=false", "-c", "submodule.recurse=false", "-C", str(cwd), *args],
        capture_output=True, text=True, check=False, pass_fds=lease_fds,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    )


def _isolated_worktrees(cwd: Path) -> list[dict[str, str]]:
    result = _isolation_git(cwd, "worktree", "list", "--porcelain", "-z")
    if result.returncode:
        raise ValueError("native worktree inventory is unavailable")
    records: list[dict[str, str]] = []
    record: dict[str, str] = {}
    for field in result.stdout.split("\0"):
        if not field:
            if record:
                records.append(record)
                record = {}
            continue
        key, _, value = field.partition(" ")
        if key == "worktree":
            record["path"] = value
        elif key in {"HEAD", "branch"}:
            record[key] = value.removeprefix("refs/heads/") if key == "branch" else value
    if record:
        records.append(record)
    return records


class WorktreeCreationAdapter:
    """Create one private task checkout using native Git, without source edits.

    Git binary/system/global configuration are trusted like the existing local
    integration adapter. Project command-valued configuration is refused; hooks
    are disabled. No prune, reset, force, cleanup, or branch adoption occurs.
    """
    kind = "git-worktree-create"

    def __init__(self, repository: Path | str, bead: str, *, decision_refs: list[str] | None = None):
        from .authority import _identifier, _strings, fingerprint, repository_identity
        from .work_lifecycle import checkout_identity

        self.checkout = checkout_identity(str(repository))
        self.repository = repository_identity(str(self.checkout))
        self.bead = _identifier(bead)
        self.decisions = _strings(decision_refs or [], "decision refs", empty=True)
        self.managed_root = Path.home() / ".pi" / "runtime" / "worktrees"
        name = f"{slugify(bead)}-{fingerprint([self.repository, bead])[7:19]}"
        self.target = self.managed_root / fingerprint(self.repository)[7:31] / name
        self.branch = f"work/{name}"

    def _paths(self) -> None:
        for path in (self.target, *self.target.parents):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise ValueError("managed checkout path is unsafe")
        for path in (self.managed_root, self.target.parent):
            if path.exists():
                info = path.stat()
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                    raise ValueError("managed worktree directories must be owner-private")

    def _source(self) -> str:
        from .authority import repository_identity
        from .integration import _has_command_config

        if repository_identity(str(self.checkout)) != self.repository or _has_command_config(self.checkout) is not False:
            raise ValueError("source repository or Git command configuration changed")
        explicit = _isolation_git(self.checkout, "config", "--get", "core.worktree")
        if explicit.returncode != 1:
            raise ValueError("explicit core.worktree configuration is unsupported for automatic isolation")
        head = _isolation_git(self.checkout, "rev-parse", "--verify", "HEAD^{commit}")
        if head.returncode or not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", head.stdout.strip()):
            raise ValueError("source commit is unavailable")
        return head.stdout.strip()

    def resolve(self) -> dict[str, Any]:
        self._paths()
        head = self._source()
        existing = _isolated_worktrees(self.checkout)
        branch = _isolation_git(self.checkout, "show-ref", "--verify", "--quiet", f"refs/heads/{self.branch}")
        if (self.target.exists() or branch.returncode != 1
                or any(Path(item["path"]).resolve() == self.target for item in existing)):
            raise ValueError("worktree path, branch or registration already exists; preserve and reconcile")
        target = str(self.target)
        return {
            "schemaVersion": 1, "adapter": self.kind, "repository": self.repository, "bead": self.bead,
            "effects": ["worktree-create"], "decisionRefs": self.decisions,
            "target": {"identity": target, "repository": self.repository, "verified": True,
                       "resources": [f"git-ref:{self.repository}:refs/heads/{self.branch}", f"path:{target}"]},
            "source": {"identity": head, "rule": "current-checked-out-commit"},
            "facts": {"checkout": target, "branch": self.branch, "sourceCheckout": str(self.checkout), "base": head},
            "preconditions": {key: True for key in ("identity", "platform", "effectClosure", "verification", "recovery")},
            "verification": [f"git-object:{head}", "native:unoccupied-worktree-path-and-branch", "native:safe-git-config"],
            "recovery": "Observe exact registered checkout/branch/commit; preserve partial state without cleanup or force",
        }

    def execute(self, action: dict[str, Any], *, lease_fds: tuple[int, ...]) -> None:
        from .authority import fingerprint

        if fingerprint(self.resolve()) != fingerprint(action):
            raise ValueError("native worktree facts changed before creation")
        self.managed_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.target.parent.mkdir(exist_ok=True, mode=0o700)
        self._paths()
        result = _isolation_git(self.checkout, "worktree", "add", "--quiet", "--no-track", "-b", self.branch,
                                "--", str(self.target), action["source"]["identity"], lease_fds=lease_fds)
        if result.returncode:
            raise ValueError("native worktree creation needs observation")

    def observe(self, action: dict[str, Any], *, attempted: bool) -> dict[str, Any]:
        from .authority import repository_identity
        from .integration import _has_command_config

        self._paths()
        self._source()
        facts = action["facts"]
        if (facts["checkout"] != str(self.target) or facts["branch"] != self.branch
                or action["repository"] != self.repository or action["bead"] != self.bead):
            raise ValueError("worktree observation is bound to different intent")
        matching = [item for item in _isolated_worktrees(self.checkout)
                    if Path(item["path"]).resolve() == self.target]
        presence = _isolation_git(self.checkout, "show-ref", "--verify", "--quiet", f"refs/heads/{self.branch}")
        branch = (_isolation_git(self.checkout, "rev-parse", "--verify", f"refs/heads/{self.branch}")
                  if presence.returncode == 0 else presence)
        status = "uncertain"
        if not matching and not self.target.exists() and presence.returncode == 1:
            # Resource FDs survive in the native writer. Holding those leases
            # again proves no cooperating local writer remains in flight.
            status = "not-applied"
        elif (len(matching) == 1 and self.target.is_dir() and matching[0].get("branch") == self.branch
              and matching[0].get("HEAD") == action["source"]["identity"] and branch.returncode == 0
              and branch.stdout.strip() == action["source"]["identity"]
              and repository_identity(str(self.target)) == self.repository
              and _has_command_config(self.target) is False):
            clean = _isolation_git(self.target, "status", "--porcelain=v1", "--untracked-files=all")
            if clean.returncode == 0 and not clean.stdout.strip():
                status = "applied"
        return {"status": status, "targetIdentity": action["target"]["identity"],
                "sourceIdentity": action["source"]["identity"],
                "evidenceRefs": [f"git-worktree:{self.target}", f"git-ref:{self.branch}", f"git-object:{action['source']['identity']}"]}


__all__ = [
    "epic_worktree_spec",
    "resolve_epic_worktree",
    "parse_worktree_porcelain",
    "list_git_worktrees",
    "worktree_snapshot_for_bead",
    "WorktreeCreationAdapter",
]
