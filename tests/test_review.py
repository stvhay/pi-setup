from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "pi" / "agent" / "skills" / "requesting-code-review" / "review-findings.schema.json"


def discovery_document() -> dict:
    return {
        "schemaVersion": 1,
        "reviewId": "review-123",
        "scope": "behavioral",
        "reviewer": {
            "target": "openrouter-localish/google/gemma-4-31b-it",
            "family": "gemma4-31b",
        },
        "findings": [
            {
                "id": "F-001",
                "severity": "important",
                "category": "behavior-preservation",
                "location": "src/example.py:42",
                "claim": "The fallback skips the existing retry path.",
                "failureScenario": "When the first request times out, the operation exits instead of retrying once.",
                "evidence": "The new early return precedes call_retry() in the changed branch.",
                "status": "unverified",
            }
        ],
    }


def test_discovery_finding_document_is_valid(agnt):
    assert agnt.validate_review_document(discovery_document()) == []


def test_adjudicated_finding_requires_external_verification_evidence(agnt):
    document = discovery_document()
    document["findings"][0]["status"] = "confirmed"

    errors = agnt.validate_review_document(document)

    assert any("verification is required" in error for error in errors)

    document["findings"][0]["verification"] = {
        "verifierFamily": "gpt-5.6-sol",
        "method": "test",
        "evidence": "pytest tests/test_retry.py::test_timeout_retries failed before the fix and passed after it.",
        "command": "pytest tests/test_retry.py::test_timeout_retries",
    }
    assert agnt.validate_review_document(document) == []


def test_review_finding_schema_rejects_confidence_and_vague_records(agnt):
    document = discovery_document()
    finding = document["findings"][0]
    finding["confidence"] = "high"
    finding["failureScenario"] = "  "

    errors = agnt.validate_review_document(document)

    assert any("confidence" in error for error in errors)
    assert any("failureScenario" in error for error in errors)


def test_review_finding_summary_counts_verification_outcomes(agnt):
    document = discovery_document()
    base = document["findings"][0]
    document["findings"] = [
        base,
        {
            **base,
            "id": "F-002",
            "severity": "critical",
            "status": "confirmed",
            "verification": {
                "verifierFamily": "gpt-5.6-sol",
                "method": "reproducer",
                "evidence": "The reproducer deletes the sibling record.",
                "command": "python /tmp/reproduce.py",
            },
        },
        {
            **base,
            "id": "F-003",
            "severity": "minor",
            "status": "refuted",
            "verification": {
                "verifierFamily": "gpt-5.6-sol",
                "method": "inspection",
                "evidence": "The caller normalizes the value before this branch.",
            },
        },
        {
            **base,
            "id": "F-004",
            "status": "unresolved",
            "verification": {
                "verifierFamily": "gpt-5.6-sol",
                "method": "specification",
                "evidence": "The two relevant requirements conflict.",
            },
        },
    ]

    assert agnt.summarize_review_findings(document) == {
        "total": 4,
        "unverified": 1,
        "confirmed": 1,
        "refuted": 1,
        "unresolved": 1,
        "bySeverity": {"critical": 1, "important": 2, "minor": 1},
    }


def test_review_annotation_fields_link_findings_to_invocation(agnt):
    document = discovery_document()
    document["reviewer"]["recordId"] = "metric-123"

    fields = agnt.review_annotation_fields(document, expected_record_id="metric-123")

    assert fields["reviewId"] == "review-123"
    assert fields["reviewScope"] == "behavioral"
    assert fields["reviewFindingStats"]["unverified"] == 1
    assert fields["reviewFindings"] == [
        {
            "id": "F-001",
            "severity": "important",
            "category": "behavior-preservation",
            "status": "unverified",
            "verificationMethod": None,
            "verifierFamily": None,
        }
    ]

    with pytest.raises(ValueError, match="does not match"):
        agnt.review_annotation_fields(document, expected_record_id="different")

    with pytest.raises(ValueError, match="reviewer target"):
        agnt.review_annotation_fields(
            document,
            expected_record_id="metric-123",
            expected_target="openrouter-localish/deepseek/deepseek-v4-flash",
        )


def test_review_loader_accepts_one_exact_json_code_fence(agnt, tmp_path):
    path = tmp_path / "findings.md"
    path.write_text(
        "```json\n" + json.dumps(discovery_document()) + "\n```\n",
        encoding="utf-8",
    )

    assert agnt.load_review_document(path) == discovery_document()


def test_review_cli_validates_and_summarizes_document(agnt, tmp_path, capsys):
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(discovery_document()), encoding="utf-8")

    assert agnt.cmd_review(["validate", str(path)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["valid"] is True

    assert agnt.cmd_review(["summary", str(path)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["summary"]["total"] == 1


def test_metrics_summary_exposes_verified_finding_yield_per_cost(agnt):
    target = "openrouter-localish/google/gemma-4-31b-it"
    record = {
        "target": target,
        "task": "review",
        "elapsedMs": 1000,
        "responseChars": 10,
        "stderrChars": 0,
        "exitCode": 0,
        "reviewScope": "behavioral",
        "reviewFindingStats": {
            "total": 3,
            "unverified": 0,
            "confirmed": 2,
            "refuted": 1,
            "unresolved": 0,
            "bySeverity": {"important": 3},
        },
        "usage": {
            "input": 100,
            "output": 20,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 120,
            "cost": {
                "input": 0.4,
                "output": 0.1,
                "cacheRead": 0.0,
                "cacheWrite": 0.0,
                "total": 0.5,
            },
        },
    }

    summary = agnt.summarize_metrics([record])

    assert summary["reviewScopes"] == {"behavioral": 1}
    assert summary["reviewFindings"]["confirmed"] == 2
    model = summary["byModel"][target]
    assert model["reviewFindings"]["refuted"] == 1
    assert model["confirmedFindingsPerUsd"] == pytest.approx(4.0)


def test_metrics_annotation_accepts_validated_findings_file(agnt, tmp_path, capsys):
    metrics_dir = tmp_path / "metrics"
    annotations = tmp_path / "annotations.jsonl"
    findings = tmp_path / "findings.json"
    record = agnt.metrics_record(
        target="openrouter-localish/google/gemma-4-31b-it",
        task="review",
        started_at="2026-07-21T00:00:00Z",
        ended_at="2026-07-21T00:00:01Z",
        elapsed_ms=1000,
        code=0,
        prompt="packet",
        out="review",
        err="",
        usage=None,
        usage_source="unavailable",
        invocation_mode="one-shot",
    )
    agnt.write_json(metrics_dir / "review.metrics.json", record)
    document = discovery_document()
    document["reviewer"]["recordId"] = record["recordId"]
    findings.write_text(json.dumps(document), encoding="utf-8")

    assert agnt.cmd_metrics([
        "annotate",
        record["recordId"],
        "--metrics-dir",
        str(metrics_dir),
        "--annotations-file",
        str(annotations),
        "--findings-file",
        str(findings),
    ]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["annotation"]["reviewId"] == "review-123"
    assert output["annotation"]["reviewFindingStats"]["unverified"] == 1
    stored = json.loads(annotations.read_text(encoding="utf-8"))
    assert stored["reviewFindings"][0]["id"] == "F-001"


def test_tracked_schema_matches_required_discovery_fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    finding = schema["$defs"]["finding"]
    assert set(
        [
            "id",
            "severity",
            "category",
            "location",
            "claim",
            "failureScenario",
            "evidence",
            "status",
        ]
    ).issubset(finding["required"])
    assert finding["additionalProperties"] is False
