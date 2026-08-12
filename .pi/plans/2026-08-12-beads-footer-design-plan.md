# Beads Footer Status Implementation Plan

**Issue:** #pi-i21b — Show active and in-progress Beads in Pi footer
**Design:** Bead `pi-i21b`
**Date:** 2026-08-12
**Branch:** main

**Goal:** Show every canonical `in_progress` Bead in Pi's existing footer and theme-highlight the Bead linked to the current session.

**Architecture:** Add a read-only `agnt work status --session-id` adapter that combines canonical Beads CLI state with existing session-work correlation. Add one auto-discovered extension that validates this bounded JSON, publishes a keyed `ctx.ui.setStatus` value, and refreshes at session start/reload and after tools that can mutate Beads. Keep Pi's built-in footer intact and add no daemon or dependency.

**Acceptance Criteria:**
- [ ] Status lists each in-progress issue as `<id> P<priority> <title>` in priority/ID order.
- [ ] Current linked issue is accent/bold themed; absent link leaves all entries plain.
- [ ] Empty, malformed, or failed state clears keyed status without replacing built-in footer.
- [ ] Startup/reload and work-mutating tool completion refresh status.
- [ ] Focused tests, config checks, and docs pass.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_beads_footer.py tests/test_agnt.py tests/test_improvement.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
```

---

### Task 1: Specify read-only work status [Independent]

**Files:**
- Modify: `tests/test_improvement.py`
- Modify: `tests/test_agnt.py`
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`

**Steps:**
1. Add focused tests for linked/unlinked session correlation and canonical in-progress projection/order.
2. Run tests and confirm missing helper/command failures.
3. Add smallest read-only helper and CLI command.
4. Re-run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_improvement.py -k 'work_status or session_work_item'
```

**Expected result:** Focused tests pass; command emits bounded schema-1 JSON and never mutates Beads.

### Task 2: Add footer extension [Depends on: Task 1]

**Files:**
- Create: `tests/test_beads_footer.py`
- Create: `pi/agent/extensions/beads-footer.ts`

**Steps:**
1. Add extension tests for multiple issues, active styling, absent link, empty/malformed/failure clearing, and refresh events.
2. Run tests and confirm extension-missing failure.
3. Implement validated formatting and keyed status refresh using existing `runAgntJson`.
4. Re-run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_beads_footer.py
```

**Expected result:** All required footer states and refresh hooks pass.

### Task 3: Document and verify [Depends on: Task 2]

**Files:**
- Modify: `pi/README.md`
- Modify: `docs/extension-web-compatibility.md`
- Modify: `pi/agent/bin/README.md`

**Steps:**
1. Document visible footer behavior, portable UI boundary, and read-only command.
2. Run focused tests, lint, config checks, and relevant full regression tests.
3. Review diff for task-only scope and commit atomically.

**Focused verification:**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
```

**Expected result:** Checks pass with docs aligned to behavior.

## File Conflicts

Tasks are serial because helper, extension, and docs describe one shared status schema.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-12-beads-footer-design-plan.md`
Recommended next skill: `test-driven-development`; `verification-before-completion` before commit.
