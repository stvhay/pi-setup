# Upstream Subagent Session Traceability Plan

**Issue:** pi-4tg9.3 — Propagate canonical session identity into every execution trace

**Date:** 2026-08-05

**Upstream bases:** pi-langfuse v1.5.9 (`3243208`), pi-archimedes v1.8.3 (`801397c`)

**Branches:** `fix/pi-session-correlation` in each upstream fork

## Goal

Use Pi's existing logical subagent session UUID as the sole normalized foreign key from parent telemetry to detailed subagent Langfuse traces.

```text
parent subagent result/projection
  childSessionId ─────────────► Langfuse sessionId
                                  subagent trace
                                  generations
                                  tools
                                  first assistant stream event
```

Each current Archimedes invocation launches one fresh `pi --mode json --no-session -p <task>` process. Pi still creates an in-memory `SessionManager`, assigns a UUID, and emits that UUID in the initial JSON `session` event. Therefore the child session UUID is already a unique invocation key.

## Minimum upstream changes

### pi-langfuse bug fix

Prefer public `ctx.sessionManager.getSessionId()` before existing session-file basename fallback. This restores session grouping for supported ephemeral `--no-session` runs without changing persistent-session compatibility.

### pi-archimedes observability enhancement

Stop ignoring Pi's JSON `session` event. Capture its `id` and expose it as optional `childSessionId` on `SubagentResult`.

## Explicit non-goals

- Do not persist Archimedes child transcripts; retain `--no-session`.
- Do not add a second `invocationId`; child session UUID is unique in current one-process/one-prompt execution.
- Do not export or transport Langfuse `traceId`.
- Do not add parent-session environment variables or cross-package trace context.
- Do not modify Pi core.
- Do not patch finalization unless a repeated short-process test fails; pi-langfuse 1.5.9 already awaits bounded shutdown.
- Do not claim TTFT means first visible text token. Current `completionStartTime` measures first assistant stream event, which may be thinking, text, or tool-call output.

## Privacy caveat

Pi's parent `tool_execution_end.result` contains Archimedes' complete `{content, details}` result, and pi-langfuse reads `event.result`. However privacy presets may suppress tool output. Therefore pi-setup's parent-owned `subagent-result` projection is the always-retained foreign-key location; parent tool-observation output is opportunistic, not canonical.

## Acceptance criteria

- [ ] Ephemeral pi-langfuse roots use exact `SessionManager.getSessionId()` UUID.
- [ ] Older Pi contexts without `getSessionId()` retain session-file basename behavior.
- [ ] Archimedes retains `--no-session` and captures exact initial JSON `session.id`.
- [ ] `SubagentResult.childSessionId` is present when a valid session event was received and absent when process fails before that event.
- [ ] Single and parallel result/details payloads preserve child IDs and existing index alignment.
- [ ] Parent projection stores `childSessionId`; exact Langfuse session lookup returns detailed child trace data without timestamp/model heuristics.
- [ ] Existing pi-langfuse finalization test passes; repeated synthetic short-process proof loses no completed observation.
- [ ] Upstream focused/full tests and typechecks pass.
- [ ] Local patchset is version-checked, reversible, and contains no private trace/session IDs.
- [ ] Forks, pushes, and draft PRs occur only after separate informed approval.

## Verified contribution constraints

### pi-langfuse

- npm only; preserve `package-lock.json`.
- Required: `npm run typecheck`, `npm test`, `npm pack --dry-run`.
- Stable v1.5.9 equals `origin/main`.

### pi-archimedes

- pnpm workspace only; use Corepack.
- Required: package/all-package TypeScript checks and full Vitest suite.
- Add date-named plan under `docs/plans/`, update plan index, and commit plan separately.
- Preserve Windows spawn behavior, `--no-session`, socket cleanup, abort behavior, and parallel order.

## Task 1: pi-langfuse TDD patch

**Files:**
- Modify: `index.ts`
- Modify: `test/index.test.ts`
- Modify: `README.md`
- Modify: `README_CN.md`

**Steps:**
1. Add integration test with session manager returning logical UUID and no file.
2. Observe RED: propagated Langfuse `sessionId` is undefined.
3. Add four-line preference for `getSessionId()` before unchanged file fallback.
4. Observe GREEN; run focused index test and typecheck.
5. Reserve full test/package gate for stable candidate review.

**Recorded RED:**
```text
Expected logical-session-id; received undefined.
```

## Task 2: required pi-archimedes plan

**Files:**
- Create: `docs/plans/2026-08-05-subagent-session-id.md`
- Modify: `docs/plans/README.md`

**Steps:**
1. Record problem as ignored documented session header, not missing session creation.
2. Specify additive optional result field and no spawn/persistence changes.
3. Include focused RED/GREEN, package/all-package typecheck, and full test commands.
4. Mark IN PROGRESS; review against `AGENTS.md`; commit plan separately with `docs:` prefix.

## Task 3: pi-archimedes TDD patch

**Files:**
- Modify: `packages/subagent/src/types.ts`
- Modify: `packages/subagent/src/handlers.ts`
- Modify: `packages/subagent/src/handlers.test.ts`
- Modify: `packages/subagent/src/stream.ts`
- Create: `packages/subagent/src/stream.test.ts` only if result assembly cannot be proved in existing tests
- Modify: `packages/subagent/README.md`
- Modify: `docs/plans/2026-08-05-subagent-session-id.md`
- Modify: `docs/plans/README.md`

