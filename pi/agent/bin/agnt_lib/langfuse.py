from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .session_time import session_start

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
        comparable = desired
        actual_evaluator = actual.get("evaluator") if actual is not None else None
        if isinstance(actual_evaluator, dict) and "scope" not in actual_evaluator and desired["evaluator"].get("scope") == "project":
            comparable = {**desired, "evaluator": {key: value for key, value in desired["evaluator"].items() if key != "scope"}}
        if actual is not None and _same(actual, comparable):
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


def _group_trace_observations(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    gaps: list[dict[str, str]] = []
    context_fields = ("sessionId", "userId", "tags", "release", "environment", "version", "public", "bookmarked")
    for row in rows:
        trace_id = row.get("traceId")
        if not isinstance(trace_id, str) or not trace_id:
            gaps.append({"scope": "traces", "code": "trace-id-unavailable"})
            continue
        groups.setdefault(trace_id, []).append(row)
    traces = []
    for trace_id, observations in groups.items():
        physical = [row for row in observations if "parentObservationId" in row and row["parentObservationId"] is None]
        roots = physical or [row for row in observations if row.get("isRootObservation") is True]
        root = roots[0] if len(roots) == 1 else None
        context = dict(root) if root is not None else {}
        if root is None:
            gaps.append({"scope": "traces", "traceId": trace_id, "code": "ambiguous-root" if roots else "root-unavailable"})
            for field in (*context_fields, "traceName"):
                values = [row[field] for row in observations if field in row]
                distinct = {json.dumps(value, sort_keys=True) for value in values}
                if len(distinct) == 1:
                    context[field] = values[0]
                elif len(distinct) > 1:
                    item = {"scope": "traces", "traceId": trace_id, "code": "conflicting-trace-context"}
                    if item not in gaps:
                        gaps.append(item)
        trace = {"id": trace_id, **{field: context[field] for field in context_fields if field in context}}
        if "traceName" in context:
            trace["name"] = context["traceName"]
        elif root is not None and "name" in root:
            trace["name"] = root["name"]
        if root is not None:
            timestamp = root.get("startTime")
            try:
                parsed = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else None
            except ValueError:
                parsed = None
            if parsed is not None and parsed.tzinfo is not None:
                trace["timestamp"] = timestamp
            else:
                gaps.append({"scope": "traces", "traceId": trace_id, "code": "root-time-unavailable"})
            for field in ("input", "output", "metadata"):
                if field in root:
                    trace[field] = root[field]
        traces.append(trace)
    return traces, gaps


class LangfuseClient:
    def __init__(self, base_url: str, public_key: str, secret_key: str):
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
        # Version of this owned REST adapter, not the official Python SDK.
        self.headers.update({
            "X-Langfuse-Sdk-Name": "pi-agnt-rest",
            "X-Langfuse-Sdk-Version": "1.0.0",
            "X-Langfuse-Public-Key": public_key,
        })
        self._score_timestamps: dict[tuple[str, str, str], str] = {}

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | list[dict[str, Any]] | None = None,
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
                status = response.status
        except urllib.error.HTTPError as exc:
            raise LangfuseError(f"Langfuse request failed with HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise LangfuseError("Langfuse request failed") from None
        except json.JSONDecodeError:
            raise LangfuseError("Langfuse response was not valid JSON") from None
        if not isinstance(payload, dict):
            raise LangfuseError("Langfuse response was not a JSON object")
        if method == "POST" and path == "/api/public/scores" and status == 207:
            if not all(field in payload for field in ("accepted", "rejected", "errors")):
                raise LangfuseError("Langfuse returned an invalid partial score acknowledgement")
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

    def _observation_rows(
        self, *, from_start_time: str, to_start_time: str, limit: int,
        page_size: int, fields: str, trace_id: str | None = None,
    ) -> dict[str, Any]:
        if not from_start_time or not to_start_time:
            raise ValueError("Langfuse reads require time bounds")
        if type(limit) is not int or type(page_size) is not int or min(limit, page_size) < 1:
            raise ValueError("Langfuse read limits must be positive integers")
        rows: list[dict[str, Any]] = []
        seen_ids: set[tuple[str | None, str]] = set()
        seen_cursors: set[str] = set()
        cursor: str | None = None
        scanned = 0
        complete = False
        reason = "max-observations"
        while scanned < limit:
            size = min(page_size, MAX_PAGE_SIZE, limit - scanned)
            params: dict[str, Any] = {
                "fromStartTime": from_start_time, "toStartTime": to_start_time,
                "fields": fields, "limit": size,
            }
            if cursor is not None:
                params["cursor"] = cursor
            if trace_id is not None:
                params["traceId"] = trace_id
            payload = self._request("GET", "/api/public/v2/observations", params=params)
            items, meta = payload.get("data"), payload.get("meta")
            if not isinstance(items, list) or not all(isinstance(row, dict) for row in items) or not isinstance(meta, dict):
                reason = "malformed-response"
                break
            accepted = items[:size]
            scanned += len(accepted)
            invalid = None
            for row in accepted:
                identifier, row_trace = row.get("id"), row.get("traceId")
                if not isinstance(identifier, str) or not identifier or (row_trace is not None and not isinstance(row_trace, str)):
                    invalid = "malformed-response"
                elif (row_trace, identifier) in seen_ids:
                    invalid = "non-advancing-page"
                elif trace_id is not None and row_trace != trace_id:
                    invalid = "unexpected-trace"
                else:
                    seen_ids.add((row_trace, identifier))
                    decoded = dict(row)
                    for field in ("input", "output"):
                        if isinstance(decoded.get(field), str):
                            try:
                                decoded[field] = json.loads(decoded[field])
                            except (ValueError, RecursionError):
                                pass
                    rows.append(decoded)
            next_cursor = meta.get("cursor")
            if next_cursor is not None and (
                not isinstance(next_cursor, str) or not next_cursor or len(next_cursor) > 8192
            ):
                cursor, reason = None, "malformed-metadata"
                break
            cursor = next_cursor
            if len(items) > size:
                # The service cursor skips records omitted from this overrun.
                cursor, reason = None, "response-overrun"
                break
            if invalid:
                reason = invalid
                break
            if cursor is not None and cursor in seen_cursors:
                reason = "non-advancing-cursor"
                break
            if cursor is None:
                complete, reason = True, "api-end"
                break
            seen_cursors.add(cursor)
            if not items:
                reason = "incomplete-response"
                break
        return {"rows": rows, "scanned": scanned, "complete": complete, "cursor": cursor, "reason": reason}

    def list_observations(
        self, *, from_start_time: str, to_start_time: str, limit: int,
        page_size: int = 100, trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self._observation_rows(
            from_start_time=from_start_time, to_start_time=to_start_time,
            limit=limit, page_size=page_size, trace_id=trace_id,
            fields="core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context",
        )
        if result["reason"] not in ("api-end", "max-observations"):
            # A short list would otherwise masquerade as complete evidence.
            raise LangfuseError(f"Langfuse observation read incomplete: {result['reason']}")
        return result["rows"]

    def list_traces(self, *, from_timestamp: str, to_timestamp: str, limit: int, page_size: int = 100) -> list[dict[str, Any]]:
        result = self.list_traces_with_metadata(
            from_timestamp=from_timestamp, to_timestamp=to_timestamp,
            max_traces=limit, page_size=page_size,
        )
        reason = result["continuation"]["reason"]
        if reason in {"malformed-response", "malformed-metadata", "non-advancing-page",
                      "non-advancing-cursor", "incomplete-response", "response-overrun"}:
            raise LangfuseError(f"Langfuse trace read incomplete: {reason}")
        return result["traces"]

    def list_traces_with_metadata(
        self, *, from_timestamp: str, to_timestamp: str,
        page_size: int = 100, max_traces: int = DEFAULT_MAX_TRACES,
    ) -> dict[str, Any]:
        result = self._observation_rows(
            from_start_time=from_timestamp, to_start_time=to_timestamp,
            limit=max_traces, page_size=page_size,
            fields="core,basic,io,metadata,trace_context",
        )
        traces, gaps = _group_trace_observations(result["rows"])
        if not result["complete"]:
            gaps.insert(0, {"scope": "traces", "code": result["reason"]})
        complete = result["complete"] and not gaps
        return {
            "traces": traces,
            "totalAvailable": None,  # v2 has no trace total; observation counts are not equivalent.
            "scanned": len(traces),
            "observationsScanned": result["scanned"],
            "maxTraces": max_traces,
            "complete": complete,
            "gaps": gaps,
            "continuation": {
                "hasMore": not result["complete"],
                "nextPage": None,  # Retained compatibility key; v2 has no page numbers.
                "nextCursor": result["cursor"],
                "reason": result["reason"] if not result["complete"] or not gaps else gaps[0]["code"],
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

    @staticmethod
    def _annotation_path_id(value: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 1000:
            raise ValueError("Langfuse annotation identifier is invalid")
        return urllib.parse.quote(value, safe="")

    def get_annotation_queue(self, queue_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/public/annotation-queues/{self._annotation_path_id(queue_id)}",
        )

    def list_annotation_queue_items(
        self,
        queue_id: str,
        *,
        limit: int,
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit < MAX_PAGE_SIZE:
            raise ValueError("Langfuse annotation limit is invalid")
        payload = self._request(
            "GET",
            f"/api/public/annotation-queues/{self._annotation_path_id(queue_id)}/items",
            params={"limit": limit + 1, "page": 1},
        )
        items = self._data(payload)
        meta = self._meta(payload)
        total = meta.get("totalItems")
        complete = (
            len(items) <= limit
            and type(total) is int
            and total == len(items)
        )
        return {"items": items[:limit], "complete": complete}

    def list_annotation_scores(
        self,
        queue_id: str,
        *,
        limit: int,
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit < MAX_PAGE_SIZE:
            raise ValueError("Langfuse annotation limit is invalid")
        payload = self._request("GET", "/api/public/v3/scores", params={
            "fields": "details,subject,annotation",
            "queueId": queue_id,
            "source": "ANNOTATION",
            "limit": limit + 1,
        })
        scores = self._data(payload)
        complete = len(scores) <= limit and not self._meta(payload).get("cursor")
        return {"scores": scores[:limit], "complete": complete}

    def get_score_config(self, config_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/public/score-configs/{self._annotation_path_id(config_id)}",
        )

    @staticmethod
    def _checked_score_timestamp(value: Any) -> datetime:
        try:
            if not isinstance(value, str) or "T" not in value:
                raise ValueError
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
            return parsed
        except ValueError:
            raise LangfuseError("Stable score timestamp is unavailable or invalid") from None

    def _score_timestamp(self, score_id: str, session_id: str, name: str, timestamp: str | None) -> str:
        if any(not isinstance(value, str) or not value for value in (score_id, session_id, name)) or "," in score_id:
            raise LangfuseError("Score identity cannot be queried unambiguously")
        if timestamp is not None:
            self._checked_score_timestamp(timestamp)
        key = (score_id, session_id, name)
        saved = self._score_timestamps.get(key)
        if saved is None:
            # Exact ID lookup is bounded without scanning an arbitrary time range.
            # Recover old scores' original timestamps before migrating their writes.
            payload = self._request("GET", "/api/public/v3/scores", params={
                "id": score_id, "fields": "subject", "limit": 2,
            })
            if not isinstance(payload, dict):
                raise LangfuseError("Score identity lookup response is not an object")
            rows = payload.get("data")
            meta = payload.get("meta")
            if not isinstance(rows, list) or len(rows) > 1 or not isinstance(meta, dict) or meta.get("cursor") is not None:
                raise LangfuseError("Score identity lookup is incomplete or ambiguous")
            if rows:
                row = rows[0]
                if (
                    not isinstance(row, dict) or row.get("id") != score_id or row.get("name") != name
                    or row.get("source") != "API" or not isinstance(row.get("subject"), dict)
                    or row["subject"].get("kind") != "session" or row["subject"].get("id") != session_id
                ):
                    raise LangfuseError("Score identity lookup does not match the requested session score")
                saved = row.get("timestamp")
                self._checked_score_timestamp(saved)
            elif timestamp is not None:
                saved = timestamp
            else:
                started = session_start(session_id)
                if started is None:
                    raise LangfuseError("New session score requires an explicit stable timestamp")
                saved = started.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            # Retain before POST: a lost acknowledgement must not change identity.
            self._score_timestamps[key] = saved
        if timestamp is not None and self._checked_score_timestamp(timestamp) != self._checked_score_timestamp(saved):
            raise LangfuseError("Score timestamp conflicts with its existing identity")
        return saved

    def put_session_score(
        self,
        *,
        score_id: str,
        session_id: str,
        name: str,
        value: str | int | float,
        metadata: dict[str, Any] | None = None,
        data_type: str = "CATEGORICAL",
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        body = [{
            "id": score_id,
            "timestamp": self._score_timestamp(score_id, session_id, name, timestamp),
            "sessionId": session_id,
            "name": name,
            "value": value,
            "dataType": data_type,
            "source": "API",
            "metadata": metadata or {},
        }]
        try:
            size = len(json.dumps(body, allow_nan=False).encode())
        except (TypeError, ValueError):
            raise LangfuseError("Score request is not valid JSON") from None
        if size > 3_000_000:
            raise LangfuseError("Score request exceeds the byte ceiling")
        result = self._request("POST", "/api/public/scores", body)
        if not isinstance(result, dict):
            raise LangfuseError("Langfuse returned an invalid score acknowledgement")
        if any(field in result for field in ("accepted", "rejected", "errors")):
            if (
                type(result.get("accepted")) is not int or result["accepted"] != 1
                or type(result.get("rejected")) is not int or result["rejected"] != 0
                or result.get("errors") != []
            ):
                # 207 rejects are terminal for this attempt, not a retry trigger.
                raise LangfuseError("Langfuse rejected the session score or returned an invalid acknowledgement")
        elif result.get("message") != "Accepted":
            raise LangfuseError("Langfuse returned an invalid score acknowledgement")
        return result

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
