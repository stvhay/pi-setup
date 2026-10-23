from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"))
from agnt_lib import improvement, langfuse

FROM = "2026-07-26T00:00:00Z"
TO = "2026-07-27T00:00:00Z"


def observation(identifier, trace_id="trace", parent=None, **extra):
    return {
        "id": identifier, "traceId": trace_id, "parentObservationId": parent,
        "startTime": "2026-07-26T12:00:00Z", "endTime": None, "projectId": "fixture",
        "type": "SPAN", "name": "agent", "traceName": "pi-agent", "sessionId": "session",
        "modelId": None, "inputPrice": None, "outputPrice": None, "totalPrice": None,
        **extra,
    }


class Client(langfuse.LangfuseClient):
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def _request(self, method, path, body=None, params=None):
        self.calls.append((method, path, params))
        return next(self.pages)


def discover(client, **kwargs):
    return client.list_traces_with_metadata(from_timestamp=FROM, to_timestamp=TO, **kwargs)


def observations(client, **kwargs):
    return client.list_observations(from_start_time=FROM, to_start_time=TO, limit=4, **kwargs)


def test_observations_cursor_fields_and_decode_once():
    client = Client([
        {"data": [observation("a", input='{"prompt":true}', output=json.dumps('{"literal":true}'), usageDetails={"cache_read_input_tokens": 0})], "meta": {"cursor": "next"}},
        {"data": [observation("b", input=None)], "meta": {}},
    ])
    rows = observations(client, trace_id="trace", page_size=1)
    assert len(rows) == 2
    assert rows[0]["input"] == {"prompt": True}
    assert rows[0]["output"] == '{"literal":true}'
    assert rows[0]["usageDetails"] == {"cache_read_input_tokens": 0}
    assert rows[1]["input"] is None
    assert "output" not in rows[1] and "usageDetails" not in rows[1]
    assert client.calls[1][2]["cursor"] == "next"
    for method, path, params in client.calls:
        assert method == "GET" and path == "/api/public/v2/observations"
        assert params["fromStartTime"] == FROM and params["toStartTime"] == TO
        assert params["traceId"] == "trace"
        assert {"core", "basic", "io", "metadata", "usage", "model"} <= set(params["fields"].split(","))
        assert "page" not in params and "parseIoAsJson" not in params


def test_trace_groups_cross_pages_and_never_promote_child_io():
    client = Client([
        {"data": [observation("child", parent="root", input='"child-private"')], "meta": {"cursor": "next"}},
        {"data": [observation("root", input='{"root":true}', metadata={"owner": "root"})], "meta": {}},
    ])
    result = discover(client, page_size=1)
    assert result["complete"] is True
    assert result["scanned"] == 1 and result["observationsScanned"] == 2
    assert result["totalAvailable"] is None
    assert len(result["traces"]) == 1
    root = result["traces"][0]
    assert root["id"] == "trace" and root["name"] == "pi-agent"
    assert root["timestamp"] == "2026-07-26T12:00:00Z"
    assert root["input"] == {"root": True} and root["metadata"] == {"owner": "root"}
    assert "child-private" not in json.dumps(result)
    assert "trace_context" in client.calls[0][2]["fields"].split(",")


@pytest.mark.parametrize("trace_name", ["pi-agent", "subagent-result"])
def test_child_only_group_is_partial_and_cannot_be_reviewed_as_settled(trace_name):
    client = Client([{"data": [observation("child", parent="missing", input='"private"', traceName=trace_name)], "meta": {}}])
    result = discover(client)
    assert result["complete"] is False
    assert result["continuation"]["hasMore"] is False
    assert "timestamp" not in result["traces"][0] and "input" not in result["traces"][0]
    assert {"scope": "traces", "traceId": "trace", "code": "root-unavailable"} in result["gaps"]

    class DiscoveryOnly:
        def list_traces_with_metadata(self, **kwargs):
            return result

    eligibility = improvement._review_eligibility(
        DiscoveryOnly(), since=FROM, until=TO, cohort_until=TO, max_traces=10,
    )
    assert eligibility[2] == {}  # no eligible session grouping, no score/network reads


def test_scan_budget_counts_observations_not_unique_traces():
    client = Client([{"data": [observation("child", parent="root")], "meta": {"cursor": "more"}}])
    result = discover(client, max_traces=1)
    assert len(client.calls) == 1
    assert result["complete"] is False
    assert result["observationsScanned"] == 1 and result["scanned"] == 1
    assert result["continuation"]["nextCursor"] == "more"
    assert result["continuation"]["nextPage"] is None
    assert result["continuation"]["reason"] == "max-observations"


