from __future__ import annotations

import json
import sys

import pytest
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib import runner_protocol as rp


def test_runtime_paths_are_project_local_and_service_metadata_redacts_token(tmp_path):
    root = tmp_path / "project"
    root.mkdir()

    paths = rp.runner_paths(root)
    assert paths["runnerDir"] == root / ".pi" / "runner"
    assert paths["servicePath"] == root / ".pi" / "runner" / "service.json"
    assert paths["tokenPath"] == root / ".pi" / "runner" / "token"
    assert paths["statePath"] == root / ".pi" / "runner" / "state.json"
    assert paths["lockPath"] == root / ".pi" / "runner" / "lock.json"
    assert paths["eventsPath"] == root / ".pi" / "runner" / "events.jsonl"
    assert paths["activeDir"] == root / ".pi" / "runner" / "active"

    saved = rp.save_service_metadata(
        root,
        {
            "pid": 1234,
            "port": 49152,
            "token": "secret-token-value",
            "startedAt": "2026-07-09T00:00:00Z",
        },
    )

    assert saved["schemaVersion"] == 1
    assert saved["apiVersion"] == rp.API_VERSION
    assert saved["root"] == str(root)
    assert saved["tokenPath"] == str(root / ".pi" / "runner" / "token")
    assert "token" not in saved

    loaded = rp.load_service_metadata(root)
    assert loaded["pid"] == 1234
    assert loaded["port"] == 49152

    redacted = rp.redact_service_metadata({**loaded, "token": "another-secret"})
    encoded = json.dumps(redacted)
    assert "another-secret" not in encoded
    assert redacted["token"] == "<redacted>"
    assert redacted["tokenPath"] == str(root / ".pi" / "runner" / "token")


def test_write_runner_state_replaces_atomically(tmp_path, monkeypatch):
    calls = []
    original_replace = rp.os.replace

    def recording_replace(source, destination):
        calls.append((Path(source), Path(destination)))
        return original_replace(source, destination)

    monkeypatch.setattr(rp.os, "replace", recording_replace)
    saved = rp.write_runner_state(tmp_path, {"paused": True})

    assert saved["paused"] is True
    assert rp.runner_paths(tmp_path)["statePath"].is_file()
    assert calls and calls[0][1] == rp.runner_paths(tmp_path)["statePath"]


def test_corrupt_runner_state_is_visible_and_never_reinitialized_by_a_write(tmp_path):
    path = rp.runner_paths(tmp_path)["statePath"]
    path.parent.mkdir(parents=True)
    path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(rp.RunnerStateCorruptionError, match="invalid runner state"):
        rp.update_runner_state(tmp_path, lambda state: state)

    assert path.read_text(encoding="utf-8") == "{not json}\n"


def test_update_runner_state_serializes_changes_against_latest_persisted_state(tmp_path):
    rp.write_runner_state(tmp_path, {"paused": False, "scheduler": {"lastTickOutcome": "completed"}})

    saved = rp.update_runner_state(
        tmp_path,
        lambda current: {**current, "paused": True, "pauseReason": "operator"},
    )

    assert saved["paused"] is True
    assert saved["scheduler"] == {"lastTickOutcome": "completed"}
    persisted = json.loads(rp.runner_paths(tmp_path)["statePath"].read_text(encoding="utf-8"))
    assert persisted["pauseReason"] == "operator"


def test_runner_state_normalization_preserves_existing_fields_and_defaults():
    state = rp.normalize_runner_state(
        {
            "paused": True,
            "pauseReason": "maintenance",
            "updatedAt": "2026-07-09T00:00:00Z",
            "custom": "keep-me",
        }
    )

    assert state["schemaVersion"] == 1
    assert state["paused"] is True
    assert state["pauseReason"] == "maintenance"
    assert state["draining"] is False
    assert state["acceptingNewWork"] is False
    assert state["leases"] == {}
    assert state["activeRuns"] == []
    assert state["budget"]["mode"] == "placeholder"
    assert state["budget"]["limitsEnforced"] is False
    assert state["budget"]["cost"] == {"usd": None, "source": "unknown"}
    assert state["budget"]["context"] == {"used": None, "limit": None, "percent": None, "source": "unknown"}
    assert {"cost-unknown", "context-unknown"}.issubset(set(state["budget"]["warnings"]))
    assert state["custom"] == "keep-me"


