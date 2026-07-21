from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


REVIEW_SCOPES = {"behavioral", "boundary"}
FINDING_SEVERITIES = {"critical", "important", "minor"}
FINDING_STATUSES = {"unverified", "confirmed", "refuted", "unresolved"}
VERIFICATION_METHODS = {"test", "reproducer", "inspection", "profile", "specification"}

_ROOT_FIELDS = {"schemaVersion", "reviewId", "scope", "reviewer", "findings"}
_REVIEWER_FIELDS = {"target", "family", "recordId"}
_FINDING_FIELDS = {
    "id",
    "severity",
    "category",
    "location",
    "claim",
    "failureScenario",
    "evidence",
    "status",
    "verification",
}
_VERIFICATION_FIELDS = {"verifierFamily", "method", "evidence", "command"}
_FINDING_REQUIRED = (
    "id",
    "severity",
    "category",
    "location",
    "claim",
    "failureScenario",
    "evidence",
    "status",
)


def _extra_fields(value: Dict[str, Any], allowed: set[str], path: str, errors: List[str]) -> None:
    for field in sorted(set(value) - allowed):
        errors.append(f"{path}.{field} is not allowed")


def _required_string(value: Dict[str, Any], field: str, path: str, errors: List[str]) -> None:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        errors.append(f"{path}.{field} must be a non-empty string")


def validate_review_document(document: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(document, dict):
        return ["document must be an object"]
    _extra_fields(document, _ROOT_FIELDS, "document", errors)
    if document.get("schemaVersion") != 1:
        errors.append("document.schemaVersion must equal 1")
    _required_string(document, "reviewId", "document", errors)
    if document.get("scope") not in REVIEW_SCOPES:
        errors.append("document.scope must be behavioral or boundary")

    reviewer = document.get("reviewer")
    if not isinstance(reviewer, dict):
        errors.append("document.reviewer must be an object")
    else:
        _extra_fields(reviewer, _REVIEWER_FIELDS, "document.reviewer", errors)
        _required_string(reviewer, "target", "document.reviewer", errors)
        _required_string(reviewer, "family", "document.reviewer", errors)
        if "recordId" in reviewer:
            _required_string(reviewer, "recordId", "document.reviewer", errors)

    findings = document.get("findings")
    if not isinstance(findings, list):
        errors.append("document.findings must be an array")
        return errors

    finding_ids: set[str] = set()
    for index, finding in enumerate(findings):
        path = f"document.findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{path} must be an object")
            continue
        _extra_fields(finding, _FINDING_FIELDS, path, errors)
        for field in _FINDING_REQUIRED:
            _required_string(finding, field, path, errors)
        finding_id = finding.get("id")
        if isinstance(finding_id, str) and finding_id.strip():
            if finding_id in finding_ids:
                errors.append(f"{path}.id duplicates {finding_id}")
            finding_ids.add(finding_id)
        if finding.get("severity") not in FINDING_SEVERITIES:
            errors.append(f"{path}.severity must be critical, important, or minor")
        status = finding.get("status")
        if status not in FINDING_STATUSES:
            errors.append(f"{path}.status must be unverified, confirmed, refuted, or unresolved")

        verification = finding.get("verification")
        if status == "unverified":
            if verification is not None:
                errors.append(f"{path}.verification must be absent while status is unverified")
            continue
        if not isinstance(verification, dict):
            errors.append(f"{path}.verification is required for status {status}")
            continue
        _extra_fields(verification, _VERIFICATION_FIELDS, f"{path}.verification", errors)
        _required_string(verification, "verifierFamily", f"{path}.verification", errors)
        _required_string(verification, "evidence", f"{path}.verification", errors)
        if verification.get("method") not in VERIFICATION_METHODS:
            errors.append(
                f"{path}.verification.method must be test, reproducer, inspection, profile, or specification"
            )
        if "command" in verification:
            _required_string(verification, "command", f"{path}.verification", errors)
    return errors


def load_review_document(path: Path | str) -> Dict[str, Any]:
    source = Path(path).expanduser()
    try:
        text = source.read_text(encoding="utf-8").strip()
        if text.startswith("```json\n") and text.endswith("\n```"):
            text = text[len("```json\n") : -len("\n```")]
        document = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load review findings from {source}: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"review findings document in {source} must be an object")
    return document


def summarize_review_findings(document: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total": 0,
        "unverified": 0,
        "confirmed": 0,
        "refuted": 0,
        "unresolved": 0,
        "bySeverity": {},
    }
    for finding in document.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        summary["total"] += 1
        status = str(finding.get("status") or "unverified")
        if status in FINDING_STATUSES:
            summary[status] += 1
        severity = str(finding.get("severity") or "unknown")
        by_severity = summary["bySeverity"]
        by_severity[severity] = int(by_severity.get(severity) or 0) + 1
    summary["bySeverity"] = dict(sorted(summary["bySeverity"].items()))
    return summary


def review_annotation_fields(
    document: Dict[str, Any],
    *,
    expected_record_id: str | None = None,
    expected_target: str | None = None,
    expected_family: str | None = None,
) -> Dict[str, Any]:
    errors = validate_review_document(document)
    if errors:
        raise ValueError("invalid review findings: " + "; ".join(errors))
    reviewer = document["reviewer"]
    reviewer_record_id = reviewer.get("recordId")
    if reviewer_record_id and expected_record_id and reviewer_record_id != expected_record_id:
        raise ValueError(
            f"reviewer recordId {reviewer_record_id!r} does not match invocation {expected_record_id!r}"
        )
    if expected_target and reviewer.get("target") != expected_target:
        raise ValueError(
            f"reviewer target {reviewer.get('target')!r} does not match invocation {expected_target!r}"
        )
    if expected_family and reviewer.get("family") != expected_family:
        raise ValueError(
            f"reviewer family {reviewer.get('family')!r} does not match invocation {expected_family!r}"
        )
    findings = []
    for finding in document["findings"]:
        verification = finding.get("verification") if isinstance(finding.get("verification"), dict) else {}
        findings.append(
            {
                "id": finding["id"],
                "severity": finding["severity"],
                "category": finding["category"],
                "status": finding["status"],
                "verificationMethod": verification.get("method"),
                "verifierFamily": verification.get("verifierFamily"),
            }
        )
    return {
        "reviewId": document["reviewId"],
        "reviewScope": document["scope"],
        "reviewFindings": findings,
        "reviewFindingStats": summarize_review_findings(document),
    }


def cmd_review(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt review", description="Validate and summarize structured review findings.")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("validate")
    sub.add_parser("summary")
    if not argv:
        parser.print_help()
        return 0
    action, rest = argv[0], argv[1:]
    if action in {"-h", "--help"}:
        parser.print_help()
        return 0
    if action not in {"validate", "summary"}:
        parser.error(f"unknown action: {action}")
    command = argparse.ArgumentParser(prog=f"agnt review {action}")
    command.add_argument("findings_file")
    args = command.parse_args(rest)
    try:
        document = load_review_document(args.findings_file)
    except ValueError as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    errors = validate_review_document(document)
    payload: Dict[str, Any] = {
        "findingsFile": str(Path(args.findings_file).expanduser()),
        "valid": not errors,
        "errors": errors,
    }
    if not errors:
        payload["summary"] = summarize_review_findings(document)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1
