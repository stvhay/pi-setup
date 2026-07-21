"""Routing feedback: negative outcome history demotes a whole model family."""

import json
import os
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"


def run_route(tmp_path, store_lines):
    store = tmp_path / "agent-invocations.jsonl"
    store.write_text(
        "\n".join(json.dumps(line) for line in store_lines) + "\n", encoding="utf-8"
    )
    env = {**os.environ, "AGNT_METRICS_OUTPUT": str(store)}
    proc = subprocess.run(
        [
            sys.executable,
            str(BIN / "agnt"),
            "route",
            "--task",
            "review",
            "--budget",
            "cheap",
            "--local-ok",
            "--monthly-paid-spend",
            "0",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_negative_history_demotes_every_venue_of_family(tmp_path):
    rejected = [
        {
            "target": "openrouter-localish/google/gemma-4-31b-it",
            "family": "gemma4-31b",
            "outcome": "rejected",
        }
        for _ in range(6)
    ]
    result = run_route(tmp_path, [{"records": rejected}])
    order = result["candidateOrder"]
    gemma_targets = {t for t in order if "gemma-4-31b" in t or "gemma4:31b" in t}
    others = [t for t in order if t not in gemma_targets]
    # Evidence is aggregated by family; every currently eligible Gemma venue
    # receives the same demotion even when the normal policy exposes only one.
    assert gemma_targets
    assert all(order.index(o) < order.index(g) for o in others for g in gemma_targets)
    assert any("demoted" in reason for reason in result["reasons"])
    assert result["selected"] not in gemma_targets


def test_positive_history_does_not_demote(tmp_path):
    accepted = [
        {"target": "ollama/gemma4:31b", "family": "gemma4-31b", "outcome": "accepted"}
        for _ in range(6)
    ]
    result = run_route(tmp_path, [{"records": accepted}])
    assert not any("demoted" in reason for reason in result["reasons"])
    hints = result["metricsHints"]
    assert hints["openrouter-localish/google/gemma-4-31b-it"]["positive"] == 6
