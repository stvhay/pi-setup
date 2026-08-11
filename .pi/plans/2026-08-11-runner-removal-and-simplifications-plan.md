# Runner Removal and Approved Simplifications Implementation Plan

**Issue:** #pi-4l23 — Remove obsolete runner and simplify agnt surfaces
**Design:** User-approved repo-wide Ponytail audit and 2026-08-11 seam discussion
**Date:** 2026-08-11
**Branch:** main

**Goal:** Remove the obsolete project-local runner automation stack and approved shallow/dead surfaces while preserving direct Pi, Beads, subagent, typed human decisions, manual run bundles, headless workers, and project verification.

**Architecture:** The separate automation project will own long-lived Pi runtime scheduling. This repository keeps deterministic domain logic under `agnt_lib`, a thin `agnt` CLI adapter for humans/CI/headless callers, Pi extensions for lifecycle/UI/provider integration, and typed tools as thin agent-facing adapters. Runner-only code is deleted rather than replaced; manual `agnt runs` and `agnt work` artifact execution remain.

**Acceptance Criteria:**
- [ ] Runner daemon, REST client/protocol/service/scheduler, orchestrator extension, runner gateway operation, startup profile, runner health checks, and runner-only docs/tests are absent.
- [ ] Direct Bead start/closeout, manual work plan/start/run/finish, run bundles, internal headless invocation, routing, approvals, ticket list/show/tree/draft, metrics, evals, and subagent delegation remain.
- [ ] `list_models`, `agnt recommend`, shallow Graphify/capture wrappers, duplicate agent-dir fallbacks, redundant slug regex, and delegating default export are removed.
- [ ] Only 25 closed-Bead plan files with no current filename references are deleted; eight plans named by closed Beads remain.
- [ ] `.pi/plans/2026-08-11-agnt-surface-seam-audit-plan.md` records the follow-up audit without implementing speculative migrations.
- [ ] User and architecture documentation describe direct Pi plus selective CLI/tool/extension seams without runner claims.
- [ ] Focused and full repository verification pass, followed by one local implementation commit and direct Bead closeout.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Lock removed and retained surfaces

**Context:** Change structural and CLI tests first. Expected failures must prove removed runner commands/files still exist while retained direct/manual paths remain callable.

**Files:**
- Modify: `tests/test_context_architecture.py`
- Modify: `tests/test_agnt.py`
- Modify: `tests/test_ticket_gateway.py`
- Modify: `tests/test_doctor.py`
- Modify: `tests/test_health.py`
- Modify: `tests/test_worktree_policy.py`
- Modify: `tests/test_maintenance.py`
- Rename: `tests/test_runner.py` → `tests/test_runs.py`

**Steps:**
1. Add/update structural assertions requiring runner production files, extension, and docs to be absent.
2. Remove tests whose requested behavior is runner deletion; retain and strengthen direct/manual run tests.
3. Require `agnt work daemon|runner` and gateway `runner_status` to reject as unsupported.
4. Require generic `agnt doctor`, work health, maintenance, and worktree policy to remain functional without runner imports.
5. Run focused tests and record expected RED against current source.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_agnt.py tests/test_ticket_gateway.py tests/test_doctor.py tests/test_health.py tests/test_worktree_policy.py tests/test_maintenance.py tests/test_runs.py
```

**Expected result:** Tests fail only because runner files/commands/profile/operation still exist or removed small surfaces remain.

### Task 2: Delete runner implementation and adapters [Depends on: Task 1]

**Context:** Remove the long-lived automation implementation. Preserve run artifact execution and manual Beads-backed work commands in `runs.py`, `invoke.py`, `work.py`, `orchestration.py`, `approvals.py`, and `worktree_policy.py`.

**Files:**
- Delete: `pi/agent/bin/agnt_lib/runner.py`
- Delete: `pi/agent/bin/agnt_lib/runner_client.py`
- Delete: `pi/agent/bin/agnt_lib/runner_protocol.py`
- Delete: `pi/agent/bin/agnt_lib/runner_scheduler.py`
- Delete: `pi/agent/bin/agnt_lib/runner_service.py`
- Delete: `pi/agent/bin/agnt_lib/startup_policy.py`
- Delete: `pi/agent/extensions/orchestrator-service.ts`
- Delete: `docs/RUNNER-SERVICE.md`
- Delete: `tests/test_orchestrator_extension.py`
- Delete: `tests/test_runner_budget.py`
- Delete: `tests/test_runner_client.py`
- Delete: `tests/test_runner_protocol.py`
- Delete: `tests/test_runner_scheduler.py`
- Delete: `tests/test_runner_service.py`
- Delete: `tests/test_runner_visibility.py`
- Delete: `tests/test_startup_policy.py`
- Modify: `pi/agent/bin/agnt`
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Modify: `pi/agent/bin/agnt_lib/gateway.py`
- Modify: `pi/agent/bin/agnt_lib/doctor.py`
- Modify: `pi/agent/bin/agnt_lib/health.py`
- Modify: `pi/agent/extensions/ticket-gateway.ts`

**Steps:**
1. Delete dedicated runner modules, extension, docs, and tests.
2. Remove runner imports, `work daemon|runner` parsers/handlers, gateway `runner_status`, doctor startup profile, and runner health inspection.
3. Move the generic `check_result` helper into `doctor.py`; remove runner-only intent/profile logic.
4. Keep `.pi/runner/` ignored so stale local token/runtime files cannot become trackable.
5. Run focused tests to GREEN.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_agnt.py tests/test_ticket_gateway.py tests/test_doctor.py tests/test_health.py tests/test_worktree_policy.py tests/test_maintenance.py tests/test_runs.py
```

