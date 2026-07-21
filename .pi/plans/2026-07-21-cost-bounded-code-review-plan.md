# Cost-Bounded Evidence-Driven Code Review Implementation Plan

**Issue:** pi-c37q — Make code review cost-bounded and evidence-driven
**Design:** Approved in the 2026-07-21 Pi conversation; summarized in Bead `pi-c37q`
**Date:** 2026-07-21
**Branch:** main (same-branch execution authorized by the user's explicit implementation approval and the project's direct-Pi workflow)

**Goal:** Preserve diverse cold-start review while preventing agentic request multiplication, keeping paid review near a $20/month ceiling, and measuring findings by external verification rather than model confidence.

**Architecture:** `agnt invoke --one-shot` will launch an ephemeral Pi peer with tools, skills, context-file discovery, and prompt templates disabled; the complete review packet is the only task context. Review routing remains task-driven but gains risk-specific candidate lists and a deterministic month-to-date paid-spend gate. OpenRouter Gemma 4 31B is the fast cheap default, local Gemma is the hard-cap fallback/control, DeepSeek V4 Flash is the cheap challenger/boundary reviewer, Kimi K2.7 is scoped, and K3 is absent from automatic review routes. Structured discovery and verification artifacts provide per-finding outcomes that can be attached to invocation metrics.

**Acceptance Criteria:**
- [ ] `agnt invoke --one-shot` passes Pi flags that prevent tools/session/context expansion and records one-shot mode plus provider request count.
- [ ] Low/medium/high review routing uses different deterministic candidate sets and never selects K3 automatically.
- [ ] Review routing applies soft/reserve/hard month-to-date paid-spend gates without relying on reviewer confidence.
- [ ] OpenRouter Gemma 4 31B remains the default fast reviewer; local Gemma is available as the hard-cap fallback; DeepSeek V4 Flash is configured as a cheap independent challenger.
- [ ] Review discovery and verifier roles use a validated per-finding artifact with concrete scenario/evidence and confirmed/refuted/unresolved adjudication.
- [ ] Invocation annotations and summaries expose review scope and verified finding counts for yield-per-cost comparison.
- [ ] User-facing review/task/helper documentation matches the implementation.
- [ ] Focused tests and the project verification suite pass.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_model_config.py tests/test_review.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Add one-shot invocation mode [Independent]

**Context:** `pi/agent/bin/agnt_lib/invoke.py` currently launches a normal Pi agent, so every tool call can create another paid provider request. A cold review packet should remain cold while using one model request.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/invoke.py`
- Modify: `pi/agent/bin/agnt_lib/metrics.py`
- Test: `tests/test_agnt.py`
- Document later: `pi/agent/bin/README.md`

**Steps:**
1. Add tests that invoke the CLI helper through a mocked `subprocess.run` and require `--no-tools`, `--no-skills`, `--no-context-files`, `--no-prompt-templates`, `--no-session`, and a concise system prompt when `--one-shot` is selected.
2. Run the focused tests and observe failure because the flag/metadata do not exist.
3. Add `--one-shot` to single and fanout invocation paths.
4. Count provider request events while parsing Pi JSON and store `invocationMode` and `providerRequests` in metrics; preserve existing callers and default agentic behavior.
5. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py -k 'one_shot or parse_pi_json or metrics_record'
```

**Expected result:** One-shot tests pass and existing invoke/metrics tests remain green.

### Task 2: Implement risk- and budget-bounded review routing [Depends on: Task 1]

**Context:** `pi/agent/tasks/review.md` currently includes K3 and generic routing does not vary review fanout by risk. The policy needs externally supplied/measured spend, not model self-confidence.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/routing.py`
- Modify: `pi/agent/tasks/review.md`
- Modify: `pi/agent/models.json`
- Modify: `pi/agent/catalog.json`
- Modify: `pi/agent/settings.json`
- Test: `tests/test_agnt.py`
- Test: `tests/test_catalog.py`
- Test: `tests/test_model_config.py`

**Steps:**
1. Add failing tests for risk-specific review candidate lists, no automatic K3, OpenRouter Gemma first, DeepSeek V4 Flash availability, and spend thresholds.
2. Add live-verified DeepSeek V4 Flash metadata and current OpenRouter rates; add Kimi opportunity rates needed for budget accounting.
3. Add flat risk-specific lists to review task frontmatter so policy remains inspectable in `tasks/review.md`.
4. Implement month-to-date marginal paid-review spend from provider-reported/OpenRouter metrics, with `AGNT_REVIEW_PAID_SPEND_USD` as an operator floor and a CLI override.
5. Apply thresholds: below $18 use normal risk policy; at/above $18 reserve budget by removing Kimi and preferring local Gemma plus DeepSeek as needed; at/above $20 route only to local Gemma. Keep K3 exclusively as a documented manual escalation target.
6. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_catalog.py tests/test_model_config.py -k 'review or deepseek or budget or route'
```

**Expected result:** Risk and spend deterministically change review candidates, and K3 is unreachable through ordinary review routing.

### Task 3: Add structured finding and adjudication artifacts [Depends on: Task 1]

**Context:** The current reviewer Markdown includes severity/location/issue/fix, but lacks finding IDs, failure scenarios, evidence status, and verifier outcomes. Invocation-level accepted/rejected annotations cannot calculate verified defect yield.

