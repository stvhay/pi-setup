from __future__ import annotations

import json
import os
import signal
import subprocess
import textwrap
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eval-workflow-compliance.sh"
BRAINSTORMING_PROMPT = (
    "/skill:brainstorming Design a tiny change that adds CONTRIBUTING.md with a Test Commands "
    "section. Do not edit files. Stop after design and approval question."
)


def _run_eval(
    tmp_path: Path,
    *args: str,
    require_candidate: bool = False,
    env_overrides: dict[str, str] | None = None,
    capture_output: bool = True,
    parent_signal_on_stdout: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "pi.jsonl"
    fake_pi = fake_bin / "pi"
    fake_pi.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import signal
            import subprocess
            import sys
            import time

            args = sys.argv[1:]
            with open(os.environ["FAKE_PI_LOG"], "a", encoding="utf-8") as stream:
                stream.write(json.dumps(args) + "\\n")

            def emit(event):
                print(json.dumps(event), flush=True)

            emit({"type": "session", "version": 3, "id": "fake", "cwd": os.getcwd()})
            emit({"type": "agent_start"})
            activity_seconds = float(os.environ.get("FAKE_PI_ACTIVITY_SECONDS", "0"))
            activity_deadline = time.monotonic() + activity_seconds
            while time.monotonic() < activity_deadline:
                if os.environ.get("FAKE_PI_NON_JSON_ACTIVITY") == "1":
                    print("not-json", flush=True)
                elif os.environ.get("FAKE_PI_JSON_ACTIVITY_TYPE"):
                    emit({"type": os.environ["FAKE_PI_JSON_ACTIVITY_TYPE"]})
                else:
                    emit(
                        {
                            "type": "message_update",
                            "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "."},
                        }
                    )
                time.sleep(0.2)
            sleep_prompt = os.environ.get("FAKE_PI_SLEEP_PROMPT")
            if sleep_prompt and sleep_prompt in args[-1]:
                time.sleep(float(os.environ["FAKE_PI_SLEEP_SECONDS"]))
            if os.environ.get("FAKE_PI_INVALID_UTF8") == "1":
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                with open(os.environ["FAKE_PI_GROUP_PID"], "w", encoding="utf-8") as stream:
                    stream.write(str(os.getpgrp()))
                sys.stdout.buffer.write(b"\\xff\\n")
                sys.stdout.buffer.flush()
                time.sleep(30)
            if os.environ.get("FAKE_PI_SPAWN_TERM_IGNORING_CHILD") == "1":
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        "import os,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                        "time.sleep(float(os.environ['FAKE_PI_CHILD_SLEEP_SECONDS']))",
                    ]
                )
                with open(os.environ["FAKE_PI_CHILD_PID"], "w", encoding="utf-8") as stream:
                    stream.write(str(child.pid))
                if os.environ.get("FAKE_PI_RETURN_WITH_CHILD") != "1":
                    time.sleep(30)
            if os.environ.get("FAKE_PI_SIGNAL_WRAPPER") == "1":
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                with open(os.environ["FAKE_PI_GROUP_PID"], "w", encoding="utf-8") as stream:
                    stream.write(str(os.getpgrp()))
                time.sleep(0.1)
                wrapper_signal = getattr(signal, os.environ.get("FAKE_PI_WRAPPER_SIGNAL", "SIGTERM"))
                os.kill(int(os.environ["WORKFLOW_EVAL_WRAPPER_PID"]), wrapper_signal)
                time.sleep(30)
            if os.environ.get("FAKE_PI_SIGNAL_PARENT") == "1":
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                with open(os.environ["FAKE_PI_GROUP_PID"], "w", encoding="utf-8") as stream:
                    stream.write(str(os.getpgrp()))
                time.sleep(0.1)
                os.kill(int(os.environ["WORKFLOW_EVAL_PARENT_PID"]), signal.SIGTERM)
                time.sleep(30)
            if os.environ.get("FAKE_PI_RECORD_GROUP") == "1":
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                with open(os.environ["FAKE_PI_GROUP_PID"], "w", encoding="utf-8") as stream:
                    stream.write(str(os.getpgrp()))
                time.sleep(30)
            candidate = "--no-skills" in args and "--skill" in args
            if os.environ.get("FAKE_PI_REQUIRE_CANDIDATE") == "1" and not candidate:
                text = "No candidate behavior was loaded."
            else:
                text = "Stop for approval before implementation."
            message = {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
                "stopReason": "stop",
                "usage": {"input": 1, "output": 1, "totalTokens": 2},
            }
            emit({"type": "message_end", "message": message})
            emit({"type": "agent_end", "messages": [message]})
            """
        ),
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    fake_date = fake_bin / "date"
    fake_date.write_text("#!/bin/sh\nprintf '20260101-000000\\n'\n", encoding="utf-8")
    fake_date.chmod(0o755)
    output_root = tmp_path / "runs"
    real_deployed_agent = tmp_path / "real-deployed-agent"
    (real_deployed_agent / "skills").mkdir(parents=True, exist_ok=True)
    deployed_agent = tmp_path / "deployed-agent"
    if not deployed_agent.exists():
        deployed_agent.symlink_to(real_deployed_agent, target_is_directory=True)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_PI_LOG": str(log),
        "FAKE_PI_REQUIRE_CANDIDATE": "1" if require_candidate else "0",
        "OUT_ROOT": str(output_root),
        "PI_CODING_AGENT_DIR": str(deployed_agent),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "commit.gpgsign",
        "GIT_CONFIG_VALUE_0": "false",
    }
    env.update(env_overrides or {})
    command = ["bash", str(SCRIPT), *args]
    if parent_signal_on_stdout is None:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=capture_output,
            check=False,
        )
    else:
        assert capture_output
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_lines = []
        assert process.stdout is not None
        for line in process.stdout:
            stdout_lines.append(line)
            if parent_signal_on_stdout in line:
                os.kill(process.pid, signal.SIGTERM)
                break
        stdout, stderr = process.communicate(timeout=10)
        result = subprocess.CompletedProcess(command, process.returncode, "".join(stdout_lines) + stdout, stderr)
    return result, log, output_root


def _single_invocation(log: Path) -> list[str]:
    rows = log.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    return json.loads(rows[0])


def _provenance(output_root: Path) -> dict[str, str]:
    paths = list(output_root.glob("*/provenance.txt"))
    assert len(paths) == 1
    return dict(line.split("=", 1) for line in paths[0].read_text(encoding="utf-8").splitlines())


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _process_group_exists(group_id: int) -> bool:
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_until_gone(check, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while check() and time.monotonic() < deadline:
        time.sleep(0.02)
    return not check()


def test_workflow_eval_requires_explicit_skill_mode_before_pi_invocation(tmp_path):
    result, log, output_root = _run_eval(tmp_path, "--case", "brainstorming_no_write")

    assert result.returncode == 2
    assert "--skill-mode is required" in result.stderr
    assert not log.exists()
    assert not output_root.exists()


def test_workflow_eval_list_remains_mode_free():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--list"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "brainstorming_no_write" in result.stdout
    assert "skill-mode" not in result.stderr


def test_workflow_eval_rejects_duplicate_cases_before_pi_invocation(tmp_path):
    result, log, _output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        "--case",
        "brainstorming_no_write",
    )

    assert result.returncode == 2
    assert "Duplicate case: brainstorming_no_write" in result.stderr
    assert not log.exists()


def test_workflow_eval_rejects_leading_zero_timeout(tmp_path):
    result, _log, _output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        env_overrides={"WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "08"},
    )

    assert result.returncode == 2
    assert "must not contain a leading zero" in result.stderr


def test_candidate_mode_loads_tracked_skills_and_preserves_prompt_and_tools(tmp_path):
    result, log, output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
    )

    assert result.returncode == 0, result.stderr
    args = _single_invocation(log)
    assert args[-1] == BRAINSTORMING_PROMPT
    assert args[args.index("--mode") + 1] == "json"
    assert "--print" not in args
    assert "--no-skills" in args
    assert args[args.index("--skill") + 1] == str(ROOT / "pi" / "agent" / "skills")
    assert {"--no-extensions", "--no-context-files", "--no-prompt-templates"} <= set(args)
    assert "--no-tools" not in args
    assert "--tools" not in args
    assert _provenance(output_root) == {
        "schemaVersion": "1",
        "skillMode": "candidate",
        "skillRoot": str(ROOT / "pi" / "agent" / "skills"),
        "ambientDiscovery": "false",
    }
    assert "Skill mode: candidate" in result.stdout
    assert f"Skill root: {ROOT / 'pi' / 'agent' / 'skills'}" in result.stdout


def test_deployed_mode_is_explicit_and_preserves_ambient_pi_invocation(tmp_path):
    result, log, output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "deployed",
        "--case",
        "brainstorming_no_write",
    )

    assert result.returncode == 0, result.stderr
    args = _single_invocation(log)
    assert args[-1] == BRAINSTORMING_PROMPT
    for option in ("--no-skills", "--skill", "--no-extensions", "--no-context-files", "--no-prompt-templates"):
        assert option not in args
    assert _provenance(output_root) == {
        "schemaVersion": "1",
        "skillMode": "deployed",
        "skillRoot": str(tmp_path / "real-deployed-agent" / "skills"),
        "ambientDiscovery": "true",
    }
    assert "Skill mode: deployed" in result.stdout


def test_case_reports_start_completion_and_elapsed_time(tmp_path):
    result, _log, _output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
    )

    assert result.returncode == 0, result.stderr
    assert "Case timeout: 300s" in result.stdout
    assert "Idle timeout: 60s" in result.stdout
    assert "Declared runtime bound: 302s" in result.stdout
    assert "START brainstorming_no_write" in result.stdout
    assert "COMPLETE brainstorming_no_write status=PASS elapsed=" in result.stdout


def test_active_case_can_exceed_idle_timeout(tmp_path):
    result, _log, output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        env_overrides={
            "WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "5",
            "WORKFLOW_EVAL_IDLE_TIMEOUT_SECONDS": "1",
            "FAKE_PI_ACTIVITY_SECONDS": "2",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "ACTIVITY brainstorming_no_write" in result.stderr
    run_dirs = [path for path in output_root.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    assert '"type": "message_update"' in (run_dirs[0] / "brainstorming_no_write.events.jsonl").read_text()


def test_supported_retry_events_reset_idle_timeout(tmp_path):
    result, _log, _output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        env_overrides={
            "WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "5",
            "WORKFLOW_EVAL_IDLE_TIMEOUT_SECONDS": "1",
            "FAKE_PI_ACTIVITY_SECONDS": "2",
            "FAKE_PI_JSON_ACTIVITY_TYPE": "auto_retry_start",
        },
    )

    assert result.returncode == 0, result.stderr


def test_non_json_chatter_does_not_reset_idle_timeout(tmp_path):
    started_at = time.monotonic()
    result, _log, _output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        env_overrides={
            "WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "5",
            "WORKFLOW_EVAL_IDLE_TIMEOUT_SECONDS": "1",
            "FAKE_PI_ACTIVITY_SECONDS": "3",
            "FAKE_PI_NON_JSON_ACTIVITY": "1",
        },
    )
    elapsed = time.monotonic() - started_at

    assert result.returncode == 124
    assert elapsed < 4.5
    assert "TIMEOUT brainstorming_no_write: idle for 1s" in result.stderr


def test_unknown_json_chatter_does_not_reset_idle_timeout(tmp_path):
    started_at = time.monotonic()
    result, _log, _output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        env_overrides={
            "WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "5",
            "WORKFLOW_EVAL_IDLE_TIMEOUT_SECONDS": "1",
            "FAKE_PI_ACTIVITY_SECONDS": "3",
            "FAKE_PI_JSON_ACTIVITY_TYPE": "not_a_pi_event",
        },
    )
    elapsed = time.monotonic() - started_at

    assert result.returncode == 124
    assert elapsed < 4.5
    assert "TIMEOUT brainstorming_no_write: idle for 1s" in result.stderr


def test_invalid_utf8_times_out_and_cleans_case_group(tmp_path):
    group_file = tmp_path / "group.pid"
    group_id = None
    try:
        result, _log, _output_root = _run_eval(
            tmp_path,
            "--skill-mode",
            "candidate",
            "--case",
            "brainstorming_no_write",
            env_overrides={
                "WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "5",
                "WORKFLOW_EVAL_IDLE_TIMEOUT_SECONDS": "1",
                "FAKE_PI_INVALID_UTF8": "1",
                "FAKE_PI_GROUP_PID": str(group_file),
            },
        )
        group_id = int(group_file.read_text())

        assert result.returncode == 124
        assert "TIMEOUT brainstorming_no_write: idle for 1s" in result.stderr
        assert _wait_until_gone(lambda: _process_group_exists(group_id))
    finally:
        if group_id is not None and _process_group_exists(group_id):
            os.killpg(group_id, signal.SIGKILL)


def test_stalled_case_times_out_and_preserves_completed_results(tmp_path):
    result, _log, output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        "--case",
        "writing_plans_creates_plan",
        env_overrides={
            "WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "5",
            "WORKFLOW_EVAL_IDLE_TIMEOUT_SECONDS": "1",
            "FAKE_PI_SLEEP_PROMPT": "Approved design",
            "FAKE_PI_SLEEP_SECONDS": "2",
        },
    )

    assert result.returncode == 124
    assert "COMPLETE brainstorming_no_write status=PASS elapsed=" in result.stdout
    assert "START writing_plans_creates_plan" in result.stdout
    assert "COMPLETE writing_plans_creates_plan status=TIMEOUT elapsed=" in result.stdout
    assert "TIMEOUT writing_plans_creates_plan: idle for 1s" in result.stderr
    assert "lastEvent=" in result.stderr
    assert "provider/model=openai-codex/gpt-5.6-luna" in result.stderr
    assert "writing_plans_creates_plan.events.jsonl" in result.stderr
    run_dirs = [path for path in output_root.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    assert "Stop for approval" in (run_dirs[0] / "brainstorming_no_write.out").read_text()


def test_timeout_kills_term_ignoring_case_descendant(tmp_path):
    pid_file = tmp_path / "child.pid"
    child_pid = None
    try:
        started_at = time.monotonic()
        result, _log, _output_root = _run_eval(
            tmp_path,
            "--skill-mode",
            "candidate",
            "--case",
            "brainstorming_no_write",
            env_overrides={
                "WORKFLOW_EVAL_CASE_TIMEOUT_SECONDS": "5",
                "WORKFLOW_EVAL_IDLE_TIMEOUT_SECONDS": "1",
                "FAKE_PI_SPAWN_TERM_IGNORING_CHILD": "1",
                "FAKE_PI_CHILD_PID": str(pid_file),
                "FAKE_PI_CHILD_SLEEP_SECONDS": "5",
            },
        )
        elapsed = time.monotonic() - started_at
        child_pid = int(pid_file.read_text())

        assert result.returncode == 124
        assert elapsed < 4.5
        assert _wait_until_gone(lambda: _pid_exists(child_pid))
    finally:
        if child_pid is not None and _pid_exists(child_pid):
            os.kill(child_pid, signal.SIGKILL)


def test_successful_case_kills_term_ignoring_descendant(tmp_path):
    pid_file = tmp_path / "child.pid"
    child_pid = None
    try:
        started_at = time.monotonic()
        result, _log, _output_root = _run_eval(
            tmp_path,
            "--skill-mode",
            "candidate",
            "--case",
            "brainstorming_no_write",
            env_overrides={
                "FAKE_PI_SPAWN_TERM_IGNORING_CHILD": "1",
                "FAKE_PI_RETURN_WITH_CHILD": "1",
                "FAKE_PI_CHILD_PID": str(pid_file),
                "FAKE_PI_CHILD_SLEEP_SECONDS": "5",
            },
        )
        elapsed = time.monotonic() - started_at
        child_pid = int(pid_file.read_text())

        assert result.returncode == 0, result.stderr
        assert elapsed < 4.5
        assert _wait_until_gone(lambda: _pid_exists(child_pid))
    finally:
        if child_pid is not None and _pid_exists(child_pid):
            os.kill(child_pid, signal.SIGKILL)


def test_wrapper_signal_kills_detached_case_group(tmp_path):
    group_file = tmp_path / "group.pid"
    group_id = None
    try:
        result, _log, _output_root = _run_eval(
            tmp_path,
            "--skill-mode",
            "candidate",
            "--case",
            "brainstorming_no_write",
            env_overrides={
                "FAKE_PI_SIGNAL_WRAPPER": "1",
                "FAKE_PI_GROUP_PID": str(group_file),
            },
            capture_output=False,
        )
        group_id = int(group_file.read_text())

        assert result.returncode == 143
        assert _wait_until_gone(lambda: _process_group_exists(group_id))
    finally:
        if group_id is not None and _process_group_exists(group_id):
            os.killpg(group_id, signal.SIGKILL)


def test_wrapper_hup_kills_detached_case_group(tmp_path):
    group_file = tmp_path / "group.pid"
    group_id = None
    try:
        result, _log, _output_root = _run_eval(
            tmp_path,
            "--skill-mode",
            "candidate",
            "--case",
            "brainstorming_no_write",
            env_overrides={
                "FAKE_PI_SIGNAL_WRAPPER": "1",
                "FAKE_PI_WRAPPER_SIGNAL": "SIGHUP",
                "FAKE_PI_GROUP_PID": str(group_file),
            },
            capture_output=False,
        )
        group_id = int(group_file.read_text())

        assert result.returncode == 129
        assert _wait_until_gone(lambda: _process_group_exists(group_id))
    finally:
        if group_id is not None and _process_group_exists(group_id):
            os.killpg(group_id, signal.SIGKILL)


def test_parent_signal_during_case_start_does_not_leave_worker(tmp_path):
    group_file = tmp_path / "group.pid"
    group_id = None
    started_at = time.monotonic()
    try:
        result, _log, _output_root = _run_eval(
            tmp_path,
            "--skill-mode",
            "candidate",
            "--case",
            "brainstorming_no_write",
            env_overrides={
                "FAKE_PI_RECORD_GROUP": "1",
                "FAKE_PI_GROUP_PID": str(group_file),
            },
            parent_signal_on_stdout="START brainstorming_no_write",
        )
        elapsed = time.monotonic() - started_at
        if group_file.exists():
            group_id = int(group_file.read_text())

        assert result.returncode == 143
        assert elapsed < 5
        assert group_id is None or _wait_until_gone(lambda: _process_group_exists(group_id))
    finally:
        if group_id is not None and _process_group_exists(group_id):
            os.killpg(group_id, signal.SIGKILL)


def test_parent_signal_kills_all_detached_case_groups(tmp_path):
    group_file = tmp_path / "group.pid"
    group_id = None
    try:
        result, _log, _output_root = _run_eval(
            tmp_path,
            "--skill-mode",
            "candidate",
            "--case",
            "brainstorming_no_write",
            env_overrides={
                "FAKE_PI_SIGNAL_PARENT": "1",
                "FAKE_PI_GROUP_PID": str(group_file),
            },
            capture_output=False,
        )
        group_id = int(group_file.read_text())

        assert result.returncode == 143
        assert _wait_until_gone(lambda: _process_group_exists(group_id))
    finally:
        if group_id is not None and _process_group_exists(group_id):
            os.killpg(group_id, signal.SIGKILL)


def test_same_second_runs_get_distinct_provenance_directories(tmp_path):
    first, _first_log, output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
    )
    second, _second_log, _same_output_root = _run_eval(
        tmp_path,
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
    )

    assert first.returncode == second.returncode == 0
    run_dirs = [path for path in output_root.iterdir() if path.is_dir()]
    assert len(run_dirs) == 2
    assert all("skillMode=candidate" in (path / "provenance.txt").read_text() for path in run_dirs)


def test_candidate_only_behavior_cannot_pass_as_deployed_evidence(tmp_path):
    candidate, _candidate_log, _candidate_output = _run_eval(
        tmp_path / "candidate",
        "--skill-mode",
        "candidate",
        "--case",
        "brainstorming_no_write",
        require_candidate=True,
    )
    deployed, _deployed_log, _deployed_output = _run_eval(
        tmp_path / "deployed",
        "--skill-mode",
        "deployed",
        "--case",
        "brainstorming_no_write",
        require_candidate=True,
    )

    assert candidate.returncode == 0, candidate.stderr
    assert deployed.returncode != 0
    assert "output did not appear to stop for approval" in deployed.stderr
