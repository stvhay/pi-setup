# Harness Reliability and Complexity Stabilization Design-Plan

**Issue:** `pi-04q7` — Stabilize harness reliability and complexity control
**Design:** Approved interactively 2026-08-16
**Date:** 2026-08-16
**Branch:** `main`

**Goal:** Restore clean-checkout CI, stabilize model routing immediately, then use trustworthy evidence to reduce aborts, output volume, lifecycle friction, latency, and silent complexity growth.

**Architecture:** Keep Pi as interactive runtime, Beads as work graph, `agnt_lib` as deterministic policy, Pi extensions as thin lifecycle adapters, and Langfuse/private metrics as evidence only. After CI is green, interleave a reversible Sol-first route with telemetry repair and one replacement-first complexity rule. Matched canaries decide lasting policy; measured recurrence decides handoff and latency work.

**Acceptance Criteria:**
- [ ] Clean-checkout CI no longer depends on local-only Git refs or timing-sensitive fake-process behavior.
- [ ] Planning, research, and primary review temporarily route to Sol high while orchestration remains Sol xhigh.
- [ ] New invocation records preserve safe task/thinking dimensions and normalized failure reasons; handoff stages become countable.
- [ ] Matched model and output-contract cohorts separate operational reliability, accepted quality, and output volume.
- [ ] Only measured handoff and latency problems receive implementation.
- [ ] Complexity control reuses existing artifacts and introduces no mandatory document suite or new canonical artifact type.
- [ ] Lasting routing/output policy is a human decision grounded in matched denominators and stated uncertainty.

**Repository verification commands:**

```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt context-health
```

---

## Evidence baseline

Public-safe aggregate evidence only; raw prompts, outputs, session IDs, trace IDs, URLs, and credentials remain private.

- Latest failed CI run had three failures: one approval-test fake process did not drain private resolver FD during resolve; two vendor tests assumed local submodule refs unavailable in a clean recursive checkout.
- Bounded 30-day metrics contained 2,387 unique invocations: 374 failed, 32 unavailable, and 393 legacy/unknown execution outcomes.
- Since 2026-08-06, failed-or-unavailable counts were Luna 278/382, Terra 62/342, and Sol 1/789. These are operational outcomes, not answer-quality rankings.
- Only 202/2,387 records had accepted/rejected or verified pass/fail labels; about 95% were classified only as `peer`.
- Recent portfolio failures had 29 explicit timeout classifications, but 313/364 lacked normalized termination reason. Token attribution is not supported: only two token-limit and six output-limit records.
- Provider-reported output totaled 6.60M tokens and child results 5.10M characters; 65% of output contracts were inline or unknown.
- Bounded Langfuse legacy scan covered 500/9,215 traces and found seven limit terminations among 41 child projections: five time, two request. This is lower-bound evidence.
- `agnt context-health` passed with only 118 skill-discovery characters remaining before its hard limit.
- `.project-init` says `github-issues`, contradicting current Beads policy.
- `pi-rxo3` has 34/34 closed children but remains in progress; this is a candidate handoff/Beads friction case, not frequency proof.

## Chosen sequence

```text
pi-04q7.1 CI baseline
├── pi-04q7.2 temporary Sol-first floor ─┐
├── pi-04q7.3 telemetry fidelity ────────┼── pi-04q7.4 matched canaries ── pi-04q7.8 lasting policy
│   ├── pi-04q7.5 measured handoff fix
│   └── pi-04q7.6 measured latency cut
└── pi-04q7.7 bounded scope-growth rule
```

After `pi-04q7.1`, routing safety, observability, and complexity work may proceed independently because their planned file sets are disjoint. Canary work waits for both temporary routing and trustworthy dimensions.

## Non-goals

- No scheduler, daemon, service, or new telemetry backend.
- No mandatory `CHARTER.md`, `REQUIREMENTS.md`, `RISKS.md`, `GLOSSARY.md`, ADR, C4, or traceability suite.
- No universal file-count change budget.
- No broad handoff rewrite before recurrence evidence.
- No permanent model ranking from aggregate failures, sparse labels, or model agreement.
- No provider purchase, credential change, push, production action, or local-live deployment in this plan.

## Task 1: Restore clean-checkout CI and record baseline (`pi-04q7.1`) [Independent]

**Context:** Repair only test assumptions. Production approval and vendor code already model intended behavior.

