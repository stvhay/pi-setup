# Orchestration Loop Decision

**Date:** 2026-06-27
**Status:** Implemented as gated command loop; no always-on daemon yet

## Context

The target architecture is:

```text
Beads work graph -> invocation artifact -> worker run -> result artifact -> bead transition
```

The repository now has the pieces needed for a production-safe manual/gated
loop:

- Beads is the canonical work graph.
- `agnt action` renders action semantics.
- `agnt runs` creates, invokes, validates, and updates run artifacts.
- `agnt work` plans, starts, runs, finishes, and optionally mutates Beads.

## Decision

Use a **gated command loop** now. Do not add an always-on daemon yet.

The production path is:

```bash
bd ready
agnt work plan <bead-id> --action <action> --target <ref> --dry-run
agnt work run <bead-id> --action <action> --target <ref> --model <provider/model> --claim --close-bead
```

`agnt work run` is the end-to-end command. It:

1. reads the bead;
2. selects/renders an action template;
3. creates `.pi/runs/<run-id>/invocation.yaml` and `result.yaml`;
4. optionally claims the bead with `--claim`;
5. invokes a worker from the invocation artifact;
6. writes prompt/response/stderr/metrics artifacts;
7. updates `result.yaml`;
8. optionally closes the bead with `--close-bead` if invocation succeeds,
   result evidence is present, and follow-up ids resolve to Beads.

## Safety gates

- `agnt work plan` is dry-run only.
- `agnt work start` writes run artifacts but mutates Beads only with `--claim`.
- `agnt work run` mutates Beads only with `--claim` / `--close-bead`.
- `agnt work finish` closes a bead only with `--close-bead`, status
  `succeeded`, non-empty evidence, and reconciled follow-up bead ids.
- `agnt work audit` checks that an empty queue is not hiding documented
  production-readiness or remaining-work signals.
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

Future hardening may add explicit idempotency keys or duplicate-run detection,
but the current design is safe because it does not hide retries or overwrite
prior evidence by default.

## Failure states

Workers report through `result.yaml` statuses:

- `succeeded`
- `failed`
- `blocked`
- `needs-human`
- `superseded`

A failed worker run does not close the bead. The operator/agent should inspect
`result.yaml`, add follow-up beads if needed, or rerun with a new run id.
Succeeded runs also do not close Beads unless they include evidence and every
`followUps` id resolves to an existing Beads item.

## Why no daemon yet

An always-on daemon would need additional policy for:

- automatic model selection and budget control;
- approval gates for write/external effects;
- worktree isolation for mutating tasks;
- retry limits and idempotency keys;
- failure escalation and notification;
- concurrent worker locking.

Those concerns should be designed and tested after the gated command loop has
real usage evidence.
