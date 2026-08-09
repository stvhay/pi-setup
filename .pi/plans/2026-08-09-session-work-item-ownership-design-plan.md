# Session Work-Item Ownership Design and Implementation Plan

**Issue:** pi-6enp — Prevent cross-work-item outcome misattribution in reused Pi sessions
**Design:** This document
**Date:** 2026-08-09
**Branch:** `fix/session-link-correlation`

**Goal:** Prevent one logical Pi session from silently moving between Beads or attributing an old explicit outcome to a new work-item link.

**Architecture:** Keep deterministic session score IDs and existing Langfuse score APIs. Before writing either canonical work-link or outcome score, read the session-scoped canonical ownership scores within bounded time/result limits and fail closed when valid ownership differs or cannot be validated. During scans, trust an explicit outcome only when its public Bead metadata matches the session correlation; otherwise omit it and add one payload-free capture-gap class.

**Acceptance Criteria:**
- [x] Same-session, same-Bead link/outcome operations remain idempotent.
- [x] Existing work-link or outcome ownership for Bead A rejects link/outcome for Bead B before either score is overwritten.
- [x] Direct-start reports non-retryable-in-place recovery using `/clone` or `/new` without exposing session IDs or prior Bead IDs.
- [x] `agnt improve link` and `outcome` expose the same public-safe recovery.
- [x] Historical link-B/outcome-A scan data cannot produce an explicit outcome for B and records a countable payload-free ownership-mismatch gap.
- [x] UUIDv7 and legacy session identities, bounded score reads, historical packet compatibility, and existing privacy rules remain intact.

**Verification Commands:**
```bash
ROOT=/Users/hays/Projects/pi-setup
"$ROOT/.venv/bin/python" -m pytest -q tests/test_improvement.py tests/test_agnt.py
"$ROOT/.venv/bin/python" -m ruff check pi/agent/bin/agnt_lib tests
"$ROOT/.venv/bin/python" -m pytest -q tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

## Root Cause and Chosen Contract

`_work_link_score_id()` and `_outcome_score_id()` intentionally key one score each by logical session. `link_session()` currently performs an unconditional upsert, so relinking replaces work-item metadata while the previous outcome remains. `scan_sessions()` then computes correlation from work-link rows and explicit outcome from outcome rows independently.

Chosen contract:

1. One logical Pi session has one public work-item owner.
2. Canonical work-link and outcome rows both declare that owner in existing `metadata.beadId`; no new public score or schema is needed.
3. Reads use existing `LangfuseClient.list_scores()` with exact session/name filters, bounded timestamps, and existing score caps. Canonical deterministic IDs win when response IDs are available; ID-less historical/test rows remain readable.
4. Missing ownership rows permit first link. Rows owned by requested Bead permit idempotent writes. Conflicting or malformed canonical ownership rows raise a public-safe `SessionWorkItemConflict` before any score write.
5. Direct-start may already have claimed the requested Bead before link detection; it must preserve truthful stage evidence, mark same-session retry unsafe, and direct the operator to `/clone` or `/new` before retrying.
6. Scanner correlation stays schema-compatible. Explicit outcome rows whose owner does not exactly match linked Bead are excluded from feature scoring and add `mismatched-work-item-outcome` to existing additive capture gaps/cohort counts. Raw IDs and conflicting values remain private and unprojected.

No file lock, new setting, migration, score type, schema bump, or generic ownership abstraction. Remote compare-and-swap is unavailable; ordinary Pi session writes are serialized by the interactive workflow.

## Task 1: Producer ownership guard [Independent]

**Context:** Enforce one work item at the shared producer used by direct-start, manual link, and outcome.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_improvement.py`

**Steps:**
1. Add focused tests for same-Bead idempotence, conflicting link ownership, conflicting outcome ownership, malformed canonical ownership, bounded session/name reads, and zero writes on conflict.
2. Run focused tests and confirm expected RED failures from missing reads/guard.
3. Add private canonical-score selection and bounded ownership-read helpers plus public-safe `SessionWorkItemConflict`.
4. Invoke guard after Bead validation and before `put_session_score()`.
5. Run focused GREEN tests.

**Focused Verification:**
```bash
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest -q tests/test_improvement.py -k 'link or outcome or ownership'
```

**Expected Result:** Conflicts raise before writes; repeated same-Bead operations pass and use deterministic IDs.

## Task 2: Scanner mismatch containment [Depends on: Task 1]

**Context:** Historical records can already contain mismatched owner metadata. Keep them visible as count-only health evidence without treating old outcomes as authoritative.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_improvement.py`

**Steps:**
1. Add scan regression with work-link Bead B and explicit outcome Bead A; assert no explicit final source and one mismatch capture gap/cohort count.
2. Confirm RED: current scan emits explicit success and no gap.
3. Filter canonical outcome rows against correlation before `_features()` and append the additive gap.
4. Add gap to existing cohort allowlist; keep top-level schema versions unchanged.
5. Run focused GREEN tests including matching outcome and historical schema fixtures.

**Focused Verification:**
```bash
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest -q tests/test_improvement.py -k 'scan and (outcome or correlation or cohort)'
```

**Expected Result:** Matching explicit outcome remains authoritative; mismatch becomes payload-free gap and cannot become explicit success.

## Task 3: Actionable CLI recovery [Depends on: Task 1]

**Context:** Generic failure currently recommends retrying the same direct-start command in the same conflicting session.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_agnt.py`
- Test: `tests/test_improvement.py`

**Steps:**
1. Add direct-start and manual CLI tests for conflict-specific, payload-free recovery.
2. Confirm RED against generic error/retry behavior.
3. Catch only `SessionWorkItemConflict` separately. Preserve generic redaction for all other failures.
4. Emit `/clone` and `/new`, target retry command, and `safeToRetry: false` for direct-start; never emit previous owner or session ID.
5. Run focused GREEN tests.

**Focused Verification:**
```bash
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest -q tests/test_agnt.py -k direct_start tests/test_improvement.py -k 'improve and (link or outcome)'
```

**Expected Result:** Conflict recovery is actionable and privacy-safe; unrelated link failures retain current generic retry semantics.

## Task 4: Documentation and complete verification [Depends on: Tasks 1-3]

**Context:** Operators must know one work item maps to one logical session and full restart/resume does not imply a fresh identity.

**Files:**
- Modify: `pi/agent/bin/README.md`
- Modify: `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Document one-work-item ownership, same-Bead idempotence, `/clone`/`/new` recovery, and mismatch-gap scan behavior.
2. Run focused tests, Ruff, full project tests, config/shell/eval checks, and diff checks once on stable candidate.
3. Request independent boundary review focused on fail-closed ownership, historical mismatch handling, bounded reads, output privacy, and CLI recovery.
4. Fix only confirmed task-scoped findings test-first; rerun invalidated gates.
5. Commit one atomic task-owned implementation commit.

**Expected Result:** Stable verified branch commit, with integration/deployment/Bead closure still separately gated.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt_lib/improvement.py` | 1, 2, 3 | Execute serially in task order. |
| `tests/test_improvement.py` | 1, 2, 3 | Add one RED/GREEN group at a time. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-09-session-work-item-ownership-design-plan.md`

Recommended next skill: `test-driven-development`; use `verification-before-completion` before claiming completion.
