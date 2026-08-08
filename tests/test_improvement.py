from __future__ import annotations

import io
import json
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
        self.reviewed = dict(reviewed) if isinstance(reviewed, dict) else {item: "v1" for item in reviewed}
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

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        max_traces=7,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=repository_root,
        dry_run=True,
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

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

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

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

    assert summary["schemaVersion"] == 1
    assert packet["schemaVersion"] == 2
    assert packet["scan"]["reviewPolicyVersion"] == "v1"
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


def test_scan_writes_private_atomic_packet_with_restrictive_permissions(tmp_path):
    output_dir = tmp_path / "private-runtime"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_dir = tmp_path / "runs"
    bundle = runs_dir / "private-run"
    bundle.mkdir(parents=True)
    (bundle / "invocation.yaml").write_text(
        json.dumps({"id": "private-run", "bead": "pi-safe.1"}),
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

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=output_dir,
        runs_dir=runs_dir,
        repository_root=repo_root,
    )

    assert summary["status"] == "ok"
    assert summary["eligibleSessions"] == 1
    assert summary["reportWritten"] is True
    assert "private-trace" not in json.dumps(summary)
    assert "run-private-run" not in json.dumps(summary)
    report_path = Path(summary["reportPath"])
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

    _, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

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

    _, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

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

    _, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

    features = packet["sessions"][0]["features"]
    assert features["finalOutcome"] == "success"
    assert "missing-outcome" not in features["captureGaps"]


def test_scan_dry_run_skips_reviewed_sessions_without_writing(tmp_path):
    reviewed = _private_trace("reviewed-session", "reviewed-trace")
    eligible = _private_trace("eligible-session", "eligible-trace")
    client = FakeScanClient(
        [reviewed, eligible],
        {"eligible-trace": _private_observations()},
        reviewed={"reviewed-session"},
    )
    output_dir = tmp_path / "must-not-exist"

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=output_dir,
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
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

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

    assert summary["eligibleSessions"] == 1
    assert summary["reviewedSessionsSkipped"] == 0
    assert packet["sessions"][0]["sessionId"] == "stale-session"


def test_scan_score_markers_are_bounded_from_pi_session_start(tmp_path):
    class QueryClient(FakeScanClient):
        def __init__(self, traces, observations):
            super().__init__(traces, observations)
            self.score_queries = []

        def list_scores(self, **kwargs):
            self.score_queries.append(kwargs)
            return super().list_scores(**kwargs)

    session_id = "2026-07-26T12-00-00-000Z_private-session"
    client = QueryClient(
        [_private_trace(session_id, "private-trace")],
        {"private-trace": _private_observations()},
    )

    improvement.scan_sessions(
        client,
        since="2026-07-27T00:00:00Z",
        until="2026-07-28T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

    session_queries = [query for query in client.score_queries if query.get("session_id") == session_id]
    assert len(session_queries) == 3
    assert {query["from_timestamp"] for query in session_queries} == {"2026-07-26T12:00:00Z"}


def test_scan_checks_multiple_review_markers_for_current_policy(tmp_path):
    class MixedMarkerClient(FakeScanClient):
        def list_scores(self, **kwargs):
            if kwargs.get("trace_id"):
                return []
            self.marker_limit = kwargs["limit"]
            return [
                {"value": "no-action", "metadata": {"reviewPolicyVersion": "older-policy"}},
                {"value": "no-action", "metadata": {"reviewPolicyVersion": "v1"}},
            ][: kwargs["limit"]]

    client = MixedMarkerClient([_private_trace("reviewed-session", "reviewed-trace")], {})

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

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

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

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

    summary, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

    expected = {
        "totalAvailable": 3,
        "scanned": 2,
        "maxTraces": 500,
        "attributable": 1,
        "unattributed": 1,
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

    _, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=tmp_path / "runs",
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

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

    _, packet = improvement.scan_sessions(
        client,
        since="2026-07-26T00:00:00Z",
        until="2026-07-27T00:00:00Z",
        limit=1,
        output_dir=tmp_path / "private",
        runs_dir=runs_dir,
        repository_root=tmp_path / "repo",
        dry_run=True,
    )

    assert packet["sessions"][0]["correlation"] == {"status": "unlinked"}


def test_scan_refuses_report_directory_inside_repository(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    client = FakeScanClient([], {})

    with pytest.raises(ValueError, match="outside repository"):
        improvement.scan_sessions(
            client,
            since="2026-07-26T00:00:00Z",
            until="2026-07-27T00:00:00Z",
            limit=1,
            output_dir=repo_root / ".pi" / "improvement",
            runs_dir=repo_root / ".pi" / "runs",
            repository_root=repo_root,
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


def test_review_rubric_requires_unknown_and_evidence_thresholds():
    rubric = (ROOT / "pi" / "agent" / "langfuse" / "improvement-review.md").read_text(encoding="utf-8")

    for required in (
        "`unknown`",
        "3 confirmed instances",
        "2 independent work items",
        "1.5×",
        "5 comparable invocations",
        "Human approval",
    ):
        assert required in rubric


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


def test_improve_link_cli_writes_idempotent_private_session_score(monkeypatch, tmp_path, capsys):
    client = FakeReviewClient()
    monkeypatch.setattr(improvement, "_client_from_env", lambda: client)
    monkeypatch.setattr(improvement, "_beads", lambda args: (0, {"id": args[1]}, ""))
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
