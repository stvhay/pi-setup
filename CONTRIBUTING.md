# Contributing

## Workflow

Every meaningful change follows this process:

1. Use Beads (`bd`/`beads`) for persistent work tracking. Start with `bd ready`, inspect work with `bd show <id>`, and claim active work with `bd update <id> --claim`.
2. Use `/skill:brainstorming` for non-trivial design choices.
3. Use `/skill:writing-plans` to create an implementation plan under `.pi/plans/`.
4. Implement in small, reviewable steps.
5. Use `/skill:verification-before-completion` before claiming done.
6. Use `/skill:documentation-standards` to validate docs when behavior, APIs, architecture, or workflows change.
7. Use `/skill:requesting-code-review` for non-trivial diffs.
8. Use `/skill:finishing-a-development-branch` for branch/project readiness before PR/merge or local completion.

GitHub issues may be used later through an adapter/export workflow, but Beads is the canonical agent-facing work graph.

## Test Commands

```bash
# layout and shell checks
scripts/check-pi-config.sh
bash -n scripts/*.sh

# unit tests for agnt/agent-instructions internals
.venv/bin/python -m pytest tests/

# deterministic agnt evals (no model calls)
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke

# workflow compliance checks (runs real models)
./scripts/eval-workflow-compliance.sh
```

## Environment

This project uses direnv + Nix. After cloning:

```bash
direnv allow
```

The committed `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/`.
Local-only snippets can go in `.envrc.local.d/`, which is gitignored.

## Code of Conduct

Be kind, be constructive, and assume good intent.
