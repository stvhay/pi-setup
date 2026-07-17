# Project Instructions

## Workflow

- Use Pi skills for design, planning, verification, review, documentation, and branch finishing.
- Keep implementation plans under `.pi/plans/`.
- Use Beads (`bd`/`beads`) for persistent agent-facing work tracking. Require a Bead before every code-changing task begins.
- Work directly in the current Pi session by default; select runner/run-artifact orchestration explicitly when useful.
- Treat GitHub issues as optional external adapters/exports, not a second source of truth.
- Do not push, merge, delete branches, remove worktrees, delete beads, change Beads remotes/history, or install hooks without explicit approval.

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
