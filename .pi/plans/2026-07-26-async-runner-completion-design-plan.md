# Asynchronous Runner Completion Design and Implementation Plan

**Issue:** pi-9n04 — Make runner completion asynchronous
**Design:** Combined below
**Date:** 2026-07-26
**Branch:** main

**Goal:** Return live runner tick requests immediately, execute work in one bounded background slot, and wake opted-in Pi orchestration sessions from durable terminal events.

**Architecture:** Keep the existing synchronous `runner_tick()` worker path and its provider watchdogs, but move live service ticks behind a single background worker thread guarded by the existing tick lock. The service returns an accepted response, records scheduler and per-run terminal events after work finishes, and keeps dry-run ticks synchronous for useful operator output. The Pi extension advances an in-memory `/v1/events` cursor during existing polling and injects one fixed-format `followUp` custom message per new `run_finished` event with `triggerTurn: true`.

**Acceptance Criteria:**
- [ ] Live `POST /v1/tick` returns an accepted response before the worker finishes; overlapping live ticks return 409.
- [ ] Dry-run ticks remain synchronous and return their action plan.
- [ ] Background completion updates scheduler status and appends compact `run_finished` events with bead, outcome, run ID, and bundle when available.
- [ ] Drain waits for an in-flight tick; worker/provider watchdogs remain unchanged.
- [ ] Extension initializes a cursor before lease attachment, catches up after transient request failures, and sends one completion follow-up per terminal event.
- [ ] Runner service API documentation matches behavior.
- [ ] Focused and full project checks pass.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_runner_service.py tests/test_runner_client.py tests/test_orchestrator_extension.py
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

## Chosen Design

- Reuse existing `ThreadingHTTPServer`, tick lock, runner state, and append-only event endpoint.
- Use one daemon worker thread per accepted tick; tick lock bounds execution to one live tick. Do not add a queue, dependency, SDK sidecar, WebSocket, SSE, or Unix signal.
- Keep `runner_tick()` unchanged so CLI/manual and scheduler behavior share one worker path.
- Keep `dryRun=true` synchronous because it does not invoke a model and callers need the returned plan.
- Emit fixed compact terminal metadata; do not inject worker output or error text into Pi model context.
- Reuse the extension's five-second polling loop. Event cursor removes guessed completion timeouts; transient failures retry from the same offset.
- Keep absolute worker/provider timeouts as safety watchdogs. This change removes only the blocking orchestrator request boundary.

## Task 1: Prove asynchronous service behavior [Independent]

**Context:** Add service-level tests before production edits. A fake tick blocks on an event so the test can prove HTTP acceptance occurs first, overlap is rejected, terminal events are durable, and drain waits.

**Files:**
- Test: `tests/test_runner_service.py`

**Steps:**
1. Add a live tick test using a blocking fake `runner_tick`.
2. Assert the first HTTP response is accepted while the fake worker remains blocked.
3. Assert a second live tick receives 409.
4. Release the worker and assert scheduler plus `run_finished` events appear.
5. Add/extend a drain assertion for the in-flight tick.
6. Run the focused test and confirm expected failure before implementation.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_service.py -k 'async or overlap or drain'
```

**Expected result:** New test fails because live `/v1/tick` still blocks.

## Task 2: Add bounded background tick execution [Depends on: Task 1]

**Context:** Move live tick execution off the HTTP and scheduler threads without changing `runner_tick()` or provider timeout behavior.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/runner_service.py`
- Modify: `pi/agent/bin/agnt_lib/runner_protocol.py`
- Test: `tests/test_runner_service.py`
- Test: `tests/test_runner_protocol.py`

**Steps:**
1. Add a nonblocking tick submission method that acquires the existing tick lock and starts one daemon worker thread.
2. Centralize started/completed/failed scheduler state and event recording in the worker.
3. Return HTTP 202 with compact acceptance metadata for live ticks; preserve synchronous dry-run responses.
4. Make autonomous scheduler loop submit work instead of awaiting it.
5. Treat tick-lock ownership as active work for graceful drain.
6. Derive compact per-run terminal events from scheduler actions without changing the scheduler API.
7. Serialize event appends with a project-local flock so concurrent service threads retain unique offsets.
8. Run focused tests until green.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_service.py tests/test_runner_client.py
```

**Expected result:** Live request returns before release; completion evidence appears after release; existing client and scheduler tests pass.

## Task 3: Prove and implement Pi completion wake-up [Depends on: Task 2]

**Context:** Consume existing `/v1/events` catch-up from the opted-in extension. Use `pi.sendMessage`, not `sendUserMessage`, so the runner does not impersonate the user.

**Files:**
- Modify: `pi/agent/extensions/orchestrator-service.ts`
- Test: `tests/test_orchestrator_extension.py`

**Steps:**
1. Add a Node harness test that feeds duplicate terminal event payloads and expects one sent custom message.
2. Confirm expected failure before production edits.
3. Add event cursor and notified-offset state.
4. Initialize cursor after daemon readiness but before lease attachment.
5. During existing polling, fetch `/v1/events?since=<offset>` and process only `run_finished` events.
6. Inject a fixed, sanitized message via `pi.sendMessage(..., { deliverAs: "followUp", triggerTurn: true })`.
7. Clear polling state idempotently at shutdown.
8. Run focused extension tests until green.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_orchestrator_extension.py
```

**Expected result:** One completion signal per event offset; repeated payloads or transient polling retries do not duplicate it.

## Task 4: Align documentation and verify [Depends on: Task 3]

**Context:** Document user-visible API and lifecycle changes, then run all repository checks.

**Files:**
- Modify: `docs/RUNNER-SERVICE.md`

**Steps:**
1. Document HTTP 202 live tick behavior, synchronous dry runs, terminal event shape, and Pi wake-up semantics.
2. Run focused tests.
3. Run full pytest, Ruff, layout, shell, deterministic eval, and whitespace checks available without mutating Git state.
4. Record verification evidence on `pi-9n04` and close it only after all checks pass.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_service.py tests/test_runner_client.py tests/test_orchestrator_extension.py
```

**Expected result:** Documentation matches passing behavior.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `tests/test_runner_service.py` | Tasks 1, 2 | Task 2 depends on Task 1. |
| `tests/test_orchestrator_extension.py` | Task 3 test and implementation verification | Red-green cycle stays within Task 3. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-26-async-runner-completion-design-plan.md`
Recommended next skill: `test-driven-development`; use `verification-before-completion` before claiming completion.