@pytest.mark.parametrize("cursor", [False, 0, -1, {}, [], "", "x" * 8193], ids=["false", "zero", "negative", "object", "array", "empty", "oversize"])
def test_invalid_cursor_never_silently_returns_a_complete_short_list(cursor):
    page = {"data": [observation("root")], "meta": {"cursor": cursor}}
    with pytest.raises(langfuse.LangfuseError, match="malformed-metadata"):
        observations(Client([page]))
    result = discover(Client([page]))
    assert result["complete"] is False
    assert result["continuation"]["reason"] == "malformed-metadata"


@pytest.mark.parametrize("pages,reason", [
    ([{"data": [observation("a")], "meta": {"cursor": "same"}}, {"data": [observation("b")], "meta": {"cursor": "same"}}], "non-advancing-cursor"),
    ([{"data": [observation("a")], "meta": {"cursor": "a"}}, {"data": [observation("a")], "meta": {"cursor": "b"}}], "non-advancing-page"),
    ([{"data": [], "meta": {"cursor": "a"}}], "incomplete-response"),
    ([{"data": None, "meta": {}}], "malformed-response"),
    ([{"data": [], "meta": None}], "malformed-response"),
])
def test_nonadvancing_or_malformed_pages_fail_closed(pages, reason):
    with pytest.raises(langfuse.LangfuseError, match=reason):
        observations(Client(pages))
    result = discover(Client(pages))
    assert result["complete"] is False
    assert result["continuation"]["reason"] == reason


def test_span_identity_is_trace_and_span_pair():
    result = discover(Client([{"data": [observation("same", "a"), observation("same", "b")], "meta": {}}]))
    assert result["complete"] is True
    assert [row["id"] for row in result["traces"]] == ["a", "b"]


def test_logical_root_and_ambiguous_roots():
    result = discover(Client([{"data": [observation("app", parent="external", isRootObservation=True, input='"app"')], "meta": {}}]))
    assert result["complete"] is True and result["traces"][0]["input"] == "app"
    result = discover(Client([{"data": [observation("a", input='"a"'), observation("b", input='"b"')], "meta": {}}]))
    assert result["complete"] is False and "input" not in result["traces"][0]
    assert result["gaps"][0]["code"] == "ambiguous-root"


def test_conflicting_child_sessions_cannot_invent_join():
    result = discover(Client([{"data": [
        observation("a", parent="root", sessionId="a"), observation("b", parent="root", sessionId="b"),
    ], "meta": {}}]))
    assert "sessionId" not in result["traces"][0]
    assert any(gap["code"] == "conflicting-trace-context" for gap in result["gaps"])


def test_observation_counts_are_not_trace_totals():
    result = discover(Client([{"data": [observation("root")], "meta": {"totalItems": 123, "totalPages": 999}}]))
    assert result["totalAvailable"] is None
    assert result["complete"] is True


def test_overrun_does_not_publish_a_cursor_that_skips_omitted_rows():
    result = discover(Client([{"data": [observation("a", "a"), observation("b", "b")], "meta": {"cursor": "skips"}}]), max_traces=1)
    assert result["scanned"] == 1 and result["complete"] is False
    assert result["continuation"]["nextCursor"] is None
    assert result["continuation"]["reason"] == "response-overrun"


def test_trace_filter_rejects_foreign_trace_rows():
    with pytest.raises(langfuse.LangfuseError, match="unexpected-trace"):
        observations(Client([{"data": [observation("root", "foreign")], "meta": {}}]), trace_id="wanted")


@pytest.mark.parametrize("timestamp", [None, "not-a-time", "2026-07-26"])
def test_invalid_root_time_is_not_settled_evidence(timestamp):
    result = discover(Client([{"data": [observation("root", startTime=timestamp)], "meta": {}}]))
    assert result["complete"] is False
    assert "timestamp" not in result["traces"][0]
    assert result["gaps"][0]["code"] == "root-time-unavailable"

    class DiscoveryOnly:
        def list_traces_with_metadata(self, **kwargs):
            return result

    eligibility = improvement._review_eligibility(
        DiscoveryOnly(), since=FROM, until=TO, cohort_until=TO, max_traces=10,
    )
    assert eligibility[2] == {}


def test_real_http_reader_preserves_base_prefix_and_query_contract(monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from urllib.parse import parse_qs, urlsplit
    from urllib.request import ProxyHandler, build_opener

    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = json.dumps({"data": [observation("root", input='{"local":true}')], "meta": {}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(langfuse.urllib.request, "urlopen", build_opener(ProxyHandler({})).open)
    try:
        client = langfuse.LangfuseClient(f"http://127.0.0.1:{server.server_port}/langfuse", "fixture", "fixture")
        result = discover(client, max_traces=2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert result["complete"] is True and result["traces"][0]["input"] == {"local": True}
    assert len(requests) == 1
    url = urlsplit(requests[0])
    assert url.path == "/langfuse/api/public/v2/observations"
    params = parse_qs(url.query)
    assert params["fromStartTime"] == [FROM] and params["toStartTime"] == [TO]
    assert params["limit"] == ["2"] and "page" not in params
    assert "trace_context" in params["fields"][0].split(",")