**Files:**
- Create: `pi/agent/bin/agnt_lib/review.py`
- Create: `pi/agent/skills/requesting-code-review/review-findings.schema.json`
- Create: `pi/agent/skills/requesting-code-review/review-findings.example.json`
- Create: `pi/agent/AGENTS.d/roles/finding-discoverer.md`
- Create: `pi/agent/AGENTS.d/roles/finding-verifier.md`
- Modify: `pi/agent/bin/agnt`
- Modify: `pi/agent/bin/agnt_lib/metrics.py`
- Test: `tests/test_review.py`
- Test: `tests/test_agnt.py`

**Steps:**
1. Add failing tests for discovery finding validation, enriched verifier evidence, invalid status/fields, summary counts, CLI validation, and metric annotations loaded from a findings file.
2. Implement a dependency-free `agnt review validate|summary` helper around the tracked schema contract.
3. Require discovery fields: ID, review ID, reviewer record ID, scope, severity, category, location, claim, concrete failure scenario, evidence, and status `unverified`.
4. Require verifier family/method/evidence for `confirmed`, `refuted`, or `unresolved`; reject confidence as an escalation signal.
5. Extend `agnt metrics annotate` with review ID/scope/findings-file and compact verified finding stats; expose aggregate confirmed/refuted/unresolved counts by model.
6. Add cold discovery and fresh-context verifier roles that output/use the artifact.
7. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_review.py tests/test_agnt.py -k 'review_finding or finding or annotation or summarize_metrics'
```

**Expected result:** Valid findings and adjudications are machine-checkable and linked to invocation metrics; incomplete or self-confidence-only records fail validation.

### Task 4: Update the review workflow and documentation [Depends on: Tasks 1-3]

**Context:** The skill still recommends agentic artifact-path reviews and automatic K3. It must build embedded behavior packets for one-shot peers and document deterministic escalation and budget behavior.

**Files:**
- Modify: `pi/agent/skills/requesting-code-review/SKILL.md`
- Modify: `pi/agent/skills/requesting-code-review/code-reviewer.md`
- Modify: `pi/agent/AGENTS.d/roles/code-reviewer.md` only if cross-references need alignment
- Modify: `pi/agent/bin/README.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `docs/AGNT-SYSTEM.md` or `docs/ARCHITECTURE.md` only where the new artifact/metric boundary is architectural
- Modify: `README.md` only if top-level command guidance requires it
- Test: `tests/test_agnt.py`
- Eval: `pi/agent/evals/role-context-smoke/eval.json` if role inventory assertions require it

**Steps:**
1. Document the measured OpenRouter Gemma evidence: 43 repository invocations cost $0.232 total with 52-second median latency; label it local evidence rather than a universal benchmark.
2. Replace artifact-path-only one-shot examples with complete packet assembly and `agnt invoke --one-shot` examples.
3. Define behavioral/boundary packet segmentation, the approximate 150-line split trigger, deterministic high-risk categories, evidence-first verification, profiling for performance claims, and budget thresholds.
4. Document that OpenRouter Gemma is preferred for speed and diversity, local Gemma is fallback/control, DeepSeek is a challenger, Kimi K2.7 is scoped, and K3 requires unresolved-critical evidence plus budget.
5. Document `agnt review` and finding-linked metrics commands without duplicating schemas.
6. Run docs/config checks.

**Focused verification:**
```bash
scripts/check-pi-config.sh
pi/agent/bin/agnt eval run role-context-smoke
rg -n 'one-shot|DeepSeek V4 Flash|finding-verifier|monthly paid' pi/agent/skills/requesting-code-review/SKILL.md pi/agent/bin/README.md docs
```

**Expected result:** Tracked workflow docs no longer instruct automatic agentic Kimi/K3 review and accurately describe artifacts and gates.

### Task 5: Full verification and independent review [Depends on: Tasks 1-4]

**Context:** This changes shared dispatch, metrics, model configuration, and review policy. It needs deterministic project checks and an independent reviewer, but no paid autonomous K3 pass.

**Files:**
- Modify only if a verified review finding requires a fix.
- Store review artifacts under: `.pi/reviews/pi-c37q/`

**Steps:**
1. Run all verification commands from the plan header.
2. Build a complete embedded diff packet and run one one-shot OpenRouter Gemma review plus one one-shot DeepSeek V4 Flash boundary review in parallel or sequentially; record actual provider cost and latency.
3. Validate and adjudicate any serious findings with fresh code/test evidence; do not accept consensus as proof.
4. Re-run affected focused and full checks after valid fixes.
5. Validate documentation against the final diff.
6. Update Bead `pi-c37q` with verification evidence and close only if acceptance criteria pass. Do not commit, push, merge, or clean without separate approval.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
git diff --check
```

**Expected result:** All checks pass, independent one-shot reviews are cost-measured, and every serious finding has confirmed/refuted/unresolved evidence.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `tests/test_agnt.py` | 1, 2, 3, 4 | Execute tasks serially and keep each TDD cycle green. |
| `pi/agent/bin/agnt_lib/metrics.py` | 1, 3 | Task 3 depends on Task 1 metrics metadata. |
| `pi/agent/skills/requesting-code-review/SKILL.md` | 3, 4 | Create schema/roles first, then document the complete workflow. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-21-cost-bounded-code-review-plan.md` (verify with `test -f`).
Recommended next skill: `test-driven-development` for Tasks 1-3; `verification-before-completion` before claiming completion.
