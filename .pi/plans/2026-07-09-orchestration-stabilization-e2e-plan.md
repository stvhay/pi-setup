# Orchestration Stabilization and End-to-End Test Plan

**Issue:** pi-2m1.20 — Make runner implementation workers execute in approved worktree with write-capable repair tools
**Design:** docs/ORCHESTRATION-LOOP.md, docs/RUNNER-SERVICE.md, docs/RUN-ARTIFACTS.md
**Date:** 2026-07-09
**Branch:** main

**Goal:** Make the Beads → runner daemon → run artifact → worker → verification/closeout loop stable enough that normal work does not require manual shell babysitting.

**Architecture:** Keep the main Pi TUI as an orchestrator/client and the project-local runner service as the execution boundary. Temporary repair mode should load the real orchestrator-service but disable only its tool restriction. Implementation workers must launch in the approved epic worktree with explicitly bounded write tools and without loading the orchestrator-service extension that strips write tools. End-to-end confidence should come from deterministic pytest coverage first, then one controlled live smoke with durable Beads/run evidence.

**Acceptance Criteria:**
- [ ] A temporary repair-mode launcher remains available while the normal runner path is unstable and is documented as temporary.
- [ ] Implementation run bundles launch workers in `invocation.worktree.path`, with write-capable tools and no orchestrator-service extension.
- [ ] Review/verify/read-only run bundles remain read-only and do not receive edit/write tooling.
- [ ] The runner daemon starts autonomously, reports `schedulerEnabled=true`, skips unmanaged ready Beads without blocker spam, and schedules dispatchable managed work.
- [ ] The runner can process a controlled approved implementation smoke from Beads to run artifact to worker attempt without manual tick/reset commands.
- [ ] Failure states are accurate: no live service is reported as `not-running` because of tick timeout, blocked work produces durable/actionable blockers, and active runs are visible.
- [ ] Closeout evidence is in Beads and `.pi/runs`; no runtime `.pi/runner/` state is treated as durable evidence.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/ -q
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
PI_CONFIG_DIR=/Users/hays/.pi scripts/check-pi-config.sh
pi/agent/bin/agnt work daemon status --json
pi/agent/bin/agnt work runner status --json
```

---

## Current Findings / Root Causes

1. **Runner can schedule but implementation workers are not yet trustworthy.** `pi-2m1.19` fixed metadata-action dispatch, daemon auto-scheduling, undrain recovery, timeout reporting, and unmanaged Bead skipping. The remaining blocker is `pi-2m1.20`: run invocation currently shells out to `pi` without proving the worker is in the approved worktree or has write tools.
2. **Normal Pi deliberately removes write tooling.** `pi/agent/extensions/orchestrator-service.ts` calls `setActiveTools()` for the main TUI. Worker invocations must therefore bypass that extension or explicitly override tooling.
3. **The repair-mode launcher is the correct temporary bootstrap escape hatch.** `scripts/pi-bootstrap-repair-mode.sh` loads normal extensions, including orchestrator-service, but sets `PI_ORCHESTRATOR_REPAIR_TOOLS=1` so only tool restriction is disabled.
4. **Manual shell commands are symptoms to remove.** Every manual reset/tick/curl sequence seen in this session should become either automatic service behavior or a single documented diagnostic command with accurate output.

## Task 1: Stabilize temporary repair mode [Independent]

**Context:** We need a reliable way to continue repairs without normal orchestrator-service removing edit tools. This is temporary and should not be confused with the production path.

**Files:**
- Modify: `scripts/pi-bootstrap-repair-mode.sh`
- Modify: `README.md` or `docs/RUNNER-SERVICE.md`
- Test: `bash -n scripts/*.sh`

**Steps:**
1. Keep `scripts/pi-bootstrap-repair-mode.sh` as the blessed bootstrap launcher.
2. Add a short doc section: when to use it, what it loads, why orchestrator-service remains loaded, and when to stop using it.
3. Ensure it includes ticket/approval tools and edit tooling.
4. Ensure it sets `PI_ORCHESTRATOR_REPAIR_TOOLS=1` rather than disabling extensions.

**Focused verification:**
```bash
bash -n scripts/pi-bootstrap-repair-mode.sh
rg -n "pi-bootstrap-repair-mode|temporary bootstrap repair" README.md docs/RUNNER-SERVICE.md scripts/pi-bootstrap-repair-mode.sh
```

**Expected result:** The launcher syntax is valid and docs clearly identify it as a temporary repair path.

## Task 2: Fix implementation worker launch mode [Depends on: Task 1]

**Context:** `pi-2m1.20` is the highest-priority implementation blocker. `invoke_run_bundle()` calls `invoke_one()` which shells out to `pi` without using the worktree path or selecting tools by allowed effects. This must be fixed before trusting runner-executed implementation work.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/invoke.py`
- Modify: `pi/agent/bin/agnt_lib/runs.py`
- Modify: `pi/agent/bin/agnt_lib/runner_scheduler.py` only if active-run snapshots need worker-mode fields
- Test: `tests/test_agnt.py` or new focused invoke/runs tests
- Test: `tests/test_runner.py`, `tests/test_runner_scheduler.py`

**Steps:**
1. Write RED tests for `invoke_run_bundle()` with an implementation invocation containing:
   - `worktree.path` pointing at a temp directory;
   - `allowedEffects` including `edit_files`/`write_workspace`;
   - `action=implement`.
2. Assert the spawned `pi` command uses:
   - `cwd=invocation.worktree.path`;
   - `--no-extensions` or an equivalent worker mode that excludes orchestrator-service;
   - explicit `--tools read,bash,edit,write,grep,find,ls` plus required ticket tools if available;
   - recorded session args when requested.
3. Write RED tests for review/verify invocations proving they remain read-only and do not receive edit/write tools.
4. Implement a small worker-launch policy function, e.g. `worker_launch_options(invocation)`, rather than scattering flags.
5. Preserve metrics/session behavior.
6. Ensure unsafe or missing worktree paths fail loudly for implementation actions.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_runner.py tests/test_runner_scheduler.py -q
```

**Expected result:** Tests prove implementation workers get write-capable no-orchestrator launch options in the approved worktree; read-only workers remain read-only.

## Task 3: Deterministic end-to-end runner fixture [Depends on: Task 2]

**Context:** Before spending model calls, add a deterministic pytest that exercises the orchestration path without relying on a model behaving correctly.

**Files:**
- Modify/Create: `tests/test_runner_e2e.py` or extend `tests/test_runner_service.py`
- Modify: `pi/agent/bin/agnt_lib/runner_client.py`, `runner_service.py`, `runner_scheduler.py` only if test exposes gaps

**Steps:**
1. Build a temp git repo/worktree fixture with a fake managed Bead:
   - `metadata.pi.action=implement`, `approved=true`, `epicId`, `worktreePolicy=epic-worktree`, `writeSet`, closeout flags.
2. Use fake Beads runner data and fake `invoke_one()`/subprocess to avoid real model calls.
3. Start `start_runner_service(... auto_schedule=True, scheduler_interval=...)`.
4. Assert the daemon autonomously schedules the managed work.
5. Assert it writes an active-run snapshot during execution and clears it afterward.
6. Assert the run bundle contains correct invocation fields, selected action, worktree, allowed effects, session refs, and result evidence.
7. Assert unmanaged ready items are skipped and do not create blockers.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_e2e.py tests/test_runner_service.py tests/test_runner_scheduler.py -q
```

**Expected result:** A deterministic service-level e2e test passes without manual ticks, model calls, or shell resets.

## Task 4: Live controlled smoke test command [Depends on: Task 3]

**Context:** Unit/integration tests are necessary but do not prove the installed Pi/extension/runtime path. Add a bounded smoke that operators can run once after deploy.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py` or add `pi/agent/bin/agnt_lib/smoke.py`
- Modify: `pi/agent/bin/README.md`
- Test: focused CLI tests

**Steps:**
1. Add an explicit smoke command or documented recipe, not hidden behavior. Candidate:
   ```bash
   agnt work smoke runner-e2e --json --dry-run
   agnt work smoke runner-e2e --json --apply
   ```
2. The smoke should create/use a disposable Beads work item only with explicit `--apply`.
3. The smoke should target a safe temporary file under a test fixture/worktree path and cleanly report how to revert/close.
4. The smoke should never push, merge, deploy, delete branches/worktrees, or rewrite Beads history.
5. The smoke result must include exact next action if it cannot run.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner*.py tests/test_agnt.py -q
pi/agent/bin/agnt work smoke runner-e2e --json --dry-run
```

**Expected result:** Dry-run smoke is deterministic and actionable. Apply mode is separately human-approved before use.

## Task 5: Normal startup/recovery soak [Depends on: Task 2]

**Context:** We need confidence that a normal `pi` launch no longer needs manual shell work.

**Files:**
- Modify tests/docs only unless gaps are found:
  - `tests/test_orchestrator_extension.py`
  - `docs/RUNNER-SERVICE.md`
  - `.pi/runs/<soak-run>/` evidence

**Steps:**
1. Deploy tracked config to live config:
   ```bash
   scripts/bootstrap-pi-config.sh --apply
   PI_CONFIG_DIR=/Users/hays/.pi scripts/check-pi-config.sh
   ```
2. Restart Pi normally, not repair mode.
3. Confirm the orchestrator extension starts or attaches the service without manual reset.
4. Confirm status reports:
   - `running=true`
   - `draining=false`
   - `acceptingNewWork=true`
   - `schedulerEnabled=true`
   - no stale active runs
5. Exit/restart Pi once to verify lease release, drain, resume/upgrade behavior.
6. Record evidence in Beads/run notes.

**Focused verification:**
```bash
PI_CONFIG_DIR=/Users/hays/.pi scripts/check-pi-config.sh
pi/agent/bin/agnt work daemon status --json
pi/agent/bin/agnt work runner status --json
```

**Expected result:** Normal Pi startup reaches healthy orchestrator/runner state without shell reset commands.

## Task 6: Closeout gates and docs [Depends on: Tasks 1-5]

**Context:** Stabilization is not done until downstream agents can understand how to operate and verify the system.

**Files:**
- Modify: `docs/RUNNER-SERVICE.md`
- Modify: `docs/ORCHESTRATION-LOOP.md`
- Modify: `docs/RUN-ARTIFACTS.md`
- Modify: `pi/agent/bin/README.md`
- Update: relevant Beads closeout notes

**Steps:**
1. Document normal mode vs temporary repair mode.
2. Document runner worker launch guarantees.
3. Document smoke/e2e commands.
4. Reconcile `pi-2m1.20` and any new follow-up Beads.
5. Run full verification.

**Focused verification:**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/ -q
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

**Expected result:** Full checks pass, docs match behavior, and Beads closeout contains evidence.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt_lib/runs.py` | Task 2, Task 3 | Task 3 depends on Task 2 and should only add e2e coverage unless gaps are found. |
| `pi/agent/bin/agnt_lib/invoke.py` | Task 2, Task 4 | Task 4 depends on Task 2; do not add smoke behavior until worker launch policy is stable. |
| `docs/RUNNER-SERVICE.md` | Task 1, Task 5, Task 6 | Task 6 consolidates docs after behavior is proven. |
| `tests/test_runner_scheduler.py` | Task 2, Task 3 | Add focused unit tests first; e2e tests should avoid duplicating scheduler internals. |

## Approval / Execution Gates

- Task 1 is already approved as part of repair-mode setup.
- Task 2 is covered by `pi-2m1.20` but needs explicit implementation approval before edits beyond planning.
- Task 4 `--apply` live smoke requires a separate approval because it creates/mutates Beads and may invoke a model.
- Cleanup of `.worktrees/`, stale `.pi/runner.stale-*`, branches, or runtime archives requires separate explicit approval.
- Commit/push/merge/deploy beyond `scripts/bootstrap-pi-config.sh --apply` requires separate explicit approval.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-09-orchestration-stabilization-e2e-plan.md` (verify with `test -f`).
Recommended next skill: `test-driven-development` for Task 2 behavior changes; `verification-before-completion` before claiming completion.
