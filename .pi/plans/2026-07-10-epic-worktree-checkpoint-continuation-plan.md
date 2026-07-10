# Epic Worktree Checkpoint Continuation Implementation Plan

**Issue:** pi-2m1.27.3 — Support dependent implementation continuation after dirty epic worktree checkpoint
**Design:** User decision pi-5eu; approval pi-19q
**Date:** 2026-07-10
**Branch:** main (runner implementation executes only in `epic/pi-2m1`)

**Goal:** Let ordered implementation stages continue in an approved epic worktree by creating an evidenced local checkpoint after a successful predecessor instead of blocking on its expected dirty state.

**Architecture:** Preserve the default dirty-worktree block for all unrelated work. Add an explicit, metadata-gated continuation policy for dependent epic-worktree implementation tasks. The scheduler records the pre-checkpoint baseline SHA, checkpoint SHA, scoped status/diff evidence, and predecessor bead/run in the successor run bundle; the runner never pushes, merges, removes a worktree, or resets a worktree automatically.

**Acceptance Criteria:**
- [ ] A dirty epic worktree remains blocked unless the next implementation task explicitly permits a recorded continuation checkpoint and depends on the prior stage.
- [ ] The continuation path creates a local commit only in the approved epic worktree and records baseline SHA, checkpoint SHA, status, and diff evidence in the run bundle.
- [ ] The dependent stage autonomously starts without a manual copy, tick, restart, or human-gate workaround.
- [ ] No push, merge, worktree deletion, or reset occurs; later scoped reset remains a separate explicit action under pi-5eu.
- [ ] Existing non-continuation dirty-worktree safeguards remain covered.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_worktree_policy.py tests/test_runner_scheduler.py tests/test_runner.py -q
.venv/bin/python -m pytest tests/ -q
git diff --check
bash -n scripts/*.sh
```

---

### Task 1: Define checkpoint-continuation metadata and pure worktree transition [Independent]

**Context:** `pi/agent/bin/agnt_lib/worktree_policy.py` currently blocks every dirty epic worktree in `resolve_epic_worktree()`. Introduce a narrow opt-in continuation contract that requires an implementation action, epic-worktree policy, explicit predecessor dependency/reference, and checkpoint approval reference. Keep all current dirty-worktree results unchanged when that contract is absent.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/orchestration.py`
- Modify: `pi/agent/bin/agnt_lib/worktree_policy.py`
- Test: `tests/test_orchestration.py`
- Test: `tests/test_worktree_policy.py`

**Steps:**
1. Add RED tests proving ordinary dirty worktrees block and only explicit continuation metadata reaches a continuation-needed state.
2. Validate and normalize the opt-in metadata; reject missing predecessor/approval evidence.
3. Add a pure resolver result containing required checkpoint inputs, not a permissive `ready` result.
4. Run focused tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_orchestration.py tests/test_worktree_policy.py -q
```

### Task 2: Create an evidenced local checkpoint before dependent dispatch [Depends on: Task 1]

**Context:** The scheduler currently calls `worktree_resolver()` and creates a human blocker for a non-dispatchable worktree. Add a narrowly injected checkpoint operation for the explicit continuation result. It must use the approved epic worktree only, capture baseline/current SHA plus `git status --short` and scoped diff evidence in the successor bundle, create the local checkpoint, then re-resolve before worker start.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/runner_scheduler.py`
- Modify: `pi/agent/bin/agnt_lib/runs.py`
- Test: `tests/test_runner_scheduler.py`
- Test: `tests/test_runner.py`

**Steps:**
1. Add RED scheduler tests for successful checkpoint-and-start, checkpoint failure without worker start, and ordinary dirty worktree remaining blocked.
2. Implement the smallest injected/subprocess-backed checkpoint helper with path/branch guards.
3. Write baseline SHA, checkpoint SHA, status/diff paths, predecessor, and approval reference into successor invocation/result evidence.
4. Re-run the resolver after checkpoint; only then invoke the worker.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_scheduler.py tests/test_runner.py -q
```

### Task 3: Preserve health and closeout semantics [Depends on: Task 2]

**Context:** A checkpointed epic worktree should be clean after the local commit and no longer cause the generic dirty-worktree health failure. Run evidence must make the local commit inspectable and ensure no automatic reset/push/merge behavior exists.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/health.py` only if checkpoint evidence needs an explicit health exception; otherwise no production health change.
- Test: `tests/test_health.py` only if production health behavior changes.
- Modify: `docs/RUNNER-SERVICE.md` if the user-facing continuation contract is added.

**Steps:**
1. Add only needed tests and docs.
2. Run full verification.
3. Deploy only under a separate live-deployment approval.
4. Execute one fresh two-stage Edabit-style normal-path witness, then inspect its baseline/checkpoint evidence and autonomous Stage B dispatch.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/ -q
scripts/check-pi-config.sh
```

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt_lib/runner_scheduler.py` | Task 2 | Sequential after Task 1 metadata contract |
| `tests/test_runner_scheduler.py` | Task 2 | Sequential TDD coverage |

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-10-epic-worktree-checkpoint-continuation-plan.md` (verified next)
Recommended next skill: `test-driven-development` for behavior changes; `verification-before-completion` before claiming completion.
