# Project-Local Runner Service Implementation Plan

**Issue:** None
**Design:** None — revised Option C design basis approved in-session on 2026-07-09
**Date:** 2026-07-09
**Branch:** main

**Goal:** Running `pi` should load an orchestrator-only main thread, verify the environment, start or attach to one project-local runner service, surface queued/active work, and have the service schedule approved Beads work through recorded `agnt` runs.

**Architecture:** Beads remains the durable work graph and `.pi/runs` remains the evidence store. `agnt` remains the deterministic control plane for routing, prompt/context composition, run artifacts, health, approvals, lessons, and non-LLM infrastructure tasks. A Python loopback REST service owns scheduling and executor lifecycle for one project root; the Pi TUI extension is a client that gates startup, restricts main-thread tools, manages a session lease, and displays status. Existing Pi/Archimedes extension capabilities are reused for subagent UI, ask/todo/footer affordances rather than replacing them.

**Acceptance Criteria:**
- [ ] `agnt doctor --profile orchestrator-startup --json` distinguishes required startup failures from acknowledged optional absences; `SEARXNG_URL` is required for search/research readiness, while intentionally absent optional provider env vars can be acknowledged without recurring warnings.
- [ ] `agnt work daemon start|stop|status --json` directly manages one loopback runner service per project root, with pid/port/auth material under `.pi/runner/` and no installed launch agent, hook, or global service.
- [ ] `agnt work runner status|pause|resume|tick --json` acts as a REST client to the project service; runner subcommands no longer bypass the service boundary except through explicit daemon lifecycle commands.
- [ ] The service enforces a project-local singleton, authenticated loopback API, heartbeat, active-run tracking, graceful drain, retry/backoff limits, duplicate-dispatch prevention, and bounded concurrency `N`.
- [ ] When `pi` starts, the orchestrator extension runs the startup health profile, starts or attaches the service if healthy, registers a lease, restricts main-thread tools to orchestrator-safe surfaces, shows ready/active/blocked runner status, and blocks background dispatch when startup is not warning-free or explicitly acknowledged.
- [ ] When the last attached Pi session exits, the extension asks the service to stop accepting new tasks and drain active work before exit.
- [ ] Active work monitoring exposes work slug, epic id, run id, model/thinking effort, context usage, accumulated cost when available, status, and blockers through both `ticket_gateway runner_status` and the TUI widget/status surface.
- [ ] Existing Beads safety gates remain: no auto-push/merge/deploy, no Beads replacement, no raw main-thread implementation path for durable work, no destructive git/service install actions without explicit approval.
- [ ] Documentation and evals reflect the new service boundary and orchestrator-only main-thread policy.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt doctor --profile orchestrator-startup --json
pi/agent/bin/agnt work daemon status --json
pi/agent/bin/agnt work runner status --json
```

---

## Approved Requirements Captured

- Prefer maintained Pi packages/extensions over custom implementation where suitable; keep the system DRY and simple.
- Keep using `agnt` for dynamic prompt guidance by role/model, deterministic infrastructure operations, filesystem-backed prompting and lessons, and global/project configuration separation.
- Optimize token cost and context efficiency through routing/model policy and context management.
- Startup must gate work until environment readiness is confirmed. Missing optional features or environment variables are acceptable only after the user's intent is recorded.
- Primary workflow: user runs `pi`; Pi loads the orchestrator and initializes/starts required dependencies/configuration.
- Startup should expose ready tasks, begin background work on ready approved work, and leave the orchestrator ready for prompting.
- Runner should stop accepting new tasks when `pi` exits but finish active/queued executor work before exiting.
- Only one runner per project root may be active on a system, managing `N` task executors.
- Monitoring should be visible in the TUI and not TUI-only: future remote dashboards, daemon mode, multi-project views, and remote daemon streaming should be possible.
- For this scope, the runner is project-level and managed as part of running `pi`; a future global daemon is not the same as this runner.
- First Option C step should create architectural separation by converting `agnt work runner` subcommands, except daemon lifecycle, into clients of a REST API.
- Design target is production-ready for a single user, not a skeleton.

## Existing Surfaces To Preserve

- `pi/agent/bin/agnt_lib/runner.py`: current runner state, lock, pause/resume/status, bounded tick, worktree blockers, write-set serialization, maintenance-idle behavior.
- `pi/agent/bin/agnt_lib/work.py`: `agnt work` CLI, run dispatch, preflight, runner/loop commands.
- `pi/agent/bin/agnt_lib/gateway.py` and `pi/agent/extensions/ticket-gateway.ts`: structured Beads gateway and `runner_status` exposure.
- `pi/agent/bin/agnt_lib/doctor.py`: readiness checks and provider/env checks.
- `pi/agent/extensions/beads-ask-bridge.ts`: durable question/approval tools.
- `pi/agent/extensions/guidance-edit-guard.ts`: deterministic guidance edit guard; keep independent.
- `docs/ORCHESTRATION-LOOP.md`, `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`, `docs/RUN-ARTIFACTS.md`: orchestration/run-artifact docs.
- Existing tests: `tests/test_runner.py`, `tests/test_ticket_gateway.py`, `tests/test_doctor.py`, `tests/test_worktree_policy.py`, `tests/test_health.py`.

## Proposed Runner API Contract

All endpoints bind to `127.0.0.1` only. Each project root gets its own service metadata under `.pi/runner/service.json`. Clients authenticate with `Authorization: Bearer <token>`; token material is local runtime state and must not be tracked.

Runtime files:

```text
.pi/runner/service.json       # pid, port, token path/ref, root, startedAt, apiVersion, concurrency
.pi/runner/token              # random local bearer token, mode 0600 where supported
.pi/runner/state.json         # compatible runner state, paused/draining/budget/heartbeat/leases
.pi/runner/events.jsonl       # compact append-only event stream for TUI/client catch-up
.pi/runner/active/<run-id>.json # active run snapshots for crash recovery and status
.pi/runner/lock.json          # singleton lock retained for compatibility/stale detection
```

Minimum v1 endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Liveness, api version, project root, heartbeat age. |
| `GET` | `/v1/status` | Full runner state: paused/draining/running, leases, active runs, budget, ready counts if cheap. |
| `POST` | `/v1/leases` | Attach a Pi client session lease `{sessionId, client, ttlSeconds}`. |
| `DELETE` | `/v1/leases/<leaseId>` | Detach a Pi client session. Last lease triggers drain by policy. |
| `POST` | `/v1/drain` | Stop accepting new tasks; finish active work; exit when idle if no leases remain. |
| `POST` | `/v1/stop` | Operator stop; default is drain, force mode only for explicit daemon stop. |
| `POST` | `/v1/pause` | Pause scheduling with reason. |
| `POST` | `/v1/resume` | Resume scheduling. |
| `POST` | `/v1/tick` | Schedule one bounded tick; mostly for tests/operator/debug, still service-mediated. |
| `GET` | `/v1/events?since=<offset>` | JSONL event catch-up for TUI/client polling; SSE can layer on this later. |

Active run status fields exposed by `/v1/status` and `ticket_gateway runner_status`:

```json
{
  "bead": "pi-abc.1",
  "slug": "short work title",
  "epicId": "pi-abc",
  "runId": "runner-pi-abc.1-YYYYmmddHHMMSS",
  "status": "queued|starting|running|blocked|failed|succeeded|draining",
  "model": "provider/model",
  "thinkingLevel": "medium",
  "context": {"used": 0, "limit": 0, "percent": null},
  "cost": {"usd": null, "source": "metrics|footer|unknown"},
  "bundle": ".pi/runs/<run-id>",
  "blockers": []
}
```

## Implementation Tasks

### Task 1: Runner protocol and state contracts [Independent]

**Context:** Define the service/client JSON contracts before implementing network behavior. Keep these contracts dependency-free and usable by tests, CLI, service, health, and ticket gateway.

**Files:**
- Create: `pi/agent/bin/agnt_lib/runner_protocol.py`
- Create: `tests/test_runner_protocol.py`
- Modify: `.gitignore`

**Steps:**
1. Write tests for service metadata path normalization, redacted status output, token-path handling, lease normalization, active-run summaries, and event offset behavior.
2. Implement dependency-free helpers/constants for runner API version, runtime file paths, service metadata load/save, state normalization, status redaction, active-run snapshot schema, and JSONL event append/read.
3. Add `.pi/runner/` to `.gitignore` because service state, lock files, active run snapshots, ports, tokens, and event logs are runtime state.
4. Preserve compatibility with existing `.pi/runner/state.json` and `.pi/runner/lock.json` fields.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_protocol.py
```

