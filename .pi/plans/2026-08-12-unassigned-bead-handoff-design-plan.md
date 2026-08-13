# Unassigned Bead Handoff Design and Implementation Plan

**Issue:** pi-800t — Allow Bead handoff from unassigned sessions
**Design:** Approved inline on 2026-08-12
**Date:** 2026-08-12
**Branch:** main

**Goal:** Let an explicitly targeted or automatically selected ready Bead start in a fresh parent-linked Pi session when source session has no work ownership, without weakening assigned-session closeout gates.

**Architecture:** `agnt_lib.improvement` distinguishes zero ownership records from malformed, conflicting, or incomplete ownership. `agnt work handoff-check` accepts only that exact unassigned state and keeps target readiness logic shared. `bead-handoff.ts` consumes closed or unassigned source metadata while reusing existing staging, shutdown, process replacement, cleanup, and recovery.

**Acceptance Criteria:**
- [ ] Zero-ownership persisted TUI session can hand off to ready target.
- [ ] Assigned source still requires successful outcome, closed Bead, and clean closeout.
- [ ] Automatic selection and target revalidation remain fail-closed.
- [ ] Fresh session is empty, parent-linked, claims target through `direct-start`, and copies no transcript.
- [ ] Existing replacement recovery guarantees remain passing.
- [ ] User/helper compatibility docs describe exception.

**Verification Commands:**
```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_improvement.py tests/test_agnt.py tests/test_bead_handoff.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest -p no:cacheprovider tests/
git diff --check
```

## Task 1: Add exact unassigned domain state

**Files:** `pi/agent/bin/agnt_lib/improvement.py`, `tests/test_improvement.py`

1. Add failing test proving zero ownership has a distinct signal.
2. Implement smallest exception/classification change.
3. Run focused improvement test.

## Task 2: Reuse handoff target preflight

**Files:** `pi/agent/bin/agnt_lib/work.py`, `tests/test_agnt.py`

1. Add failing tests for unassigned explicit/automatic target and assigned non-bypass.
2. Accept only exact unassigned signal; preserve existing source closeout path.
3. Keep existing ready lookup, selection, and revalidation shared.
4. Run focused handoff-check tests.

## Task 3: Adapt extension kickoff

**Files:** `pi/agent/extensions/bead-handoff.ts`, `tests/test_bead_handoff.py`

1. Add failing unassigned-session extension test.
2. Parse closed/unassigned source as bounded union.
3. Generate source-specific kickoff using `agnt work direct-start <target> --claim`.
4. Reuse existing staged session and process replacement path.
5. Run extension tests, including recovery cases.

## Task 4: Update docs and verify

**Files:** `pi/README.md`, `pi/agent/bin/README.md`, `docs/extension-web-compatibility.md`, optionally `docs/SELF-IMPROVEMENT.md` when needed for consistency.

1. Describe explicit unassigned exception and unchanged assigned-session gates.
2. Run focused and repository checks.
3. Review diff, commit task-owned files only, record outcome, and direct-closeout pi-800t.
