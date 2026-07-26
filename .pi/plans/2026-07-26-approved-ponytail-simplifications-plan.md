# Approved Ponytail Simplifications Implementation Plan

**Issue:** pi-gk9t — Apply approved ponytail simplifications
**Design:** Bead `pi-gk9t`
**Date:** 2026-07-26
**Branch:** main

**Goal:** Remove approved dead/generated surfaces and consolidate duplicated extension process runners while preserving lesson sync and local/on-prem electricity accounting.

**Architecture:** Delete features at their CLI and module boundaries. Keep runner service, lesson server/client, and electricity/opportunity-cost paths intact. Move repeated successful-exit JSON subprocess handling into one non-auto-discovered extension helper under `pi/agent/extensions/lib/`; keep guidance guard's fail-open stdin flow separate.

**Acceptance Criteria:**
- [ ] Generated science-family review artifacts and Pong benchmark are absent.
- [ ] `metrics import-session`, `lessons_harvest_plan`, `runner_loop`, dead symbols, and ignored runner tick path hints are absent.
- [ ] Beads bridge, ticket gateway, and orchestrator service share one agnt JSON runner.
- [ ] Ruff F401 passes and is enforced.
- [ ] Lesson sync/server and local electricity-cost tests pass.
- [ ] Full project verification passes.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Lock changed surfaces with focused checks

**Files:** `tests/test_cli_nameerrors.py`, `tests/test_runner.py`, `tests/test_orchestrator_extension.py`, `pyproject.toml`

1. Replace Pong smoke coverage with removed CLI-surface assertions.
2. Require runner tick client calls to omit ignored path hints.
3. Require three extensions to import one helper and avoid local `execFile` JSON runners.
4. Run focused pytest and Ruff F401; confirm expected RED failures.

### Task 2: Delete approved Python and generated content

**Files:** `.pi/skill-evals/google-science-family/review/`, `pi/agent/bin/agnt_lib/benchmark.py`, `pi/agent/bin/agnt`, `pi/agent/bin/agnt_lib/metrics.py`, `pi/agent/bin/agnt_lib/maintenance.py`, `pi/agent/bin/agnt_lib/runner.py`, `pi/agent/bin/agnt_lib/runner_client.py`, `pi/agent/bin/agnt_lib/work.py`, related tests

1. Delete generated review artifacts and benchmark module/dispatch.
2. Delete session importer and its CLI branch.
3. Delete test-only lesson harvest planner and obsolete runner loop.
4. Delete `_runner_symbol`, `_is_dict`, dead extension constants, and ignored tick path plumbing.
5. Run focused tests.

### Task 3: Consolidate extension subprocess runners

**Files:** `pi/agent/extensions/lib/run-agnt-json.ts` (new), `beads-ask-bridge.ts`, `ticket-gateway.ts`, `orchestrator-service.ts`

1. Add one minimal abort-aware `execFile` helper preserving stderr/stdout errors and JSON parse diagnostics.
2. Replace duplicated local runners; retain ticket gateway's payload wrapper.
3. Do not change `guidance-edit-guard.ts`, whose stdin/fail-open semantics differ.
4. Load extensions through Pi and run focused extension tests.

### Task 4: Clean imports and align docs

**Files:** Python files reported by Ruff F401, `pyproject.toml`, `docs/ARCHITECTURE.md`, `pi/agent/bin/README.md`, `pi/agent/tests/agent-context-smoke.sh`

1. Apply Ruff's F401-safe fixes after deletions.
2. Add F401 to configured Ruff selection.
3. Remove benchmark/import-session docs and smoke checks.
4. Preserve lesson sync and electricity-cost docs.

### Task 5: Verify, review, close

Run focused and full verification, inspect diff for accidental changes to lesson/electricity paths, request independent review, fix verified findings, record evidence on `pi-gk9t`, then close it.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-26-approved-ponytail-simplifications-plan.md`
Recommended skills: test-driven-development, verification-before-completion.
