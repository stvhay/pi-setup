# Pi Lesson Server

Small FastAPI service for aggregating lessons learned from Pi agent sessions.
It is intentionally unauthenticated; run it only on a trusted network such as a
VPN and expose it through your existing Caddy proxy.

## API

### `POST /lesson`

Accepts one JSON lesson (`application/json`) or JSONL/NDJSON
(`application/x-ndjson` or `application/jsonl`). Lessons are upserted by
`uuid`.

Minimum payload:

```json
{"uuid":"11111111-1111-4111-8111-111111111111","date":"2026-07-01T20:00:00Z","summary":"Agent should stop after provider failure"}
```

Recommended payload:

```json
{
  "uuid": "11111111-1111-4111-8111-111111111111",
  "date": "2026-07-01T20:00:00Z",
  "hostname": "workstation-1",
  "project": "pi-setup",
  "project_dir": "/Users/hays/Projects/pi-setup",
  "kind": "friction",
  "area": "doctor",
  "summary": "Agent continued after provider failure",
  "evidence": "OPENROUTER_API_KEY was missing; invoke failed repeatedly",
  "status": "new",
  "tags": ["environment", "provider"],
  "payload": {}
}
```

### `GET /lesson?uuid=<uuid>`

Returns one lesson as JSON.

### `PATCH /lesson?uuid=<uuid>`

Merges triage updates into the lesson. Known fields update columns; unknown
fields are stored in `payload`.

```json
{"status":"accepted","tags":["doctor","provider"],"notes":"Create a Bead in pi-setup"}
```

### `GET /lessons`

Returns lessons as JSONL (`application/x-ndjson`). Optional filters:

- `status`
- `since` (ISO timestamp)
- `project`
- `hostname`

## Test API

Set `LESSON_ENABLE_TEST_API=1` to expose:

- `POST /test/lesson`
- `GET /test/lesson?uuid=<uuid>`
- `PATCH /test/lesson?uuid=<uuid>`
- `GET /test/lessons`
- `GET /test/logs`

These use a separate `test_lessons` table so integration probes do not pollute
real triage data. They are disabled by default in `docker-compose.yml`.

For local Python tests, the app also supports `LESSON_STORE=memory`.

## Deploy with Docker Compose

This compose file runs two containers:

- `lesson-api`: FastAPI service on port `8080` inside Docker.
- `lesson-db`: private Postgres database on an internal network.

Create the external reverse-proxy network if it does not already exist:

```bash
docker network create caddy
```

Create a local secrets file. It is gitignored.

```bash
cd lesson-server
cp .env.example .env
python - <<'PY'
import secrets
print(secrets.token_urlsafe(36))
PY
$EDITOR .env   # paste the generated value as POSTGRES_PASSWORD
```

Start the service:

```bash
docker compose up -d --build
```

Check health locally from the Docker host:

```bash
docker compose ps
docker compose exec lesson-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/healthz').read().decode())"
```

Example Caddyfile entry on the same Docker network:

```caddyfile
lessons.example.internal {
  reverse_proxy lesson-api:8080
}
```

If your Caddy network has a different name, set `CADDY_NETWORK` in `.env` before `docker compose up`.

The API is intentionally unauthenticated. Expose it only behind VPN, private DNS, or another trusted access-control layer.

## Smoke test

```bash
curl -fsS http://lessons.example.internal/healthz

printf '%s\n' \
  '{"uuid":"11111111-1111-4111-8111-111111111111","date":"2026-07-01T20:00:00Z","hostname":"'"$(hostname)"'","project":"pi-setup","project_dir":"'"$PWD"'","kind":"friction","area":"doctor","summary":"Smoke lesson from curl","tags":["smoke"],"payload":{}}' \
  | curl -fsS -X POST http://lessons.example.internal/lesson \
      -H 'Content-Type: application/x-ndjson' \
      --data-binary @-

curl -fsS http://lessons.example.internal/lessons
```

## Local tests

From the repository root:

```bash
uv pip install --python .venv/bin/python -r lesson-server/requirements.txt
.venv/bin/python -m pytest tests/test_lesson_server.py
```