**Expected result:** New protocol tests pass; no secrets or absolute token values are exposed in redacted status output.

### Task 2: Loopback runner service core [Depends on: Task 1]

**Context:** Build the project-local REST service with stdlib Python primitives first. It should be usable without Pi running, but the primary lifecycle will be managed by the Pi extension and daemon CLI.

**Files:**
- Create: `pi/agent/bin/agnt_lib/runner_service.py`
- Create: `tests/test_runner_service.py`
- Modify: `pi/agent/bin/agnt_lib/runner.py`

**Steps:**
1. Write tests that start the service on `127.0.0.1:0` with a temp root, reject unauthenticated requests, accept authenticated `/v1/health` and `/v1/status`, create/delete leases, pause/resume, drain, and write service metadata.
2. Implement a small loopback HTTP server using stdlib modules (`http.server`, `socketserver`, `threading`, `urllib`/JSON helpers). Avoid new runtime dependencies unless a later review proves stdlib inadequate.
3. Retain the existing singleton lock semantics by acquiring `.pi/runner/lock.json` before serving and refusing a second live service for the same root.
4. Store heartbeat and lease state in `.pi/runner/state.json` via the Task 1 protocol helpers.
5. Implement graceful shutdown signals in-process: `draining=true`, `acceptingNewWork=false`, exit when no active runs remain and no leases are attached.
6. Keep force-stop support explicit and operator-only through the daemon client path, not as a default shutdown behavior.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_service.py tests/test_runner.py
```

**Expected result:** Service tests pass and existing runner pause/status/lock tests still pass.

### Task 3: Scheduler and executor pool [Depends on: Task 2]

**Context:** Move from one synchronous tick loop toward a service-owned scheduler that manages up to `N` executors, active run snapshots, retry/backoff, and duplicate-dispatch prevention while preserving Beads and `.pi/runs` as the durable sources of truth.

**Files:**
- Create: `pi/agent/bin/agnt_lib/runner_scheduler.py`
- Create: `tests/test_runner_scheduler.py`
- Modify: `pi/agent/bin/agnt_lib/runner.py`
- Modify: `pi/agent/bin/agnt_lib/health.py`

**Steps:**
1. Write tests with fake Beads and fake `runner_start` for: bounded concurrency, no duplicate active bead dispatch, draining stops new dispatch, active runs finish during drain, retry cap/backoff for transient failures, terminal failed/blocked states not auto-closed, stale active run detection, and write-set serialization across active executor slots.
2. Extract reusable scheduling logic from `runner_tick` while keeping `runner_tick` as a compatibility function that can call the scheduler in single-tick mode.
3. Add active run snapshot writes under `.pi/runner/active/` before invoking a worker and terminal snapshot cleanup/finalization after completion.
4. Track per-bead attempt counters and `nextEligibleAt` in runner state; default retry policy should be conservative for single-user production, e.g. max 2 automatic retries for infrastructure/transient failures, zero retries for validation/human blockers.
5. Enforce `N` from service config/state, defaulting to 1 until explicitly configured.
6. Maintain existing worktree safety: implementation dispatch still requires approved metadata, non-main clean epic worktree, and non-overlapping write sets.
7. Update health checks to report stale active snapshots and heartbeat age in addition to stale lock files.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_scheduler.py tests/test_runner.py tests/test_health.py tests/test_worktree_policy.py
```

