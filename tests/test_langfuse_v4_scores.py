from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"))
from agnt_lib import langfuse

SESSION = "2026-07-26T12-00-00-123Z_fixture"
STAMP = "2026-07-26T12:00:00.123Z"


class Client(langfuse.LangfuseClient):
    def __init__(self, replies):
        super().__init__("http://127.0.0.1", "fixture", "fixture")
        self.replies = iter(replies)
        self.calls = []

    def _request(self, method, path, body=None, params=None):
        self.calls.append((method, path, body, params))
        result = next(self.replies)
        if isinstance(result, Exception):
            raise result
        return result


def write(client, value="reviewed", **extra):
    return client.put_session_score(
        score_id="stable", session_id=SESSION, name="review_status", value=value,
        metadata={"reviewId": "fixture"}, **extra,
    )


def existing(**extra):
    return {
        "id": "stable", "name": "review_status", "source": "API", "timestamp": STAMP,
        "subject": {"kind": "session", "id": SESSION}, **extra,
    }


def test_bare_array_scores_use_stable_id_and_timestamp_across_updates():
    client = Client([{"data": [], "meta": {}}, {"message": "Accepted"}, {"message": "Accepted"}])
    write(client)
    write(client, "needs-human")
    assert [call[:2] for call in client.calls] == [
        ("GET", "/api/public/v3/scores"), ("POST", "/api/public/scores"), ("POST", "/api/public/scores"),
    ]
    assert client.calls[0][3] == {"id": "stable", "fields": "subject", "limit": 2}
    for call in client.calls[1:]:
        assert isinstance(call[2], list) and len(call[2]) == 1
        assert call[2][0]["id"] == "stable"
        assert call[2][0]["timestamp"] == STAMP
    assert [call[2][0]["value"] for call in client.calls[1:]] == ["reviewed", "needs-human"]


def test_existing_score_reuses_original_timestamp_not_session_start():
    original = "2026-07-27T13:01:02.456Z"
    client = Client([{"data": [existing(timestamp=original)], "meta": {}}, {"message": "Accepted"}])
    write(client)
    assert client.calls[1][2][0]["timestamp"] == original


def test_transport_retry_keeps_the_same_score_timestamp():
    client = Client([{"data": [], "meta": {}}, langfuse.LangfuseError("transport failed"), {"message": "Accepted"}])
    with pytest.raises(langfuse.LangfuseError):
        write(client)
    write(client)
    assert client.calls[1][2] == client.calls[2][2]
    assert len(client.calls) == 3


@pytest.mark.parametrize("payload", [
    {"data": [existing(), existing(timestamp="2026-07-27T12:00:00Z")], "meta": {}},
    {"data": [], "meta": {"cursor": "more"}},
    {"data": []},
    {"data": [existing(timestamp="bad")], "meta": {}},
    {"data": [existing(timestamp="2026-07-26")], "meta": {}},
    {"data": [existing(id="other")], "meta": {}},
    {"data": [existing(source="ANNOTATION")], "meta": {}},
    {"data": [existing(subject={"kind": "session", "id": "other"})], "meta": {}},
    {"data": [existing(name="other")], "meta": {}},
])
def test_ambiguous_or_mismatched_score_identity_never_writes(payload):
    client = Client([payload])
    with pytest.raises(langfuse.LangfuseError):
        write(client)
    assert [call[0] for call in client.calls] == ["GET"]


@pytest.mark.parametrize("response", [
    {"accepted": 0, "rejected": 1, "errors": [{"message": "private-error-sentinel"}]},
    {"accepted": 1, "rejected": 1, "errors": []},
    {"accepted": True, "rejected": 0, "errors": []},
    {"accepted": 1, "rejected": 0},
    {"message": "Accepted", "rejected": 1},
    {"id": "stable"},
])
def test_partial_rejection_and_invalid_ack_are_explicit_without_automatic_replay(response):
    client = Client([{"data": [], "meta": {}}, response])
    with pytest.raises(langfuse.LangfuseError) as caught:
        write(client)
    assert "private-error-sentinel" not in str(caught.value)
    assert len(client.calls) == 2


def test_full_acceptance_counts_preserve_zero_score():
    client = Client([{"data": [], "meta": {}}, {"accepted": 1, "rejected": 0, "errors": []}])
    write(client, 0, data_type="NUMERIC")
    assert client.calls[1][2][0]["value"] == 0


