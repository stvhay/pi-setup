# Codex-First Routing and Outcome Capture Design Plan

**Issue:** pi-ffrh.8 — Prefer Codex routing and harden Langfuse outcome capture
**Design:** Combined here
**Date:** 2026-08-02
**Branch:** main

**Goal:** Prefer subscription-backed Codex, isolate metered Olla/OpenRouter calls in fresh workers, prevent null outcome evaluations, and guarantee explicit Bead/outcome correlation at closeout.

**Architecture:** Keep venue facts in `catalog.json`, task preference in `tasks/*.md`, and deterministic selection in `routing.py`. Archimedes subagents and `agnt invoke` already start fresh `--no-session` workers; expose that requirement in route output and global instructions instead of adding another launcher. Extend existing private session scores with one idempotent explicit outcome score; let it override sampled evaluator guesses.

**Acceptance Criteria:**
- [x] Comparable balanced/cheap routes select subscription-backed Codex before metered Olla models.
- [x] Kimi K3 remains an explicit specialist/escalation model, not a routine planning, implementation, research, or review candidate; Kimi K2.7 is not in normal review fanout.
- [x] Olla cloud model output requests are capped at 16,384 tokens.
- [x] Metered route selections declare fresh-context policy; tracked instructions forbid using them as continuation models in long root conversations.
- [x] `interactive-result` is not emitted when assistant output is absent.
- [x] `agnt improve outcome <bead> <outcome>` idempotently records both Bead link and explicit final outcome; scans prefer explicit outcome over evaluator output.
- [x] Focused tests, routing smoke, full Python checks, config checks, and shell syntax checks pass.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_model_config.py tests/test_subagent_workaround.py tests/test_improvement.py tests/test_langfuse_evaluators.py
pi/agent/bin/agnt eval run routing-smoke
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
```

---

### Task 1: Codex-first cost and task policy

**Files:**
- Modify: `pi/agent/catalog.json`
- Modify: `pi/agent/bin/agnt_lib/routing.py`
- Modify: `pi/agent/tasks/{review,research,cheap-peer,planning,implementation}.md`
- Modify: `pi/agent/evals/routing-smoke/eval.json`
- Test: `tests/test_agnt.py`
- Test: `tests/test_model_config.py`

**Steps:** Add failing routing/config assertions; rank subscription before metered cash spend; declare fresh context for metered selections; keep Kimi only as explicit specialist; update deterministic smoke expectations.

### Task 2: Bound Olla cloud output

**Files:**
- Modify: `pi/agent/extensions/olla-provider.ts`
- Modify: `pi/agent/catalog.json`
- Test: `tests/test_model_config.py`

**Steps:** Add failing cap assertions, then apply one shared 16,384-token cloud cap while preserving verified context windows.

### Task 3: Drop null outcome projections

**Files:**
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Test: `tests/test_subagent_workaround.py`

**Steps:** Add a tool-only/empty-assistant regression case; skip observation creation when no output exists.

### Task 4: Explicit linked final outcomes

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `pi/agent/AGENTS.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Test: `tests/test_improvement.py`

**Steps:** Add failing CLI and scan-precedence tests; write deterministic link and outcome session scores; document claim and closeout commands.

### Task 5: Verify, review, commit

Run listed checks, inspect task-owned diff, apply configured simplification/review gates, stage one atomic commit, then close `pi-ffrh.8` with evidence.

## File Conflicts

Tasks 1–2 both modify `pi/agent/catalog.json`; execute Task 2 after Task 1 in this session.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-02-codex-routing-outcome-capture-design-plan.md`.
Recommended skills: `test-driven-development`, then `verification-before-completion`.
