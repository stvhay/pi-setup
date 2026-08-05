from __future__ import annotations

import json
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("429: insufficient_quota", "quota"),
        ("OpenrouterException - Key limit exceeded (monthly limit)", "quota"),
        ("HTTP 402: available credits can only cover 505 tokens", "credit"),
        ("insufficient credit balance", "credit"),
        ("401 Unauthorized: invalid API key", "authentication"),
        ("authentication failed for provider", "authentication"),
        ("No API key found for provider", "authentication"),
        ("No auth credentials found", "authentication"),
        ("HTTP 502 Bad Gateway", "availability"),
        ("provider returned HTTP 503", "availability"),
        ("503 Service Unavailable", "availability"),
        ("HTTP 504 Gateway Timeout", "availability"),
        ("pi invocation timed out after 60s", None),
        ("operation cancelled by caller", None),
        ("HTTP 500 internal server error", None),
        ("unknown process failure", None),
    ],
)
def test_provider_failure_classifier_is_deterministic_and_bounded(agnt, message, expected):
    assert agnt.classify_provider_failure(message) == expected


def test_provider_circuit_expires_closes_and_never_stores_raw_error(agnt, tmp_path):
    state = tmp_path / "circuits.json"
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    result = agnt.record_provider_result(
        "olla-cloud",
        error="HTTP 402: SECRET available credits can only cover 505 tokens",
        now=now,
        state_path=state,
    )

    assert result["classification"] == "credit"
    assert result["opened"] is True
    inode = state.stat().st_ino
    active = agnt.active_provider_circuits(now=now, state_path=state)
    assert state.stat().st_ino == inode, "read-only active status must not rewrite unchanged state"
    assert active["olla-cloud"]["reason"] == "credit"
    assert "SECRET" not in state.read_text(encoding="utf-8")
    assert stat.S_IMODE(state.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    inode = state.stat().st_ino
    assert agnt.close_provider_circuit("other-venue", now=now, state_path=state) is False
    assert state.stat().st_ino == inode, "closing an inactive venue must not rewrite state"

    later = now + timedelta(hours=2)
    assert agnt.active_provider_circuits(now=later, state_path=state) == {}
    assert agnt.record_provider_result("olla-cloud", success=True, now=later, state_path=state)["closed"] is False

    agnt.open_provider_circuit("olla-cloud", "quota", now=later, state_path=state)
    assert agnt.record_provider_result("olla-cloud", success=True, now=later, state_path=state)["closed"] is True
    assert agnt.active_provider_circuits(now=later, state_path=state) == {}


@pytest.mark.parametrize(
    ("reason", "seconds"),
    [("quota", 1800), ("credit", 1800), ("authentication", 900), ("availability", 120)],
)
def test_provider_circuit_uses_class_ttl_with_hard_cap(agnt, tmp_path, reason, seconds):
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    record = agnt.open_provider_circuit(reason, reason, now=now, state_path=tmp_path / f"{reason}.json")
    assert datetime.fromisoformat(record["expiresAt"].replace("Z", "+00:00")) - now == timedelta(seconds=seconds)

    capped = agnt.open_provider_circuit("capped", reason, now=now, state_path=tmp_path / "capped.json", ttl_seconds=99_999)
    assert datetime.fromisoformat(capped["expiresAt"].replace("Z", "+00:00")) - now == timedelta(hours=1)


def test_provider_circuit_mutations_are_locked_atomic_and_provider_scoped(agnt, tmp_path):
    state = tmp_path / "circuits.json"
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    providers = [f"venue-{index}" for index in range(24)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda provider: agnt.open_provider_circuit(provider, "availability", now=now, state_path=state), providers))

    active = agnt.active_provider_circuits(now=now, state_path=state)
    assert set(active) == set(providers)
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ValueError):
        agnt.open_provider_circuit("bad/provider", "quota", now=now, state_path=state)


def test_provider_circuit_refuses_symlink_state(agnt, tmp_path):
    victim = tmp_path / "victim.json"
    victim.write_text("do not touch", encoding="utf-8")
    state = tmp_path / "circuits.json"
    state.symlink_to(victim)

    with pytest.raises(OSError):
        agnt.active_provider_circuits(state_path=state)
    assert victim.read_text(encoding="utf-8") == "do not touch"


def test_provider_circuit_cli_records_status_and_success(agnt, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AGNT_PROVIDER_CIRCUIT_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", StringIO("HTTP 503 Service Unavailable"))

    assert agnt.cmd_provider_circuit(["record", "--provider", "olla-cloud"]) == 0
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["classification"] == "availability"
    assert recorded["opened"] is True

    assert agnt.cmd_provider_circuit(["status"]) == 0
    status_result = json.loads(capsys.readouterr().out)
    assert list(status_result["circuits"]) == ["olla-cloud"]

    assert agnt.cmd_provider_circuit(["success", "--provider", "olla-cloud"]) == 0
    success = json.loads(capsys.readouterr().out)
    assert success["closed"] is True


def test_provider_circuit_contract_is_documented():
    readme = (
        Path(__file__).resolve().parents[1]
        / "pi"
        / "agent"
        / "bin"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "agnt provider-circuit status" in readme
    assert "quota, credit, authentication, and availability" in readme
    assert "30 minutes" in readme
    assert "15 minutes" in readme
    assert "2 minutes" in readme
    assert "never stores raw provider errors" in readme


def test_invoke_opens_classified_circuit_and_success_closes_it(agnt, monkeypatch):
    error_event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [],
            "stopReason": "error",
            "errorMessage": "HTTP 402: available credits can only cover 505 tokens",
        },
    }
    success_event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input": 1, "output": 1, "cacheRead": 0, "cacheWrite": 0, "cost": {}},
        },
    }
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout=json.dumps(error_event), stderr=""),
            SimpleNamespace(returncode=0, stdout=json.dumps(success_event), stderr=""),
        ]
    )
    opened = []
    closed = []
    monkeypatch.setitem(agnt.invoke_one.__globals__, "subprocess", SimpleNamespace(
        run=lambda *_args, **_kwargs: next(responses),
        PIPE=-1,
        TimeoutExpired=TimeoutError,
    ))
    monkeypatch.setitem(agnt.invoke_one.__globals__, "open_provider_circuit", lambda provider, reason: opened.append((provider, reason)))
    monkeypatch.setitem(agnt.invoke_one.__globals__, "close_provider_circuit", lambda provider: closed.append(provider))

    code, _out, _err, failed = agnt.invoke_one("olla-cloud/gpt-4.1-mini", "prompt")
    assert code == 1
    assert opened == [("olla-cloud", "credit")]
    assert failed["failureClass"] == "provider"
    assert failed["providerFailureClass"] == "credit"
    assert agnt.compact_metric_record(failed)["providerFailureClass"] == "credit"

    code, out, _err, succeeded = agnt.invoke_one("olla-cloud/gpt-4.1-mini", "prompt")
    assert code == 0
    assert out == "ok"
    assert closed == ["olla-cloud"]
    assert succeeded["providerFailureClass"] is None
