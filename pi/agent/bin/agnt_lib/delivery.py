"""Recoverable delivery receipts over trusted concrete adapters, not a shell sandbox.

Lock order: sorted resource leases -> short receipt-journal lock. Authority is
rechecked without holding the journal. Adapters own native identity/effect proof;
model-supplied booleans are not an execution adapter.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator, Protocol
from uuid import uuid4

from .authority import AuthorityStore, _strings, _text, fingerprint, repository_identity
from .core import utc_now

_MAX_BYTES = 16 * 1024 * 1024
_MAX_ATTEMPTS = 3
_REF = re.compile(r"[a-f0-9]{32}\Z")
_PHASES = {"prepared", "started", "applied", "not-applied", "uncertain", "cancelled"}
_ACTIVE = {"prepared", "started", "not-applied", "uncertain"}
_TRANSITIONS = {
    "prepared": {"started", "applied", "not-applied", "uncertain", "cancelled"},
    "started": {"applied", "not-applied", "uncertain"},
    "not-applied": {"started", "applied", "not-applied", "uncertain", "cancelled"},
    "uncertain": {"applied", "not-applied", "uncertain"},
    "applied": set(), "cancelled": set(),
}
_PRECONDITIONS = {"identity", "platform", "effectClosure", "verification", "recovery"}


class EffectAdapter(Protocol):
    kind: str

    def resolve(self) -> dict[str, Any]: ...
    def execute(self, action: dict[str, Any], *, lease_fds: tuple[int, ...]) -> None: ...
    def observe(self, action: dict[str, Any], *, attempted: bool) -> dict[str, Any]: ...


def _action(value: Any, kind: str, *, canonicalize: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion", "adapter", "repository", "bead", "effects", "decisionRefs", "target", "source",
        "preconditions", "verification", "recovery", "facts",
    } or type(value.get("schemaVersion")) is not int or value.get("schemaVersion") != 1 or value.get("adapter") != kind:
        raise ValueError("invalid delivery action schema or adapter")
    result = copy.deepcopy(value)
    for key in ("adapter", "repository", "bead", "recovery"):
        _text(result[key], key)
    _strings(result["effects"], "delivery effects")
    _strings(result["decisionRefs"], "decision refs", empty=True)
    _strings(result["verification"], "verification evidence")
    if not isinstance(result["facts"], dict) or not result["facts"]:
        raise ValueError("material native delivery facts are missing")
    target, source = result["target"], result["source"]
    if not isinstance(target, dict) or set(target) != {"identity", "repository", "verified", "resources"}:
        raise ValueError("invalid delivery target")
    _text(target["identity"], "target identity")
    _text(target["repository"], "target repository")
    target["resources"] = sorted(_strings(target["resources"], "physical resource identities"))
    if not isinstance(source, dict) or set(source) != {"identity", "rule"}:
        raise ValueError("invalid resolved delivery source")
    _text(source["identity"], "source identity")
    _text(source["rule"], "source rule")
    if (target["verified"] is not True or not isinstance(result["preconditions"], dict)
            or set(result["preconditions"]) != _PRECONDITIONS
            or any(result["preconditions"][key] is not True for key in _PRECONDITIONS)):
        raise ValueError("delivery identity, platform, effect closure, verification or recovery is unproven")
    if canonicalize:
        result["repository"] = repository_identity(result["repository"])
        target["repository"] = repository_identity(target["repository"])
    if target["repository"] != result["repository"]:
        raise ValueError("delivery target repository is foreign")
    fingerprint(result)  # Reject non-JSON/non-finite adapter output before persistence.
    return result


def _causal_keys(action: dict[str, Any]) -> list[str]:
    # Changing Bead, assignment, adapter label or receipt ID must not reset the
    # retry budget for the same physical resource and requested artifact.
    return [fingerprint([resource, action["source"]["identity"]]) for resource in action["target"]["resources"]]


def _phase(receipt: dict[str, Any]) -> str:
    return receipt["events"][-1]["phase"]


class DeliveryStore:
    def __init__(self, root: Path | None = None, *, authority: AuthorityStore | None = None):
        # Owner-global resource locks also serialize distinct clones/projects
        # that resolve to the same physical provider target.
        self.root = Path(root) if root is not None else Path.home() / ".pi" / "runtime" / "delivery"
        self.authority = authority if authority is not None else AuthorityStore()

    @contextmanager
    def _lock(self, name: str, *, blocking: bool = True) -> Iterator[int]:
        if any(path.is_symlink() for path in (self.root, *self.root.parents)):
            raise ValueError("delivery receipt path must not contain a symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.root.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("delivery receipt directory must be owner-private")
        fd = os.open(self.root / f"{name}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError:
                raise ValueError("delivery resource is busy; current attempt retains ownership") from None
            yield fd
        finally:
            os.close(fd)

    @contextmanager
    def _journal(self) -> Iterator[dict[str, Any]]:
        with self._lock("journal"):
            yield self._read()

    @contextmanager
    def _leases(self, resources: list[str]) -> Iterator[tuple[int, ...]]:
        with ExitStack() as stack:
            fds = tuple(stack.enter_context(self._lock("resource-" + fingerprint(resource)[7:], blocking=False))
                        for resource in sorted(resources))
            yield fds

    def _read(self) -> dict[str, Any]:
        path = self.root / "state.json"
        if path.is_symlink():
            raise ValueError("delivery receipt state must not be a symlink")
        if not path.exists():
            return {"schemaVersion": 1, "receipts": {}}
        info = path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > _MAX_BYTES):
            raise ValueError("invalid private delivery receipt state")
        try:
            envelope = json.loads(path.read_text())
            if not isinstance(envelope, dict) or set(envelope) != {"state", "fingerprint"}:
                raise ValueError
            state = envelope["state"]
            if (not isinstance(state, dict) or set(state) != {"schemaVersion", "receipts"}
                    or type(state["schemaVersion"]) is not int or state["schemaVersion"] != 1 or not isinstance(state["receipts"], dict)
                    or envelope["fingerprint"] != fingerprint(state)):
                raise ValueError
            for ref, receipt in state["receipts"].items():
                if (not _REF.fullmatch(ref) or not isinstance(receipt, dict) or set(receipt) != {
                    "id", "assignment", "action", "actionFingerprint", "authority", "causalKeys", "events",
                } or receipt["id"] != ref):
                    raise ValueError
                _text(receipt["assignment"], "assignment")
                action = _action(receipt["action"], receipt["action"]["adapter"], canonicalize=False)
                if (receipt["actionFingerprint"] != fingerprint(action) or receipt["causalKeys"] != _causal_keys(action)
                        or not isinstance(receipt["authority"], dict)
                        or receipt["authority"].get("kind") != "standing-policy"
                        or not isinstance(receipt["events"], list) or not receipt["events"]):
                    raise ValueError
                previous = None
                for event in receipt["events"]:
                    if not isinstance(event, dict) or set(event) != {"phase", "at", "evidence"} or event["phase"] not in _PHASES:
                        raise ValueError
                    _text(event["at"], "receipt timestamp")
                    if (not isinstance(event["evidence"], dict)
                            or (previous is None and event["phase"] != "prepared")
                            or (previous is not None and event["phase"] not in _TRANSITIONS[previous])):
                        raise ValueError
                    previous = event["phase"]
            return state
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ValueError("invalid delivery receipt state") from None

    def _write(self, state: dict[str, Any]) -> None:
        encoded = json.dumps({"state": state, "fingerprint": fingerprint(state)}, sort_keys=True, allow_nan=False).encode() + b"\n"
        if len(encoded) > _MAX_BYTES:
            raise ValueError("delivery receipt capacity exceeded; preserve history and reconcile before maintenance")
        fd, name = tempfile.mkstemp(prefix=".receipt-", dir=self.root)
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
    def _result(receipt: dict[str, Any], *, status: str | None = None, reason: str | None = None) -> dict[str, Any]:
        return {"schemaVersion": 1, "status": status or _phase(receipt), "receipt": copy.deepcopy(receipt),
                **({"reason": reason} if reason else {})}

    @staticmethod
    def _receipt(state: dict[str, Any], ref: str) -> dict[str, Any]:
        if not isinstance(ref, str) or not _REF.fullmatch(ref) or ref not in state["receipts"]:
            raise ValueError("delivery receipt is unavailable")
        return state["receipts"][ref]

    def _event(self, ref: str, phase: str, evidence: dict[str, Any]) -> dict[str, Any]:
        with self._journal() as state:
            receipt = self._receipt(state, ref)
            if _phase(receipt) in {"applied", "cancelled"}:
                return self._result(receipt)
            last = receipt["events"][-1]
            if last["phase"] != phase or last["evidence"] != evidence:
                if phase not in _TRANSITIONS[last["phase"]]:
                    raise ValueError("invalid delivery receipt transition")
                receipt["events"].append({"phase": phase, "at": utc_now(), "evidence": copy.deepcopy(evidence)})
                self._write(state)
            return self._result(receipt)

    def inspect(self, ref: str) -> dict[str, Any]:
        with self._journal() as state:
            return self._result(self._receipt(state, ref))

    def find_pending(self, assignment: str, action_fingerprint: str) -> dict[str, Any] | None:
        """Recover an unbound reservation without creating authority or effects."""
        with self._journal() as state:
            matches = [receipt for receipt in state["receipts"].values()
                       if receipt["assignment"] == assignment and receipt["actionFingerprint"] == action_fingerprint
                       and _phase(receipt) in _ACTIVE]
            if len(matches) > 1:
                raise ValueError("ambiguous delivery reservation; preserve evidence")
            return self._result(matches[0]) if matches else None

    def prepare(self, assignment: str, adapter: EffectAdapter, *,
                expected_action_fingerprint: str | None = None) -> dict[str, Any]:
        try:
            action = _action(adapter.resolve(), adapter.kind)
            if expected_action_fingerprint is not None and fingerprint(action) != expected_action_fingerprint:
                raise ValueError("delivery action changed from reserved intent")
            decision = self.authority.check(assignment, action)
            if decision["status"] != "active":
                raise ValueError(decision["reason"])
        except Exception:
            return {"schemaVersion": 1, "status": "blocked", "reason": "delivery action or authority is unproven"}
        resources = set(action["target"]["resources"])
        with self._journal() as state:
            for receipt in state["receipts"].values():
                if _phase(receipt) not in _ACTIVE or not resources.intersection(receipt["action"]["target"]["resources"]):
                    continue
                if (_phase(receipt) in {"prepared", "not-applied"} and receipt["assignment"] == assignment
                        and receipt["actionFingerprint"] == fingerprint(action) and receipt["authority"] == decision["source"]):
                    return self._result(receipt)
                return self._result(receipt, status="blocked", reason="resource has a reserved or unresolved effect; reconcile its receipt")
            ref = uuid4().hex
            receipt = {"id": ref, "assignment": assignment, "action": action, "actionFingerprint": fingerprint(action),
                       "authority": decision["source"], "causalKeys": _causal_keys(action),
                       "events": [{"phase": "prepared", "at": utc_now(), "evidence": {"verification": action["verification"]}}]}
            state["receipts"][ref] = receipt
            self._write(state)
            return self._result(receipt)

    def _observe(self, receipt: dict[str, Any], adapter: EffectAdapter) -> dict[str, Any]:
        action = receipt["action"]
        try:
            if adapter.kind != action["adapter"]:
                raise ValueError
            value = adapter.observe(copy.deepcopy(action), attempted=any(event["phase"] == "started" for event in receipt["events"]))
            if (not isinstance(value, dict) or value.get("status") not in {"applied", "not-applied", "uncertain"}
                    or value.get("targetIdentity") != action["target"]["identity"]
                    or value.get("sourceIdentity") != action["source"]["identity"]):
                raise ValueError
            refs = _strings(value.get("evidenceRefs"), "provider observation evidence")
            return {"status": value["status"], "targetIdentity": value["targetIdentity"],
                    "sourceIdentity": value["sourceIdentity"], "evidenceRefs": refs}
        except Exception:
            return {"status": "uncertain", "reason": "adapter observation is unavailable or unbound"}

    def observe_current(self, ref: str, adapter: EffectAdapter) -> dict[str, Any]:
        """Fresh read under resource leases; never rewrite terminal history."""
        receipt = self.inspect(ref)["receipt"]
        with self._leases(receipt["action"]["target"]["resources"]):
            receipt = self.inspect(ref)["receipt"]
            observation = self._observe(receipt, adapter)
            return {"schemaVersion": 1, "status": observation["status"], "historicalStatus": _phase(receipt),
                    "receipt": receipt, "observation": observation}

    def reconcile(self, ref: str, adapter: EffectAdapter) -> dict[str, Any]:
        receipt = self.inspect(ref)["receipt"]
        with self._leases(receipt["action"]["target"]["resources"]):
            return self._reconcile_locked(ref, adapter)

    def _reconcile_locked(self, ref: str, adapter: EffectAdapter) -> dict[str, Any]:
        receipt = self.inspect(ref)["receipt"]
        if _phase(receipt) in {"applied", "cancelled"}:
            return self._result(receipt)
        observation = self._observe(receipt, adapter)
        return self._event(ref, observation["status"], observation)

    def cancel(self, ref: str, reason: str) -> dict[str, Any]:
        _text(reason, "cancellation reason")
        receipt = self.inspect(ref)["receipt"]
        with self._leases(receipt["action"]["target"]["resources"]):
            receipt = self.inspect(ref)["receipt"]
            if _phase(receipt) not in {"prepared", "not-applied"}:
                return self._result(receipt, status="blocked", reason="only unstarted or definitely unapplied effects may be cancelled")
            return self._event(ref, "cancelled", {"reason": reason})

    def _authorized(self, receipt: dict[str, Any]) -> bool:
        decision = self.authority.check(receipt["assignment"], receipt["action"])
        return decision["status"] == "active" and decision["source"] == receipt["authority"]

    def execute(self, ref: str, adapter: EffectAdapter) -> dict[str, Any]:
        receipt = self.inspect(ref)["receipt"]
        with self._leases(receipt["action"]["target"]["resources"]) as lease_fds:
            receipt = self.inspect(ref)["receipt"]
            phase = _phase(receipt)
            if phase in {"applied", "cancelled"}:
                return self._result(receipt)  # Historical receipt, not a fresh provider health claim.
            if phase in {"started", "uncertain"}:
                return self._reconcile_locked(ref, adapter)  # Never replay during reconciliation.
            try:
                current = _action(adapter.resolve(), adapter.kind)
                if fingerprint(current) != receipt["actionFingerprint"] or not self._authorized(receipt):
                    raise ValueError
            except Exception:
                return self._result(receipt, status="blocked", reason="prepared action or authority changed; no effect issued")
            observation = self._observe(receipt, adapter)
            if observation["status"] != "not-applied":
                return self._event(ref, observation["status"], observation)
            with self._journal() as state:
                attempts = sum(event["phase"] == "started" for prior in state["receipts"].values()
                               if set(prior["causalKeys"]).intersection(receipt["causalKeys"]) for event in prior["events"])
            if attempts >= _MAX_ATTEMPTS:
                return self._result(receipt, status="blocked", reason="delivery retry budget exhausted; preserve evidence and stop")
            if not self._authorized(receipt):
                return self._result(receipt, status="blocked", reason="authority changed before execution")
            self._event(ref, "started", {"attempt": attempts + 1})
            if not self._authorized(receipt):
                return self._event(ref, "not-applied", {"reason": "authority changed before native call", "evidenceRefs": ["local:pre-effect-authority-check"]})
            try:
                adapter.execute(copy.deepcopy(receipt["action"]), lease_fds=lease_fds)
            except Exception:
                # Exceptions and process exit codes are not proof of absence.
                # BaseException intentionally leaves durable started state for crash recovery.
                pass
            return self._reconcile_locked(ref, adapter)
