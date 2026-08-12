from __future__ import annotations

import io
import json
import re
import stat
import sys
import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pi" / "agent" / "bin"))

from agnt_lib import improvement, langfuse

LangfuseClient = langfuse.LangfuseClient


class FakeTelemetryClient(LangfuseClient):
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.bodies: list[dict[str, Any] | None] = []

    def _request(self, method: str, path: str, body=None, params=None):
        self.calls.append((method, path, dict(params or {})))
        self.bodies.append(body)
        return self.responses.pop(0)


def test_observation_reads_are_time_bounded_and_stop_at_limit():
    client = FakeTelemetryClient([
        {"data": [{"id": "one"}, {"id": "two"}], "meta": {"page": 1, "totalPages": 2}},
        {"data": [{"id": "three"}, {"id": "ignored"}], "meta": {"page": 2, "totalPages": 2}},
    ])

    rows = client.list_observations(
        from_start_time="2026-07-26T00:00:00Z",
        to_start_time="2026-07-27T00:00:00Z",
        limit=3,
        page_size=2,
    )

    assert [row["id"] for row in rows] == ["one", "two", "three"]
    assert client.calls == [
        (
            "GET",
            "/api/public/observations",
            {
                "fromStartTime": "2026-07-26T00:00:00Z",
                "toStartTime": "2026-07-27T00:00:00Z",
                "limit": 2,
                "page": 1,
            },
        ),
        (
            "GET",
            "/api/public/observations",
            {
                "fromStartTime": "2026-07-26T00:00:00Z",
                "toStartTime": "2026-07-27T00:00:00Z",
                "limit": 1,
                "page": 2,
            },
        ),
    ]


def test_observation_reads_can_filter_one_trace():
    client = FakeTelemetryClient([{"data": [], "meta": {"page": 1, "totalPages": 1}}])

    client.list_observations(
        from_start_time="2026-07-26T00:00:00Z",
        to_start_time="2026-07-27T00:00:00Z",
        trace_id="private-trace",
        limit=1,
    )

    assert client.calls[0][2]["traceId"] == "private-trace"


def test_observation_reads_reject_missing_bounds_or_nonpositive_limits():
    client = FakeTelemetryClient([])

    with pytest.raises(ValueError, match="time bounds"):
        client.list_observations(from_start_time="", to_start_time="2026-07-27T00:00:00Z", limit=1)
    with pytest.raises(ValueError, match="positive"):
        client.list_observations(from_start_time="2026-07-26T00:00:00Z", to_start_time="2026-07-27T00:00:00Z", limit=0)

    assert client.calls == []


def test_legacy_list_traces_return_contract_is_paginated():
    client = FakeTelemetryClient([
        {"data": [{"id": "first"}], "meta": {"page": 1, "totalPages": 2}},
        {"data": [{"id": "second"}], "meta": {"page": 2, "totalPages": 2}},
    ])

    rows = client.list_traces(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        limit=2,
        page_size=1,
    )

    assert isinstance(rows, list)
    assert [row["id"] for row in rows] == ["first", "second"]
    assert client.calls == [
        (
            "GET",
            "/api/public/traces",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "limit": 1,
                "page": 1,
            },
        ),
        (
            "GET",
            "/api/public/traces",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "limit": 1,
                "page": 2,
            },
        ),
    ]


def test_trace_discovery_paginates_until_api_end():
    client = FakeTelemetryClient([
        {"data": [{"id": "first"}], "meta": {}},
        {"data": [{"id": "second"}], "meta": {}},
        {"data": [], "meta": {}},
    ])

    assert hasattr(client, "list_traces_with_metadata")
    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        page_size=1,
    )

    assert discovery == {
        "traces": [{"id": "first"}, {"id": "second"}],
        "totalAvailable": None,
        "scanned": 2,
        "maxTraces": 500,
        "complete": True,
        "continuation": {"hasMore": False, "nextPage": None, "reason": "api-end"},
    }
    assert [call[2]["page"] for call in client.calls] == [1, 2, 3]


def test_trace_discovery_reports_lower_bounds_from_api_total():
    client = FakeTelemetryClient([
        {
            "data": [{"id": "first"}, {"id": "second"}],
            "meta": {"page": 1, "totalPages": 1, "totalItems": 3},
        },
    ])

    assert hasattr(client, "list_traces_with_metadata")
    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
    )

    assert discovery["totalAvailable"] == 3
    assert discovery["scanned"] == 2
    assert discovery["complete"] is False
    assert discovery["continuation"] == {
        "hasMore": True,
        "nextPage": 2,
        "reason": "api-incomplete",
    }


def test_trace_discovery_stops_at_operator_max_and_reports_lower_bound():
    client = FakeTelemetryClient([{
        "data": [{"id": "first"}, {"id": "second"}],
        "meta": {"page": 1, "totalPages": 3, "totalItems": 5},
    }])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=2,
    )

    assert discovery == {
        "traces": [{"id": "first"}, {"id": "second"}],
        "totalAvailable": 5,
        "scanned": 2,
        "maxTraces": 2,
        "complete": False,
        "continuation": {"hasMore": True, "nextPage": 2, "reason": "max-traces"},
    }


def test_trace_discovery_validates_total_against_raw_page_before_operator_cap():
    client = FakeTelemetryClient([{
        "data": [{"id": "first"}, {"id": "overflow"}],
        "meta": {"totalItems": 1},
    }])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=1,
    )

    assert discovery == {
        "traces": [{"id": "first"}],
        "totalAvailable": None,
        "scanned": 1,
        "maxTraces": 1,
        "complete": False,
        "continuation": {"hasMore": True, "nextPage": 2, "reason": "max-traces"},
    }


def test_trace_discovery_at_cap_honors_later_total_pages():
    client = FakeTelemetryClient([{
        "data": [{"id": "first"}],
        "meta": {"page": 1, "totalPages": 2, "totalItems": 1},
    }])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=1,
    )

    assert discovery == {
        "traces": [{"id": "first"}],
        "totalAvailable": 1,
        "scanned": 1,
        "maxTraces": 1,
        "complete": False,
        "continuation": {"hasMore": True, "nextPage": 2, "reason": "max-traces"},
    }


def test_trace_discovery_keeps_empty_nonterminal_page_incomplete():
    client = FakeTelemetryClient([{
        "data": [],
        "meta": {"page": 1, "totalPages": 2},
    }])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=10,
    )

    assert discovery == {
        "traces": [],
        "totalAvailable": None,
        "scanned": 0,
        "maxTraces": 10,
        "complete": False,
        "continuation": {"hasMore": True, "nextPage": 2, "reason": "api-incomplete"},
    }


def test_trace_discovery_has_finite_safe_default():
    client = FakeTelemetryClient([{"data": [], "meta": {}}])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
    )

    assert discovery["maxTraces"] == 500


def test_trace_discovery_stops_on_repeated_page_without_counting_it_twice():
    page = {"data": [{"id": "first"}], "meta": {}}
    client = FakeTelemetryClient([page, page])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=10,
    )

    assert discovery["traces"] == [{"id": "first"}]
    assert discovery["complete"] is False
    assert discovery["continuation"] == {
        "hasMore": True,
        "nextPage": 2,
        "reason": "non-advancing-page",
    }
    assert len(client.calls) == 2


def test_trace_discovery_does_not_false_complete_on_empty_page_before_valid_total():
    client = FakeTelemetryClient([
        {"data": [{"id": "first"}], "meta": {"totalItems": 2}},
        {"data": [], "meta": {"totalItems": 2}},
    ])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=10,
    )

    assert discovery["totalAvailable"] == 2
    assert discovery["complete"] is False
    assert discovery["continuation"] == {
        "hasMore": True,
        "nextPage": 3,
        "reason": "api-incomplete",
    }


def test_trace_discovery_validates_total_before_stopping_on_repeated_page():
    client = FakeTelemetryClient([
        {"data": [{"id": "first"}], "meta": {"totalItems": 3}},
        {"data": [{"id": "first"}], "meta": {"totalItems": 4}},
    ])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=10,
    )

    assert discovery["traces"] == [{"id": "first"}]
    assert discovery["totalAvailable"] is None
    assert discovery["complete"] is False
    assert discovery["continuation"]["reason"] == "non-advancing-page"


@pytest.mark.parametrize("invalid_total", [True, 1.5, -1])
def test_trace_discovery_treats_invalid_totals_as_unavailable_without_false_completion(invalid_total):
    client = FakeTelemetryClient([{
        "data": [{"id": "first"}, {"id": "second"}],
        "meta": {"totalItems": invalid_total, "totalPages": 1},
    }])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=10,
    )

    assert discovery["totalAvailable"] is None
    assert discovery["scanned"] == 2
    assert discovery["complete"] is False
    assert discovery["continuation"] == {
        "hasMore": True,
        "nextPage": 2,
        "reason": "api-incomplete",
    }


def test_trace_discovery_treats_inconsistent_totals_as_unavailable_without_false_completion():
    client = FakeTelemetryClient([
        {"data": [{"id": "first"}], "meta": {"totalItems": 3, "totalPages": 2}},
        {"data": [{"id": "second"}], "meta": {"totalItems": 4, "totalPages": 2}},
    ])

    discovery = client.list_traces_with_metadata(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        max_traces=10,
    )

    assert discovery["totalAvailable"] is None
    assert discovery["scanned"] == 2
    assert discovery["complete"] is False
    assert discovery["continuation"] == {
        "hasMore": True,
        "nextPage": 3,
        "reason": "api-incomplete",
    }


def test_score_reads_follow_cursor_and_stop_at_limit():
    client = FakeTelemetryClient([
        {"data": [{"id": "one"}, {"id": "two"}], "meta": {"cursor": "next"}},
        {"data": [{"id": "three"}], "meta": {"cursor": None}},
    ])

    rows = client.list_scores(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        limit=3,
        page_size=2,
        name="improvement_review_status",
    )

    assert [row["id"] for row in rows] == ["one", "two", "three"]
    assert client.calls == [
        (
            "GET",
            "/api/public/v3/scores",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "fields": "details,subject",
                "name": "improvement_review_status",
                "limit": 2,
            },
        ),
        (
            "GET",
            "/api/public/v3/scores",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "fields": "details,subject",
                "name": "improvement_review_status",
                "limit": 1,
                "cursor": "next",
            },
        ),
    ]


def test_score_reads_can_filter_one_session():
    client = FakeTelemetryClient([{"data": [], "meta": {"cursor": None}}])

    client.list_scores(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        session_id="private-session",
        limit=1,
    )

    assert client.calls[0][2]["sessionId"] == "private-session"


def test_score_reads_can_filter_one_trace_and_clamp_page_size():
    client = FakeTelemetryClient([{"data": [], "meta": {"cursor": None}}])

    client.list_scores(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        trace_id="private-trace",
        limit=200,
        page_size=200,
    )

    assert client.calls[0][2]["traceId"] == "private-trace"
    assert client.calls[0][2]["limit"] == 100


def test_paginated_reads_reject_malformed_metadata():
    client = FakeTelemetryClient([{"data": [{"id": "private"}], "meta": "private telemetry"}])

    with pytest.raises(langfuse.LangfuseError) as caught:
        client.list_scores(
            from_timestamp="2026-07-26T00:00:00Z",
            to_timestamp="2026-07-27T00:00:00Z",
            limit=1,
        )

    assert str(caught.value) == "Langfuse response metadata was not an object"


def test_session_score_writes_use_caller_id_for_idempotent_updates():
    client = FakeTelemetryClient([{"id": "stable-score"}, {"id": "stable-score"}])
    kwargs = {
        "score_id": "stable-score",
        "session_id": "private-session",
        "name": "improvement_review_status",
        "metadata": {"reviewId": "private-review"},
    }

    client.put_session_score(value="reviewed", **kwargs)
    client.put_session_score(value="needs-human", **kwargs)

    assert client.calls == [
        ("POST", "/api/public/scores", {}),
        ("POST", "/api/public/scores", {}),
    ]
    assert client.bodies == [
        {
            "id": "stable-score",
            "sessionId": "private-session",
            "name": "improvement_review_status",
            "value": "reviewed",
            "dataType": "CATEGORICAL",
            "source": "API",
            "metadata": {"reviewId": "private-review"},
        },
        {
            "id": "stable-score",
            "sessionId": "private-session",
            "name": "improvement_review_status",
            "value": "needs-human",
            "dataType": "CATEGORICAL",
            "source": "API",
            "metadata": {"reviewId": "private-review"},
        },
    ]


def test_transport_errors_do_not_expose_url_headers_or_response_body(monkeypatch):
    client = LangfuseClient("https://private.example", "public-secret", "private-secret")

    def fail(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            503,
            "sensitive reason",
            request.headers,
            io.BytesIO(b"private telemetry body"),
        )

    monkeypatch.setattr(langfuse.urllib.request, "urlopen", fail)

    with pytest.raises(langfuse.LangfuseError) as caught:
        client._request("GET", "/api/public/observations", params={"traceId": "private-trace"})

    message = str(caught.value)
    assert "503" in message
    for private in ("private.example", "public-secret", "private-secret", "private-trace", "telemetry body", "sensitive reason"):
        assert private not in message


def test_paginated_reads_reject_non_list_data_without_echoing_it():
    client = FakeTelemetryClient([{"data": {"private": "telemetry"}}])

    with pytest.raises(langfuse.LangfuseError) as caught:
        client.list_traces(
            from_timestamp="2026-07-26T00:00:00Z",
            to_timestamp="2026-07-27T00:00:00Z",
            limit=1,
        )

    assert str(caught.value) == "Langfuse response data was not a list"


def test_malformed_response_error_does_not_echo_telemetry(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        langfuse.urllib.request,
        "urlopen",
        lambda request, timeout: Response(b'{"private": "telemetry"'),
    )
    client = LangfuseClient("https://private.example", "public-secret", "private-secret")

    with pytest.raises(langfuse.LangfuseError) as caught:
        client._request("GET", "/api/public/traces")

    assert str(caught.value) == "Langfuse response was not valid JSON"


class FakeScanClient:
    def __init__(self, traces, observations, reviewed=(), trace_scores=None):
        self.traces = traces
        self.observations = observations
        self.reviewed = (
            dict(reviewed)
            if isinstance(reviewed, dict)
            else {item: improvement.REVIEW_POLICY_VERSION for item in reviewed}
        )
        self.trace_scores = trace_scores or {}
        self.trace_limits = []
        self.trace_maxima = []
        self.score_sessions = []
        self.score_limits = []
        self.observation_traces = []

    def list_traces(self, **kwargs):
        self.trace_limits.append(kwargs["limit"])
        return self.traces[: kwargs["limit"]]

    def list_traces_with_metadata(self, **kwargs):
        self.trace_maxima.append(kwargs.get("max_traces"))
        return {
            "traces": self.traces,
            "totalAvailable": len(self.traces),
            "scanned": len(self.traces),
            "maxTraces": kwargs.get("max_traces"),
            "complete": True,
            "continuation": {"hasMore": False, "nextPage": None, "reason": "api-end"},
        }

    def list_scores(self, **kwargs):
        self.score_limits.append(kwargs["limit"])
        if kwargs.get("trace_id"):
            return self.trace_scores.get(kwargs["trace_id"], [])
        session_id = kwargs["session_id"]
        self.score_sessions.append(session_id)
        if session_id not in self.reviewed:
            return []
        return [{
            "value": "no-action",
            "metadata": {"reviewPolicyVersion": self.reviewed[session_id]},
            "subject": {"kind": "session", "id": session_id},
        }]

    def list_observations(self, **kwargs):
        trace_id = kwargs["trace_id"]
        self.observation_traces.append(trace_id)
        return self.observations.get(trace_id, [])[: kwargs["limit"]]


def _scan_sessions(client, tmp_path, **overrides):
    options = {
        "since": "2026-07-26T00:00:00Z",
        "until": "2026-07-27T00:00:00Z",
        "limit": 1,
        "output_dir": tmp_path / "private",
        "runs_dir": tmp_path / "runs",
        "repository_root": tmp_path / "repo",
        "dry_run": True,
    }
    options.update(overrides)
    return improvement.scan_sessions(client, **options)


def test_eligible_unreviewed_summary_is_bounded_and_payload_free():
    client = FakeScanClient(
        [
            _private_trace("session-unreviewed-a", "trace-a"),
            _private_trace("session-reviewed", "trace-b"),
            _private_trace("session-unreviewed-c", "trace-c"),
        ],
        {},
        reviewed={"session-reviewed": improvement.REVIEW_POLICY_VERSION},
    )

    summary = improvement.eligible_unreviewed_session_summary(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        max_traces=25,
    )

    assert summary == {
        "schemaVersion": 1,
        "status": "ok",
        "candidateSessions": 3,
        "eligibleSessions": 2,
        "reviewedSessionsSkipped": 1,
        "childSessionsExcluded": 0,
        "unclassifiedProjectionTraces": 0,
        "sessionClassificationComplete": True,
        "settlementLagSeconds": 300,
        "activeWindowExcluded": False,
        "traceDiscoveryComplete": True,
        "lowerBound": False,
    }
    assert client.trace_maxima == [25]
    assert sorted(client.score_sessions) == ["session-reviewed", "session-unreviewed-a", "session-unreviewed-c"]
    assert client.observation_traces == []
    assert not any(session_id in json.dumps(summary) for session_id in client.score_sessions)


