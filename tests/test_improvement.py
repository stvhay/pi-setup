from __future__ import annotations

import io
import json
import stat
import sys
import urllib.error
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


def test_improvement_dir_uses_private_default_and_environment_override(monkeypatch, tmp_path):
    monkeypatch.delenv("AGNT_IMPROVEMENT_DIR", raising=False)
    assert improvement.improvement_dir() == Path.home() / ".pi" / "improvement"

    override = tmp_path / "override"
    monkeypatch.setenv("AGNT_IMPROVEMENT_DIR", str(override))
    assert improvement.improvement_dir() == override


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
