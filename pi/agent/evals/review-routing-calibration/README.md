# Review routing calibration

Paired synthetic review evaluation for `openai-codex/gpt-5.6-terra` and `openai-codex/gpt-5.6-luna`.

Execution uses Pi's native `subagent` tool, not `agnt invoke`. Each wave runs both models in parallel on identical packet text. Run waves serially to avoid one provider burst hiding latency differences.

## Bounds

- mode: `one-shot`
- thinking: `high`
- provider requests: 1
- duration: 180 seconds
- findings: at most 2
- complete child response: at most 6,000 characters
- repetitions: 3
- token/cost caps: none; both targets are subscription-backed

Packet anchors are candidate locations, not defect disclosures. Ground truth stays in `manifest.json`; clean controls use the same anchors after defects are repaired.

## Run protocol

For each packet and repetition, send one `subagent` tool call containing two tasks in manifest model order. Build each task as:

```text
review-calibration:v2 packet=<packet-id> repetition=<1..3>

<exact packet file contents>
```

Each task must set:

```json
{
  "mode": "one-shot",
  "thinking": "high",
  "limits": {"maxProviderRequests": 1, "maxDurationMs": 180000},
  "outputContract": "inline"
}
```

Do not set `maxTotalTokens` or `maxCostUsd`.

Collector rejects request-only evidence: every child result must independently expose observed provider/model, effective resolved mode/thinking/limits, one provider turn, bounded duration, and completed/timeout state. Raw parent session and collected child records are private runtime evidence with `0700` directories and `0600` files. Collect and score them outside tracked source:

```bash
RUN_DIR=.pi/eval-runs/review-routing-calibration
mkdir -p "$RUN_DIR"
python pi/agent/evals/review-routing-calibration/evaluate.py collect \
  --session "$PI_SESSION_FILE" --output "$RUN_DIR/runs.json"
python pi/agent/evals/review-routing-calibration/evaluate.py score \
  --runs "$RUN_DIR/runs.json" --output "$RUN_DIR/summary.json"
```

## Decision rule

Luna may replace Terra only for bounded low/medium first-pass review when every manifest quality floor passes, Luna recall trails Terra by no more than five percentage points, and Luna's verified finding opportunities per wall minute are at least 1.25 times Terra's. High-risk Terra review and escalation policy never change through this eval.
