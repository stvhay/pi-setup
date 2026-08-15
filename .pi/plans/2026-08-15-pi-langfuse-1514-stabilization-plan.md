# pi-langfuse 1.5.14 Stabilization Implementation Plan

**Issue:** pi-rxo3.22 — Stabilize and rebase pi-langfuse fork
**Design:** `.pi/plans/2026-08-15-pi-langfuse-quality-port-contract.md`
**Date:** 2026-08-15
**Branch:** `main` (pi-setup); local fork replacement branches listed below

**Goal:** Rebuild maintained pi-langfuse candidates on public v1.5.14, prove them through pi-setup's version-locked projection, and prepare clean upstream packets without remote mutation.

**Architecture:** Keep upstream-facing concerns isolated: ingestion batching, media-safe bounds, privacy-aware tool-byte metadata, and public quality ports each get one local branch and coherent commit based on immutable `04d55a12556bdf4c4b8b208038198dc2fd8e571b`. A separate vendor branch combines reviewed behavior for pi-setup's exact 1.5.14 package projection. pi-setup keeps existing private imports until a public release satisfies the recorded quality-port release gate.

**Local fork branches:**
- `rebuild/ingestion-byte-batches-1514`
- `rebuild/media-safe-payload-bounds-1514`
- `rebuild/tool-payload-byte-metadata-1514`
- `feat/quality-ports-1514`
- `vendor/pi-setup-1514`

Old local and remote branches remain untouched as recovery evidence. No push, PR action, deployment, branch deletion, merge, rebase of an existing ref, or other history rewrite is in scope.

**Acceptance Criteria:**
- [ ] Existing fork drafts #2-#4 are rebuilt as separate one-commit candidates on exact v1.5.14; merged source-metadata draft #5 is excluded.
- [ ] `pi-langfuse/quality` exports the contract types and factories, with bounded capture/read behavior, explicit gaps, and no authority or closeout behavior.
- [ ] Vendor branch contains all four reviewed candidates and preserves v1.5.14 source-metadata, fallback, shutdown, session, and score behavior.
- [ ] pi-setup pins exact 1.5.14 and projects the vendor delta without replacing private imports or claiming public release evidence.
- [ ] Focused and full fork checks, package projection/deployment-adapter tests, and full pi-setup checks pass.
- [ ] Internal evidence packet plus separate reviewer-facing bodies exist; no remote submission occurs.

