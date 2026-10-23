"""Recoverable work-attempt ownership and transition journal.

No session history is rewritten. The Pi adapter stages/launches the one child
identified here. Beads/quality attachment is an idempotent host callback. Lock
order: lifecycle journal -> quality -> authority -> Beads; never the reverse.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Iterator
import uuid

from .authority import _identifier, _strings, _text, fingerprint

Authorize = Callable[[dict[str, Any]], bool]
Attach = Callable[[str, str], Any]
_MAX_PATHS = 4000
_MAX_FILE = 64 * 1024 * 1024
_PREEXEC_FAILURES = {"stage-failed", "launch-request-failed", "shutdown-request-failed", "shutdown-nonzero", "exec-failed"}


class WorkAuthorityUnavailable(ValueError):
    """A direct workflow effect is outside current assignment authority."""


def checkout_identity(checkout: str) -> Path:
    from .runtime_paths import _git_context

    root = Path(checkout).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("checkout is not a directory")
    context = _git_context(root)
    return context[1] if context else root


def workspace_snapshot(checkout: str) -> dict[str, Any]:
    root = checkout_identity(checkout)
    def guarded_path(name: str) -> Path:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe workspace path")
        current = root
        for part in relative.parts[:-1]:
            current /= part
            if current.is_symlink():
                raise ValueError("workspace path traverses a symlink")
        return root / relative
    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
            capture_output=True, check=False,
            env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
        )
    head_result = git("rev-parse", "HEAD")
    head = head_result.stdout.decode().strip() if head_result.returncode == 0 else None
    branch = index_fingerprint = status_fingerprint = None
    if head is not None:
        symbolic = git("symbolic-ref", "--quiet", "HEAD")
        status_result = git("status", "--porcelain=v2", "--untracked-files=normal", "-z")
        index = git("ls-files", "--stage", "-v", "-z")
        if symbolic.returncode not in {0, 1} or index.returncode or status_result.returncode:
            raise ValueError("workspace branch or index inspection failed")
        branch = symbolic.stdout.decode().strip() if symbolic.returncode == 0 else None
        index_fingerprint = hashlib.sha256(index.stdout).hexdigest()
        status_fingerprint = hashlib.sha256(status_result.stdout).hexdigest()
        tracked = git("diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--name-only", "-z", "HEAD")
        untracked = git("ls-files", "--others", "--exclude-standard", "-z")
        if tracked.returncode or untracked.returncode:
            raise ValueError("workspace inspection failed")
        paths = {os.fsdecode(x) for x in (tracked.stdout + untracked.stdout).split(b"\0") if x}
        # Git may hide material working files behind assume-unchanged or sparse
        # flags. Hash those files too, without expanding absent sparse paths.
        for entry in index.stdout.split(b"\0"):
            if entry[:1].islower() or entry.startswith(b"S "):
                name = os.fsdecode(entry.partition(b"\t")[2])
                path = guarded_path(name)
                if path.is_symlink() or path.exists():
                    paths.add(name)
    else:
        paths = {str(path.relative_to(root)) for path in root.rglob("*")
                 if path.is_symlink() or path.is_file()}
    if len(paths) > _MAX_PATHS:
        raise ValueError("workspace snapshot path limit exceeded")
    changed = {}
    for name in sorted(paths):
        path = guarded_path(name)
        if path.is_symlink():
            value = "symlink:" + os.readlink(path)
        elif not path.exists():
            value = "deleted"
        else:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_FILE:
                raise ValueError("unsupported changed workspace entry")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
            value = f"{stat.S_IMODE(info.st_mode):o}:sha256:{digest.hexdigest()}"
        changed[name] = value
    return {"checkout": str(root), "head": head, "branch": branch, "indexFingerprint": index_fingerprint,
            "statusFingerprint": status_fingerprint, "changed": changed}


class LifecycleStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    @contextmanager
    def locked(self) -> Iterator[dict[str, Any]]:
        if any(path.is_symlink() for path in (self.root, *self.root.parents)):
            raise ValueError("journal path must not contain symlinks")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.root.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("journal directory must be owner-private")
        fd = os.open(self.root / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            path = self.root / "journal.json"
            if path.is_symlink():
                raise ValueError("journal must not be a symlink")
            if path.exists():
                info = path.stat()
                if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
                        or not stat.S_ISREG(info.st_mode) or info.st_size > 8 * 1024 * 1024):
                    raise ValueError("invalid private journal")
                envelope = json.loads(path.read_text())
                state = envelope["state"]
                if envelope["fingerprint"] != fingerprint(state):
                    raise ValueError("journal fingerprint mismatch")
                if (set(state) != {"schemaVersion", "owners", "checkpoints", "transitions"}
                        or state["schemaVersion"] != 1
                        or any(not isinstance(state[key], dict) for key in ("owners", "checkpoints", "transitions"))):
                    raise ValueError("invalid journal schema")
            else:
                state = {"schemaVersion": 1, "owners": {}, "checkpoints": {}, "transitions": {}}
            yield state
        finally:
            os.close(fd)

    def _write(self, state: dict[str, Any]) -> None:
        encoded = json.dumps({"state": state, "fingerprint": fingerprint(state)}, sort_keys=True).encode() + b"\n"
        if len(encoded) > 8 * 1024 * 1024:
            raise ValueError("journal capacity exceeded")
        fd, name = tempfile.mkstemp(prefix=".journal-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.root / "journal.json")
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def claim(self, bead: str, session: str, checkout: str) -> None:
        _identifier(bead)
        _identifier(session)
        checkout = workspace_snapshot(checkout)["checkout"]
        with self.locked() as state:
            owner = state["owners"].get(bead)
            if owner is not None and (owner["session"] != session or owner["phase"] != "active"
                                      or owner["checkout"] != checkout):
                raise ValueError("execution ownership conflict")
            if any(key != bead and (value["session"] == session or
                                    (value["checkout"] == checkout and value["phase"] != "completed"))
                   for key, value in state["owners"].items()):
                raise ValueError("session or checkout ownership cannot be shared or relabeled")
            if owner is None:
                state["owners"][bead] = {"session": session, "checkout": checkout, "phase": "active"}
                self._write(state)

    def owner(self, bead: str) -> dict[str, Any] | None:
        with self.locked() as state:
            return copy.deepcopy(state["owners"].get(bead))

    def bind_assignment(self, bead: str, session: str, assignment_ref: str) -> None:
        with self.locked() as state:
            owner = state["owners"].get(bead)
            if not owner or owner["session"] != session or owner["phase"] != "active":
                raise ValueError("assignment ownership conflict")
            if owner.get("assignmentRef") not in {None, assignment_ref}:
                raise ValueError("execution assignment is immutable")
            if owner.get("assignmentRef") is None:
                owner["assignmentRef"] = assignment_ref
                self._write(state)

    def release_completed(self, bead: str, session: str) -> None:
        """Called only after verified successful closeout, never for suspension."""
        with self.locked() as state:
            owner = state["owners"].get(bead)
            if owner is None:
                return
            if owner["session"] != session or owner["phase"] not in {"active", "completed"}:
                raise ValueError("closeout ownership conflict")
            if any(tx["sourceSession"] == session and tx["state"] not in {"attached", "cancelled"}
                   for tx in state["transitions"].values()):
                raise ValueError("pending transition must be settled before completed checkout release")
            if owner["phase"] != "completed":
                owner["phase"] = "completed"
                self._write(state)

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        with self.locked() as state:
            return copy.deepcopy(state["checkpoints"][checkpoint_id])

    def checkpoint(self, bead: str, session: str, progress: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(progress, dict) or set(progress) != {
            "objective", "decisions", "completed", "next", "blockers", "verification",
            "ownedPaths", "artifactRefs", "assignmentRef",
        }:
            raise ValueError("checkpoint progress fields are invalid")
        _text(progress["objective"], "checkpoint objective")
        _text(progress["assignmentRef"], "assignment reference")
        for key in ("decisions", "completed", "next", "blockers", "verification", "ownedPaths", "artifactRefs"):
            _strings(progress[key], key, empty=True)
        for path in progress["ownedPaths"]:
            if Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("owned path must be relative")
        with self.locked() as state:
            owner = state["owners"].get(bead)
            if not owner or owner["session"] != session or owner["phase"] != "active":
                raise ValueError("checkpoint ownership conflict")
            if any(tx["sourceSession"] == session and tx["state"] not in {"attached", "cancelled"}
                   for tx in state["transitions"].values()):
                raise ValueError("transition already pending; recover or cancel first")
            cp = {"id": uuid.uuid4().hex, "bead": bead, "session": session,
                  "previousCheckpointRef": owner.get("checkpointRef"),
                  "progress": copy.deepcopy(progress), "workspace": workspace_snapshot(owner["checkout"])}
            state["checkpoints"][cp["id"]] = cp
            owner["checkpointRef"] = cp["id"]
            self._write(state)
            return copy.deepcopy(cp)

    def latest_checkpoint(self, bead: str) -> dict[str, Any] | None:
        with self.locked() as state:
            matches = [cp for cp in state["checkpoints"].values() if cp["bead"] == bead]
            # Checkpoint dict order cannot establish time after sorted JSON writes.
            owner = state["owners"].get(bead, {})
            ref = owner.get("checkpointRef")
            if ref:
                return copy.deepcopy(state["checkpoints"][ref])
            return copy.deepcopy(matches[-1]) if len(matches) == 1 else None

    def prepare(self, *, source_session: str, checkpoint_ref: str, target_bead: str,
                target_checkout: str, target_status: str, blockers: list[str], mode: str,
                runtime_ready: bool, authorize: Authorize, source_session_file: str | None = None,
                source_quality_directory: str | None = None,
                isolation: dict[str, Any] | None = None) -> dict[str, Any]:
        if runtime_ready is not True:
            raise ValueError("runtime launch capability is unavailable; host continuation required")
        _identifier(target_bead)
        if target_status not in {"open", "in_progress"} or blockers:
            raise ValueError("target is not actionable")
        with self.locked() as state:
            cp = state["checkpoints"].get(checkpoint_ref)
            if cp is None or cp["session"] != source_session:
                raise ValueError("checkpoint ownership mismatch")
            source_bead = cp["bead"]
            if mode not in {"resume", "switch", "next"} or (mode == "resume" and source_bead != target_bead):
                raise ValueError("invalid transition mode")
            checkout = (str(Path(target_checkout).resolve(strict=False)) if isolation is not None
                        else str(checkout_identity(target_checkout)))
            identity = {"sourceSession": source_session, "sourceBead": source_bead,
                        "checkpointRef": checkpoint_ref, "targetBead": target_bead,
                        "targetCheckout": checkout, "mode": mode,
                        "assignmentRef": cp["progress"]["assignmentRef"],
                        "sourceSessionFile": source_session_file}
            if source_quality_directory is not None:
                if not isinstance(source_quality_directory, str) or not Path(source_quality_directory).is_absolute():
                    raise ValueError("source quality directory must be an absolute native binding")
                identity["sourceQualityDirectory"] = source_quality_directory
            if isolation is not None:
                from .authority import repository_identity
                if (not isinstance(isolation, dict) or set(isolation) != {"receipt", "repository", "source", "action"}
                        or isolation["receipt"] is not None
                        or isolation["repository"] != repository_identity(cp["workspace"]["checkout"])
                        or isolation["source"] != cp["workspace"]["head"] or source_bead == target_bead
                        or isolation["action"]["facts"]["sourceCheckout"] != cp["workspace"]["checkout"]):
                    raise ValueError("invalid native isolation reservation")
                identity["isolation"] = copy.deepcopy(isolation)
            tx_id = fingerprint(identity).removeprefix("sha256:")[:32]
            previous = state["transitions"].get(tx_id)
            if previous is not None:
                return copy.deepcopy(previous)
            source = state["owners"].get(source_bead)
            target = state["owners"].get(target_bead)
            if not source or source["session"] != source_session or source["phase"] != "active":
                raise ValueError("source ownership conflict")
            if any(tx["sourceSession"] == source_session and tx["state"] not in {"attached", "cancelled"}
                   for tx in state["transitions"].values()):
                raise ValueError("source ownership has a pending transition")
            if target_bead != source_bead and target is not None and target["phase"] != "paused":
                raise ValueError("target ownership conflict")
            if any(key not in {source_bead, target_bead} and value["checkout"] == checkout
                   for key, value in state["owners"].items()):
                raise ValueError("target checkout ownership conflict")
            if target is not None and target["checkout"] != checkout:
                raise ValueError("target checkout identity changed")
            if isolation is not None and (target is not None or Path(checkout).exists()):
                raise ValueError("native isolation requires an unowned absent checkout")
            source_snapshot = workspace_snapshot(source["checkout"])
            if source_snapshot != cp["workspace"]:
                raise ValueError("source workspace changed since checkpoint")
            if target_bead != source_bead and checkout == source["checkout"]:
                raise ValueError("cross-Bead switching requires checkout isolation")
            tx = {"id": tx_id, **identity, "state": "isolating" if isolation is not None else "prepared",
                  "childSession": str(uuid.uuid4()), "childSessionFile": None, "attempts": 0,
                  "targetBefore": copy.deepcopy(target),
                  "targetWorkspace": None if isolation is not None else workspace_snapshot(checkout)}
            tx["progressKey"] = fingerprint({"source": source_bead, "target": target_bead,
                                              "sourceWorkspace": source_snapshot,
                                              "targetWorkspace": tx["targetWorkspace"],
                                              "progress": cp["progress"]})
            if sum(previous.get("progressKey") == tx["progressKey"] and previous["state"] == "attached"
                   for previous in state["transitions"].values()) >= 3:
                raise ValueError("unchanged progress continuation limit reached; inspect the blocker before retry")
            if authorize(copy.deepcopy(tx)) is not True:
                raise ValueError("transition authority is unavailable")
            if target_bead != source_bead:
                state["owners"][target_bead] = {"session": tx["childSession"], "checkout": checkout,
                                                 "phase": "reserved", "transition": tx_id}
            state["transitions"][tx_id] = tx
            state["owners"][source_bead]["checkpointRef"] = checkpoint_ref
            self._write(state)
            return copy.deepcopy(tx)

    def bind_isolation_receipt(self, transition_id: str, receipt: dict[str, Any] | None = None, *,
                               publish: Callable[[], dict[str, Any] | None] | None = None) -> dict[str, Any]:
        if (receipt is None) == (publish is None):
            raise ValueError("provide one receipt or trusted publication callback")
        with self.locked() as state:
            tx = state["transitions"][transition_id]
            if tx["state"] != "isolating" or tx.get("cancelRequested"):
                raise ValueError("native isolation receipt does not match reserved intent")
            if publish is not None:
                if tx["isolation"]["receipt"] is not None:
                    return copy.deepcopy(tx)
                # Cancellation holds this same lock. It cannot classify an
                # unpublished receipt as unissued while publication is active.
                receipt = publish()
                if receipt is None:
                    return copy.deepcopy(tx)
            if (receipt["assignment"] != tx["assignmentRef"]
                    or fingerprint(receipt["action"]) != fingerprint(tx["isolation"]["action"])):
                raise ValueError("native isolation receipt does not match reserved intent")
            ref = _identifier(receipt["id"])
            if tx["isolation"]["receipt"] not in {None, ref}:
                raise ValueError("native isolation receipt binding is immutable")
            tx["isolation"]["receipt"] = ref
            self._write(state)
            return copy.deepcopy(tx)

    def complete_isolation(self, transition_id: str, *, authorize: Authorize,
                           observed: Authorize) -> dict[str, Any]:
        """Bind actual workspace only after fresh native receipt observation."""
        with self.locked() as state:
            tx = state["transitions"][transition_id]
            if tx["state"] != "isolating":
                if tx["state"] == "prepared":
                    return copy.deepcopy(tx)
                raise ValueError("transition is not preparing native isolation")
            if tx.get("cancelRequested"):
                raise ValueError("finish native isolation cancellation before further work")
            cp = state["checkpoints"][tx["checkpointRef"]]
            source = state["owners"][tx["sourceBead"]]
            target = state["owners"][tx["targetBead"]]
            if (source["session"] != tx["sourceSession"] or source["phase"] != "active"
                    or target["session"] != tx["childSession"] or target["phase"] != "reserved"
                    or workspace_snapshot(source["checkout"]) != cp["workspace"]):
                raise ValueError("isolation ownership or source workspace changed")
            if authorize(copy.deepcopy(tx)) is not True or observed(copy.deepcopy(tx)) is not True:
                raise ValueError("native isolation requires current authority and exact fresh observation")
            snapshot = workspace_snapshot(tx["targetCheckout"])
            if snapshot["checkout"] != tx["targetCheckout"]:
                raise ValueError("native isolation checkout is not a physical root")
            tx["targetWorkspace"] = snapshot
            tx["progressKey"] = fingerprint({"source": tx["sourceBead"], "target": tx["targetBead"],
                                             "sourceWorkspace": cp["workspace"], "targetWorkspace": snapshot,
                                             "progress": cp["progress"]})
            if sum(old.get("progressKey") == tx["progressKey"] and old["state"] == "attached"
                   for old in state["transitions"].values()) >= 3:
                raise ValueError("unchanged progress continuation limit reached; inspect the blocker before retry")
            tx["state"] = "prepared"
            self._write(state)
            return copy.deepcopy(tx)

    def reserve_child_file(self, transition_id: str, *, source_session: str | None = None) -> dict[str, Any]:
        with self.locked() as state:
            tx = state["transitions"][transition_id]
            if source_session is not None:
                owner = state["owners"].get(tx["sourceBead"])
                if tx["sourceSession"] != source_session or not owner or owner["session"] != source_session:
                    raise ValueError("child path binding requires its reserved source owner")
                if tx["childSessionFile"] is None and (tx["state"] not in {"prepared", "isolating"} or owner["phase"] != "active"):
                    raise ValueError("child path cannot be repaired after staging or ownership change")
            if tx["childSessionFile"] is None:
                tx["childSessionFile"] = str(self.root.resolve() / "children" / f"{_identifier(tx['childSession'])}.jsonl")
                self._write(state)
            return copy.deepcopy(tx)

    def status(self, transition_id: str) -> dict[str, Any]:
        with self.locked() as state:
            return copy.deepcopy(state["transitions"][transition_id])

    def stage(self, transition_id: str, *, child_session_file: str) -> dict[str, Any]:
        path = Path(child_session_file)
        if not path.is_absolute():
            raise ValueError("child session file must be absolute")
        with self.locked() as state:
            tx = state["transitions"][transition_id]
            if tx["state"] in {"cancelled", "isolating"}:
                raise ValueError("transition is cancelled or native isolation is unresolved")
            if tx["state"] != "prepared":
                if tx["childSessionFile"] != str(path):
                    raise ValueError("child session identity is immutable")
                return copy.deepcopy(tx)
            if tx["childSessionFile"] is not None and tx["childSessionFile"] != str(path):
                raise ValueError("reserved child session identity is immutable")
            cp = state["checkpoints"][tx["checkpointRef"]]
            if workspace_snapshot(cp["workspace"]["checkout"]) != cp["workspace"]:
                raise ValueError("source workspace changed before stage")
            if workspace_snapshot(tx["targetCheckout"]) != tx["targetWorkspace"]:
                raise ValueError("target workspace changed before stage")
            tx["childSessionFile"] = str(path)
            tx["state"] = "staged"
            state["owners"][tx["sourceBead"]]["phase"] = "yielding"
            self._write(state)
            return copy.deepcopy(tx)

    def request_launch(self, transition_id: str, *, source_session: str, authorize: Authorize,
                       host_proof_hash: str | None = None) -> dict[str, Any]:
        with self.locked() as state:
            tx = state["transitions"][transition_id]
            if tx["sourceSession"] != source_session or tx["state"] != "staged":
                raise ValueError("launch already requested or not staged; reconcile without replay")
            if authorize(copy.deepcopy(tx)) is not True:
                raise ValueError("transition authority is unavailable")
            cp = state["checkpoints"][tx["checkpointRef"]]
            if (workspace_snapshot(cp["workspace"]["checkout"]) != cp["workspace"]
                    or workspace_snapshot(tx["targetCheckout"]) != tx["targetWorkspace"]):
                raise ValueError("workspace changed before launch")
            tx["state"] = "launch-requested"
            if host_proof_hash is not None:
                tx["launchProofHash"] = host_proof_hash
            self._write(state)
            return copy.deepcopy(tx)

    def pending_transition(self, session_id: str) -> dict[str, Any] | None:
        with self.locked() as state:
            matches = [tx for tx in state["transitions"].values()
                       if tx["sourceSession"] == session_id and tx["state"] not in {"attached", "cancelled"}]
            if len(matches) > 1:
                raise ValueError("ambiguous source reservation")
            return copy.deepcopy(matches[0]) if matches else None

    def child_transition(self, session_id: str) -> dict[str, Any] | None:
        with self.locked() as state:
            matches = [tx for tx in state["transitions"].values() if tx["childSession"] == session_id]
            if len(matches) > 1:
                raise ValueError("ambiguous child session reservation")
            return copy.deepcopy(matches[0]) if matches else None

    def attach(self, transition_id: str, *, session_id: str, authorize: Authorize, attach: Attach,
               attached: Callable[[str, str], bool | None] | None = None) -> dict[str, Any]:
        with self.locked() as state:
            tx = state["transitions"][transition_id]
            if tx["childSession"] != session_id:
                raise ValueError("child ownership mismatch")
            if tx["state"] == "attached":
                return copy.deepcopy(tx)
            if tx["state"] not in {"staged", "launch-requested", "attaching"}:
                raise ValueError("transition is not staged")
            if authorize(copy.deepcopy(tx)) is not True:
                raise ValueError("transition authority is unavailable")
            cp = state["checkpoints"][tx["checkpointRef"]]
            if workspace_snapshot(cp["workspace"]["checkout"]) != cp["workspace"]:
                raise ValueError("source workspace changed before attachment")
            if workspace_snapshot(tx["targetCheckout"]) != tx["targetWorkspace"]:
                raise ValueError("target workspace changed before attachment")
            if tx["state"] == "attaching" and attached is None:
                raise ValueError("uncertain attachment requires reconciliation before retry")
            already = attached(tx["targetBead"], session_id) if attached is not None else False
            if type(already) is not bool:
                raise ValueError("attachment reconciliation is unresolved")
            if not already:
                if tx["attempts"] >= 3:
                    raise ValueError("attachment retry limit reached; reconcile manually")
                tx["state"] = "attaching"
                tx["attempts"] += 1
                self._write(state)
                attach(tx["targetBead"], session_id)
            source = state["owners"][tx["sourceBead"]]
            if source["session"] != tx["sourceSession"] or source["phase"] != "yielding":
                raise ValueError("source ownership changed during attachment")
            if tx["sourceBead"] != tx["targetBead"]:
                source["phase"] = "paused"
            state["owners"][tx["targetBead"]] = {
                "session": session_id, "checkout": tx["targetCheckout"], "phase": "active",
                "assignmentRef": tx["assignmentRef"],
                **({"checkpointRef": tx["targetBefore"]["checkpointRef"]}
                   if tx["targetBefore"] and tx["targetBefore"].get("checkpointRef") else {}),
            }
            tx["state"] = "attached"
            self._write(state)
            return copy.deepcopy(tx)

    def recover(self, transition_id: str) -> dict[str, Any]:
        tx = self.status(transition_id)
        actions = {"isolating": "reconcile-native-isolation", "prepared": "stage-exact-child", "staged": "launch-exact-child",
                   "launch-requested": "reconcile-launch", "attaching": "reconcile-attachment",
                   "attached": "continue-child", "cancelled": "continue-source"}
        action = "finish-cancellation" if tx["state"] == "isolating" and tx.get("cancelRequested") else actions[tx["state"]]
        return {**tx, "requiredAction": action}

    def cancel(self, transition_id: str, *, source_session: str,
               before_exec_failure: str | None = None, host_proof_hash: str | None = None,
               settle_isolation: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
        # Only trusted host callbacks use the failure variant. A timeout or a
        # missing process is NOT proof that exec did not occur.
        if before_exec_failure is not None and before_exec_failure not in _PREEXEC_FAILURES:
            raise ValueError("invalid pre-exec failure evidence")
        with self.locked() as state:
            tx = state["transitions"][transition_id]
            allowed = {"prepared", "staged", "cancelled"}
            if settle_isolation is not None and before_exec_failure is None:
                allowed.add("isolating")
            if before_exec_failure is not None and before_exec_failure != "stage-failed":
                allowed.add("launch-requested")
            if tx["sourceSession"] != source_session or tx["state"] not in allowed:
                raise ValueError("only a pre-attachment source can cancel; attaching needs reconciliation")
            if tx["state"] == "launch-requested" and (
                not host_proof_hash or not tx.get("launchProofHash")
                or not hmac.compare_digest(host_proof_hash, tx["launchProofHash"])
            ):
                raise ValueError("launch compensation requires the reserved host capability; reconcile unknown launch")
            if tx["state"] == "cancelled":
                return copy.deepcopy(tx)
            source = state["owners"][tx["sourceBead"]]
            if source["session"] != source_session or source["phase"] not in {"active", "yielding"}:
                raise ValueError("source ownership changed before cancellation")
            if tx["state"] == "isolating":
                # Persist intent before crossing the delivery journal boundary.
                # A crash after receipt cancellation must never restart effect
                # preparation merely because find_pending no longer finds it.
                tx["cancelRequested"] = True
                self._write(state)
                settled = settle_isolation(copy.deepcopy(tx))
                if not isinstance(settled, dict) or settled.get("status") not in {"unissued", "cancelled", "applied"}:
                    raise ValueError("unknown native isolation cannot release target ownership")
                tx["isolationSettlement"] = copy.deepcopy(settled)
            if tx["sourceBead"] != tx["targetBead"]:
                if tx["targetBefore"] is None:
                    del state["owners"][tx["targetBead"]]
                else:
                    state["owners"][tx["targetBead"]] = tx["targetBefore"]
            state["owners"][tx["sourceBead"]]["phase"] = "active"
            tx["state"] = "cancelled"
            if before_exec_failure is not None:
                tx["launchFailure"] = {"reason": before_exec_failure, "provenance": "launch-capability-pre-exec"}
            self._write(state)
            return copy.deepcopy(tx)


def runtime_store(checkout: str | None = None) -> LifecycleStore:
    from .authority import repository_identity

    identity = repository_identity(checkout or str(Path.cwd()))
    key = hashlib.sha256(identity.encode()).hexdigest()
    return LifecycleStore(Path.home() / ".pi" / "runtime" / key / "work-lifecycle")


def _closeout_context(state: dict[str, Any], session_id: str, bead_id: str) -> None:
    # Callers obtain session_id from current host context, not a CLI override.
    checkout = str(checkout_identity(str(Path.cwd())))
    owner = state["owners"].get(bead_id)
    if owner is not None and (owner["session"] != session_id or owner["checkout"] != checkout
                              or owner["phase"] not in {"active", "completed"}):
        raise ValueError("closeout checkout or execution ownership does not match")
    if any(key != bead_id and value["checkout"] == checkout and value["phase"] != "completed"
           for key, value in state["owners"].items()):
        raise ValueError("closeout checkout belongs to another execution")
    # Persisted hosts must prove their header. Legacy headless callers retain
    # their existing explicit session/checkout contract; no launch is implied.
    if os.environ.get("PI_SESSION_FILE"):
        _source_session_file(session_id, checkout)
    if any(tx["sourceSession"] == session_id and tx["state"] not in {"attached", "cancelled"}
           for tx in state["transitions"].values()):
        raise ValueError("pending transition must be settled before closeout")


def validate_closeout_context(session_id: str, bead_id: str) -> None:
    with runtime_store().locked() as state:
        _closeout_context(state, session_id, bead_id)


def guard_success_recording(session_id: str, bead_id: str, record: Callable[[], Any], *,
                            directory: Path | None = None) -> Any:
    """Serialize success with reservation; recognize bound ledgers across checkouts."""
    from .quality import current_session_id, resolve_runtime_directory

    canonical = directory is None or directory == resolve_runtime_directory("quality").resolve()
    with runtime_store().locked() as state:
        bound_source = any(tx["sourceSession"] == session_id and tx["sourceBead"] == bead_id
                           and tx.get("sourceQualityDirectory") == str(directory)
                           for tx in state["transitions"].values())
        if not canonical and not bound_source:
            # Keep the lock through publication: a concurrent prepare may be
            # about to bind this exact directory as its canonical source.
            return record()
        if any(tx["sourceSession"] == session_id and tx["state"] not in {"attached", "cancelled"}
               for tx in state["transitions"].values()):
            raise ValueError("pending transition must be settled before final success")
        owner = state["owners"].get(bead_id)
        try:
            current = current_session_id()
        except (RuntimeError, ValueError):
            current = None
        if owner is not None and owner["session"] == session_id and current == session_id:
            _closeout_context(state, session_id, bead_id)
        return record()


def authority_store() -> Any:
    from .authority import AuthorityStore

    return AuthorityStore()


def _direct_assignment(bead_id: str, scope_beads: list[str] | None = None) -> str:
    authority = authority_store()
    status = authority.inspect()["status"]
    if status == "revoked":
        raise WorkAuthorityUnavailable("owner standing policy is revoked; no new attempts")
    if status == "inactive":
        if scope_beads:
            raise WorkAuthorityUnavailable("multi-Bead assignment requires active standing policy")
        return f"direct:{bead_id}"
    if scope_beads is not None:
        for selected in sorted(set([bead_id, *scope_beads])):
            if _bead(selected).get("status") not in {"open", "in_progress"}:
                raise WorkAuthorityUnavailable("explicit work scope requires existing unfinished Beads")
    return authority.register_direct_assignment(str(Path.cwd()), bead_id, scope_beads=scope_beads)


def _require_assignment_effects(assignment: str, bead_id: str, effects: tuple[str, ...]) -> None:
    from .authority import repository_identity

    if not effects:
        return
    try:
        permission = authority_store()
        if assignment == f"direct:{bead_id}":
            allowed = permission.inspect()["status"] == "inactive"
        else:
            repository = repository_identity(str(Path.cwd()))
            action = {"repository": repository, "bead": bead_id, "effects": list(effects),
                      "target": {"repository": repository, "identity": f"beads:{bead_id}", "verified": True},
                      "decisionRefs": _decision_refs(_bead(bead_id)),
                      "preconditions": {"identity": True, "platform": True, "effectClosure": True}}
            allowed = permission.check(assignment, action)["status"] == "active"
        if not allowed:
            raise ValueError("effect is not permitted")
    except (OSError, ValueError, TypeError, AttributeError):
        raise WorkAuthorityUnavailable("direct operation effects are outside current authority") from None


def guarded_standing_beads_effect(envelope: dict[str, Any] | None, bead_id: str,
                                  effect: Callable[[], Any] | None = None, *,
                                  close_reason: str | None = None,
                                  gate: Callable[[], str | None] | None = None) -> Any:
    """Serialize known execution ownership with a controller write.

    Read-only worker actions do not exempt their controller's native writes.
    Missing worker envelope uses existing scope only, never new enrollment.
    """
    from .authority import decision_constraints, revalidate_native_beads_effect
    from .quality import current_session_id

    with runtime_store().locked() as state:
        owner = state["owners"].get(bead_id)
        if owner is not None:
            session = current_session_id()
            if (owner["phase"] != "active" or owner["session"] != session
                    or (envelope is not None and owner.get("assignmentRef") != envelope.get("source", {}).get("assignment"))):
                raise WorkAuthorityUnavailable("authority conflicts with captured execution ownership")
            _closeout_context(state, session, bead_id)
        if gate is not None:
            error = gate()
            if error:
                raise WorkAuthorityUnavailable(error)
        if envelope is not None:
            error = revalidate_native_beads_effect(envelope, bead_id, close_reason=close_reason)
            if error:
                raise WorkAuthorityUnavailable(error)
        else:
            permission = authority_store()
            assignment = owner.get("assignmentRef") if owner else None
            legacy = permission.inspect()["status"] == "inactive" and assignment in {None, f"direct:{bead_id}"}
            if not legacy:
                if owner is not None and not assignment:
                    raise WorkAuthorityUnavailable("captured authority requires reconciliation")
                if assignment is None:
                    existing = permission.assignment_for(str(Path.cwd()), bead_id)
                    if existing is None:
                        raise WorkAuthorityUnavailable("native effect requires an existing assignment")
                    assignment = existing["id"]
            canonical = _bead(bead_id)
            eligible = canonical.get("status") in {"open", "in_progress"}
            if close_reason is not None:
                eligible = eligible or (canonical.get("status") == "closed" and canonical.get("close_reason") == close_reason)
            if not eligible or _blockers(canonical) or decision_constraints(_decision_refs(canonical), bead_id):
                raise WorkAuthorityUnavailable("canonical work or decision constraints changed")
            if not legacy:
                _require_assignment_effects(assignment, bead_id, ("beads-write",))
        return effect() if effect is not None else None


def closeout_effect_guard(session_id: str | None, bead_id: str, *, reason: str) -> Callable[[tuple[str, ...]], None]:
    """Use captured scope; closeout must never enroll or widen an assignment."""
    with runtime_store().locked() as state:
        if session_id is not None:
            _closeout_context(state, session_id, bead_id)
        owner = state["owners"].get(bead_id)
        assignment = owner.get("assignmentRef") if owner else None
    if assignment is None:
        if authority_store().inspect()["status"] != "inactive":
            raise WorkAuthorityUnavailable("closeout requires a captured assignment; reconcile authority")
        assignment = f"direct:{bead_id}"

    def check(effects: tuple[str, ...]) -> None:
        from .authority import decision_constraints

        if session_id is not None:
            validate_closeout_context(session_id, bead_id)
        canonical = _bead(bead_id)
        if (canonical.get("status") == "closed" and canonical.get("close_reason") != reason
                or canonical.get("status") not in {"open", "in_progress", "closed"}
                or _blockers(canonical) or decision_constraints(_decision_refs(canonical), bead_id)):
            raise WorkAuthorityUnavailable("canonical work or decision constraints changed before closeout")
        _require_assignment_effects(assignment, bead_id, effects)

    return check


def guard_session_link(session_id: str, bead_id: str, link: Callable[[Callable[[], None]], Any], *,
                       required_effects: tuple[str, ...] = (), scope_beads: list[str] | None = None) -> Any:
    from . import quality

    attempt = quality.session_attempt_state(session_id)
    if attempt["beadId"] not in {None, bead_id} or attempt["outcome"] is not None:
        raise quality.SessionWorkItemConflict("session ownership/outcome is immutable; use handoff_bead for checkpointed continuation")
    store = runtime_store()
    if store.owner(bead_id) is None and any(
        other != session_id and outcome is None
        for other, outcome in quality.work_item_attempts(bead_id).items()
    ):
        raise quality.SessionWorkItemConflict("another legacy attempt may still own execution; reconcile ownership")
    # Durable reservation precedes the external Beads claim. A failed link keeps
    # the same owner for retry; elapsed time never grants ownership to a sibling.
    try:
        assignment_ref = _direct_assignment(bead_id, scope_beads)
    except (OSError, ValueError):
        raise WorkAuthorityUnavailable("current assignment authority requires inspection") from None
    try:
        _require_assignment_effects(assignment_ref, bead_id, required_effects)
        store.claim(bead_id, session_id, str(Path.cwd()))
        store.bind_assignment(bead_id, session_id, assignment_ref)
    except WorkAuthorityUnavailable:
        raise
    except ValueError as exc:
        raise quality.SessionWorkItemConflict(str(exc)) from exc
    # Recheck after acquiring the quality transaction, immediately before its
    # external claim callback. Capture scope here; never reacquire lifecycle
    # ownership while holding the quality lock.
    return link(lambda: _require_assignment_effects(assignment_ref, bead_id, required_effects))


def _bead(bead_id: str) -> dict[str, Any]:
    from .work import BEAD_ID, normalize_bead, run_beads_json

    if not isinstance(bead_id, str) or not BEAD_ID.fullmatch(bead_id):
        raise ValueError("invalid Bead ID")
    code, data, _ = run_beads_json(["show", bead_id])
    bead = normalize_bead(data)
    if code or not bead or bead.get("id") != bead_id:
        raise ValueError("canonical Bead is unavailable")
    return bead


def _blockers(bead: dict[str, Any]) -> list[str]:
    refs = bead.get("dependencies", [])
    if not isinstance(refs, list):
        raise ValueError("target dependencies are malformed")
    blocked = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("target dependency is malformed")
        kind = ref.get("dependency_type", ref.get("type", "blocks"))
        if kind == "parent-child" or kind in {"related", "discovered-from", "supersedes"}:
            continue
        if kind not in {"blocks", "conditional-blocks", "waits-for"}:
            raise ValueError("unknown dependency semantics")
        dependency = _bead(ref.get("depends_on_id", ref.get("id")))
        if dependency.get("status") != "closed":
            blocked.append(dependency["id"])
    return blocked


def _decision_refs(bead: dict[str, Any]) -> list[str]:
    metadata = bead.get("metadata")
    if metadata is None or metadata == "":
        metadata = {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    if not isinstance(metadata, dict) or not isinstance(metadata.get("pi", {}), dict):
        raise ValueError("canonical decision metadata is malformed")
    return _strings(metadata.get("pi", {}).get("decisionRefs", []), "decision refs", empty=True)


def delivery_store() -> Any:
    from .delivery import DeliveryStore

    return DeliveryStore(authority=authority_store())


def _isolation_action(request: dict[str, Any]) -> dict[str, Any]:
    isolation = request["isolation"]
    receipt = delivery_store().inspect(isolation["receipt"])["receipt"] if isolation["receipt"] else None
    action = receipt["action"] if receipt is not None else isolation["action"]
    if ((receipt is not None and (receipt["assignment"] != request["assignmentRef"]
                                 or fingerprint(action) != fingerprint(isolation["action"])))
            or action["adapter"] != "git-worktree-create"
            or action["bead"] != request["targetBead"] or action["target"]["identity"] != request["targetCheckout"]
            or action["facts"]["checkout"] != request["targetCheckout"]
            or action["repository"] != request["isolation"]["repository"]
            or action["source"]["identity"] != request["isolation"]["source"]):
        raise ValueError("native isolation receipt does not match transition")
    return action


def _transition_authorized(request: dict[str, Any], *, planned_action: dict[str, Any] | None = None) -> bool:
    from .quality import session_attempt_state

    if request.get("cancelRequested"):
        return False
    directory = request.get("sourceQualityDirectory")
    if not isinstance(directory, str) or not Path(directory).is_absolute():
        return False
    path = Path(directory)
    if not path.is_dir() or path.resolve() != path:
        return False
    attempt = session_attempt_state(request["sourceSession"], directory=path)
    if attempt["beadId"] != request["sourceBead"] or attempt["outcome"] == "success":
        return False
    return _transition_effects_authorized(request, planned_action=planned_action)


def _transition_effects_authorized(request: dict[str, Any], *, planned_action: dict[str, Any] | None = None) -> bool:
    """Fresh external gates; caller protects any prior source-outcome check."""
    from .authority import decision_constraints, repository_identity

    target = _bead(request["targetBead"])
    source = _bead(request["sourceBead"])
    if (target.get("status") not in {"open", "in_progress"}
            or source.get("status") not in {"open", "in_progress"} or _blockers(target)):
        return False
    if target.get("assignee") and target.get("assignee") != source.get("assignee"):
        return False
    refs = _decision_refs(target)
    if decision_constraints(refs, target["id"]):
        return False
    assignment = request["assignmentRef"]
    if assignment == f"direct:{request['sourceBead']}":
        # Continuation of an existing direct assignment grants no new effects,
        # project, or Bead. It is not standing full-delivery authority.
        return (request["sourceBead"] == request["targetBead"]
                and authority_store().inspect()["status"] == "inactive")
    creation = _isolation_action(request) if request.get("isolation") else planned_action
    if creation is not None:
        repository = repository_identity(creation["facts"]["sourceCheckout"])
        if (repository != creation["repository"] or creation["bead"] != request["targetBead"]
                or creation["facts"]["checkout"] != request["targetCheckout"]):
            return False
        if request.get("state") not in {None, "isolating"} and repository_identity(request["targetCheckout"]) != repository:
            return False
    else:
        repository = repository_identity(request["targetCheckout"])
    action = {"repository": repository, "bead": request["targetBead"], "effects": ["work-transition", "beads-write"],
              "target": {"repository": repository, "identity": request["targetCheckout"], "verified": True},
              "decisionRefs": refs,
              "preconditions": {"identity": True, "platform": True, "effectClosure": True}}
    return authority_store().check(assignment, action)["status"] == "active"


def checkpoint_current(bead_id: str, progress: dict[str, Any] | None = None, *,
                       session_id: str | None = None) -> dict[str, Any]:
    from . import quality

    session_id = session_id or quality.current_session_id()
    attempt = quality.session_attempt_state(session_id)
    if attempt["beadId"] != bead_id:
        raise ValueError("checkpoint does not match session ownership")
    if attempt["outcome"] == "success":
        raise ValueError("successful source requires closeout repair, not unfinished continuation")
    bead = _bead(bead_id)
    if bead.get("status") == "closed":
        raise ValueError("closed work uses verified closeout handoff, not an unfinished checkpoint")
    store = runtime_store()
    if store.owner(bead_id) is None:
        if any(other != session_id and outcome is None
               for other, outcome in quality.work_item_attempts(bead_id).items()):
            raise ValueError("legacy execution ownership needs reconciliation")
        store.claim(bead_id, session_id, str(Path.cwd()))
    owner = store.owner(bead_id)
    assignment_ref = owner.get("assignmentRef") or _direct_assignment(bead_id)
    store.bind_assignment(bead_id, session_id, assignment_ref)
    if progress is not None:
        if not isinstance(progress, dict):
            raise ValueError("checkpoint progress must be an object")
        if progress.get("assignmentRef", assignment_ref) != assignment_ref:
            raise ValueError("checkpoint assignment cannot replace execution scope")
        progress = {**progress, "assignmentRef": assignment_ref}
    if progress is None:
        previous = store.latest_checkpoint(bead_id)
        if previous is not None:
            progress = {**copy.deepcopy(previous["progress"]), "assignmentRef": assignment_ref}
    if progress is None:
        # No invented progress/ownership/verification. Bead and measured checkout
        # remain sufficient for a fresh attempt to inspect and continue safely.
        progress = {"objective": str(bead.get("description") or bead.get("title") or bead_id)[:16000],
                    "decisions": [], "completed": [], "next": ["Inspect Bead, referenced artifacts and preserved checkout; continue acceptance work."],
                    "blockers": _blockers(bead), "verification": [], "ownedPaths": [], "artifactRefs": [],
                    "assignmentRef": assignment_ref}
    cp = store.checkpoint(bead_id, session_id, progress)
    return {"schemaVersion": 1, "status": "checkpointed", "checkpoint": cp}


def transition_check(target_bead: str | None, *, mode: str, session_id: str,
                     checkpoint_ref: str | None = None, checkout: str | None = None) -> dict[str, Any]:
    from . import quality
    from .work import normalize_bead, order_work_items, run_beads_json

    source_quality = str(quality.resolve_runtime_directory("quality").resolve())
    attempt = quality.session_attempt_state(session_id, directory=source_quality)
    source_bead = attempt["beadId"]
    if not source_bead:
        raise ValueError("unassigned session uses normal ready-work handoff")
    if attempt["outcome"] == "success":
        raise ValueError("successful source requires closeout repair, not unfinished continuation")
    store = runtime_store()
    cp = store.get_checkpoint(checkpoint_ref) if checkpoint_ref else store.latest_checkpoint(source_bead)
    if cp is None or cp["bead"] != source_bead or cp["session"] != session_id:
        raise ValueError("matching checkpoint required before transition")
    source = _bead(source_bead)
    if source.get("status") == "closed":
        raise ValueError("closed source requires verified successful-closeout handoff")
    if mode == "resume":
        target_bead = target_bead or source_bead
    if target_bead is None:
        code, data, _ = run_beads_json(["ready", "--limit", "0"])
        if code or not isinstance(data, list):
            raise ValueError("ready work is unavailable")
        candidates = [normalize_bead(item) for item in data if isinstance(item, dict)]
        # Filter permission before deterministic priority/ID ordering. Permission
        # does not schedule projects outside the recorded queue assignment.
        for candidate in order_work_items([item for item in candidates if item and item.get("issue_type") != "epic"]):
            if candidate["id"] == source_bead:
                continue
            owner = store.owner(candidate["id"])
            candidate_checkout = checkout or (owner["checkout"] if owner else str(Path.cwd()))
            request = {"sourceBead": source_bead, "sourceSession": session_id,
                       "sourceQualityDirectory": source_quality, "targetBead": candidate["id"],
                       "assignmentRef": cp["progress"]["assignmentRef"], "targetCheckout": candidate_checkout}
            if _transition_authorized(request) and (owner is None or owner["phase"] == "paused"):
                target_bead = candidate["id"]
                break
        if target_bead is None:
            return {"schemaVersion": 1, "status": "idle", "reason": "no eligible assigned target", "checkpointRef": cp["id"]}
    target = _bead(target_bead)
    owner = store.owner(target_bead)
    creation = None
    if target_bead != source_bead and checkout is None and owner is None:
        from .worktree_policy import WorktreeCreationAdapter
        creation = WorktreeCreationAdapter(cp["workspace"]["checkout"], target_bead,
                                            decision_refs=_decision_refs(target)).resolve()
        if authority_store().check(cp["progress"]["assignmentRef"], creation)["status"] != "active":
            raise ValueError("native worktree creation is outside assignment authority")
        target_checkout = creation["facts"]["checkout"]
    else:
        target_checkout = str(checkout_identity(checkout or (owner["checkout"] if owner else str(Path.cwd()))))
    if mode == "resume" and target_bead != source_bead:
        raise ValueError("resume target must match source Bead")
    if target_bead != source_bead and target_checkout == cp["workspace"]["checkout"]:
        raise ValueError("target requires an isolated existing checkout; preserve source work")
    if target_bead != source_bead and owner and owner["phase"] != "paused":
        raise ValueError("target execution ownership is busy")
    if workspace_snapshot(cp["workspace"]["checkout"]) != cp["workspace"]:
        raise ValueError("source changed; refresh checkpoint before transition")
    request = {"sourceSession": session_id, "sourceBead": source_bead, "targetBead": target_bead,
               "sourceQualityDirectory": source_quality,
               "targetCheckout": target_checkout, "assignmentRef": cp["progress"]["assignmentRef"]}
    if not _transition_authorized(request, planned_action=creation):
        raise ValueError("target status, dependency, ownership or authority blocks transition")
    if owner is None:
        directories = {source_quality}
        if creation is None:
            directories.add(str(quality.resolve_runtime_directory("quality", cwd=target_checkout).resolve()))
        if any(outcome is None for directory in directories
               for outcome in quality.work_item_attempts(target_bead, directory=directory).values()):
            raise ValueError("target legacy ownership needs reconciliation")
    return {"schemaVersion": 1, "status": "needs-isolation" if creation else "ready", "launch": "host-required",
            **({"creation": creation} if creation else {}),
            "checkpointRef": cp["id"], "source": {"beadId": source_bead, "outcome": attempt["outcome"],
                                                "qualityDirectory": source_quality},
            "target": {"beadId": target_bead, "checkout": target_checkout, "status": target["status"]}}


def _advance_isolation(store: LifecycleStore, transition_id: str, session_id: str) -> dict[str, Any]:
    from .worktree_policy import WorktreeCreationAdapter

    tx = store.status(transition_id)
    if tx["sourceSession"] != session_id or tx["state"] != "isolating":
        raise ValueError("native isolation requires its reserved source session")
    if tx.get("cancelRequested"):
        raise ValueError("finish native isolation cancellation before further work")
    cp = store.get_checkpoint(tx["checkpointRef"])
    source_owner = store.owner(tx["sourceBead"])
    target_owner = store.owner(tx["targetBead"])
    if (not source_owner or source_owner["session"] != session_id or source_owner["phase"] != "active"
            or not target_owner or target_owner["session"] != tx["childSession"] or target_owner["phase"] != "reserved"
            or _source_session_file(session_id, cp["workspace"]["checkout"]) != tx["sourceSessionFile"]
            or workspace_snapshot(cp["workspace"]["checkout"]) != cp["workspace"]):
        raise ValueError("native isolation source or ownership changed")
    action = _isolation_action(tx)
    adapter = WorktreeCreationAdapter(action["facts"]["sourceCheckout"], tx["targetBead"],
                                      decision_refs=action["decisionRefs"])
    tx = store.reserve_child_file(tx["id"])
    receipts = delivery_store()
    if tx["isolation"]["receipt"] is None:
        publication: dict[str, Any] = {}
        def publish() -> dict[str, Any] | None:
            pending = receipts.find_pending(tx["assignmentRef"], fingerprint(action))
            if pending is None:
                if not _transition_authorized(tx):
                    publication["status"] = "authority-denied"
                    return None
                pending = receipts.prepare(tx["assignmentRef"], adapter, expected_action_fingerprint=fingerprint(action))
            publication.update(pending)
            return pending["receipt"] if pending["status"] in {"prepared", "not-applied", "started", "uncertain"} else None
        tx = store.bind_isolation_receipt(tx["id"], publish=publish)
        if tx["isolation"]["receipt"] is None:
            denied = publication["status"] == "authority-denied"
            return {**tx, "requiredAction": "inspect-current-authority" if denied else "reconcile-native-isolation",
                    "deliveryStatus": publication["status"]}
    authorized = _transition_authorized(tx)
    result = (receipts.execute(tx["isolation"]["receipt"], adapter) if authorized
              else receipts.reconcile(tx["isolation"]["receipt"], adapter))
    tx = store.status(tx["id"])
    if tx["state"] == "cancelled" or tx.get("cancelRequested"):
        raise ValueError("native isolation cancellation supersedes preparation; inspect transition status")
    if not _transition_authorized(tx):
        return {**tx, "requiredAction": "inspect-current-authority", "deliveryStatus": "authority-denied",
                "observedDeliveryStatus": result["status"]}
    if result["status"] != "applied":
        return {**tx, "requiredAction": "reconcile-native-isolation", "deliveryStatus": result["status"]}
    def observed(current: dict[str, Any]) -> bool:
        _isolation_action(current)
        return receipts.observe_current(current["isolation"]["receipt"], adapter)["status"] == "applied"
    return store.complete_isolation(tx["id"], authorize=_transition_authorized, observed=observed)


def _settle_isolation_for_cancel(tx: dict[str, Any]) -> dict[str, Any]:
    """Run under lifecycle ownership; never remove worktrees or replay writes."""
    from .worktree_policy import WorktreeCreationAdapter

    action = _isolation_action(tx)
    receipts = delivery_store()
    result = (receipts.inspect(tx["isolation"]["receipt"]) if tx["isolation"]["receipt"]
              else receipts.find_pending(tx["assignmentRef"], fingerprint(action)))
    if result is None:
        return {"status": "unissued", "receipt": None, "disposition": "preserved-no-cleanup"}
    ref = result["receipt"]["id"]
    adapter = WorktreeCreationAdapter(action["facts"]["sourceCheckout"], tx["targetBead"],
                                      decision_refs=action["decisionRefs"])
    if result["status"] in {"started", "uncertain"}:
        result = receipts.reconcile(ref, adapter)
    if result["status"] in {"prepared", "not-applied"}:
        result = receipts.cancel(ref, "source cancelled unissued or definitely unapplied isolation")
    if result["status"] == "applied":
        if receipts.observe_current(ref, adapter)["status"] != "applied":
            raise ValueError("changed native isolation requires reconciliation; preserve target ownership")
    elif result["status"] != "cancelled":
        raise ValueError("unknown native isolation cannot release target ownership")
    return {"status": result["status"], "receipt": ref, "disposition": "preserved-no-cleanup"}


def _verify_child_header(tx: dict[str, Any], *, empty: bool = False) -> None:
    path = Path(tx["childSessionFile"])
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("child session path is unsafe")
    with path.open("r") as stream:
        line = stream.readline(8193)
        if len(line) > 8192:
            raise ValueError("child header is too large")
        header = json.loads(line)
        if empty and stream.read(1):
            raise ValueError("fresh child contains unexpected session history")
    if (header.get("type") != "session" or header.get("id") != tx["childSession"]
            or not isinstance(header.get("cwd"), str) or not Path(header["cwd"]).is_absolute()
            or Path(header["cwd"]).resolve() != Path(tx["targetCheckout"])
            or header.get("parentSession") != tx.get("sourceSessionFile")):
        raise ValueError("child session identity does not match reservation")


def _source_session_file(session_id: str, checkout: str) -> str:
    from .quality import current_session_id

    if current_session_id() != session_id or checkout_identity(str(Path.cwd())) != checkout_identity(checkout):
        raise ValueError("source session or current checkout does not match execution identity")
    raw = os.environ.get("PI_SESSION_FILE")
    if not raw:
        raise ValueError("persisted source session file is required for launch")
    path = Path(raw).resolve(strict=True)
    with path.open() as stream:
        line = stream.readline(8193)
    if len(line) > 8192:
        raise ValueError("source session header is too large")
    header = json.loads(line)
    if (header.get("type") != "session" or header.get("id") != session_id
            or not isinstance(header.get("cwd"), str) or not Path(header["cwd"]).is_absolute()
            or checkout_identity(header["cwd"]) != checkout_identity(checkout)):
        raise ValueError("source session header does not match execution identity")
    return str(path)


def _launch_proof_hash(transition_id: str, source_session: str) -> str | None:
    """Private pipe capability, never a CLI flag or model-facing input."""
    raw_fd = os.environ.get("AGNT_WORK_LAUNCH_PROOF_FD")
    if raw_fd is None:
        return None
    try:
        fd = int(raw_fd)
        mode = os.fstat(fd).st_mode
        if fd < 0 or not (stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)):
            raise ValueError("not a private pipe")
        chunks = bytearray()
        while len(chunks) <= 4096:
            part = os.read(fd, 4097 - len(chunks))
            if not part:
                break
            chunks.extend(part)
        payload = json.loads(chunks) if len(chunks) <= 4096 else None
        if (not isinstance(payload, dict) or set(payload) != {"kind", "transition", "sourceSession", "secret"}
                or payload["kind"] != "work-launch-v1" or payload["transition"] != transition_id
                or payload["sourceSession"] != source_session or not isinstance(payload["secret"], str)
                or len(payload["secret"]) != 64 or any(c not in "0123456789abcdef" for c in payload["secret"])):
            raise ValueError("invalid capability")
        return fingerprint(payload)
    except (OSError, TypeError, ValueError):
        raise ValueError("invalid private launch capability") from None


def transition_context(session_id: str) -> dict[str, Any]:
    from . import quality

    store = runtime_store()
    tx = store.child_transition(session_id)
    if tx and tx["state"] != "attached":
        return {"schemaVersion": 1, "status": "child", "transition": store.recover(tx["id"])}
    attempt = quality.session_attempt_state(session_id)
    bead_id = attempt["beadId"]
    if not bead_id or _bead(bead_id).get("status") == "closed":
        return {"schemaVersion": 1, "status": "legacy"}
    return {"schemaVersion": 1, "status": "continuable", "beadId": bead_id,
            "outcome": attempt["outcome"], "owner": store.owner(bead_id),
            "pendingTransition": store.pending_transition(session_id)}


def add_cli_parsers(sub: Any) -> None:
    context = sub.add_parser("transition-context", help="inspect this session's continuation identity")
    context.add_argument("--session-id", required=True)
    cp = sub.add_parser("checkpoint", help="preserve unfinished work without closing its Bead")
    cp.add_argument("bead_id")
    cp.add_argument("--input-file", help="curated progress JSON; '-' reads at most 64 KiB from stdin")
    for name in ("transition-check", "transition-prepare"):
        parser = sub.add_parser(name, help="validate or reserve an assigned continuation")
        parser.add_argument("bead_id", nargs="?")
        parser.add_argument("--mode", choices=["resume", "switch", "next"], required=True)
        parser.add_argument("--session-id", required=True)
        parser.add_argument("--checkpoint-ref")
        parser.add_argument("--checkout")
        if name == "transition-prepare":
            parser.add_argument("--runtime-ready", action="store_true")
    for name in ("transition-status", "transition-recover", "transition-bind-child", "transition-isolate", "transition-stage", "transition-launch", "transition-attach", "transition-cancel", "transition-abort-launch"):
        parser = sub.add_parser(name, help="inspect or reconcile the exact persisted transition")
        parser.add_argument("transition_id")
        if name == "transition-recover":
            parser.add_argument("--compact", action="store_true", help="omit workspace hash inventories, retaining all progress and recovery state")
        if name in {"transition-bind-child", "transition-isolate", "transition-stage", "transition-launch", "transition-attach", "transition-cancel", "transition-abort-launch"}:
            parser.add_argument("--session-id", required=True)
        if name == "transition-abort-launch":
            parser.add_argument("--reason", choices=sorted(_PREEXEC_FAILURES), required=True)


def _transition_response(tx: dict[str, Any]) -> dict[str, Any]:
    blocked = "deliveryStatus" in tx
    return {"schemaVersion": 1, "status": "blocked" if blocked else "ok", "transition": tx,
            **({"reason": f"Native isolation remains {tx['deliveryStatus']}; reconcile transition {tx['id']}."}
               if blocked else {})}


def dispatch_cli(args: Any) -> dict[str, Any]:
    from . import quality
    from .work import run_beads_json

    store = runtime_store()
    if args.command == "transition-context":
        return transition_context(args.session_id)
    if args.command == "checkpoint":
        progress = None
        if args.input_file:
            raw = sys.stdin.read(65537) if args.input_file == "-" else Path(args.input_file).read_text()
            if len(raw.encode("utf-8")) > 65536:
                raise ValueError("checkpoint progress exceeds 64 KiB")
            progress = json.loads(raw)
            if not isinstance(progress, dict):
                raise ValueError("checkpoint progress must be an object")
        return checkpoint_current(args.bead_id, progress)
    if args.command in {"transition-check", "transition-prepare"}:
        source_file = None
        if args.command == "transition-prepare":
            if not args.runtime_ready:
                raise ValueError("runtime launch capability is unavailable; host continuation required")
            source_file = _source_session_file(args.session_id, str(Path.cwd()))
            pending = store.pending_transition(args.session_id)
            if pending is not None:
                if (args.bead_id not in {None, pending["targetBead"]} or args.mode != pending["mode"]
                        or args.checkpoint_ref not in {None, pending["checkpointRef"]}
                        or (args.checkout and str(Path(args.checkout).resolve()) != pending["targetCheckout"])
                        or source_file != pending["sourceSessionFile"]):
                    raise ValueError("source has a different pending transition; reconcile its exact reservation")
                tx = (_advance_isolation(store, pending["id"], args.session_id) if pending["state"] == "isolating"
                      else store.reserve_child_file(pending["id"]))
                return _transition_response(tx)
        result = transition_check(args.bead_id, mode=args.mode, session_id=args.session_id,
                                  checkpoint_ref=args.checkpoint_ref, checkout=args.checkout)
        if args.command == "transition-check" or result["status"] not in {"ready", "needs-isolation"}:
            return result
        isolation = None
        if result.get("creation"):
            planned = result["creation"]
            isolation = {"receipt": None, "repository": planned["repository"],
                         "source": planned["source"]["identity"], "action": planned}
        tx = store.prepare(source_session=args.session_id, checkpoint_ref=result["checkpointRef"],
                           target_bead=result["target"]["beadId"], target_checkout=result["target"]["checkout"],
                           target_status=result["target"]["status"], blockers=[], mode=args.mode,
                           runtime_ready=args.runtime_ready, authorize=_transition_authorized,
                           source_session_file=source_file,
                           source_quality_directory=result["source"]["qualityDirectory"], isolation=isolation)
        tx = store.reserve_child_file(tx["id"])
        if isolation is not None:
            tx = _advance_isolation(store, tx["id"], args.session_id)
    elif args.command == "transition-isolate":
        tx = _advance_isolation(store, args.transition_id, args.session_id)
    elif args.command == "transition-recover":
        tx = store.recover(args.transition_id)
        result = {**_transition_response(tx), "checkpoint": store.get_checkpoint(tx["checkpointRef"])}
        if args.compact:
            for record, key in ((tx, "targetWorkspace"), (result["checkpoint"], "workspace")):
                workspace = record[key]
                if workspace is None:
                    continue
                record[key] = {**{k: v for k, v in workspace.items() if k != "changed"},
                               "changedPathCount": len(workspace["changed"]),
                               "changedFingerprint": fingerprint(workspace["changed"])}
            result["presentation"] = {
                "fullCommand": f"agnt work transition-recover {args.transition_id}",
                "warning": "Workspace hash inventories omitted; checkpoint progress is unchanged, historical context, not authority. Preserve dirty work and revalidate current canonical constraints before effects.",
            }
        return result
    else:
        tx = store.status(args.transition_id)
        if args.command in {"transition-bind-child", "transition-stage", "transition-launch", "transition-cancel", "transition-abort-launch"}:
            cp = store.get_checkpoint(tx["checkpointRef"])
            if _source_session_file(args.session_id, cp["workspace"]["checkout"]) != tx["sourceSessionFile"]:
                raise ValueError("current source file does not match reserved transition")
        if args.command == "transition-bind-child":
            tx = store.reserve_child_file(tx["id"], source_session=args.session_id)
        elif args.command == "transition-stage":
            if args.session_id != tx["sourceSession"] or not _transition_authorized(tx):
                raise ValueError("source identity or authority changed before launch")
            _verify_child_header(tx, empty=tx["state"] == "prepared")
            tx = store.stage(tx["id"], child_session_file=tx["childSessionFile"])
        elif args.command == "transition-launch":
            tx = store.request_launch(tx["id"], source_session=args.session_id, authorize=_transition_authorized,
                                      host_proof_hash=_launch_proof_hash(tx["id"], args.session_id))
        elif args.command in {"transition-cancel", "transition-abort-launch"}:
            tx = store.cancel(tx["id"], source_session=args.session_id,
                              before_exec_failure=args.reason if args.command == "transition-abort-launch" else None,
                              host_proof_hash=_launch_proof_hash(tx["id"], args.session_id)
                              if args.command == "transition-abort-launch" else None,
                              settle_isolation=_settle_isolation_for_cancel
                              if args.command == "transition-cancel" else None)
        elif args.command == "transition-attach":
            if quality.current_session_id() != args.session_id or str(Path.cwd().resolve()) != tx["targetCheckout"]:
                raise ValueError("attachment must run in the reserved child session and checkout")
            if os.environ.get("PI_SESSION_FILE") and Path(os.environ["PI_SESSION_FILE"]).resolve() != Path(tx["childSessionFile"]):
                raise ValueError("current persisted session does not match reserved child file")
            _verify_child_header(tx)
            def attached(bead: str, session: str) -> bool:
                owner = quality.session_work_item(session)
                if owner not in {None, bead}:
                    raise ValueError("child session belongs to another Bead")
                return owner == bead
            def attach(bead: str, session: str) -> None:
                def claim() -> None:
                    # attach already checked source outcome under its lifecycle
                    # lock, which also excludes canonical success recording.
                    # Quality is locked here: do not reacquire its ledger.
                    if not _transition_effects_authorized(tx):
                        raise WorkAuthorityUnavailable("transition authority changed before target claim")
                    code, _, _ = run_beads_json(["update", bead, "--claim"])
                    if code:
                        raise ValueError("target Beads claim failed; preserve reserved transition")
                quality.capture_session_link(session, bead, beads_runner=run_beads_json, before_link=claim)
            tx = store.attach(tx["id"], session_id=args.session_id, authorize=_transition_authorized,
                              attach=attach, attached=attached)
    return _transition_response(tx)
