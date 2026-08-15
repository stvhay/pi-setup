---
profile_version: 1
repository: https://github.com/danielcherubini/pi-archimedes
last_checked_utc: 2026-08-12T12:22:39Z
target_ref: main
source_commit: a2bd4d6041206e9f5c0b17168a9e41749c90409d
status: current-for-target-ref
result_port_status: proposed-unreleased
recheck_every_use:
  - permissions
  - fork-state
  - templates
  - branch-protection-and-ci
  - issue-requirements
source_files:
  - path: README.md
    sha256: 27f60b28d83e607b6c81c3fdb5e4bbe4ac78f4d5ee8f660f45e2eeecafccddd0
  - path: AGENTS.md
    sha256: 27ab8e396b6762270dba593b56d8301a20536e050aa849a77710e65d8044a51b
  - path: LICENSE
    sha256: 4a69dc29421e26d9c8e50a823a1255c64441020942d4d5d0ecbc2fec8ca0b823
  - path: docs/plans/README.md
    sha256: a0fb41844379ad5dea460808b8a48a4c250a77268d672ae224b69807fe78bc4d
  - path: package.json
    sha256: e6a216a2914bd50466ed93f39dc77a75b49b15742e0a6818e0b36c5fdb4c6c02
  - path: pnpm-workspace.yaml
    sha256: 1b6fb329ddb565dfe223fbe6e95e879ccae7b59ff22d9b826c1260096760abfc
  - path: packages/subagent/package.json
    sha256: aedd14a7e71ead7da47ff7ce23364c53d85e38295f9969e793f5199b3ee67cd9
  - path: packages/subagent/README.md
    sha256: c2713ecb8da65150ef624dfb469cf719033defe03147c1a3dc3c97a1301042df
  - path: .github/workflows/ci.yml
    sha256: c602b2e35ededfd4c934b2509eb5786755cca6be7e3c419b3f3e0909e11583e2
  - path: .github/workflows/release.yml
    sha256: 441f8aaeceee89bfcdb52ac6f2453d0821a7ef755482127c727b6a1e6f1e4f58
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

- Default branch: `main`; latest stable release `v2.0.1` resolves to `bdfeea3ed77392a2d02617fa1e0d4aa5fd8317e3`. At this refresh, `main` is `a2bd4d6041206e9f5c0b17168a9e41749c90409d`, 11 commits after the release, with README/test/session-name changes and no execution-limit overlap.
- `v2.0.1` is published, non-draft, non-prerelease, and marked latest.
- pnpm 10 workspace; install with `corepack pnpm install --frozen-lockfile` and use package/workspace scripts.
- Non-trivial work requires a committed dated plan under `docs/plans/`, plan-index maintenance, reviewer dispatch, and completion under `docs/plans/done/`.
- Commits are logical and use repository conventional style.
- Required candidate checks: subagent/package TypeScript, all workspace typechecks, focused Vitest, full repository tests, and diff checks.
- No PR template, CONTRIBUTING file, CLA/DCO requirement, issue-first rule, or repository AI-contribution policy was observed at the target.
- User permission checked 2026-08-12: upstream repository is read-only; existing user fork `stvhay/pi-archimedes` grants ADMIN. After exact approval `pi-ujpw` and OAuth-scope approval `pi-v4ge`, fork `main` was fast-forwarded without force to current upstream `main@a2bd4d6`. Recheck before remote actions.
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

At upstream `main@a2bd4d6` on 2026-08-12 with Node 24.15.0 and repository-pinned pnpm 10.0.0:

- `corepack pnpm install --frozen-lockfile` — PASS
- `corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit` — PASS
- `corepack pnpm -r exec -- tsc --noEmit` — PASS
- `corepack pnpm --filter @pi-archimedes/subagent exec vitest run` — PASS, 91 tests
- `corepack pnpm test` — PASS, 572 tests
- Clean worktree after checks — PASS

## Current fork-draft evidence

Verified on 2026-08-12 after normal fast-forward pushes; all three PRs remain fork-local, OPEN+DRAFT, cleanly mergeable, and without review requests. No corresponding upstream PR exists.

| PR | Base | Head | Fresh candidate checks | Public-safe evidence |
|---|---|---|---|---|
| `stvhay/pi-archimedes#1` | `main@a2bd4d6` | `feat/subagent-execution-limits@2315b2e` | subagent TypeScript PASS; workspace TypeScript PASS; 185 subagent tests PASS; 666 monorepo tests PASS; diff check PASS | Body records a 10-request child ceiling with parent completion/result visibility. |
| `stvhay/pi-archimedes#2` | `feat/subagent-execution-limits@2315b2e` | `feat/subagent-one-shot-mode-stacked@8090d0c` | subagent TypeScript PASS; workspace TypeScript PASS; 229 subagent tests PASS; 710 monorepo tests PASS; focused output-limit suite 54 tests PASS; diff check PASS | Includes deployed exact effective-ceiling fix without repeated-error code. Body records failed provider-length classification with usable partial output/usage retained, without publishing content or private identifiers. |
| `stvhay/pi-archimedes#3` | `feat/subagent-execution-limits@2315b2e` | `fix/subagent-repeated-errors@47e30b7` | subagent TypeScript PASS; workspace TypeScript PASS; 203 subagent tests PASS; 684 monorepo tests PASS; diff check PASS | Body claims synthetic threshold/boundary tests only and explicitly records no live repeated-error recurrence. |

## Proposed result ports

- Normative proposal: `.pi/plans/2026-08-15-pi-archimedes-result-port-contract.md`.
- Target: this repository's `main` branch and public package subpaths `@pi-archimedes/subagent/types`, `@pi-archimedes/subagent/agents`, and `@pi-archimedes/core/bus`; no upstream issue, plan, branch, commit, PR, tag, or publication is authorized by the proposal.
- Required public result evidence covers output contracts, resolved limits, termination, usage, final output, child session/trace refs, ordered `details.results[]`, and the enclosing Pi tool-result type. The existing Pi `tool_result` remains transport; no result bus or service is proposed.
- The public agent seam resolves only a named agent's configured model, and the typed bus surface exposes current UI/cost payloads. pi-setup keeps routing, billing classification, authority, Bead closeout, acceptance, and quality policy.
- No released package set currently satisfies this contract. Q19R must record exact npm package versions, tarball integrity/provenance, reviewed source commit and tag, published `"./types"`, `"./agents"`, and `"./bus"` exports and declarations, and passing installed-package contract tests before Q21 adoption.

## PR implications

- Public additions must remain minimal, additive, documented, and tested for invalid inputs, Windows spawn, ordering, abort/cleanup, model rendering, output/usage preservation, and progress compatibility.
- Upstream v2.0.1 already includes child session IDs and model labels; omit duplicate candidate code.
- Use repository pnpm commands and keep reviewer-facing PR prose free of pi-setup projection mechanics.
- Profile is current for `main@a2bd4d6`; refresh again before any upstream draft creation or when that ref changes.
