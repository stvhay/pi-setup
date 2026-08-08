# Langfuse Media-Safe Finite Runtime Design and Implementation Plan

**Issue:** pi-4tg9.15.1 — Consume finite media-safe Langfuse string bounds at runtime
**Design:** This document
**Date:** 2026-08-08
**Branch:** fix/langfuse-finite-string-runtime

**Goal:** Deploy finite ordinary-string telemetry bounds without corrupting valid Langfuse-extractable media or persisting raw media in REST fallback.

**Architecture:** Use upstream draft PR 6 as problem and precedence provenance, but use the already reviewed Pi Langfuse 1.5.9 commits `a3553ce` and `14325f4` as the code baseline because PR 6 is stale, type-broken, and uses an unsupported upload API. Keep media behavior independent of the existing score-ID and ingestion-batching PRs; combine them only in the `vendor/pi-setup` lineage and the version-locked npm 1.5.9 runtime projection. Remove the local wrapper's unconditional `PI_LANGFUSE_MAX_STRING_LENGTH=off` assignment so the package's existing finite default applies while explicit operator overrides, including `off`, remain authoritative.

**Acceptance Criteria:**
- [ ] Valid unparameterized Base64 image, audio, and video Data URIs survive the OTel payload path long enough for Langfuse media extraction; raw Base64 is not retained in REST fallback.
- [ ] Ordinary strings and malformed, parameterized, non-Base64, or unsupported media-like strings become bounded privacy-safe values under finite defaults.
- [ ] Capture-disabled input/output surfaces use omission markers and retain no raw media; metadata, model parameters, status/error text, and REST fallback remain bounded or media-redacted.
- [ ] Unset `PI_LANGFUSE_MAX_STRING_LENGTH` uses package default `12_000`; an explicit valid integer or `off` still overrides it.
- [ ] Current vendor session correlation, stable score IDs, 3,000,000-byte ordered ingestion batching, oversized-event diagnostics, retry IDs, and abortable polling remain unchanged.
- [ ] `forks/pi-langfuse` points to a clean local vendor commit descending from `f156802`, and the production-only `pi-langfuse-1.5.9.patch` exactly projects that vendor source onto npm 1.5.9.
- [ ] Stale exact-version runtime detection remains whole-patch, fuzz-zero, and rollback-safe.
- [ ] Eventual upstream PR text credits PR 6 for identifying the media problem, explains why the supported OTel extraction path replaces its manual upload approach, and notes that batching is handled separately; no upstream action occurs without approval.
- [ ] Live proof uses generated synthetic bytes in memory, emits only booleans/counts/markers, and persists no raw media or telemetry score writes.

**Verification Commands:**
```bash
# Combined pi-langfuse vendor candidate
npm ci --ignore-scripts
npm run typecheck
npm test
npm pack --dry-run

git diff --check

# pi-setup projection and deployment behavior
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/test_langfuse_skill.py tests/test_package_patches.py tests/test_update_pi_config.py
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false .venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

## Source Boundaries

- Upstream media candidate: `/Users/hays/Projects/pi-setup/.worktrees/upstream/pi-langfuse-pi-4tg9-7-clean`, branch `fix/pi-4tg9-7-media-bounds-clean`, commits `a3553ce` and `14325f4`, based on upstream v1.5.9 `3243208`.
- Current combined vendor baseline: `forks/pi-langfuse` commit `f156802`, containing session correlation plus fork-local draft PR 1 score IDs and PR 2 ingestion batching.
- Root integration workspace: `/Users/hays/Projects/pi-setup/.worktrees/fix/langfuse-finite-string-runtime`.
- Upstream draft PR 6 is provenance only. Do not copy its unsupported `uploadMedia` implementation or its broad 8,192-character REST hashing.

## Task 1: Preserve reviewed source candidate [Independent]

**Context:** Treat `a3553ce` and `14325f4` as the separate upstream-quality media patch. Do not fold batching, score identity, session correlation, or local deployment behavior into this source candidate.

**Files:**
- Verify: `src/capture-policy.ts`
- Verify: `src/handlers/generation.ts`
- Verify: `src/langfuse.ts`
- Verify: `src/limits.ts`
- Verify: `src/redaction.ts`
- Verify: `src/utils.ts`
- Verify: `test/generation.test.ts`
- Verify: `test/langfuse.test.ts`
- Verify: `test/redaction.test.ts`
- Verify: `test/utils.test.ts`

**Steps:**
1. Confirm the branch is clean, based on `3243208`, and contains only the two reviewed commits.
2. Run its focused/full tests and typecheck before importing it.
3. Record PR 6 credit and supersession rationale for eventual PR text, not source code attribution unless copied code is later introduced.

**Focused verification:**
```bash
npm run typecheck
npm test
```

**Expected result:** Clean reviewed media patch passes independently and contains no batching implementation.

## Task 2: Combine media with current vendor lineage [Depends on: Task 1]

**Context:** Create a separate worktree and branch from exact vendor baseline `f156802`. Cherry-pick the two reviewed media commits in order. Resolve only shared README, `src/langfuse.ts`, and test conflicts by retaining both current batching/session/score behavior and reviewed media-redaction behavior.

**Files:**
- Modify: vendor `README.md`
- Modify: vendor `README_CN.md`
- Modify: vendor `src/capture-policy.ts`
- Modify: vendor `src/handlers/generation.ts`
- Modify: vendor `src/langfuse.ts`
- Modify: vendor `src/limits.ts`
- Modify: vendor `src/redaction.ts`
- Modify: vendor `src/utils.ts`
- Modify: vendor tests listed in Task 1 plus existing batching tests

**Steps:**
1. Verify chosen project-local worktree directory is ignored.
2. Create branch `vendor/pi-setup-media-bounds` from exact `f156802` in a separate pi-langfuse worktree.
3. Cherry-pick `a3553ce`, resolve conflicts, run focused tests, then cherry-pick `14325f4` and repeat.
4. Preserve event order/IDs, shared 3,000,000-byte ingestion ceiling, later-event continuation, and abortable polling.
5. Add only integration regressions that fail because of the combined lineage; avoid duplicating reviewed media tests.
6. Run package typecheck/full tests/pack/diff checks and create signed vendor commits.

**Focused verification:**
```bash
npm run typecheck
npm test
npm pack --dry-run
git diff --check
```

**Expected result:** Combined vendor branch descends from `f156802`, contains the media commits, and passes both media and batching coverage.

## Task 3: Make finite package default effective [Depends on: Task 2]

**Context:** The tracked wrapper currently forces `PI_LANGFUSE_MAX_STRING_LENGTH=off`, bypassing the package's existing default `12_000`. Deletion is sufficient; do not add a duplicate local numeric setting.

**Files:**
- Modify: `pi/agent/extensions/langfuse-config-env.ts`
- Modify: `tests/test_langfuse_skill.py`

**Steps:**
1. Replace the old test asserting implicit `off` with RED tests proving the wrapper leaves an unset value unset and preserves explicit `off`/numeric overrides.
2. Delete the unconditional wrapper assignment and stale corruption comment.
3. Run focused wrapper tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_langfuse_skill.py -k 'string_length or media or override'
```

