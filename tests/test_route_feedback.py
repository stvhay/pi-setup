"""Routing feedback: outcome history follows model families across venues."""

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
    env = {
        **os.environ,
        "AGNT_METRICS_OUTPUT": str(store),
        "AGNT_PROVIDER_CIRCUIT_DIR": str(tmp_path / "provider-circuits"),
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(BIN / "agnt"),
            "route",
            "--task",
            "review",
            "--budget",
            "cheap",
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


def test_negative_history_transfers_from_dormant_to_active_venue(tmp_path):
    rejected = [
        {
            "target": "olla-cloud/kimi-k2.7-code",
            "family": "kimi-k2.7-code",
            "outcome": "rejected",
        }
        for _ in range(6)
    ]
    result = run_route(tmp_path, [{"records": rejected}])
    target = "openrouter/moonshotai/kimi-k2.7-code"

    assert target in result["candidateOrder"]
    assert result["candidateOrder"].index(target) == len(result["candidateOrder"]) - 1
    assert any("demoted" in reason for reason in result["reasons"])
    assert result["selected"] != target


def test_open_provider_circuit_excludes_only_direct_openrouter(tmp_path):
    env = {
        **os.environ,
        "AGNT_PROVIDER_CIRCUIT_DIR": str(tmp_path / "provider-circuits"),
    }
    opened = subprocess.run(
        [sys.executable, str(BIN / "agnt"), "provider-circuit", "record", "--provider", "openrouter"],
        input="HTTP 402: available credits can only cover 505 tokens",
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
    )
    assert opened.returncode == 0, opened.stderr

    result = run_route(tmp_path, [])
    assert all(not target.startswith("openrouter/") for target in result["candidateOrder"])
    blocked = [item for item in result["rejectedCandidates"] if item["target"].startswith("openrouter/")]
    assert blocked
    assert all("provider circuit open: credit until " in item["reason"] for item in blocked)
    assert any(target.startswith("openai-codex/") for target in result["candidateOrder"])

    closed = subprocess.run(
        [sys.executable, str(BIN / "agnt"), "provider-circuit", "success", "--provider", "openrouter"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
    )
    assert closed.returncode == 0, closed.stderr
    assert any(target.startswith("openrouter/") for target in run_route(tmp_path, [])["candidateOrder"])


def test_positive_history_transfers_from_dormant_to_active_venue(tmp_path):
    accepted = [
        {
            "target": "olla-cloud/kimi-k2.7-code",
            "family": "kimi-k2.7-code",
            "outcome": "accepted",
        }
        for _ in range(6)
    ]
    result = run_route(tmp_path, [{"records": accepted}])
    assert not any("demoted" in reason for reason in result["reasons"])
    hints = result["metricsHints"]
    assert hints["openrouter/moonshotai/kimi-k2.7-code"]["positive"] == 6
