# Project Instructions

Applies to maintaining this repository, not projects using the deployed configuration. Shared workflow, Beads, approval, Git, and handoff rules belong in `pi/agent/AGENTS.md` (deployed to `~/.pi/agent/AGENTS.md`). If shared instructions are not already loaded, read that tracked file; repository rules below add constraints, not authority.

## Repository

Reusable Pi config source of truth: tracked repo `pi/` (deployable). Live `~/.pi` is runtime/deployed, not source. Root `AGENTS.md` governs maintenance here; `pi/agent/AGENTS.md` contains cross-project guidance. Keep each rule with its owner rather than duplicating it.

Keep deterministic domain logic in `agnt_lib`; extensions own Pi lifecycle, UI, session, and provider integration; typed tools stay thin.

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
.venv/bin/python scripts/check-python-tests.py
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

Manual behavioral canary (real models, not a routine completion gate): `scripts/eval-workflow-compliance.sh --skill-mode candidate` only if user requests it or agent recommends it for a specific behavior question routine telemetry cannot answer.

## Setup

Direnv/Nix: `direnv allow`, then `npm ci --ignore-scripts`. `.envrc` loads `flake.nix`, `.envrc.d/` and `.envrc.local.d/` snippets.

Sync README and relevant docs/SPEC.md for user-visible/architectural changes.
