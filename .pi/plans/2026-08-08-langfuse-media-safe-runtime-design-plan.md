# Langfuse Media-Safe Finite Runtime Design and Implementation Plan

**Issue:** pi-4tg9.15.1 — Consume finite media-safe Langfuse string bounds at runtime
**Design:** This document
**Date:** 2026-08-08
**Branch:** fix/langfuse-finite-string-runtime

**Goal:** Deploy finite ordinary-string telemetry bounds without corrupting valid Langfuse-extractable media or persisting raw media in REST fallback.

**Architecture:** Use upstream draft PR 6 as problem and precedence provenance, but use the reviewed media implementation rebased onto Pi Langfuse 1.5.10 as commits `30ef871`, `65c2cbd`, and `c02abb2` because PR 6 is stale, type-broken, and uses an unsupported upload API. Langfuse 1.5.10 natively contains upstream PR 9 logical-session correlation and PR 10 score entity IDs; keep the media candidate independent of the remaining ingestion-batching PR, and combine only batching plus media in the fast-forwardable `vendor/pi-setup` lineage and version-locked npm 1.5.10 runtime projection. Remove the local wrapper's unconditional `PI_LANGFUSE_MAX_STRING_LENGTH=off` assignment so the package's existing finite default applies while explicit operator overrides, including `off`, remain authoritative.

**Acceptance Criteria:**
- [x] Valid unparameterized Base64 image, audio, and video Data URIs survive the OTel payload path long enough for Langfuse media extraction; raw Base64 is not retained in REST fallback.
- [x] Ordinary strings and malformed, parameterized, non-Base64, or unsupported media-like strings become bounded privacy-safe values under finite defaults.
- [x] Capture-disabled input/output surfaces use omission markers and retain no raw media; metadata, model parameters, status/error text, and REST fallback remain bounded or media-redacted.
- [x] Unset `PI_LANGFUSE_MAX_STRING_LENGTH` uses package default `12_000`; an explicit valid integer or `off` still overrides it.
- [x] Native 1.5.10 session correlation and score entity IDs remain unchanged; vendor 3,000,000-byte ordered ingestion batching, oversized-event diagnostics, stable retry envelope IDs, and abortable polling remain intact.
- [x] `forks/pi-langfuse` points to a clean local vendor commit descending from both `f156802` and v1.5.10 `cebf7c6`, and the production-only `pi-langfuse-1.5.10.patch` exactly projects only batching plus media changes onto npm 1.5.10.
- [x] Stale exact-version runtime detection remains whole-patch, fuzz-zero, and rollback-safe; runtime npm manifest entries keep both patch bases exact so installing Langfuse cannot reify Archimedes 1.9.0.
- [x] Eventual upstream PR text credits PR 6 for identifying the media problem, explains why the supported OTel extraction path replaces its manual upload approach, and notes that batching is handled separately; no upstream action occurs without approval.
- [x] Live proof uses generated synthetic bytes in memory, emits only booleans/counts/markers, and persists no raw media or telemetry score writes.

**Verification Commands:**
```bash
# Combined pi-langfuse vendor candidate
npm ci --ignore-scripts
npm run typecheck
npm test
npm pack --dry-run

git diff --check

# pi-setup projection and deployment behavior
/Users/hays/Projects/pi-setup/.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest tests/test_langfuse_skill.py tests/test_package_patches.py tests/test_update_pi_config.py
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false /Users/hays/Projects/pi-setup/.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

## Source Boundaries

- Upstream media candidate: `/Users/hays/Projects/pi-setup/.worktrees/upstream/pi-langfuse-media-1510`, branch `fix/media-safe-payload-bounds`, commits `30ef871`, `65c2cbd`, and `c02abb2`, based on upstream v1.5.10 `cebf7c6`.
- Combined vendor branch: `/Users/hays/Projects/pi-setup/.worktrees/upstream/pi-langfuse-media-vendor`, branch `vendor/pi-setup-media-bounds`, descending from prior vendor `f156802` and upstream v1.5.10. The release makes local session and score-entity deltas baseline-native; the remaining projection is batching plus media only.
- Root integration workspace: `/Users/hays/Projects/pi-setup/.worktrees/fix/langfuse-finite-string-runtime`.
- Upstream draft PR 6 is provenance only. Do not copy its unsupported `uploadMedia` implementation or its broad 8,192-character REST hashing.

## Task 1: Preserve reviewed source candidate [Independent]

**Context:** Treat rebased commits `30ef871`, `65c2cbd`, and `c02abb2` as the separate upstream-quality media patch. Do not fold batching, score identity, session correlation, or local deployment behavior into this source candidate.

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
1. Confirm the branch is clean, based on v1.5.10 `cebf7c6`, and contains only the three reviewed media commits.
2. Run its focused/full tests and typecheck before importing it.
3. Record PR 6 credit and supersession rationale for eventual PR text, not source code attribution unless copied code is later introduced.

**Focused verification:**
```bash
npm run typecheck
npm test
```

**Expected result:** Clean reviewed media patch passes independently and contains no batching implementation.

## Task 2: Combine media with current vendor lineage [Depends on: Task 1]

**Context:** Preserve exact vendor baseline `f156802` as an ancestor so the canonical fork branch remains fast-forwardable. Import the two reviewed media commits, then merge upstream v1.5.10 so logical-session and score-entity behavior become native while current batching and reviewed media-redaction behavior remain.

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
3. Import the reviewed media commits, resolve shared README/REST conflicts, and add only the integration regression needed to keep batching tests meaningful under the new finite default.
4. Merge v1.5.10 `cebf7c6`; retain upstream-native session/score behavior plus event order, stable envelope IDs, the 3,000,000-byte ingestion ceiling, later-event continuation, and abortable polling.
5. Run package typecheck/full tests/pack/diff checks and create signed vendor commits.

**Focused verification:**
```bash
npm run typecheck
npm test
npm pack --dry-run
git diff --check
```

**Expected result:** Combined vendor branch descends from both `f156802` and v1.5.10, contains media plus batching behavior, and passes both coverage groups.

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
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest tests/test_langfuse_skill.py -k 'string_length or media or override'
```