def test_policy_v2_rechecks_sessions_reviewed_only_under_v1():
    client = FakeScanClient(
        [_private_trace("historical-session", "historical-trace")],
        {},
        reviewed={"historical-session": "v1"},
    )

    summary = improvement.eligible_unreviewed_session_summary(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
    )

    assert improvement.REVIEW_POLICY_VERSION == "v2"
    assert summary["eligibleSessions"] == 1
    assert summary["reviewedSessionsSkipped"] == 0


def _private_trace(session_id="run-private-run", trace_id="private-trace"):
    return {
        "id": trace_id,
        "sessionId": session_id,
        "timestamp": "2026-07-26T12:00:00Z",
        "latency": 2.5,
        "metadata": {
            "model": "private-model",
            "tool_call_count": 2,
            "total_tool_errors": 1,
            "turn_count": 3,
        },
        "scores": ["private-score-id"],
    }


def _private_observations():
    return [
        {
            "id": "private-generation",
            "type": "GENERATION",
            "name": "llm-generation",
            "model": "private-model",
            "latency": 1.25,
            "calculatedTotalCost": 0.03,
            "usageDetails": {"input": 100, "cacheRead": 80, "output": 20},
            "input": {
                "instructions": "private system prompt",
                "tools": [{"name": "private-tool"}],
                "input": "private user content",
            },
        },
        {
            "id": "private-tool-observation",
            "type": "TOOL",
            "name": "private-tool",
            "level": "ERROR",
            "output": "private failure at /secret/path",
            "metadata": {"isError": True, "inputBytes": 25, "outputBytes": 40},
        },
    ]


def _child_projection(
    mode: str,
    child_id: str | None,
    *,
    outcome: str = "succeeded",
    declared: str | None = None,
):
    expected = (
        "expected-unavailable" if mode == "one-shot"
        else "expected-available" if mode == "agentic" and child_id
        else "unknown"
    )
    return {
        "type": "AGENT",
        "name": "subagent-result",
        "metadata": {
            **({"childSessionId": child_id} if child_id else {}),
            "effectiveMode": mode,
            "childTraceAvailability": declared or expected,
            "executionOutcome": outcome,
        },
    }


def _cohort_session(
    *,
    providers=(),
    models=(),
    outcome="unknown",
    evaluator_outcomes=(),
    evaluator_timeouts=0,
    taxonomy=None,
    capture_gaps=(),
):
    return {
        "features": {
            "providers": list(providers),
            "models": list(models),
            "finalOutcome": outcome,
            "evaluatorOutcomes": list(evaluator_outcomes),
            "evaluatorTimeouts": evaluator_timeouts,
            "errorTaxonomy": taxonomy or improvement._error_taxonomy([]),
            "captureGaps": list(capture_gaps),
        },
    }


def test_features_collect_normalized_provider_and_observation_model_dimensions():
    traces = [{"metadata": {"provider": "vendor-provider", "model": "vendor-model"}}]
    observations = [
        {
            "type": "GENERATION",
            "provider": "generation-provider",
            "model": "generation-model",
            "metadata": {},
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "metadata": {"provider": "openai-codex", "model": "gpt-5.6-terra"},
        },
        {
            "type": "AGENT",
            "metadata": {"provider": "https://private.example", "model": "/secret/model"},
        },
        {
            "type": "AGENT",
            "metadata": {"provider": "C:/private/provider", "model": "/private/model"},
        },
    ]

    features = improvement._features(traces, observations, [])

    assert features["providers"] == ["generation-provider", "openai-codex", "vendor-provider"]
    assert features["models"] == ["generation-model", "gpt-5.6-terra", "vendor-model"]
    assert "missing-provider" not in features["captureGaps"]
    assert "missing-model" not in features["captureGaps"]
    assert "invalid-provider" in features["captureGaps"]
    assert "invalid-model" in features["captureGaps"]
    assert "missing-provider" in improvement._features([], [], [])["captureGaps"]


def test_cohort_dimension_allowlist_uses_tracked_models_and_rejects_credentials(tmp_path):
    settings = tmp_path / "pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({
        "enabledModels": [
            "openai-codex/gpt-5.6-terra",
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890/model",
            "openrouter/github_pat_abcdefghijklmnopqrstuvwxyz",
        ],
    }), encoding="utf-8")

    providers, models = improvement._cohort_dimension_allowlists(tmp_path)

    assert providers == {"openai-codex"}
    assert models == {"gpt-5.6-terra", "openai-codex/gpt-5.6-terra"}


def test_cohort_billing_classes_use_only_enabled_unambiguous_catalog_targets(tmp_path):
    agent_dir = tmp_path / "pi" / "agent"
    agent_dir.mkdir(parents=True)
    agent_dir.joinpath("settings.json").write_text(json.dumps({
        "enabledModels": [
            "openai-codex/gpt-5.6-terra",
            "openrouter/minimax/minimax-m3",
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890/private-model",
        ],
    }), encoding="utf-8")
    agent_dir.joinpath("catalog.json").write_text(json.dumps({
        "schemaVersion": 1,
        "families": {
            "terra": {"venues": [{
                "target": "openai-codex/gpt-5.6-terra",
                "billingClass": "subscription",
            }]},
            "m3": {"venues": [{
                "target": "openrouter/minimax/minimax-m3",
                "billingClass": "metered",
            }]},
            "disabled": {"venues": [{
                "target": "openrouter/disabled/model",
                "billingClass": "metered",
            }]},
            "ambiguous": {"venues": [{
                "target": "openrouter/minimax/minimax-m3",
                "billingClass": "subscription",
            }]},
        },
    }), encoding="utf-8")

    assert improvement._cohort_billing_classes(tmp_path) == {
        "openai-codex/gpt-5.6-terra": "subscription",
    }
    assert improvement._cohort_billing_classes(tmp_path / "missing") == {}

    invalid_catalog = {
        "families": {"terra": {"venues": [{
            "target": "openai-codex/gpt-5.6-terra",
            "billingClass": "subscription",
        }]}},
    }
    for schema_version in (None, 2):
        value = dict(invalid_catalog)
        if schema_version is not None:
            value["schemaVersion"] = schema_version
        agent_dir.joinpath("catalog.json").write_text(json.dumps(value), encoding="utf-8")
        assert improvement._cohort_billing_classes(tmp_path) == {}


def test_scan_separates_nominal_and_catalog_derived_marginal_cost(tmp_path):
    def generation(provider, model, calculated_cost, total_price=0):
        return {
            "type": "GENERATION",
            "name": "llm-generation",
            "model": model,
            "calculatedTotalCost": calculated_cost,
            "totalPrice": total_price,
            "usageDetails": {"input": 10, "output": 1},
            "metadata": {"provider": provider},
        }

    traces = [
        _private_trace("subscription-session", "subscription-trace"),
        _private_trace("metered-session", "metered-trace"),
        _private_trace("unknown-session", "unknown-trace"),
        _private_trace("mixed-session", "mixed-trace"),
        _private_trace("conflict-session", "conflict-trace"),
        _private_trace("missing-price-session", "missing-price-trace"),
        _private_trace("malformed-price-session", "malformed-price-trace"),
    ]
    client = FakeScanClient(traces, {
        "subscription-trace": [
            generation("openai-codex", "gpt-5.6-terra", 0.13),
            generation("openai-codex", "gpt-5.6-terra-subscription", 0),
        ],
        "metered-trace": [generation("openrouter", "minimax/minimax-m3", 0, total_price=0.02)],
        "unknown-trace": [generation("private-provider", "private-model", 0.04)],
        "mixed-trace": [
            generation("openai-codex", "gpt-5.6-terra", 0.1),
            generation("openrouter", "minimax/minimax-m3", 0.2),
        ],
        "conflict-trace": [{
            **generation("openai-codex", "gpt-5.6-terra", 0.05),
            "provider": "openai-codex",
            "metadata": {"provider": "openrouter", "model": "minimax/minimax-m3"},
        }],
        "missing-price-trace": [{
            "type": "GENERATION",
            "name": "llm-generation",
            "model": "minimax/minimax-m3",
            "calculatedTotalCost": 0,
            "totalPrice": 0,
            "usageDetails": {"input": 10, "output": 1},
            "metadata": {"provider": "openrouter"},
        }],
        "malformed-price-trace": [generation("openrouter", "minimax/minimax-m3", "private-cost")],
    })
    repository_root = tmp_path / "repo"
    agent_dir = repository_root / "pi" / "agent"
    agent_dir.mkdir(parents=True)
    agent_dir.joinpath("settings.json").write_text(json.dumps({
        "enabledModels": [
            "openai-codex/gpt-5.6-terra",
            "openrouter/minimax/minimax-m3",
        ],
    }), encoding="utf-8")
    agent_dir.joinpath("catalog.json").write_text(json.dumps({
        "schemaVersion": 1,
        "families": {
            "terra": {"venues": [{
                "target": "openai-codex/gpt-5.6-terra",
                "billingClass": "subscription",
            }]},
            "m3": {"venues": [{
                "target": "openrouter/minimax/minimax-m3",
                "billingClass": "metered",
            }]},
        },
    }), encoding="utf-8")

    summary, packet = _scan_sessions(
        client,
        tmp_path,
        limit=10,
        repository_root=repository_root,
    )

    features = {item["sessionId"]: item["features"] for item in packet["sessions"]}
    assert features["subscription-session"]["cost"] == pytest.approx(0.13)
    assert features["subscription-session"]["costAccounting"] == {
        "schemaVersion": 1,
        "nominalUsd": pytest.approx(0.13),
        "marginalUsd": 0,
        "observedGenerations": 2,
        "unknownGenerations": 0,
        "byBillingClass": {"subscription": 2, "metered": 0, "unknown": 0},
    }
    assert features["metered-session"]["costAccounting"]["marginalUsd"] == pytest.approx(0.02)
    assert features["unknown-session"]["costAccounting"]["marginalUsd"] is None
    assert features["unknown-session"]["costAccounting"]["unknownGenerations"] == 1
    assert features["mixed-session"]["costAccounting"] == {
        "schemaVersion": 1,
        "nominalUsd": pytest.approx(0.3),
        "marginalUsd": pytest.approx(0.2),
        "observedGenerations": 2,
        "unknownGenerations": 0,
        "byBillingClass": {"subscription": 1, "metered": 1, "unknown": 0},
    }
    for session_id in ("conflict-session", "missing-price-session", "malformed-price-session"):
        assert features[session_id]["costAccounting"]["marginalUsd"] is None
        assert features[session_id]["costAccounting"]["unknownGenerations"] == 1
    assert summary["cohortHealth"]["costs"] == {
        "schemaVersion": 1,
        "nominalUsd": pytest.approx(0.54),
        "marginalUsd": pytest.approx(0.22),
        "marginalLowerBound": True,
        "knownMarginalSessions": 3,
        "unknownMarginalSessions": 4,
        "nonzeroMarginalSessions": 2,
        "observedGenerations": 9,
        "byBillingClass": {"subscription": 3, "metered": 4, "unknown": 2},
    }
    assert packet["schemaVersion"] == 2
    assert summary["schemaVersion"] == 1
    assert sorted(client.observation_traces) == sorted([
        "subscription-trace",
        "metered-trace",
        "unknown-trace",
        "mixed-trace",
        "conflict-trace",
        "missing-price-trace",
        "malformed-price-trace",
    ])
    safe_costs = json.dumps(summary["cohortHealth"]["costs"])
    assert "subscription-session" not in safe_costs
    assert "gpt-5.6-terra" not in safe_costs
    assert "private-provider" not in safe_costs


def test_cohort_marginal_cost_inherits_scan_lower_bound():
    session = _cohort_session()
    session["features"].update({
        "cost": 0.1,
        "costAccounting": {
            "schemaVersion": 1,
            "nominalUsd": 0.1,
            "marginalUsd": 0.1,
            "observedGenerations": 1,
            "unknownGenerations": 0,
            "byBillingClass": {"subscription": 0, "metered": 1, "unknown": 0},
        },
    })

    health = improvement._cohort_health(
        [session],
        trace_discovery={
            "maxTraces": 1,
            "complete": False,
            "continuation": {"hasMore": True},
        },
        scan_limit=1,
        eligible_session_count=1,
        allowed_providers=set(),
        allowed_models=set(),
    )

    assert health["costs"]["knownMarginalSessions"] == 1
    assert health["costs"]["unknownMarginalSessions"] == 0
    assert health["costs"]["marginalLowerBound"] is True


def test_cohort_health_filters_unsafe_dimensions_without_changing_private_models():
    features = improvement._features([{"metadata": {"model": "legacy private model"}}], [], [])

    health = improvement._cohort_health(
        [{"features": features}],
        trace_discovery={"maxTraces": 1, "complete": True, "continuation": {"hasMore": False}},
        scan_limit=1,
        eligible_session_count=1,
        allowed_providers=set(),
        allowed_models=set(),
    )

    assert features["models"] == ["legacy private model"]
    assert health["modelOutcomes"] == []
    assert health["unknownModelSessions"] == 1
    assert "legacy private model" not in json.dumps(health)


def test_cohort_health_aggregates_memberships_unknowns_errors_and_limits():
    first_taxonomy = improvement._error_taxonomy([{
        "type": "AGENT",
        "name": "subagent-result",
        "level": "ERROR",
        "metadata": {
            "failureClass": "provider",
            "providerFailureClass": "quota",
            "outcomeBlocking": True,
        },
    }])
    second_taxonomy = improvement._error_taxonomy([{
        "type": "TOOL",
        "level": "ERROR",
        "metadata": {"errorClass": "recovered", "errorSource": "tool", "outcomeBlocking": False},
    }])
    sessions = [
        _cohort_session(
            providers=["openai-codex", "https://private.example"],
            models=["gpt-5.6-terra", "/secret/model"],
            outcome="success",
            evaluator_outcomes=[{"name": "outcome", "value": "success"}],
            taxonomy=first_taxonomy,
        ),
        _cohort_session(
            providers=["openai-codex"],
            models=["gpt-5.6-luna"],
            outcome="failure",
            evaluator_timeouts=1,
            taxonomy=second_taxonomy,
            capture_gaps=["missing-usage", "trace-limit"],
        ),
        _cohort_session(
            providers=["https://private.example", "ghp_abcdefghijklmnopqrstuvwxyz1234567890"],
            models=["/secret/model", "github_pat_abcdefghijklmnopqrstuvwxyz"],
            capture_gaps=["missing-provider", "missing-model", "observation-limit"],
        ),
    ]
    discovery = {
        "maxTraces": 9,
        "complete": False,
        "continuation": {"hasMore": True, "reason": "max-traces"},
    }

    health = improvement._cohort_health(
        sessions,
        trace_discovery=discovery,
        scan_limit=3,
        eligible_session_count=4,
        allowed_providers={"openai-codex"},
        allowed_models={"gpt-5.6-luna", "gpt-5.6-terra"},
    )

    assert health["schemaVersion"] == 1
    assert health["observedSessions"] == 3
    assert health["outcomes"] == {"success": 1, "partial": 0, "failure": 1, "unclear": 0, "unknown": 1}
    assert health["providerOutcomes"] == [{
        "provider": "openai-codex",
        "sessions": 2,
        "outcomes": {"success": 1, "partial": 0, "failure": 1, "unclear": 0, "unknown": 0},
    }]
    assert health["unknownProviderSessions"] == 2
    assert [item["model"] for item in health["modelOutcomes"]] == ["gpt-5.6-luna", "gpt-5.6-terra"]
    assert health["unknownModelSessions"] == 2
    assert health["evaluatorCoverage"] == {
        "sessionsWithOutcomes": 1,
        "sessionsWithoutOutcomes": 2,
        "outcomeRecords": 1,
        "sessionsWithTimeouts": 1,
        "timeouts": 1,
    }
    assert health["errors"]["byClass"]["provider"] == 1
    assert health["errors"]["byClass"]["recovered"] == 1
    assert health["errors"]["bySource"]["provider"] == 1
    assert health["errors"]["bySource"]["tool"] == 1
    assert health["errors"]["outcomeBlocking"] == {"true": 1, "false": 1, "unknown": 0}
    assert health["captureGaps"]["missing-usage"] == 1
    assert health["captureGaps"]["trace-limit"] == 1
    assert health["captureGaps"]["observation-limit"] == 1
    assert health["completeness"] == {
        "eligibleSessionsAvailable": 4,
        "traceDiscoveryComplete": False,
        "traceDiscoveryHasMore": True,
        "sessionLimitReached": True,
        "lowerBound": True,
    }
    assert health["limits"] == {
        "scanSessions": 3,
        "discoveryTraces": 9,
        "discoveryPageSize": 100,
        "tracesPerSession": 20,
        "observationsPerTrace": 500,
        "scoresPerQuery": 100,
    }
    assert "private.example" not in json.dumps(health)
    assert "/secret" not in json.dumps(health)
    assert "ghp_" not in json.dumps(health)
    assert "github_pat_" not in json.dumps(health)


