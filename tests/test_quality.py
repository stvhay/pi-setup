from __future__ import annotations

import json
import stat
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / "pi" / "agent" / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

from agnt_lib import quality


def beads_ok(args):
    return 0, {"id": args[1]}, ""


def test_local_invocation_and_result_are_authoritative_and_private(tmp_path):
    linked = quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    recorded = quality.capture_session_outcome(
        "session-1",
        "pi-work.1",
        "success",
        beads_runner=beads_ok,
        directory=tmp_path,
    )

    assert linked == {"schemaVersion": 1, "status": "linked", "beadId": "pi-work.1"}
    assert recorded == {
        "schemaVersion": 1,
        "status": "recorded",
        "beadId": "pi-work.1",
        "outcome": "success",
    }
    assert quality.session_work_item("session-1", directory=tmp_path) == "pi-work.1"
    assert quality.session_handoff_source("session-1", directory=tmp_path) == {
        "beadId": "pi-work.1",
        "outcome": "success",
    }

    ledger = tmp_path / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [row["recordType"] for row in rows] == ["invocation", "result"]
    assert all(set(row) <= {
        "schemaVersion", "recordType", "sessionId", "beadId", "outcome", "evidenceRefs", "capturedAt"
    } for row in rows)
    assert stat.S_IMODE(ledger.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    serialized = ledger.read_text(encoding="utf-8")
    for private in ("prompt", "response", "secret", str(tmp_path.resolve())):
        assert private not in serialized


def test_ledger_appends_without_replacing_or_duplicating_records(tmp_path):
    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    ledger = tmp_path / "ledger.jsonl"
    inode = ledger.stat().st_ino
    first = ledger.read_bytes()

    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    assert ledger.read_bytes() == first

    quality.capture_session_outcome(
        "session-1", "pi-work.1", "success", beads_runner=beads_ok, directory=tmp_path
    )
    assert ledger.stat().st_ino == inode
    assert ledger.read_bytes().startswith(first)
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2
    assert list(tmp_path.glob("*.tmp")) == []


def test_concurrent_capture_keeps_complete_json_lines(tmp_path):
    def capture(index):
        quality.capture_session_link(
            f"session-{index}",
            f"pi-work.{index}",
            beads_runner=beads_ok,
            directory=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(capture, range(20)))

    rows = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert len(rows) == 20
    assert {row["sessionId"] for row in rows} == {f"session-{index}" for index in range(20)}


def test_same_session_rejects_another_bead_before_append(tmp_path):
    quality.capture_session_link(
        "session-1", "pi-first.1", beads_runner=beads_ok, directory=tmp_path
    )
    ledger = tmp_path / "ledger.jsonl"
    before = ledger.read_bytes()

    with pytest.raises(quality.SessionWorkItemConflict, match="another work item"):
        quality.capture_session_link(
            "session-1", "pi-second.1", beads_runner=beads_ok, directory=tmp_path
        )

    assert ledger.read_bytes() == before


def test_missing_and_malformed_local_authority_fail_closed(tmp_path):
    with pytest.raises(quality.SessionUnassigned, match="no linked work item"):
        quality.session_handoff_source("session-1", directory=tmp_path)
    assert not (tmp_path / "ledger.jsonl").exists()

    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    with pytest.raises(quality.SessionOutcomeUnavailable, match="unavailable"):
        quality.session_handoff_source("session-1", directory=tmp_path)

    with (tmp_path / "ledger.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"schemaVersion":1,"recordType":"invocation","sessionId":"session-bad"}\n')
    with pytest.raises(ValueError, match="ledger row"):
        quality.session_work_item("session-1", directory=tmp_path)


def test_capture_rejects_unknown_fields_and_unsafe_evidence(tmp_path):
    base = {
        "schemaVersion": 1,
        "recordType": "invocation",
        "sessionId": "session-1",
        "beadId": "pi-work.1",
        "evidenceRefs": ["trace:abc-123"],
    }
    assert quality.capture(base, beads_runner=beads_ok, directory=tmp_path)["status"] == "linked"

    with pytest.raises(ValueError, match="unknown fields"):
        quality.capture({**base, "prompt": "private body"}, beads_runner=beads_ok, directory=tmp_path)

    for unsafe in (
        "/tmp/private",
        "https://private.example",
        "https:private.example",
        "password" + ":private",
        "s" + "k-privatecredentialvalue",
        "eyJ" + "header123.payload123.signature123",
        "trace:" + "eyJ" + "header123.payload123.signature123",
        "trace:" + "s" + "k-privatecredentialvalue",
        "opaque-reference",
    ):
        with pytest.raises(ValueError, match="evidence"):
            quality.capture(
                {**base, "sessionId": f"session-{len(unsafe)}", "evidenceRefs": [unsafe]},
                beads_runner=beads_ok,
                directory=tmp_path,
            )


@pytest.mark.parametrize("bead_data", [None, {}, {"id": "pi-other.1"}, []])
def test_capture_rejects_malformed_bead_readback_before_append(tmp_path, bead_data):
    with pytest.raises(ValueError, match="could not load work item"):
        quality.capture_session_link(
            "session-1",
            "pi-work.1",
            beads_runner=lambda _args: (0, bead_data, ""),
            directory=tmp_path,
        )

    assert not (tmp_path / "ledger.jsonl").exists()


def test_runtime_env_cannot_redirect_ledger_inside_repository(monkeypatch, tmp_path):
    redirected = tmp_path / "repo-owned"
    resolved = tmp_path / "resolved-private"
    monkeypatch.setenv("AGNT_QUALITY_DIR", str(redirected))
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: resolved)

    quality.capture_session_link("session-1", "pi-work.1", beads_runner=beads_ok)

    assert (resolved / "ledger.jsonl").is_file()
    assert not redirected.exists()


def test_short_append_rolls_back_incomplete_row(monkeypatch, tmp_path):
    quality.capture_session_link(
        "session-1", "pi-work.1", beads_runner=beads_ok, directory=tmp_path
    )
    ledger = tmp_path / "ledger.jsonl"
    before = ledger.read_bytes()
    real_write = quality.os.write

    def short_write(fd, data):
        return real_write(fd, data[:10])

    monkeypatch.setattr(quality.os, "write", short_write)
    with pytest.raises(OSError, match="incomplete"):
        quality.capture_session_outcome(
            "session-1",
            "pi-work.1",
            "success",
            beads_runner=beads_ok,
            directory=tmp_path,
        )

    assert ledger.read_bytes() == before
    assert quality.session_work_item("session-1", directory=tmp_path) == "pi-work.1"


def test_capture_result_requires_exact_schema_and_supported_outcome(tmp_path):
    payload = {
        "schemaVersion": 1,
        "recordType": "result",
        "sessionId": "session-1",
        "beadId": "pi-work.1",
        "outcome": "success",
        "evidenceRefs": [],
    }
    with pytest.raises(quality.SessionUnassigned, match="no linked work item"):
        quality.capture(payload, beads_runner=beads_ok, directory=tmp_path)

    quality.capture(
        {
            "schemaVersion": 1,
            "recordType": "invocation",
            "sessionId": "session-1",
            "beadId": "pi-work.1",
            "evidenceRefs": [],
        },
        beads_runner=beads_ok,
        directory=tmp_path,
    )
    assert quality.capture(payload, beads_runner=beads_ok, directory=tmp_path)["status"] == "recorded"

    with pytest.raises(ValueError, match="outcome"):
        quality.capture(
            {**payload, "sessionId": "session-2", "outcome": "excellent"},
            beads_runner=beads_ok,
            directory=tmp_path,
        )


def test_capture_cli_accepts_only_validated_json(monkeypatch, tmp_path, capsys):
    payload = {
        "schemaVersion": 1,
        "recordType": "invocation",
        "sessionId": "session-private",
        "beadId": "pi-work.1",
        "evidenceRefs": [],
    }
    monkeypatch.setattr(quality, "resolve_runtime_directory", lambda kind: tmp_path)
    monkeypatch.setattr(quality, "_beads", beads_ok)

    assert quality.cmd_quality(["capture", "--payload", json.dumps(payload), "--json"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "linked"
    assert "session-private" not in output

    assert quality.cmd_quality([
        "capture",
        "--payload",
        json.dumps({**payload, "prompt": "private body"}),
        "--json",
    ]) == 2
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "schemaVersion": 1,
        "status": "error",
        "error": "quality capture failed",
    }
    assert "private body" not in output
