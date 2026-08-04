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
MAX_PAGE_SIZE = 100
DEFAULT_MAX_TRACES = 500


class LangfuseError(RuntimeError):
    pass


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
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise LangfuseError(f"Langfuse request failed with HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise LangfuseError("Langfuse request failed") from None
        except json.JSONDecodeError:
            raise LangfuseError("Langfuse response was not valid JSON") from None
        if not isinstance(payload, dict):
            raise LangfuseError("Langfuse response was not a JSON object")
        return payload

    @staticmethod
    def _data(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data") or payload.get("items") or []
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise LangfuseError("Langfuse response data was not a list")
        return data

    @staticmethod
    def _meta(payload: dict[str, Any]) -> dict[str, Any]:
        meta = payload.get("meta") or {}
        if not isinstance(meta, dict):
            raise LangfuseError("Langfuse response metadata was not an object")
        return meta

    def _list(self, path: str) -> list[dict[str, Any]]:
        return self._data(self._request("GET", path, params={"limit": 50, "page": 1}))

    def _legacy_rows(
        self,
        path: str,
        *,
        bounds: dict[str, str],
        limit: int,
        page_size: int,
        filters: dict[str, str] | None = None,
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
                **(filters or {}),
                "limit": min(page_size, MAX_PAGE_SIZE, limit - len(rows)),
                "page": page,
            })
            items = self._data(payload)
            rows.extend(items)
            meta = self._meta(payload)
            if not items or page >= int(meta.get("totalPages") or page):
                break
            page += 1
        return rows[:limit]

    def list_observations(
        self,
        *,
        from_start_time: str,
        to_start_time: str,
        limit: int,
        page_size: int = 100,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._legacy_rows(
            "/api/public/observations",
            bounds={"fromStartTime": from_start_time, "toStartTime": to_start_time},
            limit=limit,
            page_size=page_size,
            filters={"traceId": trace_id} if trace_id else None,
        )

    def list_traces(self, *, from_timestamp: str, to_timestamp: str, limit: int, page_size: int = 100) -> list[dict[str, Any]]:
        return self._legacy_rows(
            "/api/public/traces",
            bounds={"fromTimestamp": from_timestamp, "toTimestamp": to_timestamp},
            limit=limit,
            page_size=page_size,
        )

    def list_traces_with_metadata(
        self,
        *,
        from_timestamp: str,
        to_timestamp: str,
        page_size: int = 100,
        max_traces: int = DEFAULT_MAX_TRACES,
    ) -> dict[str, Any]:
        if not from_timestamp or not to_timestamp:
            raise ValueError("Langfuse reads require time bounds")
        if page_size < 1 or type(max_traces) is not int or max_traces < 1:
            raise ValueError("Langfuse read limits must be positive")
        traces: list[dict[str, Any]] = []
        page = 1
        total_available: int | None = None
        total_unavailable = False
        previous_items: list[dict[str, Any]] | None = None
        complete = False
        reason = "max-traces"
        next_page: int | None = 1
        while len(traces) < max_traces:
            payload = self._request("GET", "/api/public/traces", params={
                "fromTimestamp": from_timestamp,
                "toTimestamp": to_timestamp,
                "limit": min(page_size, MAX_PAGE_SIZE, max_traces - len(traces)),
                "page": page,
            })
            items = self._data(payload)
            meta = self._meta(payload)
            repeated_page = bool(items and items == previous_items)
            uncapped_count = len(traces) + (0 if repeated_page else len(items))

            raw_total = meta.get("totalItems")
            if raw_total is not None:
                if (
                    type(raw_total) is not int
                    or raw_total < uncapped_count
                    or (total_available is not None and raw_total != total_available)
                ):
                    total_available = None
                    total_unavailable = True
                elif not total_unavailable:
                    total_available = raw_total

            if not repeated_page:
                previous_items = items
                traces.extend(items[: max_traces - len(traces)])

            if total_available is not None and len(traces) > total_available:
                total_available = None
                total_unavailable = True

            if repeated_page:
                reason = "non-advancing-page"
                next_page = page
                break

            raw_total_pages = meta.get("totalPages")
            total_pages = raw_total_pages if type(raw_total_pages) is int and raw_total_pages > 0 else None
            if not items:
                complete = (
                    not total_unavailable
                    and (total_available is None or len(traces) >= total_available)
                    and (total_pages is None or page >= total_pages)
                )
                reason = "api-end" if complete else "api-incomplete"
                next_page = None if complete else page + 1
                break
            if total_pages is not None and page >= total_pages:
                complete = not total_unavailable and (total_available is None or len(traces) >= total_available)
                reason = "api-end" if complete else "api-incomplete"
                next_page = None if complete else page + 1
                break
            if len(traces) >= max_traces:
                complete = not total_unavailable and total_available == len(traces)
                reason = "api-end" if complete else "max-traces"
                next_page = None if complete else page + 1
                break
            page += 1

        return {
            "traces": traces,
            "totalAvailable": total_available,
            "scanned": len(traces),
            "maxTraces": max_traces,
            "complete": complete,
            "continuation": {
                "hasMore": not complete,
                "nextPage": next_page,
                "reason": reason,
            },
        }

    def list_scores(
        self,
        *,
        from_timestamp: str,
        to_timestamp: str,
        limit: int,
        page_size: int = 100,
        name: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
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
                "limit": min(page_size, MAX_PAGE_SIZE, limit - len(rows)),
            }
            if session_id:
                params["sessionId"] = session_id
            if trace_id:
                params["traceId"] = trace_id
            if cursor:
                params["cursor"] = cursor
            payload = self._request("GET", "/api/public/v3/scores", params=params)
            items = self._data(payload)
            rows.extend(items)
            cursor = self._meta(payload).get("cursor")
            if not items or not cursor:
                break
        return rows[:limit]

    def put_session_score(
        self,
        *,
        score_id: str,
        session_id: str,
        name: str,
        value: str | int | float,
        metadata: dict[str, Any] | None = None,
        data_type: str = "CATEGORICAL",
    ) -> dict[str, Any]:
        return self._request("POST", "/api/public/scores", {
            "id": score_id,
            "sessionId": session_id,
            "name": name,
            "value": value,
            "dataType": data_type,
            "source": "API",
            "metadata": metadata or {},
        })

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
    except (OSError, ValueError, LangfuseError) as exc:
        if not args.quiet:
            print(f"Langfuse evaluator sync failed: {exc}")
        return 2


__all__ = ["LangfuseClient", "LangfuseError", "cmd_langfuse", "load_manifest", "run_sync"]
