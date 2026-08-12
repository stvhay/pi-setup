# Repository Inspection Routing Implementation Plan

**Issue:** pi-1fgw.4 — Route repository inspection by access and billing
**Design:** Bead scope plus tracked routing, Archimedes, and calibration contracts
**Date:** 2026-08-12
**Branch:** main

**Goal:** Route repository-required delegation only to agentic workers, keep qualified subscription-backed inspection at zero marginal cost by default, and admit metered agentic inspection only with visible justification, estimate, and hard limits.

**Architecture:** Extend existing `agnt route` policy with one source-access dimension and reuse catalog billing/rates for admission and cost estimates. Keep enforcement thin in the tracked Archimedes wrapper: repository access rejects one-shot mode, while metered agentic repository work requires route-generated justification, estimate, and limits. Reuse existing review-calibration packets for a paired agentic subscription/metered canary; add no new evaluator or billing subsystem.

**Acceptance Criteria:**
- [x] `--access repository` emits agentic execution and repository metadata; `--access self-contained` preserves cold one-shot review.
- [x] Repository one-shot dispatch is rejected before upstream execution.
- [x] Repository routes exclude metered candidates unless justification, positive token estimates, and marginal USD budget are complete.
- [x] Accepted metered repository candidates expose estimated marginal cost and bounded subagent limits; fanout aggregate estimate does not exceed supplied budget.
- [x] Subscription candidates remain preferred within comparable quality and expose zero marginal cost without default request/token/cost caps.
- [x] Paired agentic Luna/M3 inspection over existing seeded and clean behavioral/boundary packets records quality, latency, and actual/estimated marginal cost before commit.

**Verification Commands:**
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_agnt.py tests/test_agent_os_compat.py tests/test_context_architecture.py
pi/agent/bin/agnt eval run routing-smoke
scripts/check-pi-config.sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
git diff --check
```

---

### Task 1: Measure repository-inspection routes [Independent]

**Context:** Reuse the four tracked `pi/agent/evals/review-routing-calibration/packets/*.md` files as repository-only evidence sources. Run paired agentic Luna and M3 inspections with identical prompts. Luna has zero marginal model cost. Each M3 child is caller-bounded to 4 provider requests, 40,000 total tokens, 180 seconds, and $0.10; four packets cap aggregate requested marginal spend at $0.40.

**Files:**
- Create after scoring: `pi/agent/evals/review-routing-calibration/results-2026-08-12-repository-inspection.md`
- Reuse: `pi/agent/evals/review-routing-calibration/evaluate.py`
- Reuse: `pi/agent/evals/review-routing-calibration/packets/*.md`

**Steps:**
1. Dispatch paired agentic tasks that point to exact tracked packet paths without embedding packet contents.
2. Preserve returned artifacts and collect provider/model, requests, elapsed time, termination, usage, and cost.
3. Reuse existing output validation and semantic rubrics to score recall, precision, clean false positives, and valid outputs.
4. Record comparison and routing decision. Do not promote M3 from one canary; use result only to verify subscription default is non-inferior and expose any measured tradeoff.

**Expected result:** Both routes inspect filesystem successfully; report contains quality, latency, and cost evidence before policy rollout.

### Task 2: Specify access and budget behavior [Depends on: Task 1]

**Files:**
- Modify: `tests/test_agnt.py`
- Modify: `tests/test_agent_os_compat.py`
- Modify: `tests/test_context_architecture.py`
- Modify: `pi/agent/evals/routing-smoke/eval.json`

**Steps:**
1. Add focused tests for repository-agentic mode, self-contained review one-shot mode, subscription-first comparable quality, incomplete metered evidence rejection, budget-overrun rejection, aggregate fanout cost, route-generated limits, one-shot repository rejection, and bounded metered repository acceptance.
2. Run focused tests and confirm failures are caused by missing access/budget policy.

**Focused verification:**
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_agnt.py tests/test_agent_os_compat.py tests/test_context_architecture.py
```

### Task 3: Implement minimum routing and guard [Depends on: Task 2]

**Files:**
- Modify: `pi/agent/bin/agnt_lib/routing.py`
- Modify: `pi/agent/extensions/archimedes.ts`

**Steps:**
1. Add `--access auto|self-contained|repository`, estimated input/output token bounds, `--max-marginal-usd`, and `--metered-justification quality-benefit|missing-capability`.
2. Derive execution mode from access; use existing task default only for `auto`.
3. Use catalog rates to estimate metered cost. Reject incomplete or over-budget metered repository candidates.
4. Bound metered fanout aggregate estimate and emit source access, billing class, estimate, justification, execution mode, and limits in selection/fanout/subagent examples.
5. Replace keyword-based metered-review rejection with explicit thin transport checks. Strip custom policy metadata before upstream execution.
6. Run focused tests to green.

**Expected result:** Repository access cannot reach tool-disabled workers; subscription inspection needs no marginal budget; admitted metered inspection is justified and bounded.

### Task 4: Align policy and docs [Depends on: Task 3]

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/skills/requesting-code-review/SKILL.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/ARCHITECTURE.md`

**Steps:**
1. Require `--access repository` for filesystem-dependent peers and `--access self-contained` for complete cold packets.
2. Document subscription-first default and exact metered justification/estimate/budget contract.
3. Keep subscription agentic work uncapped by default; identify calibration caps as caller experiment limits.
4. Run static and focused checks.

### Task 5: Verify, review, and close [Depends on: Task 4]

**Steps:**
1. Run verification commands from header once on stable candidate.
2. Inspect staged/untracked boundaries, diff, and task-owned files.
3. Run one subscription-backed repository review of the final diff; verify any finding locally.
4. Commit task-owned changes, record outcome, and run direct closeout.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `tests/test_agnt.py` and routing smoke | Tasks 2, 3 | Tests fail first; implementation follows. |
| `tests/test_agent_os_compat.py` and wrapper | Tasks 2, 3 | Transport contract written before wrapper change. |
| Policy docs and routing output | Tasks 3, 4 | Docs use green output shape. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-12-repository-inspection-routing-plan.md`
Recommended next skill: `test-driven-development` for behavior changes; `verification-before-completion` before claiming completion.
