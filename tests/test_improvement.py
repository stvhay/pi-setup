from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pi" / "agent" / "bin"))

from agnt_lib.langfuse import LangfuseClient


class FakeTelemetryClient(LangfuseClient):
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def _request(self, method: str, path: str, body=None, params=None):
        self.calls.append((method, path, dict(params or {})))
        return self.responses.pop(0)


def test_observation_reads_are_time_bounded_and_stop_at_limit():
    client = FakeTelemetryClient([
        {"data": [{"id": "one"}, {"id": "two"}], "meta": {"page": 1, "totalPages": 2}},
        {"data": [{"id": "three"}, {"id": "ignored"}], "meta": {"page": 2, "totalPages": 2}},
    ])

    rows = client.list_observations(
        from_start_time="2026-07-26T00:00:00Z",
        to_start_time="2026-07-27T00:00:00Z",
        limit=3,
        page_size=2,
    )

    assert [row["id"] for row in rows] == ["one", "two", "three"]
    assert client.calls == [
        (
            "GET",
            "/api/public/observations",
            {
                "fromStartTime": "2026-07-26T00:00:00Z",
                "toStartTime": "2026-07-27T00:00:00Z",
                "limit": 2,
                "page": 1,
            },
        ),
        (
            "GET",
            "/api/public/observations",
            {
                "fromStartTime": "2026-07-26T00:00:00Z",
                "toStartTime": "2026-07-27T00:00:00Z",
                "limit": 1,
                "page": 2,
            },
        ),
    ]


def test_observation_reads_reject_missing_bounds_or_nonpositive_limits():
    client = FakeTelemetryClient([])

    with pytest.raises(ValueError, match="time bounds"):
        client.list_observations(from_start_time="", to_start_time="2026-07-27T00:00:00Z", limit=1)
    with pytest.raises(ValueError, match="positive"):
        client.list_observations(from_start_time="2026-07-26T00:00:00Z", to_start_time="2026-07-27T00:00:00Z", limit=0)

    assert client.calls == []


def test_trace_reads_are_time_bounded_and_paginated():
    client = FakeTelemetryClient([
        {"data": [{"id": "first"}], "meta": {"page": 1, "totalPages": 2}},
        {"data": [{"id": "second"}], "meta": {"page": 2, "totalPages": 2}},
    ])

    rows = client.list_traces(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        limit=2,
        page_size=1,
    )

    assert [row["id"] for row in rows] == ["first", "second"]
    assert client.calls == [
        (
            "GET",
            "/api/public/traces",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "limit": 1,
                "page": 1,
            },
        ),
        (
            "GET",
            "/api/public/traces",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "limit": 1,
                "page": 2,
            },
        ),
    ]


def test_score_reads_follow_cursor_and_stop_at_limit():
    client = FakeTelemetryClient([
        {"data": [{"id": "one"}, {"id": "two"}], "meta": {"cursor": "next"}},
        {"data": [{"id": "three"}], "meta": {"cursor": None}},
    ])

    rows = client.list_scores(
        from_timestamp="2026-07-26T00:00:00Z",
        to_timestamp="2026-07-27T00:00:00Z",
        limit=3,
        page_size=2,
        name="improvement_review_status",
    )

    assert [row["id"] for row in rows] == ["one", "two", "three"]
    assert client.calls == [
        (
            "GET",
            "/api/public/v3/scores",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "fields": "details,subject",
                "name": "improvement_review_status",
                "limit": 2,
            },
        ),
        (
            "GET",
            "/api/public/v3/scores",
            {
                "fromTimestamp": "2026-07-26T00:00:00Z",
                "toTimestamp": "2026-07-27T00:00:00Z",
                "fields": "details,subject",
                "name": "improvement_review_status",
                "limit": 1,
                "cursor": "next",
            },
        ),
    ]