def test_runner_state_migrates_legacy_ttl_lease_to_informational_client_record():
    state = rp.normalize_runner_state({
        "leases": {
            "pi-stale": {
                "leaseId": "pi-stale",
                "sessionId": "pi-stale",
                "client": "pi-tui",
                "attachedAt": "2026-07-09T00:00:00Z",
                "ttlSeconds": 300,
                "expiresAt": "2026-07-09T00:05:00Z",
            }
        }
    })

    lease = state["leases"]["pi-stale"]
    assert lease["lastSeenAt"] == "2026-07-09T00:00:00Z"
    assert "ttlSeconds" not in lease
    assert "expiresAt" not in lease


def test_lease_normalization_records_connection_identity_without_ttl_watchdog():
    lease = rp.normalize_lease(
        {"sessionId": "pi-session-1", "client": "pi-tui", "ttlSeconds": 120},
        now="2026-07-09T00:00:00Z",
    )

    assert lease["schemaVersion"] == 1
    assert lease["leaseId"] == "pi-session-1"
    assert lease["sessionId"] == "pi-session-1"
    assert lease["client"] == "pi-tui"
    assert lease["attachedAt"] == "2026-07-09T00:00:00Z"
    assert lease["lastSeenAt"] == "2026-07-09T00:00:00Z"
    assert "ttlSeconds" not in lease
    assert "expiresAt" not in lease


def test_active_run_snapshot_summary_is_compact_and_stable(tmp_path):
    snapshot = rp.normalize_active_run_snapshot(
        {
            "bead": "pi-2m1.1",
            "title": "Define runner protocol and runtime state contracts",
            "epicId": "pi-2m1",
            "runId": "runner-pi-2m1.1-20260709120000",
            "status": "running",
            "model": "openai-codex/gpt-5.6-sol",
            "thinkingLevel": "medium",
            "context": {"used": 1000, "limit": 2000},
            "cost": {"usd": 0.25, "source": "metrics"},
            "bundle": str(tmp_path / ".pi" / "runs" / "runner-pi-2m1.1"),
            "blockers": ["waiting for test"],
            "extra": "preserved",
        }
    )

    assert snapshot["schemaVersion"] == 1
    assert snapshot["slug"] == "define-runner-protocol-and-runtime-state"
    assert snapshot["context"] == {"used": 1000, "limit": 2000, "percent": 50.0}
    assert snapshot["cost"] == {"usd": 0.25, "source": "metrics"}
    assert snapshot["blockers"] == ["waiting for test"]
    assert snapshot["extra"] == "preserved"

    summary = rp.active_run_summary(snapshot)
    assert summary == {
        "bead": "pi-2m1.1",
        "slug": "define-runner-protocol-and-runtime-state",
        "epicId": "pi-2m1",
        "runId": "runner-pi-2m1.1-20260709120000",
        "status": "running",
        "model": "openai-codex/gpt-5.6-sol",
        "thinkingLevel": "medium",
        "context": {"used": 1000, "limit": 2000, "percent": 50.0},
        "cost": {"usd": 0.25, "source": "metrics"},
        "bundle": str(tmp_path / ".pi" / "runs" / "runner-pi-2m1.1"),
        "blockers": ["waiting for test"],
    }


def test_runner_events_append_and_read_by_line_offset(tmp_path):
    first = rp.append_runner_event(tmp_path, {"type": "started", "runId": "run-1"}, now="2026-07-09T00:00:00Z")
    second = rp.append_runner_event(tmp_path, {"type": "finished", "runId": "run-1"}, now="2026-07-09T00:01:00Z")

    assert first["offset"] == 0
    assert second["offset"] == 1

    all_events = rp.read_runner_events(tmp_path)
    assert all_events["nextOffset"] == 2
    assert [event["type"] for event in all_events["events"]] == ["started", "finished"]

    later_events = rp.read_runner_events(tmp_path, since=1)
    assert later_events["nextOffset"] == 2
    assert [event["type"] for event in later_events["events"]] == ["finished"]
