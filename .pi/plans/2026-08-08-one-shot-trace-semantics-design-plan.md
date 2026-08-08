# One-Shot Child Trace Semantics Design Plan

**Issue:** pi-4tg9.15.3 — Make one-shot child trace availability explicit
**Design:** Approved inline 2026-08-08
**Date:** 2026-08-08
**Branch:** `fix/one-shot-trace-semantics`

**Goal:** Distinguish expected one-shot trace isolation from missing successful agentic child traces without weakening isolation or adding Langfuse calls.

**Architecture:** Existing Archimedes results already expose resolved `execution.profile.mode`. The local parent projection will publish validated `effectiveMode` and declared `childTraceAvailability`. Improvement scans will resolve parent projection child IDs against `pi-agent` roots already returned by bounded trace discovery, then emit private per-session and safe cohort count summaries. Missing roots remain unknown when discovery is incomplete; private exact lookup remains live-proof only.

**Non-goals:** No public subagent input/result change, upstream/vendor patch, one-shot extension loading, extra Langfuse query, raw child ID in safe summaries, schema-version bump, or parent-soak closure.

**Availability states:**
- `available`: exactly one completed discovered child root.
- `expected-unavailable`: validated one-shot projection with no discovered root.
- `missing`: successful agentic projection with a child ID but no root under complete discovery.
- `ambiguous`: multiple discovered child roots.
- `incomplete`: discovered child roots exist but none is completed.
- `unknown`: malformed/missing mode or child ID, failed non-one-shot child without a root, or incomplete discovery.

**Acceptance Criteria:**
- [ ] Parent `subagent-result` metadata exposes validated `effectiveMode` and declared `childTraceAvailability`.
- [ ] One-shot isolation and Archimedes execution remain unchanged.
- [ ] Scanner uses only already-discovered traces and reports count-only per-session/cohort availability states.
- [ ] Successful agentic missing roots become explicit gaps only under complete discovery.
- [ ] One-shot missing roots become `expected-unavailable`, while a deliberately available completed root becomes `available`.
- [ ] Ambiguous, incomplete, malformed, missing-key, failed, and incomplete-discovery cases remain truthful.
- [ ] Existing schema-1 and schema-2 consumers remain compatible; no raw child IDs enter cohort summaries.
- [ ] Deterministic, full-project, and bounded live regressions pass.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_subagent_workaround.py tests/test_improvement.py -q
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Project effective execution semantics [Independent]

**Files:**
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Test: `tests/test_subagent_workaround.py`

**Steps:**
1. Add RED result-projection tests for agentic, one-shot, missing, and malformed execution evidence.
2. Derive mode only from resolved result execution evidence.
3. Emit `effectiveMode` and declared availability in `subagent-result` metadata without changing tool details or execution.
4. Run focused wrapper tests.

### Task 2: Classify bounded child roots [Depends on: Task 1]

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_improvement.py`

**Steps:**
1. Add RED pure and scanner-level tests covering every availability state and complete/incomplete discovery.
2. Index `pi-agent` roots by child session from existing bounded discovery.
3. Add a pure count-only reducer consumed by `_features()` and `_cohort_health()`.
4. Mark only confirmed successful-agentic misses as capture gaps; keep expected isolation distinct.
5. Preserve top-level schema versions and historical packet validation.

### Task 3: Align documentation [Depends on: Task 2]

**Files:**
- Modify: `pi/README.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify if needed: `docs/extension-web-compatibility.md`

**Steps:**
1. Document effective mode, declared expectation, bounded discovered-root classification, and lower-bound semantics.
2. State that one-shot isolation remains unchanged and exact private lookup is separate live proof.

### Task 4: Verify, review, and stage [Depends on: Tasks 1–3]

1. Run focused and full verification commands.
2. Run one subscription-backed Terra review; verify any serious finding test-first.
3. Commit one clean signed candidate.
4. Request separate approval for local-main integration, deployment, bounded live agentic/one-shot proof, Bead closeout, and worktree cleanup.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-08-one-shot-trace-semantics-design-plan.md`.
Recommended next skill: `test-driven-development`; use `verification-before-completion` before completion claims.