**Expected result:** Runner surfaces are absent and direct/manual work behavior passes.

### Task 3: Apply approved shallow and dead-code cuts [Depends on: Task 2]

**Context:** Apply independently verified Ponytail findings without adding abstractions.

**Files:**
- Delete: `pi/agent/bin/agnt_lib/graphify.py`
- Modify: `pi/agent/bin/agnt`
- Modify: `pi/agent/bin/agnt_lib/tasks.py`
- Modify: `pi/agent/bin/agnt_lib/core.py`
- Modify: `pi/agent/bin/agnt_lib/metrics.py`
- Modify: `pi/agent/bin/agnt_lib/worktree_policy.py`
- Modify: `pi/agent/extensions/langfuse-config-env.ts`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Modify: `pi/agent/extensions/agent-os-compat.ts`
- Delete: 25 unreferenced closed-Bead files under `.pi/plans/`
- Modify: affected tests/docs

**Steps:**
1. Delete unused `list_models` and `agnt recommend`.
2. Inline Graphify binary/`uv tool run` selection into the front controller.
3. Replace `capture` with direct `subprocess.check_output(..., text=True)` calls.
4. Use Pi `getAgentDir()`, remove the second slug hyphen regex, and export `installAgentOSCompat` directly.
5. Delete only the precomputed set of 25 closed plans with no current filename references.
6. Run focused CLI, extension, worktree, metrics, and config tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_agent_os_compat.py tests/test_langfuse_skill.py tests/test_subagent_workaround.py tests/test_worktree_policy.py tests/test_context_architecture.py
scripts/check-pi-config.sh
```

**Expected result:** Approved small surfaces are absent and existing behavior passes.

### Task 4: Align architecture, instructions, and audit handoff [Depends on: Tasks 2-3]

**Context:** Remove runner claims and state the intended module/interface/adapter seam compactly. Keep detailed command prose out of loaded instructions.

**Files:**
- Create: `.pi/plans/2026-08-11-agnt-surface-seam-audit-plan.md`
- Modify: `README.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ORCHESTRATION-LOOP.md`
- Modify: `docs/RUN-ARTIFACTS.md`
- Modify: `docs/extension-web-compatibility.md`
- Modify: `pi/README.md` if runner wording exists
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/bin/README.md`
- Modify: affected skills/tasks/evals found by exact search

**Steps:**
1. Remove runner service, startup profile, status operation, and daemon command references.
2. Preserve direct Pi, Beads, manual run artifacts, subagent, approval, and headless worker documentation.
3. Add one compact seam rule: `agnt_lib` domain modules; CLI human/CI/headless adapter; extensions lifecycle/UI/provider adapters; typed tools agent-facing adapters.
4. Save and verify the future surface/seam audit plan.
5. Run documentation/config checks and stale-term searches.

**Focused verification:**
```bash
scripts/check-pi-config.sh
rg -n -i 'runner service|runner_status|work daemon|work runner|orchestrator-service|orchestrator-startup' README.md docs pi/agent --glob '!*.patch' && exit 1 || true
test -f .pi/plans/2026-08-11-agnt-surface-seam-audit-plan.md
```

**Expected result:** No active runner claims remain and the audit handoff exists.

### Task 5: Final verification, review, commit, and close [Depends on: Tasks 1-4]

**Steps:**
1. Run focused suites after each changed subsystem.
2. Run the complete verification matrix once against the final candidate.
3. Inspect `git diff --check`, diff/stat, deleted files, and requirement coverage.
4. Run independent read-only review; verify findings locally and fix confirmed issues.
5. Stage only task-owned changes, commit once, record `agnt improve outcome pi-4l23 success`, and run `agnt work direct-closeout pi-4l23`.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt` | Tasks 2-3 | Remove runner import first, then inline Graphify and remove alias. |
| `tests/test_agnt.py` | Tasks 1-3 | Establish retained command behavior before production deletions; update small-surface expectations in same focused suite. |
| architecture/docs | Tasks 2-4 | Code removal precedes one final documentation pass. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-11-runner-removal-and-simplifications-plan.md` (verify with `test -f`)
Recommended next skill: `test-driven-development` for behavior changes; `verification-before-completion` before claiming completion.
