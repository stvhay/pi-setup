from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .core import split_target
from .provider_circuits import classify_provider_failure, close_provider_circuit, open_provider_circuit
from .metrics import add_usage, empty_usage, metrics_record, new_invocation_id, utc_now

ONE_SHOT_SYSTEM_PROMPT = (
    "You are a read-only reviewer. Analyze only the complete packet in the user message. "
    "Do not claim to inspect files or run tools. Return only the requested format."
)


def assistant_text(message: Dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: List[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            chunks.append(str(block.get("text") or ""))
    return "".join(chunks)


def parse_pi_json_output(stdout: str) -> Tuple[str, Dict[str, Any] | None, str, str]:
    texts: List[str] = []
    message_end_usages: List[Dict[str, Any]] = []
    turn_end_usages: List[Dict[str, Any]] = []
    provider_error = ""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") not in {"message_end", "turn_end"}:
            continue
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        if message.get("stopReason") == "error":
            provider_error = str(message.get("errorMessage") or "provider returned a terminal error")
        usage = message.get("usage")
        if event.get("type") == "message_end":
            text = assistant_text(message)
            if text:
                texts.append(text)
            if isinstance(usage, dict):
                message_end_usages.append(usage)
        elif isinstance(usage, dict):
            turn_end_usages.append(usage)

    usages = message_end_usages or turn_end_usages
    if not usages:
        return "".join(texts), None, "unavailable", provider_error
    usage_total = empty_usage()
    for usage in usages:
        add_usage(usage_total, usage)
    usage_total["providerRequests"] = len(usages)
    return "".join(texts), usage_total, ("message_end" if message_end_usages else "turn_end"), provider_error


def safe_target_name(target: str) -> str:
    return target.replace("/", "__").replace(":", "_")
def invoke_one(
    target: str,
    prompt: str,
    *,
    metrics: bool = True,
    task: str | None = None,
    risk_category: str | None = None,
    thinking_level: str | None = None,
    outcome: str = "unknown",
    human_override: bool = False,
    fallback_used: bool = False,
    record_session: bool = False,
    session_id: str | None = None,
    session_name: str | None = None,
    cwd: Path | str | None = None,
    pi_args: List[str] | None = None,
    timeout_seconds: int | float | None = None,
    one_shot: bool = False,
    invocation_id: str | None = None,
    parent_session_id: str | None = None,
    work_item: str | None = None,
) -> Tuple[int, str, str, Dict[str, Any] | None]:
    provider, model = split_target(target)
    invocation_id = invocation_id or new_invocation_id()
    started_at = utc_now()
    started = time.monotonic()
    session_args: List[str] = []
    if record_session:
        if session_id:
            session_args.extend(["--session-id", session_id])
        if session_name:
            session_args.extend(["--name", session_name])
    else:
        session_args.append("--no-session")
    extra_args = list(pi_args or [])
    if thinking_level and thinking_level != "default":
        extra_args.extend(["--thinking", thinking_level])
    if one_shot:
        extra_args.extend(
            [
                "--no-tools",
                "--no-skills",
                "--no-context-files",
                "--no-prompt-templates",
                "--system-prompt",
                ONE_SHOT_SYSTEM_PROMPT,
            ]
        )
    run_kwargs = {
        "input": prompt,
        "text": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "cwd": str(Path(cwd).expanduser()) if cwd is not None else None,
        "timeout": timeout_seconds,
    }
    try:
        if metrics:
            proc = subprocess.run(
                ["pi", "--mode", "json", *session_args, *extra_args, "--provider", provider, "--model", model],
                **run_kwargs,
            )
            out, usage, usage_source, provider_error = parse_pi_json_output(proc.stdout)
        else:
            proc = subprocess.run(
                ["pi", "--print", *session_args, *extra_args, "--provider", provider, "--model", model],
                **run_kwargs,
            )
            out, usage, usage_source, provider_error = proc.stdout, None, "not_requested", ""
    except subprocess.TimeoutExpired as exc:
        ended_at = utc_now()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        raw_out = exc.output.decode("utf-8", errors="replace") if isinstance(exc.output, bytes) else str(exc.output or "")
        if metrics:
            out, usage, _, provider_error = parse_pi_json_output(raw_out)
        else:
            out, usage, provider_error = raw_out, None, ""
        stderr_text = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        err = f"pi invocation timed out after {timeout_seconds}s"
        if provider_error:
            err = f"{err}\n{provider_error}"
        if stderr_text:
            err = f"{err}\n{stderr_text}"
        record = None
        if metrics:
            record = metrics_record(
                target=target,
                task=task,
                started_at=started_at,
                ended_at=ended_at,
                elapsed_ms=elapsed_ms,
                code=124,
                prompt=prompt,
                out=out,
                err=err,
                usage=usage,
                usage_source="timeout",
                invocation_id=invocation_id,
                parent_session_id=parent_session_id,
                work_item=work_item,
                failure_class="timeout",
                risk_category=risk_category,
                thinking_level=thinking_level,
                outcome=outcome,
                human_override=human_override,
                fallback_used=fallback_used,
                invocation_mode="one-shot" if one_shot else "agentic",
            )
        return 124, out, err, record
    ended_at = utc_now()
    elapsed_ms = int((time.monotonic() - started) * 1000)
    code = proc.returncode or (1 if provider_error else 0)
    err = proc.stderr
    if provider_error:
        err = f"{err.rstrip()}\n{provider_error}".lstrip()
    provider_failure_class = classify_provider_failure(provider_error or err) if code != 0 else None
    try:
        if code == 0:
            close_provider_circuit(provider)
        elif provider_failure_class:
            open_provider_circuit(provider, provider_failure_class)
    except (OSError, ValueError):
        pass
    record = None
    if metrics:
        record = metrics_record(
            target=target,
            task=task,
            started_at=started_at,
            ended_at=ended_at,
            elapsed_ms=elapsed_ms,
            code=code,
            prompt=prompt,
            out=out,
            err=err,
            usage=usage,
            usage_source=usage_source,
            invocation_id=invocation_id,
            parent_session_id=parent_session_id,
            work_item=work_item,
            failure_class="provider" if provider_error or provider_failure_class else ("process" if code != 0 else None),
            provider_failure_class=provider_failure_class,
            risk_category=risk_category,
            thinking_level=thinking_level,
            outcome=outcome,
            human_override=human_override,
            fallback_used=fallback_used,
            invocation_mode="one-shot" if one_shot else "agentic",
        )
    return code, out, err, record
