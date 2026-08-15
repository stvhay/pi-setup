# pi-archimedes 2.1.0 Hardening Implementation Plan

**Issue:** pi-rxo3.24 — Stabilize and rebase pi-archimedes fork
**Design:** `.pi/plans/2026-08-15-pi-archimedes-result-port-contract.md`
**Date:** 2026-08-15
**Branch:** `main` plus local fork branches named below

**Goal:** Prove pi-setup against pi-archimedes 2.1.0, rebuild maintained fork stacks without history rewrite, add public result ports, and prepare upstream packets without upstream submission.

**Architecture:** Preserve upstream `v2.1.0@2ed26aa` as immutable base. Rebuild features as a linear local stack with one coherent commit per branch: bounded execution, one-shot mode, repeated-error protection, then public result ports. Build one vendor projection above that stack for pi-setup-only runtime and footer compatibility; pi-setup keeps routing, billing, authority, persistence, and quality policy. Do not migrate `pi/agent/extensions/archimedes.ts` or delete duplicate consumer types yet: contract assigns that adoption to Q21 after an exact public release; this task proves installed patched public imports separately.

**Acceptance Criteria:**
- [ ] Pi-setup uses exact `pi-archimedes@2.1.0` package bases and exact production patches generated from reviewed vendor source.
- [ ] Maintained local candidates have exact base/head evidence, one coherent commit per stack step, clean diffs, and no rewritten existing history.
- [ ] Public `./types`, `./agents`, and `./bus` imports expose contract types/functions and preserve ordered complete result evidence.
- [ ] Focused and full fork checks, package tarball apply/reverse checks, and full pi-setup checks pass.
- [ ] Internal evidence plus reviewer-facing bodies exist; only the separately approved clone-safety vendor-branch push occurs—no upstream-candidate push, PR, merge, deployment, release, or cleanup.

**Verification Command(s):**
```bash
corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit
corepack pnpm -r exec -- tsc --noEmit
corepack pnpm --filter @pi-archimedes/subagent exec vitest run
corepack pnpm test
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Refresh Source Profile [Independent]

**Context:** Refresh `.pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md` for current public source/package state before candidate edits.

**Files:**
- Modify: `.pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md`

**Steps:**
1. Record `main`/tag/npm/package integrity, source hashes, permissions, fork drafts, branch protection, templates, issue/PR state, CI, and clean baseline.
2. Distinguish npm/tag release 2.1.0 from stale GitHub Releases metadata.
3. Keep remote actions excluded during source refresh; any later fork publication requires its own exact approval.

**Focused verification:**
```bash
rg -n '2ed26aa|2\.1\.0|last_checked_utc|status: current-for-target-ref' .pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md
```

**Expected result:** Profile names exact current source and package evidence.

### Task 2: Rebuild Maintained Feature Stack [Depends on: Task 1]

**Context:** Existing remote drafts target `a2bd4d6` and contain merge-heavy histories. Create new local candidates from `v2.1.0` without altering old branches.

**Files:**
- Worktree/branch: `.worktrees/upstream/pi-archimedes-limits-210` / `rebuild/subagent-execution-limits-210`
- Worktree/branch: `.worktrees/upstream/pi-archimedes-one-shot-210` / `rebuild/subagent-one-shot-mode-210`
- Worktree/branch: `.worktrees/upstream/pi-archimedes-repeated-errors-210` / `rebuild/subagent-repeated-errors-210`
- Modify: existing bounded execution, one-shot, repeated-error source/tests/docs carried from reviewed v2 candidates

**Steps:**
1. Create every named branch from immutable predecessor: limits from `2ed26aa`; one-shot from new limits head; repeated-errors from new one-shot head. Do not check out or rewrite existing candidate branches.
2. Carry feature-only deltas from reviewed refs: limits `a2bd4d6..2315b2e`; one-shot `c717d96..8090d0c`; repeated-errors `c717d96..47e30b7`, excluding merge-only/base rollback changes.
3. Install each worktree with `corepack pnpm install --frozen-lockfile` from that worktree cwd.
4. Resolve only 2.1.0 drift. Retain `agents.ts`/`local-config.ts` local thinking overrides and their v2.1.0 tests before every commit.
5. Run focused tests and package TypeScript after each stack step.
6. Commit one coherent commit per branch; verify exact one-commit predecessor ranges and ancestry.

**Focused verification:**
```bash
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit
corepack pnpm --filter @pi-archimedes/subagent exec vitest run
```

**Expected result:** Three clean ordered local candidates with no existing-history rewrite.

### Task 3: Add Public Result Ports [Depends on: Task 2]

**Context:** Implement normative public ports on top of full execution stack. TDD required for new behavior.

**Files:**
- Worktree/branch: `.worktrees/upstream/pi-archimedes-result-ports-210` / `feat/result-ports-210`
- Modify: `packages/subagent/package.json`
- Modify: `packages/subagent/src/types.ts`
- Modify: `packages/subagent/src/agents.ts`
- Modify: `packages/subagent/src/index.ts`
- Modify: `packages/subagent/src/execute.ts`
- Modify: `packages/subagent/src/stream.ts`
- Modify: `packages/core/src/bus.ts`
- Modify: `packages/subagent/README.md`
- Create/modify tests beside affected source
- Create: `docs/plans/done/2026-08-15-public-subagent-result-ports.md`
- Modify: `docs/plans/README.md`

**Steps:**
1. Install worktree dependencies with `corepack pnpm install --frozen-lockfile` from worktree cwd.
2. Add public-import and behavior tests first; confirm RED for missing exports and declarations, single/parallel success and failure, request-order preservation, complete `details.results[]`, retained partial output and usage, resolved limits/termination, output-contract transport, child session/trace equality and one-shot omission, aggregate nested usage, Pi `tool_result`-only delivery, public agent-model resolution including local overrides, and typed bus payload/error isolation.
3. Add smallest public exports/types/functions and transport fields required by contract.
4. Preserve Pi `tool_result` as sole result transport and existing ordering/failure evidence.
5. Run focused tests, package/full TypeScript, full tests, and pack dry-runs.
6. Commit one coherent result-port candidate.

**Focused verification:**
```bash
corepack pnpm --filter @pi-archimedes/subagent exec vitest run
corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit
corepack pnpm -r exec -- tsc --noEmit
corepack pnpm test
(cd packages/subagent && npm pack --dry-run)
(cd packages/core && npm pack --dry-run)
```

**Expected result:** Public imports and runtime evidence satisfy contract without policy leakage.

### Task 4: Build Pi-setup Vendor Projection [Depends on: Task 3]

**Context:** Carry only reviewed production/runtime additions needed by pi-setup above result ports, including combined precedence tests and footer compatibility.

**Files:**
- Worktree/branch: `.worktrees/upstream/pi-archimedes-vendor-210` / `vendor/pi-setup-210`
- Modify: `forks/pi-archimedes` submodule pointer
- Modify: `.gitmodules` (`vendor/pi-setup-210` tracking branch)
- Replace: `patches/pi-packages/pi-archimedes-*-2.0.1.patch` with 2.1.0 equivalents
- Modify: `scripts/apply-pi-package-patches.sh`
- Modify: `pi/agent/settings.json`
- Modify: `patches/pi-packages/README.md`
- Modify: `tests/test_package_patches.py`
- Modify: `tests/test_pi_packages.py`
- Modify relevant deployment/package tests

**Steps:**
1. Add/update root tests first and confirm RED for 2.1.0 pin, vendor head, `.gitmodules` branch, exact `v2.1.0` ancestry, one-commit candidate lineages, public exports, and patch names.
2. Build vendor branch from result ports plus bounded combined tests/footer compatibility only.
3. Generate production-only zero-fuzz patches against exact npm 2.1.0 tarballs.
4. Update pin/helper/docs/tests; retain pi-setup policy outside fork. Keep current private-path and duplicate-type consumer compatibility until Q21, but add installed-package contract tests that directly import and exercise public `./types`, `./agents`, and `./bus` from patched packages.
5. Prove patch check/apply/idempotence/reverse and installed public imports in isolated real npm tarball roots; record `npm view` integrity and package times. Extract exact `pi-archimedes@2.1.0`, `@pi-archimedes/subagent@2.1.0`, `@pi-archimedes/core@2.1.0`, and footer tarballs with `npm pack` before invoking `scripts/apply-pi-package-patches.sh` against that root.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_package_patches.py tests/test_pi_packages.py tests/test_subagent_workaround.py
npm view pi-archimedes@2.1.0 @pi-archimedes/subagent@2.1.0 @pi-archimedes/core@2.1.0 dist.integrity time --json
```

