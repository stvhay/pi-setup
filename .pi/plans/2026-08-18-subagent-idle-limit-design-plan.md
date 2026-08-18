# Progress-Aware Subagent Idle Limit Design and Implementation Plan

**Issue:** pi-840u — Add progress-aware subagent idle limits
**Design:** Approved in current session
**Date:** 2026-08-18
**Branch:** parent `main`; fork `work/pi-840u-idle-limit`

**Goal:** Replace routine subscription-backed wall deadlines with a sliding child-activity lease while preserving optional hard duration bounds.

**Architecture:** Add optional `maxIdleMs` beside existing `maxDurationMs`. One per-child controller owns resettable idle, fixed hard, parent, and worker-stop causes; first cause is recorded synchronously and wins. `streamEvents` renews idle only after minimum runtime validation of known child JSON events, including `message_update` and `tool_execution_update`; its parent-generated display heartbeat never renews the lease. Idle pauses while the child awaits a bridged human `ask`, then restarts with a fresh lease; hard timeout and parent cancellation remain active. Existing two-minute no-event startup protection stays independent and is documented as worker-startup behavior. Subscription review/research calls use `maxIdleMs`; metered, calibration, and explicitly bounded callers may retain `maxDurationMs`.

**Acceptance Criteria:**
- [ ] `maxIdleMs` is validated, minimum-resolved, configurable through subagent and meta settings, publicly typed, and exposed in tool schema.
- [ ] Child inactivity after startup emits `idle-limit` with configured limit, observed idle duration, and partial/unknown usage evidence; existing no-event startup behavior remains distinct.
- [ ] Runtime-valid known child events renew idle deadline; JSON primitives, arrays, unknown/malformed events, malformed lines, stderr, and parent UI heartbeat do not.
- [ ] `maxDurationMs`, parent cancellation, and worker-emitted limit reasons retain existing semantics and deterministic first-cause precedence.
- [ ] `tool_execution_update` counts as child activity without changing result/output behavior.
- [ ] Idle pauses during bridged human `ask`; answer/cancel/socket close resumes it while hard timeout and parent abort remain active.
- [ ] Subscription routine-review examples use `maxIdleMs`; metered self-contained/repository calls and explicit calibration experiments keep hard duration limits.
- [ ] Langfuse/local projection classifies `idle-limit` as timeout/unavailable and maps requested/effective caller/operator `maxIdleMs` evidence.
- [ ] Fork source, subagent/meta package patches, normative result contract, docs, tests, profile, and parent gitlink remain coherent.

