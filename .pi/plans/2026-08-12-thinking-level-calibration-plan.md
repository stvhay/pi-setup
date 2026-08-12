# Thinking-Level Calibration Implementation Plan

**Issue:** pi-1fgw.5 — Calibrate task-based thinking-level selection
**Design:** Bead scope plus tracked routing/eval contracts
**Date:** 2026-08-12
**Branch:** main

**Goal:** Define an observable-feature thinking rubric, replay representative task classes across candidate levels, and change no defaults without measured quality parity.

**Architecture:** Reuse `agnt` routing's existing thinking seam and eval conventions. Add one pure rubric beside `choose_thinking_level`, plus a tracked calibration manifest/evaluator and seven sanitized self-contained packets. Keep raw child records private under `.pi/eval-runs`; track protocol, aggregate results, and conservative routing decision only.

**Acceptance Criteria:**
- [x] Rubric uses phase, effect severity, ambiguity, novelty, reversibility, testability, and source breadth; unknown and consequential classes resolve to high/xhigh.
- [x] Only predefined mechanical inventory, documentation, and formatting profiles can resolve below high.
- [x] Mechanical inventory, documentation, formatting, architecture, implementation, security, and final verification packets replay at low/medium/high/xhigh on one fixed subscription model.
- [x] Scoring reports quality, latency, output tokens, tool errors, review findings, and completion quality separately.
- [x] Existing task defaults remain unchanged unless a lower candidate meets tracked per-case parity and aggregate guardrails.

**Verification Commands:**
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_agnt.py tests/test_thinking_level_calibration.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python pi/agent/evals/thinking-level-calibration/evaluate.py validate
pi/agent/bin/agnt eval run routing-smoke
scripts/check-pi-config.sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check pi/agent/bin/agnt_lib pi/agent/evals/thinking-level-calibration tests
git diff --check
```

---

### Task 1: Specify rubric and scorer [Independent]

**Files:**
- Modify: `tests/test_agnt.py`
- Create: `tests/test_thinking_level_calibration.py`
- Create: `pi/agent/evals/thinking-level-calibration/manifest.json`
- Create: `pi/agent/evals/thinking-level-calibration/packets/*.md`

**Steps:**
1. Add failing rubric tests for conservative defaults and exact lower-level allowlist.
2. Add failing evaluator tests for manifest validation, independent metrics, parity gates, and malformed evidence.
3. Run focused tests and confirm expected missing-feature failures.

### Task 2: Implement minimum rubric and evaluator [Depends on: Task 1]

**Files:**
- Modify: `pi/agent/bin/agnt_lib/routing.py`
- Create: `pi/agent/evals/thinking-level-calibration/evaluate.py`
- Create: `pi/agent/evals/thinking-level-calibration/README.md`

**Steps:**
1. Implement pure observable-feature rubric without changing `select_model` defaults.
2. Implement manifest validation and record scoring using stdlib only.
3. Run focused tests to green.

### Task 3: Run bounded replay [Depends on: Task 2]

**Files:**
- Create: `pi/agent/evals/thinking-level-calibration/results-2026-08-12.md`
- Runtime only: `.pi/eval-runs/thinking-level-calibration/*`

**Steps:**
1. Run each sanitized packet at low, medium, high, and xhigh on `openai-codex/gpt-5.6-sol`, one cold provider request each.
2. Collect effective dimensions, latency, output tokens, tool errors, findings, and structured completion result.
3. Score records and track aggregate evidence plus per-class parity.
4. Keep defaults unchanged unless every tracked gate passes.

### Task 4: Verify and close [Depends on: Task 3]

**Steps:**
1. Run header verification once on stable candidate.
2. Review diff and verify findings locally.
3. Commit task-owned changes, record outcome, and run direct closeout.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `routing.py`, evaluator tests | Tasks 1–2 | Tests fail first; implementation follows. |
| calibration manifest/records | Tasks 1–3 | Protocol freezes before replay. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-12-thinking-level-calibration-plan.md`
Recommended next skill: `test-driven-development`; `verification-before-completion` before completion.
