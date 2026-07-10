from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib import runner_protocol as rp
from agnt_lib.runner_service import RunnerServiceError, start_runner_service


def request_json(base_url: str, method: str, path: str, *, token: str | None = None, payload: dict | None = None) -> dict:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_until(predicate, *, timeout: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


def test_service_rejects_unauthenticated_requests_and_serves_health_status(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        with pytest.raises(HTTPError) as error:
            request_json(service.base_url, "GET", "/v1/health")
        assert error.value.code == 401

        health = request_json(service.base_url, "GET", "/v1/health", token="secret-token")
        assert health["ok"] is True
        assert health["apiVersion"] == rp.API_VERSION
        assert health["root"] == str(tmp_path.resolve())

        status = request_json(service.base_url, "GET", "/v1/status", token="secret-token")
        assert status["schemaVersion"] == 1
        assert status["running"] is True
        assert status["paused"] is False
        assert status["draining"] is False
        assert status["acceptingNewWork"] is True
        assert status["leases"] == {}
        assert "secret-token" not in json.dumps(status)
        assert status["service"]["tokenPath"] == str(tmp_path / ".pi" / "runner" / "token")
    finally:
        service.stop(force=True)


def test_status_heartbeat_preserves_scheduler_and_operator_control_state(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        rp.update_runner_state(
            tmp_path,
            lambda state: {
                **state,
                "paused": True,
                "pauseReason": "operator",
                "acceptingNewWork": False,
                "scheduler": {"lastTickOutcome": "completed"},
            },
        )

        status = request_json(service.base_url, "GET", "/v1/status", token="secret-token")

        assert status["paused"] is True
        assert status["scheduler"]["lastTickOutcome"] == "completed"
        persisted = rp.read_runner_state(tmp_path)
        assert persisted["pauseReason"] == "operator"
    finally:
        service.stop(force=True)


def test_service_client_and_drain_mutations_preserve_active_scheduler_state(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        rp.update_runner_state(
            tmp_path,
            lambda state: {**state, "activeRuns": [{"bead": "pi-active", "runId": "run-active"}], "attempts": {"pi-ready": {"count": 1}}},
        )

        request_json(service.base_url, "POST", "/v1/leases", token="secret-token", payload={"sessionId": "pi-session", "client": "pi-tui"})
        drained = request_json(service.base_url, "POST", "/v1/drain", token="secret-token", payload={"reason": "operator"})

        assert drained["state"]["draining"] is True
        persisted = rp.read_runner_state(tmp_path)
        assert persisted["activeRuns"][0]["bead"] == "pi-active"
        assert persisted["attempts"]["pi-ready"]["count"] == 1
        assert persisted["leases"]["pi-session"]["client"] == "pi-tui"
    finally:
        service.stop(force=True)


def test_service_writes_metadata_token_state_and_refuses_second_live_owner(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        metadata = rp.load_service_metadata(tmp_path)
        assert metadata["host"] == "127.0.0.1"
        assert metadata["port"] == service.port
        assert metadata["baseUrl"] == service.base_url
        assert metadata["tokenPath"] == str(tmp_path / ".pi" / "runner" / "token")
        assert "token" not in metadata
        assert (tmp_path / ".pi" / "runner" / "token").read_text(encoding="utf-8").strip() == "secret-token"

        state = json.loads((tmp_path / ".pi" / "runner" / "state.json").read_text(encoding="utf-8"))
        assert state["running"] is True
        assert state["heartbeatAt"]

        with pytest.raises(RunnerServiceError) as error:
            start_runner_service(tmp_path, host="127.0.0.1", port=0, token="other-token")
        assert "runner service already active" in str(error.value)
    finally:
        service.stop(force=True)


def test_service_lease_lifecycle_pause_resume_and_drain(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        lease_result = request_json(
            service.base_url,
            "POST",
            "/v1/leases",
            token="secret-token",
            payload={"sessionId": "pi-session-1", "client": "pi-tui", "ttlSeconds": 120},
        )
        assert lease_result["lease"]["leaseId"] == "pi-session-1"
        assert lease_result["state"]["leases"]["pi-session-1"]["client"] == "pi-tui"
        assert lease_result["state"]["acceptingNewWork"] is True

        paused = request_json(service.base_url, "POST", "/v1/pause", token="secret-token", payload={"reason": "maintenance"})
        assert paused["paused"] is True
        assert paused["state"]["pauseReason"] == "maintenance"
        assert paused["state"]["acceptingNewWork"] is False

        resumed = request_json(service.base_url, "POST", "/v1/resume", token="secret-token", payload={})
        assert resumed["paused"] is False
        assert resumed["state"]["acceptingNewWork"] is True

        draining = request_json(service.base_url, "POST", "/v1/drain", token="secret-token", payload={"reason": "operator shutdown"})
        assert draining["draining"] is True
        assert draining["state"]["acceptingNewWork"] is False
        assert wait_until(lambda: not service.thread.is_alive())
    finally:
        service.stop(force=True)


def test_service_start_clears_stale_active_runs_from_previous_owner(tmp_path):
    paths = rp.runner_paths(tmp_path)
    paths["activeDir"].mkdir(parents=True, exist_ok=True)
    bundle = tmp_path / ".pi" / "runs" / "runner-pi-stale-1"
    bundle.mkdir(parents=True)
    (bundle / "result.yaml").write_text(
        json.dumps({
            "schemaVersion": 1,
            "invocationId": "runner-pi-stale-1",
            "status": "needs-human",
            "summary": "Invocation artifact created; worker has not run yet.",
            "evidence": [],
            "artifacts": [],
            "followUps": [],
            "metricsRef": None,
            "sessionRef": None,
            "transcriptRef": None,
            "memorySummaryRef": None,
            "approvalRefs": [],
            "decisionRefs": [],
            "healthChecks": [],
            "closeoutChecks": [],
            "completedAt": None,
        }),
        encoding="utf-8",
    )
    stale_run = {"runId": "runner-pi-stale-1", "bead": "pi-stale", "bundle": str(bundle), "status": "running"}
    paths["statePath"].write_text(json.dumps({"schemaVersion": 1, "running": False, "activeRuns": [stale_run]}), encoding="utf-8")
    (paths["activeDir"] / "runner-pi-stale-1.json").write_text(json.dumps(stale_run), encoding="utf-8")

    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        status = request_json(service.base_url, "GET", "/v1/status", token="secret-token")
        assert status["activeRuns"] == []
        assert not (paths["activeDir"] / "runner-pi-stale-1.json").exists()
        result = json.loads((bundle / "result.yaml").read_text(encoding="utf-8"))
        assert result["status"] == "failed"
        assert "stale active run" in result["summary"]
    finally:
        service.stop(force=True)


def test_scheduler_rechecks_drain_after_active_run_finishes(tmp_path):
    service = start_runner_service(
        tmp_path, host="127.0.0.1", port=0, token="secret-token",
        auto_schedule=True, scheduler_interval=0.02,
    )
    try:
        state = service.httpd.read_state()
        state["activeRuns"] = [{"runId": "runner-active", "bead": "pi-task.1"}]
        service.httpd.write_state(state)
        drained = request_json(service.base_url, "POST", "/v1/drain", token="secret-token", payload={"reason": "mid-flight"})
        assert drained["state"]["activeRuns"] == [{"runId": "runner-active", "bead": "pi-task.1"}]
        assert service.thread.is_alive()
        state = service.httpd.read_state()
        state["activeRuns"] = []
        service.httpd.write_state(state)
        assert wait_until(lambda: not service.thread.is_alive())
    finally:
        service.stop(force=True)


def test_drain_stops_without_waiting_for_client_lease_release(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        request_json(
            service.base_url,
            "POST",
            "/v1/leases",
            token="secret-token",
            payload={"sessionId": "pi-stale-client", "client": "pi-tui"},
        )
        drained = request_json(service.base_url, "POST", "/v1/drain", token="secret-token", payload={"reason": "operator drain"})
        assert drained["draining"] is True
        assert wait_until(lambda: not service.thread.is_alive())
    finally:
        service.stop(force=True)


def test_service_stop_endpoint_is_explicit_and_releases_lock(tmp_path):
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")

    stopped = request_json(service.base_url, "POST", "/v1/stop", token="secret-token", payload={"force": True})
    assert stopped["stopping"] is True
    assert wait_until(lambda: not service.thread.is_alive())
    assert not (tmp_path / ".pi" / "runner" / "lock.json").exists()

    replacement = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="replacement-token")
    replacement.stop(force=True)


def test_service_rejects_overlapping_ticks(monkeypatch, tmp_path):
    from agnt_lib import runner_service

    entered = threading.Event()
    release = threading.Event()

    def blocking_tick(**_kwargs):
        entered.set()
        assert release.wait(timeout=2)
        return {"schemaVersion": 1, "actions": []}

    monkeypatch.setattr(runner_service, "runner_tick", blocking_tick)
    service = start_runner_service(tmp_path, host="127.0.0.1", port=0, token="secret-token")
    try:
        worker = threading.Thread(target=service.httpd.run_tick, kwargs={"dry_run": False, "limit": 1})
        worker.start()
        assert entered.wait(timeout=1)
        assert service.httpd.run_tick(dry_run=False, limit=1) is None
        release.set()
        worker.join(timeout=1)
    finally:
        release.set()
        service.stop(force=True)


def test_service_auto_scheduler_ticks_without_manual_endpoint(monkeypatch, tmp_path):
    calls = []

    def fake_tick(**kwargs):
        calls.append(kwargs)
        return {"schemaVersion": 1, "dryRun": kwargs.get("dry_run"), "actions": [{"bead": "pi-ready.1", "action": "started"}]}

    from agnt_lib import runner_service

    monkeypatch.setattr(runner_service, "runner_tick", fake_tick)

    service = start_runner_service(
        tmp_path,
        host="127.0.0.1",
        port=0,
        token="secret-token",
        auto_schedule=True,
        scheduler_interval=0.05,
        scheduler_limit=1,
    )
    try:
        status = request_json(service.base_url, "GET", "/v1/status", token="secret-token")
        assert status["schedulerEnabled"] is True
        assert status["schedulerAlive"] is True
        assert status["service"]["schedulerEnabled"] is True
        assert wait_until(lambda: len(calls) >= 1)
        assert calls[0]["root"] == tmp_path.resolve()
        assert calls[0]["dry_run"] is False
        assert calls[0]["limit"] == 1
        assert wait_until(lambda: any(event["type"] == "scheduler_tick_completed" for event in rp.read_runner_events(tmp_path)["events"]))
        status = request_json(service.base_url, "GET", "/v1/status", token="secret-token")
        assert status["scheduler"]["lastTickCompletedAt"]
        assert status["scheduler"]["lastActions"] == [{"bead": "pi-ready.1", "action": "started"}]
        completed = next(event for event in rp.read_runner_events(tmp_path)["events"] if event["type"] == "scheduler_tick_completed")
        assert completed["actions"] == [{"bead": "pi-ready.1", "action": "started"}]
    finally:
        service.stop(force=True)


def test_service_scheduler_survives_system_exit_and_records_tick_failure(monkeypatch, tmp_path):
    calls = []

    def fatal_once(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise SystemExit("simulated scheduler fatal exit")
        return {"schemaVersion": 1, "dryRun": kwargs.get("dry_run"), "actions": []}

    from agnt_lib import runner_service

    monkeypatch.setattr(runner_service, "runner_tick", fatal_once)

    service = start_runner_service(
        tmp_path,
        host="127.0.0.1",
        port=0,
        token="secret-token",
        auto_schedule=True,
        scheduler_interval=0.02,
        scheduler_limit=1,
    )
    try:
        assert wait_until(lambda: len(calls) >= 2)
        status = request_json(service.base_url, "GET", "/v1/status", token="secret-token")
        assert status["schedulerAlive"] is True
        events = rp.read_runner_events(tmp_path)["events"]
        assert any(event["type"] == "scheduler_tick_failed" and "simulated scheduler fatal exit" in event["error"] for event in events)
    finally:
        service.stop(force=True)


def test_service_reports_dead_scheduler_as_degraded_and_non_accepting(monkeypatch, tmp_path):
    from agnt_lib import runner_service

    monkeypatch.setattr(runner_service, "runner_tick", lambda **_kwargs: {"schemaVersion": 1, "actions": []})
    service = start_runner_service(
        tmp_path,
        host="127.0.0.1",
        port=0,
        token="secret-token",
        auto_schedule=True,
        scheduler_interval=0.05,
        scheduler_limit=1,
    )
    try:
        service.httpd.scheduler_thread = threading.Thread()
        status = request_json(service.base_url, "GET", "/v1/status", token="secret-token")
        assert status["schedulerAlive"] is False
        assert status["status"] == "degraded"
        assert status["acceptingNewWork"] is False
    finally:
        service.stop(force=True)
