# Pi 0.84.1 Security Upgrade Implementation Plan

**Issue:** pi-pz5o — Upgrade Pi after patched transitive security release
**Design:** None
**Date:** 2026-08-07
**Branch:** fix/pi-0841-security-upgrade

**Goal:** Pin tested and deployed Pi to 0.84.1, remove the known Undici and brace-expansion advisories, and preserve Archimedes child progress under Pi 0.84's delta-only JSON stream.

**Architecture:** Keep Pi's owner-published shrinkwrap as the security boundary; do not add root overrides. Update the tracked test/runtime pin and compatibility documentation together. Adapt only the private Archimedes subprocess parser: assemble 0.84 text/thinking deltas for live output, retain 0.74–0.83 cumulative-message compatibility, and keep usage authoritative at `message_end`.

**Acceptance Criteria:**
- [x] `@earendil-works/pi-coding-agent` is pinned exactly to 0.84.1 and its shrinkwrap contains Undici 8.9.0 and brace-expansion 5.0.9.
- [x] `npm audit --omit=optional` reports zero vulnerabilities.
- [x] Archimedes preserves ordered live text/thinking from Pi 0.84 delta events and does not double-count usage.
- [x] Existing bounded execution, one-shot, repeated-error, token-progress, child-session, and output-projection behavior remains passing.
- [x] Project documentation and pin assertions name Pi 0.84.1.

**Verification Command(s):**
```bash
npm ci --ignore-scripts
npm audit --omit=optional
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Adapt Archimedes JSON deltas [Independent]

**Context:** Pi 0.84 removes cumulative `message` and `assistantMessageEvent.partial` from JSON/RPC `message_update`. Child stdout still ends each turn with authoritative `message_end`.

**Files:**
- Modify: `forks/pi-archimedes/packages/core/src/index.ts`
- Modify: `forks/pi-archimedes/packages/core/src/startup/index.ts`
- Modify: `forks/pi-archimedes/packages/subagent/src/handlers.ts`
- Modify: `forks/pi-archimedes/packages/subagent/src/index.ts`
- Modify: `forks/pi-archimedes/packages/subagent/src/stream.ts`
- Modify: `forks/pi-archimedes/packages/subagent/src/types.ts`
- Modify: `forks/pi-archimedes/meta/src/settings.ts`
- Test: `forks/pi-archimedes/packages/subagent/src/handlers.test.ts`
- Test: `forks/pi-archimedes/packages/subagent/src/stream.test.ts`

**Steps:**
1. Add failing tests using real Pi 0.84 wire shapes for ordered text/thinking deltas, pre-finalization close, and finalized replacement.
2. Add minimum per-message content-index assembly and reset it on `message_start`/`message_end`.
3. Keep the legacy cumulative-message path for Pi 0.74–0.83 children.
4. Bound cumulative live preview reconstruction at 12,000 characters and stop emitting unchanged progress after the ceiling; final output remains complete at `message_end`.
5. Count usage only from authoritative `message_end`; preserve partial termination state and output.
6. Mark TUI imports used only as types so Pi 0.84's exports pass `verbatimModuleSyntax` checks without runtime imports.
7. Run package/workspace TypeScript and subagent/full tests under normal dependencies and exact Pi 0.74.0 and 0.84.1.

**Focused verification:**
```bash
pnpm --filter @pi-archimedes/subagent test
pnpm --filter @pi-archimedes/subagent typecheck
pnpm typecheck
pnpm test
```

**Expected result:** Delta output remains visible in content-index order; finalized usage is counted once; all existing execution controls pass.

### Task 2: Pin Pi and project parser [Depends on: Task 1]

**Context:** Use owner release 0.84.1 rather than overrides. Project runtime projection must include the vendor parser compatibility change.

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `tests/test_beads_workspace.py`
- Modify: `docs/extension-web-compatibility.md`
- Modify: `forks/pi-archimedes`
- Modify: `patches/pi-packages/pi-archimedes-subagent-1.8.3.patch`
- Modify if needed: `patches/pi-packages/README.md`

**Steps:**
1. Change pin assertion first and confirm it fails.
2. Install exact Pi 0.84.1 with lifecycle scripts disabled; verify nested patched dependency versions and zero audit findings.
3. Pin the verified vendor commit and regenerate the production-only 1.8.3 patch from the clean npm base.
4. Update compatibility documentation for Pi 0.84.1 and delta-stream handling.
5. Prove fuzz-free patch application and exact vendor source matching.

**Focused verification:**
```bash
npm ci --ignore-scripts
npm audit --omit=optional
.venv/bin/python -m pytest tests/test_beads_workspace.py tests/test_package_patches.py -q
PI_CONFIG_DEST="$TMP/.pi" scripts/apply-pi-package-patches.sh
```

**Expected result:** Exact release and projected runtime are reproducible with no vulnerable transitive versions.

### Task 3: Full verification and local rollout [Depends on: Tasks 1–2]

**Context:** Deployment changes live `~/.pi` and requires informed approval after local verification.

**Files:**
- Runtime only after approval: `~/.pi`
- Closeout: `.beads/issues.jsonl`

**Steps:**
1. Run full deterministic project gates and independent patch review.
2. Request approval to integrate, fast-forward the authorized vendor branch, deploy Pi/config, and run live agentic and one-shot children.
3. Verify live Pi 0.84.1, nested patched versions, delta output, usage, child session, limits, and zero audit findings.
4. Close/export pi-pz5o, commit closeout, and clean merged temporary worktrees.

**Focused verification:**
```bash
pi --version
npm audit --omit=optional
scripts/check-pi-config.sh
```

**Expected result:** Local runtime is Pi 0.84.1 with secure nested dependencies and preserved extension behavior.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| Archimedes production sources | Tasks 1–2 | Task 2 regenerates projection only after Task 1 commits vendor source. |
| `.beads/issues.jsonl` | Task 3 | Preserve approval mutations across main integration; export explicitly at closeout. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-07-pi-0841-security-upgrade-plan.md`
Recommended next skill: `test-driven-development`; use `verification-before-completion` before commit and rollout.