**Expected result:** Scheduler handles concurrent read-only work safely, serializes conflicting implementation work, drains cleanly, and reports stale state through health checks.

### Task 4: CLI daemon lifecycle and REST client boundary [Depends on: Tasks 2-3]

**Context:** Convert `agnt work runner` subcommands into service clients. Keep direct process management under `agnt work daemon start|stop|status`; the service may expose an internal `serve` subcommand for spawned child processes, but user-facing runner operations should go through REST.

**Files:**
- Create: `pi/agent/bin/agnt_lib/runner_client.py`
- Create: `tests/test_runner_client.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Modify: `tests/test_runner.py`
- Modify: `pi/agent/bin/README.md`

**Steps:**
1. Write tests for client discovery from `.pi/runner/service.json`, missing-service errors, auth header inclusion, status/pause/resume/tick JSON calls, and daemon start/stop/status command behavior using fakes where possible.
2. Add `agnt work daemon start --json [--root] [--concurrency N] [--interval seconds]`, `agnt work daemon stop --json [--drain|--force]`, and `agnt work daemon status --json`.
3. Implement daemon start as a project-local background process that launches the service for the current git/project root, writes metadata only after health succeeds, and refuses to start if a live service already owns the root.
4. Convert `agnt work runner status|pause|resume|tick` to call the REST client. If no service is running, return a clear JSON error with suggested action `agnt work daemon start --json` rather than silently falling back to direct local state mutation.
5. Decide the compatibility fate of `agnt work loop`: either deprecate with guidance to `daemon start` or make it a foreground service wrapper that still uses the same service core. Do not leave it as a second scheduler path.
6. Ensure all command outputs remain JSON-stable for extension clients.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_client.py tests/test_runner.py
pi/agent/bin/agnt work daemon status --json || true
```

