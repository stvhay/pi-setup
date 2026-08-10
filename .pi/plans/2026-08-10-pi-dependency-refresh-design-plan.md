# Pi Dependency Refresh Design and Implementation Plan

**Issue:** pi-4gf8 — Refresh Langfuse, skills, Graphify, and BetterWright
**Design:** approved in session 019fe9a7-7dbe-7226-b562-0690b5182735
**Date:** 2026-08-10
**Branch:** `feature/dependency-refresh`

**Goal:** Refresh selected Pi packages and skills while preserving the reviewed Langfuse runtime guarantees and keeping generated Graphify data private.

**Architecture:** Git skill packages become unpinned default-branch sources; patched npm packages remain exact versioned bases. `pi-langfuse` 1.5.12 is audited first, then only missing batching/media behavior is rebuilt in separate fork candidates and combined in a vendor runtime projection. Graphify 0.9.25 skill guidance is reconciled with the local `agnt` and hook-safety contract before one separately approval-backed full Gemini rebuild. BetterWright remains unpinned and is updated during rollout.

**Acceptance Criteria:**
- [ ] Langfuse and Matt Pocock skill sources have no ref suffix, retain intended filters, and tests/docs describe default-branch tracking.
- [ ] Exact `pi-langfuse` 1.5.12 plus its version-locked projection preserves stable IDs, ordered sub-3,000,000-byte ingestion, media-safe payloads, capability-gated legacy fallback, bounded shutdown, and rollback-safe repair.
- [ ] Graphify tracked/live skill reports 0.9.25, retains `agnt`/hook safeguards, and ignored graph artifacts use current path-qualified node IDs after an approved full Gemini rebuild.
- [ ] BetterWright 1.7.1 is documented and verified during rollout; source remains unpinned.
- [ ] Focused and full project checks pass from a stable candidate.

