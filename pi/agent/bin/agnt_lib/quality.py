from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from subprocess import run as run_process
from typing import Any, Iterator

from .runtime_paths import resolve_runtime_directory

BEAD_ID = re.compile(r"[a-z][a-z0-9]*-[A-Za-z0-9._-]+\Z")
OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
EVIDENCE_REF = re.compile(
    r"(?:artifact|invocation|observation|result|run|trace):[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z"
)
SENSITIVE_REF = re.compile(
    r"(?:api.?key|authorization|bearer|password|secret|token|gh[pousr]_|github_pat_|glpat-|xox[baprs]-|npm_|pypi-|[sp]k-|AKIA[0-9A-Z]{16})",
    re.IGNORECASE,
)
JWT_REF = re.compile(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\Z")
TASK_OUTCOMES = frozenset({"success", "partial", "failure", "unclear"})
ACTIVITY_IDS = (
    "capture",
    "work-learning",
    "architecture-coherence",
    "capability-calibration",
    "quality-system-review",
)
QUALITY_ACTIVITY_LABELS = {
    activity: f"quality:{activity}" for activity in ACTIVITY_IDS
}
LEGACY_ACTIVITY_LABELS = {
    "maintenance:design-review": "architecture-coherence",
    "maintenance:architecture-review": "architecture-coherence",
    "maintenance:simplification": "architecture-coherence",
    "maintenance:workflow-retro": "work-learning",
    "maintenance:context-health": "architecture-coherence",
    "maintenance:improvement-review": "work-learning",
    "maintenance:lessons-harvest": "work-learning",
}
LEGACY_GIT_CHECKPOINT_LABELS = frozenset({
    "maintenance:design-review",
    "maintenance:architecture-review",
    "maintenance:simplification",
    "maintenance:workflow-retro",
    "maintenance:context-health",
})
LEGACY_WORK_LEARNING_CHECKPOINT_LABELS = frozenset({
    "maintenance:improvement-review",
    "maintenance:lessons-harvest",
})
DEFAULT_SIGNAL_THRESHOLDS = {
    "closedImplementationBeads": 5,
    "commits": 10,
    "failedOrBlockedRuns": 2,
    "humanBlockers": 2,
    "contextWarnings": 3,
    "healthWarnings": 3,
    "healthFailures": 1,
    "eligibleUnreviewedSessions": 5,
}
ACTIVITY_FIELDS = frozenset({
    "id",
    "source",
    "inputs",
    "trigger",
    "owner",
    "method",
    "output",
    "receiver",
    "acceptanceRule",
    "evidence",
    "budget",
    "escalation",
    "retirementCondition",
})
CONTROL_PLAN_PATH = Path(__file__).resolve().parents[2] / "quality" / "control-plan.json"
LEDGER_NAME = "ledger.jsonl"
RECEIPTS_NAME = "receipts.jsonl"
APPLICATIONS_NAME = "applications.jsonl"
MAX_EVIDENCE_REFS = 16
MAX_LEDGER_BYTES = 16 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 64 * 1024
HASH_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")
FINDING_STATUSES = ("unverified", "confirmed", "refuted", "unresolved")
VERIFICATION_METHODS = frozenset({"test", "reproducer", "inspection", "profile", "specification"})
EVIDENCE_REF_FIELDS = frozenset({
    "ref",
    "source",
    "availability",
    "provenance",
    "integrity",
    "sensitivity",
    "retention",
})
EVIDENCE_AVAILABILITY = frozenset({"available", "partial", "unavailable", "unknown"})
EVIDENCE_INTEGRITY = frozenset({"verified", "unverified", "unknown"})
EVIDENCE_SENSITIVITY = frozenset({"public", "internal", "private", "restricted"})
EVIDENCE_RETENTION = frozenset({"session", "work-item", "cohort", "durable"})
FINDING_CORE_FIELDS = frozenset({
    "schemaVersion",
    "id",
    "activity",
    "source",
    "category",
    "severity",
    "claim",
    "status",
    "evidenceRefs",
    "verification",
    "proposedIntervention",
})
REVIEW_ASSIGNMENT_FIELDS = frozenset({
    "schemaVersion",
    "assignmentId",
    "activity",
    "action",
    "scope",
    "evidenceRefs",
    "rubric",
    "privacyConstraints",
    "modelConstraints",
    "outputContract",
    "stopRules",
    "authority",
})
REVIEW_ASSIGNMENT_ID = re.compile(r"review-[0-9a-f]{64}\Z")
MAX_REVIEW_ASSIGNMENT_ITEMS = 20
MAX_LANGFUSE_ANNOTATION_ITEMS = 16
LANGFUSE_ANNOTATION_GAPS = frozenset({
    "empty-queue",
    "item-limit",
    "items-incomplete",
    "items-unavailable",
    "missing-item-scores",
    "missing-reviewer",
    "missing-score-config",
    "pending-items",
    "queue-incomplete",
    "queue-unavailable",
    "score-config-limit",
    "score-configs-incomplete",
    "score-configs-unavailable",
    "score-limit",
    "scores-incomplete",
    "scores-unavailable",
    "unmatched-annotations",
})
AUTHORITY_CLAIM_FIELDS = frozenset({
    "accepted",
    "acceptance",
    "allowedEffects",
    "approved",
    "authority",
    "authorization",
    "grant",
    "humanApproval",
    "mode",
})
EXTERNAL_RESULT_FIELDS = frozenset({
    "schemaVersion",
    "source",
    "artifact",
    "scope",
    "category",
    "status",
    "evidenceRefs",
    "provenance",
    "gaps",
    "resumptionPath",
})
EXTERNAL_RESULT_STATUSES = frozenset({"completed", "partial", "lost", "uncertain"})


class SessionWorkItemConflict(ValueError):
    pass


class SessionOutcomeUnavailable(ValueError):
    pass


class SessionUnassigned(ValueError):
    pass


def current_session_id() -> str:
    session_id = os.environ.get("PI_SESSION_ID")
    if session_id:
        return _session_id(session_id)
    session_file = os.environ.get("PI_SESSION_FILE")
    if not session_file:
        raise ValueError("current Pi session is unavailable")
    return _session_id(Path(session_file).stem)


def _session_id(value: Any) -> str:
    if not isinstance(value, str) or not OPAQUE_ID.fullmatch(value):
        raise ValueError("current Pi session is unavailable")
    return value


def _bead_id(value: Any) -> str:
    if not isinstance(value, str) or not BEAD_ID.fullmatch(value):
        raise ValueError("bead ID is malformed")
    return value


def _evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_EVIDENCE_REFS:
        raise ValueError("evidence references are invalid")
    for ref in value:
        body = ref.partition(":")[2] if isinstance(ref, str) else ""
        if (
            not isinstance(ref, str)
            or not EVIDENCE_REF.fullmatch(ref)
            or SENSITIVE_REF.search(ref)
            or JWT_REF.fullmatch(body)
        ):
            raise ValueError("evidence reference is unsafe")
    return value


def _captured_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _quality_directory(directory: str | os.PathLike[str] | None = None) -> Path:
    path = Path(directory).expanduser() if directory is not None else resolve_runtime_directory("quality")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise OSError("quality runtime path is not a directory")
    path.chmod(0o700)
    return path


@contextmanager
def _locked_store(
    directory: str | os.PathLike[str] | None,
    name: str,
    *,
    exclusive: bool,
) -> Iterator[tuple[int | None, Path]]:
    root = _quality_directory(directory)
    path = root / name
    flags = (os.O_RDWR | os.O_CREAT | os.O_APPEND) if exclusive else os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if exclusive:
            raise
        yield None, root
        return
    try:
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode) or (not exclusive and stat.S_IMODE(mode) != 0o600):
            raise OSError("quality store is not a private regular file")
        if exclusive:
            os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield fd, root
    finally:
        os.close(fd)


@contextmanager
def _locked_ledger(
    directory: str | os.PathLike[str] | None,
    *,
    exclusive: bool,
) -> Iterator[tuple[int | None, Path]]:
    with _locked_store(directory, LEDGER_NAME, exclusive=exclusive) as state:
        yield state


