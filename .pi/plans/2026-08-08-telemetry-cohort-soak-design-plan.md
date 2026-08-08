# Telemetry Cohort Soak Design and Execution Plan

**Issue:** pi-4tg9.15 — Soak corrected telemetry and evaluator cohorts
**Design:** Approved interactively on 2026-08-08
**Date:** 2026-08-08
**Branch:** feature/telemetry-cohort-soak

**Goal:** Validate a bounded fresh production telemetry cohort without exposing raw evidence, and file every failed hard gate as an atomic blocker before trusting cohort metrics.

**Architecture:** Reuse `agnt improve scan`; add no production command or generic eval kind. Freeze one post-change window beginning `2026-08-08T00:00:00Z`, with at most 500 traces and 50 sessions. Store packet, verifier, and detailed result only under a private `~/.pi/improvement/soaks/pi-4tg9.15/` directory with directory mode `0700` and file mode `0600`. A one-off deterministic verifier may query bounded Langfuse metadata needed for joins, but emits only aggregate counts and named hard-gate results. Raw session/trace/observation IDs, inputs, outputs, URLs, paths, and score comments never enter chat, Git, or Beads.

**Known preflight blocker:** Tracked and live `pi/agent/extensions/langfuse-config-env.ts` still sets `PI_LANGFUSE_MAX_STRING_LENGTH ||= "off"`. This preserves media but fails finite ordinary-string behavior. `pi-4tg9.7` remains correctly closed under its local-source-only completion boundary; this soak will create a separate runtime-consumption blocker rather than reopen or redefine it.

**Non-goals:** No model calls, remote score/review writes, evaluator changes, routing changes, raw packet review by a cloud model, media-storage migration, Langfuse v4 migration, or production telemetry code changes.

**Acceptance Criteria:**
- [x] Frozen scan discovers all traces inside its 500-trace cap and includes every candidate session inside its 50-session cap, or reports truthful lower-bound/continuation state.
- [x] Subscription-backed OpenAI/Codex sessions with complete usage preserve zero calculated cost; metered providers are not tested against the zero-cost rule.
- [x] At least three explicitly labeled root sessions across at least two linked work items are present, or label coverage is reported as a blocker without writing new scores.
- [x] Every sampled subagent projection has a valid child-session join to an ended child root within the bounded lookup window; missing/duplicate/opaque joins remain failures.
- [ ] Existing `Subagent output quality — calibration (100%)` scores correlate to sampled projection observations and artifact/status contracts without exposing content.
- [ ] Finite ordinary-string policy is enabled and bounded ingestion remains enabled; current `off` policy must fail and produce a separate blocker.
- [x] Packet and detailed verifier evidence remain private with `0700`/`0600` permissions; only payload-free aggregate conclusions enter Beads.
- [x] `pi-4tg9.15` closes only when every hard gate passes. Any failed gate is linked atomically and keeps the soak open.

**Verification Commands:**
```bash
python3 ~/.pi/improvement/soaks/pi-4tg9.15/verify.py --self-test
python3 ~/.pi/improvement/soaks/pi-4tg9.15/verify.py \
  --packet ~/.pi/improvement/soaks/pi-4tg9.15/packet.json \
  --summary ~/.pi/improvement/soaks/pi-4tg9.15/scan-summary.json \
  --output ~/.pi/improvement/soaks/pi-4tg9.15/aggregate.json
python3 - <<'PY'
import json
from pathlib import Path
p = Path.home() / '.pi/improvement/soaks/pi-4tg9.15/aggregate.json'
data = json.loads(p.read_text())
assert data['schemaVersion'] == 1
assert set(data['hardGates']) == {
    'artifactAwareScoring', 'finitePayload', 'outcomeLabels',
    'projectionJoins', 'subscriptionCost', 'truthfulCompleteness'
}
assert data['privateEvidence'] is True
PY
python3 - <<'PY'
import stat
from pathlib import Path
root = Path.home() / '.pi/improvement/soaks/pi-4tg9.15'
assert stat.S_IMODE(root.stat().st_mode) == 0o700
assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in root.iterdir() if path.is_file())
PY
.venv/bin/python -m pytest tests/test_improvement.py tests/test_beads_workspace.py -q
scripts/check-pi-config.sh
git diff --check
```

---

### Task 1: Freeze private cohort

1. Create private soak directory with mode `0700`.
2. Run `agnt improve scan --since 2026-08-08T00:00:00Z --limit 50 --max-traces 500 --recheck --json`.
3. Copy the generated packet to `packet.json`, save safe CLI output as `scan-summary.json`, and set both to `0600`.
4. Stop if trace discovery is incomplete for reasons other than an explicit cap, if more than 50 candidate sessions exist, or if packet/summary schemas disagree.

### Task 2: Verify hard gates

1. Write private `verify.py` with bounded constants and no secret logging.
2. Add a synthetic `--self-test` covering aggregate schema, failed-gate preservation, and payload-free output.
3. Verify subscription cost, existing explicit labels, session/root and child projection joins, artifact-contract evaluator score joins, finite string/ingestion bounds, and completeness.
4. Write only counts, Boolean gates, safe enum reasons, and configured numeric caps to `aggregate.json`.

### Task 3: Reconcile failures

1. Treat every failed hard gate as evidence, not as a reason to weaken the gate.
2. Create one atomic Bead per independent root cause. First expected blocker: consume the reviewed media-safe finite-string `pi-langfuse` implementation in the deployed runtime while preserving explicit `off` override support.
3. Add only sanitized aggregate counts and blocker IDs to `pi-4tg9.15`; do not copy private evidence.
4. Keep `pi-4tg9.15` in progress while any hard gate remains failed.

### Task 4: Verify tracked closeout state

1. Run focused improvement and Beads tests, config validation, and diff checks.
2. Commit this plan plus explicit Beads export changes atomically on the feature branch.
3. Do not integrate, deploy, close the soak, or clean the worktree without separate approval.

## Result

Private immutable packet covers all 23 candidate sessions across 144 fully discovered traces. Subscription accounting passed for 23/23 OpenAI/Codex sessions with complete usage and zero calculated cost. Completeness reporting passed and truthfully remained a lower bound because one session hit the 20-trace cap. All 28 selected projection observations correlated to one quality score (21 excellent, 7 poor), but none requested an artifact contract. Eight successful one-shot calibration projections retained child IDs, artifacts, usage, and scores but had no child trace because one-shot disables discovered extensions; the projection omitted mode/availability classification. No explicit linked outcomes appeared because canonical UUIDv7 sessions that began before the scan window used the window boundary for score lookup. Bounded ingestion passed at 3,000,000 bytes; ordinary strings remain unbounded. Created blockers `pi-4tg9.15.1` through `pi-4tg9.15.4`; parent soak remains in progress. Raw evidence remains private.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-08-telemetry-cohort-soak-design-plan.md`
Recommended next skill: `verification-before-completion` before claiming the soak phase complete.
