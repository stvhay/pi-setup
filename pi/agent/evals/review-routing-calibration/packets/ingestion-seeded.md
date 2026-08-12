# Paired review packet: ingestion behavior

Review only this packet. Anchors A1–A3 are candidate review locations; an anchor may be defective or safe. Report at most two concrete Critical/Important findings. Use anchor ID as finding `id`. Do not report style or generic hardening.

## Objective

Decide whether changed ingestion behavior violates stated wire-size, ordering, or retry invariants.

## Current decision

No finding is accepted yet; test candidate anchors against primary evidence below.

## Evidence sources

One-shot worker cannot retrieve repository files. Bounded source, contract, tests, and output schema are embedded below; no raw transcript is included.

## Constraints

Review only A1–A3. Return at most two Critical/Important findings and at most 6,000 characters.

## Verification target

Each finding must identify violated contract, concrete failure, and anchor; clean behavior must produce PASS.

## Stop conditions

Stop after deciding all candidate anchors from packet evidence. Do not request unrelated source or infer undeclared behavior.

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
    return len(json.dumps({"batch": events}, ensure_ascii=False))


def send_score(post, score, attempts=2):
    for attempt in range(attempts):
        # ANCHOR A2
        envelope = {"id": str(uuid4()), "type": "score-create", "body": score}
        body = json.dumps({"batch": [envelope]}, ensure_ascii=False)
        if len(body.encode("utf-8")) > MAX_BODY_BYTES:
            raise ValueError("score request exceeds 3,000,000 UTF-8 bytes")
        response = post(body)
        if response.status < 500:
            return response
    return response


def partition(events):
    # ANCHOR A3
    pending = list(events)
    batches = []
    while pending:
        event = pending.pop(0)
        event_body = json.dumps({"batch": [event]}, ensure_ascii=False)
        if len(event_body.encode("utf-8")) > MAX_BODY_BYTES:
            continue
        batch = [event]
        while pending and serialized_size([*batch, pending[0]]) <= MAX_BODY_BYTES:
            batch.append(pending.pop(0))
        batches.append(batch)
    return batches
```

## Existing tests

```python
def test_ascii_batches_fit_limit():
    events = [{"id": str(i), "body": "x" * 1000} for i in range(10)]
    assert all(serialized_size(batch) <= MAX_BODY_BYTES for batch in partition(events))


def test_successful_score_posts_once(fake_post):
    response = send_score(fake_post, {"value": 1})
    assert response.status == 200
    assert fake_post.call_count == 1
```

## Output

Return only one JSON object. Total response must be at most 6,000 characters.

```json
{
  "schemaVersion": 1,
  "reviewId": "case-01a",
  "scope": "behavioral",
  "reviewer": {"target": "calibration-candidate", "family": "codex"},
  "findings": [
    {
      "id": "A1",
      "severity": "important",
      "category": "correctness",
      "location": "example.py:ANCHOR A1",
      "claim": "specific violated invariant",
      "failureScenario": "specific input and result",
      "evidence": "packet evidence",
      "status": "unverified"
    }
  ]
}
```

Use an empty `findings` array for PASS.
