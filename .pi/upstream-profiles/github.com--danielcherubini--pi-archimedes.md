---
profile_version: 1
repository: https://github.com/danielcherubini/pi-archimedes
last_checked_utc: 2026-08-10T01:24:07Z
target_ref: v2.0.1
source_commit: bdfeea3ed77392a2d02617fa1e0d4aa5fd8317e3
status: current-for-target-ref
recheck_every_use:
  - permissions
  - fork-state
  - templates
  - branch-protection-and-ci
  - issue-requirements
source_files:
  - path: README.md
    sha256: f9d2101c4bc2962f5e227fb35272b82203af33aa44b793ee4665aef23c1bae07
  - path: AGENTS.md
    sha256: 2baf700cba85a48c252316c7cdea9b96339240b853997e2d22e7529359317a73
  - path: LICENSE
    sha256: 4a69dc29421e26d9c8e50a823a1255c64441020942d4d5d0ecbc2fec8ca0b823
  - path: docs/plans/README.md
    sha256: f7a465e02831bd08d8e98d5082b3026a92eeb160f8b5ef2ef08a88d9c3ba019c
  - path: package.json
    sha256: ce5f54ed0dd8894a8c858a0c9714cbb4251900e33526cff7376900c6342988fd
  - path: pnpm-workspace.yaml
    sha256: 1b6fb329ddb565dfe223fbe6e95e879ccae7b59ff22d9b826c1260096760abfc
  - path: packages/subagent/package.json
    sha256: aedd14a7e71ead7da47ff7ce23364c53d85e38295f9969e793f5199b3ee67cd9
  - path: packages/subagent/README.md
    sha256: 4594861f0c78f4588946387aae5ecad6b936cefddae4f3e74dcd0e39002c90b4
  - path: .github/workflows/ci.yml
    sha256: c602b2e35ededfd4c934b2509eb5786755cca6be7e3c419b3f3e0909e11583e2
  - path: .github/workflows/release.yml
    sha256: 37f0eed57655922f66c5f75c1ee0d7f5402881ddfffe3326bad8d02543d388ec
  - path: packages/subagent/src/compact.ts
    sha256: b691f6834ad3d541d83c28204bbb839351bcf572ac3eb320eab921fc9b743810
  - path: packages/subagent/src/expanded.ts
    sha256: f328a87bcf873c0be6905ad9422b2385f554532d29386c5c239e4593ebbc94f7
  - path: packages/subagent/src/handlers.ts
    sha256: 4a9ad5a5ab8733d85ea024868582778766374b5b487295b4f576c0d73f9d0f8e
  - path: packages/subagent/src/index.ts
    sha256: c630e5c5e31062a0ef0c377f1f292c434c809cefcb997830397397537f8efcaa
  - path: packages/subagent/src/spawn.ts
    sha256: ec5492e224f5b90e88588745ec012368672c762ccc78ef2d524d02a30a323b59
  - path: packages/subagent/src/stream.ts
    sha256: 578cefc6958cb38bd6516966dfe36cec97fea1b822796b1d1a0c3c19f08068ed
  - path: packages/subagent/src/types.ts
    sha256: 1a3bbc9079aa1f1e6b9a57ed14ffc7c252f9769de339b9c63e230cb5fc90d01e
  - path: packages/subagent/src/execute.ts
    sha256: fb171ae4c86600976f4f4bbe5bac12aec82453a3fda080e1f3519c6e64cdb816
  - path: packages/subagent/src/stream.test.ts
    sha256: 1873f6dd78ffb8abf950c34bda0835c5e79e17f67a76bc33c541e212748bc913
---

# danielcherubini/pi-archimedes upstream profile

## Contribution workflow

- Default branch: `main`; latest stable release `v2.0.1` resolves to `bdfeea3ed77392a2d02617fa1e0d4aa5fd8317e3`. The branch had advanced to `ee0ce51223a36b186143c780d8ce741188ac8038` only to archive plan 020 when checked.
- `v2.0.1` is published, non-draft, non-prerelease, and marked latest.
- pnpm 10 workspace; install with `corepack pnpm install --frozen-lockfile` and use package/workspace scripts.
- Non-trivial work requires a committed dated plan under `docs/plans/`, plan-index maintenance, reviewer dispatch, and completion under `docs/plans/done/`.
- Commits are logical and use repository conventional style.
- Required candidate checks: subagent/package TypeScript, all workspace typechecks, focused Vitest, full repository tests, and diff checks.
- No PR template, CONTRIBUTING file, CLA/DCO requirement, issue-first rule, or repository AI-contribution policy was observed at the target.
- User permission checked 2026-08-10: upstream repository is read-only; user fork `stvhay/pi-archimedes` grants ADMIN and its `main` now matches exact v2.0.1. Recheck before remote actions.
- Upstream `main` was unprotected and had zero open issues when checked. Fork draft CI remains a staging signal, not proof of upstream acceptance.
- Release/publish workflow is tag-driven and publishes packages in dependency order; PR approval does not authorize release or publication.

## Policy findings

- License: MIT `LICENSE` now exists at v2.0.1, resolving the old profile gap.
- Branch naming, commit signing, signoff, and contributor eligibility rules remain unspecified.
- Package interface changes should update `packages/subagent/README.md`; repository-level user-visible changes should align root `README.md`.
- `pnpm-lock.yaml` is tracked. No generated-source update rule was observed.
- README says Node.js >=24 while CI uses Node 22; verify both project-prescribed CI shape and the local Node 24 supported environment rather than silently rewriting guidance.

## Coding style

**Confidence:** high
**Evidence checked:** v2.0.1 source files listed above, current release metadata, CI/release workflows, and clean subagent baseline.

- TypeScript ESM with explicit exported result/config types and additive optional compatibility fields.
- Existing architecture runs each worker as a fresh `pi --mode json --no-session -p` child process.
- Preserve process arguments, environment inheritance, Windows `process.execPath`/`windowsHide`, abort behavior, socket cleanup, progress shape, parallel result ordering, model labels, child session correlation, and cost/usage reporting.
- Compact and expanded renderers both show `progress.model ?? result.model`; upstream already satisfies the model-label requirement for agentic execution and supplies the seam one-shot should reuse.
- Tests use Vitest, focused synthetic child streams, and package-level typechecks.
- Plan and implementation/documentation commits remain separate logical units when repository workflow requires them.

## Current baseline evidence

At exact v2.0.1 on 2026-08-09:

- `corepack pnpm install --frozen-lockfile` — PASS
- `corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit` — PASS
- `corepack pnpm --filter @pi-archimedes/subagent exec vitest run` — PASS, 54 tests
- Clean worktree after checks — PASS

## PR implications

- Fork-local drafts 1–3 now stage behaviorally rebuilt v2.0.1 candidates and remain OPEN+DRAFT without reviewer requests; no corresponding upstream PR exists.
- Public additions must remain minimal, additive, documented, and tested for invalid inputs, Windows spawn, ordering, abort/cleanup, model rendering, output/usage preservation, and progress compatibility.
- Upstream v2.0.1 already includes child session IDs and model labels; omit duplicate candidate code.
- Use repository pnpm commands and keep reviewer-facing PR prose free of pi-setup projection mechanics.
- Refresh this profile before any actual upstream draft creation because upstream `main` is ahead of v2.0.1.
