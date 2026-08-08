# Review Routing Calibration Implementation Plan

**Issue:** pi-4tg9.31 — Calibrate Codex review routing by latency-adjusted yield
**Design:** Approved subagent-driven paired evaluation
**Date:** 2026-08-07
**Branch:** feat/review-routing-calibration

**Goal:** Compare Terra and Luna on identical bounded review packets using native subagent execution evidence, then retain Terra unless Luna clears predeclared quality and latency-adjusted-yield gates.

**Architecture:** Keep execution interactive and native to the patched `subagent` tool rather than adding another `agnt invoke` path. Track synthetic packets, ground truth, bounds, and thresholds under one eval directory. A small additive Archimedes result envelope exposes observed provider plus the effective resolved profile/limits. A stdlib collector/scorer correlates parent-session subagent call arguments with results by task/model, validates requested and observed dimensions, scores opaque anchored findings against private semantic rubrics, and emits a reproducible aggregate report; raw session/run artifacts remain private.

**Acceptance Criteria:**
- [x] Two seeded packets and matched clean controls cover behavioral and deployment-boundary defects.
- [x] Terra and Luna each run every packet three times in paired waves with `mode=one-shot`, `thinking=high`, one provider request, 180-second deadline, at most two findings, and 6,000 response characters.
- [x] Collector validates exact packet payload, model, mode, thinking, limits, output contract, observed model/provider, provider-request count, duration, termination, and response size from session call/result records.
- [x] Scorer reports completion/timeout, median/p95 latency, confirmed unique seed IDs, verified opportunities, false positives, verification checks/time, precision, recall, and verified hits per wall minute.
- [x] Luna is eligible only at recall >=75%, precision >=90%, clean-run false-positive rate <=10%, timeout <=10%, recall deficit <=5 points, and latency-adjusted yield >=1.25x Terra.
- [x] High-risk routing and escalation remain unchanged.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_review_routing_calibration.py -q
.venv/bin/python pi/agent/evals/review-routing-calibration/evaluate.py validate
.venv/bin/python pi/agent/evals/review-routing-calibration/evaluate.py collect --session "$PI_SESSION_FILE" --output .pi/eval-runs/review-routing-calibration/runs.json
.venv/bin/python pi/agent/evals/review-routing-calibration/evaluate.py score --runs .pi/eval-runs/review-routing-calibration/runs.json --output .pi/eval-runs/review-routing-calibration/summary.json
```

---

### Task 1: Build deterministic eval assets [Independent]

**Files:**
- Modify: `forks/pi-archimedes`
- Modify: `patches/pi-packages/pi-archimedes-subagent-1.8.3.patch`
- Modify: `scripts/update-pi-config.sh`
- Modify: `tests/test_package_patches.py`
- Modify: `tests/test_update_pi_config.py`
- Create: `pi/agent/evals/review-routing-calibration/manifest.json`
- Create: `pi/agent/evals/review-routing-calibration/README.md`
- Create: `pi/agent/evals/review-routing-calibration/packets/*.md`
- Create: `pi/agent/evals/review-routing-calibration/evaluate.py`
- Create: `tests/test_review_routing_calibration.py`

**Steps:**
1. Add failing Archimedes tests for observed provider and cloned effective profile/limits in every executor result.
2. Add tests for opaque manifest cases, reordered call/result correlation, strict paired dimensions/duration, semantic-rubric verification, private permissions, thresholds, and report metrics.
3. Implement the minimum Archimedes evidence fields and version-locked production projection.
4. Implement the stdlib collector/scorer and validate all packet anchors/ground truth without model calls.
5. Commit and deploy verified assets before expensive trials.

**Expected result:** Synthetic session fixtures produce deterministic per-model scores and promotion decisions.

### Task 2: Run paired subagent trials [Depends on: Task 1]

**Context:** Execute 12 serial waves. Each wave contains one Terra and one Luna child in parallel so packet, start window, thinking, and limits are matched while repetitions expose provider noise.

**Steps:**
1. For each packet/repetition, call the native `subagent` tool with both model targets and identical task text.
2. Use `mode=one-shot`, `thinking=high`, `maxProviderRequests=1`, `maxDurationMs=180000`, and no token/cost caps.
3. Collect matching parent-session calls/results to private `.pi/eval-runs/` data.
4. Score and inspect every invalid output or unexpected finding against packet ground truth.
5. Produce tracked aggregate report without raw private session data.

**Expected result:** 24 dimension-valid child records with three paired repetitions per packet.

### Task 3: Apply evidence threshold [Depends on: Task 2]

**Files:**
- Create: `pi/agent/evals/review-routing-calibration/results-2026-08-08.md`
- Modify only if threshold passes: `pi/agent/tasks/review.md`
- Modify only if threshold passes: routing tests/docs tied to low/medium bounded review

**Steps:**
1. Record aggregate and per-wave evidence, invalid/timeout disposition, and threshold calculation.
2. Keep Terra default unless every quality gate and 1.25x yield threshold passes.
3. If Luna passes, change only low/medium bounded first-pass ordering; do not alter high-risk Terra + escalation policy.
4. Run full deterministic project gates and independent review.

**Expected result:** Routing decision is mechanically traceable to predeclared criteria.

## Result

Completed with 24 exact-payload, dimension-valid records. Both models reached 100% recall/precision, zero clean false positives/timeouts, and 100% valid outputs. Terra delivered 5.122 verified opportunities/minute versus Luna's 3.347; Luna/Terra ratio `0.653` failed the predeclared `1.25` promotion gate. Terra and high-risk escalation remain unchanged. Aggregate evidence: `pi/agent/evals/review-routing-calibration/results-2026-08-08.md`.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-07-review-routing-calibration-plan.md`
Recommended next skill: `test-driven-development`; use `verification-before-completion` before commit and closeout.
