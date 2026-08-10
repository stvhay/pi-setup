# Bead Session Handoff Implementation Plan

**Issue:** pi-yx0a — Automate fresh-session handoff between Beads
**Design:** Bead `pi-yx0a` DESIGN field
**Date:** 2026-08-10
**Branch:** main

**Goal:** Let agent close one Bead and start next ready Bead in fresh Pi session without human slash-command input or transcript copying.

**Architecture:** Add one tracked extension exposing `handoff_bead` and `/handoff-bead`. Tool queues command as follow-up; command runs deterministic `agnt work handoff-check`, then calls `ctx.newSession({ parentSession, withSession })`. Preflight reuses existing session ownership/outcome and Beads JSON helpers; replacement context receives only target Bead ID and direct-start instruction.

**Acceptance Criteria:**
- [ ] `handoff_bead` queues `/handoff-bead <id>` without replacing session inside tool execution.
- [ ] Command rejects missing closeout, unclosed source Bead, missing/not-ready target, non-TUI mode, and ephemeral source session before replacement.
- [ ] Successful command uses `ctx.newSession`, records parent-session provenance, and calls only replacement `withSession` context to initiate `agnt work direct-start <id>`.
- [ ] No source transcript, clone/fork, or compaction policy enters handoff.
- [ ] Conflict guidance prefers `handoff_bead`; `/new` remains human fallback only.
- [ ] Required focused and project verification passes.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_bead_handoff.py tests/test_agnt.py tests/test_improvement.py tests/test_context_architecture.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Add deterministic preflight [Independent]

**Context:** Existing `pi/agent/bin/agnt_lib/improvement.py` owns canonical session-to-Bead link/outcome reads. Existing `pi/agent/bin/agnt_lib/work.py` owns Beads JSON validation and direct-work JSON results.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Test: `tests/test_improvement.py`
- Test: `tests/test_agnt.py`

**Steps:**
1. Add failing tests for linked closeout extraction and handoff preflight success/failures.
2. Run focused tests and confirm expected missing-function/behavior failures.
3. Add minimum helper that requires one canonical source Bead and matching explicit outcome.
4. Add `agnt work handoff-check TARGET --session-id SESSION` using existing Beads helpers; require source closed and target present in `bd ready`.
5. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py tests/test_agnt.py -k handoff
```

**Expected result:** Handoff preflight emits bounded `ready` JSON only after source closeout and target readiness; all failures are explicit and nonzero.

### Task 2: Add Pi handoff extension [Depends on: Task 1]

**Context:** Follow upstream `reload-runtime.ts` tool-to-command pattern and `handoff.ts` `ctx.newSession` lifecycle. Treat replacement as terminal; capture strings only and use replacement callback context after switch.

**Files:**
- Create: `pi/agent/extensions/bead-handoff.ts`
- Create: `tests/test_bead_handoff.py`

**Steps:**
1. Add Node-loader tests for registration, queued follow-up, mode/session guards, preflight failure, parent provenance, and replacement-context continuation.
2. Run focused test and confirm missing extension failure.
3. Implement `handoff_bead` plus `/handoff-bead` with strict single Bead argument.
4. Call tracked `agnt work handoff-check` before replacement.
5. Call `ctx.newSession({ parentSession, withSession })`; send bounded target-only kickoff through replacement context.
6. Run focused test.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_bead_handoff.py
```

**Expected result:** Tool queues command; command creates fresh parent-linked session and initiates direct-start without old runtime handles or transcript context.

### Task 3: Replace normal conflict guidance [Depends on: Task 1]

**Context:** Structured recovery currently exposes `["/clone", "/new"]` in direct-start and improvement errors. New normal path is agent tool; only human fallback is `/new`.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Modify: `tests/test_improvement.py`
- Modify: `tests/test_agnt.py`

**Steps:**
1. Change tests first to expect `handoff_bead` target arguments and `/new` fallback, with no `/clone`.
2. Confirm focused RED.
3. Update exception text, JSON payloads, and terminal messages minimally.
4. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py tests/test_agnt.py -k 'fresh_session or conflict or handoff'
```

**Expected result:** Model-facing recovery names `handoff_bead`; `/new` is explicitly fallback; `/clone` absent.

### Task 4: Align instructions and docs [Depends on: Tasks 2, 3]

**Context:** Required surfaces are global AGENTS, self-improvement loop, agnt command reference, and user-facing Pi config docs. Compatibility matrix should state mode boundary.

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/README.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/extension-web-compatibility.md`
- Modify: `tests/test_context_architecture.py`

**Steps:**
1. Add/adjust guidance checks first where practical.
2. Document closeout-first agent handoff, bounded context, parent provenance, and `/new` fallback.
3. Keep `/fork`/`/clone` semantics outside work-item handoff and add no compaction policy.
4. Run focused context and config checks.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_bead_handoff.py
scripts/check-pi-config.sh
```

**Expected result:** Required docs consistently name automated handoff; no normal work-item guidance recommends `/clone`.

### Task 5: Verify, review, and commit [Depends on: Tasks 1-4]

**Context:** Shared behavior and global instructions require full deterministic gates and independent diff review before atomic local commit.

**Files:**
- Review all task-owned paths above plus `.beads/issues.jsonl` and this plan.

**Steps:**
1. Run focused extension and Python tests.
2. Run config, shell, Ruff, full pytest, routing-smoke, and role-context-smoke.
3. Inspect `git diff --check`, status, and full task diff.
4. Request independent code review; fix confirmed issues with focused tests.
5. Re-run fresh affected/full gates.
6. Stage task-owned files and create one local atomic commit.
7. Record `agnt improve outcome pi-yx0a success`, close `pi-yx0a`, and report next ready Beads.

**Focused verification:**
```bash
git diff --check
```

**Expected result:** Clean verified task diff, one local commit, outcome recorded, Bead closed.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt_lib/improvement.py` | 1, 3 | Task 3 depends on Task 1. |
| `pi/agent/bin/agnt_lib/work.py` | 1, 3 | Task 3 depends on Task 1. |
| `tests/test_improvement.py` | 1, 3 | Task 3 depends on Task 1. |
| `tests/test_agnt.py` | 1, 3 | Task 3 depends on Task 1. |
| `tests/test_bead_handoff.py` | 2, 4 | Documentation assertions follow extension behavior. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-10-bead-session-handoff-plan.md` (verify with `test -f`).
Recommended skills: `test-driven-development` during implementation; `verification-before-completion` before completion.
