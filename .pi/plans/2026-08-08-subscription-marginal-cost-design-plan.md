# Subscription Marginal-Cost Accounting Design and Implementation Plan

**Issue:** pi-4tg9.42 — Separate inferred subscription price from marginal spend
**Design:** This document
**Date:** 2026-08-08
**Branch:** fix/subscription-marginal-cost

**Goal:** Keep Langfuse nominal price evidence while reporting truthful billing-aware marginal spend for private sessions and safe cohort summaries.

**Architecture:** Preserve the existing per-session `cost` scalar as Langfuse nominal cost for historical packet compatibility. Load billing classes only from enabled targets in tracked `pi/agent/catalog.json`, classify each generation from bounded provider/model dimensions after removing the telemetry-only `-subscription` suffix, and add nested schema-1 `costAccounting` with nominal USD, nullable marginal USD, observed/unknown generation counts, and count-only billing classes. Add a schema-1 cohort `costs` aggregate that sums known marginal values, reports unknown sessions separately, and marks the sum as a lower bound when any session is unknown. Subscription generations contribute zero marginal cost, metered generations contribute nominal cost, and missing/ambiguous catalog evidence remains unknown rather than zero.

**Non-goals:** Do not change raw Langfuse records, subscription aliasing, model routing, paid-review metrics, top-level packet/summary schema versions, evaluator configuration, package code, or API call counts.

**Acceptance Criteria:**
- [ ] Existing per-session `cost` remains the same nominal Langfuse value.
- [ ] A raw-model OpenAI/Codex subscription generation with positive `calculatedTotalCost` retains positive nominal USD and reports zero marginal USD.
- [ ] An enabled metered/OpenRouter generation retains nonzero nominal and marginal USD.
- [ ] Unknown or disabled billing targets report `marginalUsd: null`; cohort marginal sum is explicitly a lower bound and never treats unknown as zero.
- [ ] Mixed known subscription/metered sessions sum only metered nominal cost into marginal USD and remain complete.
- [ ] Safe cohort output contains only counts/amounts/classes, never provider/model/session/trace identifiers or payloads in cost accounting.
- [ ] Scanner makes no additional Langfuse calls and keeps top-level schema-1/schema-2 compatibility.
- [ ] Focused/full tests, Ruff, config, shell, eval, diff, and bounded private read-only recheck pass.

**Verification Commands:**
```bash
.venv/bin/python -m pytest -q tests/test_improvement.py
.venv/bin/python -m pytest -q tests/
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Add billing and cost-accounting RED fixtures

**Files:**
- Test: `tests/test_improvement.py`

**Steps:**
1. Add catalog fixtures with enabled subscription, metered, disabled, and malformed targets.
2. Add private-feature expectations for legacy nominal cost plus nested subscription/metered/unknown/mixed marginal accounting.
3. Add cohort expectations for known/unknown session counts, marginal lower-bound truth, and identifier-free output.
4. Run focused tests and confirm failure because billing-aware fields do not exist.

**Focused verification:**
```bash
.venv/bin/python -m pytest -q tests/test_improvement.py -k 'billing or marginal_cost or cost_accounting'
```

**Expected result:** RED fails on missing catalog billing/accounting fields, not fixture errors.

### Task 2: Implement minimal billing-aware accounting

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_improvement.py`

**Steps:**
1. Load an allowlisted `target -> billingClass` map from enabled models and tracked catalog; fail closed to no mappings on malformed/missing data.
2. Classify each generation using safe provider/model dimensions and the telemetry-only suffix normalization.
3. Preserve legacy nominal `cost`; add nested schema-1 per-session accounting with nullable marginal value.
4. Pass the map through existing scan feature construction without adding API calls.
5. Add count-only cohort aggregation and truthful lower-bound semantics.
6. Run focused tests until GREEN, then all improvement tests and Ruff.

**Focused verification:**
```bash
.venv/bin/python -m pytest -q tests/test_improvement.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib/improvement.py tests/test_improvement.py
```

**Expected result:** Subscription nominal/marginal split, metered cost, mixed known cost, and unknown truthfulness pass with no raw identifiers.

### Task 3: Document and verify candidate

**Files:**
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify if needed: `pi/agent/bin/README.md`
- Private only: `~/.pi/improvement/soaks/pi-4tg9.42/`

**Steps:**
1. Document legacy nominal compatibility, catalog-derived marginal accounting, and unknown/lower-bound semantics.
2. Run a bounded read-only scan through candidate code; retain packet/summary outside Git with 0700/0600 permissions and print count-only results.
3. Require the reproduced subscription session to retain nominal cost but report zero marginal cost; metered and unknown deterministic fixtures remain authoritative.
4. Run the complete project gate and review the exact diff for schema/privacy/API-call regressions.
5. Commit one signed atomic implementation candidate; keep integration/deployment/live recheck separately approval-gated.

**Focused verification:**
```bash
.venv/bin/python -m pytest -q tests/test_improvement.py tests/test_context_architecture.py
scripts/check-pi-config.sh
git diff --check
```

**Expected result:** Clean local candidate passes deterministic and bounded private evidence gates without production mutation.

## File Conflicts

All tasks touch `tests/test_improvement.py`; execute serially. Tasks 2 and 3 both depend on Task 1 RED evidence.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-08-subscription-marginal-cost-design-plan.md`.
Recommended next skill: `test-driven-development`; use `verification-before-completion` before candidate commit.