**Expected result:** Runner subcommands are API clients; only daemon lifecycle commands directly manage the process/service boundary.

### Task 5: Startup health profile and intent acknowledgements [Independent, then used by Task 6]

**Context:** Startup must block background work until environment readiness is confirmed and warnings are either fixed or intentionally acknowledged. Provider env checks should not nag for providers the user intentionally does not use.

**Files:**
- Create: `pi/agent/bin/agnt_lib/startup_policy.py`
- Create: `tests/test_startup_policy.py`
- Modify: `pi/agent/bin/agnt_lib/doctor.py`
- Modify: `tests/test_doctor.py`
- Modify: `pi/agent/bin/README.md`

**Steps:**
1. Write tests for profile selection, required env failure (`SEARXNG_URL`), optional provider acknowledgement (`ANTHROPIC_API_KEY` intentionally absent), redaction, and strict exit behavior.
2. Add `agnt doctor --profile orchestrator-startup --json` and keep existing `--check` behavior working.
3. Define startup profile checks to include at least: `command.pi`, `command.bd`, `python.version`, `git.root`, `node.version`, `catalog.parse`, `verification.commands`, provider env policy, `SEARXNG_URL`, and Beads workspace health.
4. Add a small intent config mechanism, e.g. project `.pi/doctor-intent.json` and global `~/.pi/agent/doctor-intent.json`, for non-secret acknowledgements such as `{ "intentionallyAbsentEnv": { "ANTHROPIC_API_KEY": "not used" } }`. Ensure local runtime intent files are not accidentally tracked unless explicitly intended.
5. Produce a startup report that separates `failures`, `warnings`, and `acknowledgedWarnings`; background runner dispatch is allowed only when failures are zero and unacknowledged warnings are zero.
6. Do not mutate shell startup files or repair environment automatically.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_startup_policy.py tests/test_doctor.py
pi/agent/bin/agnt doctor --profile orchestrator-startup --json || true
```

**Expected result:** The profile is strict enough to block unsafe startup, but can record intentional optional absence without repeated warnings.

### Task 6: Orchestrator-only Pi extension [Depends on: Tasks 2, 4, 5]

**Context:** The main Pi thread should act as an orchestrator/client. It should not be the normal implementation worker for durable Beads work. This extension enforces startup readiness, service attach/start, tool surface narrowing, lease lifecycle, status display, and drain-on-exit.

**Files:**
- Create: `pi/agent/extensions/orchestrator-service.ts`
- Create: `tests/test_orchestrator_extension.py`
- Modify: `pi/agent/settings.json` if package/extension registration changes are required
- Modify: `scripts/check-pi-config.sh` only if new config files need validation

**Steps:**
1. Write static/text tests that confirm the extension registers `session_start` and `session_shutdown` handlers, invokes `agnt doctor --profile orchestrator-startup --json`, uses `agnt work daemon start/status`, creates/deletes service leases, calls drain on shutdown, uses `pi.setActiveTools`, and never shells out to raw `bd`.
2. Implement `session_start` behavior:
   - run startup health profile;
   - if failures/unacknowledged warnings exist, show a blocking widget/status with suggested fixes and do not start background dispatch;
   - if healthy, start or attach the daemon, create a lease, and begin polling status/events.
3. Restrict main-thread tools with `pi.setActiveTools()` to an orchestrator-safe allowlist. Initial proposed allowlist: `read`, `ticket_gateway`, `ticket_question`, `ticket_approval`, `ticket_decision_resolve`, `recall`, and any future dedicated `runner_gateway` tool. Do not include raw `bash`, `edit`, `write`, or raw `subagent` in the orchestrator profile.
4. Register a compact command such as `/runner` or extend `/work` only if it does not conflict with `ticket-gateway.ts`; otherwise keep the gateway command as the user-facing work view and add status widgets here.
5. Implement `session_shutdown` behavior: delete the lease; if this was the last lease, request drain. The shutdown handler must be idempotent and tolerate an already-stopped service.
6. Surface health/runner state via `ctx.ui.setStatus` and/or a widget. Keep output compact and truncate large JSON.
7. Do not install launch agents, hooks, or global background services.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_orchestrator_extension.py
scripts/check-pi-config.sh
```

