---
profile_version: 1
repository: https://github.com/danielcherubini/pi-archimedes
last_checked_utc: 2026-08-15T17:59:10Z
target_ref: v2.1.0
source_commit: 2ed26aa1d3301cc01a927d9409778bbd13df4798
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
    sha256: 8903a46ec98f9fca2580c457899654a41f176d3ed0f799aa668ca60ecea454b6
  - path: package.json
    sha256: e6a216a2914bd50466ed93f39dc77a75b49b15742e0a6818e0b36c5fdb4c6c02
  - path: pnpm-workspace.yaml
    sha256: 1b6fb329ddb565dfe223fbe6e95e879ccae7b59ff22d9b826c1260096760abfc
  - path: packages/core/package.json
    sha256: 8f22032719059ce7822a14465c330d92231abd996726e7e096e67ed8653eeea3
  - path: packages/core/src/bus.ts
    sha256: 013d791ce4f2c3e157545170c35988dde84465b3fe430b4f8599ff1d8f2d2c5a
  - path: packages/core/src/bus.test.ts
    sha256: 26924160cb42e240d7aa8a9d1c0ee4b731c9469104702aad87ce1569aa81c093
  - path: packages/subagent/package.json
    sha256: 60487b3861740fa368080acbd6f575ec18bfbcebb484c02d802f46e54816cb2b
  - path: packages/subagent/README.md
    sha256: 24768f9384a0f0746e41881a411f697f5148f6bca9d276d9f67309a0c889358d
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
  - path: packages/subagent/src/agents.ts
    sha256: e1f06b59245af1b6208574dcad4da0ae4fe8d7e185ed58918a052b29859d9d4d
  - path: packages/subagent/src/agents.test.ts
    sha256: ce19cae77b8f54415a6c4bceb9c7a1ab59b69f87cf22823d0a021dd829203b99
  - path: packages/subagent/src/local-config.ts
    sha256: ba7ae08321ef860d66f20daf4628159ebb8e5ee734341ad8aacca3a15651b4d5
  - path: packages/subagent/src/local-config.test.ts
    sha256: 5363feff2a57ddf3ed843a3e66ba05ae19363e07f76246037c55d2133705aa71
  - path: packages/subagent/src/save-agent.test.ts
    sha256: daa05299c368bf94469956c683fec6441c308fdd7f2f3b585f06e6dc82f7a462
---

# danielcherubini/pi-archimedes upstream profile

## Contribution workflow

