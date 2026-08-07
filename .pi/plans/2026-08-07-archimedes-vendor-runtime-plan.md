# Archimedes Vendor Runtime Implementation Plan

**Issue:** pi-4tg9.18 / pi-4tg9.18.1
**Design:** None
**Date:** 2026-08-07
**Branch:** feat/run-archimedes-vendor-stack

**Goal:** Run the reviewed bounded/one-shot Archimedes stack locally from a pullable fork ref without merging either draft PR.

**Architecture:** Fast-forward the existing fork-only `vendor/pi-setup` integration branch so it contains child-session correlation plus both reviewed candidate stacks. Keep `npm:pi-archimedes@1.8.3` as the installable base because Pi's git installer invokes npm and the upstream pnpm monorepo uses unsupported `workspace:*` dependencies. Pin the reviewed vendor source as the existing submodule, and make installed meta/subagent production files match that source through the repository's existing version-locked, preflighted patch mechanism.

**Acceptance Criteria:**
- [ ] `stvhay/pi-archimedes:vendor/pi-setup` is a normal fast-forward from `c27561d` to the verified combined stack and both draft PR refs remain unchanged.
- [ ] `forks/pi-archimedes` pins the exact combined vendor head.
- [ ] Runtime patches cover only production/package files needed by installed `pi-archimedes` and `@pi-archimedes/subagent` 1.8.3.
- [ ] Patch checking is version-locked, rejects partial state, preflights all packages before mutation, and remains idempotent.
- [ ] Deployed `~/.pi` loads the patched schema and a fresh one-shot child completes with one provider request semantics.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_package_patches.py tests/test_pi_packages.py tests/test_agent_os_compat.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
scripts/apply-pi-package-patches.sh --check
PI_CONFIG_DIR="$HOME/.pi" scripts/check-pi-config.sh
git diff --check
```

---

### Task 1: Pin combined vendor source

**Files:**
- Modify: `forks/pi-archimedes` gitlink
- Modify: `patches/pi-packages/README.md`

**Steps:**
1. Verify remote `vendor/pi-setup` equals reviewed combined head and draft refs are unchanged.
2. Advance the submodule gitlink to that exact head.
3. Document why direct Pi git installation is unavailable and how the version-locked runtime projection works.

### Task 2: Extend runtime projection test-first

**Files:**
- Modify: `tests/test_package_patches.py`
- Modify: `scripts/apply-pi-package-patches.sh`
- Modify: `patches/pi-packages/pi-archimedes-subagent-1.8.3.patch`
- Create: `patches/pi-packages/pi-archimedes-meta-1.8.3.patch`

**Steps:**
1. Add RED fixtures for the installed meta package, combined subagent markers, all-package preflight, idempotence, and partial-state rejection.
2. Generate production-only patches from upstream `801397c` to vendor head.
3. Add meta patch preflight/application using the existing helper; keep all package checks before any mutation.
4. Run focused tests and patch dry-runs against clean package fixtures.

### Task 3: Deploy and prove live behavior

**Files:**
- Modify: `docs/extension-web-compatibility.md`
- Modify: `.beads/issues.jsonl` through Beads export

**Steps:**
1. Run project checks from the final branch.
2. Reinstall the exact npm base to remove the old narrower patch, then run the tracked patch helper.
3. Verify installed production files match vendor source for every patched path.
4. Deploy tracked Pi config and run a fresh headless one-shot subagent proof.
5. Record exact source/runtime heads and verification without merging either draft PR.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-07-archimedes-vendor-runtime-plan.md`
Recommended next skill: `test-driven-development`; use `verification-before-completion` before completion claims.
