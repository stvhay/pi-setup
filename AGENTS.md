# Project Instructions

## Workflow

- Use Pi skills for design, planning, verification, review, docs, and branch finishing.
- Keep implementation plans under `.pi/plans/`.
- Use Beads (`bd`/`beads`) as the canonical agent-facing work graph. Run `bd prime` for workflow context, `bd ready` for unblocked work, and `bd show <id>` to inspect a bead.
- GitHub issues, if used, are an external adapter/export surface rather than a second source of truth for agents.
- With explicit approval for an implementation, agents may commit changes in this repository.
- Do not push, merge, delete branches, rewrite history, remove worktrees, delete beads, change Beads remotes, rewrite Beads/Dolt history, or install Beads hooks without explicit approval.

## Repository and deployment policy

This repository is the source of truth for reusable Pi configuration:

- `pi/` is tracked directly in this repository and is the deployable config source.
- Live `~/.pi` is runtime/deployed state, not the source of truth.

When changing Pi config:

1. Edit files under tracked `pi/`.
2. Verify with the project checks.
3. Deploy to `~/.pi` only when requested or needed for verification, using `scripts/bootstrap-pi-config.sh --apply`.
4. Never commit runtime secrets, sessions, caches, onboarding state, trust state, or API keys.

Track `flake.lock` for reproducible Nix/direnv environments.

## Verification

Document project test/lint/typecheck commands here.

Current known commands:

```bash
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
```

The `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/` and `.envrc.local.d/`.

## Documentation

Keep README and relevant docs/SPEC.md files aligned with user-visible and architectural changes.