- Default branch and current public tag: `main` and `v2.1.0` both resolve to `2ed26aa1d3301cc01a927d9409778bbd13df4798`.
- npm published `pi-archimedes@2.1.0`, `@pi-archimedes/subagent@2.1.0`, and `@pi-archimedes/core@2.1.0` on 2026-08-15. GitHub's latest-release API still reports v2.0.1; source tag, successful release workflow, and npm registry are the current public package evidence.
- pnpm 10 workspace; run `corepack pnpm install --frozen-lockfile` from the repository/worktree directory, then package/workspace scripts.
- Non-trivial work requires a committed dated plan under `docs/plans/`, plan-index maintenance, reviewer dispatch, and completion under `docs/plans/done/`.
- Commits are logical and use repository conventional style.
- Required candidate checks: subagent/package TypeScript, all workspace typechecks, focused Vitest, full repository tests, package dry-runs, and diff checks.
- No PR template, CONTRIBUTING file, CLA/DCO requirement, issue-first rule, or repository AI-contribution policy exists at the target.
- Permissions rechecked 2026-08-15: upstream is read-only; existing fork `stvhay/pi-archimedes` grants ADMIN. Recheck before any remote action.
- Upstream `main` is unprotected. It has zero open issues and one unrelated open image-paste PR (#30). Current `main@2ed26aa` CI and v2.1.0 release workflow succeeded.
- Release/publish workflow is tag-driven and publishes packages in dependency order; PR approval does not authorize release or publication.

## Policy findings

- License: MIT `LICENSE`.
- Branch naming, commit signing, signoff, and contributor eligibility rules are unspecified.
- Package interface changes should update `packages/subagent/README.md`; repository-level user-visible changes should align root `README.md` only when needed.
- `pnpm-lock.yaml` is tracked. No generated-source update rule exists.
- README says Node.js >=24 while CI uses Node 22; verify project-prescribed CI shape and local Node 24 rather than changing guidance.

## Coding style

**Confidence:** high
**Evidence checked:** v2.1.0 source files listed above, release metadata, workflows, and clean baseline.

- TypeScript ESM with relative intra-package imports, public cross-package subpaths, explicit exported result/config types, and additive optional compatibility fields.
- Existing architecture runs each worker as a fresh `pi --mode json --no-session -p` child process.
- Preserve process arguments, environment inheritance, Windows `process.execPath`/`windowsHide`, abort behavior, socket cleanup, progress shape, parallel result ordering, model labels, child session correlation, and usage reporting.
- v2.1.0 adds local JSON thinking overrides in `agents.ts`; public agent-model resolution must reuse `discoverAgents` so those overrides remain authoritative.
- Tests use Vitest, synthetic child streams, and package-level typechecks.
- Plan and implementation/documentation changes should remain coherent and reviewable.

## Current baseline evidence

At `v2.1.0@2ed26aa` on 2026-08-15 with Node 24.15.0 and repository-pinned pnpm 10.0.0:

- `corepack pnpm install --frozen-lockfile` — PASS (from worktree cwd; invoking Corepack from another repository selected the wrong package manager and was rejected before install).
- `corepack pnpm --filter @pi-archimedes/subagent exec tsc --noEmit` — PASS.
- `corepack pnpm -r exec -- tsc --noEmit` — PASS.
- `corepack pnpm --filter @pi-archimedes/subagent exec vitest run` — PASS, 112 tests.
- `corepack pnpm test` — PASS, 593 tests.
- Clean worktree after checks — PASS.

## Current fork-draft state

Rechecked 2026-08-15. All three fork-local PRs remain OPEN+DRAFT and report mergeable, with no review requests or status checks. Their last fresh candidate matrices were recorded on 2026-08-12; current work rebuilds new local candidates rather than rewriting these remote branches.

| PR | Base | Remote head | State |
|---|---|---|---|
| `stvhay/pi-archimedes#1` | `main` | `feat/subagent-execution-limits@2315b2e` | Open draft; based on prior `main@a2bd4d6`. |
| `stvhay/pi-archimedes#2` | `feat/subagent-execution-limits` | `feat/subagent-one-shot-mode-stacked@8090d0c` | Open draft; stacked on prior limits head. |
| `stvhay/pi-archimedes#3` | `feat/subagent-execution-limits` | `fix/subagent-repeated-errors@47e30b7` | Open draft; stacked on prior limits head. |

## Local v2.1.0 candidates

Built locally from immutable `v2.1.0@2ed26aa` without rewriting existing fork histories or mutating remotes:

| Candidate | Head | Predecessor |
|---|---|---|
| `rebuild/subagent-execution-limits-210` | `23d8fbf7381f2081806165e26d6b0962aef13ef9` | `2ed26aa1d3301cc01a927d9409778bbd13df4798` |
| `rebuild/subagent-one-shot-mode-210` | `f277470d64d014b496efe7e4ae4d57275d8e1907` | `23d8fbf7381f2081806165e26d6b0962aef13ef9` |
| `rebuild/subagent-repeated-errors-210` | `3576ddfd154fb274813a16e07607a15520ce73b7` | `f277470d64d014b496efe7e4ae4d57275d8e1907` |
| `feat/result-ports-210` | `a9efbf159ee8b2717aae1df8742bd7382e97c1a3` | `3576ddfd154fb274813a16e07607a15520ce73b7` |
| `vendor/pi-setup-210` | `1c4750ddb844cd8579f3076922603915098e9f96` | `a9efbf159ee8b2717aae1df8742bd7382e97c1a3` |

Each row is exactly one commit above its predecessor. Final vendor verification passed all recursive TypeScript checks, 271 focused subagent tests, 754 workspace tests, and npm package previews. Exact npm 2.1.0 bases accepted the zero-context projection, idempotent reapply, reverse dry-runs, and public `./agents`, `./types`, and `./bus` imports under Pi's Jiti runtime.

## Proposed result ports

- Normative proposal: `.pi/plans/2026-08-15-pi-archimedes-result-port-contract.md`.
- Target: public subpaths `@pi-archimedes/subagent/types`, `@pi-archimedes/subagent/agents`, and `@pi-archimedes/core/bus`; no upstream mutation is authorized by the proposal.
- Required public result evidence covers output contracts, resolved limits, termination, usage, final output, child session/trace refs, ordered `details.results[]`, and the enclosing Pi tool-result type. Pi `tool_result` remains the only result transport.
- Agent resolution returns only configured model. Typed bus exports current UI/cost payloads. pi-setup keeps routing, billing, authority, closeout, acceptance, persistence, and quality policy.
- No released package set currently satisfies this contract. `pi-rxo3.24` local candidates and patches are not release evidence.

## PR implications

- Rebuild from `v2.1.0@2ed26aa`; do not rewrite existing fork-draft histories during hardening.
- Keep public additions minimal, additive, documented, and tested for invalid inputs, Windows spawn, ordering, abort/cleanup, model rendering, output/usage preservation, and progress compatibility.
- Preserve v2.1.0 child session/model and local thinking-override behavior; omit duplicate candidate code.
- Use repository pnpm commands and keep reviewer-facing prose free of pi-setup projection mechanics.
- Profile is current for `v2.1.0@2ed26aa`; refresh before upstream draft creation or when target ref changes.
