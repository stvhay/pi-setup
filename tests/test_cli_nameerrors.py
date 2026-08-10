from __future__ import annotations

import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))


def test_improve_command_is_advertised_and_dispatched(agnt, monkeypatch, capsys):
    assert agnt.main(["--help"]) == 0
    assert "improve" in capsys.readouterr().out

    seen = []
    monkeypatch.setattr(agnt, "cmd_improve", lambda args: seen.append(args) or 7)
    assert agnt.main(["improve", "scan", "--dry-run"]) == 7
    assert seen == [["scan", "--dry-run"]]


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


def test_invoke_eval_can_embed_skill_and_assert_output(monkeypatch, tmp_path):
    from agnt_lib import evals

    (tmp_path / "prompt.md").write_text("Emergency pressure scenario", encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("ROOT CAUSE POLICY", encoding="utf-8")
    seen = {}

    def fake_invoke(_target, prompt, **kwargs):
        seen["prompt"] = prompt
        seen["kwargs"] = kwargs
        return 0, "Root cause investigation\nNo edit before evidence", "", None

    monkeypatch.setattr(evals, "invoke_one", fake_invoke)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = evals.run_invoke_eval(
        tmp_path / "eval.json",
        {
            "prompt": "prompt.md",
            "skill": "SKILL.md",
            "defaultModels": ["test/model"],
            "assert": {"contains": ["Root cause investigation"], "notContains": ["I edited production"]},
        },
        out_dir,
        False,
        [],
    )

    assert result["failures"] == []
    assert seen["prompt"].startswith("ROOT CAUSE POLICY")
    assert seen["prompt"].endswith("Emergency pressure scenario")
    assert seen["kwargs"]["one_shot"] is True


def test_invoke_eval_dry_run_materializes_embedded_one_shot_prompt(tmp_path):
    from agnt_lib import evals

    (tmp_path / "prompt.md").write_text("scenario", encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("skill body", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = evals.run_invoke_eval(
        tmp_path / "eval.json",
        {"prompt": "prompt.md", "skill": "SKILL.md", "defaultModels": ["test/model"]},
        out_dir,
        True,
        [],
    )

    worker = result["results"][0]["plannedWorker"]
    assert worker["mode"] == "one-shot"
    assert worker["target"] == "test/model"
    planned_prompt = Path(worker["promptFile"])
    assert planned_prompt.parent == out_dir
    assert planned_prompt.read_text(encoding="utf-8") == "skill body\n\n---\n\nscenario"


def test_prompt_help_omits_pattern_note_import(agnt, capsys):
    with pytest.raises(SystemExit) as exc:
        agnt.cmd_prompt(["--help"])
    assert exc.value.code == 0
    assert "import-pattern-note" not in capsys.readouterr().out