**Files:**
- Modify: `tests/test_approvals.py`
- Modify: `tests/test_package_patches.py`
- Create: `.pi/plans/2026-08-16-harness-reliability-complexity-stabilization-design-plan.md`

**Steps:**
1. Preserve failing GitHub Actions output as the pre-fix reproduction.
2. Update the fake `agnt` resolve branch to drain FD 3 when resolver proof is supplied.
3. Replace Archimedes tag/branch resolution with `cat-file`/parent checks against existing immutable SHA constants.
4. Delete `test_langfuse_upstream_candidates_are_single_commits_on_v1514`; retained pinned-head/base/one-commit test already covers clone-visible runtime state.
5. Run focused tests repeatedly, full pytest, then documented project checks.
6. Commit task-owned plan/test changes and close with direct closeout.

**Focused verification:**

```bash
.venv/bin/python -m pytest -q \
  tests/test_approvals.py::test_beads_question_bridge_preserves_custom_response_multi_selection_and_cancellation \
  tests/test_package_patches.py::test_archimedes_vendor_submodule_pins_clean_210_stack \
  tests/test_package_patches.py::test_langfuse_vendor_submodule_pins_combined_runtime_head
```

**Expected result:** All tests pass without resolving any local-only branch or tag name.

## Task 2: Apply reversible Sol-first routing floor (`pi-04q7.2`) [Depends on: Task 1]

**Context:** Operational evidence plus user experience justifies a temporary safety floor, not a lasting quality claim.

**Files:**
- Modify: `pi/agent/tasks/planning.md`
- Modify: `pi/agent/tasks/research.md`
- Modify: `pi/agent/tasks/review.md`
- Modify: `pi/agent/evals/routing-smoke/eval.json`
- Modify: `tests/test_agnt.py`
- Modify: `tests/test_model_config.py`
- Modify: `docs/MODEL-PORTFOLIO-2026-08.md`

**Steps:**
1. Add failing route assertions for planning/research/review Sol-high defaults while preserving cheap-peer and Sol-xhigh orchestration.
2. Put Sol first for planning, research, and primary review; keep Luna explicit cheap/mechanical and Terra challenger paths.
3. Label policy temporary and point rollback to this task's policy diff.
4. Run routing/model tests and deterministic routing smoke eval.
5. Do not deploy live config without separate exact approval.

**Focused verification:**

```bash
.venv/bin/python -m pytest -q tests/test_agnt.py tests/test_model_config.py
pi/agent/bin/agnt eval run routing-smoke
```

## Task 3: Repair invocation and handoff telemetry fidelity (`pi-04q7.3`) [Depends on: Task 1]

**Context:** Current producer loses routing task/effective thinking and frequently omits safe termination reason. Handoff frequency is unobservable.

**Files:**
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Modify: `pi/agent/extensions/bead-handoff.ts`
- Modify only if deterministic normalization belongs there: `pi/agent/bin/agnt_lib/metrics.py`, `pi/agent/bin/agnt_lib/work.py`
- Test: `tests/test_subagent_workaround.py`
- Test: `tests/test_bead_handoff.py`
- Test: `tests/test_agnt.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `docs/ARCHITECTURE.md`

**Steps:**
1. Add failing tests for routing task, effective mode/thinking, output contract, and fallback `process-error` normalization.
2. Reuse current metadata and metric schema; add no backend.
3. Add count-only handoff stage/result/duration events to existing private runtime evidence.
4. Verify no prompt/output/identifier leakage and compatibility with old records.

**Focused verification:**

```bash
.venv/bin/python -m pytest -q \
  tests/test_subagent_workaround.py tests/test_bead_handoff.py \
  tests/test_output_redaction.py tests/test_agnt.py