def test_scan_emits_identical_cohort_health_without_extra_api_calls(tmp_path):
    first = _private_trace("session-one", "trace-one")
    first["timestamp"] = "2026-07-26T13:00:00Z"
    first["metadata"]["provider"] = "openai-codex"
    second = _private_trace("session-two", "trace-two")
    client = FakeScanClient(
        [first, second],
        {
            "trace-one": [
                *_private_observations(),
                {
                    "type": "AGENT",
                    "name": "interactive-result",
                    "metadata": {"provider": "openai-codex", "model": "gpt-5.6-terra", "executionOutcome": "succeeded"},
                },
            ],
            "trace-two": [],
        },
        trace_scores={
            "trace-one": [{"name": "Apparent task outcome", "value": "success", "source": "EVAL"}],
        },
    )
    repository_root = tmp_path / "repo"
    settings = repository_root / "pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"enabledModels": ["openai-codex/gpt-5.6-terra"]}), encoding="utf-8")

    summary, packet = _scan_sessions(
        client,
        tmp_path,
        max_traces=7,
        repository_root=repository_root,
    )

    assert summary["schemaVersion"] == 1
    assert packet["schemaVersion"] == 2
    assert packet["scan"]["cohortHealth"] == summary["cohortHealth"]
    assert summary["cohortHealth"]["observedSessions"] == 1
    assert summary["cohortHealth"]["completeness"]["sessionLimitReached"] is True
    assert summary["cohortHealth"]["limits"]["discoveryTraces"] == 7
    assert summary["cohortHealth"]["providerOutcomes"][0]["provider"] == "openai-codex"
    assert "session-one" not in json.dumps(summary)
    assert "trace-one" not in json.dumps(summary)
    assert client.observation_traces == ["trace-one"]


def test_scan_excludes_exact_agentic_child_sessions_before_root_limit(tmp_path):
    child_root = _private_trace("agentic-child", "agentic-child-root")
    child_root.update({"name": "pi-agent"})
    child_root["metadata"]["completed"] = True
    parent_projection = _private_trace("parent-session", "parent-projection")
    parent_projection.update({"name": "subagent-result"})
    client = FakeScanClient(
        [child_root, parent_projection],
        {
            "agentic-child-root": [],
            "parent-projection": [_child_projection("agentic", "agentic-child")],
        },
    )

    summary, packet = _scan_sessions(client, tmp_path, limit=1)

    assert [session["sessionId"] for session in packet["sessions"]] == ["parent-session"]
    assert summary["candidateSessions"] == 1
    assert summary["traceDiscovery"]["childSessionsExcluded"] == 1
    assert "agentic-child" not in client.score_sessions
    assert client.observation_traces == ["parent-projection"]
    assert "agentic-child" not in json.dumps(summary)


def test_scan_keeps_malformed_child_declarations_as_unclassified_roots(tmp_path):
    projection = _private_trace("parent-session", "parent-projection")
    projection.update({"name": "subagent-result"})
    malformed = _child_projection("agentic", None)
    malformed["metadata"]["childTraceAvailability"] = "expected-available"
    client = FakeScanClient([projection], {"parent-projection": [malformed]})

    summary, packet = _scan_sessions(client, tmp_path)

    assert [session["sessionId"] for session in packet["sessions"]] == ["parent-session"]
    assert summary["traceDiscovery"]["childSessionsExcluded"] == 0
    assert summary["traceDiscovery"]["sessionClassificationComplete"] is False
    assert summary["cohortHealth"]["completeness"]["lowerBound"] is True


def test_scan_classifies_child_traces_from_bounded_discovery_without_extra_api_calls(tmp_path):
    parent_root = _private_trace("parent-session", "parent-root")
    parent_root.update({"name": "pi-agent"})
    parent_root["metadata"]["completed"] = True
    agentic_projection = _private_trace("parent-session", "agentic-projection")
    agentic_projection.update({"name": "subagent-result"})
    one_shot_projection = _private_trace("parent-session", "one-shot-projection")
    one_shot_projection.update({"name": "subagent-result"})
    child_root = _private_trace("agentic-child", "agentic-child-root")
    child_root.update({"name": "pi-agent"})
    child_root["metadata"]["completed"] = True
    client = FakeScanClient(
        [parent_root, agentic_projection, one_shot_projection, child_root],
        {
            "parent-root": _private_observations(),
            "agentic-projection": [_child_projection("agentic", "agentic-child")],
            "one-shot-projection": [_child_projection(
                "one-shot",
                "019f9e82-cc80-7000-8000-000000000000",
            )],
            "agentic-child-root": [],
        },
    )

    summary, packet = _scan_sessions(
        client,
        tmp_path,
        limit=10,
    )

    parent = next(item for item in packet["sessions"] if item["sessionId"] == "parent-session")
    assert parent["features"]["childTraceHealth"] == {
        "schemaVersion": 1,
        "projections": 2,
        "byMode": {"agentic": 1, "one-shot": 1, "unknown": 0},
        "byAvailability": {
            "available": 1,
            "expected-unavailable": 1,
            "missing": 0,
            "ambiguous": 0,
            "incomplete": 0,
            "unknown": 0,
        },
        "declarationMismatches": 0,
    }
    assert summary["cohortHealth"]["childTraces"] == parent["features"]["childTraceHealth"]
    assert client.observation_traces == [
        "agentic-projection",
        "one-shot-projection",
        "parent-root",
    ]
    assert [session["sessionId"] for session in packet["sessions"]] == ["parent-session"]
    assert summary["traceDiscovery"]["childSessionsExcluded"] == 1
    assert "parent-session" not in json.dumps(summary)
    assert "agentic-child" not in json.dumps(summary)
    assert "019f9e82-cc80-7000-8000-000000000000" not in json.dumps(summary)


@pytest.mark.parametrize(("projection", "roots", "complete", "expected", "mismatches"), [
    (_child_projection("agentic", "missing-child"), {}, True, "missing", 0),
    (
        _child_projection("agentic", "duplicate-child"),
        {"duplicate-child": [{"metadata": {"completed": True}}, {"metadata": {"completed": True}}]},
        True,
        "ambiguous",
        0,
    ),
    (
        _child_projection("agentic", "active-child"),
        {"active-child": [{"metadata": {"completed": False}}]},
        True,
        "incomplete",
        0,
    ),
    (
        _child_projection("agentic", "cancelled-child", outcome="failed"),
        {"cancelled-child": [{"metadata": {"completed": False, "cancelled": True}}]},
        True,
        "available",
        0,
    ),
    (
        _child_projection("agentic", "malformed-root-child"),
        {"malformed-root-child": [{"metadata": "private malformed metadata"}]},
        True,
        "incomplete",
        0,
    ),
    (_child_projection("agentic", "bounded-child"), {}, False, "unknown", 0),
    (_child_projection("agentic", "failed-child", outcome="failed"), {}, True, "unknown", 0),
    (
        _child_projection("one-shot", "instrumented-one-shot"),
        {"instrumented-one-shot": [{"metadata": {"completed": True}}]},
        True,
        "available",
        0,
    ),
    (_child_projection("one-shot", None), {}, True, "unknown", 0),
    (
        _child_projection("one-shot", "mismatch-child", declared="expected-available"),
        {},
        True,
        "unknown",
        1,
    ),
    (_child_projection("future-mode", "unknown-mode-child"), {}, True, "unknown", 0),
])
def test_child_trace_health_classifies_bounded_join_states(projection, roots, complete, expected, mismatches):
    health = improvement._child_trace_health([projection], roots, discovery_complete=complete)

    assert health["projections"] == 1
    assert health["byAvailability"][expected] == 1
    assert sum(health["byAvailability"].values()) == 1
    assert health["declarationMismatches"] == mismatches
    assert "childSessionId" not in json.dumps(health)


def test_child_trace_health_projects_join_failures_into_count_only_capture_gaps():
    observations = [
        _child_projection("agentic", "private-missing-id"),
        _child_projection("agentic", "duplicate-child"),
        _child_projection("agentic", "active-child"),
        _child_projection("one-shot", "mismatch-child", declared="expected-available"),
    ]
    roots = {
        "duplicate-child": [{"metadata": {"completed": True}}, {"metadata": {"completed": True}}],
        "active-child": [{"metadata": {"completed": False}}],
    }

    features = improvement._features(
        [],
        observations,
        [],
        child_trace_roots=roots,
        trace_discovery_complete=True,
    )
    health = improvement._cohort_health(
        [{"features": features}],
        trace_discovery={"maxTraces": 500, "complete": True, "continuation": {"hasMore": False}},
        scan_limit=1,
        eligible_session_count=1,
        allowed_providers=set(),
        allowed_models=set(),
    )

    expected = {
        "missing-child-trace",
        "ambiguous-child-trace",
        "incomplete-child-trace",
        "unknown-child-trace",
        "invalid-child-trace-declaration",
    }
    assert expected <= set(features["captureGaps"])
    assert all(health["captureGaps"][gap] == 1 for gap in expected)
    assert health["childTraces"] == features["childTraceHealth"]
    assert "private-missing-id" not in json.dumps(health)
    assert "mismatch-child" not in json.dumps(health)


