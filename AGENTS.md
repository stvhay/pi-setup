# Project Instructions

## Workflow

- Use Pi skills for design, planning, verification, review, docs, and branch finishing.
- Keep implementation plans under `.pi/plans/`.
- Use Beads (`bd`/`beads`) as the canonical agent-facing work graph. Every code-changing task must have a Bead before edits begin. Run `bd prime` for workflow context, `bd ready` for unblocked work, and `bd show <id>` to inspect a bead.
- Work directly in the current Pi session by default. The project-local runner, run artifacts, and orchestrated worktrees are optional paths selected explicitly for work that benefits from them.
- GitHub issues, if used, are an external adapter/export surface rather than a second source of truth for agents.
- Unless explicitly narrowed, implementation approval includes staging and one local atomic commit of task-owned changes; use the shared development completion contract before closeout.
- Beads messages about git operations describe Beads' internal sync mechanism, not agent authority for normal repository git commands.
- Do not push, merge, delete branches, rewrite history, remove worktrees, delete beads, change Beads remotes, rewrite Beads/Dolt history, or install Beads hooks without explicit approval.

## Repository and deployment policy

This repository is the source of truth for reusable Pi configuration:

- `pi/` is tracked directly in this repository and is the deployable config source.
- Live `~/.pi` is runtime/deployed state, not the source of truth.

When changing Pi config:

1. Edit files under tracked `pi/`.
2. Verify with the project checks.
3. Deploy to `~/.pi` only when requested or needed for verification, using `scripts/update-pi-config.sh`.
4. Never commit runtime secrets, sessions, caches, onboarding state, trust state, or API keys.

Track `flake.lock` for reproducible Nix/direnv environments.

## Verification

Current known commands:

```bash
# locked Node dependencies for extension tests
npm ci --ignore-scripts

# layout and shell checks
scripts/check-pi-config.sh
bash -n scripts/*.sh

# deterministic Python checks (also enforced in .github/workflows/ci.yml)
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/

# deterministic agnt evals (no model calls)
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke

# workflow compliance checks (runs real models)
./scripts/eval-workflow-compliance.sh
```

## Environment

This project uses direnv + Nix:

```bash
direnv allow
npm ci --ignore-scripts
```

The `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/` and `.envrc.local.d/`.

## Documentation

Keep README and relevant docs/SPEC.md files aligned with user-visible and architectural changes.
