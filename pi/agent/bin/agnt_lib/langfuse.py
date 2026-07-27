from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / "langfuse" / "evaluators.json"


def load_manifest(path: Path | str = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or not isinstance(data.get("evaluators"), list) or not isinstance(data.get("rules"), list):
        raise ValueError("invalid Langfuse evaluator manifest")
    return data


def _same(actual: Any, desired: Any) -> bool:
    if isinstance(desired, dict):
        return isinstance(actual, dict) and all(key in actual and _same(actual[key], value) for key, value in desired.items())
    if isinstance(desired, list):
        return isinstance(actual, list) and len(actual) == len(desired) and all(_same(a, d) for a, d in zip(actual, desired))
    return actual == desired


def run_sync(manifest: dict[str, Any], client: Any, *, apply: bool, quiet: bool) -> int:
    evaluators = {item.get("name"): item for item in client.list_evaluators()}
    rules = {item.get("name"): item for item in client.list_rules()}
    drift = False

    for desired in manifest["evaluators"]:
        actual = evaluators.get(desired["name"])
        if actual is not None and _same(actual, desired):
            continue
        drift = True
        label = "missing" if actual is None else "outdated"
        if not quiet:
            print(f"{label} evaluator: {desired['name']}")
        if apply:
            client.create_evaluator(desired)

    for desired in manifest["rules"]:
        actual = rules.get(desired["name"])
        if actual is not None and _same(actual, desired):
            continue
        drift = True
        label = "missing" if actual is None else "outdated"
        if not quiet:
            print(f"{label} rule: {desired['name']}")
        if apply:
            if actual is None:
                client.create_rule(desired)
            else:
                client.update_rule(actual["id"], desired)

    return 0 if apply or not drift else 1


class LangfuseClient:
    def __init__(self, base_url: str, public_key: str, secret_key: str):
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value is not None})
        request = urllib.request.Request(
            self.base_url + path + (f"?{query}" if query else ""),
            data=json.dumps(body).encode() if body is not None else None,
            headers=self.headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    def _list(self, path: str) -> list[dict[str, Any]]:
        payload = self._request("GET", path, params={"limit": 50, "page": 1})
        return payload.get("data") or payload.get("items") or []

    def _legacy_rows(
        self,
        path: str,
        *,
        bounds: dict[str, str],
        limit: int,
        page_size: int,
    ) -> list[dict[str, Any]]:
        if not all(bounds.values()):
            raise ValueError("Langfuse reads require time bounds")
        if limit < 1 or page_size < 1:
            raise ValueError("Langfuse read limits must be positive")
        rows: list[dict[str, Any]] = []
        page = 1
        while len(rows) < limit:
            payload = self._request("GET", path, params={
                **bounds,
                "limit": min(page_size, limit - len(rows)),
                "page": page,
            })
            items = payload.get("data") or []
            rows.extend(items)
            meta = payload.get("meta") or {}
            if not items or page >= int(meta.get("totalPages") or page):
                break
            page += 1
        return rows[:limit]

    def list_observations(self, *, from_start_time: str, to_start_time: str, limit: int, page_size: int = 100) -> list[dict[str, Any]]:
        return self._legacy_rows(
            "/api/public/observations",
            bounds={"fromStartTime": from_start_time, "toStartTime": to_start_time},
            limit=limit,
            page_size=page_size,
        )

    def list_traces(self, *, from_timestamp: str, to_timestamp: str, limit: int, page_size: int = 100) -> list[dict[str, Any]]:
        return self._legacy_rows(
            "/api/public/traces",
            bounds={"fromTimestamp": from_timestamp, "toTimestamp": to_timestamp},
            limit=limit,
            page_size=page_size,
        )

    def list_scores(
        self,
        *,
        from_timestamp: str,
        to_timestamp: str,
        limit: int,
        page_size: int = 100,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        if not from_timestamp or not to_timestamp:
            raise ValueError("Langfuse reads require time bounds")
        if limit < 1 or page_size < 1:
            raise ValueError("Langfuse read limits must be positive")
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(rows) < limit:
            params = {
                "fromTimestamp": from_timestamp,
                "toTimestamp": to_timestamp,
                "fields": "details,subject",
                "name": name,
                "limit": min(page_size, limit - len(rows)),
            }
            if cursor:
                params["cursor"] = cursor
            payload = self._request("GET", "/api/public/v3/scores", params=params)
            items = payload.get("data") or []
            rows.extend(items)
            cursor = (payload.get("meta") or {}).get("cursor")
            if not items or not cursor:
                break
        return rows[:limit]

    def list_evaluators(self):
        return self._list("/api/public/unstable/evaluators")

    def list_rules(self):
        return self._list("/api/public/unstable/evaluation-rules")

    def create_evaluator(self, body):
        return self._request("POST", "/api/public/unstable/evaluators", body)

    def create_rule(self, body):
        return self._request("POST", "/api/public/unstable/evaluation-rules", body)

    def update_rule(self, rule_id, body):
        return self._request("PATCH", f"/api/public/unstable/evaluation-rules/{rule_id}", body)


def _client_from_env() -> LangfuseClient:
    config: dict[str, Any] = {}
    config_dir = Path(os.environ.get("PI_CONFIG_DIR", Path.home() / ".pi"))
    path = config_dir / "agent" / "pi-langfuse" / "config.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    base_url = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST") or config.get("host")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY") or config.get("publicKey")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY") or config.get("secretKey")
    if not all((base_url, public_key, secret_key)):
        raise ValueError("Langfuse credentials are not configured")
    return LangfuseClient(base_url, public_key, secret_key)


def cmd_langfuse(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt langfuse", description="Check or apply tracked Langfuse evaluator configuration.")
    parser.add_argument("action", choices=("check", "apply"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run_sync(load_manifest(args.manifest), _client_from_env(), apply=args.action == "apply", quiet=args.quiet)
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        if not args.quiet:
            print(f"Langfuse evaluator sync failed: {exc}")
        return 2


__all__ = ["LangfuseClient", "cmd_langfuse", "load_manifest", "run_sync"]
