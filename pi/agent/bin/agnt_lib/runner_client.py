from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import runner_protocol as protocol

DEFAULT_TIMEOUT_SECONDS = 2.0
STARTUP_TIMEOUT_SECONDS = 5.0


class RunnerClientError(RuntimeError):
    def __init__(self, message: str, *, payload: Dict[str, Any] | None = None):
        super().__init__(message)
        self.payload = payload or {"schemaVersion": 1, "error": message}


def _missing_service_payload(root: Path | str | None = None, *, detail: str | None = None) -> Dict[str, Any]:
    normalized = protocol.normalize_root(root)
    payload = {
        "schemaVersion": 1,
        "status": "not-running",
        "running": False,
        "connected": False,
        "root": str(normalized),
        "servicePath": str(protocol.runner_paths(normalized)["servicePath"]),
        "suggestedAction": "agnt work daemon start --json",
    }
    if detail:
        payload["detail"] = detail
    return payload


def _timeout_payload(root: Path | str | None = None, *, detail: str | None = None) -> Dict[str, Any]:
    normalized = protocol.normalize_root(root)
    payload = {
        "schemaVersion": 1,
        "status": "timeout",
        "running": None,
        "connected": None,
        "root": str(normalized),
        "servicePath": str(protocol.runner_paths(normalized)["servicePath"]),
        "suggestedAction": "agnt work runner status --json",
    }
    if detail:
        payload["detail"] = detail
    return payload


