# Beads work graph for pi-setup

This repository uses **Beads** (`bd`/`beads`) as the canonical agent-facing work
graph. Beads stores work items and dependencies; larger plans stay under
`.pi/plans/`, and per-run invocation/result artifacts stay under `.pi/runs/`.

## Tracked vs. local state

Tracked portable files:

- `.beads/README.md`
- `.beads/config.yaml`
- `.beads/metadata.json`
- `.beads/issues.jsonl`
- `.beads/.gitignore`

Local/runtime files are ignored by `.beads/.gitignore`, including the embedded
Dolt database, locks, export state, and interaction logs.

## Fresh checkout

CI pins Beads 1.1.0 and verifies that a temporary checkout can import the tracked
JSONL export and query the resulting work graph. Bootstrap a new local checkout
with:

```bash
bd bootstrap --yes
```

## Agent quick reference

```bash
bd prime              # dynamic Beads workflow context
bd status             # project work graph summary
bd ready              # unblocked work
bd show <id>          # inspect a bead
bd update <id> --claim
bd close <id> --reason "completed with verification"
```

## Worktrees and lifecycle

- Linked Git worktrees resolve to the main repository's `.beads/` workspace.
  Treat that graph as shared state; do not initialize or copy another graph into
  each worktree.
- Retry failed execution on the same Bead with a new run id. Inspect current
  status and dependencies first, append new evidence, and never close from a
  failed run.
- Reopen an existing Bead only when its original scope and acceptance criteria
  still describe the work. Otherwise create a replacement and mark the old Bead
  superseded with `bd supersede <old> --with=<new>`.
- Never reopen a rejected or cancelled human decision to authorize new action;
  create a new decision with current scope and consequences.

## Safety policy

- Querying beads is read-only and normally allowed.
- Creating, claiming, commenting, or closing beads is normal local state
  mutation for approved work.
- Deleting beads, changing remotes, rewriting/force-syncing Dolt history, or
  installing Beads hooks requires explicit approval.
- Hooks were intentionally not installed during setup.
- `export.git-add` is disabled so Beads does not silently stage files.

GitHub issues, if used later, should be an adapter/export integration rather
than a second agent-facing source of truth.