**Steps:**
1. Add RED test: valid JSON `session` event stores exact ID.
2. Add RED test: final result exposes `childSessionId`; missing/invalid header leaves field undefined.
3. Add RED parallel/result-shape regression only if existing executor tests do not already prove unchanged index alignment.
4. Add `childSessionId?: string` to `StreamState` and `SubagentResult`.
5. Handle `session` event without emitting extra progress.
6. Copy captured ID into final result. Do not add field to `SubagentProgress`.
7. Update docs and mark plan complete after verification.
8. Run focused tests and typecheck; reserve full suite for final candidate gate.

**Focused commands:**
```bash
corepack pnpm --dir packages/subagent exec vitest run src/stream.test.ts
corepack pnpm --dir packages/subagent exec tsc --noEmit
```

## Task 4: combined synthetic proof

**Harness:** Package-native focused tests use the same synthetic UUID; a Python assertion checks both fixtures contain that exact key and no added invocation/trace contract.

**Steps:**
1. Feed synthetic Pi JSON session completion through patched Archimedes stream test.
2. Verify returned parent result contains exact `childSessionId`.
3. Feed the same UUID through patched pi-langfuse handler test and capture propagated Langfuse `sessionId`.
4. Assert equality and absence of timestamp/model matching or extra invocation/trace keys.
5. Run existing `agent_end waits for runtime shutdown` proof.
6. Keep credentials unset and all IDs synthetic.

**Environment note:** Actual `npm pack` and direct `node --import tsx` both SIGSEGV on local Nix Node 22.22.3, while repository-owned npm/Vitest/tsx checks pass and `agnt doctor --json` reports no environment fault. Do not retry the crashing paths; retain required `npm pack --dry-run` in the final gate.

## Task 5: reversible pi-setup integration

**Selected mechanism:** Exact npm pins plus tracked runtime-only unified diffs applied by an idempotent, version/context-locked helper.

**Files:**
- Modify: `pi/agent/settings.json` (`pi-langfuse@1.5.9`, `pi-archimedes@1.8.3`)
- Create: `patches/pi-packages/{README.md,pi-langfuse-1.5.9.patch,pi-archimedes-subagent-1.8.3.patch}`
- Create: `scripts/apply-pi-package-patches.sh`
- Create: `tests/test_package_patches.py`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Modify: `pi/agent/extensions/lib/runtime-artifacts.ts`
- Modify: `pi/agent/bin/agnt_lib/metrics.py`
- Modify: focused tests and affected README/architecture docs

**Local behavior:**
- Read bounded `details.results[*].childSessionId` from Archimedes result.
- Store it on parent `subagent-result` projection, metric, and private result artifact.
- Prefer public parent `getSessionId()` before historical file fallback.
- Keep historical records readable when child ID is absent.
- Retain existing private artifact `invocationId` for backward-compatible paths; never use it for child trace lookup.
- Never hand-edit deployed package files; run the tracked helper after Pi installs exact pinned packages.

**Rollback:** Reinstall the two exact npm versions to remove runtime edits, revert this task's settings/helper/patch/projection changes, then deploy tracked config. No session/metric/artifact deletion is required.

## Task 6: review and final verification

1. Independent review of each upstream diff and local integration.
2. Verify every finding against source; fix only confirmed blockers.
3. Run final stable-candidate gates once:

```bash
# pi-langfuse
npm run typecheck
env -u LANGFUSE_PRIVACY_PRESET -u LANGFUSE_CAPTURE_CWD -u LANGFUSE_CAPTURE_SYSTEM_PROMPT -u LANGFUSE_CAPTURE_TOOL_IO npm test
npm pack --dry-run

# pi-archimedes
corepack pnpm --dir packages/subagent exec tsc --noEmit
corepack pnpm -r exec -- tsc --noEmit
corepack pnpm test

# pi-setup
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
git diff --check
```

4. Inspect for secrets/private IDs, unrelated version bumps, generated files, lockfile drift, and expanded protocol scope.

## Task 7: local commits

- pi-langfuse: one logical bug-fix commit.
- pi-archimedes: required plan commit, then implementation/docs commit.
- pi-setup: one atomic task-owned integration/patchset commit unless split is required for deterministic patch artifacts.
- No push, merge, tag, release, package publication, branch deletion, or worktree removal.

## Task 8: draft PR approval and publication

1. Create durable approval gate containing fork names, branches, commits, diff stats, verification, exact titles/bodies, consequences, and rollback.
2. After approval only, create/reuse `stvhay` forks, push two bounded branches, and open draft PRs against upstream `main`.
3. Suggested titles:
   - pi-langfuse: `fix: use logical Pi session ID for ephemeral runs`
   - pi-archimedes: `feat(subagent): expose child Pi session ID in results`
4. Do not mark ready, merge, tag, release, or publish packages.

## Review feedback disposition

**Applied:**
- `--no-session` retains logical identity; no persistence change.
- `childSessionId` is sufficient normalized foreign key for current one-shot model.
- No extra invocation ID, child trace ID, parent environment protocol, or Pi core change.
- Finalization and TTFT claims narrowed to current tested semantics.

**Qualified:**
- Parent tool result contains the ID, but privacy policy may suppress tool output. pi-setup parent projection remains canonical retained join record.

Plan path: `.pi/plans/2026-08-05-upstream-traceability-patches-design-plan.md`