**Verification Command(s):**
```bash
# fork candidate/vendor checks; managed capture env is removed for hermetic upstream tests
env -u LANGFUSE_PRIVACY_PRESET -u LANGFUSE_CAPTURE_INPUTS -u LANGFUSE_CAPTURE_OUTPUTS \
  -u LANGFUSE_CAPTURE_TOOL_IO -u LANGFUSE_CAPTURE_SYSTEM_PROMPT -u LANGFUSE_CAPTURE_CWD \
  -u LANGFUSE_CAPTURE_SOURCE_METADATA npm run typecheck
env -u LANGFUSE_PRIVACY_PRESET -u LANGFUSE_CAPTURE_INPUTS -u LANGFUSE_CAPTURE_OUTPUTS \
  -u LANGFUSE_CAPTURE_TOOL_IO -u LANGFUSE_CAPTURE_SYSTEM_PROMPT -u LANGFUSE_CAPTURE_CWD \
  -u LANGFUSE_CAPTURE_SOURCE_METADATA npm test
npm pack --dry-run

# pi-setup
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Record current upstream and baseline [Independent]

**Context:** Refresh `.pi/upstream-profiles/github.com--gooyoung--pi-langfuse.md` against public v1.5.14 and record current setup/fork baseline. Public tag and `main` both resolve to `04d55a12556bdf4c4b8b208038198dc2fd8e571b`.

**Files:**
- Modify: `.pi/upstream-profiles/github.com--gooyoung--pi-langfuse.md`

**Steps:**
1. Verify public Git tag/main, npm version/integrity/time, fork permissions, templates, rules, branch protection, issues, and open fork drafts.
2. Re-read and hash profile source files from exact public commit.
3. Run current vendor package checks and pi-setup integration/package/deployment-adapter tests.
4. Record environmental test contamination separately from candidate failures.

**Focused verification:**
```bash
rg -n 'target_ref: v1.5.14|source_commit: 04d55a12556bdf4c4b8b208038198dc2fd8e571b' .pi/upstream-profiles/github.com--gooyoung--pi-langfuse.md
```

**Expected result:** Current source-stamped profile and reproducible baseline evidence.

### Task 2: Rebuild existing fork candidates [Depends on: Task 1]

**Context:** Rebuild commits `9c4103d`, `bcaa42a`, and `f534c5d` onto v1.5.14 without moving or rewriting old refs. Resolve only v1.5.14 source-metadata/release overlap.

**Files:**
- Modify on ingestion branch: `README.md`, `README_CN.md`, `src/langfuse.ts`, `test/langfuse.test.ts`
- Modify on media branch: existing media candidate files
- Modify on tool-byte branch: existing tool-byte candidate files

**Steps:**
1. Create each named replacement branch directly from `upstream-v1.5.14`.
2. Cherry-pick its one old candidate commit; resolve conflicts by preserving both current public behavior and candidate-specific behavior.
3. Inspect full base diff and commit metadata.
4. Run typecheck, focused tests, full tests with managed capture env removed, and package dry-run on each candidate.

**Focused verification:**
```bash
git merge-base --is-ancestor upstream-v1.5.14 <candidate-branch>
git rev-list --count upstream-v1.5.14..<candidate-branch>
```

**Expected result:** Each replacement branch is exactly one coherent commit above v1.5.14 and passes required checks.

### Task 3: Implement public quality ports with TDD [Depends on: Task 1]

**Context:** Implement the exact contract in `.pi/plans/2026-08-15-pi-langfuse-quality-port-contract.md` as one independent upstream candidate. Reuse current config, capture policy, redaction, runtime, native `fetch`, `AbortSignal`, and existing API endpoint semantics; add no dependency.

**Files:**
- Create: `forks/pi-langfuse/src/quality.ts`
- Create: `forks/pi-langfuse/test/quality.test.ts`
- Modify: `forks/pi-langfuse/package.json`
- Modify only if user-facing contract needs it: `forks/pi-langfuse/README.md`, `forks/pi-langfuse/README_CN.md`

**Steps:**
1. Create `feat/quality-ports-1514` from `upstream-v1.5.14`.
2. Write focused tests first for public export shape, capture redaction/lifecycle/buffered/flush/unavailable behavior, bounded traces/observations/scores/annotations, abort/service gaps, validation, and governance exclusions.
3. Run tests and confirm RED because export/factories are absent.
4. Implement minimum `src/quality.ts` using existing package seams and stable gap codes.
5. Run focused tests GREEN, then typecheck/full tests/package dry-run.
6. Inspect package contents and public type names.

**Focused verification:**
```bash
npm exec -- tsx --test test/quality.test.ts
npm run typecheck
npm pack --dry-run
```

**Expected result:** Contract tests pass; package includes `src/quality.ts`; no authority, Bead, acceptance, closeout, or pi-setup policy behavior exists.

### Task 4: Build pi-setup vendor branch [Depends on: Tasks 2, 3]

**Context:** Combine all four reviewed candidate trees on `vendor/pi-setup-1514` without changing candidate refs. Preserve exact public base behavior where candidates overlap.

**Files:**
- Modify: combined candidate production, docs, and tests inside `forks/pi-langfuse`

**Steps:**
1. Create vendor branch from `upstream-v1.5.14`.
2. Apply candidate deltas in order: media, ingestion, tool-byte metadata, quality ports.
3. Resolve overlap once at shared runtime/capture/tests while preserving each candidate's assertions.
4. Commit one vendor integration commit.
5. Run focused and full fork verification and inspect diff against every candidate requirement.

**Focused verification:**
```bash
git diff --check upstream-v1.5.14..vendor/pi-setup-1514
env -u LANGFUSE_PRIVACY_PRESET -u LANGFUSE_CAPTURE_TOOL_IO -u LANGFUSE_CAPTURE_SYSTEM_PROMPT -u LANGFUSE_CAPTURE_CWD npm test
```

**Expected result:** One clean vendor commit above v1.5.14 contains all required behavior.

### Task 5: Upgrade pi-setup projection to 1.5.14 [Depends on: Task 4]

**Context:** Project exact vendor production/package changes onto installed `pi-langfuse@1.5.14`. Keep quality ports explicitly unreleased and keep existing private imports until release gate completion.

**Files:**
- Modify: `forks/pi-langfuse` submodule pointer
- Rename/replace: `patches/pi-packages/pi-langfuse-1.5.12.patch` -> `patches/pi-packages/pi-langfuse-1.5.14.patch`
- Modify: `scripts/apply-pi-package-patches.sh`
- Modify: `scripts/update-pi-config.sh`
- Modify: `pi/agent/settings.json`
- Modify: `patches/pi-packages/README.md`
- Modify: `pi/README.md`
- Modify: `docs/extension-web-compatibility.md`
- Modify tests: `tests/test_package_patches.py`, `tests/test_update_pi_config.py`, `tests/test_pi_packages.py`, and relevant quality-port contract tests

**Steps:**
1. Update root tests first to require exact 1.5.14, new patch path, vendor head, quality export, and unchanged private-import release gate.
2. Run focused root tests and confirm RED against 1.5.12 configuration.
3. Generate minimal installed-file patch from exact v1.5.14 to vendor branch; exclude tests/development-only files.
4. Update exact pins, marker checks, docs, and submodule pointer.
5. Run focused package/update/config tests GREEN and patch apply/reverse checks against clean exact package source.
6. Confirm no caller imports `pi-langfuse/quality` as released and no private import was deleted.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_package_patches.py tests/test_update_pi_config.py tests/test_pi_packages.py tests/test_agent_os_compat.py
scripts/apply-pi-package-patches.sh --check
```

