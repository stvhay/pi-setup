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


def test_trace_reads_are_time_bounded_and_paginated():
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
        self.score_sessions = []
        self.observation_traces = []

    def list_traces(self, **kwargs):
        self.trace_limits.append(kwargs["limit"])
        return self.traces[: kwargs["limit"]]

    def list_scores(self, **kwargs):
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

    assert summary == {
        "schemaVersion": 1,
        "status": "ok",
        "scannedTraces": 2,
        "candidateSessions": 2,
        "eligibleSessions": 1,
        "reviewedSessionsSkipped": 1,
        "unlinkedSessions": 1,
        "reportWritten": False,
        "reportPath": None,
    }
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

    assert client.marker_limit == 100
    assert summary["reviewedSessionsSkipped"] == 1
    assert packet["sessions"] == []


def test_scan_expands_bounded_trace_window_past_reviewed_prefix(tmp_path):
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

    assert client.trace_limits == [10, 20]
    assert summary["eligibleSessions"] == 1
    assert packet["sessions"][0]["sessionId"] == "eligible-session"


def test_scan_marks_truncated_observations_as_capture_gap(tmp_path):
    observations = [{"id": str(index), "type": "TOOL", "metadata": {}} for index in range(501)]
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

    assert "observation-limit" in packet["sessions"][0]["features"]["captureGaps"]


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


def test_review_decisions_accept_strict_private_schema():
    decisions = _review_decisions()

    validated = improvement.validate_decisions(_review_packet(), decisions)

    assert validated == decisions


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
    for private in ("private-session", "private-trace", "private system prompt", "private user content"):
        assert private not in output
