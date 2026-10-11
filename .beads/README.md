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
Dolt database, locks, export state, and interaction logs. Native `export.auto`
is throttled by `export.interval` (currently 60s), so rapid mutations may leave
`issues.jsonl` stale. `export.git-add` remains disabled. Direct closeout explicitly
exports with `bd export --readonly`, verifies canonical target closure parity,
and commits portable state before handoff. Dolt is authoritative; JSONL is
interchange, not a full history backup or remote sync mechanism.

Pi is a custom lifecycle integration, not a built-in `bd setup` recipe. The tested
profile is Beads **1.3.1**, embedded Dolt, no automatic hooks or Git operations,
and explicit portable-state boundaries. Auto-export may be disabled in another
project without changing that boundary.

## Fresh checkout

CI pins Beads 1.3.1 and verifies that a temporary checkout can import the tracked
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
agnt work direct-start <id> --claim
# Implement, verify, and commit task-owned changes first.
agnt work direct-closeout <id> --outcome success --reason "completed with verification"
# Then call handoff_bead (no target) in Pi.
```

Raw `bd update --claim` and `bd close` are low-level Beads transitions, not
substitutes for Pi session linking and closeout. Prime's “stealth/no git ops”
wording concerns Beads sync; project Git authority still governs local commits.

## Audit and diagnostics

Beads 1.3.1's optional interaction sidecar defaults off; it is incomplete and
non-authoritative. With audit enabled, explicit status updates and closure emit
rows, but claim and the `reopen` command do not. Current Pi handoff writes no
reopen transition. A historical reopen-shaped row alone does not identify its
caller. Dolt retains canonical history independently.

This repository ignores runtime sidecars. Existing projects that track
`.beads/interactions.jsonl` must preserve their history: direct closeout accepts
unchanged committed history plus exact append-only closure rows for the target
and reason. Dirty reopen, assignment, foreign, malformed or tampered rows are
not adopted. Stop and ask the originating transition owner to verify and commit
those appends at that boundary; never delete, untrack, or silently sweep them
into a later closeout.

`agnt doctor --json` checks the supported version and JSON capability/result,
not exit status alone. Embedded full doctor is unsupported: health remains
unverified/degraded even when `bd list` and supported conventions checks pass.
Those checks prove queryability and lint/stale/orphans only, not full database
integrity. Never follow diagnostic reinitialization/migration hints automatically.

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