**Expected result:** Package default governs unset runtime state; explicit operator values remain unchanged.

## Task 4: Regenerate version-locked production projection [Depends on: Task 2, Task 3]

**Context:** Pin the root submodule to the combined vendor commit and replace the existing consolidated npm 1.5.10 patch with the minimum production-file diff from clean upstream v1.5.10. Do not project README, tests, plans, or package-manager noise.

**Files:**
- Modify: `forks/pi-langfuse` gitlink
- Rename/modify: `patches/pi-packages/pi-langfuse-1.5.9.patch` → `pi-langfuse-1.5.10.patch`
- Modify: `patches/pi-packages/README.md`
- Modify: `pi/agent/settings.json`
- Modify: `scripts/apply-pi-package-patches.sh`
- Modify: `scripts/update-pi-config.sh`
- Modify: `tests/test_package_patches.py`
- Modify: `tests/test_pi_packages.py`
- Modify: `tests/test_update_pi_config.py`

**Steps:**
1. Add RED contract checks for the new media-safe production markers and updated vendor SHA.
2. Generate a zero-context patch from clean v1.5.10 `cebf7c6` to the combined vendor head, restricted to the six changed production files.
3. Verify the patch applies with `--force --fuzz=0` to clean npm 1.5.10 and reverses exactly after application.
4. Verify an exact-version runtime carrying the old projection is classified stale and repaired rollback-safely; keep current whole-patch classifier unless a failing test proves a gap.
5. Pin both patch-base entries exactly in the runtime npm manifest before and after installs so npm cannot upgrade Archimedes while migrating Langfuse; cover the observed 1.8.3→1.9.0 reification failure test-first.
6. Update projection documentation and tests without exposing payloads.

**Focused verification:**
```bash
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest tests/test_package_patches.py tests/test_update_pi_config.py
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
6. Create clean signed commits. Fork-local draft staging is allowed when separately directed; do not deploy live, create/update actual upstream PRs, or close the Bead.

**Expected result:** Clean local candidates pass all gates with review evidence; remote publication and live rollout remain separately approval-gated.

## Results

- Clean v1.5.10 media candidate `c02abb2` passed TypeScript and 84 package tests and is staged as fork-local draft PR 3; upstream PR 6 and repository were not mutated.
- Combined vendor `7f6e9ec` descends from prior vendor `f156802` and v1.5.10, passed TypeScript, all 88 package tests, pack dry-run, and diff checks.
- The zero-context 1.5.10 projection changes six production files, applies and reverses with fuzz zero, and byte-matches vendor production sources.
- Root focused verification passed Ruff, 56 package/deployment/config tests, shell syntax, Pi config, and diff checks.
- Real isolated 1.5.9-to-1.5.10 migration retained Archimedes 1.8.3, applied all patches, and was idempotent; a failed-upgrade regression preserves the old Langfuse manifest/package pair.
- Synthetic in-memory proof reported finite default, bounded ordinary/malformed values, transient media preservation, REST omission, and explicit `off` without printing or persisting Base64.
- Review `20260808-110452-langfuse-media-runtime` found two Important defects; model-media fallback and failed-install manifest divergence were reproduced and fixed test-first. Fresh one-shot verification marked both confirmed-fixed and found no new Critical/Important defect.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| Vendor `src/langfuse.ts` | Task 1 media behavior, Task 2 batching integration | Task 2 explicitly preserves both semantics and runs both test groups. |
| `patches/pi-packages/pi-langfuse-1.5.10.patch` | Task 4 projection, Task 5 verification | Freeze projection before final verification. |
| `patches/pi-packages/README.md` | Tasks 4 and 5 | Update once after projection behavior stabilizes. |

## Publication Boundary

- Fork-local draft 1 is now redundant because its score-ID change shipped upstream in v1.5.10; leave it untouched until later closeout approval. Fork-local batching draft 2 remains unchanged during local implementation.
- Fork-local draft PR 3, `https://github.com/stvhay/pi-langfuse/pull/3`, stages the clean media candidate against fork main at v1.5.10, credits PR 6, and explains that it supersedes PR 6's media half while batching remains separate.
- Creating an actual upstream draft, marking any PR Ready, requesting review, pushing upstream, merging, releasing, or publishing requires explicit later approval.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-08-langfuse-media-safe-runtime-design-plan.md` (verify with `test -f`).
Recommended next skill: `test-driven-development`; use `verification-before-completion` before claiming completion.
