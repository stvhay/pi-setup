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

## Agent quick reference

```bash
bd prime              # dynamic Beads workflow context
bd status             # project work graph summary
bd ready              # unblocked work
bd show <id>          # inspect a bead
bd update <id> --claim
bd close <id> --reason "completed with verification"
bd bootstrap --dry-run --json
```

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
