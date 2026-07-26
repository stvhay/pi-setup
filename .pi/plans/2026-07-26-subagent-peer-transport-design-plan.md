# Subagent Peer Transport Design and Implementation Plan

**Issue:** pi-6kep — Route interactive peers through Archimedes subagent
**Design:** Approved in conversation; captured here
**Date:** 2026-07-26
**Branch:** main (same-tree work explicitly approved)

**Goal:** Use Archimedes `subagent` for interactive peer execution and live TUI status while retaining `agnt` routing, persistent metrics, and cold one-shot/headless execution.

**Architecture:** Interactive skills run `agnt route`, then call the `subagent` tool with `agent` omitted and the routed model supplied. Existing `subagent-error-workaround.ts` also records each completed Archimedes result as a schema-v1 metric without storing prompts or outputs. `agnt invoke --one-shot` remains the cold review path; run-artifact/headless execution remains unchanged.

**Non-goals:** Replace or copy Archimedes; deep-import Archimedes internals; add named agent profiles; add a subagent wall-clock timeout; remove `agnt invoke`; migrate optional run-artifact workers; contact or modify upstream projects.

**Acceptance Criteria:**
- [x] Interactive skill guidance routes models with `agnt route` and invokes unnamed `subagent` calls, including parallel `tasks` calls.
- [x] `requesting-code-review` retains cold `agnt invoke --one-shot` behavior.
- [x] Completed single and parallel unnamed subagent results create ignored schema-v1 records under `<git-root>/.pi/metrics/invocations/`; named profiles are skipped when provider attribution is unavailable.
- [x] Metric records store counts and lengths, not prompt or response bodies.
- [x] Existing empty/nonzero subagent failure normalization remains intact.
- [x] Architecture and self-improvement docs describe Archimedes as interactive transport and `agnt` as routing/recording plus headless execution.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_subagent_workaround.py tests/test_context_architecture.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
git diff --check
```

---

### Task 1: Specify transport and metrics behavior [Independent]

**Files:**
- Modify: `tests/test_subagent_workaround.py`
- Modify: `tests/test_context_architecture.py`

**Steps:**
1. Add a test that sends a completed single subagent result through the extension and asserts a schema-v1 metric with target, usage, elapsed time, lengths, and no prompt/output body.
2. Add parallel coverage and retain existing failure/success passthrough assertions.
3. Add a static skill invariant: `agnt invoke` in active skills must be cold `--one-shot` usage.
4. Run focused tests and confirm failure because metrics recording and guidance migration do not exist.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_subagent_workaround.py tests/test_context_architecture.py
```

### Task 2: Record Archimedes results [Depends on: Task 1]

**Files:**
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`

**Steps:**
1. Track subagent start time by tool-call id.
2. Convert each completed result to the existing schema-v1 metric shape.
3. Resolve repository root from `ctx.cwd`; write unique records under `.pi/metrics/invocations/`.
4. Store only prompt/output lengths and usage totals; never persist bodies.
5. Preserve current failure normalization and make telemetry failure non-fatal.
6. Run focused tests to green.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_subagent_workaround.py
```

### Task 3: Migrate interactive skill guidance [Depends on: Task 1]

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/skills/dev-workflow-common/SKILL.md`
- Modify: `pi/agent/skills/dispatching-parallel-agents/SKILL.md`
- Modify: `pi/agent/skills/subagent-driven-development/SKILL.md`
- Modify: `pi/agent/skills/research/SKILL.md`
- Modify: `pi/agent/skills/research/workflows/QuickResearch.md`
- Modify: `pi/agent/skills/research/workflows/StandardResearch.md`
- Modify: `pi/agent/skills/research/workflows/ExtensiveResearch.md`
- Modify: `pi/agent/skills/council/SKILL.md`
- Modify: `pi/agent/skills/council/workflows/Quick.md`
- Modify: `pi/agent/skills/redteam/SKILL.md`
- Modify: `pi/agent/skills/redteam/references/ParallelAnalysis.md`
- Modify: `pi/agent/skills/hypothesis-tournament/SKILL.md`
- Modify: `pi/agent/skills/verification-before-completion/SKILL.md`
- Modify: `pi/agent/skills/writing-plans/SKILL.md`

**Steps:**
1. Define one shared pattern: route with `agnt route`, pass the selected target as `model`, omit `agent`, and use the `tasks` array for parallel work.
2. Replace shell-background fanout examples with subagent tool payloads.
3. Tell the parent to persist returned outputs only when downstream workflows require files.
4. Keep read-only/worktree/verification/URL-validation gates unchanged.
5. Leave `pi/agent/skills/requesting-code-review/SKILL.md` on `agnt invoke --one-shot`.
6. Run the static skill invariant to green.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py
```

### Task 4: Align tracked docs [Depends on: Tasks 2 and 3]

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `pi/agent/bin/README.md`

**Steps:**
1. Show `agnt route -> Archimedes subagent -> metrics` as the interactive path.
2. Describe `agnt invoke` as cold/headless and run-artifact transport rather than default interactive peer transport.
3. State that the observer captures subagent counts/usage without prompt/output bodies.
4. Keep runtime telemetry ignored and consolidation behavior unchanged.

**Focused verification:**
```bash
rg -n "Archimedes|subagent|one-shot|metrics" docs/ARCHITECTURE.md docs/AGNT-SYSTEM.md docs/SELF-IMPROVEMENT.md
```

### Task 5: Full verification and review [Depends on: Tasks 2, 3, and 4]

**Steps:**
1. Run all verification commands from the header.
2. Inspect `git diff --stat`, `git diff --check`, and scoped diff.
3. Run a cold review through `agnt invoke --one-shot`; verify findings against files/tests.
4. Update and close `pi-6kep` only after evidence passes.
5. Do not commit unless separately requested.

## File Conflicts

Tasks 2 and 3 are independent after Task 1. Task 4 depends on both because docs describe their combined behavior.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-26-subagent-peer-transport-design-plan.md`
Recommended next skill: `test-driven-development`; use `verification-before-completion` before claiming completion.
