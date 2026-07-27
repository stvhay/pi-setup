from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .langfuse import LangfuseError, _client_from_env
from .metrics import git_root
from .runs import default_runs_dir

REVIEW_SCORE = "improvement_review_status"
REVIEW_POLICY_VERSION = "v1"
TRACE_LIMIT_MULTIPLIER = 10
MAX_TRACE_READ = 500
MAX_TRACES_PER_SESSION = 20
OBSERVATIONS_PER_TRACE = 500


def improvement_dir() -> Path:
    return Path(os.environ.get("AGNT_IMPROVEMENT_DIR", Path.home() / ".pi" / "improvement")).expanduser()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _bytes(value: Any) -> int:
    if value is None:
        return 0
    text = value if isinstance(value, str) else _canonical(value)
    return len(text.encode())


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    return int(_number(value))


def _sum_trace_metadata(traces: list[dict[str, Any]], key: str) -> tuple[int, bool]:
    values = []
    for trace in traces:
        metadata = trace.get("metadata") or {}
        if isinstance(metadata, dict) and key in metadata:
            values.append(_int(metadata[key]))
    return sum(values), bool(values)


def _features(
    traces: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    scores: list[dict[str, Any]],
) -> dict[str, Any]:
    generations = [item for item in observations if item.get("type") == "GENERATION"]
    tools = [item for item in observations if item.get("type") == "TOOL"]
    tool_calls, has_tool_calls = _sum_trace_metadata(traces, "tool_call_count")
    tool_errors, has_tool_errors = _sum_trace_metadata(traces, "total_tool_errors")
    turns, has_turns = _sum_trace_metadata(traces, "turn_count")
    if not has_tool_calls:
        tool_calls = len(tools)
    if not has_tool_errors:
        tool_errors = sum(
            bool((item.get("metadata") if isinstance(item.get("metadata"), dict) else {}).get("isError") or item.get("level") == "ERROR")
            for item in tools
        )
    if not has_turns:
        turns = sum(item.get("name") == "turn" for item in observations)

    fresh_input = cache_read = output = 0
    cost = 0.0
    instruction_bytes = tool_bytes = input_bytes = 0
    prompt_parts = []
    models = set()
    missing_usage = False
    for generation in generations:
        usage = generation.get("usageDetails") or generation.get("usage") or {}
        input_tokens = _int(usage.get("input"))
        cached = _int(usage.get("cacheRead"))
        fresh_input += input_tokens
        cache_read += cached
        output += _int(usage.get("output"))
        missing_usage = missing_usage or not bool(usage)
        cost += _number(generation.get("calculatedTotalCost") or generation.get("totalPrice"))
        if generation.get("model"):
            models.add(str(generation["model"]))
        request = generation.get("input")
        if isinstance(request, dict):
            instructions = request.get("instructions")
            request_tools = request.get("tools")
            request_input = request.get("input")
            instruction_bytes += _bytes(instructions)
            tool_bytes += _bytes(request_tools)
            input_bytes += _bytes(request_input)
            prompt_parts.append({"instructions": instructions, "tools": request_tools})
        else:
            input_bytes += _bytes(request)

    for trace in traces:
        metadata = trace.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("model"):
            models.add(str(metadata["model"]))

    tool_metadata = [item["metadata"] for item in tools if isinstance(item.get("metadata"), dict)]
    tool_input_bytes = sum(_int(metadata.get("inputBytes")) for metadata in tool_metadata)
    tool_output_bytes = sum(_int(metadata.get("outputBytes")) for metadata in tool_metadata)
    signatures = Counter()
    evaluator_timeouts = 0
    for observation in observations:
        metadata = observation.get("metadata") or {}
        is_error = bool((isinstance(metadata, dict) and metadata.get("isError")) or observation.get("level") == "ERROR")
        if is_error:
            signatures[_hash(observation.get("statusMessage") or observation.get("output") or observation.get("name"))] += 1
            if "evaluator" in str(observation.get("name") or "").lower():
                evaluator_timeouts += 1

    evaluator_outcomes = []
    final_outcome: Any = "unknown"
    for score in scores:
        score_name = str(score.get("name") or "")
        if score.get("source") != "EVAL" and "outcome" not in score_name.lower():
            continue
        item = {key: score.get(key) for key in ("name", "value", "dataType", "source") if score.get(key) is not None}
        evaluator_outcomes.append(item)
        if "outcome" in score_name.lower():
            final_outcome = score.get("value")
    for trace in traces:
        metadata = trace.get("metadata") or {}
        if final_outcome == "unknown" and isinstance(metadata, dict) and metadata.get("semanticOutcome"):
            final_outcome = metadata["semanticOutcome"]

    capture_gaps = []
    if not generations:
        capture_gaps.append("no-generations")
    if missing_usage:
        capture_gaps.append("missing-usage")
    if not models:
        capture_gaps.append("missing-model")
    if final_outcome == "unknown":
        capture_gaps.append("missing-outcome")

    return {
        "finalOutcome": final_outcome,
        "toolCalls": tool_calls,
        "toolErrors": tool_errors,
        "turns": turns,
        "latencySeconds": sum(_number(trace.get("latency")) for trace in traces),
        "tokens": {"freshInput": fresh_input, "cacheRead": cache_read, "output": output},
        "cost": round(cost, 10),
        "payloadBytes": {
            "instructions": instruction_bytes,
            "tools": tool_bytes,
            "input": input_bytes,
            "toolInput": tool_input_bytes,
            "toolOutput": tool_output_bytes,
        },
        "models": sorted(models),
        "promptHash": _hash(prompt_parts),
        "evaluatorOutcomes": evaluator_outcomes,
        "evaluatorTimeouts": evaluator_timeouts,
        "errorSignatures": [{"hash": key, "count": count} for key, count in sorted(signatures.items())],
        "captureGaps": capture_gaps,
    }