**Expected result:** The extension is loadable by Pi config checks and statically demonstrates the required startup/shutdown/tool-gating behavior.

### Task 7: Runner status gateway and TUI visibility [Depends on: Tasks 4, 6]

**Context:** Monitoring must be visible in the TUI and available outside the TUI. `ticket_gateway runner_status` should become the stable structured model-facing status surface, while the extension renders a compact human view.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/gateway.py`
- Modify: `pi/agent/extensions/ticket-gateway.ts`
- Modify: `pi/agent/extensions/orchestrator-service.ts`
- Modify: `tests/test_ticket_gateway.py`
- Create or modify: `tests/test_runner_visibility.py`

**Steps:**
1. Write tests where `ticket_gateway({operation: "runner_status"})` returns service status, lease/drain state, active runs, budget, heartbeat, and safe redacted service metadata.
2. Update gateway runner status to prefer the REST client when a service is running and return clear `service: absent` state when not.
3. Update TypeScript summary rendering to include `running|paused|draining`, active count, and the first active work slug without dumping large payloads into chat.
4. Add or update the TUI widget/status renderer to show active work slug, model/thinking, context percent when known, and cost when known.
5. Keep Archimedes/footer integration DRY: do not replace Archimedes footer unless a specific conflict is observed.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_ticket_gateway.py tests/test_runner_visibility.py
```

**Expected result:** Both the model-facing gateway and TUI-facing extension expose the same service-backed runner state.

### Task 8: Budget, context, and cost accounting hardening [Depends on: Tasks 3, 7]

