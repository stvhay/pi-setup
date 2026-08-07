# Paired review packet: ingestion behavior

Review only this packet. Anchors A1–A3 are candidate review locations; an anchor may be defective or safe. Report at most two concrete Critical/Important findings. Use anchor ID as finding `id`. Do not report style or generic hardening.

## Contract

- Serialized request bodies must remain at or below 3,000,000 UTF-8 bytes.
- Event order must be preserved across split requests.
- Retry attempts must reuse envelope IDs so server deduplication is effective.
- Individually oversized events may be rejected locally without blocking later sendable events.

## Patch

```python
import json
from uuid import uuid4

MAX_BODY_BYTES = 3_000_000


def serialized_size(events):
    # ANCHOR A1
    body = json.dumps({"batch": events}, ensure_ascii=False, separators=(",", ":"))
    return len(body.encode("utf-8"))


def send_score(post, score, attempts=2):
    # ANCHOR A2
    envelope = {"id": str(uuid4()), "type": "score-create", "body": score}
    body = json.dumps({"batch": [envelope]}, ensure_ascii=False, separators=(",", ":"))
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("score request exceeds 3,000,000 UTF-8 bytes")
    for attempt in range(attempts):
        response = post(body)
        if response.status < 500:
            return response
    return response


def partition(events):
    # ANCHOR A3
    pending = list(events)
    batches = []
    current = []
    while pending:
        event = pending.pop(0)
        if serialized_size([event]) > MAX_BODY_BYTES:
            continue
        if current and serialized_size([*current, event]) > MAX_BODY_BYTES:
            batches.append(current)
            current = []
        current.append(event)
    if current:
        batches.append(current)
    return batches
```

## Existing tests

```python
def test_multibyte_batches_fit_limit():
    events = [{"id": str(i), "body": "🙂" * 300_000} for i in range(4)]
    batches = partition(events)
    assert [event["id"] for batch in batches for event in batch] == ["0", "1", "2", "3"]
    assert all(serialized_size(batch) <= MAX_BODY_BYTES for batch in batches)


def test_score_retries_reuse_envelope_id(fake_post_503_then_200):
    response = send_score(fake_post_503_then_200, {"value": 1})
    bodies = [json.loads(call.args[0]) for call in fake_post_503_then_200.call_args_list]
    assert response.status == 200
    assert bodies[0]["batch"][0]["id"] == bodies[1]["batch"][0]["id"]
```

## Output

Return only one JSON object. Total response must be at most 6,000 characters.

```json
{
  "schemaVersion": 1,
  "reviewId": "case-01b",
  "scope": "behavioral",
  "reviewer": {"target": "calibration-candidate", "family": "codex"},
  "findings": []
}
```

Every finding must contain `id`, `severity`, `category`, `location`, `claim`, `failureScenario`, `evidence`, and `status: "unverified"`. Use an empty `findings` array for PASS.
