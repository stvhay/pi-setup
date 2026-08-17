# Lasting Routing and Output Policy Implementation Plan

**Issue:** pi-04q7.8 — Set lasting routing and output policy
**Design:** Approved in-session decision
**Date:** 2026-08-17
**Branch:** main

**Goal:** Replace temporary Sol-first wording with approved Terra-low/Sol effort ladder and evidence-bounded output-contract defaults.

**Architecture:** Keep existing task frontmatter and output-contract transport. Change policy only: `cheap-peer` selects Terra at low thinking; planning/research use Sol low/medium/high by risk; review uses Sol low/medium/xhigh and retains Terra as challenger; orchestration stays Sol xhigh and `max` remains an explicit exceptional override. Output contracts remain caller-selected: `artifact` for deferred full results, `status-only` for deterministic checks, `inline` when content is needed now, and `pass-no-findings` opt-in.

**Acceptance Criteria:**
- [ ] Routing tasks, deterministic evals, and tests encode approved ladder.
- [ ] Lasting decision cites matched denominators and low-confidence limits without claiming permanent model rank.
- [ ] Temporary policy wording is removed; Terra and other independent challengers remain available.
- [ ] Output-contract guidance matches canary results and adds no framework/runtime logic.
- [ ] Rollback is documented as policy-commit revert; live `~/.pi` deployment stays excluded.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_model_config.py tests/test_context_architecture.py
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
```

---

### Task 1: Lock policy with failing checks

**Files:**
- Modify: `tests/test_agnt.py`
- Modify: `tests/test_model_config.py`
- Modify: `pi/agent/evals/routing-smoke/eval.json`

**Steps:**
1. Change assertions to approved model/effort ladder and output guidance.
2. Run focused tests/eval; confirm failures come from old policy.

### Task 2: Apply minimum tracked policy

**Files:**
- Modify: `pi/agent/tasks/cheap-peer.md`
- Modify: `pi/agent/tasks/planning.md`
- Modify: `pi/agent/tasks/research.md`
- Modify: `pi/agent/tasks/review.md`
- Modify: `pi/agent/tasks/orchestration.md`
- Modify: `pi/agent/AGENTS.md`

**Steps:**
1. Reuse existing task frontmatter; add no router code or schema.
2. Add one conditional output-contract rule to root workflow guidance.
3. Run focused tests/eval until green.

### Task 3: Synchronize decision documentation

**Files:**
- Modify: `docs/MODEL-PORTFOLIO-2026-08.md`
- Modify: `docs/MODEL-OUTPUT-CANARY-2026-08.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/agent/skills/requesting-code-review/SKILL.md`

**Steps:**
1. Record matched denominators, uncertainty, human-selected ladder, output defaults, and rollback.
2. Remove temporary/pending wording and keep challenger routes explicit.
3. Run focused and full repository verification.

## Execution Handoff

Plan saved to `.pi/plans/2026-08-17-lasting-routing-output-policy-plan.md`.
Recommended skills: `test-driven-development`, then `verification-before-completion`.