**Verification Commands:**
```bash
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
scripts/apply-pi-package-patches.sh --check
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

## Chosen boundaries

- Unpin only the two git skill packages. Keep `pi-langfuse` exact-pinned because patch validation and rollback depend on a known npm tree.
- Do not auto-update every unpinned package on every config deployment. Update selected live packages once during approved rollout; later `pi update --extensions` follows unpinned git/npm sources.
- Preserve 1.5.12 native capability gating, shutdown isolation, final system-prompt capture, session correlation, and score IDs. Do not replay superseded 1.5.10 code.
- Keep Langfuse media and ingestion changes as separate fork candidates; combine only in the vendor/runtime lineage.
- Keep `graphify-out/` ignored. Never commit generated graph, semantic cache, reports, images, or model artifacts.
- No hooks are installed. No upstream PR, Ready, merge, release, or pi-setup push is included.

## Task 1: Audit pi-langfuse 1.5.12 and establish RED coverage

**Files:**
- Inspect: `forks/pi-langfuse/{index.ts,src/langfuse.ts,src/handlers/agent.ts,tests/**,README.md}`
- Test: upstream pi-langfuse tests plus focused batching/media regressions

**Steps:**
1. Fetch exact upstream tag `v1.5.12` and verify its peeled commit.
2. Compare v1.5.10, v1.5.12, prior batching candidate, media candidate, and combined vendor tree by production behavior.
3. Classify every prior production delta as native, still needed, or obsolete.
4. Port tests before production changes for still-needed behavior, including environment isolation.

**Focused verification:**
```bash
npm ci
npm run typecheck
npm test
npm pack --dry-run
```

## Task 2: Rebuild separate 1.5.12 fork candidates

**Depends on:** Task 1

**Files:**
- Modify: pi-langfuse candidate branches under isolated upstream worktrees
- Test: `tests/langfuse.test.ts` and any existing focused suites

**Steps:**
1. Rebuild media-safe payload handling directly on v1.5.12 without batching changes.
2. Rebuild bounded shared ingestion directly on v1.5.12 without media changes, preserving score-envelope IDs only if 1.5.12 still lacks them.
3. Preserve capability-gated legacy fallback and per-step shutdown handling from v1.5.12.
4. Verify each candidate independently and commit signed logical changes.
5. Do not update existing fork draft branches until force-with-lease approval is obtained.

## Task 3: Assemble vendor and migrate pi-setup projection

**Depends on:** Task 2

**Files:**
- Modify: `forks/pi-langfuse` gitlink
- Replace: `patches/pi-packages/pi-langfuse-1.5.10.patch` with `pi-langfuse-1.5.12.patch`
- Modify: `patches/pi-packages/README.md`
- Modify: `scripts/apply-pi-package-patches.sh`
- Modify: `scripts/update-pi-config.sh`
- Modify: `pi/agent/settings.json`
- Modify: `pi/README.md`, `docs/extension-web-compatibility.md`
- Test: `tests/test_package_patches.py`, `tests/test_update_pi_config.py`, `tests/test_pi_packages.py`, `tests/test_langfuse_skill.py`

**Steps:**
1. Combine reviewed candidates on a local vendor branch based on exact v1.5.12.
2. Generate a production-only zero-context patch from clean npm 1.5.12.
3. RED: update tests to require exact 1.5.12, new patch name/head, native 1.5.12 behavior, and stale 1.5.10 repair.
4. Update exact install/reinstall/rollback logic and docs.
5. Prove clean/applied/partial/nonzero-offset classifications with fuzz=0.

## Task 4: Unpin and refresh skill packages

**Files:**
- Modify: `pi/agent/settings.json`
- Modify: `tests/test_langfuse_skill.py`, `tests/test_pi_packages.py`
- Modify: `docs/extension-web-compatibility.md`

**Steps:**
1. RED: require `git:github.com/langfuse/skills` and filtered `git:github.com/mattpocock/skills` without `@ref`.
2. Preserve Matt Pocock skill filters and disabled extensions/prompts/themes.
3. Update docs to state default-branch tracking and record the reviewed current heads as evidence, not pins.
4. During approved rollout, run targeted package updates and verify live checkouts equal remote default heads.

## Task 5: Refresh Graphify 0.9.25 skill and graph

**Files:**
- Modify: `pi/agent/skills/graphify/**`
- Generated ignored: `graphify-out/**`
- Test: context architecture and Graphify helper tests

**Steps:**
1. Compare bundled 0.9.25 Pi skill/reference files with the tracked concise wrapper.
2. Import current extraction/query/honesty behavior while retaining `agnt graphify` as the command seam and explicit approval for hook changes.
3. Set tracked `.graphify_version` and README provenance to 0.9.25; deploy bytes later through normal config rollout.
4. Before the semantic rebuild, create a durable informed approval recording Gemini scope, corpus size, cost uncertainty, no tracked outputs, and cancellation boundary.
5. Run one full `graphify extract . --force` with configured Gemini after tracked candidate stabilizes. Verify path-qualified IDs and graph diagnostics. Do not commit outputs.

## Task 6: Refresh BetterWright

**Files:**
- Modify: `docs/extension-web-compatibility.md`
- Possibly test: package inventory assertions if current-version evidence is added

**Steps:**
1. Keep `npm:betterwright` unpinned.
2. Update stale documented version/behavior to 1.7.1.
3. During approved rollout, run targeted package update and verify installed 1.7.1 plus browser tool availability without remote site actions.

## Task 7: Final review, rollout gates, and closeout

**Depends on:** Tasks 3–6

1. Run focused and full verification from the stable feature branch.
2. Review only task-owned deltas; repair confirmed findings test-first.
3. Commit signed logical changes.
4. Request informed approval for any fork force-with-lease refresh, local-main integration, package deployment, live git-package updates, and cleanup.
5. After rollout and restart, run no model call except the separately approved Graphify extraction. Verify package versions, source bytes, skill heads, privacy/runtime checks, and ignored graph health.
6. Record outcome, close/export Bead, sign closeout, and remove only merged task worktrees/branches when approved.

## File conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/settings.json` | 3, 4 | Task 4 follows Task 3 in one root candidate. |
| `docs/extension-web-compatibility.md` | 3, 4, 6 | Update once after all exact versions/heads are known. |
| `tests/test_pi_packages.py` | 3, 4 | Keep one shared fixture update. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-10-pi-dependency-refresh-design-plan.md`

Recommended next skill: `test-driven-development` for behavior changes; `verification-before-completion` before completion claims.
