---
profile_version: 1
repository: https://github.com/gooyoung/pi-langfuse
last_checked_utc: 2026-08-12T08:49:25Z
target_ref: v1.5.12
source_commit: c79c527a7294e1d4b8153525d5218e87354cbcb1
status: current-for-target-ref
quality_port_status: proposed-unreleased
recheck_every_use:
  - permissions
  - fork-state
  - templates
  - branch-protection-and-ci
  - issue-requirements
source_files:
  - path: README.md
    sha256: 280fb745bc97172178431f713216b3436b8192b9ed9b435dab21b207229adb25
  - path: README_CN.md
    sha256: b7b204c24056d324791e902d062745fd70bd42254647ef9b14bd3b8988f12b37
  - path: AGENTS.md
    sha256: 2d0b44fb79d7814319741acd9e25cdb0d16ea559dbdda54aae0e7439e16cd8ab
  - path: DEVELOPMENT.md
    sha256: 196e9623b39fe43011f5a41ea19f9e4431bb0836273239a9060dfa07d14996fd
  - path: DEVELOPMENT_CN.md
    sha256: f99ad1b19c17f00782d35d57b25c1d87b52aa0ed5f25db0e82e1f0ca184e1721
  - path: package.json
    sha256: 6b23c313563eeb17fe84c1483ae2cf55111cc19c555e384055ef7f1599ac0969
  - path: package-lock.json
    sha256: 3c8a85edf68c7bbaf933a6193b141ab6f1b03abb04af0db8610718503a4b2673
  - path: .github/workflows/publish.yml
    sha256: c5e0be88634700712947da8645490c3ec4a87e304ca9c4fde9020869fa40c672
  - path: index.ts
    sha256: 90c67250f7f2dd481922b4935efabf37f29fc7ba17390dbf71f239595ad3bb0f
  - path: src/state.ts
    sha256: b1bf3e3af672c1aa1bec9166acb1f110f8552297434ee806b5a5f85bebedcd0f
  - path: src/langfuse.ts
    sha256: 7ebaeb6c574e9ed4cc03e65eb810f87b2a9699c9441916e83196b2ae24c76437
  - path: src/handlers/agent.ts
    sha256: 08ff8c2d3e897c14d1cb616d25dbcfd5c3cbaa1d08324719029625743e5f90bc
  - path: src/handlers/tool.ts
    sha256: aef64ed903f1b14de3ff85a8a4836902efe2eac7ecaf6cc48d154a1ecb625293
  - path: src/capture-policy.ts
    sha256: 424390f188d75642471260e76055d35af211e8aad1f9ce4fab9858ac318f84ca
  - path: src/constants.ts
    sha256: b61cbd789b0461dcc404457960844add968b17ce7d3f08e8342e3ca2ba48c30b
  - path: src/utils.ts
    sha256: fc50dab22371592296fa59c3cb33fb98f6ebd3fe8a36cc10c5d5bc2f1b5fde66
  - path: src/types.ts
    sha256: 765ba0e144942793072ead95db235a42fca967548adf22e2633cbe38b32a8c4e
  - path: test/index.test.ts
    sha256: 78871aea43e59a22d4df205b5a25854c1a5c6ef09964649224d8c413d2ebadc8
  - path: test/capture-policy.test.ts
    sha256: ef447b6228f3e8ba26fd77c695de606246f65662fae598173ff17886f9669b51a
  - path: test/limits.test.ts
    sha256: f272cd452baedeb3f12a1c405f6abb323e77c6bb2f68cd7f2360f8d9f5a2b51a
  - path: test/utils.test.ts
    sha256: 130c826de79d0f41d9b90278eff1370ae911e1f78fef9e16ed2da646b4a3b6a9
  - path: test/state.test.ts
    sha256: 471fcaaac505569ad5d1dfaa30d786853a605948661464fc51407a0367e6944b
  - path: test/langfuse.test.ts
    sha256: d3c6e67bc2e23324ac64d9a0704507f9d54a667b8c789308332049e503051b2c
  - path: test/system-prompt-capture.test.ts
    sha256: b30031519dc047eb8b8be1d6d44c54772a164d734264df613aacdfd081787227
---

# gooyoung/pi-langfuse upstream profile

## Contribution workflow

