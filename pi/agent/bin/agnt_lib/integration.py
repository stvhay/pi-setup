from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from .core import utc_now

_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_OPAQUE_ID = re.compile(r"[0-9a-f]{16}")
_POLL_SECONDS = 0.05
_COMMAND_CONFIG_PATTERNS = (
    r"merge\..*\.driver",
    r"filter\..*\.(clean|smudge|process)",
    r"branch\..*\.mergeoptions",
)


class IntegrationLockError(RuntimeError):
    def __init__(self, evidence: dict[str, Any]):
        super().__init__(str(evidence.get("status") or "integration-lock-error"))
        self.evidence = evidence


class IntegrationLockTimeout(IntegrationLockError):
    pass


class IntegrationLockCancelled(IntegrationLockError):
    pass


def _git(cwd: Path | str, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        worktree = str(Path(cwd).expanduser().resolve())
        overrides = (
            "core.hooksPath=/dev/null",
            "core.fsmonitor=false",
            "core.bare=false",
            f"core.worktree={worktree}",
            "commit.gpgSign=false",
            "merge.verifySignatures=false",
        )
        config = [item for value in overrides for item in ("-c", value)]
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return subprocess.run(
            ["git", *config, "-C", worktree, f"--work-tree={worktree}", *args],
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError:
        return subprocess.CompletedProcess([], 127, "", "")


def _common_git_dir(cwd: Path | str) -> Path:
    result = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if result.returncode != 0 or not result.stdout.strip():
        raise IntegrationLockError({"schemaVersion": 1, "status": "integration-unavailable"})
    common_dir = Path(result.stdout.strip()).resolve()
    if not common_dir.is_dir():
        raise IntegrationLockError({"schemaVersion": 1, "status": "integration-unavailable"})
    return common_dir


def _lock_file(cwd: Path | str, target_branch: str) -> tuple[Path, str]:
    common_dir = _common_git_dir(cwd)
    lock_id = hashlib.sha256(f"{common_dir}\0refs/heads/{target_branch}".encode()).hexdigest()[:16]
    parent = common_dir / "agnt"
    lock_dir = parent / "integration-locks"
    try:
        if parent.is_symlink() or lock_dir.is_symlink():
            raise OSError
        parent.mkdir(mode=0o700, exist_ok=True)
        lock_dir.mkdir(mode=0o700, exist_ok=True)
        parent.chmod(0o700)
        lock_dir.chmod(0o700)
    except OSError:
        raise IntegrationLockError({"schemaVersion": 1, "status": "integration-unavailable", "lockId": lock_id}) from None
    return lock_dir / f"{lock_id}.lock", lock_id


def _read_metadata(descriptor: int) -> tuple[dict[str, Any] | None, bool]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    raw = os.read(descriptor, 4096)
    if not raw:
        return None, False
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, True
    return (value if isinstance(value, dict) else None), True


def _write_metadata(descriptor: int, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    os.write(descriptor, payload)
    os.fsync(descriptor)


def _wait_evidence(status: str, lock_id: str, started: float, metadata: dict[str, Any] | None) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schemaVersion": 1,
        "status": status,
        "lockId": lock_id,
        "waitedMs": round((time.monotonic() - started) * 1000),
    }
    owner_id = metadata.get("ownerId") if isinstance(metadata, dict) else None
    if isinstance(owner_id, str) and _OPAQUE_ID.fullmatch(owner_id):
        evidence["holderId"] = owner_id
    return evidence


@contextmanager
def integration_semaphore(
    cwd: Path | str,
    *,
    target_branch: str,
    timeout_seconds: float = 30,
    cancel_check: Callable[[], bool] | None = None,
) -> Iterator[dict[str, Any]]:
    """Hold one target-ref integration semaphore shared by all linked worktrees."""
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must be non-negative")
    lock_path, lock_id = _lock_file(cwd, target_branch)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(lock_path, flags, 0o600)
        os.chmod(lock_path, 0o600)
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        raise IntegrationLockError({"schemaVersion": 1, "status": "integration-unavailable", "lockId": lock_id}) from None
    started = time.monotonic()
    acquired = False
    contended = False
    metadata: dict[str, Any] | None = None
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                if cancel_check is not None and cancel_check():
                    raise IntegrationLockCancelled(_wait_evidence("cancelled", lock_id, started, metadata))
                if contended and time.monotonic() - started >= timeout_seconds:
                    raise IntegrationLockTimeout(_wait_evidence("lock-timeout", lock_id, started, metadata))
                break
            except BlockingIOError:
                contended = True
                metadata, _present = _read_metadata(descriptor)
                if cancel_check is not None and cancel_check():
                    raise IntegrationLockCancelled(_wait_evidence("cancelled", lock_id, started, metadata))
                if time.monotonic() - started >= timeout_seconds:
                    raise IntegrationLockTimeout(_wait_evidence("lock-timeout", lock_id, started, metadata))
                time.sleep(min(_POLL_SECONDS, max(0, timeout_seconds - (time.monotonic() - started))))

        previous, previous_present = _read_metadata(descriptor)
        previous_state = previous.get("state") if isinstance(previous, dict) else None
        recovered = previous_present and previous_state != "released"
        previous_owner = previous.get("ownerId") if isinstance(previous, dict) else None
        owner_id = uuid4().hex[:16]
        evidence: dict[str, Any] = {
            "schemaVersion": 1,
            "status": "acquired",
            "lockId": lock_id,
            "ownerId": owner_id,
            "waitedMs": round((time.monotonic() - started) * 1000),
            "recoveredStaleHolder": recovered,
        }
        if recovered and isinstance(previous_owner, str) and _OPAQUE_ID.fullmatch(previous_owner):
            evidence["recoveredOwnerId"] = previous_owner
        _write_metadata(
            descriptor,
            {
                "acquiredAt": utc_now(),
                "lockId": lock_id,
                "ownerId": owner_id,
                "state": "held",
            },
        )
        try:
            yield evidence
        finally:
            try:
                _write_metadata(
                    descriptor,
                    {
                        "lockId": lock_id,
                        "ownerId": owner_id,
                        "releasedAt": utc_now(),
                        "state": "released",
                    },
                )
            except OSError:
                pass
    except OSError:
        raise IntegrationLockError({"schemaVersion": 1, "status": "integration-unavailable", "lockId": lock_id}) from None
    finally:
        if acquired:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            os.close(descriptor)
        except OSError:
            pass


def _result(status: str, lock: dict[str, Any] | None = None, **values: Any) -> dict[str, Any]:
    result = {"schemaVersion": 1, "status": status}
    if lock:
        for key in ("lockId", "ownerId", "waitedMs", "recoveredStaleHolder", "recoveredOwnerId"):
            if key in lock:
                result[key] = lock[key]
    result.update(values)
    return result


def _head(cwd: Path | str) -> str | None:
    result = _git(cwd, "rev-parse", "--verify", "HEAD")
    value = result.stdout.strip().lower()
    return value if result.returncode == 0 and _OID.fullmatch(value) else None


def _status(cwd: Path | str) -> str | None:
    result = _git(cwd, "status", "--porcelain=v1", "--untracked-files=all")
    return result.stdout if result.returncode == 0 else None


def _merge_in_progress(cwd: Path | str) -> bool:
    return _git(cwd, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0


def _has_command_config(cwd: Path | str) -> bool | None:
    result = _git(cwd, "config", "--show-scope", "--null", "--name-only", "--list")
    if result.returncode != 0:
        return None
    fields = result.stdout.split("\0")
    if fields[-1:] == [""]:
        fields.pop()
    if len(fields) % 2:
        return None
    return any(
        scope not in {"system", "global"}
        and any(re.fullmatch(pattern, key.lower()) for pattern in _COMMAND_CONFIG_PATTERNS)
        for scope, key in zip(fields[::2], fields[1::2])
    )


def integrate_local_commit(
    cwd: Path | str,
    *,
    target_branch: str,
    expected_head: str,
    source_sha: str,
    timeout_seconds: float = 30,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Merge one exact local commit after target-scoped serialization and revalidation."""
    expected_head = expected_head.lower()
    source_sha = source_sha.lower()
    branch_check = _git(cwd, "check-ref-format", "--branch", target_branch)
    if branch_check.returncode != 0 or not _OID.fullmatch(expected_head) or not _OID.fullmatch(source_sha):
        return _result("invalid-request")
    lock: dict[str, Any] | None = None
    try:
        with integration_semaphore(
            cwd,
            target_branch=target_branch,
            timeout_seconds=timeout_seconds,
            cancel_check=cancel_check,
        ) as lock:
            branch = _git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")
            if branch.returncode != 0 or branch.stdout.strip() != target_branch:
                return _result("target-branch-mismatch", lock, sourceSha=source_sha)
            before = _head(cwd)
            if before is None:
                return _result("integration-unavailable", lock, sourceSha=source_sha)
            if before != expected_head:
                return _result("target-diverged", lock, sourceSha=source_sha, targetHeadBefore=before)
            source = _git(cwd, "rev-parse", "--verify", f"{source_sha}^{{commit}}")
            if source.returncode != 0 or source.stdout.strip().lower() != source_sha:
                return _result("source-unavailable", lock, sourceSha=source_sha, targetHeadBefore=before)
            command_config = _has_command_config(cwd)
            if command_config is None:
                return _result("integration-unavailable", lock, sourceSha=source_sha, targetHeadBefore=before)
            if command_config:
                return _result("unsafe-git-config", lock, sourceSha=source_sha, targetHeadBefore=before)
            status_before = _status(cwd)
            if status_before is None:
                return _result("integration-unavailable", lock, sourceSha=source_sha, targetHeadBefore=before)
            if status_before or _merge_in_progress(cwd):
                return _result("target-dirty", lock, sourceSha=source_sha, targetHeadBefore=before)

            merged = _git(cwd, "merge", "--no-edit", "--no-verify", source_sha)
            if merged.returncode != 0:
                if _merge_in_progress(cwd):
                    aborted = _git(cwd, "merge", "--abort")
                    after = _head(cwd)
                    status_after = _status(cwd)
                    restored = (
                        aborted.returncode == 0
                        and after == before
                        and status_after == ""
                        and not _merge_in_progress(cwd)
                    )
                    return _result(
                        "conflict" if restored else "recovery-required",
                        lock,
                        sourceSha=source_sha,
                        targetHeadBefore=before,
                        targetHeadAfter=after,
                        rollbackVerified=restored,
                    )
                after = _head(cwd)
                unchanged = after == before and _status(cwd) == "" and not _merge_in_progress(cwd)
                return _result(
                    "merge-failed" if unchanged else "recovery-required",
                    lock,
                    sourceSha=source_sha,
                    targetHeadBefore=before,
                    targetHeadAfter=after,
                    rollbackVerified=unchanged,
                )

            after = _head(cwd)
            branch_after = _git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")
            ancestor = _git(cwd, "merge-base", "--is-ancestor", source_sha, "HEAD")
            verified = (
                after is not None
                and branch_after.returncode == 0
                and branch_after.stdout.strip() == target_branch
                and ancestor.returncode == 0
                and _status(cwd) == ""
                and not _merge_in_progress(cwd)
            )
            if not verified:
                return _result(
                    "recovery-required",
                    lock,
                    sourceSha=source_sha,
                    targetHeadBefore=before,
                    targetHeadAfter=after,
                    verificationPassed=False,
                )
            return _result(
                "already-integrated" if after == before else "integrated",
                lock,
                sourceSha=source_sha,
                targetHeadBefore=before,
                targetHeadAfter=after,
                verificationPassed=True,
            )
    except (IntegrationLockTimeout, IntegrationLockCancelled, IntegrationLockError) as exc:
        return dict(exc.evidence)
    except (OSError, ValueError):
        return _result("integration-unavailable", lock)


__all__ = [
    "IntegrationLockCancelled",
    "IntegrationLockError",
    "IntegrationLockTimeout",
    "integrate_local_commit",
    "integration_semaphore",
]