**Verification Commands:**
```bash
cd forks/pi-archimedes
corepack pnpm --filter @pi-archimedes/subagent exec vitest run
corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit
corepack pnpm -r exec -- tsc --noEmit
corepack pnpm test

cd ../..
.venv/bin/python -m pytest tests/test_subagent_workaround.py tests/test_package_patches.py tests/test_review_routing_calibration.py
# Package-patch tests use temporary projections; live ~/.pi check/deploy is separately gated.
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Add failing public-limit tests

**Files:** `forks/pi-archimedes/packages/subagent/src/{config,limits,index,execution-profile}.test.ts`

1. Assert `maxIdleMs` validation, zero-as-unlimited config behavior, minimum source resolution, one-shot/agentic profile preservation, public schema bounds, and meta settings save round-trip.
2. Run focused tests and confirm failures are caused by missing `maxIdleMs` support.

### Task 2: Add failing execution-control tests

**Files:** `forks/pi-archimedes/packages/subagent/src/execute.test.ts`, `stream.test.ts`

1. Test idle abort after inactivity.
2. Test activity renewal beyond one idle window and `observed` measured from last valid activity.
3. Test hard-first, idle-first, parent-first, worker-first, and deterministic equal-tick precedence.
4. Test settlement synchronously on close/error so late timers cannot abort/reclassify success.
5. Test `message_update` and `tool_execution_update` renew activity while JSON primitives/arrays/unknown or malformed known events, malformed lines, stderr, and parent heartbeat do not.
6. Test pending/resolved/cancelled/socket-closed human asks pause/resume idle while hard/parent causes still win.
7. Test spawn failure and stream rejection dispose timers/listeners.
8. Run focused tests and preserve RED evidence.

### Task 3: Implement minimum runtime support

**Files:** `forks/pi-archimedes/packages/subagent/src/{types,config,limits,index,execute,stream,spawn}.ts`, `forks/pi-archimedes/meta/src/settings.ts`

1. Add `maxIdleMs` and `idle-limit` to existing public unions, limit lists, operator defaults, and meta settings handling.
2. Implement one resettable controller with explicit `activity`, `pauseIdle`, `resumeIdle`, `recordWorkerStop`, `settle`, and first-cause evidence; fixed hard and parent causes never pause.
3. Wire worker stderr/repeated-error causes before termination, and settle synchronously in every stream terminal path.
4. Wire activity only after minimum runtime validation of known child event shapes; count tool updates without routing through `onProgress`.
5. Wire ask socket pending lifecycle to idle pause/resume and cleanup.
6. Preserve startup safeguard, process termination, partial output, usage, parallel ordering, and existing hard-limit behavior.
7. Run focused tests to GREEN, then full package tests/typecheck.

### Task 4: Switch subscription policy and telemetry

**Files:** `pi/agent/skills/requesting-code-review/SKILL.md`, `.pi/skill-evals/requesting-code-review/scenarios/avoid-avoidable-subagent-aborts.md`, `pi/agent/extensions/subagent-error-workaround.ts`, `tests/test_subagent_workaround.py`, `tests/test_review_routing_calibration.py`, related eval/docs files found by `rg`.

1. Add failing policy/telemetry tests first and capture RED evidence.
2. Replace routine subscription review `maxDurationMs: 300000` examples/assertions with `maxIdleMs: 300000`; research remains uncapped where it already has no caller deadline.
3. Keep metered self-contained/repository hard bounds and explicit calibration manifests/results unchanged.
4. Normalize `idle-limit` as timeout/unavailable with effective/requested max-idle, caller/operator source, partial output, and artifact evidence.

### Task 5: Align fork and parent documentation

**Files:** `forks/pi-archimedes/packages/subagent/README.md`, fork root `README.md` if needed, `.pi/plans/2026-08-15-pi-archimedes-result-port-contract.md`, `pi/README.md`, `docs/extension-web-compatibility.md`, `patches/pi-packages/README.md`, `.pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md`.

Document idle vs hard semantics, valid activity, limits, and subscription policy without changing unrelated behavior.

### Task 6: Produce maintained projection

1. Complete and move fork plan under `docs/plans/done/`; update fork plan index.
2. Commit one logical fork change on `work/pi-840u-idle-limit`.
3. Regenerate exact `@pi-archimedes/subagent@2.1.0` and `pi-archimedes@2.1.0` meta production patches from `v2.1.0` to candidate fork head.
4. Update parent proof constants, both patch digests, profile provenance, tests, and submodule gitlink.
5. Run fixture/temp projection tests. Do not run live `scripts/apply-pi-package-patches.sh --check` or deploy to `~/.pi` without separate deployment scope.
6. Full network proof remains blocked until exact `vendor/pi-setup-210` push approval because it verifies remote head equality.

### Task 7: Review, verify, commit, close

1. Run model-assisted review against exact diff; verify findings against source/tests.
2. Run full verification after final changes.
3. Commit parent task-owned changes atomically.
4. Obtain separate exact approval before any fork push; no push, PR, tag, release, or publication is implied.
5. Run `agnt work direct-closeout pi-840u --outcome success` only after portable fork commit is reachable and parent tree is clean.

## File Conflicts

Runtime tests and implementation share subagent files, so Tasks 1–3 are serial. Projection and documentation depend on final fork commit. Parent commit/closeout depends on approved fork publication or another portable recovery source.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-18-subagent-idle-limit-design-plan.md`.
Recommended execution: TDD for behavior changes; verification-before-completion before commits.
