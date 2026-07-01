from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


class FakeResponse:
    def __init__(self, body: str):
        self.body = body.encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_lessons_capture_writes_redacted_provenance_record(agnt, monkeypatch, tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    monkeypatch.setenv("AGNT_LESSONS_INBOX", str(inbox))
    monkeypatch.setattr(agnt.socket, "gethostname", lambda: "test-host")
    monkeypatch.setitem(agnt.lesson_record.__globals__, "capture", lambda argv: str(tmp_path))

    code = agnt.cmd_lessons([
        "capture",
        "--summary",
        "Provider key leaked in logs",
        "--kind",
        "friction",
        "--area",
        "doctor",
        "--evidence",
        "OPENROUTER_API_KEY=sk-or-secret-value",
        "--tag",
        "provider",
    ])

    assert code == 0
    rows = read_jsonl(inbox)
    assert len(rows) == 1
    row = rows[0]
    assert row["hostname"] == "test-host"
    assert row["project"] == tmp_path.name
    assert row["project_dir"] == str(tmp_path)
    assert row["summary"] == "Provider key leaked in logs"
    assert row["evidence"] == "OPENROUTER_API_KEY=<redacted>"
    assert row["tags"] == ["provider"]


def test_lessons_push_archives_only_after_success(agnt, monkeypatch, tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    archive = tmp_path / "pushed"
    lesson = agnt.lesson_record(summary="Push me", project="pi-setup", project_dir=str(tmp_path))
    inbox.write_text(json.dumps(lesson) + "\n", encoding="utf-8")
    requests = []

    def fake_urlopen(req, timeout=10):
        requests.append(req)
        return FakeResponse('{"accepted":1,"updated":0,"errors":[]}')

    monkeypatch.setattr(agnt.urllib.request, "urlopen", fake_urlopen)

    code = agnt.cmd_lessons(["push", "--url", "https://lessons.example", "--file", str(inbox), "--archive-dir", str(archive)])

    assert code == 0
    assert inbox.read_text(encoding="utf-8") == ""
    archived = list(archive.glob("*.jsonl"))
    assert len(archived) == 1
    assert read_jsonl(archived[0])[0]["uuid"] == lesson["uuid"]
    assert requests[0].full_url == "https://lessons.example/lesson"
    assert requests[0].headers["Content-type"] == "application/x-ndjson"


def test_lessons_push_preserves_inbox_on_failure(agnt, monkeypatch, tmp_path):
    inbox = tmp_path / "inbox.jsonl"
    inbox.write_text(json.dumps(agnt.lesson_record(summary="Do not lose me")) + "\n", encoding="utf-8")

    def fake_urlopen(req, timeout=10):
        raise OSError("network down")

    monkeypatch.setattr(agnt.urllib.request, "urlopen", fake_urlopen)

    code = agnt.cmd_lessons(["push", "--url", "https://lessons.example", "--file", str(inbox)])

    assert code == 1
    assert "Do not lose me" in inbox.read_text(encoding="utf-8")


def test_lessons_pull_writes_jsonl_with_filters(agnt, monkeypatch, tmp_path):
    out = tmp_path / "pulled.jsonl"
    body = json.dumps({"uuid": "11111111-1111-4111-8111-111111111111", "summary": "remote"}) + "\n"
    urls = []

    def fake_urlopen(req, timeout=10):
        urls.append(req.full_url if hasattr(req, "full_url") else str(req))
        return FakeResponse(body)

    monkeypatch.setattr(agnt.urllib.request, "urlopen", fake_urlopen)

    code = agnt.cmd_lessons(["pull", "--url", "https://lessons.example", "--project", "pi-setup", "--limit", "1", "-o", str(out)])

    assert code == 0
    assert read_jsonl(out)[0]["summary"] == "remote"
    assert "project=pi-setup" in urls[0]


def test_lessons_triage_drafts_bead_commands(agnt, tmp_path, capsys):
    inbox = tmp_path / "lessons.jsonl"
    lesson = agnt.lesson_record(summary="Doctor should catch missing node", area="doctor", kind="friction")
    inbox.write_text(json.dumps(lesson) + "\n", encoding="utf-8")

    code = agnt.cmd_lessons(["triage", "--file", str(inbox), "--draft-beads"])

    assert code == 0
    out = capsys.readouterr().out
    assert "bd create" in out
    assert lesson["uuid"] in out
    assert "Doctor should catch missing node" in out
