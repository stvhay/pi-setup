from __future__ import annotations

import json
import os
import uuid as uuid_lib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Iterable

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


MAIN_TABLE = "lessons"
TEST_TABLE = "test_lessons"


class Lesson(BaseModel):
    model_config = ConfigDict(extra="allow")

    uuid: str
    date: datetime
    hostname: str | None = None
    project: str | None = None
    project_dir: str | None = None
    kind: str | None = None
    area: str | None = None
    summary: str
    evidence: str | None = None
    status: str = "new"
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("uuid")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        return str(uuid_lib.UUID(value))

    @field_validator("date")
    @classmethod
    def normalize_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


PATCHABLE_FIELDS = {
    "date",
    "hostname",
    "project",
    "project_dir",
    "kind",
    "area",
    "summary",
    "evidence",
    "status",
    "tags",
    "payload",
}


class MemoryStore:
    def __init__(self) -> None:
        self.tables: dict[str, dict[str, dict[str, Any]]] = {MAIN_TABLE: {}, TEST_TABLE: {}}

    def init(self) -> None:
        return None

    def upsert_many(self, table: str, lessons: list[Lesson]) -> dict[str, Any]:
        accepted = 0
        updated = 0
        now = datetime.now(timezone.utc)
        bucket = self.tables.setdefault(table, {})
        for lesson in lessons:
            row = lesson.model_dump(mode="json")
            row["received_at"] = bucket.get(row["uuid"], {}).get("received_at") or now.isoformat().replace("+00:00", "Z")
            row["updated_at"] = now.isoformat().replace("+00:00", "Z")
            if row["uuid"] in bucket:
                updated += 1
            bucket[row["uuid"]] = row
            accepted += 1
        return {"accepted": accepted, "updated": updated, "errors": []}

    def get(self, table: str, lesson_uuid: str) -> dict[str, Any] | None:
        return self.tables.setdefault(table, {}).get(str(uuid_lib.UUID(lesson_uuid)))

    def patch(self, table: str, lesson_uuid: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        row = self.get(table, lesson_uuid)
        if row is None:
            return None
        for key, value in patch.items():
            if key in PATCHABLE_FIELDS:
                row[key] = value
            else:
                row.setdefault("payload", {})[key] = value
        row["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return row

    def list(self, table: str, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        rows = list(self.tables.setdefault(table, {}).values())
        for key in ["status", "project", "hostname"]:
            if filters.get(key):
                rows = [row for row in rows if row.get(key) == filters[key]]
        if filters.get("since"):
            since = parse_datetime(str(filters["since"])).isoformat().replace("+00:00", "Z")
            rows = [row for row in rows if str(row.get("date")) >= since]
        return sorted(rows, key=lambda row: (row.get("date") or "", row.get("uuid") or ""))

    def count(self, table: str) -> int:
        return len(self.tables.setdefault(table, {}))


class PostgresStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def init(self) -> None:
        with self.connect() as conn, conn.cursor() as cur:
            for table in [MAIN_TABLE, TEST_TABLE]:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                      uuid UUID PRIMARY KEY,
                      date TIMESTAMPTZ NOT NULL,
                      received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                      hostname TEXT,
                      project TEXT,
                      project_dir TEXT,
                      kind TEXT,
                      area TEXT,
                      summary TEXT NOT NULL,
                      evidence TEXT,
                      status TEXT NOT NULL DEFAULT 'new',
                      tags TEXT[] NOT NULL DEFAULT '{{}}',
                      payload JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    )
                    """
                )
                cur.execute(f"CREATE INDEX IF NOT EXISTS {table}_status_idx ON {table} (status)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS {table}_date_idx ON {table} (date)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS {table}_project_idx ON {table} (project)")

    def upsert_many(self, table: str, lessons: list[Lesson]) -> dict[str, Any]:
        accepted = 0
        updated = 0
        with self.connect() as conn, conn.cursor() as cur:
            for lesson in lessons:
                row = lesson.model_dump()
                cur.execute(f"SELECT 1 FROM {table} WHERE uuid = %s", (row["uuid"],))
                existed = cur.fetchone() is not None
                cur.execute(
                    f"""
                    INSERT INTO {table}
                    (uuid, date, hostname, project, project_dir, kind, area, summary, evidence, status, tags, payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (uuid) DO UPDATE SET
                      date = EXCLUDED.date,
                      hostname = EXCLUDED.hostname,
                      project = EXCLUDED.project,
                      project_dir = EXCLUDED.project_dir,
                      kind = EXCLUDED.kind,
                      area = EXCLUDED.area,
                      summary = EXCLUDED.summary,
                      evidence = EXCLUDED.evidence,
                      status = EXCLUDED.status,
                      tags = EXCLUDED.tags,
                      payload = EXCLUDED.payload,
                      updated_at = now()
                    """,
                    (
                        row["uuid"],
                        row["date"],
                        row.get("hostname"),
                        row.get("project"),
                        row.get("project_dir"),
                        row.get("kind"),
                        row.get("area"),
                        row["summary"],
                        row.get("evidence"),
                        row.get("status") or "new",
                        row.get("tags") or [],
                        Jsonb(row.get("payload") or {}),
                    ),
                )
                accepted += 1
                updated += 1 if existed else 0
        return {"accepted": accepted, "updated": updated, "errors": []}

    def get(self, table: str, lesson_uuid: str) -> dict[str, Any] | None:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE uuid = %s", (str(uuid_lib.UUID(lesson_uuid)),))
            return normalize_row(cur.fetchone())

    def patch(self, table: str, lesson_uuid: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get(table, lesson_uuid)
        if current is None:
            return None
        merged = dict(current)
        payload = dict(merged.get("payload") or {})
        for key, value in patch.items():
            if key in PATCHABLE_FIELDS:
                merged[key] = value
            else:
                payload[key] = value
        merged["payload"] = payload
        lesson = Lesson(**{key: merged[key] for key in Lesson.model_fields if key in merged})
        self.upsert_many(table, [lesson])
        return self.get(table, lesson_uuid)

    def list(self, table: str, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for key in ["status", "project", "hostname"]:
            if filters.get(key):
                clauses.append(f"{key} = %s")
                params.append(filters[key])
        if filters.get("since"):
            clauses.append("date >= %s")
            params.append(parse_datetime(str(filters["since"])))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table}{where} ORDER BY date ASC, uuid ASC", params)
            return [normalize_row(row) for row in cur.fetchall()]

    def count(self, table: str) -> int:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS count FROM {table}")
            return int(cur.fetchone()["count"])


def parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    output = dict(row)
    for key in ["uuid"]:
        if key in output and output[key] is not None:
            output[key] = str(output[key])
    for key in ["date", "received_at", "updated_at"]:
        if isinstance(output.get(key), datetime):
            output[key] = output[key].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    output.setdefault("tags", [])
    output.setdefault("payload", {})
    return output


def store_from_env():
    if os.environ.get("LESSON_STORE") == "memory":
        return MemoryStore()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required unless LESSON_STORE=memory")
    return PostgresStore(database_url)


store = store_from_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init()
    yield


app = FastAPI(title="Pi Lesson Server", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def parse_lessons(request: Request) -> list[Lesson]:
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    try:
        if "application/x-ndjson" in content_type or "application/jsonl" in content_type:
            rows = [json.loads(line) for line in body.decode("utf-8").splitlines() if line.strip()]
        else:
            parsed = json.loads(body.decode("utf-8") or "{}")
            rows = parsed if isinstance(parsed, list) else [parsed]
        return [Lesson(**row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid lesson payload: {exc}") from exc


def lessons_response(rows: Iterable[dict[str, Any]]) -> PlainTextResponse:
    text = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    return PlainTextResponse(text, media_type="application/x-ndjson")


def filters(status: str | None, since: str | None, project: str | None, hostname: str | None) -> dict[str, str | None]:
    return {"status": status, "since": since, "project": project, "hostname": hostname}


@app.post("/lesson")
async def post_lesson(request: Request) -> JSONResponse:
    lessons = await parse_lessons(request)
    return JSONResponse(store.upsert_many(MAIN_TABLE, lessons))


@app.get("/lesson")
def get_lesson(uuid: str = Query(...)) -> dict[str, Any]:
    row = store.get(MAIN_TABLE, uuid)
    if row is None:
        raise HTTPException(status_code=404, detail="lesson not found")
    return row


@app.patch("/lesson")
def patch_lesson(patch: dict[str, Any], uuid: str = Query(...)) -> dict[str, Any]:
    row = store.patch(MAIN_TABLE, uuid, patch)
    if row is None:
        raise HTTPException(status_code=404, detail="lesson not found")
    return row


@app.get("/lessons")
def list_lessons(
    status: str | None = None,
    since: str | None = None,
    project: str | None = None,
    hostname: str | None = None,
) -> PlainTextResponse:
    return lessons_response(store.list(MAIN_TABLE, filters(status, since, project, hostname)))


if os.environ.get("LESSON_ENABLE_TEST_API") == "1":

    @app.post("/test/lesson")
    async def post_test_lesson(request: Request) -> JSONResponse:
        lessons = await parse_lessons(request)
        return JSONResponse(store.upsert_many(TEST_TABLE, lessons))

    @app.get("/test/lesson")
    def get_test_lesson(uuid: str = Query(...)) -> dict[str, Any]:
        row = store.get(TEST_TABLE, uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="test lesson not found")
        return row

    @app.patch("/test/lesson")
    def patch_test_lesson(patch: dict[str, Any], uuid: str = Query(...)) -> dict[str, Any]:
        row = store.patch(TEST_TABLE, uuid, patch)
        if row is None:
            raise HTTPException(status_code=404, detail="test lesson not found")
        return row

    @app.get("/test/lessons")
    def list_test_lessons(
        status: str | None = None,
        since: str | None = None,
        project: str | None = None,
        hostname: str | None = None,
    ) -> PlainTextResponse:
        return lessons_response(store.list(TEST_TABLE, filters(status, since, project, hostname)))

    @app.get("/test/logs")
    def test_logs() -> dict[str, Any]:
        return {"status": "ok", "testLessonCount": store.count(TEST_TABLE)}
