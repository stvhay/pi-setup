# Local Integration Semaphore Design and Implementation Plan

**Issue:** `pi-c65z.3` — Serialize parallel integration with a merge semaphore
**Design:** `.pi/plans/2026-08-11-nominal-approval-gate-audit.md`
**Date:** 2026-08-12
**Branch:** `main` (project-authorized direct work)

**Goal:** Serialize approved local merges into one shared Git target and fail closed on divergence or conflict without adding a daemon.

**Architecture:** Add one `agnt_lib` integration module and expose it through `agnt work integrate`. A target-ref-scoped `fcntl.flock` file lives under Git's common directory, so linked worktrees share it; kernel ownership releases automatically on process death. Persistent metadata is advisory evidence only: opaque lock/owner IDs, state, and timestamps, never repository paths, branch names, arguments, or content. The command acquires the semaphore before revalidating exact target branch/HEAD and source commit, requires a clean target, runs one local `git merge --no-edit --no-verify`, verifies ancestry and cleanliness, and aborts conflicts without reset or alternate strategy.

**Native Git evaluation:** `git worktree lock` prevents administrative prune/move/remove of one linked worktree; it does not serialize commands inside that worktree or hold a transaction across preflight, merge, and verification. Git's internal index/ref lockfiles protect individual writes but not this multi-command invariant. Existing project `fcntl.flock` patterns provide process-death recovery without lease daemons or PID-based lock stealing.

**Deliberate limits:** POSIX-only, matching existing `fcntl` usage and supported CI/runtime. One target ref serializes; unrelated target refs use different lock files. Interrupted Git mutation may leave target dirty, but next holder cannot proceed because clean-state and exact-HEAD checks fail. No automatic destructive recovery.

**Acceptance Criteria:**
- [ ] Concurrent attempts for one target ref enter mutation serially; target preconditions are rechecked under lock.
- [ ] Kernel lock release lets a successor continue after killed holder; stale advisory metadata is reported safely.
- [ ] Lock evidence contains no secrets, Git refs, command arguments, or private paths.
- [ ] Conflicts abort and restore exact baseline HEAD/clean status; ambiguous recovery stops.
- [ ] Tests cover concurrency, conflict, killed/stale holder recovery, cancellation/timeout, and unrelated linked-worktree preservation.
- [ ] Policy permits only exact initially approved local integration through this guard; remote mutation and history rewrite remain gated.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_integration.py tests/test_agnt.py tests/test_context_architecture.py -q
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Test lock and merge behavior

**Files:**
- Create: `tests/test_integration.py`

**Steps:**
1. Add real temporary-repository tests for serialized concurrent merges, killed-holder recovery, timeout/cancellation, conflict rollback, and unrelated linked-worktree preservation.
2. Run focused tests and confirm expected failure because integration module/command is absent.

### Task 2: Implement minimal guarded integration

**Files:**
- Create: `pi/agent/bin/agnt_lib/integration.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`

**Steps:**
1. Add target-ref lock identity and `fcntl` acquisition with bounded wait/cancellation.
2. Store only sanitized advisory owner state in lock file.
3. Add exact in-lock Git preflight, local merge, conflict abort, and post-merge checks.
4. Add `agnt work integrate` adapter and bounded JSON/exit statuses.
5. Run focused tests to green.

### Task 3: Align policy and command docs

**Files:**
- Modify: `AGENTS.md`
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/skills/dev-workflow-common/SKILL.md`
- Modify: `pi/agent/skills/subagent-driven-development/SKILL.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `tests/test_context_architecture.py`

**Steps:**
1. Permit one exact initially approved local merge through the guarded helper after source/target/HEAD binding.
2. Keep fetch/push/remote mutation, alternate conflict repair, reset/force/clean, and history rewrite outside that authority.
3. Document ownership, timeout, cancellation, stale-holder evidence, conflict rollback, and POSIX limit.
4. Add architecture assertions, run focused checks, then final project gates.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-12-integration-semaphore-design-plan.md`.
Recommended skills: `test-driven-development`; `verification-before-completion` before commit.