**Expected result:** Exact 2.1.0 runtime projection works with pi-setup and reverses cleanly.

### Task 5: Verify and Prepare Packets [Depends on: Task 4]

**Context:** Final evidence and reviewer prose only; no upstream submission. Publish the exact vendor branch only if separately approved and required for a fetchable gitlink.

**Files:**
- Create: `.pi/reviews/pi-archimedes-210-upstream-ready/README.md`
- Create: `.pi/reviews/pi-archimedes-210-upstream-ready/*-body.md`

**Steps:**
1. Audit each branch diff/commit/ancestry and final vendor projection.
2. Run complete fork and pi-setup matrices once final candidates stabilize.
3. Route read-only review; fix verified in-scope findings with focused reruns.
4. Write exact internal evidence and separate reviewer-facing bodies with human review pending.
5. Stage explicit root paths, inspect cached/unstaged/untracked boundaries, commit once, then direct-closeout.

**Focused verification:**
```bash
git diff --check
git diff --cached --check
git status --short --untracked-files=all
```

**Expected result:** Clean committed root candidate and local upstream-ready packets; no upstream PR/deployment action occurs.

## Execution Results

- Clean stack: `2ed26aa` → `23d8fbf` → `f277470` → `3576ddf` → `a9efbf1` → vendor `1c4750d`; every edge is one direct-parent commit.
- Final fork gate: recursive TypeScript PASS; 271 focused subagent tests PASS; 754 workspace tests PASS; package previews PASS.
- Exact npm proof: integrity-pinned 2.1.0 tarballs accepted patch preflight/apply/applied-check/idempotent reapply and zero-fuzz reverse dry-runs; public agents/types/bus imports PASS under Pi Jiti.
- Root packet path: `.pi/reviews/pi-archimedes-210-upstream-ready/`; exact approved fork vendor branch `vendor/pi-setup-210@1c4750d` was pushed for gitlink fetchability; no upstream-candidate push, PR, deployment, or release.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| Subagent source/tests/docs | Tasks 2, 3, 4 | Linear branch dependency; each candidate starts from prior immutable head. |
| Root package patch tests/docs | Tasks 4, 5 | Stabilize Task 4 before final evidence and staging. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-15-pi-archimedes-210-hardening-plan.md` (verify with `test -f`).
Recommended next skill: `test-driven-development` for result-port/root behavior; `verification-before-completion` before completion.
