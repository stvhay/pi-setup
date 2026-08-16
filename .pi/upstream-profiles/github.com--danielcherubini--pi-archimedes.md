---
profile_version: 1
repository: https://github.com/danielcherubini/pi-archimedes
last_checked_utc: 2026-08-15T17:59:10Z
target_ref: v2.1.0
source_commit: 2ed26aa1d3301cc01a927d9409778bbd13df4798
status: current-for-target-ref
result_port_status: maintained-fork-verified
result_port_verified_utc: 2026-08-16T18:59:39Z
npm_pi_archimedes_published_utc: 2026-08-15T10:25:15.706Z
npm_pi_archimedes_integrity: sha512-TitGWAXRE6W+3bXwg7pIhnoKR7w3PzXW417RGpGyUwHgFIqHi20eRDAs0TipBoDO/HAsQVcdpXjB//W9D/1zRQ==
npm_pi_archimedes_registry: https://registry.npmjs.org/pi-archimedes/2.1.0
npm_subagent_published_utc: 2026-08-15T10:25:13.730Z
npm_subagent_integrity: sha512-Num0675GR2hWcp21r4epe7mqQDIgpMomUv55C9G1a96zv1mL9Gkv5eaSPe9iudI43j1lhdPEtcK3ObJs7tK9VA==
npm_subagent_registry: https://registry.npmjs.org/%40pi-archimedes%2Fsubagent/2.1.0
npm_core_published_utc: 2026-08-15T10:24:55.193Z
npm_core_integrity: sha512-TiZBNrhyk8trUw3J66J78HNUEVsgIWkzvDJUqGq2hxvwCDS32FcJWn0K2wX+0Og8lWawmsot2n7lsYUn0ysocw==
npm_core_registry: https://registry.npmjs.org/%40pi-archimedes%2Fcore/2.1.0
maintained_fork_base: 2ed26aa1d3301cc01a927d9409778bbd13df4798
maintained_fork_limits: 23d8fbf7381f2081806165e26d6b0962aef13ef9
maintained_fork_one_shot: f277470d64d014b496efe7e4ae4d57275d8e1907
maintained_fork_repeated_errors: 3576ddfd154fb274813a16e07607a15520ce73b7
maintained_fork_result_ports: a9efbf159ee8b2717aae1df8742bd7382e97c1a3
maintained_fork_head: 1c4750ddb844cd8579f3076922603915098e9f96
maintained_fork_branch: vendor/pi-setup-210
maintained_fork_commit: https://github.com/stvhay/pi-archimedes/commit/1c4750ddb844cd8579f3076922603915098e9f96
superproject_gitlink: 1c4750ddb844cd8579f3076922603915098e9f96
derived_patch_meta: patches/pi-packages/pi-archimedes-meta-2.1.0.patch
derived_patch_meta_sha256: 571e73ac589c03a256e802286b64f27c1869831fa1ca05f7f87c8b3369fb4a28
derived_patch_ask: patches/pi-packages/pi-archimedes-ask-2.1.0.patch
derived_patch_ask_sha256: eaa4c814f481ef95c1a95866170ec59d9553a257ed96634a37422f065fa062cc
derived_patch_core: patches/pi-packages/pi-archimedes-core-2.1.0.patch
derived_patch_core_sha256: 520ff1888ffe785f6648a2de5823023a6c146017ba21d8c7c6c1f12d2b81d73f
derived_patch_footer: patches/pi-packages/pi-archimedes-footer-2.1.0.patch
derived_patch_footer_sha256: 0e680ca78ed7422abf0241d8dfba982497b93b14064ef375aa4a3f7c0e437e34
derived_patch_subagent: patches/pi-packages/pi-archimedes-subagent-2.1.0.patch
derived_patch_subagent_sha256: 41de1eadb6f329f5c884421d80620df4135c28e34c070b1fc1cb9aba871a5ff0
package_proof: scripts/verify-pi-archimedes-package-patches.sh
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

## Maintained result ports

- Normative contract: `.pi/plans/2026-08-15-pi-archimedes-result-port-contract.md`.
- Q19V verifies the exact `stvhay/pi-archimedes` stack at immutable commit [`1c4750d`](https://github.com/stvhay/pi-archimedes/commit/1c4750ddb844cd8579f3076922603915098e9f96), published branch `vendor/pi-setup-210`, and matching `forks/pi-archimedes` gitlink as maintained source.
- Public subpaths are `@pi-archimedes/subagent/types`, `@pi-archimedes/subagent/agents`, and `@pi-archimedes/core/bus`. Result evidence covers output contracts, resolved limits, termination, usage, partial output, child session/trace refs, ordered `details.results[]`, and enclosing Pi tool-result type. Pi `tool_result` remains sole result transport.
- Registry version records for [`pi-archimedes`](https://registry.npmjs.org/pi-archimedes/2.1.0), [`subagent`](https://registry.npmjs.org/%40pi-archimedes%2Fsubagent/2.1.0), and [`core`](https://registry.npmjs.org/%40pi-archimedes%2Fcore/2.1.0) bind exact package names, versions, signatures, and tarball integrities. They omit `gitHead`, and npm attestation endpoints return 404, so Q19V claims no SLSA provenance. The package proof instead byte-compares each integrity-verified tarball file with `v2.1.0@2ed26aa` source, allowing only npm's semantic `workspace:*` manifest normalization.
- `scripts/verify-pi-archimedes-package-patches.sh` verifies the five patch hashes, zero-fuzz apply/idempotence/reverse, byte-exact maintained source projection, public TypeScript declarations, governance exclusions, and 100 installed-package tests. Reinstall exact 2.1.0 packages for base rollback; restore the pinned gitlink and patches for projection rollback.
- Agent resolution returns only configured model. Typed bus exports current UI/cost payloads. pi-setup keeps routing, billing, authority, closeout, acceptance, persistence, and quality policy. External-upstream submission is deferred under `pi-vzqq`; future releases may replace these projections but do not gate Q21.

## PR implications

- Rebuild from `v2.1.0@2ed26aa`; do not rewrite existing fork-draft histories during hardening.
- Keep public additions minimal, additive, documented, and tested for invalid inputs, Windows spawn, ordering, abort/cleanup, model rendering, output/usage preservation, and progress compatibility.
- Preserve v2.1.0 child session/model and local thinking-override behavior; omit duplicate candidate code.
- Use repository pnpm commands and keep reviewer-facing prose free of pi-setup projection mechanics.
- Profile is current for `v2.1.0@2ed26aa`; refresh before upstream draft creation or when target ref changes.