@dataclass
class RunnerClient:
    root: Path | str | None = None
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    @property
    def normalized_root(self) -> Path:
        return protocol.normalize_root(self.root)

    def _metadata_and_token(self) -> tuple[Dict[str, Any], str]:
        metadata = protocol.load_service_metadata(self.normalized_root)
        base_url = metadata.get("baseUrl") or (f"http://{metadata.get('host')}:{metadata.get('port')}" if metadata.get("host") and metadata.get("port") else None)
        if not metadata or not base_url:
            raise RunnerClientError("runner service is not running", payload=_missing_service_payload(self.normalized_root))
        token_path = Path(str(metadata.get("tokenPath") or protocol.runner_paths(self.normalized_root)["tokenPath"])).expanduser()
        try:
            token = token_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RunnerClientError(
                "runner service token is unavailable",
                payload=_missing_service_payload(self.normalized_root, detail=f"token unavailable: {exc}"),
            ) from exc
        if not token:
            raise RunnerClientError("runner service token is empty", payload=_missing_service_payload(self.normalized_root, detail="token is empty"))
        data = dict(metadata)
        data["baseUrl"] = str(base_url).rstrip("/")
        return data, token

    def request(self, method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        metadata, token = self._metadata_and_token()
        body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{metadata['baseUrl']}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                parsed = json.loads(response.read().decode("utf-8") or "{}")
        except HTTPError as exc:
            try:
                error_payload = json.loads(exc.read().decode("utf-8") or "{}")
            except Exception:
                error_payload = {"schemaVersion": 1, "error": str(exc), "statusCode": exc.code}
            raise RunnerClientError("runner service returned an error", payload=error_payload) from exc
        except TimeoutError as exc:
            raise RunnerClientError(
                "runner service request timed out",
                payload=_timeout_payload(self.normalized_root, detail=str(exc)),
            ) from exc
        except (URLError, OSError) as exc:
            raise RunnerClientError(
                "runner service request failed",
                payload=_missing_service_payload(self.normalized_root, detail=str(exc)),
            ) from exc
        if not isinstance(parsed, dict):
            raise RunnerClientError("runner service returned non-object JSON", payload={"schemaVersion": 1, "error": "non-object JSON"})
        return parsed

    def status(self) -> Dict[str, Any]:
        return self.request("GET", "/v1/status")

    def pause(self, *, reason: str | None = None) -> Dict[str, Any]:
        return self.request("POST", "/v1/pause", {"reason": reason or "paused by operator"})

    def resume(self) -> Dict[str, Any]:
        return self.request("POST", "/v1/resume", {})

    def tick(self, *, dry_run: bool = True, limit: int = 1) -> Dict[str, Any]:
        return self.request("POST", "/v1/tick", {"dryRun": dry_run, "limit": limit})

    def drain(self, *, reason: str | None = None) -> Dict[str, Any]:
        return self.request("POST", "/v1/drain", {"reason": reason or "drain requested"})

    def stop(self, *, force: bool = False) -> Dict[str, Any]:
        return self.request("POST", "/v1/stop", {"force": force})


def runner_client_status(root: Path | str | None = None) -> Dict[str, Any]:
    return RunnerClient(root).status()


def runner_client_pause(root: Path | str | None = None, *, reason: str | None = None) -> Dict[str, Any]:
    return RunnerClient(root).pause(reason=reason)


def runner_client_resume(root: Path | str | None = None) -> Dict[str, Any]:
    return RunnerClient(root).resume()


def runner_client_tick(
    *,
    root: Path | str | None = None,
    dry_run: bool = True,
    limit: int = 1,
    runs_dir: Path | None = None,
    metrics_dir: Path | None = None,
) -> Dict[str, Any]:
    payload = RunnerClient(root).tick(dry_run=dry_run, limit=limit)
    if runs_dir is not None:
        payload.setdefault("client", {})["runsDirIgnored"] = str(runs_dir)
    if metrics_dir is not None:
        payload.setdefault("client", {})["metricsDirIgnored"] = str(metrics_dir)
    return payload


def daemon_status(root: Path | str | None = None) -> Dict[str, Any]:
    try:
        status = RunnerClient(root).status()
    except RunnerClientError as exc:
        payload = dict(exc.payload)
        payload.setdefault("schemaVersion", 1)
        payload.setdefault("running", False)
        payload.setdefault("connected", False)
        return payload
    result = {"schemaVersion": 1, "running": bool(status.get("running")), "connected": True, "status": status.get("status"), "service": status}
    result["root"] = status.get("root")
    return result


def _agnt_script() -> Path:
    return Path(__file__).resolve().parents[1] / "agnt"


def daemon_start(
    *,
    root: Path | str | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
    concurrency: int | None = None,
    interval: float | None = None,
    timeout: float = STARTUP_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    normalized = protocol.normalize_root(root)
    current = daemon_status(normalized)
    if current.get("connected") and current.get("running"):
        return {"schemaVersion": 1, "started": False, "alreadyRunning": True, "status": current}

    paths = protocol.runner_paths(normalized)
    paths["runnerDir"].mkdir(parents=True, exist_ok=True)
    log_path = paths["runnerDir"] / "service.log"
    cmd = [
        sys.executable,
        str(_agnt_script()),
        "work",
        "daemon",
        "serve",
        "--root",
        str(normalized),
        "--host",
        host,
        "--port",
        str(port),
        "--json",
    ]
    if concurrency is not None:
        cmd.extend(["--concurrency", str(concurrency)])
    if interval is not None:
        cmd.extend(["--interval", str(interval)])
    log_handle = log_path.open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(cmd, stdout=log_handle, stderr=log_handle, start_new_session=True)
    finally:
        log_handle.close()

    deadline = time.time() + timeout
    last_status: Dict[str, Any] | None = None
    while time.time() < deadline:
        last_status = daemon_status(normalized)
        if last_status.get("connected") and last_status.get("running"):
            return {"schemaVersion": 1, "started": True, "pid": process.pid, "status": last_status, "logPath": str(log_path)}
        if process.poll() is not None:
            break
        time.sleep(0.05)
    return {
        "schemaVersion": 1,
        "started": False,
        "error": "runner daemon did not become healthy before timeout",
        "pid": process.pid,
        "returnCode": process.poll(),
        "status": last_status or daemon_status(normalized),
        "logPath": str(log_path),
    }


def daemon_stop(*, root: Path | str | None = None, drain: bool = True, force: bool = False, reason: str | None = None) -> Dict[str, Any]:
    if drain and force:
        return {"schemaVersion": 1, "stopping": False, "error": "choose either drain or force, not both"}
    try:
        client = RunnerClient(root)
        if force:
            return client.stop(force=True)
        return client.drain(reason=reason or "daemon stop requested")
    except RunnerClientError as exc:
        payload = dict(exc.payload)
        payload.setdefault("schemaVersion", 1)
        payload["stopping"] = False
        return payload


def daemon_serve(
    *,
    root: Path | str | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
    concurrency: int | None = None,
    interval: float | None = None,
) -> Dict[str, Any]:
    from .runner_service import start_runner_service

    handle = start_runner_service(
        root,
        host=host,
        port=port,
        auto_schedule=True,
        scheduler_interval=interval,
        scheduler_limit=concurrency or 1,
        concurrency=concurrency,
    )
    try:
        handle.thread.join()
    except KeyboardInterrupt:
        handle.stop(force=False)
    return {"schemaVersion": 1, "served": True, "root": str(handle.root), "baseUrl": handle.base_url}


__all__ = [
    "RunnerClient",
    "RunnerClientError",
    "daemon_serve",
    "daemon_start",
    "daemon_status",
    "daemon_stop",
    "runner_client_pause",
    "runner_client_resume",
    "runner_client_status",
    "runner_client_tick",
]
