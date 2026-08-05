---
profile_version: 1
repository: https://github.com/danielcherubini/pi-archimedes
last_checked_utc: 2026-08-05T18:30:00Z
target_ref: v1.8.3
source_commit: 801397c052ea064fc237ff4e035c2a0910d391c8
status: current-for-target-ref
recheck_every_use:
  - permissions
  - fork-state
  - templates
  - branch-protection-and-ci
  - issue-requirements
source_files:
  - path: README.md
    sha256: c2fb4e255bf7dd6b7804a81fc96df8e3e7e367be53d1544980759ec3ad6912fe
  - path: AGENTS.md
    sha256: 2baf700cba85a48c252316c7cdea9b96339240b853997e2d22e7529359317a73
  - path: docs/plans/README.md
    sha256: b219dbfb0aa7a7778d0fb69bc3d28ad2401bddf5d307978adf213a2ae9eb39e3
  - path: package.json
    sha256: ce5f54ed0dd8894a8c858a0c9714cbb4251900e33526cff7376900c6342988fd
  - path: pnpm-workspace.yaml
    sha256: 1b6fb329ddb565dfe223fbe6e95e879ccae7b59ff22d9b826c1260096760abfc
  - path: packages/subagent/package.json
    sha256: 7f122c81fea5666d6e313abad0ad34505e51f772d5c60b790d503564544f1836
  - path: packages/subagent/README.md
    sha256: cb307c5fab87316bb22c9a144486b37c98c6c7215ea38e34eb3776115db2c832
  - path: .github/workflows/ci.yml
    sha256: c602b2e35ededfd4c934b2509eb5786755cca6be7e3c419b3f3e0909e11583e2
  - path: .github/workflows/release.yml
    sha256: 37f0eed57655922f66c5f75c1ee0d7f5402881ddfffe3326bad8d02543d388ec
  - path: packages/subagent/src/spawn.ts
    sha256: ec5492e224f5b90e88588745ec012368672c762ccc78ef2d524d02a30a323b59
  - path: packages/subagent/src/stream.ts
    sha256: 4a77b199a498a39385f64003a2fc6cff2c88f86a366ab7fadb74d8c7b1b392ff
  - path: packages/subagent/src/types.ts
    sha256: 63983d29f0a792cb13aaffefd353227bd2f62612eddb3fa3ac5fe2c34330a530
  - path: packages/subagent/src/execute.ts
    sha256: fb171ae4c86600976f4f4bbe5bac12aec82453a3fda080e1f3519c6e64cdb816
  - path: packages/subagent/src/handlers.test.ts
    sha256: 5ee597b74c1a2c5e20b72f7996786bb9dc91770b44ab52475c73d4052b9cdb06
---

# danielcherubini/pi-archimedes upstream profile

## Contribution workflow

- Default branch observed: `main`; target tag matched `origin/main` when checked.
- pnpm workspace; install with frozen lockfile and use package/workspace scripts.
- Non-trivial work requires a committed dated plan under `docs/plans/`, plan index updates, reviewer dispatch, and completion/move to `docs/plans/done/`.
- Commits should be logical and use repository conventional style.
- Required candidate checks: subagent/package TypeScript checks, all workspace typechecks, focused Vitest, full repository tests, and diff checks.
- No PR template or repository AI-contribution policy observed in checked sources.
- User permission observed 2026-08-05: pull-only upstream; fork required. Recheck every use.
- Release/publish workflow is tag-driven and publishes packages in dependency order; PR approval does not authorize release or publication.

## Policy findings

- License: no root/subagent package license field or root license file was observed at the target ref.
- CLA/DCO, contributor eligibility, commit signoff/signing, branch naming, and issue-first requirements: none observed in checked sources. Recheck repository settings and current GitHub metadata every use.
- Documentation: package API changes should update the relevant package README; non-trivial work must also maintain the plan index/status.
- Generated artifacts: `pnpm-lock.yaml` is tracked. No generated-source update rule was observed.

## Coding style

**Confidence:** high

- TypeScript workspace with explicit exported result/config types and additive optional compatibility fields.
- Existing architecture treats each worker as a fresh process and intentionally retains `pi --mode json --no-session -p`.
- Preserve process arguments, environment inheritance, Windows `process.execPath`/`windowsHide`, abort behavior, socket cleanup, progress shape, parallel result ordering, and cost/usage reporting.
- Tests use Vitest, focused synthetic process streams, and package-level typechecks.
- Plan and code commits are separate logical units when repository workflow requires it.

## PR implications

- Plan before implementation and keep plan index/status current.
- Public API additions should be minimal, additive, and documented.
- Test absence/invalid inputs, Windows spawn behavior, parallel ordering, abort/cleanup, and unchanged progress contracts.
- Use repository pnpm commands rather than generic npm invocations.
- Keep PR body focused on user-visible contract and verification; omit pi-setup local patch mechanics.
