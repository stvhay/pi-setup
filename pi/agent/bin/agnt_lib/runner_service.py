from __future__ import annotations

import json
import os
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, unquote, urlparse

from . import runner_protocol as protocol
from .runner import acquire_runner_lock, release_runner_lock, runner_pause, runner_resume, runner_status, runner_tick
from .runs import update_run_result

SERVICE_OWNER = "agnt-runner-service"


class RunnerServiceError(RuntimeError):
    """Raised when the project-local runner service cannot start."""


class _RunnerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, *, root: Path, token: str, lock_owner: str, scheduler_enabled: bool = False):
        super().__init__(server_address, handler_class)
        self.root = protocol.normalize_root(root)
        self.token = token
        self.lock_owner = lock_owner
        self.scheduler_enabled = scheduler_enabled
        self.scheduler_thread: threading.Thread | None = None
        self._shutdown_requested = False
        self._state_lock = threading.RLock()
        self._tick_lock = threading.Lock()
        self._cleanup_lock = threading.Lock()
        self._cleaned_up = False

    @property
    def host(self) -> str:
        return str(self.server_address[0])

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def paths(self) -> Dict[str, Path]:
        return protocol.runner_paths(self.root)

    def read_state(self) -> Dict[str, Any]:
        with self._state_lock:
            state = protocol.read_runner_state(self.root)
            state.setdefault("running", True)
            state.setdefault("root", str(self.root))
            return state

    def write_state(self, state: Dict[str, Any], *, heartbeat: bool = True) -> Dict[str, Any]:
        with self._state_lock:
            data = protocol.normalize_runner_state(state)
            data["root"] = str(self.root)
            data["running"] = bool(data.get("running", True))
            data["acceptingNewWork"] = bool(data.get("running")) and not bool(data.get("paused")) and not bool(data.get("draining"))
            if heartbeat:
                data["heartbeatAt"] = protocol.utc_now()
            data["updatedAt"] = protocol.utc_now()
            return protocol.write_runner_state(self.root, data)

    def mutate_state(self, update, *, heartbeat: bool = True) -> Dict[str, Any]:
        """Apply a service-owned state transition to the latest document."""
        with self._state_lock:
            def apply(current: Dict[str, Any]) -> Dict[str, Any]:
                data = protocol.normalize_runner_state(update(current))
                data["root"] = str(self.root)
                data["running"] = bool(data.get("running", True))
                data["acceptingNewWork"] = bool(data["running"]) and not bool(data.get("paused")) and not bool(data.get("draining"))
                if heartbeat:
                    data["heartbeatAt"] = protocol.utc_now()
                data["updatedAt"] = protocol.utc_now()
                return data

            return protocol.update_runner_state(self.root, apply)

    def run_tick(self, *, dry_run: bool, limit: int) -> Dict[str, Any] | None:
        """Run at most one scheduler or HTTP tick at a time."""
        if not self._tick_lock.acquire(blocking=False):
            return None
        try:
            return runner_tick(root=self.root, dry_run=dry_run, limit=limit)
        finally:
            self._tick_lock.release()

    def heartbeat(self) -> Dict[str, Any]:
        # Status polling updates only its own heartbeat field against the
        # latest state; it must never replay a stale full-state snapshot.
        return self.mutate_state(lambda state: state, heartbeat=True)

    def record_scheduler_tick(self, phase: str, *, error: str | None = None, actions: list[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        # Apply scheduler visibility to the latest state rather than replaying
        # a pre-tick snapshot over pause, drain, or active-run transitions.
        def update(state: Dict[str, Any]) -> Dict[str, Any]:
            scheduler = dict(state.get("scheduler") or {})
            timestamp = protocol.utc_now()
            if phase == "started":
                scheduler["lastTickStartedAt"] = timestamp
            else:
                scheduler["lastTickCompletedAt"] = timestamp
                scheduler["lastTickOutcome"] = phase
            if error:
                scheduler["lastTickError"] = error
            elif phase == "completed":
                scheduler.pop("lastTickError", None)
                scheduler["lastActions"] = actions or []
            state["scheduler"] = scheduler
            return state

        return self.mutate_state(update)

    def status_payload(self) -> Dict[str, Any]:
        state = self.heartbeat()
        service_metadata = protocol.redact_service_metadata(protocol.load_service_metadata(self.root))
        lock_status = runner_status(self.root)
        scheduler_alive = self.scheduler_thread.is_alive() if self.scheduler_enabled and self.scheduler_thread else False
        accepting_new_work = bool(state.get("acceptingNewWork")) and (not self.scheduler_enabled or scheduler_alive)
        status = "draining" if state.get("draining") else "paused" if state.get("paused") else "running"
        if self.scheduler_enabled and not scheduler_alive:
            status = "degraded"
        return {
            "schemaVersion": protocol.SCHEMA_VERSION,
            "apiVersion": protocol.API_VERSION,
            "status": status,
            "running": bool(lock_status.get("running")),
            "paused": bool(state.get("paused")),
            "draining": bool(state.get("draining")),
            "acceptingNewWork": accepting_new_work,
            "schedulerEnabled": self.scheduler_enabled,
            "schedulerAlive": scheduler_alive,
            "scheduler": state.get("scheduler") or {},
            "root": str(self.root),
            "heartbeatAt": state.get("heartbeatAt"),
            "updatedAt": state.get("updatedAt"),
            "leases": state.get("leases") or {},
            "activeRuns": state.get("activeRuns") or [],
            "budget": state.get("budget") or dict(protocol.DEFAULT_BUDGET),
            "service": {**service_metadata, "schedulerEnabled": self.scheduler_enabled},
            "lock": lock_status.get("lock"),
        }

    def should_stop_after_state(self, state: Dict[str, Any]) -> bool:
        # Client presence is informational only: a stale/disconnected Pi session
        # must never delay an explicit operator drain of autonomous work.
        return bool(state.get("draining")) and not bool(state.get("activeRuns"))

    def request_service_shutdown(self, *, force: bool = False) -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        def request_stop(state: Dict[str, Any]) -> Dict[str, Any]:
            state["draining"] = True
            if force:
                state["forceStopRequested"] = True
            state["stopRequestedAt"] = protocol.utc_now()
            return state

        self.mutate_state(request_stop)
        threading.Thread(target=self.shutdown, name="agnt-runner-service-shutdown", daemon=True).start()

    def maybe_shutdown_when_drained(self, state: Dict[str, Any]) -> None:
        if self.should_stop_after_state(state):
            self.request_service_shutdown(force=False)

    def cleanup(self) -> None:
        with self._cleanup_lock:
            if self._cleaned_up:
                return
            self._cleaned_up = True
            def mark_stopped(state: Dict[str, Any]) -> Dict[str, Any]:
                state["running"] = False
                state["stoppedAt"] = protocol.utc_now()
                return state

            self.mutate_state(mark_stopped, heartbeat=False)
            protocol.append_runner_event(self.root, {"type": "service_stopped", "baseUrl": self.base_url})
            release_runner_lock(self.root, owner=self.lock_owner)


class _Handler(BaseHTTPRequestHandler):
    server: _RunnerHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - inherited API name
        return

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {self.server.token}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send_json(401, {"schemaVersion": protocol.SCHEMA_VERSION, "error": "unauthorized"})
        return False

    def _json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            parsed = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def do_GET(self) -> None:
        if not self._require_auth():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/v1/health":
            self.server.heartbeat()
            self._send_json(
                200,
                {
                    "schemaVersion": protocol.SCHEMA_VERSION,
                    "apiVersion": protocol.API_VERSION,
                    "ok": True,
                    "root": str(self.server.root),
                    "pid": os.getpid(),
                    "baseUrl": self.server.base_url,
                },
            )
            return
        if parsed.path == "/v1/status":
            self._send_json(200, self.server.status_payload())
            return
        if parsed.path == "/v1/events":
            query = parse_qs(parsed.query)
            since = int((query.get("since") or [0])[0] or 0)
            self._send_json(200, protocol.read_runner_events(self.server.root, since=since))
            return
        self._send_json(404, {"schemaVersion": protocol.SCHEMA_VERSION, "error": "not found"})

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        parsed = urlparse(self.path)
        body = self._json_body()
        if parsed.path == "/v1/leases":
            lease = protocol.normalize_lease(body)

            def attach_lease(state: Dict[str, Any]) -> Dict[str, Any]:
                leases = dict(state.get("leases") or {})
                leases[lease["leaseId"]] = lease
                state["leases"] = leases
                return state

            saved = self.server.mutate_state(attach_lease)
            protocol.append_runner_event(self.server.root, {"type": "lease_attached", "leaseId": lease["leaseId"]})
            self._send_json(200, {"schemaVersion": protocol.SCHEMA_VERSION, "lease": lease, "state": saved})
            return
        if parsed.path == "/v1/pause":
            runner_pause(self.server.root, reason=str(body.get("reason") or "paused by operator"))
            state = self.server.mutate_state(lambda current: {**current, "running": True})
            protocol.append_runner_event(self.server.root, {"type": "paused", "reason": state.get("pauseReason")})
            self._send_json(200, {"schemaVersion": protocol.SCHEMA_VERSION, "paused": True, "state": state})
            return
        if parsed.path == "/v1/resume":
            runner_resume(self.server.root)
            state = self.server.mutate_state(lambda current: {**current, "running": True})
            protocol.append_runner_event(self.server.root, {"type": "resumed"})
            self._send_json(200, {"schemaVersion": protocol.SCHEMA_VERSION, "paused": False, "state": state})
            return
        if parsed.path == "/v1/drain":
            def request_drain(state: Dict[str, Any]) -> Dict[str, Any]:
                state["draining"] = True
                state["drainReason"] = str(body.get("reason") or "drain requested")
                state["drainRequestedAt"] = protocol.utc_now()
                return state

            saved = self.server.mutate_state(request_drain)
            protocol.append_runner_event(self.server.root, {"type": "drain_requested", "reason": saved.get("drainReason")})
            self._send_json(200, {"schemaVersion": protocol.SCHEMA_VERSION, "draining": True, "state": saved})
            self.server.maybe_shutdown_when_drained(saved)
            return
        if parsed.path == "/v1/stop":
            force = bool(body.get("force"))
            protocol.append_runner_event(self.server.root, {"type": "stop_requested", "force": force})
            self._send_json(200, {"schemaVersion": protocol.SCHEMA_VERSION, "stopping": True, "force": force})
            self.server.request_service_shutdown(force=force)
            return
        if parsed.path == "/v1/tick":
            dry_run = bool(body.get("dryRun", True))
            limit = int(body.get("limit") or 1)
            result = self.server.run_tick(dry_run=dry_run, limit=limit)
            if result is None:
                self._send_json(409, {"schemaVersion": protocol.SCHEMA_VERSION, "error": "runner tick already in progress"})
            else:
                self._send_json(200, result)
            return
        self._send_json(404, {"schemaVersion": protocol.SCHEMA_VERSION, "error": "not found"})

    def do_DELETE(self) -> None:
        if not self._require_auth():
            return
        parsed = urlparse(self.path)
        prefix = "/v1/leases/"
        if parsed.path.startswith(prefix):
            lease_id = unquote(parsed.path[len(prefix) :])
            released = False

            def detach_lease(state: Dict[str, Any]) -> Dict[str, Any]:
                nonlocal released
                leases = dict(state.get("leases") or {})
                released = lease_id in leases
                leases.pop(lease_id, None)
                state["leases"] = leases
                return state

            saved = self.server.mutate_state(detach_lease)
            protocol.append_runner_event(self.server.root, {"type": "lease_released", "leaseId": lease_id, "released": released})
            self._send_json(200, {"schemaVersion": protocol.SCHEMA_VERSION, "released": released, "state": saved})
            self.server.maybe_shutdown_when_drained(saved)
            return
        self._send_json(404, {"schemaVersion": protocol.SCHEMA_VERSION, "error": "not found"})


@dataclass
class RunnerServiceHandle:
    root: Path
    host: str
    port: int
    token: str
    httpd: _RunnerHTTPServer
    thread: threading.Thread
    scheduler_thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def stop(self, *, force: bool = False, timeout: float = 2.0) -> None:
        if self.thread.is_alive():
            self.httpd.request_service_shutdown(force=force)
            self.thread.join(timeout=timeout)
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=timeout)
        self.httpd.cleanup()
        self.httpd.server_close()


def _serve(httpd: _RunnerHTTPServer) -> None:
    try:
        httpd.serve_forever(poll_interval=0.05)
    finally:
        httpd.cleanup()
        httpd.server_close()


def _clear_stale_active_runs(root: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    active = [run for run in state.get("activeRuns") or [] if isinstance(run, dict)]
    if not active:
        return state
    paths = protocol.runner_paths(root)
    for run in active:
        run_id = str(run.get("runId") or "")
        bundle = run.get("bundle")
        if bundle:
            result_path = Path(str(bundle)) / "result.yaml"
            if result_path.is_file():
                try:
                    update_run_result(
                        Path(str(bundle)),
                        status="failed",
                        summary="Cleared stale active run from previous runner service owner.",
                        evidence=["stale active run cleared during runner service startup"],
                        completed=True,
                    )
                except SystemExit:
                    pass
        if run_id:
            try:
                (paths["activeDir"] / f"{run_id}.json").unlink()
            except FileNotFoundError:
                pass
    state = dict(state)
    state["activeRuns"] = []
    return state


def _scheduler_action_summary(result: Any) -> list[Dict[str, Any]]:
    if not isinstance(result, dict) or not isinstance(result.get("actions"), list):
        return []
    summary: list[Dict[str, Any]] = []
    for item in result["actions"][:8]:
        if not isinstance(item, dict):
            continue
        row = {key: item[key] for key in ("bead", "action", "error") if isinstance(item.get(key), str)}
        if isinstance(item.get("context"), str):
            row["context"] = item["context"][:240]
        summary.append(row)
    return summary


def _scheduler_loop(httpd: _RunnerHTTPServer, *, interval: float, limit: int) -> None:
    while not httpd._shutdown_requested:
        state = httpd.read_state()
        if state.get("running") and not state.get("paused") and not state.get("draining"):
            httpd.record_scheduler_tick("started")
            protocol.append_runner_event(httpd.root, {"type": "scheduler_tick_started"})
            try:
                result = httpd.run_tick(dry_run=False, limit=limit)
                if result is None:
                    result = {"schemaVersion": protocol.SCHEMA_VERSION, "actions": []}
            except (KeyboardInterrupt, GeneratorExit):
                raise
            except BaseException as exc:
                httpd.record_scheduler_tick("failed", error=str(exc))
                protocol.append_runner_event(httpd.root, {"type": "scheduler_tick_failed", "error": str(exc)})
            else:
                actions = _scheduler_action_summary(result)
                httpd.record_scheduler_tick("completed", actions=actions)
                protocol.append_runner_event(httpd.root, {"type": "scheduler_tick_completed", "actions": actions})
        # A drain may arrive while a tick owns an active slot. Re-evaluate
        # after every loop so completion of that slot reaches shutdown.
        httpd.maybe_shutdown_when_drained(httpd.read_state())
        if httpd._shutdown_requested:
            break
        threading.Event().wait(max(0.05, interval))


def start_runner_service(
    root: Path | str | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
    lock_owner: str = SERVICE_OWNER,
    auto_schedule: bool = False,
    scheduler_interval: float | None = None,
    scheduler_limit: int = 1,
    concurrency: int | None = None,
) -> RunnerServiceHandle:
    normalized_root = protocol.normalize_root(root)
    lock = acquire_runner_lock(normalized_root, owner=lock_owner)
    if not lock.get("acquired"):
        raise RunnerServiceError(f"runner service already active for {normalized_root}: {lock.get('existing') or lock}")

    token_value = token or secrets.token_urlsafe(32)
    try:
        paths = protocol.runner_paths(normalized_root)
        paths["runnerDir"].mkdir(parents=True, exist_ok=True)
        paths["activeDir"].mkdir(parents=True, exist_ok=True)
        paths["tokenPath"].write_text(token_value + "\n", encoding="utf-8")
        try:
            paths["tokenPath"].chmod(0o600)
        except OSError:
            pass

        httpd = _RunnerHTTPServer(
            (host, port),
            _Handler,
            root=normalized_root,
            token=token_value,
            lock_owner=lock_owner,
            scheduler_enabled=auto_schedule,
        )
        metadata = protocol.save_service_metadata(
            normalized_root,
            {
                "pid": os.getpid(),
                "host": httpd.host,
                "port": httpd.port,
                "baseUrl": httpd.base_url,
                "startedAt": protocol.utc_now(),
                "heartbeatAt": protocol.utc_now(),
            },
        )
        previous_state = _clear_stale_active_runs(normalized_root, httpd.read_state())
        previous_state.pop("drainReason", None)
        previous_state.pop("drainRequestedAt", None)
        initial_state = {
            **previous_state,
            "running": True,
            "paused": False,
            "draining": False,
            "service": {**protocol.redact_service_metadata(metadata), "schedulerEnabled": auto_schedule},
            "host": httpd.host,
            "port": httpd.port,
            "baseUrl": httpd.base_url,
            "startedAt": metadata.get("startedAt"),
        }
        if concurrency is not None:
            initial_state["concurrency"] = concurrency
        if scheduler_interval is not None:
            initial_state["intervalSeconds"] = scheduler_interval
        state = httpd.write_state(initial_state)
        protocol.append_runner_event(normalized_root, {"type": "service_started", "baseUrl": httpd.base_url})
        thread = threading.Thread(target=_serve, args=(httpd,), name=f"agnt-runner-service:{normalized_root}", daemon=True)
        thread.start()
        scheduler_thread = None
        if auto_schedule:
            interval = float(scheduler_interval if scheduler_interval is not None else 30.0)
            scheduler_thread = threading.Thread(
                target=_scheduler_loop,
                kwargs={"httpd": httpd, "interval": interval, "limit": scheduler_limit},
                name=f"agnt-runner-scheduler:{normalized_root}",
                daemon=True,
            )
            httpd.scheduler_thread = scheduler_thread
            scheduler_thread.start()
        return RunnerServiceHandle(
            root=normalized_root,
            host=httpd.host,
            port=httpd.port,
            token=token_value,
            httpd=httpd,
            thread=thread,
            scheduler_thread=scheduler_thread,
        )
    except Exception:
        release_runner_lock(normalized_root, owner=lock_owner)
        raise


__all__ = ["RunnerServiceError", "RunnerServiceHandle", "SERVICE_OWNER", "start_runner_service"]
