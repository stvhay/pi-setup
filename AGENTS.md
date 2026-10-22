# Project Instructions

## Workflow

- Use Pi skills for design, planning, verification, review, docs, and branch finishing.
- Keep implementation plans under `.pi/plans/`.
- Use Beads (`bd`/`beads`) as the canonical agent-facing work graph. Every code-changing task must have a Bead before edits begin. Run `bd prime` for workflow context, `bd ready` for unblocked work, and `bd show <id>` to inspect a bead.
- Work directly in the current Pi session by default. Run artifacts and orchestrated worktrees are optional paths selected explicitly for work that benefits from them.
- GitHub issues, if used, are an external adapter/export surface rather than a second source of truth for agents.
- Unless explicitly narrowed, implementation approval includes staging and one local atomic commit of task-owned changes; use the shared development completion contract before closeout.
- Initial implementation approval may preauthorize exact reversible local Git setup and cleanup: named task branches/worktrees, post-integration removal, and staged deletion of tracked/config-controlled assets. Before cleanup or deletion, show exact paths/branches and commit-SHA recovery sources. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs, remote deletion, force/reset/clean, or history rewrite.
- Initial implementation approval may preauthorize one exact local integration through `agnt work integrate` when it names target checkout/branch, expected target HEAD, and source commit SHA. The helper serializes the target, rechecks scope under lock, aborts conflicts, and stops on divergence; any alternate integration strategy requires explicit approval.
- Initial implementation approval may preauthorize deployment to verified local-live and explicitly designated test/staging environments as one single-use action when it binds the Bead, source-selection rule, resolved target identity, exact preview and effect bounds, verification, rollback, and stop conditions. Production, unknown/mismatched targets, secrets changes, destructive rollback, and scope/preview changes require new explicit approval; rejection, cancellation, or timeout fails closed.
- Initial implementation approval may preauthorize one ordinary branch push after successful Bead closeout when it binds exact remote and branch identity, approved base SHA, bounded candidate-selection rule, expected remote state, final gates, and fail-closed checks. First push attempt consumes authority. Protected or production branch pushes, PR actions, force, tags, releases, merges, deletion, and history rewrite remain outside that authority.
- Beads messages about git operations describe Beads' internal sync mechanism, not agent authority for normal repository git commands.
- Outside that exact initial scope, push, branch/worktree deletion, local merge, and deployment require explicit approval. Do not merge outside guarded integration, deploy outside verified non-production boundaries, force/reset/clean, delete beads, change Beads remotes, rewrite Beads/Dolt history, or install Beads hooks without explicit approval. Remote deletion and history rewrite remain explicitly gated.

## Repository and deployment policy

This repository is the source of truth for reusable Pi configuration:

- `pi/` is tracked directly in this repository and is the deployable config source.
- Live `~/.pi` is runtime/deployed state, not the source of truth.

When changing Pi config:

1. Edit files under tracked `pi/`.
2. Verify with the project checks.
3. Deploy to verified local-live `~/.pi` only when the initial approved scope names that exact deployment or later approval does, using `scripts/update-pi-config.sh`; dry-run and verify first, retain rollback evidence, and stop if canonical source/destination identity differs.
4. Never commit runtime secrets, sessions, caches, onboarding state, trust state, or API keys.

Deployment-only: follow `pi/README.md#deployment-evidence-and-recovery`; reuse verified source, not full tests.

Track `flake.lock` for reproducible Nix/direnv environments.

## Dependency upgrade policy

- Upgrade dependencies first, then adapt and verify our patches against the updated dependency graph. Target the latest stable plugin releases and direct/transitive runtime and development dependencies, not merely the newest top-level plugin version or versions allowed by existing ranges.
- Inspect upstream constraints and refresh lockfiles deliberately. Do not retain older dependencies solely to preserve patches, avoid migration work, or inherit upstream pins unchanged. Resolve compatibility conflicts; if the latest stable versions cannot form a working supported graph, explain the specific conflict and obtain an explicit user-approved exception with the retained version, reason, and revisit condition.
- Keep exact versions, integrity checks, and lockfiles for reproducibility after selecting and verifying the updated graph. They record a tested result, not permission to leave dependencies stale. Preserve explicitly intentional rolling sources; prerelease adoption requires separate agreement.
- Port or retire patches with equivalent contract tests. Verify the actual resolved dependencies in both fresh and reused installation paths, plus audit results, package projections, and behavior/privacy tests. Updating a fork lockfile alone is not proof that installed plugins receive those dependencies; never force overrides merely to silence an audit.
- Report plugin currency, dependency currency/security exceptions, and live deployment status separately. Do not call an upgrade complete with unapproved stale-dependency exceptions. This policy does not grant push, merge, credential-change, or deployment authority.

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
.venv/bin/python -m pytest tests/ --durations=15

# deterministic agnt evals (no model calls)
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

Manual behavioral canary (runs real models; not a routine completion gate): run
`scripts/eval-workflow-compliance.sh --skill-mode candidate` only when user
requests it or the agent recommends it for a specific behavior question that
routine telemetry cannot answer.

## Environment

This project uses direnv + Nix:

```bash
direnv allow
npm ci --ignore-scripts
```

The `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/` and `.envrc.local.d/`.

## Documentation

Keep README and relevant docs/SPEC.md files aligned with user-visible and architectural changes.