- Default branch: `main`; stable target `v1.5.12` resolves to `c79c527a7294e1d4b8153525d5218e87354cbcb1` and matches checked upstream `main`.
- npm-only project; use tracked `package-lock.json` with `npm ci`.
- Required candidate checks: `npm run typecheck`, `npm test`, `npm pack --dry-run`, and diff checks.
- `AGENTS.md`, `DEVELOPMENT.md`, and `DEVELOPMENT_CN.md` now agree on `npm test`; the older direct `node --test` guidance is gone.
- No PR template, issue template, CLA/DCO, or repository AI-contribution policy observed at this target.
- Mutable state checked 2026-08-12T08:49:25Z: upstream permission `READ`; `stvhay/pi-langfuse` exists with `ADMIN`; upstream has open issue #17 and draft PR #18; no repository rulesets were present; branch-protection details remain unavailable through the API (HTTP 404).
- Publish workflow is release/tag driven on Node 24 and runs install, typecheck, tag validation, package inspection, then npm provenance publication. PR approval never authorizes release.

## Target changes relevant to this contribution

- v1.5.11 captures the final system prompt at `agent_start`, after later extension overrides.
- v1.5.12 capability-gates legacy trace REST fallback for Langfuse v4 `events_only`, isolates shutdown-step failures, bounds score shutdown independently, and keeps later shutdown steps running after one failure.
- Logical Pi session correlation and stable score entity/body IDs remain native; retry-stable ingestion envelope IDs are still absent.
- v1.5.12 still sends each `ingestBatch()` argument as one request and still lacks media-safe finite ordinary-string handling, so reviewed batching/media contributions remain candidates but must be rebuilt around the new fallback and shutdown seams.
- Tool byte metadata is computed from `captured.toolInput` and `captured.toolOutput` after capture policy replacement. Disabled tool capture therefore measures an unavailable serialization marker rather than the bounded pre-policy representation; any correction must keep exact counts separately controlled and version the metadata semantics.

## Policy findings

- License: root `package.json` declares MIT; no root license file observed.
- Commit signoff/signing, branch naming, issue-first requirements, and generated-source rules: none observed.
- User-facing behavior belongs in paired English/Chinese READMEs.
- Package contents are checked with `npm pack --dry-run`; no generated production source is tracked.

## Coding style

**Confidence:** high

- TypeScript entrypoint with small helpers, defensive catches, semicolons, and double quotes.
- Tests use `node:test`, `assert`, synthetic IDs, fake runtimes, captured handlers, and `try/finally` cleanup.
- Validate `unknown` at runtime boundaries; avoid unrelated modernization of existing `any`, array-style, or brace conventions.
- Keep lifecycle, session isolation, privacy shaping, trace fallback, and shutdown ordering changes narrowly tested.

## Proposed quality ports

- Normative proposal: `.pi/plans/2026-08-15-pi-langfuse-quality-port-contract.md`.
- Target: this repository's `main` branch and public package subpath `pi-langfuse/quality`; no upstream issue, branch, commit, PR, tag, or publication is authorized by the proposal.
- Required public factories: `createObservationCapturePort` and `createServiceEvidencePort`. pi-langfuse owns capture redaction, observation lifecycle, session propagation, export/flush completion, and explicit gaps; bounded private service evidence covers traces, observations, scores, annotation queue items/scores, score configs, completeness, and gaps.
- Authorization, Bead closeout, result acceptance, and pi-setup quality policy remain outside the package contract.
- No released package currently satisfies this contract. Q18R must record the exact npm version, tarball integrity/provenance, reviewed source commit and tag, published `"./quality"` export and types, and passing installed-package contract tests before Q20 adoption.

## PR implications

- Rebuild against v1.5.12; never replay the 1.5.10 `src/langfuse.ts` wholesale.
- Preserve capability detection and `runShutdownStep()` behavior while adding bounded ingestion.
- Keep media handling separate from batching in fork-local review candidates; combine only in the vendor/runtime lineage.
- Source-metadata privacy candidate: fork draft [stvhay/pi-langfuse#5](https://github.com/stvhay/pi-langfuse/pull/5) and upstream draft [gooyoung/pi-langfuse#18](https://github.com/gooyoung/pi-langfuse/pull/18), both at `90ce2d8c87cc6f12407fd445b8baabeecb9be456`.
- Reviewer prose should list repository-required checks and behavior evidence, not private workflow artifacts.
