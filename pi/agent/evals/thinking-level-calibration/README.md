# Thinking-level calibration

Controlled replay for observable task-feature thinking policy. Fixed model `openai-codex/gpt-5.6-sol` isolates thinking level from model-family and venue effects.

## Rubric

`agnt_lib.routing.task_thinking_level` accepts only observable features:

- task phase;
- effect severity;
- ambiguity;
- novelty;
- reversibility;
- testability; and
- source breadth.

Unknown features, high-impact work, architecture, security, and final verification resolve to `xhigh`. Implementation and every unmatched profile resolve to `high`. Only exact low-risk profiles for mechanical inventory, formatting, and documentation may resolve to `low` or `medium`. Model confidence or self-rated difficulty is never an input.

This conservative shape follows two verified findings: OpenAI recommends more reasoning for ambiguous, complex, multi-step work and lower-latency execution for straightforward, well-defined tasks; Snell et al. found effective test-time compute varies with prompt difficulty and should be allocated per prompt. Sources:

- https://developers.openai.com/api/docs/guides/reasoning
- https://developers.openai.com/api/docs/guides/reasoning-best-practices
- https://arxiv.org/abs/2408.03314

## Protocol

Seven sanitized packets cover mechanical inventory, documentation, formatting, architecture, implementation, security, and final verification. Run each at `low`, `medium`, `high`, and `xhigh` with:

```json
{
  "model": "openai-codex/gpt-5.6-sol",
  "mode": "one-shot",
  "limits": {"maxProviderRequests": 1, "maxDurationMs": 180000},
  "outputContract": "inline"
}
```

Use identical packet text across levels. Run four levels in one parallel wave per case to reduce time drift; run cases serially. Do not set token or cost caps for this subscription-backed one-shot experiment.

Raw parent session and collected records remain private runtime data:

```bash
RUN_DIR=.pi/eval-runs/thinking-level-calibration
mkdir -p "$RUN_DIR"
python pi/agent/evals/thinking-level-calibration/evaluate.py validate
python pi/agent/evals/thinking-level-calibration/evaluate.py collect \
  --session "$PI_SESSION_FILE" --output "$RUN_DIR/runs.json"
python pi/agent/evals/thinking-level-calibration/evaluate.py score \
  --runs "$RUN_DIR/runs.json" --output "$RUN_DIR/summary.json"
```

Scoring requires one complete cell per case and level. It reports completion quality, latency, output tokens, tool errors, and review findings separately. Lower-level default changes require exact per-case quality parity with `xhigh` plus at least 10% aggregate latency reduction across eligible profiles. One run per cell is calibration evidence, not a stable latency benchmark; no promotion should rely on a noisy pass alone.

Latest result: [`results-2026-08-12.md`](results-2026-08-12.md). Quality matched, but latency gate failed; routing defaults remain unchanged.
