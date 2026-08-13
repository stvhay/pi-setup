# Epic Footer Rendering Implementation Plan

**Issue:** pi-dfko — Design and implement in-progress Epic footer rendering
**Design:** Approved option 1 — fixed `◆` glyph slot
**Date:** 2026-08-13
**Branch:** main

**Goal:** Propagate Beads issue type into the portable footer status and distinguish Epics without changing sorted, aligned, responsive row behavior.

**Architecture:** `agnt work status` adds canonical `issueType` to each item while retaining priority/ID ordering. `beads-footer.ts` validates the optional typed field for backward compatibility and renders a fixed-width type slot: `◆` for Epics, blank for other types. Archimedes continues to treat each newline-delimited row as opaque text, so its existing sanitization and width truncation remain authoritative.

**Acceptance Criteria:**
- [ ] `agnt work status` exposes issue type and preserves priority/ID sorting.
- [ ] Footer distinguishes Epic rows with `◆`, aligns ordinary and Epic rows, and preserves current-session styling.
- [ ] Malformed typed payloads clear status; legacy payloads without type remain ordinary rows.
- [ ] Relevant docs and focused regressions describe the portable contract and rendering.
- [ ] Project verification passes; deployment remains separately gated.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_beads_footer.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
npm --prefix forks/pi-archimedes/packages/footer test -- --run
scripts/apply-pi-package-patches.sh --check
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/
```

---

### Task 1: Propagate issue type [Independent]

**Context:** `work_status()` currently emits only `id`, `priority`, and `title`.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Test: `tests/test_agnt.py`

**Steps:**
1. Extend the status item contract with `issueType` derived from Beads `issue_type` (or legacy `type`).
2. Keep the existing priority/ID sort.
3. Add Epic and ordinary fixtures to the existing ordering test.
4. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py -k work_status
```

### Task 2: Render Epic slot [Depends on: Task 1]

**Context:** `beads-footer.ts` validates and formats keyed status text; existing Archimedes patch splits and truncates each row.

**Files:**
- Modify: `pi/agent/extensions/beads-footer.ts`
- Test: `tests/test_beads_footer.py`

**Steps:**
1. Add typed item validation with missing-type fallback to ordinary.
2. Render `◆` in a fixed type column for Epics and blanks for other issue types.
3. Add focused tests for Epic/ordinary alignment, current-session styling, legacy payloads, and malformed types.
4. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_beads_footer.py
```

### Task 3: Update contract docs [Depends on: Task 2]

**Context:** User-visible format is documented in `pi/README.md` and `docs/extension-web-compatibility.md`.

**Files:**
- Modify: `pi/README.md`
- Modify: `docs/extension-web-compatibility.md`

**Steps:**
1. Document `issueType` propagation and fixed Epic glyph slot.
2. Document priority/ID ordering and existing width behavior.
3. Run config/documentation-related checks.

**Focused verification:**
```bash
rg -n "issueType|◆|priority/ID|Epic" pi/README.md docs/extension-web-compatibility.md
```

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-13-epic-footer-design-plan.md` (verified after write).
Recommended next skill: test-driven-development, then verification-before-completion.
