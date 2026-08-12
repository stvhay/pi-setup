# Project Instructions

## Workflow

- Use Pi skills for design, planning, verification, review, documentation, and branch finishing.
- Keep implementation plans under `.pi/plans/`.
- Use Beads (`bd`/`beads`) for persistent agent-facing work tracking. Require a Bead before every code-changing task begins.
- Work directly in the current Pi session by default; select run-artifact orchestration explicitly when useful.
- Treat GitHub issues as optional external adapters/exports, not a second source of truth.
- Unless explicitly narrowed, implementation approval includes staging and one local atomic commit of task-owned changes; use the shared development completion contract before closeout.
- Initial implementation approval may preauthorize exact reversible local Git setup and cleanup: named task branches/worktrees, post-integration removal, and staged deletion of tracked/config-controlled assets. Before cleanup or deletion, show exact paths/branches and commit-SHA recovery sources. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs, remote deletion, force/reset/clean, or history rewrite.
- Outside that exact initial scope, branch/worktree deletion requires explicit approval. Do not push, merge, force/reset/clean, delete beads, change Beads remotes/history, or install hooks without explicit approval. Remote deletion and history rewrite remain explicitly gated.

## Verification

Document project test/lint/typecheck commands here.

```bash
# examples; replace with project commands
<test command>
<lint command>
```

## Environment

This project uses direnv + Nix:

```bash
direnv allow
```

The `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/` and `.envrc.local.d/`.

## Documentation

Keep README and relevant docs/SPEC.md files aligned with user-visible and architectural changes.