def _correlate(session_id: str, runs_dir: Path) -> dict[str, Any]:
    if not session_id.startswith("run-"):
        return {"status": "unlinked"}
    run_id = session_id[4:]
    if not run_id or run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
        return {"status": "unlinked"}
    bundle = runs_dir / run_id
    try:
        invocation = json.loads((bundle / "invocation.yaml").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unlinked"}
    if not isinstance(invocation, dict) or invocation.get("id") != run_id:
        return {"status": "unlinked"}
    return {
        "status": "linked",
        "runId": run_id,
        "beadId": invocation.get("bead"),
        "bundle": str(bundle),
    }


def _write_packet(output_dir: Path, packet: dict[str, Any]) -> Path:
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_dir.chmod(0o700)
    target = output_dir / f"scan-{packet['reportId']}.json"
    fd, temporary = tempfile.mkstemp(prefix=".scan-", suffix=".tmp", dir=output_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(packet, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, target)
        target.chmod(0o600)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise
    return target


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _is_current_review(scores: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(score.get("metadata"), dict)
        and score["metadata"].get("reviewPolicyVersion") == REVIEW_POLICY_VERSION
        for score in scores
    )


def scan_sessions(
    client: Any,
    *,
    since: str,
    until: str,
    limit: int,
    output_dir: Path,
    runs_dir: Path,
    repository_root: Path,
    recheck: bool = False,
    dry_run: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if limit < 1:
        raise ValueError("scan limit must be positive")
    if not since or not until:
        raise ValueError("scan requires time bounds")
    if _inside(output_dir, repository_root):
        raise ValueError("improvement directory must be outside repository")

    trace_limit = min(max(limit * TRACE_LIMIT_MULTIPLIER, 10), MAX_TRACE_READ)
    review_cache: dict[str, bool] = {}
    while True:
        traces = client.list_traces(from_timestamp=since, to_timestamp=until, limit=trace_limit)
        groups: dict[str, list[dict[str, Any]]] = {}
        for trace in traces:
            session_id = trace.get("sessionId")
            if isinstance(session_id, str) and session_id:
                groups.setdefault(session_id, []).append(trace)
        for session_id in groups:
            if session_id not in review_cache:
                scores = [] if recheck else client.list_scores(
                    from_timestamp=since,
                    to_timestamp=until,
                    session_id=session_id,
                    name=REVIEW_SCORE,
                    limit=1,
                )
                review_cache[session_id] = _is_current_review(scores)
        eligible_groups = [(session_id, items) for session_id, items in groups.items() if not review_cache[session_id]]
        if len(eligible_groups) >= limit or len(traces) < trace_limit or trace_limit == MAX_TRACE_READ:
            break
        trace_limit = min(trace_limit * 2, MAX_TRACE_READ)

    sessions = []
    for session_id, session_traces in eligible_groups[:limit]:
        selected_traces = session_traces[:MAX_TRACES_PER_SESSION]
        observations = []
        trace_scores = []
        observations_truncated = False
        for trace in selected_traces:
            rows = client.list_observations(
                from_start_time=since,
                to_start_time=until,
                trace_id=str(trace["id"]),
                limit=OBSERVATIONS_PER_TRACE + 1,
            )
            observations_truncated = observations_truncated or len(rows) > OBSERVATIONS_PER_TRACE
            observations.extend(rows[:OBSERVATIONS_PER_TRACE])
            trace_scores.extend(client.list_scores(
                from_timestamp=since,
                to_timestamp=until,
                trace_id=str(trace["id"]),
                limit=100,
            ))
        correlation = _correlate(session_id, runs_dir)
        features = _features(selected_traces, observations, trace_scores)
        if len(session_traces) > len(selected_traces):
            features["captureGaps"].append("trace-limit")
        if observations_truncated:
            features["captureGaps"].append("observation-limit")
        sessions.append({
            "sessionId": session_id,
            "traceIds": [str(trace["id"]) for trace in selected_traces],
            "correlation": correlation,
            "features": features,
        })

    report_id = _hash({"since": since, "until": until, "sessions": [item["sessionId"] for item in sessions]})[:16]
    packet = {
        "schemaVersion": 1,
        "reportId": report_id,
        "createdAt": until,
        "scan": {
            "since": since,
            "until": until,
            "limit": limit,
            "recheck": recheck,
            "reviewPolicyVersion": REVIEW_POLICY_VERSION,
        },
        "sessions": sessions,
    }
    summary = {
        "schemaVersion": 1,
        "status": "ok",
        "scannedTraces": len(traces),
        "candidateSessions": len(groups),
        "eligibleSessions": len(sessions),
        "reviewedSessionsSkipped": sum(review_cache.get(session_id, False) for session_id in groups),
        "unlinkedSessions": sum(item["correlation"]["status"] == "unlinked" for item in sessions),
        "reportWritten": not dry_run,
        "reportPath": None,
    }
    if not dry_run:
        summary["reportPath"] = str(_write_packet(output_dir, packet))
    return summary, packet


def _timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _scan_limit(value: str) -> int:
    limit = int(value)
    if not 1 <= limit <= 50:
        raise argparse.ArgumentTypeError("limit must be between 1 and 50")
    return limit


def cmd_improve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt improve", description="Review private Langfuse telemetry safely.")
    sub = parser.add_subparsers(dest="action")
    scan = sub.add_parser("scan", help="write a bounded private review packet")
    scan.add_argument("--since", type=_timestamp)
    scan.add_argument("--limit", type=_scan_limit, default=20)
    scan.add_argument("--recheck", action="store_true")
    scan.add_argument("--dry-run", action="store_true")
    scan.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.action != "scan":
        parser.print_help()
        return 0

    now = datetime.now(timezone.utc).replace(microsecond=0)
    until = now.isoformat().replace("+00:00", "Z")
    since = args.since or (now - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    try:
        summary, _ = scan_sessions(
            _client_from_env(),
            since=since,
            until=until,
            limit=args.limit,
            output_dir=improvement_dir(),
            runs_dir=default_runs_dir(),
            repository_root=git_root(),
            recheck=args.recheck,
            dry_run=args.dry_run,
        )
    except (LangfuseError, OSError, ValueError):
        if args.json:
            print(json.dumps({"schemaVersion": 1, "status": "error", "error": "improvement scan failed"}))
        else:
            print("Improvement scan failed.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"Eligible sessions: {summary['eligibleSessions']}; report: {summary['reportPath'] or 'not written'}")
    return 0


__all__ = ["cmd_improve", "improvement_dir", "scan_sessions"]