**Expected result:** pi-setup deterministically installs 1.5.14, applies exact vendor projection, and preserves release governance.

### Task 6: Prepare upstream-ready packets [Depends on: Tasks 2, 3]

**Context:** Create internal evidence and separate reviewer-facing bodies. Existing remote PRs remain untouched; source-metadata draft #5 is recorded as superseded by upstream #18/v1.5.14.

**Files:**
- Create: `.pi/reviews/pi-langfuse-1514-upstream-ready/evidence.md`
- Create: `.pi/reviews/pi-langfuse-1514-upstream-ready/ingestion-body.md`
- Create: `.pi/reviews/pi-langfuse-1514-upstream-ready/media-body.md`
- Create: `.pi/reviews/pi-langfuse-1514-upstream-ready/tool-byte-body.md`
- Create: `.pi/reviews/pi-langfuse-1514-upstream-ready/quality-ports-body.md`

**Steps:**
1. Record exact profile timestamp, base/head refs, commit lists, changed files, diffstats, checks, review status, exclusions, and unresolved concerns internally.
2. Draft reviewer-facing Summary/Motivation/Compatibility/Testing/Development disclosure bodies without private workflow details.
3. State human review is pending; do not claim completed human review.
4. Verify no secrets, private telemetry, local paths, Beads, or submission commands appear in reviewer bodies.

**Focused verification:**
```bash
test -f .pi/reviews/pi-langfuse-1514-upstream-ready/evidence.md
for body in .pi/reviews/pi-langfuse-1514-upstream-ready/*-body.md; do rg -n '^## (Summary|Motivation|Compatibility|Testing|Development disclosure)$' "$body"; done
```

**Expected result:** Upstream-ready local packet exists with no remote action.

### Task 7: Final verification and closeout [Depends on: Tasks 4, 5, 6]

**Context:** Stabilize root and fork candidate boundaries, run full matrices once, review, commit task-owned changes, and close direct work.

**Files:**
- All task-owned files above

**Steps:**
1. Inspect root and submodule statuses, diffs, candidate commit ranges, untracked files, and deletion recovery.
2. Run fork final matrix on each upstream-facing candidate and vendor branch.
3. Run full documented pi-setup verification matrix.
4. Request read-only peer review for contract, regression, and packet risks; verify findings against source/tests.
5. Stage explicit task-owned paths, rerun diff checks/final matrix if candidate changes, and create one root atomic commit.
6. Run `agnt work direct-closeout pi-rxo3.22 --outcome success --reason "..."`; do not push, submit, deploy, merge, or clean branches/worktrees.

**Focused verification:**
```bash
git diff --check
git diff --cached --check
git status --short --untracked-files=all
```

**Expected result:** Fork and pi-setup gates pass from stable candidates; committed local work and Bead closeout evidence exist.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| fork `src/langfuse.ts`, shared tests/docs | 2, 4 | Task 4 integrates already-verified candidate deltas after Tasks 2 and 3. |
| fork `src/capture-policy.ts`, `src/types.ts`, `src/utils.ts` | 2, 3, 4 | Quality branch stays independent; vendor resolves overlap without changing candidate refs. |
| package manifest/export and root patch | 3, 5 | Task 5 projects Task 3 only after vendor integration passes. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-15-pi-langfuse-1514-stabilization-plan.md` (verify with `test -f`).
Recommended next skill: `test-driven-development` for quality-port and projection behavior; `verification-before-completion` before completion claims.
