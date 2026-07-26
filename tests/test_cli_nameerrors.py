from __future__ import annotations

import sys
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))


def test_removed_benchmark_and_session_import_are_not_advertised(agnt, capsys):
    assert agnt.main(["--help"]) == 0
    assert "benchmark" not in capsys.readouterr().out

    assert agnt.cmd_metrics(["--help"]) == 0
    assert "import-session" not in capsys.readouterr().out


def test_removed_session_importer_has_no_deployed_hook():
    assert not (BIN.parent.parent / ".githooks" / "pre-commit").exists()


def test_invoke_eval_records_metrics_without_nameerror(monkeypatch, tmp_path):
    from agnt_lib import evals

    prompt = tmp_path / "prompt.md"
    prompt.write_text("say ok", encoding="utf-8")
    monkeypatch.setattr(evals, "invoke_one", lambda *_args, **_kwargs: (0, "OK", "", {"target": "test/model"}))

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = evals.run_invoke_eval(
        tmp_path / "eval.json", {"prompt": "prompt.md", "task": "review", "defaultModels": ["test/model"]}, out_dir, False, []
    )

    assert result["failures"] == []


def test_prompt_pattern_note_has_timestamp_helper(monkeypatch, tmp_path):
    from agnt_lib import prompt

    monkeypatch.setattr(prompt, "PROMPT_PATTERNS", tmp_path)
    path = prompt.write_pattern_note(
        name="Test pattern", source_url="https://example.com", source_license="MIT", pattern="brief", rewrite="rewrite", notes=None,
    )

    assert path.is_file()
    assert "createdAt:" in path.read_text(encoding="utf-8")