```

## Task 4: Run matched model and output-contract canaries (`pi-04q7.4`) [Depends on: Tasks 2 and 3]

**Context:** Reuse current calibration machinery rather than invent another experiment framework.

**Files:**
- Prefer modifying/reusing: `pi/agent/evals/review-routing-calibration/`
- Prefer modifying/reusing: `pi/agent/evals/thinking-level-calibration/`
- Private raw runs: `.pi/eval-runs/` (ignored)
- Create public-safe aggregate result under existing eval directory or `.pi/plans/`
- Test: `tests/test_review_routing_calibration.py`, `tests/test_thinking_level_calibration.py`

**Steps:**
1. Extend paired review calibration to Terra-high versus Sol-high with identical packets and verifier.
2. Add matched planning/research packets for Luna-medium versus Sol-high using existing collection/result contracts where possible.
3. Run twenty matched output-contract calls comparing current inline with existing artifact/status-oriented contracts.
4. Report execution, usable result, accepted/verified quality, latency, retries, output tokens, and parent-visible characters separately.
5. Stop at planned cohort unless saturation or a predeclared failure boundary justifies fewer calls.

**Expected result:** Evidence supports a bounded decision or explicitly remains insufficient; no model self-grading becomes authority.

## Task 5: Automate measured handoff and Beads friction (`pi-04q7.5`) [Depends on: Task 3]

**Files:**
- Likely modify: `pi/agent/bin/agnt_lib/work.py`
- Keep thin adapter: `pi/agent/extensions/bead-handoff.ts`
- Test: `tests/test_agnt.py`, `tests/test_bead_handoff.py`

**Steps:**
1. Classify at least 20 handoff/lifecycle attempts or stop at documented saturation.
2. Select only highest-frequency deterministic recoverable case.
3. Put logic in `agnt_lib`; keep extension as lifecycle/UI adapter.
4. If no case recurs enough, close with evidence and no code.

## Task 6: Remove proven deterministic lifecycle latency (`pi-04q7.6`) [Depends on: Task 3]

**Files:**
- Existing maintenance: `pi/agent/bin/agnt_lib/metrics.py`
- Candidate producer: `pi/agent/extensions/subagent-error-workaround.ts`
- Candidate projection path: `pi/agent/bin/agnt_lib/improvement.py`, `pi/agent/bin/agnt_lib/langfuse.py`
- Tests: `tests/test_agnt.py`, `tests/test_subagent_workaround.py`, `tests/test_improvement.py`

**Steps:**
1. Run existing `agnt metrics consolidate`; remeasure route p50/p95 before code.
2. Measure repeated runtime-path resolution and lifecycle projection p50/p95.
3. Implement only largest repeated source above material threshold; prefer batching/caching/deletion.
4. Preserve local-ledger authority and fail-open best-effort projection behavior.

## Task 7: Bound scope growth without new governance artifacts (`pi-04q7.7`) [Depends on: Task 1]

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/skills/brainstorming/SKILL.md`
- Modify: `pi/agent/skills/project-init/templates/AGENTS.md`
- Modify: `.project-init`
- Consolidate/delete descriptions under: `pi/agent/skills/*/SKILL.md`
- Test: `tests/test_context_architecture.py`, `tests/test_agnt.py`

**Rule:** Before changing a public or persistent contract, security boundary, dependency set, or cross-cutting mechanism, state intended outcome, affected boundary, smallest implementation, and verification. If materially different interpretations remain, ask one targeted question; otherwise proceed without new governance artifacts.

**Focused verification:**

```bash
.venv/bin/python -m pytest -q tests/test_context_architecture.py tests/test_agnt.py
pi/agent/bin/agnt context-health
```

## Task 8: Set lasting routing and output policy (`pi-04q7.8`) [Depends on: Task 4]

**Files:**
- Modify chosen task policies under `pi/agent/tasks/`
- Modify: `pi/agent/evals/routing-smoke/eval.json`
- Modify: `docs/MODEL-PORTFOLIO-2026-08.md`
- Modify matching tests only

**Steps:**
1. Present matched denominators, uncertainty, and rollback options to user.
2. Use a durable decision blocker only if final choice must survive handoff.
3. Keep, narrow, or revert temporary Sol floor and output defaults.
4. Remove temporary wording and run full routing verification.

## File conflicts

| Files | Tasks | Resolution |
|---|---|---|
| `tests/test_agnt.py` | 2, 3, 5, 6, 7, 8 | Dependency graph serializes shared phases; rebase expectations on latest closed predecessor. |
| `pi/agent/tasks/review.md`, routing eval/docs | 2, 8 | Task 8 depends on canary after Task 2; it finalizes or reverts temporary policy. |
| `pi/agent/extensions/bead-handoff.ts` | 3, 5 | Task 5 depends on telemetry task and changes behavior only after measurement. |

## Execution handoff

Plan saved to: `.pi/plans/2026-08-16-harness-reliability-complexity-stabilization-design-plan.md`.

Recommended skills: `test-driven-development` for behavior/test changes, `systematic-debugging` for remaining failures, and `verification-before-completion` before every commit/closeout.
