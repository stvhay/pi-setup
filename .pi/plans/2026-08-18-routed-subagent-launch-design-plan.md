# Routed Subagent Launch Design and Implementation Plan

**Issue:** pi-hnue — Launch routed subagents in one tool call
**Design:** Bead `pi-hnue`
**Date:** 2026-08-18
**Branch:** `main`

**Goal:** Let one `subagent` call ask deterministic `agnt route` policy to select and launch each routed child without changing manual or inherited launches.

**Architecture:** `pi/agent/extensions/archimedes.ts` remains the only launch adapter. It validates optional single/per-child route intents, calls `agnt route` through `runAgntJson`, intersects route limits with caller limits, strips local fields, delegates to upstream Archimedes, and brands aligned child results with validated route receipts. `subagent-error-workaround.ts` prefers those receipts for route task and execution dimensions while retaining existing fallbacks for unrouted calls.

**Acceptance Criteria:**
- [ ] Single and parallel route intents select and launch upstream children in stable order.
- [ ] Route/manual selection conflicts, route failure, no candidate, and malformed output fail before upstream launch.
- [ ] Caller limits may tighten but never widen route-generated limits.
- [ ] Final result details contain validated route receipts; observer metrics/projections prefer them.
- [ ] Manual model/agent launches and parent inheritance remain unchanged.
- [ ] User docs describe one-call routed launch and manual fallback.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_agent_os_compat.py tests/test_subagent_workaround.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Specify routed launch behavior

**Files:**
- Modify: `tests/test_agent_os_compat.py`
- Modify: `tests/test_subagent_workaround.py`

**Steps:**
1. Add wrapper integration assertions for route schema, single/parallel selection, stable receipt order, stricter caller limits, conflict rejection, and route failure/malformed output before launch.
2. Add observer assertions proving trusted receipts override conflicting caller/upstream dimensions.
3. Run focused tests and confirm expected RED failures.

### Task 2: Implement route adapter

**Files:**
- Modify: `pi/agent/extensions/archimedes.ts`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`

**Steps:**
1. Add bounded route schema and CLI argument mapping.
2. Validate selected route output and build trusted receipts.
3. Resolve routes before policy/launch, intersect limits, preserve parallel indexes, and annotate final results.
4. Reject ambiguous or failed routing with zero upstream launches.
5. Prefer receipts in observer task/model/provider/mode/thinking dimensions.
6. Run focused tests to GREEN.

### Task 3: Align public documentation

**Files:**
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `docs/extension-web-compatibility.md`
- Modify if required by validation: `docs/ARCHITECTURE.md`

**Steps:**
1. Replace copy-then-launch guidance with optional one-call `route` flow while retaining manual CLI flow.
2. Document exclusivity, fail-closed behavior, limit intersection, receipts, and parallel form.
3. Run focused and full verification matrix.

## File Conflicts

Tasks 1 and 2 touch coupled wrapper/observer behavior and run serially under TDD. Documentation follows stable implementation.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-18-routed-subagent-launch-design-plan.md`.
Recommended skills: `test-driven-development`, then `verification-before-completion`.
