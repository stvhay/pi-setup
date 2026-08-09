from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eval-workflow-compliance.sh"
BRAINSTORMING_PROMPT = (
    "/skill:brainstorming Design a tiny change that adds CONTRIBUTING.md with a Test Commands "
    "section. Do not edit files. Stop after design and approval question."
)


def _run_eval(tmp_path: Path, *args: str, require_candidate: bool = False) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
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
            import sys

            args = sys.argv[1:]
            with open(os.environ["FAKE_PI_LOG"], "a", encoding="utf-8") as stream:
                stream.write(json.dumps(args) + "\\n")
            candidate = "--no-skills" in args and "--skill" in args
            if os.environ.get("FAKE_PI_REQUIRE_CANDIDATE") == "1" and not candidate:
                print("No candidate behavior was loaded.")
            else:
                print("Stop for approval before implementation.")
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
    result = subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, log, output_root


def _single_invocation(log: Path) -> list[str]:
    rows = log.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    return json.loads(rows[0])


def _provenance(output_root: Path) -> dict[str, str]:
    paths = list(output_root.glob("*/provenance.txt"))
    assert len(paths) == 1
    return dict(line.split("=", 1) for line in paths[0].read_text(encoding="utf-8").splitlines())


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
