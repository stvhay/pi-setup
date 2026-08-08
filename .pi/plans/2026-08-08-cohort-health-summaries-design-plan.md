# Cohort Health Summaries Design and Implementation Plan

**Issue:** pi-4tg9.14 — Extend improvement scans with cohort health summaries
**Design:** Approved inline 2026-08-08
**Date:** 2026-08-08
**Branch:** feature/cohort-health-summaries

**Goal:** Add one payload-free, bounded cohort-health aggregate to the existing improvement scan without changing its public command, top-level schemas, or per-session evidence.

**Architecture:** Extend `_features()` with normalized provider membership and observation-model membership. Add one pure `_cohort_health()` reducer over already-selected session features; it performs no Langfuse calls and reports session-membership outcome counts, evaluator coverage, summed error taxonomy, capture gaps, completeness, and every active scan/capture cap. Emit the same nested schema-1 aggregate in the schema-1 safe summary and schema-2 private packet. Invalid or private-looking dimension labels remain unknown rather than copied or inferred.

**Non-goals:** No separate command, additional trace/observation/score fetches, rates over unobserved sessions, raw IDs/payloads, model-to-provider inference, top-level schema bump, review-policy change, or historical packet migration.

**Acceptance Criteria:**
- [ ] Existing selected-session scan reports stable provider/model membership outcomes plus explicit unknown-session counts.
- [ ] Final outcomes, evaluator coverage/timeouts, error classes/sources/blocking state, and capture gaps aggregate from existing normalized features only.
- [ ] Aggregate exposes scan session, discovery trace/page, traces/session, observations/trace, and scores/query caps plus truthful discovery/session-limit state.
- [ ] Summary remains schema 1, private packet remains schema 2, review policy remains v1, and historical schema-1 packets remain reviewable.
- [ ] Safe summary contains no session/trace/observation IDs, payloads, URLs, secrets, hashes, absolute paths, or malformed dimension labels.
- [ ] Focused and full project verification pass.

**Verification Commands:**
```bash
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest tests/test_improvement.py -q
/Users/hays/Projects/pi-setup/.venv/bin/python -m ruff check pi/agent/bin/agnt_lib/improvement.py tests/test_improvement.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Define normalized aggregate contract

**Files:**
- Modify: `tests/test_improvement.py`
- Modify: `pi/agent/bin/agnt_lib/improvement.py`

**Steps:**
1. Add failing pure-helper tests for multiple providers/models/outcomes, unknown dimensions, evaluator coverage, error sums, capture gaps, zero sessions, stable ordering, and safe labels.
2. Add the minimum dimension normalizer and provider extraction to `_features()`.
3. Implement `_cohort_health()` over session features only.
4. Run focused tests and Ruff.

**Expected result:** Deterministic payload-free aggregate with explicit denominators and unknowns.

### Task 2: Integrate bounded scan metadata

**Files:**
- Modify: `tests/test_improvement.py`
- Modify: `pi/agent/bin/agnt_lib/improvement.py`

**Steps:**
1. Add failing scan-level tests proving identical aggregate placement in summary/private packet.
2. Cover incomplete discovery, operator session cap, trace/observation gaps, all active caps, malformed dimensions, and no eligible sessions.
3. Wire `_cohort_health()` after selected sessions are built; preserve all existing top-level fields and schemas.
4. Prove tool-result envelopes and historical review compatibility remain unchanged.

**Expected result:** One bounded scan truthfully reports observed cohort health and every active cap without extra API calls.

### Task 3: Document and verify

**Files:**
- Modify: `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Document session-membership semantics, unknown handling, lower-bound/completeness meaning, aggregate contents, and active limits.
2. Run focused and full deterministic gates.
3. Request independent final review; fix only verified Critical/Important findings.
4. Commit one task-owned atomic implementation candidate.

**Expected result:** Reviewed, reproducible candidate ready for separately approved main integration/deployment.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-08-cohort-health-summaries-design-plan.md`
Recommended next skill: `test-driven-development`; use `verification-before-completion` before commit and closeout.