**Context:** The service should optimize token/cost efficiency and avoid uncontrolled spending. Existing routing/metrics should remain the source of policy; the service should enforce configured limits and surface cost/context state.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/runner_scheduler.py`
- Modify: `pi/agent/bin/agnt_lib/runner_protocol.py`
- Modify: `pi/agent/bin/agnt_lib/metrics.py` if additional summarization helpers are needed
- Modify: `pi/agent/bin/agnt_lib/routing.py` only if a policy hook is missing
- Create: `tests/test_runner_budget.py`

**Steps:**
1. Write tests for budget state normalization, dispatch refusal when budget is exhausted, warning state when usage is unknown, and surfaced cost/context values from fake run results or metrics.
2. Define a minimal local budget config in runner state/config: default safe mode should expose `limitsEnforced=false` until explicit limits are configured, but the service must still report unknown cost clearly.
3. Add support for configured per-session or per-run soft limits where data is available. Dispatch should pause or block with a durable Beads decision when an enforced limit would be exceeded.
4. Ensure selected model/thinking remains policy-selected by `agnt` routing; no direct service-side model overrides.
5. Surface context usage when worker/session metrics are available; otherwise report `unknown` rather than inventing values.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_runner_budget.py tests/test_runner_scheduler.py tests/test_ticket_gateway.py
```

**Expected result:** The runner status honestly reports cost/context state, and enforced budget limits prevent new dispatch without killing active work.

### Task 9: Documentation, evals, and command references [Depends on: Tasks 1-8]

**Context:** User-visible docs must describe the new service boundary and replace the old “no service yet” decision. Evals should catch regression to a raw main-thread implementation path.

**Files:**
- Create: `docs/RUNNER-SERVICE.md`
- Modify: `docs/ORCHESTRATION-LOOP.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/RUN-ARTIFACTS.md` if new service refs appear in run artifacts
- Modify: `README.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/agent/AGENTS.md` if orchestrator-only guidance changes
- Modify or create eval fixtures under `pi/agent/evals/`

**Steps:**
1. Document the REST service lifecycle, state files, API, singleton semantics, drain behavior, startup health gate, and security model.
2. Update old docs that say there is no service/daemon yet. Use precise wording: project-local runner service managed by `pi`/`agnt`, not installed global daemon or launch agent.
3. Document operator commands and expected startup flow.
4. Add/adjust evals so role/context guidance says the main thread is orchestrator-only and durable implementation should go through Beads/runner, not raw tools.
5. Keep README concise and link to detailed docs.

**Focused verification:**
```bash
rg -n "no installed service yet|not an installed service|gated command loop plus explicit project-local runner" docs README.md pi/agent/bin/README.md || true
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

**Expected result:** Documentation reflects the implemented service boundary and evals pass with orchestrator-only guidance.

### Task 10: End-to-end controlled soak and closeout checks [Depends on: Tasks 1-9]

**Context:** The target is production-ready for one user. After unit/docs/eval checks pass, run a controlled local soak before considering the work complete.

**Files:**
- Create: `.pi/plans/2026-07-09-runner-service-soak.md` or a date-adjusted soak record
- Modify: docs only if soak reveals behavior gaps
- No tracked runtime `.pi/runner/` or `.pi/runs/` artifacts should be committed

**Steps:**
1. Start from a clean working tree or documented feature branch/worktree.
2. Run `agnt doctor --profile orchestrator-startup --json` and record whether warnings are fixed or acknowledged.
3. Start the service with `agnt work daemon start --json --concurrency 1`.
4. Run `agnt work runner status --json` and `ticket_gateway runner_status` from Pi to verify client/gateway views.
5. Use dry-run queue processing first: `agnt work runner tick --dry-run --json`.
6. If safe ready work exists, run a limited live dispatch with no auto-close unless closeout checks are explicitly satisfied.
7. Exit Pi and verify the service drains: no new work accepted, active work finishes, daemon exits when the last lease is gone.
8. Run health and closeout checks.
9. Capture a retrospective/follow-up bead for any remaining production hardening.

**Focused verification:**
```bash
pi/agent/bin/agnt doctor --profile orchestrator-startup --json
pi/agent/bin/agnt work daemon start --json --concurrency 1
pi/agent/bin/agnt work runner status --json
pi/agent/bin/agnt work runner tick --dry-run --json --limit 1
pi/agent/bin/agnt work health --json
pi/agent/bin/agnt work daemon stop --json --drain
```

**Expected result:** Service can start, report, dry-run schedule, drain, and stop cleanly without committing runtime state.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt_lib/runner.py` | Tasks 2, 3 | Task 3 depends on Task 2 and should preserve compatibility wrappers/tests. |
| `pi/agent/bin/agnt_lib/work.py` | Task 4 plus possible docs/eval updates | Task 4 owns CLI behavior; later tasks only document/use it. |
| `pi/agent/bin/agnt_lib/doctor.py` | Task 5 | Isolated; Task 6 consumes the new profile. |
| `pi/agent/extensions/orchestrator-service.ts` | Tasks 6, 7 | Task 7 depends on Task 6 and only extends status rendering. |
| `pi/agent/bin/agnt_lib/gateway.py` | Task 7 | Wait until client boundary exists in Task 4. |
| Docs and command README | Tasks 4, 5, 9 | Prefer minimal command docs in earlier tasks; Task 9 performs final alignment. |

