from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import pytest

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib.runner_client import RunnerClient, RunnerClientError, daemon_status
from agnt_lib.runner_service import start_runner_service


def test_runner_client_reports_missing_service_with_suggested_action(tmp_path):
    client = RunnerClient(tmp_path)

    with pytest.raises(RunnerClientError) as error:
        client.status()

    payload = error.value.payload
    assert payload["status"] == "not-running"
    assert payload["suggestedAction"] == "agnt work daemon start --json"
    assert payload["root"] == str(tmp_path.resolve())

    status = daemon_status(root=tmp_path)
    assert status["running"] is False
    assert status["connected"] is False
    assert status["suggestedAction"] == "agnt work daemon start --json"


def test_runner_client_uses_service_metadata_token_and_json_methods(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        client = RunnerClient(tmp_path)
        status = client.status()
        assert status["running"] is True
        assert "secret-token" not in json.dumps(status)

        paused = client.pause(reason="maintenance")
        assert paused["paused"] is True
        assert paused["state"]["pauseReason"] == "maintenance"

        resumed = client.resume()
        assert resumed["paused"] is False

        drain = client.drain(reason="test drain")
        assert drain["draining"] is True
    finally:
        service.stop(force=True)


def test_runner_client_sends_bearer_auth_and_payload(monkeypatch, tmp_path):
    token_path = tmp_path / ".pi" / "runner" / "token"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("secret-token\n", encoding="utf-8")
    service_path = tmp_path / ".pi" / "runner" / "service.json"
    service_path.write_text(
        json.dumps({"schemaVersion": 1, "apiVersion": 1, "baseUrl": "http://127.0.0.1:54321", "tokenPath": str(token_path)}) + "\n",
        encoding="utf-8",
    )
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return json.dumps({"ok": True}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return Response()

    from agnt_lib import runner_client

    monkeypatch.setattr(runner_client, "urlopen", fake_urlopen)

    result = RunnerClient(tmp_path).tick(dry_run=True, limit=2)

    assert result == {"ok": True}
    assert captured["url"] == "http://127.0.0.1:54321/v1/tick"
    assert captured["method"] == "POST"
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert json.loads(captured["body"]) == {"dryRun": True, "limit": 2}


def test_runner_client_reports_timeout_without_claiming_service_is_not_running(monkeypatch, tmp_path):
    token_path = tmp_path / ".pi" / "runner" / "token"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("secret-token\n", encoding="utf-8")
    (tmp_path / ".pi" / "runner" / "service.json").write_text(
        json.dumps({"schemaVersion": 1, "apiVersion": 1, "baseUrl": "http://127.0.0.1:54321", "tokenPath": str(token_path)}) + "\n",
        encoding="utf-8",
    )

    from agnt_lib import runner_client

    def fake_urlopen(_request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(runner_client, "urlopen", fake_urlopen)

    with pytest.raises(RunnerClientError) as error:
        RunnerClient(tmp_path).tick(dry_run=False, limit=1)

    payload = error.value.payload
    assert payload["status"] == "timeout"
    assert payload["running"] is None
    assert payload["connected"] is None
    assert payload["suggestedAction"] == "agnt work runner status --json"


def test_work_daemon_cli_uses_lifecycle_functions(agnt, capsys):
    calls = []

    with patch.dict(
        agnt.cmd_work.__globals__,
        {
            "daemon_status": lambda root=None: {"schemaVersion": 1, "running": False, "status": "not-running"},
            "daemon_start": lambda **kwargs: calls.append(("start", kwargs)) or {"schemaVersion": 1, "started": True},
            "daemon_stop": lambda **kwargs: calls.append(("stop", kwargs)) or {"schemaVersion": 1, "stopping": True},
        },
    ):
        assert agnt.cmd_work(["daemon", "status", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["running"] is False
        assert agnt.cmd_work(["daemon", "start", "--json", "--concurrency", "2", "--interval", "1.5"]) == 0
        assert agnt.cmd_work(["daemon", "stop", "--json", "--drain"]) == 0

    assert calls[0][0] == "start"
    assert calls[0][1]["concurrency"] == 2
    assert calls[0][1]["interval"] == 1.5
    assert calls[1][0] == "stop"
    assert calls[1][1]["drain"] is True
