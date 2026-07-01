from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "lesson-server" / "app" / "main.py"


def load_lesson_app(monkeypatch):
    monkeypatch.setenv("LESSON_STORE", "memory")
    monkeypatch.setenv("LESSON_ENABLE_TEST_API", "1")
    spec = importlib.util.spec_from_file_location("lesson_server_app", APP_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["lesson_server_app"] = module
    spec.loader.exec_module(module)
    return module.app


def test_post_json_lesson_and_get_jsonl_listing(monkeypatch):
    app = load_lesson_app(monkeypatch)
    client = TestClient(app)
    lesson = {
        "uuid": "11111111-1111-4111-8111-111111111111",
        "date": "2026-07-01T20:00:00Z",
        "hostname": "dev-host",
        "project": "pi-setup",
        "project_dir": "/Users/hays/Projects/pi-setup",
        "kind": "friction",
        "area": "doctor",
        "summary": "Provider failure should stop agent improvisation",
        "evidence": "invoke returned provider error",
        "tags": ["provider", "health"],
        "payload": {"provider": "example"},
    }

    response = client.post("/lesson", json=lesson)

    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    fetched = client.get("/lesson", params={"uuid": lesson["uuid"]})
    assert fetched.status_code == 200
    assert fetched.json()["summary"] == lesson["summary"]
    listing = client.get("/lessons")
    assert listing.status_code == 200
    assert listing.headers["content-type"].startswith("application/x-ndjson")
    rows = [json.loads(line) for line in listing.text.splitlines()]
    assert [row["uuid"] for row in rows] == [lesson["uuid"]]


def test_post_jsonl_upserts_and_patch_lesson(monkeypatch):
    app = load_lesson_app(monkeypatch)
    client = TestClient(app)
    uuid = "22222222-2222-4222-8222-222222222222"
    body = "\n".join(
        [
            json.dumps({"uuid": uuid, "date": "2026-07-01T20:01:00Z", "summary": "first"}),
            json.dumps({"uuid": uuid, "date": "2026-07-01T20:02:00Z", "summary": "second", "status": "new"}),
        ]
    )

    response = client.post("/lesson", content=body, headers={"content-type": "application/x-ndjson"})
    assert response.status_code == 200
    assert response.json()["accepted"] == 2
    assert response.json()["updated"] == 1

    patch = client.patch(f"/lesson?uuid={uuid}", json={"status": "accepted", "tags": ["triaged"]})
    assert patch.status_code == 200
    fetched = client.get("/lesson", params={"uuid": uuid}).json()
    assert fetched["summary"] == "second"
    assert fetched["status"] == "accepted"
    assert fetched["tags"] == ["triaged"]


def test_test_endpoints_are_isolated_from_main_lessons(monkeypatch):
    app = load_lesson_app(monkeypatch)
    client = TestClient(app)
    prod_uuid = "33333333-3333-4333-8333-333333333333"
    test_uuid = "44444444-4444-4444-8444-444444444444"

    client.post("/lesson", json={"uuid": prod_uuid, "date": "2026-07-01T20:03:00Z", "summary": "prod"})
    client.post("/test/lesson", json={"uuid": test_uuid, "date": "2026-07-01T20:04:00Z", "summary": "test"})
    patched = client.patch(f"/test/lesson?uuid={test_uuid}", json={"status": "checked"})

    assert patched.status_code == 200
    assert client.get("/test/lesson", params={"uuid": test_uuid}).json()["status"] == "checked"
    prod_rows = [json.loads(line) for line in client.get("/lessons").text.splitlines()]
    test_rows = [json.loads(line) for line in client.get("/test/lessons").text.splitlines()]
    assert [row["uuid"] for row in prod_rows] == [prod_uuid]
    assert [row["uuid"] for row in test_rows] == [test_uuid]
    logs = client.get("/test/logs")
    assert logs.status_code == 200
    assert logs.json()["testLessonCount"] == 1