def _validate_row(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("quality ledger row must be an object")
    record_type = value.get("recordType")
    fields = {"schemaVersion", "recordType", "sessionId", "beadId", "evidenceRefs", "capturedAt"}
    if record_type == "result":
        fields.add("outcome")
    if set(value) != fields:
        raise ValueError("quality ledger row fields are invalid")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("quality ledger row schema is invalid")
    if record_type not in {"invocation", "result"}:
        raise ValueError("quality ledger row type is invalid")
    _session_id(value.get("sessionId"))
    _bead_id(value.get("beadId"))
    _evidence_refs(value.get("evidenceRefs"))
    captured_at = value.get("capturedAt")
    if not isinstance(captured_at, str) or not captured_at.endswith("Z"):
        raise ValueError("quality ledger row timestamp is invalid")
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("quality ledger row timestamp is invalid") from exc
    if record_type == "result" and value.get("outcome") not in TASK_OUTCOMES:
        raise ValueError("quality ledger row outcome is invalid")
    return value


def _session_state(rows: list[dict[str, Any]], session_id: str) -> tuple[str | None, str | None]:
    bead_id = None
    outcome = None
    linked = False
    for row in rows:
        if row["sessionId"] != session_id:
            continue
        if bead_id is None:
            bead_id = row["beadId"]
        elif row["beadId"] != bead_id:
            raise ValueError("quality ledger session ownership conflicts")
        if row["recordType"] == "invocation":
            linked = True
            continue
        if not linked:
            raise ValueError("quality ledger result has no invocation")
        if outcome is None:
            outcome = row["outcome"]
        elif row["outcome"] != outcome:
            raise ValueError("quality ledger session outcome conflicts")
    return bead_id, outcome


def _read_json_rows(fd: int, validator: Any, label: str) -> list[dict[str, Any]]:
    size = os.fstat(fd).st_size
    if size > MAX_LEDGER_BYTES:
        raise ValueError(f"quality {label} exceeds bounded size")
    os.lseek(fd, 0, os.SEEK_SET)
    data = os.read(fd, size)
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise ValueError(f"quality {label} row is incomplete")
    try:
        return [validator(json.loads(line)) for line in data.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"quality {label} row is invalid") from exc


def _read_rows(fd: int) -> list[dict[str, Any]]:
    rows = _read_json_rows(fd, _validate_row, "ledger")
    for session_id in {row["sessionId"] for row in rows}:
        _session_state(rows, session_id)
    return rows


def _append_row(fd: int, root: Path, row: dict[str, Any]) -> None:
    encoded = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    original_size = os.fstat(fd).st_size
    if len(encoded) > 4096 or original_size + len(encoded) > MAX_LEDGER_BYTES:
        raise ValueError("quality ledger row exceeds bounded size")
    try:
        written = os.write(fd, encoded)
        if written != len(encoded):
            raise OSError("quality ledger append was incomplete")
    except OSError:
        os.ftruncate(fd, original_size)
        os.fsync(fd)
        raise
    os.fsync(fd)
    directory_fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _validate_bead(bead_id: str, beads_runner: Any) -> None:
    result = beads_runner(["show", bead_id])
    data = result[1] if isinstance(result, tuple) and len(result) > 1 and result[0] == 0 else None
    if isinstance(data, list):
        data = data[0] if len(data) == 1 else None
    if not isinstance(data, dict) or data.get("id") != bead_id:
        raise ValueError("could not load work item")


def _record_matches(row: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(row.get(key) == value for key, value in expected.items())


def capture_session_link(
    session_id: str,
    bead_id: str,
    *,
    beads_runner: Any,
    directory: str | os.PathLike[str] | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    session_id = _session_id(session_id)
    bead_id = _bead_id(bead_id)
    refs = _evidence_refs(evidence_refs or [])
    _validate_bead(bead_id, beads_runner)
    expected = {
        "recordType": "invocation",
        "sessionId": session_id,
        "beadId": bead_id,
        "evidenceRefs": refs,
    }
    with _locked_ledger(directory, exclusive=True) as (fd, root):
        assert fd is not None
        rows = _read_rows(fd)
        owner, _outcome = _session_state(rows, session_id)
        if owner is not None and owner != bead_id:
            raise SessionWorkItemConflict(
                "current Pi session belongs to another work item; use handoff_bead or the /new human fallback and retry"
            )
        if not any(_record_matches(row, expected) for row in rows):
            _append_row(fd, root, {"schemaVersion": 1, **expected, "capturedAt": _captured_at()})
    return {"schemaVersion": 1, "status": "linked", "beadId": bead_id}


def capture_session_outcome(
    session_id: str,
    bead_id: str,
    outcome: str,
    *,
    beads_runner: Any,
    directory: str | os.PathLike[str] | None = None,
    evidence_refs: list[str] | None = None,
    require_link: bool = True,
) -> dict[str, Any]:
    session_id = _session_id(session_id)
    bead_id = _bead_id(bead_id)
    if outcome not in TASK_OUTCOMES:
        raise ValueError("task outcome is unsupported")
    refs = _evidence_refs(evidence_refs or [])
    _validate_bead(bead_id, beads_runner)
    with _locked_ledger(directory, exclusive=True) as (fd, root):
        assert fd is not None
        rows = _read_rows(fd)
        owner, recorded = _session_state(rows, session_id)
        if owner is not None and owner != bead_id:
            raise SessionWorkItemConflict(
                "current Pi session belongs to another work item; use handoff_bead or the /new human fallback and retry"
            )
        if recorded is not None and recorded != outcome:
            raise SessionWorkItemConflict("current Pi session already has another final outcome")
        if owner is None and require_link:
            raise SessionUnassigned("current Pi session has no linked work item")
        if owner is None:
            invocation = {
                "schemaVersion": 1,
                "recordType": "invocation",
                "sessionId": session_id,
                "beadId": bead_id,
                "evidenceRefs": [],
                "capturedAt": _captured_at(),
            }
            _append_row(fd, root, invocation)
        expected = {
            "recordType": "result",
            "sessionId": session_id,
            "beadId": bead_id,
            "outcome": outcome,
            "evidenceRefs": refs,
        }
        if not any(_record_matches(row, expected) for row in rows):
            _append_row(fd, root, {"schemaVersion": 1, **expected, "capturedAt": _captured_at()})
    return {"schemaVersion": 1, "status": "recorded", "beadId": bead_id, "outcome": outcome}


def session_work_item(
    session_id: str,
    *,
    directory: str | os.PathLike[str] | None = None,
) -> str | None:
    session_id = _session_id(session_id)
    with _locked_ledger(directory, exclusive=False) as (fd, _root):
        owner, _outcome = _session_state(_read_rows(fd) if fd is not None else [], session_id)
    return owner


def session_handoff_source(
    session_id: str,
    *,
    directory: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    session_id = _session_id(session_id)
    with _locked_ledger(directory, exclusive=False) as (fd, _root):
        owner, outcome = _session_state(_read_rows(fd) if fd is not None else [], session_id)
    if owner is None:
        raise SessionUnassigned("current Pi session has no linked work item")
    if outcome is None:
        raise SessionOutcomeUnavailable("current Pi session closeout outcome is unavailable")
    return {"beadId": owner, "outcome": outcome}


def current_session_work_item(session_id: str) -> str | None:
    return session_work_item(session_id)


def current_session_handoff_source(session_id: str) -> dict[str, str]:
    return session_handoff_source(session_id)


def current_session_closeout_source(session_id: str) -> dict[str, str]:
    return session_handoff_source(session_id)


def _validate_capture_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("quality capture payload must be an object")
    record_type = value.get("recordType")
    fields = {"schemaVersion", "recordType", "sessionId", "beadId", "evidenceRefs"}
    if record_type == "result":
        fields.add("outcome")
    unknown = set(value) - fields
    missing = fields - set(value)
    if unknown:
        raise ValueError(f"quality capture has unknown fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"quality capture is missing fields: {sorted(missing)}")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("quality capture schema is invalid")
    if record_type not in {"invocation", "result"}:
        raise ValueError("quality capture record type is unsupported")
    _session_id(value.get("sessionId"))
    _bead_id(value.get("beadId"))
    _evidence_refs(value.get("evidenceRefs"))
    if record_type == "result" and value.get("outcome") not in TASK_OUTCOMES:
        raise ValueError("quality capture outcome is unsupported")
    return value


def capture(
    payload: Any,
    *,
    beads_runner: Any,
    directory: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    payload = _validate_capture_payload(payload)
    kwargs = {
        "beads_runner": beads_runner,
        "directory": directory,
        "evidence_refs": payload["evidenceRefs"],
    }
    if payload["recordType"] == "invocation":
        return capture_session_link(payload["sessionId"], payload["beadId"], **kwargs)
    return capture_session_outcome(
        payload["sessionId"], payload["beadId"], payload["outcome"], **kwargs
    )


def _labels(bead: dict[str, Any]) -> set[str]:
    return {str(label) for label in bead.get("labels") or []}


def _is_closed(bead: dict[str, Any]) -> bool:
    return str(bead.get("status") or "").lower() == "closed"


def _is_implementation(bead: dict[str, Any]) -> bool:
    labels = _labels(bead)
    if "implementation" in labels or "implement" in str(bead.get("title") or "").lower():
        return True
    metadata = bead.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = None
    pi_metadata = metadata.get("pi") if isinstance(metadata, dict) else None
    return isinstance(pi_metadata, dict) and pi_metadata.get("action") == "implement"


def _is_human_blocker(bead: dict[str, Any]) -> bool:
    labels = _labels(bead)
    return (
        bool(labels.intersection({"human", "human-gate", "approval"}))
        or "human" in str(bead.get("title") or "").lower()
        or str(bead.get("issue_type") or bead.get("type") or "") == "decision"
    )


def _activity_from_labels(bead: dict[str, Any]) -> str | None:
    labels = _labels(bead)
    for activity, label in QUALITY_ACTIVITY_LABELS.items():
        if label in labels:
            return activity
    return next(
        (activity for label, activity in LEGACY_ACTIVITY_LABELS.items() if label in labels),
        None,
    )


def open_quality_activities(beads: list[dict[str, Any]]) -> set[str]:
    return {
        activity
        for bead in beads
        if not _is_closed(bead)
        if (activity := _activity_from_labels(bead)) is not None
    }


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_closed_time(
    beads: list[dict[str, Any]],
    *,
    labels: frozenset[str],
    activities: frozenset[str],
) -> datetime | None:
    times = []
    for bead in beads:
        bead_labels = _labels(bead)
        if not _is_closed(bead) or not (
            bead_labels.intersection(labels)
            or any(QUALITY_ACTIVITY_LABELS[activity] in bead_labels for activity in activities)
        ):
            continue
        timestamp = _parse_time(bead.get("closed_at") or bead.get("closedAt"))
        if timestamp is not None:
            times.append(timestamp)
    return max(times) if times else None


def default_improvement_review_provider(*, since: str | None, until: str) -> dict[str, Any]:
    from .improvement import eligible_unreviewed_session_summary
    from .langfuse import LangfuseError, _client_from_env

    if since is None:
        end = datetime.fromisoformat(until.replace("Z", "+00:00"))
        since = (end - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    try:
        return eligible_unreviewed_session_summary(
            _client_from_env(),
            since=since,
            until=until,
        )
    except (LangfuseError, OSError, ValueError):
        return {"schemaVersion": 1, "status": "unavailable"}


def collect_beads(beads_runner: Any = None) -> tuple[list[dict[str, Any]], list[str]]:
    code, data, error = (beads_runner or _beads)(["list"])
    if code != 0:
        return [], [str(error or "bd list failed")]
    if not isinstance(data, list):
        return [], ["bd list returned non-list JSON"]
    return [item for item in data if isinstance(item, dict)], []


def git_commit_summary(
    root: Path | str | None = None,
    *,
    since: datetime | None = None,
) -> dict[str, Any]:
    repository = Path(root).expanduser() if root is not None else Path.cwd()
    command = ["git", "-C", str(repository), "rev-list", "--count"]
    if since is not None:
        command.append(f"--since={since.isoformat()}")
    command.append("HEAD")
    try:
        process = run_process(command, text=True, capture_output=True)
    except OSError as exc:
        return {"commitsSinceQualityReview": 0, "error": str(exc)}
    if process.returncode != 0:
        return {
            "commitsSinceQualityReview": 0,
            "error": process.stderr.strip() or "git history unavailable",
        }
    try:
        count = int((process.stdout or "0").strip() or 0)
    except ValueError:
        count = 0
    return {
        "commitsSinceQualityReview": count,
        "since": since.isoformat().replace("+00:00", "Z") if since else None,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def collect_runs(runs_dir: Path | str | None = None) -> list[dict[str, Any]]:
    from .runs import default_runs_dir

    root = Path(runs_dir).expanduser() if runs_dir is not None else default_runs_dir()
    if not root.is_dir():
        return []
    runs = []
    for bundle in sorted(path for path in root.iterdir() if path.is_dir()):
        invocation = _read_json(bundle / "invocation.yaml") or {}
        result = _read_json(bundle / "result.yaml") or {}
        runs.append({
            "id": str(invocation.get("id") or result.get("invocationId") or bundle.name),
            "status": result.get("status"),
        })
    return runs


def _summary_count(report: dict[str, Any] | None, key: str) -> int:
    summary = report.get("summary") if isinstance(report, dict) else None
    try:
        return int(summary.get(key) or 0) if isinstance(summary, dict) else 0
    except (TypeError, ValueError):
        return 0


def durable_activity_snapshots(
    *,
    beads: list[dict[str, Any]] | None = None,
    runs: list[dict[str, Any]] | None = None,
    git_summary: dict[str, Any] | None = None,
    health_report: dict[str, Any] | None = None,
    context_health_report: dict[str, Any] | None = None,
    improvement_review_report: dict[str, Any] | None = None,
    thresholds: dict[str, int] | None = None,
    root: Path | str | None = None,
    runs_dir: Path | str | None = None,
    beads_runner: Any = None,
    git_summary_provider: Any = git_commit_summary,
    improvement_review_provider: Any = default_improvement_review_provider,
) -> dict[str, dict[str, Any]]:
    collection_gaps = []
    if beads is None:
        beads, bead_warnings = collect_beads(beads_runner)
        if bead_warnings:
            collection_gaps.append("beads-unavailable")
    if runs is None:
        runs = collect_runs(runs_dir)

    git_checkpoint = _latest_closed_time(
        beads,
        labels=LEGACY_GIT_CHECKPOINT_LABELS,
        activities=frozenset({"architecture-coherence", "quality-system-review"}),
    )
    work_learning_checkpoint = _latest_closed_time(
        beads,
        labels=LEGACY_WORK_LEARNING_CHECKPOINT_LABELS,
        activities=frozenset({"work-learning"}),
    )
    generated_at = _captured_at()
    if git_summary is None:
        git_summary = git_summary_provider(root, since=git_checkpoint)
    if improvement_review_report is None:
        improvement_review_report = improvement_review_provider(
            since=(
                work_learning_checkpoint.isoformat().replace("+00:00", "Z")
                if work_learning_checkpoint
                else None
            ),
            until=generated_at,
        )
    if health_report is None:
        from .health import work_health_report

        health_report = work_health_report(
            root=root,
            runs_dir=runs_dir,
            include_beads=False,
        )
    if context_health_report is None:
        from .context_health import context_health_report as build_context_health_report

        context_health_report = build_context_health_report()

    try:
        commits = int(git_summary.get("commitsSinceQualityReview") or 0)
    except (TypeError, ValueError):
        commits = 0
    signals: dict[str, Any] = {
        "closedImplementationBeads": sum(
            1 for bead in beads if _is_closed(bead) and _is_implementation(bead)
        ),
        "commitsSinceQualityReview": commits,
        "failedOrBlockedRuns": sum(
            1 for run in runs if str(run.get("status") or "") in {"failed", "blocked"}
        ),
        "humanBlockers": sum(
            1 for bead in beads if not _is_closed(bead) and _is_human_blocker(bead)
        ),
        "contextWarnings": _summary_count(context_health_report, "warningCount"),
        "healthWarnings": _summary_count(health_report, "warningCount"),
        "healthFailures": _summary_count(health_report, "failureCount"),
    }
    work_learning_gaps = list(collection_gaps)
    eligible_sessions = improvement_review_report.get("eligibleSessions")
    if (
        improvement_review_report.get("status") == "ok"
        and type(eligible_sessions) is int
        and eligible_sessions >= 0
    ):
        signals["eligibleUnreviewedSessions"] = eligible_sessions
        if improvement_review_report.get("lowerBound") is True:
            work_learning_gaps.append("eligible-sessions-lower-bound")
    else:
        signals["eligibleUnreviewedSessions"] = None
        work_learning_gaps.append("eligible-sessions-unknown")

    limits = {**DEFAULT_SIGNAL_THRESHOLDS, **(thresholds or {})}
    due_signals = {
        "capture": [],
        "work-learning": [
            name
            for name in ("humanBlockers", "eligibleUnreviewedSessions")
            if type(signals[name]) is int and signals[name] >= limits[name]
        ],
        "architecture-coherence": [
            name
            for name, threshold in (
                ("closedImplementationBeads", limits["closedImplementationBeads"]),
                ("commitsSinceQualityReview", limits["commits"]),
                ("failedOrBlockedRuns", limits["failedOrBlockedRuns"]),
                ("contextWarnings", limits["contextWarnings"]),
                ("healthWarnings", limits["healthWarnings"]),
                ("healthFailures", limits["healthFailures"]),
            )
            if signals[name] >= threshold
        ],
        "capability-calibration": [],
        "quality-system-review": [],
    }
    active = open_quality_activities(beads)
    snapshots = {}
    for activity in ACTIVITY_IDS:
        triggered_signals = due_signals[activity]
        suppressed = bool(triggered_signals) and activity in active
        gaps = list(collection_gaps)
        if activity == "work-learning":
            gaps = work_learning_gaps
        if activity == "architecture-coherence" and git_summary.get("error"):
            gaps.append("git-history-unknown")
        snapshot = {
            "schemaVersion": 1,
            "triggered": bool(triggered_signals) and not suppressed,
            "evidenceRefs": [],
            "gaps": sorted(set(gaps)),
            "signals": {
                **signals,
                "activityLabel": QUALITY_ACTIVITY_LABELS[activity],
                "triggeredSignals": triggered_signals,
                "duplicateSuppressed": suppressed,
            },
        }
        snapshots[activity] = _validate_snapshot(snapshot)
    return snapshots


def _canonical(value: Any) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("quality value is not canonical JSON") from exc


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 1000


def _text_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and len(value) <= 32
        and all(_text(item) for item in value)
        and len(set(value)) == len(value)
    )


def validate_evidence_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != EVIDENCE_REF_FIELDS:
        raise ValueError("evidence reference fields are invalid")
    try:
        _evidence_refs([value.get("ref")])
    except ValueError as exc:
        raise ValueError("evidence reference pointer is invalid") from exc
    if any(
        not isinstance(value.get(field), str)
        or not OPAQUE_ID.fullmatch(value[field])
        for field in ("source", "provenance")
    ):
        raise ValueError("evidence reference provenance is invalid")
    for field, allowed in (
        ("availability", EVIDENCE_AVAILABILITY),
        ("integrity", EVIDENCE_INTEGRITY),
        ("sensitivity", EVIDENCE_SENSITIVITY),
        ("retention", EVIDENCE_RETENTION),
    ):
        if value.get(field) not in allowed:
            raise ValueError(f"evidence reference {field} is invalid")
    return value


def _finding_evidence_refs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) > MAX_EVIDENCE_REFS:
        raise ValueError("finding evidence references are invalid")
    refs = [validate_evidence_ref(item) for item in value]
    if len({_canonical(item) for item in refs}) != len(refs):
        raise ValueError("finding evidence references are invalid")
    return refs


def _review_assignment_contract(routing_task: Any, output_name: Any) -> dict[str, Any]:
    if (
        not isinstance(routing_task, str)
        or not OPAQUE_ID.fullmatch(routing_task)
        or not _text(output_name)
    ):
        raise ValueError("review assignment contract is invalid")
    return {
        "privacyConstraints": {
            "evidenceSensitivity": "private",
            "allowedReviewerClasses": [
                "human",
                "local-self-hosted",
                "explicitly-authorized-provider",
            ],
            "providerAccess": "explicit-approval-required",
            "rawEvidenceExport": False,
        },
        "modelConstraints": {
            "routingTask": routing_task,
            "capability": "demonstrated-required",
        },
        "outputContract": {
            "name": output_name,
            "schemaVersion": 1,
            "requiredFields": [
                "assignmentId",
                "reviewStatus",
                "route",
                "gaps",
                "sessions",
            ],
        },
        "stopRules": {
            "maxAttempts": 1,
            "timeoutSeconds": 900,
            "onUnavailable": "route-human",
            "onTimeout": "route-human",
            "onPrivacyUncertain": "route-human",
            "onSchemaInvalid": "route-human",
        },
    }


def validate_review_assignment(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REVIEW_ASSIGNMENT_FIELDS:
        raise ValueError("review assignment fields are invalid")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("review assignment schema is invalid")
    if value.get("activity") not in ACTIVITY_IDS:
        raise ValueError("review assignment activity is invalid")

    action = value.get("action")
    if (
        not isinstance(action, dict)
        or set(action) != {"id", "routingTask"}
        or any(
            not isinstance(action.get(field), str)
            or not OPAQUE_ID.fullmatch(action[field])
            for field in action
        )
    ):
        raise ValueError("review assignment action is invalid")

    scope = value.get("scope")
    if (
        not isinstance(scope, dict)
        or set(scope) != {"kind", "id", "itemCount", "maxItems"}
        or any(
            not isinstance(scope.get(field), str)
            or not OPAQUE_ID.fullmatch(scope[field])
            for field in ("kind", "id")
        )
        or type(scope.get("itemCount")) is not int
        or type(scope.get("maxItems")) is not int
        or not 1 <= scope["itemCount"] <= scope["maxItems"] <= MAX_REVIEW_ASSIGNMENT_ITEMS
    ):
        raise ValueError("review assignment scope is invalid")

    evidence_refs = value.get("evidenceRefs")
    if (
        not isinstance(evidence_refs, list)
        or len(evidence_refs) != scope["itemCount"]
        or len({_canonical(item) for item in evidence_refs}) != len(evidence_refs)
    ):
        raise ValueError("review assignment evidence is invalid")
    for item in evidence_refs:
        if validate_evidence_ref(item)["sensitivity"] != "private":
            raise ValueError("review assignment evidence must remain private")

    rubric = value.get("rubric")
    rubric_path = rubric.get("path") if isinstance(rubric, dict) else None
    if (
        not isinstance(rubric, dict)
        or set(rubric) != {"path", "version"}
        or not _text(rubric_path)
        or not _text(rubric.get("version"))
        or Path(rubric_path).is_absolute()
        or "\\" in rubric_path
        or ".." in Path(rubric_path).parts
    ):
        raise ValueError("review assignment rubric is invalid")

    output = value.get("outputContract")
    output_name = output.get("name") if isinstance(output, dict) else None
    contract = _review_assignment_contract(action["routingTask"], output_name)
    if any(value.get(field) != expected for field, expected in contract.items()):
        raise ValueError("review assignment constraints are invalid")
    if value.get("authority") != {"status": "none", "allowedEffects": []}:
        raise ValueError("review assignment authority is invalid")

    assignment_id = value.get("assignmentId")
    core = {key: item for key, item in value.items() if key != "assignmentId"}
    expected_id = "review-" + _fingerprint(core).partition(":")[2]
    if assignment_id != expected_id or not REVIEW_ASSIGNMENT_ID.fullmatch(str(assignment_id or "")):
        raise ValueError("review assignment identity is invalid")
    return value


def build_review_assignment(
    *,
    activity: str,
    action: dict[str, Any],
    scope: dict[str, Any],
    evidence_refs: list[dict[str, Any]],
    rubric: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(action, dict) or set(action) != {"id", "routingTask", "outputContract"}:
        raise ValueError("review assignment action is invalid")
    core = {
        "schemaVersion": 1,
        "activity": activity,
        "action": {"id": action["id"], "routingTask": action["routingTask"]},
        "scope": scope,
        "evidenceRefs": evidence_refs,
        "rubric": rubric,
        **_review_assignment_contract(action["routingTask"], action["outputContract"]),
        "authority": {"status": "none", "allowedEffects": []},
    }
    assignment_id = "review-" + _fingerprint(core).partition(":")[2]
    return validate_review_assignment({**core, "assignmentId": assignment_id})


def normalize_assigned_review_result(
    assignment: Any,
    result: Any,
) -> dict[str, Any]:
    assignment = validate_review_assignment(assignment)
    required = {"schemaVersion", *assignment["outputContract"]["requiredFields"]}
    forbidden = {"accepted", "acceptance", "allowedEffects", "authority", "authorization", "grant", "mode"}
    if (
        not isinstance(result, dict)
        or not required.issubset(result)
        or forbidden.intersection(result)
    ):
        raise ValueError("assigned review result fields are invalid")
    if result.get("schemaVersion") != 1 or type(result.get("schemaVersion")) is not int:
        raise ValueError("assigned review result schema is invalid")
    if result.get("assignmentId") != assignment["assignmentId"]:
        raise ValueError("assigned review result does not match assignment")
    if (
        result.get("reviewStatus") != "completed"
        or result.get("route") != "none"
        or result.get("gaps") != []
        or not isinstance(result.get("sessions"), list)
    ):
        raise ValueError("assigned review result status is invalid")
    return {
        "schemaVersion": 1,
        "resultType": "evidence",
        "category": "review",
        "source": "assigned-agent",
        "assignmentId": assignment["assignmentId"],
        "status": "completed",
        "evidenceRefs": assignment["evidenceRefs"],
        "authority": {"status": "none", "allowedEffects": []},
    }


def _langfuse_annotation_ref(kind: str, value: Any) -> str:
    if not _text(value):
        raise ValueError("Langfuse annotation identifier is invalid")
    digest = _fingerprint(value).partition(":")[2][:24]
    return f"langfuse-{kind}-{digest}"


def _contains_authority_claim(value: Any) -> bool:
    pending = [value]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if not isinstance(item, (dict, list)) or id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, dict):
            if AUTHORITY_CLAIM_FIELDS.intersection(item):
                return True
            pending.extend(item.values())
        else:
            pending.extend(item)
    return False


def _relative_result_path(value: Any) -> str:
    path = Path(value) if isinstance(value, str) else Path()
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or value != value.strip()
        or path.is_absolute()
        or path == Path(".")
        or ".." in path.parts
        or "\\" in value
        or any(character in value for character in "\0\r\n")
        or ":" in path.parts[0]
        or path.parts[0].startswith("~")
        or path.as_posix() != value
    ):
        raise ValueError("external result path is invalid")
    return value


def normalize_external_result(result: Any) -> dict[str, Any]:
    """Normalize editor review or browser takeover metadata without importing bodies."""
    if _contains_authority_claim(result):
        raise ValueError("external result authority fields are forbidden")
    if not isinstance(result, dict) or set(result) != EXTERNAL_RESULT_FIELDS:
        raise ValueError("external result fields are invalid")
    if result.get("schemaVersion") != 1 or type(result.get("schemaVersion")) is not int:
        raise ValueError("external result schema is invalid")

    contracts = {
        "editor": ("review", {"editor", "nvim"}),
        "takeover": ("execution", {"betterwright"}),
    }
    source = result.get("source")
    category = result.get("category")
    if not isinstance(source, str) or source not in contracts or category != contracts[source][0]:
        raise ValueError("external result category is invalid")

    artifact = result.get("artifact")
    if (
        not isinstance(artifact, dict)
        or set(artifact) != {"path", "sensitivity"}
        or not isinstance(artifact.get("sensitivity"), str)
        or artifact["sensitivity"] not in EVIDENCE_SENSITIVITY
    ):
        raise ValueError("external result artifact is invalid")
    _relative_result_path(artifact.get("path"))

    scope = result.get("scope")
    if (
        not isinstance(scope, dict)
        or set(scope) != {"kind", "id"}
        or any(
            not isinstance(scope.get(field), str)
            or not OPAQUE_ID.fullmatch(scope[field])
            for field in ("kind", "id")
        )
    ):
        raise ValueError("external result scope is invalid")

    evidence_refs = _finding_evidence_refs(result.get("evidenceRefs"))
    sensitivity_rank = {"public": 0, "internal": 1, "private": 2, "restricted": 3}
    if any(
        sensitivity_rank[item["sensitivity"]] > sensitivity_rank[artifact["sensitivity"]]
        for item in evidence_refs
    ):
        raise ValueError("external result artifact sensitivity is invalid")

    provenance = result.get("provenance")
    if (
        not isinstance(provenance, dict)
        or set(provenance) != {"adapter", "actor", "sessionRef"}
        or not isinstance(provenance.get("adapter"), str)
        or provenance["adapter"] not in contracts[source][1]
        or provenance.get("actor") != "human"
    ):
        raise ValueError("external result provenance is invalid")
    try:
        _evidence_refs([provenance.get("sessionRef")])
    except ValueError as exc:
        raise ValueError("external result provenance is invalid") from exc
    if not provenance["sessionRef"].startswith("invocation:"):
        raise ValueError("external result provenance is invalid")

    status = result.get("status")
    gaps = result.get("gaps")
    if (
        not isinstance(status, str)
        or status not in EXTERNAL_RESULT_STATUSES
        or not isinstance(gaps, list)
        or len(gaps) > 32
        or any(not isinstance(gap, str) or not OPAQUE_ID.fullmatch(gap) for gap in gaps)
        or len(set(gaps)) != len(gaps)
        or (status == "completed") != (gaps == [])
    ):
        raise ValueError("external result state is invalid")

    resumption_path = result.get("resumptionPath")
    if resumption_path is not None:
        _relative_result_path(resumption_path)
    if status == "completed" and resumption_path is not None:
        raise ValueError("external result resumption path is invalid")
    if source == "takeover" and status != "completed" and resumption_path is None:
        raise ValueError("external result resumption path is required")

    return {
        **result,
        "resultType": "evidence",
        "authority": {"status": "none", "allowedEffects": []},
    }


def normalize_langfuse_annotation_result(
    *,
    queue_id: str,
    queue: Any,
    items: Any,
    scores: Any,
    score_configs: Any,
    completeness: Any,
    gaps: Any,
) -> dict[str, Any]:
    """Normalize current Langfuse queue API rows without copying annotation bodies."""
    if _contains_authority_claim([queue, items, scores, score_configs, completeness]):
        raise ValueError("Langfuse annotation authority fields are forbidden")
    if not _text(queue_id):
        raise ValueError("Langfuse annotation queue ID is invalid")
    if (
        not isinstance(items, list)
        or len(items) > MAX_LANGFUSE_ANNOTATION_ITEMS
        or not isinstance(scores, list)
        or len(scores) > MAX_LANGFUSE_ANNOTATION_ITEMS
        or not isinstance(score_configs, list)
        or len(score_configs) > MAX_LANGFUSE_ANNOTATION_ITEMS
    ):
        raise ValueError("Langfuse annotation import exceeds its bound")
    completeness_fields = {"queue", "items", "scores", "scoreConfigs"}
    if (
        not isinstance(completeness, dict)
        or set(completeness) != completeness_fields
        or any(type(completeness[field]) is not bool for field in completeness_fields)
    ):
        raise ValueError("Langfuse annotation completeness is invalid")
    if (
        not isinstance(gaps, list)
        or len(gaps) > 32
        or len(set(gaps)) != len(gaps)
        or any(gap not in LANGFUSE_ANNOTATION_GAPS for gap in gaps)
    ):
        raise ValueError("Langfuse annotation gaps are invalid")

    normalized_gaps = set(gaps)
    related_gaps = {
        "queue": {"queue-incomplete", "queue-unavailable"},
        "items": {"item-limit", "items-incomplete", "items-unavailable"},
        "scores": {"score-limit", "scores-incomplete", "scores-unavailable"},
        "scoreConfigs": {
            "score-config-limit",
            "score-configs-incomplete",
            "score-configs-unavailable",
        },
    }
    default_gaps = {
        "queue": "queue-incomplete",
        "items": "items-incomplete",
        "scores": "scores-incomplete",
        "scoreConfigs": "score-configs-incomplete",
    }
    for field in completeness_fields:
        if completeness[field] is False and not normalized_gaps.intersection(related_gaps[field]):
            normalized_gaps.add(default_gaps[field])

    queue_ref = _langfuse_annotation_ref("queue", queue_id)
    config_ids: list[str] = []
    if queue is None:
        if completeness["queue"] or items or scores or score_configs:
            raise ValueError("Langfuse annotation unavailable queue is invalid")
    else:
        raw_config_ids = queue.get("scoreConfigIds") if isinstance(queue, dict) else None
        if (
            not isinstance(queue, dict)
            or queue.get("id") != queue_id
            or not isinstance(raw_config_ids, list)
            or not raw_config_ids
            or len(raw_config_ids) > 32
            or len(set(raw_config_ids)) != len(raw_config_ids)
            or any(not _text(config_id) for config_id in raw_config_ids)
        ):
            raise ValueError("Langfuse annotation queue is invalid")
        config_ids = list(raw_config_ids)
        if len(config_ids) > MAX_LANGFUSE_ANNOTATION_ITEMS:
            normalized_gaps.add("score-config-limit")

    item_by_subject: dict[tuple[str, str], dict[str, Any]] = {}
    completed_items = 0
    object_types: set[str] = set()
    for item in items:
        object_type = item.get("objectType") if isinstance(item, dict) else None
        status = item.get("status") if isinstance(item, dict) else None
        if (
            not isinstance(item, dict)
            or not _text(item.get("id"))
            or item.get("queueId") != queue_id
            or not _text(item.get("objectId"))
            or object_type not in {"TRACE", "OBSERVATION", "SESSION"}
            or status not in {"PENDING", "COMPLETED"}
        ):
            raise ValueError("Langfuse annotation queue item is invalid")
        subject = (object_type.lower(), item["objectId"])
        if subject in item_by_subject:
            raise ValueError("Langfuse annotation queue items are duplicated")
        item_by_subject[subject] = item
        object_types.add(subject[0])
        if status == "COMPLETED":
            completed_items += 1
        else:
            normalized_gaps.add("pending-items")
    if queue is not None and not items:
        normalized_gaps.add("empty-queue")

    config_by_id: dict[str, dict[str, Any]] = {}
    for config in score_configs:
        config_id = config.get("id") if isinstance(config, dict) else None
        if (
            not isinstance(config, dict)
            or not _text(config_id)
            or config_id not in config_ids
            or config.get("dataType") not in {"NUMERIC", "BOOLEAN", "CATEGORICAL", "TEXT"}
            or config_id in config_by_id
        ):
            raise ValueError("Langfuse annotation score config is invalid")
        config_by_id[config_id] = config
    if queue is not None and any(config_id not in config_by_id for config_id in config_ids):
        normalized_gaps.add("missing-score-config")

    reviewers: set[str] = set()
    annotations: list[dict[str, Any]] = []
    evidence_refs: list[dict[str, Any]] = []
    scored_configs: dict[tuple[str, str], set[str]] = {}
    score_ids: set[str] = set()
    for score in scores:
        subject = score.get("subject") if isinstance(score, dict) else None
        data_type = score.get("dataType") if isinstance(score, dict) else None
        score_id = score.get("id") if isinstance(score, dict) else None
        value = score.get("value") if isinstance(score, dict) else None
        if (
            not isinstance(score, dict)
            or not _text(score_id)
            or score_id in score_ids
            or not _text(score.get("name"))
            or score.get("source") != "ANNOTATION"
            or score.get("queueId") != queue_id
            or data_type not in {"NUMERIC", "BOOLEAN", "CATEGORICAL", "TEXT", "CORRECTION"}
            or not isinstance(subject, dict)
            or subject.get("kind") not in {"trace", "observation", "session"}
            or not _text(subject.get("id"))
        ):
            raise ValueError("Langfuse annotation score is invalid")
        if (
            (data_type == "NUMERIC" and (
                type(value) not in {int, float} or not math.isfinite(value)
            ))
            or (data_type == "BOOLEAN" and type(value) is not bool)
            or (data_type in {"CATEGORICAL", "TEXT", "CORRECTION"} and not isinstance(value, str))
        ):
            raise ValueError("Langfuse annotation score value is invalid")
        score_ids.add(score_id)
        subject_key = (subject["kind"], subject["id"])
        if subject_key not in item_by_subject:
            normalized_gaps.add("unmatched-annotations")
            continue

        config_id = score.get("configId")
        config_ref = None
        if data_type == "CORRECTION":
            if score["name"] != "output" or config_id is not None:
                raise ValueError("Langfuse corrected output is invalid")
            kinds = ["corrected-output"]
            evidence_source = "langfuse-correction"
        else:
            if not _text(config_id) or config_id not in config_ids:
                normalized_gaps.add("unmatched-annotations")
                continue
            config = config_by_id.get(config_id)
            if config is None:
                normalized_gaps.add("missing-score-config")
            elif config["dataType"] != data_type:
                raise ValueError("Langfuse annotation score config does not match score")
            config_ref = _langfuse_annotation_ref("score-config", config_id)
            scored_configs.setdefault(subject_key, set()).add(config_id)
            comment = score.get("comment")
            if comment is not None and not isinstance(comment, str):
                raise ValueError("Langfuse annotation comment is invalid")
            kinds = ["score", *(["comment"] if comment else [])]
            evidence_source = "langfuse-annotation"

        author = score.get("authorUserId")
        reviewer = None
        if author is None:
            normalized_gaps.add("missing-reviewer")
        elif not _text(author):
            raise ValueError("Langfuse annotation reviewer is invalid")
        else:
            reviewer = _langfuse_annotation_ref("user", author)
            reviewers.add(reviewer)

        evidence_ref = validate_evidence_ref({
            "ref": "result:" + _langfuse_annotation_ref(
                "correction" if data_type == "CORRECTION" else "annotation", score_id
            ),
            "source": evidence_source,
            "availability": "available",
            "provenance": queue_ref,
            "integrity": "verified",
            "sensitivity": "private",
            "retention": "cohort",
        })
        evidence_refs.append(evidence_ref)
        annotations.append({
            "evidenceRef": evidence_ref["ref"],
            "kinds": kinds,
            "reviewer": reviewer,
            "scoreConfigRef": config_ref,
            "subject": {
                "kind": subject["kind"],
                "ref": _langfuse_annotation_ref(subject["kind"], subject["id"]),
            },
        })

    expected_configs = set(config_ids)
    if any(
        item["status"] == "COMPLETED" and scored_configs.get(subject, set()) != expected_configs
        for subject, item in item_by_subject.items()
    ):
        normalized_gaps.add("missing-item-scores")

    rubric_configs = [
        {
            "ref": _langfuse_annotation_ref("score-config", config_id),
            "dataType": config_by_id[config_id]["dataType"],
        }
        for config_id in config_ids
        if config_id in config_by_id
    ]
    gap_list = sorted(normalized_gaps)
    fully_complete = all(completeness.values()) and not gap_list
    return {
        "schemaVersion": 1,
        "resultType": "evidence",
        "category": "review",
        "source": "langfuse-annotation-queue",
        "status": "unavailable" if queue is None else "completed" if fully_complete else "partial",
        "reviewers": sorted(reviewers),
        "rubric": {
            "scoreConfigs": rubric_configs,
            "complete": completeness["scoreConfigs"] and len(rubric_configs) == len(config_ids),
        },
        "scope": {
            "queueRef": queue_ref,
            "itemCount": len(items),
            "completedItems": completed_items,
            "objectTypes": sorted(object_types),
            "maxItems": MAX_LANGFUSE_ANNOTATION_ITEMS,
        },
        "annotations": annotations,
        "evidenceRefs": evidence_refs,
        "completeness": {**completeness, "complete": fully_complete},
        "gaps": gap_list,
        "authority": {"status": "none", "allowedEffects": []},
    }


def normalize_ask_result(result: Any) -> dict[str, Any]:
    required = {"id", "question", "options", "selectionMode", "selectedOptions"}
    optional = {"description", "customInput"}
    if not isinstance(result, dict) or not required.issubset(result) or set(result) - required - optional:
        raise ValueError("ask result fields are invalid")
    question_id = result.get("id")
    if not _text(question_id):
        raise ValueError("ask result question ID is invalid")
    if not _text(result.get("question")) or not _text_list(result.get("options")):
        raise ValueError("ask result question is invalid")
    if "description" in result and not _text(result["description"]):
        raise ValueError("ask result description is invalid")
    selection_mode = result.get("selectionMode")
    if selection_mode not in {"single", "multi"}:
        raise ValueError("ask result selection mode is invalid")
    selected = result.get("selectedOptions")
    if (
        not isinstance(selected, list)
        or len(selected) > len(result["options"])
        or any(not _text(item) or item not in result["options"] for item in selected)
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("ask result selected options are invalid")
    custom = result.get("customInput")
    if custom is not None:
        if not _text(custom):
            raise ValueError("ask result custom input is invalid")
        custom = custom.strip()
    if selection_mode == "single" and (len(selected) > 1 or (selected and custom)):
        raise ValueError("ask result selected options are invalid")
    return {
        "schemaVersion": 1,
        "resultType": "constraint",
        "category": "answer",
        "source": "ask",
        "retention": "session",
        "questionId": question_id,
        "status": "answered" if selected or custom else "cancelled",
        "selectedOptions": list(selected),
        **({"customInput": custom} if custom else {}),
        "authority": {"status": "none", "allowedEffects": []},
    }


def normalize_ask_results(results: Any) -> dict[str, Any]:
    if not isinstance(results, list) or not 1 <= len(results) <= 32:
        raise ValueError("ask results are invalid")
    return {
        "schemaVersion": 1,
        "source": "ask",
        "results": [normalize_ask_result(result) for result in results],
    }


def normalize_ticket_decision_result(
    decision_bead: str,
    decision: Any,
) -> dict[str, Any]:
    decision_bead = _bead_id(decision_bead)
    if not isinstance(decision, dict):
        raise ValueError("ticket decision result is invalid")
    kind = decision.get("kind")
    status = decision.get("status")
    if kind not in {"question", "approval"} or status not in {
        "approved", "answered", "rejected", "cancelled", "timed-out",
    }:
        raise ValueError("ticket decision result category or status is invalid")
    if (kind == "question" and status == "approved") or (
        kind == "approval" and status == "answered"
    ):
        raise ValueError("ticket decision result category or status is invalid")
    if status in {"approved", "answered"} and decision.get("resolver") != {"kind": "human-ui"}:
        raise ValueError("ticket decision result lacks human UI provenance")
    if kind == "approval" and status == "approved" and not HASH_REF.fullmatch(
        str(decision.get("requestFingerprint") or "")
    ):
        raise ValueError("ticket approval request is unbound")
    target_bead = _bead_id(decision.get("targetBead"))
    evidence_ref = validate_evidence_ref({
        "ref": f"result:ticket-{decision_bead}",
        "source": "beads-decision",
        "availability": "available",
        "provenance": f"ticket:{decision_bead}",
        "integrity": "verified",
        "sensitivity": "internal",
        "retention": "durable",
    })
    return {
        "schemaVersion": 1,
        "resultType": "constraint",
        "category": "answer" if kind == "question" else "authorization",
        "source": f"ticket-{kind}",
        "retention": "durable",
        "decisionBead": decision_bead,
        "targetBead": target_bead,
        "status": status,
        "evidenceRefs": [evidence_ref],
        "authority": {"status": "none", "allowedEffects": []},
    }


def validate_finding(
    value: Any,
    *,
    public: bool = False,
    public_extensions: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or not FINDING_CORE_FIELDS.issubset(value):
        raise ValueError("finding core fields are invalid")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("finding schema is invalid")
    for field in ("id", "category", "severity", "claim", "proposedIntervention"):
        if not _text(value.get(field)):
            label = "intervention" if field == "proposedIntervention" else field
            raise ValueError(f"finding {label} is invalid")
    for field in ("activity", "source"):
        if not isinstance(value.get(field), str) or not OPAQUE_ID.fullmatch(value[field]):
            raise ValueError(f"finding {field} is invalid")
    status = value.get("status")
    if status not in FINDING_STATUSES:
        raise ValueError("finding status is invalid")
    evidence_refs = _finding_evidence_refs(value.get("evidenceRefs"))
    verification = value.get("verification")
    if status == "unverified":
        if verification is not None:
            raise ValueError("finding verification must be absent while unverified")
    elif (
        not isinstance(verification, dict)
        or set(verification) != {"method", "evidenceRefs"}
        or verification.get("method") not in VERIFICATION_METHODS
    ):
        raise ValueError("finding verification is invalid")
    else:
        verification_refs = _finding_evidence_refs(verification.get("evidenceRefs"))
        if any(ref not in evidence_refs for ref in verification_refs):
            raise ValueError("finding verification references unknown evidence")
    if public:
        allowed = set(public_extensions or ())
        if any(not isinstance(field, str) or not field for field in allowed):
            raise ValueError("public finding extension fields are invalid")
        if set(value) - FINDING_CORE_FIELDS - allowed:
            raise ValueError("public finding cannot copy raw private evidence")
    return value


def validate_control_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "policyVersion",
        "mode",
        "activities",
    }:
        raise ValueError("quality control plan fields are invalid")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("quality control plan schema is invalid")
    if not _text(value.get("policyVersion")) or not OPAQUE_ID.fullmatch(value["policyVersion"]):
        raise ValueError("quality control plan version is invalid")
    if value.get("mode") not in {"disabled", "observe"}:
        raise ValueError("quality control plan mode is invalid")
    activities = value.get("activities")
    if not isinstance(activities, list) or [item.get("id") if isinstance(item, dict) else None for item in activities] != list(ACTIVITY_IDS):
        raise ValueError("quality control plan activities are invalid")
    for activity in activities:
        if set(activity) != ACTIVITY_FIELDS:
            raise ValueError("quality control plan activity fields are invalid")
        for field in (
            "source",
            "trigger",
            "owner",
            "method",
            "output",
            "receiver",
            "acceptanceRule",
            "escalation",
            "retirementCondition",
        ):
            if not _text(activity[field]):
                raise ValueError(f"quality control plan activity {field} is invalid")
        if not _text_list(activity["inputs"]) or not _text_list(activity["evidence"]):
            raise ValueError("quality control plan activity inputs or evidence are invalid")
        budget = activity["budget"]
        if (
            not isinstance(budget, dict)
            or set(budget) != {"unit", "limitPercent"}
            or budget.get("unit") != "invocation-share"
            or type(budget.get("limitPercent")) is not int
            or not 1 <= budget["limitPercent"] <= 20
        ):
            raise ValueError("quality control plan activity budget is invalid")
    return value


def load_control_plan(
    plan_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    path = Path(plan_path) if plan_path is not None else CONTROL_PLAN_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("quality control plan is unavailable") from exc
    return validate_control_plan(value)


def _gaps(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > MAX_EVIDENCE_REFS
        or any(not isinstance(item, str) or not OPAQUE_ID.fullmatch(item) for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError("quality snapshot gaps are invalid")
    return value


def _validate_snapshot(value: Any) -> dict[str, Any]:
    fields = {"schemaVersion", "triggered", "evidenceRefs", "gaps", "signals"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("quality snapshot fields are invalid")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("quality snapshot schema is invalid")
    if type(value.get("triggered")) is not bool or not isinstance(value.get("signals"), dict):
        raise ValueError("quality snapshot trigger or signals are invalid")
    if any(not _text(key) for key in value["signals"]):
        raise ValueError("quality snapshot signals are invalid")
    _evidence_refs(value.get("evidenceRefs"))
    _gaps(value.get("gaps"))
    if len(_canonical(value).encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("quality snapshot exceeds bounded size")
    return value


def _validate_work_packet(value: Any, *, activity: str, mode: str) -> dict[str, Any] | None:
    if value is None and mode in {"disabled", "observe"}:
        return None
    fields = {
        "schemaVersion",
        "activity",
        "method",
        "receiver",
        "evidenceRefs",
        "gaps",
        "allowedEffects",
    }
    if (
        mode != "observe"
        or not isinstance(value, dict)
        or frozenset(value) not in {frozenset(fields), frozenset({*fields, "labels"})}
        or value.get("schemaVersion") != 1
        or value.get("activity") != activity
        or not _text(value.get("method"))
        or not _text(value.get("receiver"))
        or value.get("allowedEffects") != []
        or (
            "labels" in value
            and value["labels"] != [QUALITY_ACTIVITY_LABELS[activity]]
        )
    ):
        raise ValueError("quality receipt work packet is invalid")
    _evidence_refs(value.get("evidenceRefs"))
    _gaps(value.get("gaps"))
    return value


def _validate_receipt(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "receiptId",
        "dedupeKey",
        "policyVersion",
        "policyFingerprint",
        "snapshotFingerprint",
        "activity",
        "mode",
        "triggerReason",
        "evidenceRefs",
        "gaps",
        "authority",
        "workPacket",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("quality receipt fields are invalid")
    if value.get("schemaVersion") != 1 or type(value.get("schemaVersion")) is not int:
        raise ValueError("quality receipt schema is invalid")
    if value.get("activity") not in ACTIVITY_IDS or value.get("mode") not in {"disabled", "observe"}:
        raise ValueError("quality receipt decision is invalid")
    if (
        not _text(value.get("policyVersion"))
        or not OPAQUE_ID.fullmatch(value["policyVersion"])
        or not _text(value.get("triggerReason"))
    ):
        raise ValueError("quality receipt context is invalid")
    if not HASH_REF.fullmatch(str(value.get("policyFingerprint") or "")) or not HASH_REF.fullmatch(str(value.get("snapshotFingerprint") or "")):
        raise ValueError("quality receipt fingerprint is invalid")
    _evidence_refs(value.get("evidenceRefs"))
    _gaps(value.get("gaps"))
    if value.get("authority") != {"status": "unknown", "allowedEffects": []}:
        raise ValueError("quality receipt authority is invalid")
    packet = _validate_work_packet(
        value.get("workPacket"), activity=value["activity"], mode=value["mode"]
    )
    if value["mode"] == "observe" and (value["triggerReason"] == "not-triggered") != (packet is None):
        raise ValueError("quality receipt trigger and work packet conflict")
    if packet is not None and (
        packet["evidenceRefs"] != value["evidenceRefs"] or packet["gaps"] != value["gaps"]
    ):
        raise ValueError("quality receipt evidence and work packet conflict")
    core = {key: item for key, item in value.items() if key not in {"receiptId", "dedupeKey"}}
    expected_id = "quality-" + _fingerprint(core).partition(":")[2]
    if value.get("receiptId") != expected_id or value.get("dedupeKey") != expected_id:
        raise ValueError("quality receipt identity is invalid")
    return value


def _validate_application(value: Any) -> dict[str, Any]:
    fields = {"schemaVersion", "status", "receiptId", "activity", "authority", "assignmentRef"}
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != 1
        or value.get("status") not in {"observed", "disabled", "not-due"}
        or value.get("activity") not in ACTIVITY_IDS
        or value.get("authority") != {"status": "unknown", "allowedEffects": []}
        or not isinstance(value.get("receiptId"), str)
        or not OPAQUE_ID.fullmatch(value["receiptId"])
    ):
        raise ValueError("quality application row is invalid")
    assignment_ref = value.get("assignmentRef")
    expected_ref = f"artifact:quality-assignment-{value['receiptId']}"
    if (value["status"] == "observed" and assignment_ref != expected_ref) or (
        value["status"] != "observed" and assignment_ref is not None
    ):
        raise ValueError("quality application assignment reference is invalid")
    return value


def _persist_receipt(receipt: dict[str, Any], directory: str | os.PathLike[str] | None) -> None:
    with _locked_store(directory, RECEIPTS_NAME, exclusive=True) as (fd, root):
        assert fd is not None
        rows = _read_json_rows(fd, _validate_receipt, "receipt")
        matches = [row for row in rows if row["receiptId"] == receipt["receiptId"]]
        if matches and any(row != receipt for row in matches):
            raise ValueError("quality receipt identity conflicts")
        if not matches:
            _append_row(fd, root, receipt)


def assess(
    snapshot: Any,
    activity: str,
    *,
    directory: str | os.PathLike[str] | None = None,
    plan_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    plan = load_control_plan(plan_path)
    snapshot = _validate_snapshot(snapshot)
    selected = next((item for item in plan["activities"] if item["id"] == activity), None)
    if selected is None:
        raise ValueError("quality activity is unknown")
    triggered = snapshot["triggered"]
    packet = None
    if plan["mode"] == "observe" and triggered:
        packet = {
            "schemaVersion": 1,
            "activity": activity,
            "method": selected["method"],
            "receiver": selected["receiver"],
            "evidenceRefs": snapshot["evidenceRefs"],
            "gaps": snapshot["gaps"],
            "labels": [QUALITY_ACTIVITY_LABELS[activity]],
            "allowedEffects": [],
        }
    core = {
        "schemaVersion": 1,
        "policyVersion": plan["policyVersion"],
        "policyFingerprint": _fingerprint(plan),
        "snapshotFingerprint": _fingerprint(snapshot),
        "activity": activity,
        "mode": plan["mode"],
        "triggerReason": selected["trigger"] if triggered else "not-triggered",
        "evidenceRefs": snapshot["evidenceRefs"],
        "gaps": snapshot["gaps"],
        "authority": {"status": "unknown", "allowedEffects": []},
        "workPacket": packet,
    }
    receipt_id = "quality-" + _fingerprint(core).partition(":")[2]
    receipt = _validate_receipt({**core, "receiptId": receipt_id, "dedupeKey": receipt_id})
    _persist_receipt(receipt, directory)
    return receipt


def _load_receipt(
    receipt_id: str,
    directory: str | os.PathLike[str] | None,
) -> dict[str, Any]:
    if not isinstance(receipt_id, str) or not OPAQUE_ID.fullmatch(receipt_id):
        raise ValueError("quality receipt ID is invalid")
    with _locked_store(directory, RECEIPTS_NAME, exclusive=False) as (fd, _root):
        rows = _read_json_rows(fd, _validate_receipt, "receipt") if fd is not None else []
    matches = [row for row in rows if row["receiptId"] == receipt_id]
    if len(matches) != 1:
        raise ValueError("quality receipt is unavailable")
    return matches[0]


def _write_private_assignment(
    root: Path,
    receipt_id: str,
    packet: dict[str, Any],
) -> str:
    assignments = root / "assignments"
    assignments.mkdir(mode=0o700, exist_ok=True)
    if assignments.is_symlink() or not assignments.is_dir():
        raise OSError("quality assignments path is not a directory")
    assignments.chmod(0o700)
    path = assignments / f"{receipt_id}.json"
    encoded = (_canonical(packet) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        existing_flags = os.O_RDONLY | (os.O_NOFOLLOW if hasattr(os, "O_NOFOLLOW") else 0)
        existing = os.open(path, existing_flags)
        try:
            mode = os.fstat(existing).st_mode
            data = os.read(existing, len(encoded) + 1)
            if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o600 or data != encoded:
                raise OSError("quality assignment conflicts")
        finally:
            os.close(existing)
    else:
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(encoded)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        except Exception:
            os.close(fd)
            path.unlink(missing_ok=True)
            raise
        else:
            os.close(fd)
            directory_fd = os.open(assignments, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    return f"artifact:quality-assignment-{receipt_id}"


def apply(
    receipt_id: str,
    *,
    directory: str | os.PathLike[str] | None = None,
    plan_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    receipt = _load_receipt(receipt_id, directory)
    plan = load_control_plan(plan_path)
    if receipt["policyFingerprint"] != _fingerprint(plan):
        return {
            "schemaVersion": 1,
            "status": "blocked",
            "receiptId": receipt_id,
            "reason": "policy-mismatch",
        }
    activity = next(item for item in plan["activities"] if item["id"] == receipt["activity"])
    packet = receipt["workPacket"]
    if (
        receipt["policyVersion"] != plan["policyVersion"]
        or receipt["mode"] != plan["mode"]
        or receipt["triggerReason"] not in {"not-triggered", activity["trigger"]}
        or (
            packet is not None
            and (
                packet["method"] != activity["method"]
                or packet["receiver"] != activity["receiver"]
            )
        )
    ):
        raise ValueError("quality receipt does not match current control plan")
    with _locked_store(directory, APPLICATIONS_NAME, exclusive=True) as (fd, root):
        assert fd is not None
        rows = _read_json_rows(fd, _validate_application, "application")
        matches = [row for row in rows if row["receiptId"] == receipt_id]
        if len(matches) > 1:
            raise ValueError("quality application identity conflicts")
        if matches:
            return matches[0]
        assignment_ref = _write_private_assignment(root, receipt_id, packet) if packet is not None else None
        status = "observed" if packet is not None else "disabled" if receipt["mode"] == "disabled" else "not-due"
        result = _validate_application({
            "schemaVersion": 1,
            "status": status,
            "receiptId": receipt_id,
            "activity": receipt["activity"],
            "authority": receipt["authority"],
            "assignmentRef": assignment_ref,
        })
        _append_row(fd, root, result)
        return result


def quality_status(
    *,
    directory: str | os.PathLike[str] | None = None,
    plan_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    plan = load_control_plan(plan_path)
    with _locked_store(directory, RECEIPTS_NAME, exclusive=False) as (fd, _root):
        receipts = _read_json_rows(fd, _validate_receipt, "receipt") if fd is not None else []
    with _locked_store(directory, APPLICATIONS_NAME, exclusive=False) as (fd, _root):
        applications = _read_json_rows(fd, _validate_application, "application") if fd is not None else []
    return {
        "schemaVersion": 1,
        "status": "ok",
        "mode": plan["mode"],
        "policyVersion": plan["policyVersion"],
        "policyFingerprint": _fingerprint(plan),
        "receipts": len(receipts),
        "applications": len(applications),
        "assignments": sum(item["assignmentRef"] is not None for item in applications),
    }


def _beads(args: list[str]) -> tuple[int, Any, str]:
    from .work import run_beads_json

    return run_beads_json(args)


def cmd_quality(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="agnt quality",
        description="Capture and normalize facts or assess observe-only quality policy.",
    )
    sub = parser.add_subparsers(dest="action")
    capture_cmd = sub.add_parser("capture", help="append a validated invocation or result fact")
    capture_cmd.add_argument("--payload", help="JSON capture payload; defaults to stdin")
    capture_cmd.add_argument("--json", action="store_true")
    normalize_ask_cmd = sub.add_parser(
        "normalize-ask", help="normalize transient ask results without persistence"
    )
    normalize_ask_cmd.add_argument("--payload", help="JSON result array; defaults to stdin")
    normalize_ask_cmd.add_argument("--json", action="store_true")
    normalize_result_cmd = sub.add_parser(
        "normalize-result", help="normalize editor or takeover result evidence"
    )
    normalize_result_cmd.add_argument("--payload", help="JSON result; defaults to stdin")
    normalize_result_cmd.add_argument("--json", action="store_true")
    assess_cmd = sub.add_parser("assess", help="persist one deterministic decision receipt")
    assess_cmd.add_argument("--activity", required=True)
    assess_input = assess_cmd.add_mutually_exclusive_group()
    assess_input.add_argument("--snapshot", help="JSON snapshot; defaults to stdin")
    assess_input.add_argument("--collect", action="store_true", help="derive snapshot from durable local signals")
    assess_cmd.add_argument("--root")
    assess_cmd.add_argument("--runs-dir")
    assess_cmd.add_argument("--no-beads", action="store_true")
    assess_cmd.add_argument("--json", action="store_true")
    apply_cmd = sub.add_parser("apply", help="apply one current receipt within observe-only policy")
    apply_cmd.add_argument("--receipt", required=True)
    apply_cmd.add_argument("--json", action="store_true")
    status_cmd = sub.add_parser("status", help="show current policy and private receipt counts")
    status_cmd.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.action is None:
        parser.print_help()
        return 0
    try:
        if args.action == "capture":
            raw = args.payload if args.payload is not None else sys.stdin.read()
            result = capture(json.loads(raw), beads_runner=_beads)
        elif args.action == "normalize-ask":
            raw = args.payload if args.payload is not None else sys.stdin.read()
            result = normalize_ask_results(json.loads(raw))
        elif args.action == "normalize-result":
            raw = args.payload if args.payload is not None else sys.stdin.read()
            result = normalize_external_result(json.loads(raw))
        elif args.action == "assess":
            if args.activity not in ACTIVITY_IDS:
                raise ValueError("quality activity is unknown")
            if args.collect:
                snapshots = durable_activity_snapshots(
                    root=Path(args.root).expanduser() if args.root else None,
                    runs_dir=Path(args.runs_dir).expanduser() if args.runs_dir else None,
                    beads=[] if args.no_beads else None,
                )
                snapshot = snapshots[args.activity]
            else:
                raw = args.snapshot if args.snapshot is not None else sys.stdin.read()
                snapshot = json.loads(raw)
            result = assess(snapshot, args.activity)
        elif args.action == "apply":
            result = apply(args.receipt)
        else:
            result = quality_status()
    except (json.JSONDecodeError, OSError, ValueError):
        error = f"quality {args.action} failed"
        print(json.dumps({"schemaVersion": 1, "status": "error", "error": error}))
        return 2
    print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
    return 3 if result.get("status") == "blocked" else 0
