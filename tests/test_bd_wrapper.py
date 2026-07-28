from __future__ import annotations

import os
import subprocess
from pathlib import Path


WRAPPER = Path("pi/agent/bin/bd")


def _fake_bd(tmp_path: Path) -> Path:
    binary = tmp_path / "bin" / "bd"
    binary.parent.mkdir()
    binary.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'before' '- Git authority: no git operations in this context' "
        "'- Git authority: no git operations in this context (different)' 'after'\n"
        "printf 'diagnostic\\n' >&2\n"
        "exit \"${FAKE_EXIT:-0}\"\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def _run(tmp_path: Path, *args: str, exit_code: int = 0) -> subprocess.CompletedProcess[str]:
    assert WRAPPER.is_file()
    fake = _fake_bd(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{fake.parent}:{os.environ['PATH']}",
        "FAKE_EXIT": str(exit_code),
    }
    return subprocess.run([str(WRAPPER), *args], env=env, text=True, capture_output=True, check=False)


def test_prime_removes_only_exact_misleading_git_authority_line(tmp_path):
    result = _run(tmp_path, "prime", exit_code=7)

    assert result.returncode == 7
    assert result.stdout.splitlines() == [
        "before",
        "- Git authority: no git operations in this context (different)",
        "after",
    ]
    assert result.stderr == "diagnostic\n"


def test_non_prime_commands_pass_through_unchanged(tmp_path):
    result = _run(tmp_path, "ready")

    assert result.returncode == 0
    assert "- Git authority: no git operations in this context" in result.stdout
    assert result.stderr == "diagnostic\n"
