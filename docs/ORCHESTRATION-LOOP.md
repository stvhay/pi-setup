# Orchestration Loop Decision

**Date:** 2026-06-27
**Updated:** 2026-07-09
**Status:** Implemented as a Beads-first gated workflow with a project-local loopback runner service. The service is started or attached by `pi`/`agnt`; it is not a global daemon, launch agent, hook, or remote scheduler.

## Context

The target architecture is:

```text
Beads work graph -> invocation artifact -> worker run -> result artifact -> bead transition
```

The repository now has the pieces needed for a production-safe Beads-first loop:

- Beads is the canonical work graph for work, dependencies, blockers, approvals, closeout, and maintenance checkpoints.
- Archimedes/Pi todos and ask dialogs are live UX projections; durable decisions and outcomes must land in Beads or `.pi/runs`.
- `agnt action` renders action semantics.
- `agnt runs` creates, invokes, validates, and updates run artifacts.
- `agnt work` plans, starts, runs, finishes, audits, checks health, manages the project-local runner service, and creates maintenance checkpoint Beads only through explicit commands.
- The Pi orchestrator extension gates startup, narrows main-thread tools, attaches a service lease, displays status, and asks the service to drain on session shutdown.

## Decision

Use a **gated command workflow** backed by a **project-local loopback runner service**. The service creates an architectural boundary between the orchestrator/client main thread and worker execution without installing host-level background infrastructure.

Manual dispatch remains available and explicit:

```bash
bd ready
agnt work tree --epic <epic-id> --json
agnt work plan <bead-id> --action <action> --target <ref> --dry-run
agnt work run <bead-id> --action <action> --target <ref> --claim --close-bead
```

The service path is project-local and REST-mediated:

```bash
agnt doctor --profile orchestrator-startup --json
agnt work daemon status --json
agnt work daemon start --json --concurrency 1
agnt work runner status --json
agnt work runner tick --dry-run --json --limit 1
agnt work daemon stop --json --drain
```

`agnt work daemon start|stop|status` are the direct lifecycle commands. `agnt work runner status|pause|resume|tick` are clients of the running service; they do not mutate runner state through a second local path. `agnt work loop` is deprecated in favor of the service lifecycle.

`agnt work run` is the end-to-end command. It:

1. reads the bead;
2. validates `metadata.pi` and dispatch policy;
3. selects model and thinking level from routing policy;
4. creates `.pi/runs/<run-id>/invocation.yaml` and `result.yaml` with ticket, worktree, dispatch, session, memory, and todo-seed snapshots;
5. optionally claims the bead with `--claim`;
6. invokes a worker from the invocation artifact, recording a worker session when dispatched by the runner;
7. writes prompt/response/stderr/metrics/session artifacts;
8. updates `result.yaml` with evidence, approvals, decisions, health checks, closeout checks, follow-ups, and refs;
9. optionally closes the bead with `--close-bead` if invocation succeeds, evidence is present, approvals/decisions are resolved, checks pass, and follow-up ids resolve to Beads.

## Safety gates

- `agnt work plan` is dry-run only.
- `agnt work start` writes run artifacts but mutates Beads only with `--claim`.
- `agnt work run` mutates Beads only with `--claim` / `--close-bead`.
- `agnt work finish` closes a bead only with `--close-bead`, status `succeeded`, non-empty evidence, passing health/closeout checks, resolved approval/decision refs, and reconciled follow-up bead ids.
- `agnt work health` checks run artifacts, Beads refs, approvals, decisions, stale sessions, stale runner locks/heartbeats, active-run snapshots, dirty current/epic worktrees, raw-tool bypass markers, and failed checks.
- `agnt work audit` checks that an empty queue is not hiding documented production-readiness or remaining-work signals.
- `agnt approvals` creates Beads-backed human decision records; timeout, reject, or cancel states leave visible blockers.
- Implementation dispatch requires approved metadata, write sets, closeout policy, and a clean non-main epic worktree.
- The main Pi thread is orchestrator-only for durable work: status, planning, review, questions, approvals, and gateway operations are allowed; raw main-thread implementation paths are not the normal route.
- Remote/destructive git operations, deployments, hook installs, Beads deletion, Beads remote changes, and Dolt history rewrites still require explicit approval.

## Idempotency model

Current idempotency is artifact-based:

- every run has a unique run id;
- repeated attempts create separate run bundles unless `--id` is explicitly reused;
- terminal result status is recorded in `result.yaml`;
- Beads preserve state transitions and close reasons;
- `.pi/runner/active/<run-id>.json` snapshots expose active work and are cleaned up after terminal execution.

Future hardening may add explicit idempotency keys and duplicate-run detection. The current design is safe because it does not hide retries or overwrite prior evidence by default, and the runner uses a project-local singleton lock under `.pi/runner/`.

## Failure states

Workers report through `result.yaml` statuses:

- `succeeded`
- `failed`
- `blocked`
- `needs-human`
- `superseded`

A failed worker run does not close the bead. The operator/agent should inspect `result.yaml`, add follow-up beads if needed, or rerun with a new run id. Succeeded runs also do not close Beads unless they include evidence, every `followUps` id resolves to an existing Beads item, approval/decision refs are closed, and health/closeout checks pass. Observational-memory summaries can support context, but they do not satisfy closeout unless promoted into Beads or `.pi/runs` evidence.

## Runner service and maintenance cadence

The runner service schedules ready work through the same validators and run artifacts as manual dispatch. It records worker sessions by default, respects pause/resume/drain state, refuses unsafe worktrees, creates durable blockers for invalid dispatch or enforced budget limits, prevents duplicate active bead dispatch, serializes overlapping implementation write sets, and can create due maintenance checkpoint Beads when the queue is idle.

Maintenance cadence is derived from durable signals: closed implementation beads, commits since the last maintenance checkpoint, failed/blocked runs, human blockers, context-health warnings, health warnings/failures, stale artifacts, and recorded session volume. Use:

```bash
agnt work maintenance due --json
agnt work maintenance create-beads --dry-run --json
```

`create-beads` mutates Beads only with explicit `--apply`. Read-only maintenance review beads may be auto-created by the runner; simplification/refactor implementation beads are created with `approved: false` and remain human-gated.

## Service boundary rationale

The service provides production-grade single-user separation without broad host lifecycle commitments. It is project-local, authenticated on loopback, and stores pid/port/token/state under `.pi/runner/`. This yields deterministic scheduling and status visibility while preserving explicit gates and avoiding hidden startup behavior outside Pi/agnt.

Remaining expansion areas are deliberate future work: production soak evidence, notification policy, richer remote dashboard support, multi-project views, remote daemon streaming, and stronger host lifecycle management. See [Project-Local Runner Service](RUNNER-SERVICE.md) for operator details.