@pytest.mark.parametrize(("mode", "child_id"), [
    ("agentic", "019f9b81-c180-7000-8000-000000000000"),
    ("agentic", "019fa605-6800-7000-8000-000000000000"),
    ("one-shot", "not-a-logical-pi-session"),
])
def test_scan_keeps_out_of_window_or_malformed_child_absence_unknown(tmp_path, mode, child_id):
    projection = _private_trace("parent-session", "child-projection")
    projection.update({"name": "subagent-result"})
    client = FakeScanClient(
        [projection],
        {"child-projection": [_child_projection(mode, child_id)]},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    health = packet["sessions"][0]["features"]["childTraceHealth"]
    assert health["byAvailability"]["unknown"] == 1
    assert health["byAvailability"]["missing"] == 0
    assert summary["cohortHealth"]["captureGaps"]["unknown-child-trace"] == 1
    assert summary["cohortHealth"]["captureGaps"]["missing-child-trace"] == 0
    assert child_id not in json.dumps(summary)


def test_scan_marks_score_capture_limit_as_lower_bound(tmp_path):
    trace = _private_trace("score-limited-session", "score-limited-trace")
    scores = [
        {"name": f"quality-{index}", "value": 1, "source": "EVAL"}
        for index in range(improvement.SCORES_PER_QUERY + 1)
    ]
    client = FakeScanClient(
        [trace],
        {"score-limited-trace": _private_observations()},
        trace_scores={"score-limited-trace": scores},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    features = packet["sessions"][0]["features"]
    assert len(features["evaluatorOutcomes"]) == improvement.SCORES_PER_QUERY
    assert "score-limit" in features["captureGaps"]
    assert summary["cohortHealth"]["captureGaps"]["score-limit"] == 1
    assert summary["cohortHealth"]["completeness"]["lowerBound"] is True
    assert set(client.score_limits) == {improvement.SCORES_PER_QUERY + 1}


def test_cohort_health_handles_zero_sessions():
    health = improvement._cohort_health(
        [],
        trace_discovery={"maxTraces": 500, "complete": True, "continuation": {"hasMore": False}},
        scan_limit=5,
        eligible_session_count=0,
        allowed_providers=set(),
        allowed_models=set(),
    )

    assert health["observedSessions"] == 0
    assert health["unknownProviderSessions"] == 0
    assert health["unknownModelSessions"] == 0
    assert health["evaluatorCoverage"]["sessionsWithoutOutcomes"] == 0
    assert health["completeness"]["lowerBound"] is False


def _tool_observation(*, input_marker=..., output_marker=..., metadata=None):
    observation = {
        "id": "private-tool-observation",
        "type": "TOOL",
        "name": "private-tool",
        "metadata": metadata if metadata is not None else {},
    }
    if input_marker is not ...:
        observation["input"] = input_marker
    if output_marker is not ...:
        observation["output"] = output_marker
    return observation


@pytest.mark.parametrize(
    ("observations", "expected_bytes", "status", "matched", "gap"),
    [
        ([], {"toolInput": 0, "toolOutput": 0}, "not-observed", 0, None),
        (
            [_tool_observation(input_marker=None, output_marker=None, metadata={"inputBytes": 26, "outputBytes": 26})],
            {"toolInput": None, "toolOutput": None},
            "inferred-unavailable",
            1,
            "inferred-tool-payload-bytes",
        ),
        (
            [
                _tool_observation(metadata={"inputBytes": 5, "outputBytes": 7}),
                _tool_observation(metadata={"outputBytes": 11}),
            ],
            {"toolInput": None, "toolOutput": 18},
            "unavailable",
            0,
            "missing-tool-payload-bytes",
        ),
        (
            [_tool_observation(metadata={"inputBytes": 5, "outputBytes": False})],
            {"toolInput": 5, "toolOutput": None},
            "unavailable",
            0,
            "missing-tool-payload-bytes",
        ),
        (
            [_tool_observation(input_marker=None, metadata={"inputBytes": 26, "outputBytes": 26})],
            {"toolInput": 26, "toolOutput": 26},
            "available",
            0,
            None,
        ),
        (
            [_tool_observation(input_marker=None, output_marker=None, metadata={"inputBytes": 26.0, "outputBytes": 26})],
            {"toolInput": None, "toolOutput": 26},
            "unavailable",
            0,
            "missing-tool-payload-bytes",
        ),
        (
            [
                _tool_observation(metadata={"inputBytes": 5, "outputBytes": 7}),
                _tool_observation(input_marker=None, output_marker=None, metadata={"inputBytes": 26, "outputBytes": 26}),
            ],
            {"toolInput": None, "toolOutput": None},
            "inferred-unavailable",
            1,
            "inferred-tool-payload-bytes",
        ),
    ],
)
def test_tool_payload_byte_aggregation_is_availability_aware(observations, expected_bytes, status, matched, gap):
    features = improvement._features([], observations, [])

    assert {name: features["payloadBytes"][name] for name in expected_bytes} == expected_bytes
    assert features["payloadByteMetadata"]["toolIo"] == {
        "status": status,
        "rule": "pi-langfuse-1.5.7-dual-null-dual-26",
        "matchedObservations": matched,
        "examinedObservations": len(observations),
    }
    assert (gap in features["captureGaps"]) if gap else not {
        "inferred-tool-payload-bytes",
        "missing-tool-payload-bytes",
    }.intersection(features["captureGaps"])


def test_usage_validation_preserves_present_zero_and_nulls_only_missing_dimensions():
    present_zero = improvement._features([], [{
        "type": "GENERATION",
        "usageDetails": {"input": 0, "cacheRead": 0, "output": 0, "total": 0},
    }], [])
    missing_cache = improvement._features([], [{
        "type": "GENERATION",
        "usageDetails": {"input": 7, "output": 3, "total": 10},
        "usage": {"input": 70, "cacheRead": 60, "output": 30},
    }], [])

    assert present_zero["tokens"] == {"freshInput": 0, "cacheRead": 0, "output": 0}
    assert "missing-usage" not in present_zero["captureGaps"]
    assert missing_cache["tokens"] == {"freshInput": 7, "cacheRead": None, "output": 3}
    assert "missing-usage" in missing_cache["captureGaps"]


@pytest.mark.parametrize("invalid_primary", [None, []])
def test_usage_validation_falls_back_from_unusable_primary_shape(invalid_primary):
    features = improvement._features([], [{
        "type": "GENERATION",
        "usageDetails": invalid_primary,
        "usage": {"input": 7, "cacheRead": 2, "output": 3},
    }], [])

    assert features["tokens"] == {"freshInput": 7, "cacheRead": 2, "output": 3}
    assert "missing-usage" not in features["captureGaps"]


@pytest.mark.parametrize("invalid", [True, -1, float("nan"), "0"])
def test_usage_validation_rejects_invalid_required_values(invalid):
    features = improvement._features([], [{
        "type": "GENERATION",
        "usageDetails": {"input": invalid, "cacheRead": 0, "output": 0, "total": 0},
    }], [])

    assert features["tokens"] == {"freshInput": None, "cacheRead": 0, "output": 0}
    assert "missing-usage" in features["captureGaps"]


@pytest.mark.parametrize(
    ("execution", "apparent", "explicit", "expected_final", "expected_source"),
    [
        ("failed", "success", None, "failure", "execution"),
        ("unavailable", "success", None, "unclear", "execution"),
        ("succeeded", "partial", None, "partial", "apparent"),
        ("failed", "partial", None, "failure", "execution"),
        ("failed", "partial", "success", "success", "explicit"),
    ],
)
def test_objective_execution_outcome_precedes_only_apparent_evaluation(
    execution,
    apparent,
    explicit,
    expected_final,
    expected_source,
):
    observations = [{
        "type": "AGENT",
        "name": "interactive-result",
        "metadata": {"executionOutcome": execution},
    }]
    scores = [{
        "name": "Apparent task outcome",
        "value": apparent,
        "source": "EVAL",
    }]
    if explicit:
        scores.append({
            "name": improvement.OUTCOME_SCORE,
            "value": explicit,
            "source": "API",
        })

    features = improvement._features([], observations, scores)

    assert features["executionOutcome"] == execution
    assert features["apparentOutcome"] == apparent
    assert features["finalOutcome"] == expected_final
    assert features["finalOutcomeSource"] == expected_source


def test_latest_root_execution_wins_and_subagent_quality_stays_separate():
    observations = [
        {
            "type": "AGENT",
            "name": "interactive-result",
            "startTime": "2026-08-05T02:00:00Z",
            "metadata": {"executionOutcome": "succeeded"},
        },
        {
            "type": "AGENT",
            "name": "interactive-result",
            "startTime": "2026-08-05T01:00:00Z",
            "metadata": {"executionOutcome": "failed"},
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "startTime": "2026-08-05T03:00:00Z",
            "metadata": {"executionOutcome": "failed"},
        },
    ]
    scores = [{"name": "Apparent task outcome", "value": "success", "source": "EVAL"}]

    features = improvement._features([], observations, scores)

    assert features["executionOutcome"] == "succeeded"
    assert features["apparentOutcome"] == "success"
    assert features["finalOutcome"] == "success"
    assert features["finalOutcomeSource"] == "apparent"


def test_latest_root_without_execution_metadata_stays_unknown():
    observations = [
        {
            "type": "AGENT",
            "name": "interactive-result",
            "startTime": "2026-08-05T01:00:00Z",
            "metadata": {"executionOutcome": "succeeded"},
        },
        {
            "type": "AGENT",
            "name": "interactive-result",
            "startTime": "2026-08-05T02:00:00Z",
            "metadata": {},
        },
    ]

    features = improvement._features([], observations, [])

    assert features["executionOutcome"] == "unknown"
    assert features["finalOutcome"] == "unknown"
    assert features["finalOutcomeSource"] == "unknown"


def test_scan_normalizes_exact_tool_fingerprint_without_copying_payload(tmp_path):
    observations = [
        _tool_observation(input_marker=None, output_marker=None, metadata={"inputBytes": 26, "outputBytes": 26}),
        _tool_observation(
            input_marker="PRIVATE TOOL INPUT",
            output_marker="PRIVATE TOOL OUTPUT",
            metadata={"inputBytes": 18, "outputBytes": 19},
        ),
    ]
    client = FakeScanClient(
        [_private_trace("private-session", "private-trace")],
        {"private-trace": observations},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    assert summary["schemaVersion"] == 1
    assert packet["schemaVersion"] == 2
    assert packet["scan"]["reviewPolicyVersion"] == improvement.REVIEW_POLICY_VERSION
    features = packet["sessions"][0]["features"]
    assert features["payloadBytes"]["toolInput"] is None
    assert features["payloadBytes"]["toolOutput"] is None
    assert features["payloadByteMetadata"]["toolIo"] == {
        "status": "inferred-unavailable",
        "rule": "pi-langfuse-1.5.7-dual-null-dual-26",
        "matchedObservations": 1,
        "examinedObservations": 2,
    }
    assert "inferred-tool-payload-bytes" in features["captureGaps"]
    assert "PRIVATE TOOL INPUT" not in json.dumps(packet)
    assert "PRIVATE TOOL OUTPUT" not in json.dumps(packet)


def test_settlement_rejects_zero_length_window():
    with pytest.raises(ValueError, match="no settled time window"):
        improvement._settled_window(
            "2026-07-27T11:00:00Z",
            "2026-07-27T11:05:00Z",
            "2026-07-27T11:05:00Z",
        )


def test_settlement_lookahead_classifies_children_across_watermark(tmp_path):
    child_root = _private_trace("agentic-child", "child-root")
    child_root.update({"name": "pi-agent", "timestamp": "2026-07-27T11:56:00Z"})
    child_root["metadata"]["completed"] = True
    parent_projection = _private_trace("parent-session", "parent-projection")
    parent_projection.update({"name": "subagent-result", "timestamp": "2026-07-27T11:58:00Z"})

    class TimeFilteringClient(FakeScanClient):
        def list_traces_with_metadata(self, **kwargs):
            self.trace_bounds = kwargs
            traces = [trace for trace in self.traces if trace["timestamp"] <= kwargs["to_timestamp"]]
            return {
                "traces": traces,
                "totalAvailable": len(traces),
                "scanned": len(traces),
                "maxTraces": kwargs.get("max_traces"),
                "complete": True,
                "continuation": {"hasMore": False, "nextPage": None, "reason": "api-end"},
            }

    client = TimeFilteringClient(
        [child_root, parent_projection],
        {"child-root": [], "parent-projection": [_child_projection("agentic", "agentic-child")]},
    )

    summary, packet = _scan_sessions(
        client,
        tmp_path,
        since="2026-07-27T11:00:00Z",
        until="2026-07-27T12:00:00Z",
        observed_at="2026-07-27T12:02:00Z",
    )

    assert client.trace_bounds["to_timestamp"] == "2026-07-27T12:02:00Z"
    assert packet["sessions"] == []
    assert summary["traceDiscovery"]["childSessionsExcluded"] == 1
    assert client.score_sessions == []


def test_scan_settlement_watermark_excludes_active_data_and_is_replayable(tmp_path):
    active_trace = _private_trace("active-session", "active-trace")
    active_trace["timestamp"] = "2026-07-27T11:58:00Z"

    class TimeFilteringClient(FakeScanClient):
        def list_traces_with_metadata(self, **kwargs):
            self.trace_bounds = kwargs
            traces = [trace for trace in self.traces if trace["timestamp"] <= kwargs["to_timestamp"]]
            return {
                "traces": traces,
                "totalAvailable": len(traces),
                "scanned": len(traces),
                "maxTraces": kwargs.get("max_traces"),
                "complete": True,
                "continuation": {"hasMore": False, "nextPage": None, "reason": "api-end"},
            }

    first_client = TimeFilteringClient([active_trace], {"active-trace": []})
    first_summary, first_packet = _scan_sessions(
        first_client,
        tmp_path,
        since="2026-07-27T11:00:00Z",
        until="2026-07-27T12:00:00Z",
        observed_at="2026-07-27T12:02:00Z",
    )

    assert first_client.trace_bounds["to_timestamp"] == "2026-07-27T12:02:00Z"
    assert first_packet["scan"]["settlement"] == {
        "schemaVersion": 1,
        "requestedUntil": "2026-07-27T12:00:00Z",
        "watermark": "2026-07-27T11:57:00Z",
        "readUntil": "2026-07-27T12:02:00Z",
        "lagSeconds": 300,
        "activeWindowExcluded": True,
    }
    assert first_summary["settlement"] == {"lagSeconds": 300, "activeWindowExcluded": True}
    assert first_packet["sessions"] == []

    replay_client = TimeFilteringClient([active_trace], {"active-trace": []})
    replay_summary, replay_packet = _scan_sessions(
        replay_client,
        tmp_path,
        since="2026-07-27T11:00:00Z",
        until=first_packet["scan"]["until"],
        observed_at="2026-07-27T13:00:00Z",
    )

    assert replay_packet["reportId"] == first_packet["reportId"]
    assert replay_packet["sessions"] == first_packet["sessions"]
    assert replay_summary["cohortHealth"] == first_summary["cohortHealth"]


def test_settled_scan_selection_is_stable_when_api_trace_order_changes(tmp_path):
    traces = [
        _private_trace("2026-07-26T12-00-00-000Z_root-a", "trace-a"),
        _private_trace("2026-07-26T13-00-00-000Z_root-b", "trace-b"),
    ]
    observations = {"trace-a": [], "trace-b": []}

    first_summary, first_packet = _scan_sessions(FakeScanClient(traces, observations), tmp_path)
    second_summary, second_packet = _scan_sessions(FakeScanClient(list(reversed(traces)), observations), tmp_path)

    assert first_packet["reportId"] == second_packet["reportId"]
    assert first_packet["sessions"] == second_packet["sessions"]
    assert first_summary["cohortHealth"] == second_summary["cohortHealth"]


def test_scan_retains_private_projection_timing_and_lineage_across_projects(tmp_path):
    projection = _private_trace("parent-session", "parent-trace")
    projection.update({"name": "subagent-result"})
    observation = _child_projection("agentic", "child-session")
    observation.update({
        "id": "private-observation-id",
        "traceId": "parent-trace",
        "parentObservationId": "private-parent-observation-id",
        "startTime": "2026-07-26T12:00:01Z",
        "endTime": "2026-07-26T12:00:03Z",
        "latency": 2.0,
        "input": "PRIVATE INPUT",
        "output": "PRIVATE OUTPUT",
    })
    observation["metadata"].update({"invocationId": "private-invocation-id", "index": 2})
    client = FakeScanClient([projection], {"parent-trace": [observation]})

    summary, packet = _scan_sessions(
        client,
        tmp_path,
        repository_root=tmp_path / "different-project",
    )

    assert packet["sessions"][0]["features"]["projections"] == [{
        "observationId": "private-observation-id",
        "traceId": "parent-trace",
        "parentObservationId": "private-parent-observation-id",
        "invocationId": "private-invocation-id",
        "childSessionId": "child-session",
        "index": 2,
        "effectiveMode": "agentic",
        "childTraceAvailability": "expected-available",
        "startTime": "2026-07-26T12:00:01Z",
        "endTime": "2026-07-26T12:00:03Z",
        "latencySeconds": 2.0,
    }]
    serialized_summary = json.dumps(summary)
    for private in (
        "private-observation-id",
        "private-parent-observation-id",
        "private-invocation-id",
        "child-session",
        "parent-trace",
        "PRIVATE INPUT",
        "PRIVATE OUTPUT",
        str(tmp_path),
    ):
        assert private not in serialized_summary


def test_scan_writes_private_atomic_packet_with_restrictive_permissions(tmp_path):
    output_dir = tmp_path / "private-runtime"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_dir = tmp_path / "runs"
    bundle = runs_dir / "private-run"
    bundle.mkdir(parents=True)
    (bundle / "invocation.yaml").write_text(
        json.dumps({
            "id": "private-run",
            "bead": "pi-safe.1",
            "createdAt": "2026-07-26T12:00:00Z",
            "routingTask": "review",
            "effectiveRole": "quality-reviewer",
            "dispatchPolicy": {"risk": "medium"},
        }),
        encoding="utf-8",
    )
    client = FakeScanClient(
        [_private_trace()],
        {"private-trace": _private_observations()},
        trace_scores={
            "private-trace": [
                {
                    "name": "Apparent task outcome",
                    "value": "success",
                    "source": "EVAL",
                    "subject": {"kind": "trace", "id": "private-trace"},
                },
                {
                    "name": "tool_call_count",
                    "value": 2,
                    "source": "API",
                    "subject": {"kind": "trace", "id": "private-trace"},
                },
            ],
        },
    )

    summary, packet = _scan_sessions(
        client,
        tmp_path,
        output_dir=output_dir,
        runs_dir=runs_dir,
        repository_root=repo_root,
        dry_run=False,
    )

    assert summary["status"] == "ok"
    assert summary["eligibleSessions"] == 1
    assert summary["reportWritten"] is True
    assert summary["reportPath"] is None
    assert "private-trace" not in json.dumps(summary)
    assert "run-private-run" not in json.dumps(summary)
    assert str(output_dir) not in json.dumps(summary)
    report_path, = output_dir.glob("scan-*.json")
    assert report_path.parent == output_dir
    assert stat.S_IMODE(output_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
    assert list(output_dir.glob(".*.tmp")) == []
    assert json.loads(report_path.read_text(encoding="utf-8")) == packet

    session = packet["sessions"][0]
    assert session["sessionId"] == "run-private-run"
    assert session["traceIds"] == ["private-trace"]
    assert session["correlation"]["status"] == "linked"
    assert session["correlation"]["runId"] == "private-run"
    assert session["correlation"]["beadId"] == "pi-safe.1"
    assert session["correlation"]["startedAt"] == "2026-07-26T12:00:00Z"
    assert session["correlation"]["routingTask"] == "review"
    assert session["correlation"]["role"] == "quality-reviewer"
    assert session["correlation"]["risk"] == "medium"
    assert session["features"]["tokens"] == {"freshInput": 100, "cacheRead": 80, "output": 20}
    assert session["features"]["toolCalls"] == 2
    assert session["features"]["toolErrors"] == 1
    assert session["features"]["turns"] == 3
    assert session["features"]["payloadBytes"]["toolInput"] == 25
    assert session["features"]["payloadBytes"]["toolOutput"] == 40
    assert len(session["features"]["promptHash"]) == 64
    assert session["features"]["finalOutcome"] == "success"
    assert session["features"]["evaluatorOutcomes"] == [{
        "name": "Apparent task outcome",
        "value": "success",
        "source": "EVAL",
    }]
    assert session["features"]["errorSignatures"][0]["count"] == 1


def test_scan_joins_projected_outcomes_and_payload_free_error_signals(tmp_path):
    session_id = "interactive-session"
    root = _private_trace(session_id, "root-trace")
    projection = _private_trace(session_id, "projection-trace")
    projection["metadata"] = {}
    signals = [{
        "toolName": "bash",
        "inputHash": "a" * 64,
        "count": 1,
        "exitCode": 1,
        "cancelled": False,
        "timedOut": False,
        "classification": "recovered",
    }]
    client = FakeScanClient(
        [root, projection],
        {
            "root-trace": _private_observations(),
            "projection-trace": [{
                "id": "projection-observation",
                "type": "AGENT",
                "name": "interactive-result",
                "metadata": {"toolErrorSignals": signals},
            }],
        },
        trace_scores={
            "projection-trace": [{
                "name": "Apparent task outcome",
                "value": "success",
                "source": "EVAL",
                "subject": {"kind": "trace", "id": "projection-trace"},
            }],
        },
    )

    _, packet = _scan_sessions(client, tmp_path)

    features = packet["sessions"][0]["features"]
    assert features["finalOutcome"] == "success"
    assert features["toolErrorSignals"] == signals
    assert "missing-outcome" not in features["captureGaps"]


def test_error_taxonomy_is_payload_free_and_keeps_unknown_visible():
    tool_signals = [
        {
            "toolName": "read",
            "inputHash": "a" * 64,
            "count": 3,
            "cancelled": False,
            "timedOut": False,
            "classification": "recovered",
        },
        {
            "toolName": "bash",
            "inputHash": "b" * 64,
            "count": 2,
            "cancelled": False,
            "timedOut": True,
            "classification": "infrastructure",
        },
    ]
    observations = [
        {
            "type": "TOOL",
            "name": "expected-negative-test",
            "level": "ERROR",
            "output": "SECRET expected payload",
            "metadata": {
                "errorClass": "expected",
                "errorSource": "tool",
                "outcomeBlocking": False,
            },
        },
        {
            "type": "AGENT",
            "name": "interactive-result",
            "metadata": {"executionOutcome": "succeeded", "toolErrorSignals": tool_signals},
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "level": "ERROR",
            "metadata": {
                "executionOutcome": "failed",
                "failureClass": "provider",
                "providerFailureClass": "credit",
                "exitCode": 1,
            },
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "metadata": {
                "executionOutcome": "succeeded",
                "artifactStatus": "failed",
                "artifactFailureClass": "write",
                "exitCode": 0,
            },
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "level": "ERROR",
            "metadata": {"executionOutcome": "failed", "exitCode": 2},
        },
        {"type": "SPAN", "name": "subagent-quality evaluator", "level": "ERROR", "metadata": {}},
        {"type": "SPAN", "name": "unclassified", "level": "ERROR", "output": "SECRET unknown payload"},
        {
            "type": "AGENT",
            "name": "interactive-result",
            "level": "ERROR",
            "metadata": {
                "executionOutcome": "failed",
                "failureClass": "provider",
                "providerFailureClass": "availability",
            },
        },
    ]

    taxonomy = improvement._features([], observations, [])["errorTaxonomy"]

    assert taxonomy == {
        "schemaVersion": 1,
        "rawErrorObservationCount": 6,
        "unclassifiedRawErrorObservationCount": 0,
        "classifiedSignals": 12,
        "actionableSignals": 7,
        "nonActionableSignals": 4,
        "unknownSignals": 1,
        "byClass": {
            "expected": 1,
            "recovered": 3,
            "provider": 2,
            "infrastructure": 4,
            "agent": 1,
            "unknown": 1,
        },
        "bySource": {
            "tool": 6,
            "provider": 2,
            "process": 1,
            "artifact": 1,
            "evaluator": 1,
            "unknown": 1,
        },
        "outcomeBlocking": {"true": 1, "false": 1, "unknown": 10},
    }
    serialized = json.dumps(taxonomy)
    assert "SECRET" not in serialized
    assert "a" * 64 not in serialized
    assert "b" * 64 not in serialized


def test_error_taxonomy_precedence_prefers_explicit_then_provider_then_infrastructure():
    observations = [
        {
            "type": "AGENT",
            "name": "subagent-result",
            "level": "ERROR",
            "metadata": {
                "errorClass": "recovered",
                "errorSource": "tool",
                "providerFailureClass": "quota",
                "failureClass": "provider",
            },
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "level": "ERROR",
            "metadata": {
                "providerFailureClass": "quota",
                "artifactFailureClass": "write",
                "failureClass": "process",
            },
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "level": "ERROR",
            "metadata": {"artifactFailureClass": "write", "failureClass": "process"},
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "level": "ERROR",
            "metadata": {"failureClass": "process"},
        },
        {
            "type": "AGENT",
            "name": "subagent-result",
            "level": "ERROR",
            "metadata": {"failureClass": "timeout"},
        },
    ]

    taxonomy = improvement._features([], observations, [])["errorTaxonomy"]

    assert taxonomy["byClass"] == {
        "expected": 0,
        "recovered": 1,
        "provider": 1,
        "infrastructure": 2,
        "agent": 1,
        "unknown": 0,
    }
    assert taxonomy["actionableSignals"] == 4
    assert taxonomy["nonActionableSignals"] == 1


def test_error_taxonomy_retains_unclassified_raw_tool_errors_without_guessing():
    taxonomy = improvement._features([], [{
        "type": "TOOL",
        "name": "unclassified-tool",
        "level": "ERROR",
        "output": "SECRET raw tool output",
        "metadata": {"errorClass": "not-a-class", "artifactFailureClass": ""},
    }], [])["errorTaxonomy"]

    assert taxonomy["rawErrorObservationCount"] == 1
    assert taxonomy["unclassifiedRawErrorObservationCount"] == 1
    assert taxonomy["classifiedSignals"] == 0
    assert taxonomy["unknownSignals"] == 0
    assert "SECRET" not in json.dumps(taxonomy)


def test_scan_uses_explicit_private_work_item_link(tmp_path):
    class LinkedClient(FakeScanClient):
        def list_scores(self, **kwargs):
            if kwargs.get("name") == improvement.WORK_LINK_SCORE:
                return [{
                    "value": "linked",
                    "metadata": {"schemaVersion": 1, "beadId": "pi-work.1"},
                    "subject": {"kind": "session", "id": kwargs["session_id"]},
                }]
            return super().list_scores(**kwargs)

    client = LinkedClient(
        [_private_trace("interactive-session", "private-trace")],
        {"private-trace": _private_observations()},
    )

    _, packet = _scan_sessions(client, tmp_path)

    assert packet["sessions"][0]["correlation"] == {"status": "linked", "beadId": "pi-work.1"}


def test_scan_prefers_explicit_linked_outcome_over_sampled_evaluator(tmp_path):
    class OutcomeClient(FakeScanClient):
        def list_scores(self, **kwargs):
            if kwargs.get("name") == improvement.WORK_LINK_SCORE:
                return [{
                    "value": "linked",
                    "metadata": {"schemaVersion": 1, "beadId": "pi-work.1"},
                    "subject": {"kind": "session", "id": kwargs["session_id"]},
                }]
            if kwargs.get("name") == improvement.OUTCOME_SCORE:
                return [{
                    "name": improvement.OUTCOME_SCORE,
                    "value": "success",
                    "source": "API",
                    "metadata": {"schemaVersion": 1, "beadId": "pi-work.1"},
                    "subject": {"kind": "session", "id": kwargs["session_id"]},
                }]
            return super().list_scores(**kwargs)

    client = OutcomeClient(
        [_private_trace("interactive-session", "private-trace")],
        {"private-trace": _private_observations()},
        trace_scores={
            "private-trace": [{
                "name": "Apparent task outcome",
                "value": "failure",
                "source": "EVAL",
            }],
        },
    )

    _, packet = _scan_sessions(client, tmp_path)

    features = packet["sessions"][0]["features"]
    assert features["finalOutcome"] == "success"
    assert "missing-outcome" not in features["captureGaps"]


def test_scan_rejects_explicit_outcome_owned_by_different_work_item(tmp_path):
    class MismatchedOutcomeClient(FakeScanClient):
        def list_scores(self, **kwargs):
            if kwargs.get("name") == improvement.WORK_LINK_SCORE:
                return [{
                    "id": improvement._work_link_score_id(kwargs["session_id"]),
                    "name": improvement.WORK_LINK_SCORE,
                    "value": "linked",
                    "metadata": {"schemaVersion": 1, "beadId": "pi-second.1"},
                    "subject": {"kind": "session", "id": kwargs["session_id"]},
                }]
            if kwargs.get("name") == improvement.OUTCOME_SCORE:
                return [{
                    "id": improvement._outcome_score_id(kwargs["session_id"]),
                    "name": improvement.OUTCOME_SCORE,
                    "value": "success",
                    "source": "API",
                    "metadata": {"schemaVersion": 1, "beadId": "pi-first.1"},
                    "subject": {"kind": "session", "id": kwargs["session_id"]},
                }]
            return super().list_scores(**kwargs)

    client = MismatchedOutcomeClient(
        [_private_trace("interactive-session", "private-trace")],
        {"private-trace": _private_observations()},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    session = packet["sessions"][0]
    assert session["correlation"] == {"status": "linked", "beadId": "pi-second.1"}
    assert session["features"]["finalOutcome"] == "unknown"
    assert session["features"]["finalOutcomeSource"] == "unknown"
    assert "mismatched-work-item-outcome" in session["features"]["captureGaps"]
    assert summary["cohortHealth"]["captureGaps"]["mismatched-work-item-outcome"] == 1
    assert "pi-first.1" not in json.dumps(session["features"])


def test_scan_rejects_explicit_outcome_with_ambiguous_idless_links(tmp_path):
    class AmbiguousLinkClient(FakeScanClient):
        def list_scores(self, **kwargs):
            if kwargs.get("name") == improvement.WORK_LINK_SCORE:
                return [
                    {
                        "name": improvement.WORK_LINK_SCORE,
                        "value": "linked",
                        "metadata": {"schemaVersion": 1, "beadId": bead_id},
                        "subject": {"kind": "session", "id": kwargs["session_id"]},
                    }
                    for bead_id in ("pi-second.1", "pi-first.1")
                ]
            if kwargs.get("name") == improvement.OUTCOME_SCORE:
                return [{
                    "name": improvement.OUTCOME_SCORE,
                    "value": "success",
                    "source": "API",
                    "metadata": {"schemaVersion": 1, "beadId": "pi-second.1"},
                    "subject": {"kind": "session", "id": kwargs["session_id"]},
                }]
            return super().list_scores(**kwargs)

    client = AmbiguousLinkClient(
        [_private_trace("interactive-session", "private-trace")],
        {"private-trace": _private_observations()},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    session = packet["sessions"][0]
    assert session["correlation"] == {"status": "unlinked"}
    assert session["features"]["finalOutcome"] == "unknown"
    assert session["features"]["finalOutcomeSource"] == "unknown"
    assert "mismatched-work-item-outcome" in session["features"]["captureGaps"]
    assert summary["cohortHealth"]["captureGaps"]["mismatched-work-item-outcome"] == 1


def test_scan_dry_run_skips_reviewed_sessions_without_writing(tmp_path):
    reviewed = _private_trace("reviewed-session", "reviewed-trace")
    eligible = _private_trace("eligible-session", "eligible-trace")
    client = FakeScanClient(
        [reviewed, eligible],
        {"eligible-trace": _private_observations()},
        reviewed={"reviewed-session"},
    )
    output_dir = tmp_path / "must-not-exist"

    summary, packet = _scan_sessions(
        client,
        tmp_path,
        output_dir=output_dir,
    )

    expected_summary = {
        "schemaVersion": 1,
        "status": "ok",
        "scannedTraces": 2,
        "traceDiscovery": {
            "totalAvailable": 2,
            "scanned": 2,
            "maxTraces": 500,
            "attributable": 2,
            "unattributed": 0,
            "rootSessions": 2,
            "childSessionsExcluded": 0,
            "unclassifiedProjectionTraces": 0,
            "sessionClassificationComplete": True,
            "complete": True,
            "continuation": {"hasMore": False, "nextPage": None, "reason": "api-end"},
        },
        "candidateSessions": 2,
        "eligibleSessions": 1,
        "reviewedSessionsSkipped": 1,
        "unlinkedSessions": 1,
        "reportWritten": False,
        "reportPath": None,
    }
    assert {key: summary[key] for key in expected_summary} == expected_summary
    assert summary["cohortHealth"] == packet["scan"]["cohortHealth"]
    assert [item["sessionId"] for item in packet["sessions"]] == ["eligible-session"]
    assert client.observation_traces == ["eligible-trace"]
    assert not output_dir.exists()


def test_scan_rechecks_stale_review_policy_markers(tmp_path):
    client = FakeScanClient(
        [_private_trace("stale-session", "stale-trace")],
        {"stale-trace": []},
        reviewed={"stale-session": "older-policy"},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    assert summary["eligibleSessions"] == 1
    assert summary["reviewedSessionsSkipped"] == 0
    assert packet["sessions"][0]["sessionId"] == "stale-session"


@pytest.mark.parametrize(("session_id", "since", "until", "expected"), [
    (
        "2026-07-26T12-00-00-000Z_private-session",
        "2026-07-27T00:00:00Z",
        "2026-07-28T00:00:00Z",
        "2026-07-26T12:00:00Z",
    ),
    (
        "018cc251-f400-7000-8000-000000000000",
        "2024-01-02T00:00:00Z",
        "2024-01-03T00:00:00Z",
        "2024-01-01T00:00:00Z",
    ),
])
def test_scan_score_markers_are_bounded_from_session_start(tmp_path, session_id, since, until, expected):
    class QueryClient(FakeScanClient):
        def __init__(self, traces, observations):
            super().__init__(traces, observations)
            self.score_queries = []

        def list_scores(self, **kwargs):
            self.score_queries.append(kwargs)
            return super().list_scores(**kwargs)

    trace = _private_trace(session_id, "private-trace")
    trace["timestamp"] = since
    client = QueryClient(
        [trace],
        {"private-trace": _private_observations()},
    )

    _scan_sessions(
        client,
        tmp_path,
        since=since,
        until=until,
    )

    session_queries = [query for query in client.score_queries if query.get("session_id") == session_id]
    assert len(session_queries) == 3
    assert {query["from_timestamp"] for query in session_queries} == {expected}


@pytest.mark.parametrize(("session_id", "fallback", "expected"), [
    ("018cc251-f400-7000-8000-000000000000", "2023-12-31T00:00:00Z", "2023-12-31T00:00:00Z"),
    ("018cc251-f5f4-7000-8000-000000000000", "2024-01-01T00:00:00.250000Z", "2024-01-01T00:00:00.250000Z"),
    ("550e8400-e29b-41d4-a716-446655440000", "2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z"),
    ("ffffffff-ffff-7fff-bfff-ffffffffffff", "2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z"),
    ("not-a-session", "2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z"),
])
def test_session_score_since_validates_uuidv7_and_uses_safe_fallback(session_id, fallback, expected):
    assert improvement._session_score_since(session_id, fallback) == expected


def test_scan_checks_multiple_review_markers_for_current_policy(tmp_path):
    class MixedMarkerClient(FakeScanClient):
        def list_scores(self, **kwargs):
            if kwargs.get("trace_id"):
                return []
            self.marker_limit = kwargs["limit"]
            return [
                {"value": "no-action", "metadata": {"reviewPolicyVersion": "older-policy"}},
                {"value": "no-action", "metadata": {"reviewPolicyVersion": improvement.REVIEW_POLICY_VERSION}},
            ][: kwargs["limit"]]

    client = MixedMarkerClient([_private_trace("reviewed-session", "reviewed-trace")], {})

    summary, packet = _scan_sessions(client, tmp_path)

    assert client.marker_limit == improvement.SCORES_PER_QUERY + 1
    assert summary["reviewedSessionsSkipped"] == 1
    assert packet["sessions"] == []


def test_scan_trace_discovery_paginates_past_reviewed_prefix(tmp_path):
    traces = [_private_trace(f"reviewed-{index}", f"trace-{index}") for index in range(10)]
    traces.append(_private_trace("eligible-session", "eligible-trace"))
    client = FakeScanClient(
        traces,
        {"eligible-trace": []},
        reviewed={f"reviewed-{index}" for index in range(10)},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    assert client.trace_limits == []
    assert summary["eligibleSessions"] == 1
    assert packet["sessions"][0]["sessionId"] == "eligible-session"


def test_trace_discovery_reports_lower_bounds_and_unattributed_traces(tmp_path):
    attributed = _private_trace("eligible-session", "attributed-trace")
    unattributed = _private_trace("", "unattributed-trace")

    class IncompleteScanClient(FakeScanClient):
        def list_traces_with_metadata(self, **kwargs):
            return {
                "traces": self.traces,
                "totalAvailable": 3,
                "scanned": 2,
                "complete": False,
                "continuation": {"hasMore": True, "nextPage": 3, "reason": "api-incomplete"},
            }

    client = IncompleteScanClient(
        [attributed, unattributed],
        {"attributed-trace": []},
    )

    summary, packet = _scan_sessions(client, tmp_path)

    expected = {
        "totalAvailable": 3,
        "scanned": 2,
        "maxTraces": 500,
        "attributable": 1,
        "unattributed": 1,
        "rootSessions": 1,
        "childSessionsExcluded": 0,
        "unclassifiedProjectionTraces": 0,
        "sessionClassificationComplete": False,
        "complete": False,
        "continuation": {"hasMore": True, "nextPage": 3, "reason": "api-incomplete"},
    }
    assert "traceDiscovery" in summary
    assert summary["traceDiscovery"] == expected
    assert packet["scan"]["traceDiscovery"] == expected


def test_scan_marks_truncated_observations_as_capture_gap(tmp_path):
    observations = [
        _tool_observation(input_marker=None, output_marker=None, metadata={"inputBytes": 26, "outputBytes": 26}),
        *[
            {"id": str(index), "type": "TOOL", "metadata": {"inputBytes": 1, "outputBytes": 2}}
            for index in range(500)
        ],
    ]
    client = FakeScanClient(
        [_private_trace("eligible-session", "eligible-trace")],
        {"eligible-trace": observations},
    )

    _, packet = _scan_sessions(client, tmp_path)

    features = packet["sessions"][0]["features"]
    assert "observation-limit" in features["captureGaps"]
    assert "inferred-tool-payload-bytes" in features["captureGaps"]
    assert features["payloadByteMetadata"]["toolIo"] == {
        "status": "inferred-unavailable",
        "rule": "pi-langfuse-1.5.7-dual-null-dual-26",
        "matchedObservations": 1,
        "examinedObservations": 500,
    }


def test_scan_never_correlates_parent_directory_session_ids(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (tmp_path / "invocation.yaml").write_text(json.dumps({"id": "..", "bead": "pi-unsafe"}), encoding="utf-8")
    client = FakeScanClient(
        [_private_trace("run-..", "private-trace")],
        {"private-trace": []},
    )

    _, packet = _scan_sessions(
        client,
        tmp_path,
        runs_dir=runs_dir,
    )

    assert packet["sessions"][0]["correlation"] == {"status": "unlinked"}


def test_scan_refuses_report_directory_inside_repository(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    client = FakeScanClient([], {})

    with pytest.raises(ValueError, match="outside repository"):
        _scan_sessions(
            client,
            tmp_path,
            output_dir=repo_root / ".pi" / "improvement",
            runs_dir=repo_root / ".pi" / "runs",
            repository_root=repo_root,
            dry_run=False,
        )


def _review_packet():
    return {
        "schemaVersion": 1,
        "reportId": "0123456789abcdef",
        "createdAt": "2026-07-27T00:00:00Z",
        "scan": {
            "since": "2026-07-26T00:00:00Z",
            "until": "2026-07-27T00:00:00Z",
            "limit": 1,
            "recheck": False,
            "reviewPolicyVersion": "v1",
        },
        "sessions": [{
            "sessionId": "private-session",
            "traceIds": ["private-trace"],
            "correlation": {"status": "unlinked"},
            "features": {
                "toolErrors": 2,
                "models": ["private-model"],
                "captureGaps": [],
            },
        }],
    }


def _review_decisions():
    return {
        "schemaVersion": 1,
        "reportId": "0123456789abcdef",
        "reviewPolicyVersion": "v1",
        "reviewedAt": "2026-07-27T01:00:00Z",
        "sessions": [{
            "sessionId": "private-session",
            "decision": "actions-created",
            "findings": [{
                "findingId": "finding-0123456789ab",
                "category": "coordination-error",
                "errorRelevance": "contributing",
                "impact": "medium",
                "attribution": "prompt-system",
                "confidence": 0.8,
                "evidenceRefs": ["/sessions/0/features/toolErrors"],
                "proposedIntervention": "prompt",
                "public": {
                    "title": "Improve coordination instruction targeting",
                    "affectedPaths": ["pi/agent/AGENTS.md"],
                    "aggregate": "Repeated coordination failures occurred across reviewed work items.",
                    "proposedIntervention": "Clarify one conflicting coordination instruction.",
                    "acceptanceCriteria": ["A deterministic regression case passes."],
                    "evaluationRequirement": "Run routing and role-context smoke evaluations.",
                },
            }],
        }],
    }


def _monitoring_session(session_id, *, model="private-model"):
    return {
        "sessionId": session_id,
        "traceIds": [f"trace-{session_id}"],
        "correlation": {
            "status": "linked",
            "beadId": "pi-source",
            "routingTask": "review",
            "risk": "medium",
            "role": "quality-reviewer",
        },
        "features": {
            "toolErrors": 0,
            "models": [model],
            "promptHash": "a" * 64,
            "captureGaps": [],
        },
    }


def _monitoring_packet(report_id, session_ids, *, model="private-model"):
    return {
        "schemaVersion": 2,
        "reportId": report_id,
        "createdAt": "2026-07-30T00:00:00Z",
        "scan": {
            "since": "2026-07-26T00:00:00Z",
            "until": "2026-07-30T00:00:00Z",
            "limit": len(session_ids),
            "recheck": False,
            "reviewPolicyVersion": "v1",
        },
        "sessions": [_monitoring_session(session_id, model=model) for session_id in session_ids],
    }


def _no_action_decisions(packet):
    return {
        "schemaVersion": 1,
        "reportId": packet["reportId"],
        "reviewPolicyVersion": "v1",
        "reviewedAt": packet["createdAt"],
        "sessions": [
            {"sessionId": session["sessionId"], "decision": "no-action", "findings": []}
            for session in packet["sessions"]
        ],
    }


def _promote_monitoring_source(tmp_path):
    packet = _monitoring_packet("source-report", ["2026-07-27T00-00-00-000Z_source"])
    decisions = _review_decisions()
    decisions["reportId"] = packet["reportId"]
    decisions["reviewedAt"] = packet["createdAt"]
    decisions["sessions"][0]["sessionId"] = packet["sessions"][0]["sessionId"]
    state_dir = tmp_path / "private-state"

    def beads_runner(args):
        if args[0] == "show":
            return 0, {
                "id": args[1],
                "status": "closed",
                "closed_at": "2026-07-28T00:00:00Z",
            }, ""
        return 0, {"id": args[args.index("--id") + 1]}, ""

    base = {
        "finding_id": "finding-0123456789ab",
        "state_dir": state_dir,
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "beads_runner": beads_runner,
    }
    preview = improvement.promote_finding(None, packet, decisions, apply=False, **base)["approvalPreview"]
    result = improvement.promote_finding(
        FakeReviewClient(), packet, decisions, apply=True, approval=_approved_preview(preview), **base
    )
    return packet, decisions, state_dir, beads_runner, result["beadId"]


def test_review_rubric_requires_unknown_and_evidence_thresholds():
    rubric = (ROOT / "pi" / "agent" / "langfuse" / "improvement-review.md").read_text(encoding="utf-8")

    for required in (
        "`unknown`",
        "3 confirmed instances",
        "2 independent work items",
        "1.5×",
        "5 comparable invocations",
        "`relatedFindingId`",
        "`validated`",
        "`recurrent`",
        "Human approval",
    ):
        assert required in rubric


def test_human_calibrated_policy_accepts_security_boundary_regression():
    packet = _review_packet()
    decisions = _review_decisions()
    packet["scan"]["reviewPolicyVersion"] = improvement.REVIEW_POLICY_VERSION
    decisions["reviewPolicyVersion"] = improvement.REVIEW_POLICY_VERSION
    finding = decisions["sessions"][0]["findings"][0]
    finding["category"] = "security-boundary"
    finding["impact"] = "high"
    finding["attribution"] = "tooling"
    finding["proposedIntervention"] = "code"

    rubric = (ROOT / "pi" / "agent" / "langfuse" / "improvement-review.md").read_text(encoding="utf-8")

    assert improvement.REVIEW_POLICY_VERSION == "v2"
    assert improvement.validate_decisions(packet, decisions) == decisions
    for required in (
        "`security-boundary`",
        "confirmed credential exposure",
        "zero deterministic actionable signals",
        "workflow stall",
        "output-limit truncation",
        "| `security-success` | Successful outcome, zero actionable signals, and separately confirmed credential exposure | `security-boundary`, high impact |",
        "| `handoff-stall` | Handoff contract does not start the ready target and no infrastructure cause is verified | `coordination-error`, workflow intervention |",
        "| `one-shot-truncation` | Avoidable configured output cap terminates otherwise usable one-shot work | `token-inefficiency`, routing or workflow intervention |",
    ):
        assert required in rubric


def test_v1_decision_rejects_v2_only_security_category():
    packet = _review_packet()
    decisions = _review_decisions()
    decisions["sessions"][0]["findings"][0]["category"] = "security-boundary"

    with pytest.raises(ValueError, match="category is unsupported"):
        improvement.validate_decisions(packet, decisions)


def test_historical_schema_1_private_packet_remains_reviewable():
    packet = _review_packet()
    decisions = _review_decisions()

    assert packet["schemaVersion"] == 1
    assert improvement.validate_decisions(packet, decisions) == decisions


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("unknown-field", "unknown fields"),
        ("bad-finding-id", "findingId"),
        ("unsupported-category", "category"),
        ("missing-evidence", "evidenceRefs"),
        ("bad-evidence-pointer", "evidence reference"),
        ("copied-public-text", "copied private packet text"),
    ],
)
def test_review_decisions_reject_unsafe_or_malformed_content(case, message):
    packet = _review_packet()
    decisions = _review_decisions()
    finding = decisions["sessions"][0]["findings"][0]
    if case == "unknown-field":
        finding["sourceExcerpt"] = "private content"
    elif case == "bad-finding-id":
        finding["findingId"] = "../../private"
    elif case == "unsupported-category":
        finding["category"] = "invented"
    elif case == "missing-evidence":
        finding["evidenceRefs"] = []
    elif case == "bad-evidence-pointer":
        finding["evidenceRefs"] = ["/sessions/0/privateInput"]
    else:
        finding["public"]["aggregate"] = "private-model"

    with pytest.raises(ValueError, match=message):
        improvement.validate_decisions(packet, decisions)


class FakeReviewClient:
    def __init__(self, fail_once=False):
        self.calls = []
        self.fail_once = fail_once

    def list_scores(self, **_kwargs):
        return []

    def put_session_score(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_once:
            self.fail_once = False
            raise langfuse.LangfuseError("private score write failed")
        return {"id": kwargs["score_id"]}


def test_review_preview_does_not_write_scores_or_emit_private_ids():
    client = FakeReviewClient()

    summary = improvement.review_sessions(client, _review_packet(), _review_decisions(), apply=False)

    assert summary == {
        "schemaVersion": 1,
        "status": "preview",
        "reviewedSessions": 1,
        "findings": 1,
        "scoresWritten": 0,
    }
    assert client.calls == []
    assert "private-session" not in json.dumps(summary)


def test_review_apply_uses_deterministic_idempotent_session_markers():
    client = FakeReviewClient()
    packet = _review_packet()
    decisions = _review_decisions()

    first = improvement.review_sessions(client, packet, decisions, apply=True)
    second = improvement.review_sessions(client, packet, decisions, apply=True)

    assert first["scoresWritten"] == second["scoresWritten"] == 1
    assert len(client.calls) == 2
    assert client.calls[0] == client.calls[1]
    marker = client.calls[0]
    assert marker["session_id"] == "private-session"
    assert marker["name"] == "improvement_review_status"
    assert marker["value"] == "actions-created"
    assert marker["data_type"] == "CATEGORICAL"
    assert marker["metadata"] == {
        "schemaVersion": 1,
        "reviewPolicyVersion": "v1",
        "reviewedAt": "2026-07-27T01:00:00Z",
        "findingIds": ["finding-0123456789ab"],
        "beadIds": [],
    }


def test_review_score_failure_is_retryable_with_same_marker_id():
    client = FakeReviewClient(fail_once=True)
    packet = _review_packet()
    decisions = _review_decisions()

    with pytest.raises(langfuse.LangfuseError):
        improvement.review_sessions(client, packet, decisions, apply=True)
    improvement.review_sessions(client, packet, decisions, apply=True)

    assert client.calls[0]["score_id"] == client.calls[1]["score_id"]


def test_improvement_dir_uses_private_default_and_environment_override(monkeypatch, tmp_path):
    monkeypatch.delenv("AGNT_IMPROVEMENT_DIR", raising=False)
    assert improvement.improvement_dir() == Path.home() / ".pi" / "improvement"

    override = tmp_path / "override"
    monkeypatch.setenv("AGNT_IMPROVEMENT_DIR", str(override))
    assert improvement.improvement_dir() == override


def test_improve_review_cli_is_preview_only_by_default(monkeypatch, tmp_path, capsys):
    private_dir = tmp_path / "private"
    private_dir.mkdir()
    report_path = private_dir / "report.json"
    decisions_path = private_dir / "decisions.json"
    report_path.write_text(json.dumps(_review_packet()), encoding="utf-8")
    decisions_path.write_text(json.dumps(_review_decisions()), encoding="utf-8")
    monkeypatch.setattr(improvement, "git_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(improvement, "_client_from_env", lambda: pytest.fail("preview must not create client"))

    result = improvement.cmd_improve(["review", str(report_path), str(decisions_path), "--json"])

    assert result == 0
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "preview"
    assert "private-session" not in output
    assert "private-trace" not in output


def test_improve_review_cli_applies_markers_only_with_apply(monkeypatch, tmp_path, capsys):
    private_dir = tmp_path / "private"
    private_dir.mkdir()
    report_path = private_dir / "report.json"
    decisions_path = private_dir / "decisions.json"
    report_path.write_text(json.dumps(_review_packet()), encoding="utf-8")
    decisions_path.write_text(json.dumps(_review_decisions()), encoding="utf-8")
    client = FakeReviewClient()
    monkeypatch.setattr(improvement, "git_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)

    result = improvement.cmd_improve(["review", str(report_path), str(decisions_path), "--apply", "--json"])

    assert result == 0
    assert json.loads(capsys.readouterr().out)["status"] == "applied"
    assert len(client.calls) == 1


def _approved_preview(preview):
    return {
        "metadata": {
            "pi": {
                "approval": {
                    "kind": "approval",
                    "status": "approved",
                    "resolver": {"kind": "human-ui"},
                    "preview": preview,
                },
            },
        },
    }


def test_promotion_initializes_private_monitoring_state(tmp_path):
    _packet, _decisions, state_dir, _beads_runner, bead_id = _promote_monitoring_source(tmp_path)

    state = json.loads((state_dir / "promotion-finding-0123456789ab.json").read_text(encoding="utf-8"))

    assert state == {
        "schemaVersion": 2,
        "findingId": "finding-0123456789ab",
        "beadId": bead_id,
        "creationPending": False,
        "linkRepairNeeded": False,
        "monitoring": {
            "status": "promoted",
            "cohortKey": state["monitoring"]["cohortKey"],
            "minimumSamples": 5,
            "implementedAt": None,
            "sampleIds": [],
            "recurrentFindingIds": [],
        },
    }
    assert re.fullmatch(r"[0-9a-f]{64}", state["monitoring"]["cohortKey"])


def test_reviewed_matched_cohorts_stay_monitoring_until_minimum_then_validate(tmp_path):
    _source, _decisions, state_dir, beads_runner, _bead_id = _promote_monitoring_source(tmp_path)
    first_packet = _monitoring_packet(
        "later-report-1",
        [f"2026-07-29T00-00-00-00{index}Z_case" for index in range(4)],
    )
    first_packet["sessions"].append(_monitoring_session("2026-07-29T00-00-00-009Z_unmatched", model="other-model"))

    first = improvement.review_sessions(
        FakeReviewClient(),
        first_packet,
        _no_action_decisions(first_packet),
        apply=True,
        state_dir=state_dir,
        beads_runner=beads_runner,
    )
    state_path = state_dir / "promotion-finding-0123456789ab.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert first["monitoring"] == {"monitoring": 1, "validated": 0, "recurrent": 0}
    assert state["monitoring"]["status"] == "monitoring"
    assert len(state["monitoring"]["sampleIds"]) == 4
    assert state["monitoring"]["implementedAt"] == "2026-07-28T00:00:00Z"

    final_packet = _monitoring_packet("later-report-2", ["2026-07-30T00-00-00-000Z_case"])
    final = improvement.review_sessions(
        FakeReviewClient(),
        final_packet,
        _no_action_decisions(final_packet),
        apply=True,
        state_dir=state_dir,
        beads_runner=beads_runner,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert final["monitoring"] == {"monitoring": 0, "validated": 1, "recurrent": 0}
    assert state["monitoring"]["status"] == "validated"
    assert len(state["monitoring"]["sampleIds"]) == 5


def test_related_later_finding_marks_recurrence_without_public_mutation(tmp_path):
    _source, _decisions, state_dir, beads_runner, _bead_id = _promote_monitoring_source(tmp_path)
    packet = _monitoring_packet("recurrent-report", ["2026-07-29T00-00-00-000Z_case"])
    decisions = _review_decisions()
    decisions["reportId"] = packet["reportId"]
    decisions["reviewedAt"] = packet["createdAt"]
    decisions["sessions"][0]["sessionId"] = packet["sessions"][0]["sessionId"]
    finding = decisions["sessions"][0]["findings"][0]
    finding["findingId"] = "finding-abcdef012345"
    finding["relatedFindingId"] = "finding-0123456789ab"
    calls = []

    def no_public_mutation(args):
        calls.append(args)
        return beads_runner(args)

    summary = improvement.review_sessions(
        FakeReviewClient(),
        packet,
        decisions,
        apply=True,
        state_dir=state_dir,
        beads_runner=no_public_mutation,
    )
    state = json.loads(
        (state_dir / "promotion-finding-0123456789ab.json").read_text(encoding="utf-8")
    )

    assert summary["monitoring"] == {"monitoring": 0, "validated": 0, "recurrent": 1}
    assert state["monitoring"]["status"] == "recurrent"
    assert state["monitoring"]["recurrentFindingIds"] == ["finding-abcdef012345"]
    assert all(args[0] == "show" for args in calls)

    with pytest.raises(ValueError, match="exact human approval"):
        improvement.promote_finding(
            FakeReviewClient(),
            packet,
            decisions,
            finding_id="finding-abcdef012345",
            state_dir=state_dir,
            repository_root=tmp_path / "repo",
            tracked_paths={"pi/agent/AGENTS.md"},
            apply=True,
            approval=None,
            beads_runner=beads_runner,
        )


def test_invalid_related_finding_fails_before_review_marker_write(tmp_path):
    _source, _decisions, state_dir, beads_runner, _bead_id = _promote_monitoring_source(tmp_path)
    packet = _monitoring_packet("invalid-related-report", ["2026-07-29T00-00-00-000Z_case"])
    decisions = _review_decisions()
    decisions["reportId"] = packet["reportId"]
    decisions["reviewedAt"] = packet["createdAt"]
    decisions["sessions"][0]["sessionId"] = packet["sessions"][0]["sessionId"]
    decisions["sessions"][0]["findings"][0]["findingId"] = "finding-abcdef012345"
    decisions["sessions"][0]["findings"][0]["relatedFindingId"] = "finding-deadbeefdead"
    client = FakeReviewClient()

    with pytest.raises(ValueError, match="does not match monitored"):
        improvement.review_sessions(
            client,
            packet,
            decisions,
            apply=True,
            state_dir=state_dir,
            beads_runner=beads_runner,
        )

    assert client.calls == []


def test_related_finding_requires_available_closed_implementation_boundary(tmp_path):
    _source, _decisions, state_dir, _beads_runner, _bead_id = _promote_monitoring_source(tmp_path)
    packet = _monitoring_packet("open-boundary-report", ["2026-07-29T00-00-00-000Z_case"])
    decisions = _review_decisions()
    decisions["reportId"] = packet["reportId"]
    decisions["reviewedAt"] = packet["createdAt"]
    decisions["sessions"][0]["sessionId"] = packet["sessions"][0]["sessionId"]
    decisions["sessions"][0]["findings"][0]["findingId"] = "finding-abcdef012345"
    decisions["sessions"][0]["findings"][0]["relatedFindingId"] = "finding-0123456789ab"
    client = FakeReviewClient()

    with pytest.raises(ValueError, match="implementation boundary is unavailable"):
        improvement.review_sessions(
            client,
            packet,
            decisions,
            apply=True,
            state_dir=state_dir,
            beads_runner=lambda args: (0, {"id": args[1], "status": "open"}, ""),
        )

    assert client.calls == []


def test_reapplying_review_preserves_promoted_bead_links(tmp_path):
    packet, decisions, state_dir, beads_runner, bead_id = _promote_monitoring_source(tmp_path)
    client = FakeReviewClient()

    improvement.review_sessions(
        client,
        packet,
        decisions,
        apply=True,
        state_dir=state_dir,
        beads_runner=beads_runner,
    )

    assert client.calls[0]["metadata"]["beadIds"] == [bead_id]


def test_correlated_session_uses_exact_start_time_for_monitoring(tmp_path):
    _source, _decisions, state_dir, beads_runner, _bead_id = _promote_monitoring_source(tmp_path)
    packet = _monitoring_packet("headless-report", ["run-later"])
    packet["sessions"][0]["correlation"]["startedAt"] = "2026-07-29T00:00:00Z"

    improvement.review_sessions(
        FakeReviewClient(),
        packet,
        _no_action_decisions(packet),
        apply=True,
        state_dir=state_dir,
        beads_runner=beads_runner,
    )
    state = json.loads(
        (state_dir / "promotion-finding-0123456789ab.json").read_text(encoding="utf-8")
    )

    assert len(state["monitoring"]["sampleIds"]) == 1


def test_concurrent_monitoring_updates_preserve_both_samples(monkeypatch, tmp_path):
    _source, _decisions, state_dir, beads_runner, _bead_id = _promote_monitoring_source(tmp_path)
    packets = [
        _monitoring_packet("parallel-a", ["2026-07-29T00-00-00-001Z_case"]),
        _monitoring_packet("parallel-b", ["2026-07-29T00-00-00-002Z_case"]),
    ]
    original_write = improvement._write_private_json
    first_write = threading.Event()
    second_write = threading.Event()
    write_count = 0
    count_lock = threading.Lock()

    def controlled_write(output_dir, filename, value):
        nonlocal write_count
        if filename == "promotion-finding-0123456789ab.json" and value.get("monitoring", {}).get("sampleIds"):
            with count_lock:
                write_count += 1
                current = write_count
            if current == 1:
                first_write.set()
                second_write.wait(timeout=0.2)
            else:
                second_write.set()
        return original_write(output_dir, filename, value)

    monkeypatch.setattr(improvement, "_write_private_json", controlled_write)
    errors = []

    def update(packet):
        try:
            improvement._update_monitoring_states(
                packet,
                _no_action_decisions(packet),
                state_dir=state_dir,
                beads_runner=beads_runner,
            )
        except Exception as error:  # pragma: no cover - asserted below
            errors.append(error)

    first = threading.Thread(target=update, args=(packets[0],))
    second = threading.Thread(target=update, args=(packets[1],))
    first.start()
    assert first_write.wait(timeout=1)
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    state = json.loads(
        (state_dir / "promotion-finding-0123456789ab.json").read_text(encoding="utf-8")
    )
    assert errors == []
    assert not first.is_alive() and not second.is_alive()
    assert len(state["monitoring"]["sampleIds"]) == 2


@pytest.mark.parametrize("decision", ["excluded", "needs-human"])
def test_inconclusive_review_decisions_do_not_validate_monitoring(tmp_path, decision):
    _source, _decisions, state_dir, beads_runner, _bead_id = _promote_monitoring_source(tmp_path)
    packet = _monitoring_packet("inconclusive-report", ["2026-07-29T00-00-00-000Z_case"])
    decisions = _no_action_decisions(packet)
    decisions["sessions"][0]["decision"] = decision

    summary = improvement.review_sessions(
        FakeReviewClient(),
        packet,
        decisions,
        apply=True,
        state_dir=state_dir,
        beads_runner=beads_runner,
    )
    state = json.loads(
        (state_dir / "promotion-finding-0123456789ab.json").read_text(encoding="utf-8")
    )

    assert summary["monitoring"] == {"monitoring": 1, "validated": 0, "recurrent": 0}
    assert state["monitoring"]["sampleIds"] == []


def test_scan_projects_matched_monitoring_privately_but_summary_is_count_only(tmp_path):
    state_dir = tmp_path / "private-state"
    source_id = "2026-07-27T00-00-00-000Z_source"
    source_client = FakeScanClient(
        [_private_trace(source_id, "source-trace")],
        {"source-trace": _private_observations()},
    )
    _source_summary, source_packet = _scan_sessions(
        source_client,
        tmp_path,
        output_dir=state_dir,
        limit=1,
    )
    decisions = _review_decisions()
    decisions["reportId"] = source_packet["reportId"]
    decisions["reviewPolicyVersion"] = source_packet["scan"]["reviewPolicyVersion"]
    decisions["reviewedAt"] = source_packet["createdAt"]
    decisions["sessions"][0]["sessionId"] = source_id

    def beads_runner(args):
        if args[0] == "show":
            return 0, {"id": args[1], "status": "closed", "closed_at": "2026-07-28T00:00:00Z"}, ""
        return 0, {"id": args[args.index("--id") + 1]}, ""

    base = {
        "finding_id": "finding-0123456789ab",
        "state_dir": state_dir,
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "beads_runner": beads_runner,
    }
    preview = improvement.promote_finding(
        None, source_packet, decisions, apply=False, **base
    )["approvalPreview"]
    improvement.promote_finding(
        FakeReviewClient(),
        source_packet,
        decisions,
        apply=True,
        approval=_approved_preview(preview),
        **base,
    )

    later_id = "2026-07-29T00-00-00-000Z_later"
    later_client = FakeScanClient(
        [_private_trace(later_id, "later-trace")],
        {"later-trace": _private_observations()},
    )
    summary, packet = _scan_sessions(
        later_client,
        tmp_path,
        output_dir=state_dir,
        limit=1,
        beads_runner=beads_runner,
    )

    assert packet["monitoring"] == [{
        "findingId": "finding-0123456789ab",
        "status": "monitoring",
        "matchedSessionIndexes": [0],
        "minimumSamples": 5,
        "reviewedSamples": 0,
    }]
    assert summary["monitoring"] == {
        "promoted": 0,
        "monitoring": 1,
        "validated": 0,
        "recurrent": 0,
        "matchedSessions": 1,
    }
    assert "finding-0123456789ab" not in json.dumps(summary)


def test_promote_preview_contains_only_exact_public_bead_and_approval_text(tmp_path):
    summary = improvement.promote_finding(
        None,
        _review_packet(),
        _review_decisions(),
        finding_id="finding-0123456789ab",
        state_dir=tmp_path / "private-state",
        repository_root=tmp_path / "repo",
        tracked_paths={"pi/agent/AGENTS.md"},
        apply=False,
        beads_runner=lambda _args: pytest.fail("preview must not mutate Beads"),
    )

    assert summary["status"] == "preview"
    assert summary["bead"] == {
        "title": "Improve coordination instruction targeting",
        "category": "coordination-error",
        "affectedPaths": ["pi/agent/AGENTS.md"],
        "description": (
            "Category: coordination-error\n\n"
            "Affected tracked paths:\n- pi/agent/AGENTS.md\n\n"
            "Sanitized aggregate: Repeated coordination failures occurred across reviewed work items.\n\n"
            "Proposed intervention: Clarify one conflicting coordination instruction.\n\n"
            "Evaluation requirement: Run routing and role-context smoke evaluations."
        ),
        "acceptance": "- A deterministic regression case passes.",
        "labels": ["continuous-improvement", "coordination-error", "human-approved"],
    }
    assert summary["approvalPreview"]["scope"].endswith(improvement.render_public_bead(summary["bead"]))
    output = json.dumps(summary)
    for private in ("private-session", "private-trace", "finding-0123456789ab", "private-model"):
        assert private not in output


@pytest.mark.parametrize(
    "unsafe",
    [
        "url",
        "ssh-url",
        "absolute-path",
        "email",
        "uuid",
        "hash-id",
        "secret",
        "telemetry",
        "unknown-field",
        "copied-text",
        "case-changed-copy",
        "newline-path",
    ],
)
def test_promote_rejects_unsafe_public_preview_before_bead_mutation(tmp_path, unsafe):
    packet = _review_packet()
    decisions = _review_decisions()
    public = decisions["sessions"][0]["findings"][0]["public"]
    tracked_paths = {"pi/agent/AGENTS.md"}
    if unsafe == "url":
        public["aggregate"] = "See https://private.example/evidence"
    elif unsafe == "ssh-url":
        public["aggregate"] = "See ssh://private.example/evidence"
    elif unsafe == "absolute-path":
        public["affectedPaths"] = ["/private/repo/file.py"]
    elif unsafe == "email":
        public["aggregate"] = "Reported by private@example.com"
    elif unsafe == "uuid":
        public["aggregate"] = "Evidence 12345678-1234-1234-1234-123456789abc"
    elif unsafe == "hash-id":
        public["aggregate"] = "Evidence PATH_HASH:483cca468d65"
    elif unsafe == "secret":
        public["aggregate"] = "Use API key private-value"
    elif unsafe == "telemetry":
        public["aggregate"] = "One traceId was affected"
    elif unsafe == "unknown-field":
        public["telemetryId"] = "private-observation"
    elif unsafe == "copied-text":
        public["aggregate"] = "private-model"
    elif unsafe == "case-changed-copy":
        public["aggregate"] = "PRIVATE-MODEL"
    else:
        public["affectedPaths"] = ["pi/agent/file.py\nInjected: private content"]
        tracked_paths.add("pi/agent/file.py\nInjected: private content")
    calls = []

    with pytest.raises(ValueError, match="public"):
        improvement.promote_finding(
            None,
            packet,
            decisions,
            finding_id="finding-0123456789ab",
            state_dir=tmp_path / "private-state",
            repository_root=tmp_path / "repo",
            tracked_paths=tracked_paths,
            apply=True,
            approval=None,
            beads_runner=lambda args: calls.append(args),
        )

    assert calls == []


def test_promote_apply_requires_human_approval_of_exact_preview(tmp_path):
    calls = []
    kwargs = {
        "finding_id": "finding-0123456789ab",
        "state_dir": tmp_path / "private-state",
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "apply": True,
        "beads_runner": lambda args: calls.append(args),
    }

    with pytest.raises(ValueError, match="exact human approval"):
        improvement.promote_finding(None, _review_packet(), _review_decisions(), approval=None, **kwargs)

    preview = improvement.promote_finding(
        None,
        _review_packet(),
        _review_decisions(),
        apply=False,
        **{key: value for key, value in kwargs.items() if key != "apply"},
    )["approvalPreview"]
    preview["scope"] += " changed"
    with pytest.raises(ValueError, match="exact human approval"):
        improvement.promote_finding(
            None,
            _review_packet(),
            _review_decisions(),
            approval=_approved_preview(preview),
            **kwargs,
        )

    assert calls == []


def test_private_json_write_fsyncs_file_and_directory(monkeypatch, tmp_path):
    synced = []
    monkeypatch.setattr(improvement.os, "fsync", lambda fd: synced.append(fd))

    improvement._write_private_json(tmp_path / "private", "state.json", {"schemaVersion": 1})

    assert len(synced) == 2


def test_promote_apply_creates_once_and_links_private_marker(tmp_path):
    client = FakeReviewClient()
    created = []

    def beads_runner(args):
        created.append(args)
        return 0, {"id": args[args.index("--id") + 1]}, ""

    base = {
        "finding_id": "finding-0123456789ab",
        "state_dir": tmp_path / "private-state",
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "beads_runner": beads_runner,
    }
    preview = improvement.promote_finding(
        None, _review_packet(), _review_decisions(), apply=False, **base
    )["approvalPreview"]
    approval = _approved_preview(preview)

    first = improvement.promote_finding(
        client, _review_packet(), _review_decisions(), apply=True, approval=approval, **base
    )
    second = improvement.promote_finding(
        client, _review_packet(), _review_decisions(), apply=True, approval=approval, **base
    )

    assert first["status"] == "promoted"
    assert second["status"] == "already-promoted"
    assert first["beadId"] == second["beadId"]
    assert improvement.BEAD_ID.fullmatch(first["beadId"])
    assert len(created) == 1
    assert "--id" in created[0]
    command = json.dumps(created[0])
    for private in ("private-session", "private-trace", "finding-0123456789ab", "private-model"):
        assert private not in command
    assert client.calls[0]["metadata"]["beadIds"] == [first["beadId"]]
    state_path = tmp_path / "private-state" / "promotion-finding-0123456789ab.json"
    assert stat.S_IMODE((tmp_path / "private-state").stat().st_mode) == 0o700
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600


def test_promote_serializes_concurrent_create_attempts(tmp_path):
    client = FakeReviewClient()
    create_barrier = threading.Barrier(2)
    created = []

    def beads_runner(args):
        created.append(args)
        try:
            create_barrier.wait(timeout=0.2)
        except threading.BrokenBarrierError:
            pass
        return 0, {"id": args[args.index("--id") + 1]}, ""

    base = {
        "finding_id": "finding-0123456789ab",
        "state_dir": tmp_path / "private-state",
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "beads_runner": beads_runner,
    }
    preview = improvement.promote_finding(
        None, _review_packet(), _review_decisions(), apply=False, **base
    )["approvalPreview"]

    def invoke():
        return improvement.promote_finding(
            client,
            _review_packet(),
            _review_decisions(),
            apply=True,
            approval=_approved_preview(preview),
            **base,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: invoke(), range(2)))

    assert len(created) == 1
    assert {result["status"] for result in results} == {"promoted", "already-promoted"}


def test_promote_rejects_mismatched_private_state(tmp_path):
    state_dir = tmp_path / "private-state"
    improvement._write_private_json(state_dir, "promotion-finding-0123456789ab.json", {
        "schemaVersion": 99,
        "findingId": "finding-deadbeefdead",
        "beadId": "pi-wrong.1",
        "creationPending": False,
        "linkRepairNeeded": False,
    })

    with pytest.raises(ValueError, match="private promotion state"):
        improvement.promote_finding(
            FakeReviewClient(),
            _review_packet(),
            _review_decisions(),
            finding_id="finding-0123456789ab",
            state_dir=state_dir,
            repository_root=tmp_path / "repo",
            tracked_paths={"pi/agent/AGENTS.md"},
            apply=True,
            approval=None,
            beads_runner=lambda _args: pytest.fail("invalid state must not create"),
        )


def test_promote_ignores_other_pending_findings_when_linking_session(tmp_path):
    decisions = _review_decisions()
    second = json.loads(json.dumps(decisions["sessions"][0]["findings"][0]))
    second["findingId"] = "finding-abcdef012345"
    second["public"]["title"] = "Improve separate verification behavior"
    decisions["sessions"][0]["findings"].append(second)
    state_dir = tmp_path / "private-state"
    improvement._write_private_json(state_dir, "promotion-finding-abcdef012345.json", {
        "schemaVersion": 1,
        "findingId": "finding-abcdef012345",
        "beadId": "pi-pending.1",
        "creationPending": True,
        "linkRepairNeeded": True,
    })
    client = FakeReviewClient()
    created = []

    def beads_runner(args):
        created.append(args)
        return 0, {"id": args[args.index("--id") + 1]}, ""

    base = {
        "finding_id": "finding-0123456789ab",
        "state_dir": state_dir,
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "beads_runner": beads_runner,
    }
    preview = improvement.promote_finding(
        None, _review_packet(), decisions, apply=False, **base
    )["approvalPreview"]

    result = improvement.promote_finding(
        client,
        _review_packet(),
        decisions,
        apply=True,
        approval=_approved_preview(preview),
        **base,
    )

    assert result["status"] == "promoted"
    assert client.calls[0]["metadata"]["beadIds"] == [result["beadId"]]


def test_promote_state_failure_after_create_blocks_duplicate_retry(monkeypatch, tmp_path):
    client = FakeReviewClient()
    created = []

    def beads_runner(args):
        if args[0] == "show":
            return 0, {"id": args[1]}, ""
        created.append(args)
        return 0, {"id": args[args.index("--id") + 1]}, ""

    base = {
        "finding_id": "finding-0123456789ab",
        "state_dir": tmp_path / "private-state",
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "beads_runner": beads_runner,
    }
    preview = improvement.promote_finding(
        None, _review_packet(), _review_decisions(), apply=False, **base
    )["approvalPreview"]
    original_write = improvement._write_private_json
    writes = 0

    def fail_second_write(*args, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("disk full")
        return original_write(*args, **kwargs)

    monkeypatch.setattr(improvement, "_write_private_json", fail_second_write)
    with pytest.raises(OSError, match="disk full"):
        improvement.promote_finding(
            client,
            _review_packet(),
            _review_decisions(),
            apply=True,
            approval=_approved_preview(preview),
            **base,
        )

    second = improvement.promote_finding(
        client,
        _review_packet(),
        _review_decisions(),
        apply=True,
        approval=_approved_preview(preview),
        **base,
    )
    assert second["schemaVersion"] == 1
    assert second["status"] == "promoted"
    assert second["created"] is False
    assert len(created) == 1


def test_promote_link_write_failure_retries_without_duplicate_bead(tmp_path):
    client = FakeReviewClient(fail_once=True)
    created = []

    def beads_runner(args):
        created.append(args)
        return 0, {"id": args[args.index("--id") + 1]}, ""

    base = {
        "finding_id": "finding-0123456789ab",
        "state_dir": tmp_path / "private-state",
        "repository_root": tmp_path / "repo",
        "tracked_paths": {"pi/agent/AGENTS.md"},
        "beads_runner": beads_runner,
    }
    preview = improvement.promote_finding(
        None, _review_packet(), _review_decisions(), apply=False, **base
    )["approvalPreview"]

    first = improvement.promote_finding(
        client,
        _review_packet(),
        _review_decisions(),
        apply=True,
        approval=_approved_preview(preview),
        **base,
    )
    second = improvement.promote_finding(
        client,
        _review_packet(),
        _review_decisions(),
        apply=True,
        approval=None,
        **base,
    )

    assert first["status"] == "link-repair-needed"
    assert second["status"] == "promoted"
    assert len(created) == 1
    assert client.calls[0]["score_id"] == client.calls[1]["score_id"]


def test_improve_promote_cli_previews_without_remote_clients(monkeypatch, tmp_path, capsys):
    private_dir = tmp_path / "private"
    private_dir.mkdir()
    report_path = private_dir / "report.json"
    decisions_path = private_dir / "decisions.json"
    report_path.write_text(json.dumps(_review_packet()), encoding="utf-8")
    decisions_path.write_text(json.dumps(_review_decisions()), encoding="utf-8")
    monkeypatch.setattr(improvement, "git_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(improvement, "_git_tracked_paths", lambda _root: {"pi/agent/AGENTS.md"}, raising=False)
    monkeypatch.setattr(improvement, "_client_from_env", lambda: pytest.fail("preview must not create client"))
    monkeypatch.setattr(improvement, "_beads", lambda _args: pytest.fail("preview must not mutate Beads"), raising=False)
    monkeypatch.setenv("AGNT_IMPROVEMENT_DIR", str(private_dir / "state"))

    result = improvement.cmd_improve([
        "promote",
        str(report_path),
        str(decisions_path),
        "--finding",
        "finding-0123456789ab",
        "--json",
    ])

    assert result == 0
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "preview"
    for private in ("private-session", "private-trace", "finding-0123456789ab", "private-model"):
        assert private not in output


class FakeSessionOwnershipClient:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.score_queries = []
        self.put_calls = []

    def list_scores(self, **kwargs):
        self.score_queries.append(kwargs)
        return [
            row
            for row in self.rows
            if row.get("name") == kwargs["name"]
            and (row.get("subject") or {}).get("id") == kwargs["session_id"]
        ][: kwargs["limit"]]

    def put_session_score(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"id": kwargs["score_id"]}


def _ownership_score(session_id, name, bead_id):
    score_id = (
        improvement._work_link_score_id(session_id)
        if name == improvement.WORK_LINK_SCORE
        else improvement._outcome_score_id(session_id)
    )
    return {
        "id": score_id,
        "name": name,
        "value": "linked" if name == improvement.WORK_LINK_SCORE else "success",
        "source": "API",
        "metadata": {"schemaVersion": 1, "beadId": bead_id},
        "subject": {"kind": "session", "id": session_id},
    }


def test_session_handoff_source_requires_linked_explicit_closeout():
    session_id = "018cc251-f400-7000-8000-000000000000"
    client = FakeSessionOwnershipClient([
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-current.1"),
        _ownership_score(session_id, improvement.OUTCOME_SCORE, "pi-current.1"),
    ])

    assert improvement.session_handoff_source(client, session_id) == {
        "beadId": "pi-current.1",
        "outcome": "success",
    }

    missing_outcome = FakeSessionOwnershipClient([
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-current.1"),
    ])
    with pytest.raises(ValueError, match="closeout outcome"):
        improvement.session_handoff_source(missing_outcome, session_id)


def test_session_handoff_source_rejects_invalid_outcome_without_visibility_retry():
    session_id = "018cc251-f400-7000-8000-000000000000"
    invalid = _ownership_score(session_id, improvement.OUTCOME_SCORE, "pi-current.1")
    invalid["value"] = "rejected"
    client = FakeSessionOwnershipClient([
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-current.1"),
        invalid,
    ])

    with pytest.raises(ValueError, match="invalid") as caught:
        improvement.session_handoff_source(client, session_id)

    assert not isinstance(caught.value, improvement.SessionOutcomeUnavailable)


def test_closeout_handoff_source_waits_for_one_written_outcome(monkeypatch):
    session_id = "018cc251-f400-7000-8000-000000000000"
    client = FakeSessionOwnershipClient()
    improvement.record_session_outcome(
        client,
        session_id=session_id,
        bead_id="pi-current.1",
        outcome="success",
        beads_runner=lambda _args: (0, {"id": "pi-current.1"}, ""),
    )
    client.rows = [
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-current.1"),
        _ownership_score(session_id, improvement.OUTCOME_SCORE, "pi-current.1"),
    ]
    list_scores = client.list_scores
    hidden = [True]

    def delayed_list_scores(**kwargs):
        rows = list_scores(**kwargs)
        if kwargs["name"] == improvement.OUTCOME_SCORE and hidden[0]:
            hidden[0] = False
            return []
        return rows

    monkeypatch.setattr(client, "list_scores", delayed_list_scores)
    now = [0.0]
    sleeps = []
    monkeypatch.setattr(improvement, "monotonic", lambda: now[0])

    def advance(delay):
        sleeps.append(delay)
        now[0] += delay

    monkeypatch.setattr(improvement, "sleep", advance)

    assert improvement.closeout_handoff_source(client, session_id) == {
        "beadId": "pi-current.1",
        "outcome": "success",
    }
    assert [call["name"] for call in client.put_calls].count(improvement.OUTCOME_SCORE) == 1
    assert sleeps == [improvement.CLOSEOUT_OUTCOME_INITIAL_BACKOFF_SECONDS]


def test_closeout_handoff_source_stops_at_monotonic_deadline(monkeypatch):
    session_id = "018cc251-f400-7000-8000-000000000000"
    client = FakeSessionOwnershipClient([
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-current.1"),
    ])
    now = [0.0]
    sleeps = []
    monkeypatch.setattr(improvement, "CLOSEOUT_OUTCOME_TIMEOUT_SECONDS", 0.25)
    monkeypatch.setattr(improvement, "CLOSEOUT_OUTCOME_INITIAL_BACKOFF_SECONDS", 0.1)
    monkeypatch.setattr(improvement, "CLOSEOUT_OUTCOME_MAX_BACKOFF_SECONDS", 0.2)
    monkeypatch.setattr(improvement, "monotonic", lambda: now[0])

    def advance(delay):
        sleeps.append(delay)
        now[0] += delay

    monkeypatch.setattr(improvement, "sleep", advance)

    with pytest.raises(improvement.SessionOutcomeUnavailable, match="bounded wait"):
        improvement.closeout_handoff_source(client, session_id)

    assert sleeps == pytest.approx([0.1, 0.15])
    assert [query["name"] for query in client.score_queries].count(
        improvement.OUTCOME_SCORE
    ) == 3


@pytest.mark.parametrize(
    "error",
    [
        ValueError("outcome rejected"),
        improvement.SessionWorkItemConflict("wrong owner"),
        langfuse.LangfuseError("transport failed"),
        TimeoutError("transport timed out"),
    ],
    ids=("rejection", "wrong-owner", "transport", "timeout"),
)
def test_closeout_handoff_source_does_not_retry_other_errors(monkeypatch, error):
    calls = []

    def fail(_client, _session_id):
        calls.append(error)
        raise error

    monkeypatch.setattr(improvement, "session_handoff_source", fail)
    monkeypatch.setattr(
        improvement,
        "sleep",
        lambda _delay: pytest.fail("non-visibility errors must not be retried"),
    )

    with pytest.raises(type(error), match=re.escape(str(error))):
        improvement.closeout_handoff_source(object(), "session")

    assert calls == [error]


def test_session_handoff_source_uses_only_canonical_score_ownership(monkeypatch):
    session_id = "run-cwd-shadow"
    client = FakeSessionOwnershipClient([
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-current.1"),
        _ownership_score(session_id, improvement.OUTCOME_SCORE, "pi-current.1"),
    ])
    monkeypatch.setattr(
        improvement,
        "_correlate",
        lambda *_args, **_kwargs: pytest.fail("handoff source must not inspect run bundles"),
    )

    assert improvement.session_handoff_source(client, session_id) == {
        "beadId": "pi-current.1",
        "outcome": "success",
    }


@pytest.mark.parametrize("existing_name", [improvement.WORK_LINK_SCORE, improvement.OUTCOME_SCORE])
def test_link_session_rejects_conflicting_canonical_owner_before_write(existing_name):
    session_id = "018cc251-f400-7000-8000-000000000000"
    client = FakeSessionOwnershipClient([
        _ownership_score(session_id, existing_name, "pi-first.1"),
    ])

    with pytest.raises(ValueError, match="handoff_bead") as caught:
        improvement.link_session(
            client,
            session_id=session_id,
            bead_id="pi-second.1",
            beads_runner=lambda args: (0, {"id": args[1]}, ""),
        )

    assert client.put_calls == []
    assert "pi-first.1" not in str(caught.value)


def test_link_session_fails_closed_on_malformed_canonical_owner():
    session_id = "018cc251-f400-7000-8000-000000000000"
    malformed = _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-first.1")
    malformed["metadata"] = {"schemaVersion": 1}
    client = FakeSessionOwnershipClient([malformed])

    with pytest.raises(ValueError, match="handoff_bead"):
        improvement.link_session(
            client,
            session_id=session_id,
            bead_id="pi-second.1",
            beads_runner=lambda args: (0, {"id": args[1]}, ""),
        )

    assert client.put_calls == []


def test_link_session_fails_closed_when_ownership_read_hits_cap():
    session_id = "018cc251-f400-7000-8000-000000000000"
    rows = []
    for index in range(improvement.SCORES_PER_QUERY + 1):
        row = _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-second.1")
        row["id"] = f"noncanonical-{index}"
        rows.append(row)
    client = FakeSessionOwnershipClient(rows)

    with pytest.raises(ValueError, match="handoff_bead"):
        improvement.link_session(
            client,
            session_id=session_id,
            bead_id="pi-second.1",
            beads_runner=lambda args: (0, {"id": args[1]}, ""),
        )

    assert client.put_calls == []


def test_link_session_allows_same_owner_with_bounded_canonical_reads():
    session_id = "018cc251-f400-7000-8000-000000000000"
    client = FakeSessionOwnershipClient([
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-work.1"),
        _ownership_score(session_id, improvement.OUTCOME_SCORE, "pi-work.1"),
    ])

    result = improvement.link_session(
        client,
        session_id=session_id,
        bead_id="pi-work.1",
        beads_runner=lambda args: (0, {"id": args[1]}, ""),
    )

    assert result == {"schemaVersion": 1, "status": "linked", "beadId": "pi-work.1"}
    assert [query["name"] for query in client.score_queries] == [
        improvement.WORK_LINK_SCORE,
        improvement.OUTCOME_SCORE,
    ]
    assert all(query["session_id"] == session_id for query in client.score_queries)
    assert all(query["from_timestamp"] < query["to_timestamp"] for query in client.score_queries)
    assert all(1 <= query["limit"] <= improvement.SCORES_PER_QUERY + 1 for query in client.score_queries)
    assert [call["name"] for call in client.put_calls] == [improvement.WORK_LINK_SCORE]


@pytest.mark.parametrize("action", ["link", "outcome"])
def test_improve_cli_requires_fresh_session_after_work_item_conflict(action, monkeypatch, capsys):
    session_id = "018cc251-f400-7000-8000-000000000000"
    client = FakeSessionOwnershipClient([
        _ownership_score(session_id, improvement.WORK_LINK_SCORE, "pi-first.1"),
    ])
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "_beads", lambda args: (0, {"id": args[1]}, ""))
    monkeypatch.setenv("PI_SESSION_ID", session_id)
    argv = [action, "pi-second.1", "--json"]
    if action == "outcome":
        argv.insert(2, "success")

    assert improvement.cmd_improve(argv) == 2

    output = capsys.readouterr().out
    assert json.loads(output) == {
        "schemaVersion": 1,
        "status": "error",
        "error": "session belongs to another work item",
        "recovery": {
            "action": "start-fresh-session",
            "handoffTool": {
                "name": "handoff_bead",
                "arguments": {"targetBead": "pi-second.1"},
            },
            "humanFallback": {"command": "/new"},
        },
    }
    assert "/clone" not in output
    assert client.put_calls == []


def test_improve_link_cli_writes_idempotent_private_session_score(monkeypatch, tmp_path, capsys):
    client = FakeReviewClient()
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "_beads", lambda args: (0, {"id": args[1]}, ""))
    monkeypatch.delenv("PI_SESSION_ID", raising=False)
    monkeypatch.setenv("PI_SESSION_FILE", str(tmp_path / "2026-07-28T00-00-00Z_private-session.jsonl"))

    result = improvement.cmd_improve(["link", "pi-work.1", "--json"])

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {
        "beadId": "pi-work.1",
        "schemaVersion": 1,
        "status": "linked",
    }
    assert len(client.calls) == 1
    assert client.calls[0]["session_id"] == "2026-07-28T00-00-00Z_private-session"
    assert client.calls[0]["name"] == improvement.WORK_LINK_SCORE
    assert client.calls[0]["metadata"] == {"schemaVersion": 1, "beadId": "pi-work.1"}


def test_improve_link_cli_prefers_canonical_pi_session_id(monkeypatch, tmp_path, capsys):
    client = FakeReviewClient()
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "_beads", lambda args: (0, {"id": args[1]}, ""))
    monkeypatch.setenv("PI_SESSION_FILE", str(tmp_path / "2026-07-28T00-00-00Z_legacy-session.jsonl"))
    monkeypatch.setenv("PI_SESSION_ID", "018cc251-f400-7000-8000-000000000000")

    assert improvement.cmd_improve(["link", "pi-work.1", "--json"]) == 0

    assert json.loads(capsys.readouterr().out)["status"] == "linked"
    assert client.calls[0]["session_id"] == "018cc251-f400-7000-8000-000000000000"


def test_improve_link_cli_uses_pi_session_id_fallback_idempotently(monkeypatch, capsys):
    client = FakeReviewClient()
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "_beads", lambda args: (0, {"id": args[1]}, ""))
    monkeypatch.delenv("PI_SESSION_FILE", raising=False)
    monkeypatch.setenv("PI_SESSION_ID", "current-session-id")

    outputs = []
    for _ in range(2):
        assert improvement.cmd_improve(["link", "pi-work.1", "--json"]) == 0
        outputs.append(json.loads(capsys.readouterr().out))

    assert outputs == [
        {"beadId": "pi-work.1", "schemaVersion": 1, "status": "linked"},
        {"beadId": "pi-work.1", "schemaVersion": 1, "status": "linked"},
    ]
    assert [call["session_id"] for call in client.calls] == [
        "current-session-id",
        "current-session-id",
    ]
    assert client.calls[0]["score_id"] == client.calls[1]["score_id"]


def test_improve_outcome_cli_links_bead_and_writes_idempotent_final_outcome(monkeypatch, tmp_path, capsys):
    client = FakeReviewClient()
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "_beads", lambda args: (0, {"id": args[1]}, ""))
    monkeypatch.delenv("PI_SESSION_ID", raising=False)
    monkeypatch.setenv("PI_SESSION_FILE", str(tmp_path / "2026-07-28T00-00-00Z_private-session.jsonl"))

    result = improvement.cmd_improve(["outcome", "pi-work.1", "success", "--json"])

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {
        "beadId": "pi-work.1",
        "outcome": "success",
        "schemaVersion": 1,
        "status": "recorded",
    }
    assert [call["name"] for call in client.calls] == [
        improvement.WORK_LINK_SCORE,
        improvement.OUTCOME_SCORE,
    ]
    outcome = client.calls[1]
    assert outcome["session_id"] == "2026-07-28T00-00-00Z_private-session"
    assert outcome["value"] == "success"
    assert outcome["metadata"] == {"schemaVersion": 1, "beadId": "pi-work.1"}


def test_improve_outcome_cli_prefers_canonical_pi_session_id(monkeypatch, tmp_path, capsys):
    client = FakeReviewClient()
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "_beads", lambda args: (0, {"id": args[1]}, ""))
    monkeypatch.setenv("PI_SESSION_FILE", str(tmp_path / "2026-07-28T00-00-00Z_legacy-session.jsonl"))
    monkeypatch.setenv("PI_SESSION_ID", "018cc251-f400-7000-8000-000000000000")

    assert improvement.cmd_improve(["outcome", "pi-work.1", "success", "--json"]) == 0

    assert json.loads(capsys.readouterr().out)["status"] == "recorded"
    assert {call["session_id"] for call in client.calls} == {"018cc251-f400-7000-8000-000000000000"}


def test_improve_scan_cli_emits_safe_json_only(monkeypatch, tmp_path, capsys):
    client = FakeScanClient(
        [_private_trace("private-session", "private-trace")],
        {"private-trace": _private_observations()},
    )
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "git_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(improvement, "default_runs_dir", lambda: tmp_path / "runs")
    monkeypatch.setenv("AGNT_IMPROVEMENT_DIR", str(tmp_path / "private"))

    result = improvement.cmd_improve([
        "scan",
        "--since",
        "2026-07-26T00:00:00Z",
        "--limit",
        "1",
        "--dry-run",
        "--json",
    ])

    assert result == 0
    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary["eligibleSessions"] == 1
    assert summary["reportWritten"] is False
    assert client.trace_maxima == [500]
    for private in ("private-session", "private-trace", "private system prompt", "private user content"):
        assert private not in output


def test_improve_scan_cli_forwards_operator_max_traces(monkeypatch, tmp_path, capsys):
    client = FakeScanClient([], {})
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "git_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(improvement, "default_runs_dir", lambda: tmp_path / "runs")
    monkeypatch.setenv("AGNT_IMPROVEMENT_DIR", str(tmp_path / "private"))

    result = improvement.cmd_improve([
        "scan",
        "--since",
        "2026-07-26T00:00:00Z",
        "--max-traces",
        "7",
        "--dry-run",
        "--json",
    ])

    assert result == 0
    assert client.trace_maxima == [7]
    assert json.loads(capsys.readouterr().out)["traceDiscovery"]["maxTraces"] == 7
