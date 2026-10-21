"""Standing delivery authority; not a shell sandbox or a quality experiment grant.

The owner store is trusted local runtime state. Historical import deliberately
records weaker provenance; it does not assert that an old input channel survived.
Only the explicit admission operation can activate a policy. Checking project
metadata never admits a policy or creates an assignment.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any, Iterator

_POLICY = Path(__file__).resolve().parents[2] / "authority" / "full-delivery.json"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
_MAX_BYTES = 4 * 1024 * 1024


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _strings(value: Any, name: str, *, empty: bool = False) -> list[str]:
    if (not isinstance(value, list) or (not value and not empty)
            or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in value)
            or len(set(value)) != len(value)):
        raise ValueError(f"invalid {name}")
    return list(value)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 16000:
        raise ValueError(f"invalid {name}")
    return value


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid assignment identifier")
    return value


def load_policy() -> dict[str, Any]:
    return json.loads(_POLICY.read_text())


def _policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion", "id", "projects", "effects", "exclusions", "requires", "expiry",
    } or value.get("schemaVersion") != 1:
        raise ValueError("invalid standing policy")
    template = load_policy()
    for key in ("id", "projects", "expiry", "requires"):
        if value[key] != template[key]:
            raise ValueError(f"unsupported policy {key}")
    effects = _strings(value["effects"], "policy effects")
    exclusions = _strings(value["exclusions"], "policy exclusions")
    if (not set(effects) <= set(template["effects"])
            or not set(exclusions) >= set(template["exclusions"])
            or set(effects) & set(exclusions)):
        raise ValueError("policy exceeds supported ceiling")
    return copy.deepcopy(value)


def repository_identity(repository: str) -> str:
    # Git common directory binds sibling worktrees to one repository. Non-Git
    # projects use their canonical directory. Checkout ownership is separate.
    path = Path(_text(repository, "repository")).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("repository must be an existing absolute directory")
    from .runtime_paths import _git_context

    context = _git_context(path.resolve())
    return context[2].removeprefix("git:") if context else str(path.resolve())


class AuthorityStore:
    def __init__(self, root: Path | None = None):
        # No cwd/project/environment override: project discovery cannot redirect
        # the owner's authority. Explicit root is for trusted hosts and fixtures.
        self.root = Path(root) if root is not None else Path.home() / ".pi" / "authority"

    @contextmanager
    def locked(self) -> Iterator[dict[str, Any]]:
        for path in (self.root, *self.root.parents):
            if path.is_symlink():
                raise ValueError("authority path must not contain symlinks")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.root.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("authority directory must be owner-private")
        fd = os.open(self.root / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield self._read()
        finally:
            os.close(fd)

    def _read(self) -> dict[str, Any]:
        path = self.root / "state.json"
        if path.is_symlink():
            raise ValueError("authority state must not be a symlink")
        if not path.exists():
            return {"schemaVersion": 1, "revision": 0, "admission": None,
                    "revocation": None, "assignments": {}}
        info = path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > _MAX_BYTES):
            raise ValueError("invalid private authority state")
        state = json.loads(path.read_text())
        if (not isinstance(state, dict) or set(state) != {
            "schemaVersion", "revision", "admission", "revocation", "assignments",
        } or state["schemaVersion"] != 1 or type(state["revision"]) is not int
                or state["revision"] < 0 or not isinstance(state["assignments"], dict)):
            raise ValueError("invalid authority state schema")
        if state["admission"] is not None:
            admission = state["admission"]
            self._validate_historical(admission["record"])
            if admission["fingerprint"] != fingerprint(admission["record"]):
                raise ValueError("authority admission fingerprint mismatch")
        if state["revocation"] is not None:
            _text(state["revocation"], "revocation")
        for key, assignment in state["assignments"].items():
            if _identifier(key) != assignment.get("id"):
                raise ValueError("invalid assignment state")
            self._validate_assignment(assignment)
        return state

    def _write(self, state: dict[str, Any]) -> None:
        encoded = json.dumps(state, sort_keys=True, allow_nan=False).encode() + b"\n"
        if len(encoded) > _MAX_BYTES:
            raise ValueError("authority store capacity exceeded")
        fd, name = tempfile.mkstemp(prefix=".state-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.root / "state.json")
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def _validate_historical(record: Any) -> None:
        if not isinstance(record, dict) or set(record) != {
            "kind", "owner", "policy", "consent", "evidenceRefs", "inputOrigin",
        } or record["kind"] != "historical-consent" or record["inputOrigin"] != "not-retained":
            raise ValueError("invalid historical consent record")
        _policy(record["policy"])
        _text(record["owner"], "owner")
        _text(record["consent"], "consent")
        _strings(record["evidenceRefs"], "consent evidence")

    def admit_historical(self, record: dict[str, Any]) -> dict[str, Any]:
        """Explicit owner-authorized migration, NOT an authenticity verifier.

        This is an installation/rollout operation. Ordinary authority checks do
        not call it. Historical import cannot replace, widen, or un-revoke an
        existing admission. A later new ceiling needs a distinct human path.
        """
        self._validate_historical(record)
        admission = {"record": copy.deepcopy(record), "fingerprint": fingerprint(record)}
        with self.locked() as state:
            if state["revocation"]:
                raise ValueError("standing authority is revoked")
            if state["admission"] is not None and state["admission"] != admission:
                raise ValueError("owner admission is immutable; cannot replace or widen")
            if state["admission"] is None:
                state["admission"] = admission
                state["revision"] += 1
                self._write(state)
            return self._inspection(state)

    @staticmethod
    def _inspection(state: dict[str, Any]) -> dict[str, Any]:
        admission = state["admission"]
        return {"schemaVersion": 1,
                "status": "revoked" if state["revocation"] else "active" if admission else "inactive",
                "revision": state["revision"],
                "provenance": admission["record"]["kind"] if admission else None,
                "policyFingerprint": fingerprint(admission["record"]["policy"]) if admission else None,
                "admissionFingerprint": admission["fingerprint"] if admission else None}

    def inspect(self) -> dict[str, Any]:
        with self.locked() as state:
            return self._inspection(state)

    def revoke(self, reason: str) -> dict[str, Any]:
        _text(reason, "revocation reason")
        with self.locked() as state:
            if state["revocation"] is None:
                state["revocation"] = reason
                state["revision"] += 1
                self._write(state)
            return self._inspection(state)

    @staticmethod
    def _validate_assignment(value: dict[str, Any]) -> None:
        if set(value) != {"id", "repository", "beads", "effects", "deniedEffects", "intentRef"}:
            raise ValueError("invalid assignment fields")
        _identifier(value["id"])
        _text(value["repository"], "repository")
        _text(value["intentRef"], "assignment intent")
        _strings(value["beads"], "assignment beads")
        _strings(value["effects"], "assignment effects")
        _strings(value["deniedEffects"], "assignment exclusions", empty=True)

    def assign(self, assignment_id: str, *, repository: str, beads: list[str], effects: list[str],
               intent_ref: str, denied_effects: list[str] | None = None) -> dict[str, Any]:
        assignment = {"id": _identifier(assignment_id), "repository": repository_identity(repository),
                      "beads": beads, "effects": effects, "intentRef": intent_ref,
                      "deniedEffects": denied_effects or []}
        self._validate_assignment(assignment)
        with self.locked() as state:
            previous = state["assignments"].get(assignment_id)
            if previous is not None and previous != assignment:
                raise ValueError("assignment is immutable; use a new explicit assignment")
            if previous is None:
                state["assignments"][assignment_id] = copy.deepcopy(assignment)
                state["revision"] += 1
                self._write(state)
        return copy.deepcopy(assignment)

    def assignment_for(self, repository: str, bead_id: str) -> dict[str, Any] | None:
        repository = repository_identity(repository)
        with self.locked() as state:
            matches = [item for item in state["assignments"].values()
                       if item["repository"] == repository and bead_id in item["beads"]]
            if len(matches) > 1:
                raise ValueError("multiple assignments match; resolve intent without widening restrictions")
            return copy.deepcopy(matches[0]) if matches else None

    def register_direct_assignment(self, repository: str, bead_id: str, *, scope_beads: list[str] | None = None) -> str:
        """Capture explicit work intent, never every ready Bead or an existing scope expansion."""
        identity = repository_identity(repository)
        beads = sorted(set([bead_id, *(scope_beads or [])]))
        with self.locked() as state:
            if self._inspection(state)["status"] != "active":
                raise ValueError("standing policy is not active")
            matches = [item for item in state["assignments"].values()
                       if item["repository"] == identity and set(beads) & set(item["beads"])]
            if len(matches) > 1:
                raise ValueError("multiple assignments match; resolve intent without widening restrictions")
            if matches:
                existing = matches[0]
                if scope_beads is not None and set(existing["beads"]) != set(beads):
                    raise ValueError("explicit work set conflicts with existing immutable scope")
                return existing["id"]
            assignment_id = "direct-" + fingerprint([identity, bead_id if scope_beads is None else beads])[7:31]
            assignment = {"id": assignment_id, "repository": identity, "beads": beads,
                          "effects": ["read", "external-read", "artifact-write", "beads-write", "repo-write",
                                      "git-commit", "work-transition", *(["worktree-create"] if len(beads) > 1 else [])],
                          "deniedEffects": [], "intentRef": f"bead:{bead_id}"}
            self._validate_assignment(assignment)
            if assignment_id in state["assignments"]:
                raise ValueError("assignment identity is immutable; resolve existing scope")
            state["assignments"][assignment_id] = assignment
            state["revision"] += 1
            self._write(state)
            return assignment_id

    def check(self, assignment_id: str, action: dict[str, Any], *,
              policy: dict[str, Any] | None = None) -> dict[str, Any]:
        def blocked(reason: str) -> dict[str, Any]:
            return {"schemaVersion": 1, "status": "blocked", "reason": reason, "allowedEffects": []}
        try:
            current = _policy(policy if policy is not None else load_policy())
            decision_failure = decision_constraints(action.get("decisionRefs", []), action.get("bead"))
            if decision_failure:
                return blocked(decision_failure)
            with self.locked() as state:
                inspection = self._inspection(state)
                if inspection["status"] != "active":
                    return blocked("standing policy is not active")
                ceiling = state["admission"]["record"]["policy"]
                if (not set(current["effects"]) <= set(ceiling["effects"])
                        or not set(current["exclusions"]) >= set(ceiling["exclusions"])):
                    return blocked("policy exceeds admitted ceiling")
                assignment = state["assignments"].get(_identifier(assignment_id))
                if assignment is None or action.get("bead") not in assignment["beads"]:
                    return blocked("action is outside assignment")
                repository = repository_identity(action.get("repository"))
                if repository != assignment["repository"]:
                    return blocked("repository is outside assignment")
                effects = _strings(action.get("effects"), "action effects")
                permitted = set(current["effects"]) & set(assignment["effects"])
                permitted -= set(current["exclusions"]) | set(assignment["deniedEffects"])
                if not set(effects) <= permitted:
                    return blocked("effect is outside effective authority")
                target = action.get("target")
                try:
                    target_repository = repository_identity(target.get("repository")) if isinstance(target, dict) else None
                except (OSError, ValueError, TypeError):
                    return blocked("target identity is unknown or foreign")
                if (not isinstance(target, dict) or target.get("verified") is not True
                        or not isinstance(target.get("identity"), str) or not target["identity"].strip()
                        or target_repository != repository):
                    return blocked("target identity is unknown or foreign")
                preconditions = action.get("preconditions")
                if not isinstance(preconditions, dict) or any(
                    preconditions.get(key) is not True for key in ("identity", "platform", "effectClosure")
                ):
                    return blocked("action precondition is unsatisfied")
                return {"schemaVersion": 1, "status": "active", "allowedEffects": effects,
                        "source": {"kind": "standing-policy", "assignment": assignment_id,
                                   "assignmentFingerprint": fingerprint(assignment),
                                   "admissionFingerprint": inspection["admissionFingerprint"],
                                   "policyFingerprint": fingerprint(current)},
                        "revision": state["revision"], "actionFingerprint": fingerprint(action)}
        except (OSError, ValueError, KeyError, TypeError):
            return blocked("invalid or unavailable standing authority state")


# Generic external_write/deploy/push/delete_files are intentionally absent:
# those need a concrete delivery adapter with independently resolved targets.
_LOCAL_EFFECTS = {"read_workspace": "read", "write_artifacts": "artifact-write",
                  "edit_files": "repo-write", "write_workspace": "repo-write",
                  "update_beads": "beads-write", "external_read": "external-read"}


def decision_constraints(refs: list[str], bead_id: str) -> str | None:
    """Re-read decisions; standing permission cannot answer or erase rejection."""
    from .work import normalize_bead, run_beads_json

    for ref in _strings(refs, "decision references", empty=True):
        _identifier(ref)
        code, data, _ = run_beads_json(["show", ref])
        bead = normalize_bead(data)
        if code != 0 or not bead or bead.get("id") != ref:
            return "decision constraint is unavailable"
        metadata = bead.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("pi", {}), dict):
            return "decision constraint is malformed"
        approval = metadata.get("pi", {}).get("approval", {})
        if not isinstance(approval, dict):
            return "decision constraint is malformed"
        if (bead.get("status") != "closed" or approval.get("targetBead") != bead_id
                or approval.get("status") not in {"approved", "answered"}
                or approval.get("resolver") != {"kind": "human-ui"}):
            return "decision constraint is pending, rejected, or unresolved"
    return None


def resolve_local_assignment(assignment_id: str, bead_id: str, effects: list[str],
                             decision_refs: list[str] | None = None) -> dict[str, Any]:
    try:
        mapped = sorted({_LOCAL_EFFECTS[item] for item in _strings(effects, "dispatch effects")})
        if "repo-write" not in mapped:
            raise ValueError("implementation worker requires repo-write authority")
        repository = repository_identity(str(Path.cwd()))
        action = {"repository": repository, "bead": bead_id, "effects": mapped,
                  "target": {"identity": repository, "repository": repository, "verified": True},
                  "preconditions": {"identity": True, "platform": True, "effectClosure": True}}
        if decision_refs:
            action["decisionRefs"] = decision_refs
        resolved = AuthorityStore().check(assignment_id, action)
        if resolved["status"] == "active":
            resolved["action"] = action
        return resolved
    except (OSError, KeyError, TypeError, ValueError):
        return {"schemaVersion": 1, "status": "blocked", "allowedEffects": [],
                "reason": "standing dispatch requires a local assignment or a concrete delivery adapter"}


def revalidate_standing_envelope(envelope: dict[str, Any], bead_id: str, *,
                                 workspace: str, effects: list[str]) -> str | None:
    try:
        source = envelope["source"]
        action = envelope["action"]
        if (source["kind"] != "standing-policy" or action["bead"] != bead_id
                or repository_identity(workspace) != repository_identity(action["repository"])
                or "repo-write" not in action["effects"]
                or not {_LOCAL_EFFECTS[item] for item in _strings(effects, "worker effects")} <= set(action["effects"])):
            raise ValueError("standing assignment mismatch")
        decision = AuthorityStore().check(source["assignment"], action)
        if decision["status"] != "active" or decision["source"] != source:
            raise ValueError("standing authority changed")
    except (OSError, ValueError, KeyError, TypeError):
        return "standing authority is unavailable, changed, or revoked"
    return None


def revalidate_bookkeeping_gate(envelope: dict[str, Any], bead_id: str, *, grant_resolver=None,
                                claim_directory: Path | None = None) -> str | None:
    """Recheck an explicit worker gate; never grant controller effects or renew claims."""
    from .orchestration import resolve_orchestration_authority
    from .quality import locally_revoked_capability_grant

    try:
        decision = envelope.get("decisionBead")
        if not isinstance(decision, str) or not decision or not bead_id:
            raise ValueError("missing exact gate or work item")
        if "targetBead" in envelope and envelope["targetBead"] != bead_id:
            raise ValueError("stored exact gate target does not match work item")
        kwargs = {"grant_resolver": grant_resolver} if grant_resolver is not None else {}
        resolved = resolve_orchestration_authority(
            {"pi": {"action": "implement", "approvalRefs": [decision]}}, bead_id=bead_id, **kwargs,
        )
        if resolved["status"] != "active" or any(
            resolved.get(key) != envelope.get(key) for key in ("decisionBead", "grantFingerprint", "grant", "allowedEffects")
        ):
            raise ValueError("exact gate changed")
        if locally_revoked_capability_grant(decision, resolved["grantFingerprint"], directory=claim_directory):
            raise ValueError("exact gate locally revoked")
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return "explicit worker gate is unavailable or changed"
    return None


def revalidate_native_beads_effect(envelope: dict[str, Any], bead_id: str, *, close_reason: str | None = None) -> str | None:
    """Check controller bookkeeping independently of a worker's effect list."""
    from .work_lifecycle import _bead, _blockers, _decision_refs

    try:
        error = revalidate_standing_envelope(
            envelope, bead_id, workspace=str(Path.cwd()), effects=["edit_files"],
        )
        if error:
            return error
        source = envelope["source"]
        canonical = _bead(bead_id)
        eligible = canonical.get("status") in {"open", "in_progress"}
        if close_reason is not None:
            eligible = eligible or (canonical.get("status") == "closed" and canonical.get("close_reason") == close_reason)
        if not eligible or _blockers(canonical):
            raise ValueError("canonical work is blocked or changed")
        action = dict(envelope["action"])
        action["effects"] = sorted(set(action["effects"]) | {"beads-write"})
        action["decisionRefs"] = sorted(set(action.get("decisionRefs", [])) | set(_decision_refs(canonical)))
        decision = AuthorityStore().check(source["assignment"], action)
        if decision["status"] != "active" or decision["source"] != source:
            raise ValueError("standing authority changed")
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return "standing authority does not permit the native Beads effect"
    return None


def cmd_authority(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt authority")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    sub.add_parser("template")
    admit = sub.add_parser("import-historical", help="explicit owner-authorized migration, not proof of input origin")
    admit.add_argument("--input-file", required=True)
    assign = sub.add_parser("assign", help="record current delegated intent; never enroll a project")
    assign.add_argument("--input-file", required=True)
    check = sub.add_parser("check")
    check.add_argument("assignment")
    check.add_argument("--input-file", required=True)
    revoke = sub.add_parser("revoke")
    revoke.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    store = AuthorityStore()
    try:
        payload = json.loads(Path(args.input_file).read_text()) if hasattr(args, "input_file") else None
        if args.command == "template":
            result = {"policy": load_policy(), "fingerprint": fingerprint(load_policy())}
        elif args.command == "inspect":
            result = store.inspect()
        elif args.command == "import-historical":
            result = store.admit_historical(payload)
        elif args.command == "assign":
            result = store.assign(**payload)
        elif args.command == "check":
            result = store.check(args.assignment, payload)
        else:
            result = store.revoke(args.reason)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"schemaVersion": 1, "status": "blocked", "reason": "invalid authority operation or private state"}), file=sys.stderr)
        return 2


__all__ = ["AuthorityStore", "cmd_authority"]