**Expected result:** Package default governs unset runtime state; explicit operator values remain unchanged.

## Task 4: Regenerate version-locked production projection [Depends on: Task 2, Task 3]

**Context:** Pin the root submodule to the combined vendor commit and replace the existing consolidated npm 1.5.9 patch with the minimum production-file diff from clean upstream v1.5.9. Do not project README, tests, plans, or package-manager noise.

**Files:**
- Modify: `forks/pi-langfuse` gitlink
- Modify: `patches/pi-packages/pi-langfuse-1.5.9.patch`
- Modify: `patches/pi-packages/README.md`
- Modify: `tests/test_package_patches.py`
- Modify if required by behavior evidence: `tests/test_update_pi_config.py`

**Steps:**
1. Add RED contract checks for the new media-safe production markers and updated vendor SHA.
2. Generate a zero-context patch from clean `3243208` to the combined vendor head, restricted to production files.
3. Verify the patch applies with `--force --fuzz=0` to clean npm 1.5.9 and reverses exactly after application.
4. Verify an exact-version runtime carrying the old projection is classified stale and repaired rollback-safely; keep current whole-patch classifier unless a failing test proves a gap.
5. Update projection documentation and tests without exposing payloads.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_package_patches.py tests/test_update_pi_config.py
scripts/check-pi-config.sh
git diff --check
```

**Expected result:** Tracked patch exactly matches combined vendor production files and stale-runtime repair remains safe.

## Task 5: Document and verify candidate [Depends on: Task 4]

**Context:** Document finite-default, media-preservation, REST omission, explicit-off, and separate upstream PR boundaries. Then run full package/project gates and a subscription-backed independent review without metered OpenRouter calls.

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `patches/pi-packages/README.md`
- Update checklist/results: this plan

**Steps:**
1. Keep user-facing docs aligned with runtime behavior and privacy boundaries.
2. Run full source and root verification matrices once after tracked files stabilize.
3. Run an isolated stale-to-current deployment rehearsal against a temporary `.pi` destination.
4. Run a private synthetic in-memory media proof; print no Base64 or identifiers.
5. Request independent Terra review of only the media/vendor/runtime delta; fix verified Critical/Important findings test-first.
6. Create clean signed commits. Do not push, deploy live, create/update upstream PRs, or close the Bead.

**Expected result:** Clean local candidates pass all gates with review evidence; remote publication and live rollout remain separately approval-gated.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| Vendor `src/langfuse.ts` | Task 1 media behavior, Task 2 batching integration | Task 2 explicitly preserves both semantics and runs both test groups. |
| `patches/pi-packages/pi-langfuse-1.5.9.patch` | Task 4 projection, Task 5 verification | Freeze projection before final verification. |
| `patches/pi-packages/README.md` | Tasks 4 and 5 | Update once after projection behavior stabilizes. |

## Publication Boundary

- Fork-local drafts 1 and 2 remain unchanged.
- A future separate media branch/PR should target current upstream main, credit PR 6, and explain that it supersedes PR 6's media half while batching remains separate.
- Creating an actual upstream draft, marking Ready, requesting review, pushing upstream, merging, releasing, or publishing requires explicit later approval.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-08-langfuse-media-safe-runtime-design-plan.md` (verify with `test -f`).
Recommended next skill: `test-driven-development`; use `verification-before-completion` before claiming completion.
