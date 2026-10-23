# Project Instructions

## Workflow

- Use Pi skills: design/planning/verification/review/docs/branch finishing. Implementation plans: `.pi/plans/`.
- Beads (`bd`/`beads`): canonical work graph; each code-changing task needs a Bead before edits. Run `bd prime`, `bd ready`, `bd show <id>`.
- Default to direct current-session work; explicitly opt into beneficial run artifacts/orchestrated worktrees. GitHub issues: external adapter/export, never agent truth.
- Unless explicitly narrowed, implementation approval includes staging and one local atomic commit of task-owned changes; follow the shared development completion contract before closeout.
- Initial implementation approval may preauthorize exact reversible local Git setup and cleanup: named task branches/worktrees, post-integration removal, and staged tracked/config-controlled deletions. Before cleanup/deletion, show exact paths/branches and commit-SHA recovery sources. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs/deletion, force/reset/clean, or history rewrite.
- Initial implementation approval may preauthorize one exact local integration via `agnt work integrate`, naming target checkout/branch, expected target HEAD, and source commit SHA. It serializes the target, rechecks scope under lock, aborts conflicts, and stops on divergence; alternatives need explicit approval.
- Initial implementation approval may preauthorize deployment to verified local-live and explicitly designated test/staging environments: one single-use action binding Bead, source-selection rule, resolved target identity, exact preview/effect bounds, verification, rollback, and stop conditions. Production, unknown/mismatched targets, secrets changes, destructive rollback, or scope/preview changes need new explicit approval; rejection/cancellation/timeout fails closed.
- Initial implementation approval may preauthorize one ordinary branch push after successful Bead closeout, binding exact remote and branch identity, approved base SHA, bounded candidate-selection rule, expected remote state, final gates, and fail-closed checks. First attempt consumes authority. Protected or production branch pushes, PR actions, force, tags, releases, merges, deletion, and history rewrite are excluded.
- Beads sync messages grant no repository Git authority. Outside exact initial scope, push, branch/worktree deletion, local merge, deployment need explicit approval. Also require explicit approval to merge outside guarded integration, deploy outside verified non-production boundaries, force/reset/clean, delete Beads, change Beads remotes, rewrite Beads/Dolt history, or install Beads hooks. Remote deletion/history rewrite remain explicitly gated.

## Repository

Reusable Pi config source of truth: tracked repo `pi/` (deployable). Live `~/.pi` is runtime/deployed, not source.

Pi config changes:
1. Edit tracked `pi/`; run project checks.
2. Deploy verified local-live `~/.pi` only with initial/later approval naming that exact deployment. Use `scripts/update-pi-config.sh`: first dry-run/verify, retain rollback evidence, stop on canonical source/destination mismatch.
3. Never commit runtime secrets, sessions, caches, onboarding/trust state, or API keys.

Deployment-only: follow `pi/README.md#deployment-evidence-and-recovery`; reuse verified source, not full tests. Track `flake.lock` (reproducible Nix/direnv).

## Dependency upgrade policy

- Before adapting/verifying patches, upgrade plugins and direct/transitive runtime/development deps to latest stable—not just top-level/range-allowed versions.
- Check upstream constraints; refresh locks deliberately. Never retain old dependencies just for patches, migration avoidance, or unchanged upstream pins. Resolve conflicts; if latest stable cannot form a working supported graph, explain the specific conflict and get an explicit user-approved exception: version, reason, revisit condition.
- Keep exact verified versions, integrity checks and locks for reproducibility, not stale-dependency permission. Preserve explicitly intentional rolling sources; prereleases need separate agreement.
- Port/retire patches with equivalent contract tests. Verify actual fresh/reused installed dependencies, audits, projections, behavior/privacy tests. Fork locks alone do not prove delivery; never force overrides just to silence audits.
- Separately report plugin currency, dependency currency/security exceptions, live deployment. Unapproved stale-dependency exceptions block completion. This grants no push/merge/credential-change/deployment authority.

## Verification

Deterministic Python (also CI); deterministic no-model evals.

```bash
npm ci --ignore-scripts
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

Manual behavioral canary (real models, not a routine completion gate): `scripts/eval-workflow-compliance.sh --skill-mode candidate` only if user requests it or agent recommends it for a specific behavior question routine telemetry cannot answer.

## Setup

Direnv/Nix: `direnv allow`, then `npm ci --ignore-scripts`. `.envrc` loads `flake.nix`, `.envrc.d/` and `.envrc.local.d/` snippets.

Sync README and relevant docs/SPEC.md for user-visible/architectural changes.
