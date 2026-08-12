# Project Instructions

## Workflow

- Use Pi skills for design, planning, verification, review, documentation, and branch finishing.
- Keep implementation plans under `.pi/plans/`.
- Use Beads (`bd`/`beads`) for persistent agent-facing work tracking. Require a Bead before every code-changing task begins.
- Work directly in the current Pi session by default; select run-artifact orchestration explicitly when useful.
- Treat GitHub issues as optional external adapters/exports, not a second source of truth.
- Unless explicitly narrowed, implementation approval includes staging and one local atomic commit of task-owned changes; use the shared development completion contract before closeout.
- Initial implementation approval may preauthorize exact reversible local Git setup and cleanup: named task branches/worktrees, post-integration removal, and staged deletion of tracked/config-controlled assets. Before cleanup or deletion, show exact paths/branches and commit-SHA recovery sources. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs, remote deletion, force/reset/clean, or history rewrite.
- Initial implementation approval may preauthorize one exact local integration through `agnt work integrate` when it names target checkout/branch, expected target HEAD, and source commit SHA. The helper serializes the target, rechecks scope under lock, aborts conflicts, and stops on divergence; any alternate integration strategy requires explicit approval.
- Initial implementation approval may preauthorize deployment to verified local-live and explicitly designated test/staging environments as one single-use action when it binds the Bead, source-selection rule, resolved target identity, exact preview and effect bounds, verification, rollback, and stop conditions. Production, unknown/mismatched targets, secrets changes, destructive rollback, and scope/preview changes require new explicit approval; rejection, cancellation, or timeout fails closed.
- Initial implementation approval may preauthorize one ordinary branch push after successful Bead closeout when it binds exact remote and branch identity, approved base SHA, bounded candidate-selection rule, expected remote state, final gates, and fail-closed checks. First push attempt consumes authority. Protected or production branch pushes, PR actions, force, tags, releases, merges, deletion, and history rewrite remain outside that authority.
- Outside that exact initial scope, push, branch/worktree deletion, local merge, and deployment require explicit approval. Do not merge outside guarded integration, deploy outside verified non-production boundaries, force/reset/clean, delete beads, change Beads remotes/history, or install hooks without explicit approval. Remote deletion and history rewrite remain explicitly gated.

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