def test_opaque_session_requires_explicit_stable_timestamp_for_new_score():
    client = Client([{"data": [], "meta": {}}])
    with pytest.raises(langfuse.LangfuseError, match="timestamp"):
        client.put_session_score(score_id="stable", session_id="opaque", name="status", value="done")
    assert len(client.calls) == 1


def test_explicit_timestamp_supports_opaque_sessions():
    client = Client([{"data": [], "meta": {}}, {"message": "Accepted"}])
    client.put_session_score(score_id="stable", session_id="opaque", name="status", value="done", timestamp=STAMP)
    assert client.calls[1][2][0]["timestamp"] == STAMP


def test_custom_rest_adapter_identifies_itself_without_claiming_official_python_sdk():
    client = Client([])
    headers = {key.lower(): value for key, value in client.headers.items()}
    assert headers["x-langfuse-sdk-name"] == "pi-agnt-rest"
    assert headers["x-langfuse-sdk-version"] == "1.0.0"
    assert headers["x-langfuse-public-key"] == "fixture"


@pytest.mark.parametrize("phase", ["lookup", "acknowledgement"])
def test_nonobject_responses_are_sanitized_protocol_errors(phase):
    replies = [[]] if phase == "lookup" else [{"data": [], "meta": {}}, []]
    client = Client(replies)
    with pytest.raises(langfuse.LangfuseError):
        write(client)
    assert len(client.calls) == (1 if phase == "lookup" else 2)


def test_timestamp_conflict_never_posts():
    client = Client([{"data": [existing()], "meta": {}}])
    with pytest.raises(langfuse.LangfuseError, match="timestamp"):
        write(client, timestamp="2026-07-27T00:00:00Z")
    assert len(client.calls) == 1


def test_oversized_score_never_posts():
    client = Client([{"data": [], "meta": {}}])
    with pytest.raises(langfuse.LangfuseError, match="byte ceiling"):
        write(client, "x" * 3_000_000)
    assert len(client.calls) == 1


def test_uuid7_and_legacy_session_names_share_exact_millisecond_start_time():
    import uuid
    from datetime import datetime, timezone
    milliseconds = int(datetime(2026, 7, 26, 12, tzinfo=timezone.utc).timestamp()) * 1000 + 123
    identifier = str(uuid.UUID(int=(milliseconds << 80) | (7 << 76) | (2 << 62) | 42))
    client = Client([{"data": [], "meta": {}}, {"message": "Accepted"}])
    client.put_session_score(score_id="stable", session_id=identifier, name="status", value="done")
    assert client.calls[1][2][0]["timestamp"] == STAMP


def test_new_clients_keep_timestamp_stable_before_new_score_visibility():
    first = Client([{"data": [], "meta": {}}, {"message": "Accepted"}])
    second = Client([{"data": [], "meta": {}}, {"message": "Accepted"}])
    write(first)
    write(second)
    assert first.calls[1][2] == second.calls[1][2]


@pytest.mark.parametrize(("status", "reply", "accepted"), [
    (202, {"message": "Accepted"}, True),
    (207, {"accepted": 1, "rejected": 0, "errors": []}, True),
    (207, {"message": "Accepted"}, False),
])
def test_actual_urllib_score_wire_preserves_prefix_array_identity_and_headers(status, reply, accepted):
    import base64
    import json
    import threading
    import urllib.parse
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, body):
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            requests.append((self.command, self.path, dict(self.headers), None))
            self.reply(200, {"data": [], "meta": {}})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.command, self.path, dict(self.headers), body))
            self.reply(status, reply)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        client = langfuse.LangfuseClient(f"http://127.0.0.1:{server.server_port}/langfuse", "fixture", "fixture")
        if accepted:
            write(client)
        else:
            with pytest.raises(langfuse.LangfuseError, match="acknowledgement"):
                write(client)
        assert [request[0] for request in requests] == ["GET", "POST"]
        lookup = urllib.parse.urlsplit(requests[0][1])
        assert lookup.path == "/langfuse/api/public/v3/scores"
        assert urllib.parse.parse_qs(lookup.query) == {"id": ["stable"], "fields": ["subject"], "limit": ["2"]}
        assert requests[1][1] == "/langfuse/api/public/scores"
        assert requests[1][3][0]["timestamp"] == STAMP
        for request in requests:
            headers = {key.lower(): value for key, value in request[2].items()}
            assert headers["authorization"] == "Basic " + base64.b64encode(b"fixture:fixture").decode()
            assert headers["x-langfuse-sdk-name"] == "pi-agnt-rest"
            assert headers["x-langfuse-sdk-version"] == "1.0.0"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
