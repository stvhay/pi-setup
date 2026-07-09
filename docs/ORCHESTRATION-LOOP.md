# Orchestration Loop Decision

**Date:** 2026-06-27
**Status:** Implemented as gated command loop plus project-local singleton runner; no installed service/daemon yet

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
- `agnt work` plans, starts, runs, finishes, audits, checks health, manages the singleton runner, and creates maintenance checkpoint Beads only through explicit commands.

## Decision

Use a **gated command loop** and an explicit project-local singleton runner. Do not install an always-on service yet.

The manual production path is:

```bash
bd ready
agnt work tree --epic <epic-id> --json
agnt work plan <bead-id> --action <action> --target <ref> --dry-run
agnt work run <bead-id> --action <action> --target <ref> --claim --close-bead
```

The runner path is explicit and local:

```bash
agnt work runner status --json
agnt work runner tick --dry-run --json
agnt work loop --limit 1
```

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
- `agnt work finish` closes a bead only with `--close-bead`, status
  `succeeded`, non-empty evidence, passing health/closeout checks, resolved approval/decision refs, and reconciled follow-up bead ids.
- `agnt work health` checks run artifacts, Beads refs, approvals, decisions, stale sessions, stale runner locks, dirty current/epic worktrees, raw-tool bypass markers, and failed checks.
- `agnt work audit` checks that an empty queue is not hiding documented
  production-readiness or remaining-work signals.
- `agnt approvals` creates Beads-backed human decision records; timeout, reject, or cancel states leave visible blockers.
- Implementation dispatch requires approved metadata, write sets, closeout policy, and a clean non-main epic worktree.
- Remote/destructive git operations, deployments, hook installs, Beads deletion,
  Beads remote changes, and Dolt history rewrites still require explicit
  approval.

## Idempotency model

Current idempotency is artifact-based:

- every run has a unique run id;
- repeated attempts create separate run bundles unless `--id` is explicitly
  reused;
- terminal result status is recorded in `result.yaml`;
- Beads preserve state transitions and close reasons.

Future hardening may add explicit idempotency keys, duplicate-run detection, and stronger budget enforcement. The current design is safe because it does not hide retries or overwrite prior evidence by default, and the runner uses a project-local singleton lock under `.pi/runner/`.

## Failure states

Workers report through `result.yaml` statuses:

- `succeeded`
- `failed`
- `blocked`
- `needs-human`
- `superseded`

A failed worker run does not close the bead. The operator/agent should inspect
`result.yaml`, add follow-up beads if needed, or rerun with a new run id.
Succeeded runs also do not close Beads unless they include evidence, every `followUps` id resolves to an existing Beads item, approval/decision refs are closed, and health/closeout checks pass. Observational-memory summaries can support context, but they do not satisfy closeout unless promoted into Beads or `.pi/runs` evidence.

## Runner and maintenance cadence

`agnt work runner tick` drains ready work through the same validators and run artifacts as manual dispatch. It records worker sessions by default, respects pause/resume state, refuses unsafe worktrees, creates durable blockers for invalid dispatch, and can create due maintenance checkpoint Beads when the queue is idle.

Maintenance cadence is derived from durable signals: closed implementation beads, commits since the last maintenance checkpoint, failed/blocked runs, human blockers, context-health warnings, health warnings/failures, stale artifacts, and recorded session volume. Use:

```bash
agnt work maintenance due --json
agnt work maintenance create-beads --dry-run --json
```

`create-beads` mutates Beads only with explicit `--apply`. Read-only maintenance review beads may be auto-created by the runner; simplification/refactor implementation beads are created with `approved: false` and remain human-gated.

## Why no installed service yet

An installed always-on service still needs additional policy for retry limits, budget enforcement, notification, production soak, and host lifecycle management. The project-local runner gives deterministic behavior without installing hooks, launch agents, or services.