## Suggested Beads Breakdown

Do not create these beads without explicit implementation/work-graph approval. This table is ready to convert into an epic with child tasks.

| Bead title | Type | Depends on | Suggested metadata/action |
|---|---|---|---|
| Epic: Project-local runner service and orchestrator-only Pi startup | epic | — | Tracks full plan. |
| Define runner protocol and runtime state contracts | task | epic | `plan`/`implement`, write set: protocol/tests/gitignore. |
| Implement loopback runner service core | task | protocol | `implement`, write set: `runner_service.py`, `runner.py`, tests. |
| Implement scheduler/executor pool hardening | task | service core | `implement`, write set: scheduler/runner/health/tests. |
| Convert runner CLI to daemon lifecycle plus REST client | task | service+scheduler | `implement`, write set: `work.py`, `runner_client.py`, tests/docs. |
| Add startup health profile and intent acknowledgements | task | epic | `implement`, write set: doctor/startup policy/tests. |
| Add orchestrator-only Pi extension | task | CLI+startup profile | `implement`, write set: extension/settings/tests. |
| Surface service-backed runner status in gateway/TUI | task | extension+client | `implement`, write set: gateway/extensions/tests. |
| Enforce/report budget, context, and cost state | task | scheduler+visibility | `implement`, write set: budget/metrics/tests. |
| Update docs and evals for service boundary | task | implementation tasks | `finish`/`docs`, write set: docs/readmes/evals. |
| Run controlled single-user production soak | task | all implementation/docs | `verify`, write set: soak record only. |

## Peer Review Notes

This plan is high-impact and touches startup, service lifecycle, and tool policy. Before implementation, use at least one read-only peer review focused on missing failure modes and one focused on Pi extension/API correctness, for example:

```bash
~/.pi/agent/bin/agnt invoke --task review olla-local/qwen3:8b .pi/plans/2026-07-09-project-local-runner-service-plan.md
~/.pi/agent/bin/agnt invoke --task review openai-codex/gpt-5.4-mini .pi/plans/2026-07-09-project-local-runner-service-plan.md
```

## Implementation Approval Boundary

This plan does not itself approve implementation, service startup, Beads mutation, deployment to live `~/.pi`, or any background installation. Implementation should begin only after an explicit implementation request or approved Beads work item. Service installation as a host-level launch agent remains out of scope and would require a separate approval.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-09-project-local-runner-service-plan.md` (verified with `test -f`)
Recommended next skill: `test-driven-development` for behavior changes; `verification-before-completion` before claiming completion.
