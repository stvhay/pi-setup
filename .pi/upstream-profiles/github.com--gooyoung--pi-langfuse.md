---
profile_version: 1
repository: https://github.com/gooyoung/pi-langfuse
last_checked_utc: 2026-08-15T15:48:55Z
target_ref: v1.5.14
source_commit: 04d55a12556bdf4c4b8b208038198dc2fd8e571b
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
    sha256: 4a7cc741acaba821f848fb9bee89877392252f6006e364dc4b4812f0a552ee8a
  - path: README_CN.md
    sha256: 87150d24e5684336216cdbbaf2fdb9a86f0035dfd5a9e748ea02130158d8a935
  - path: AGENTS.md
    sha256: 4cd480307dd7da58842f6b58e7d21e71152964a0619bc5facd9a59aabc9a7a04
  - path: DEVELOPMENT.md
    sha256: 196e9623b39fe43011f5a41ea19f9e4431bb0836273239a9060dfa07d14996fd
  - path: DEVELOPMENT_CN.md
    sha256: f99ad1b19c17f00782d35d57b25c1d87b52aa0ed5f25db0e82e1f0ca184e1721
  - path: package.json
    sha256: b03d15233ae863b79637f3cf333563c1051b1afb8d4dcf7d24d871c504f76f39
  - path: package-lock.json
    sha256: 77498c9a66f614504a0da28f095c177fc7072681e65e937555d41a0113fe6f21
  - path: .github/workflows/publish.yml
    sha256: c5e0be88634700712947da8645490c3ec4a87e304ca9c4fde9020869fa40c672
  - path: index.ts
    sha256: 90c67250f7f2dd481922b4935efabf37f29fc7ba17390dbf71f239595ad3bb0f
  - path: src/state.ts
    sha256: b1bf3e3af672c1aa1bec9166acb1f110f8552297434ee806b5a5f85bebedcd0f
  - path: src/config.ts
    sha256: 6316a4eb4e55aaaf481286ff1220f863e59c768ff5af669a62a038ea4413c937
  - path: src/commands.ts
    sha256: 77bce3479025686f6f47bf0bc402a8fe4bd4ecbe0369676e0542ee23813f7b2f
  - path: src/langfuse.ts
    sha256: 79196cc0f1e0a5839a082e2350c4ad1c44c080a406acff7b433aaf86d74d5873
  - path: src/handlers/agent.ts
    sha256: 11603133bc55de38e4e9184adcf82e532f8345ffb1ddf65647728cfc8ce98dcf
  - path: src/handlers/generation.ts
    sha256: b655ced6ecdd305d7a1a6e6d9ad9def8379a89246ef01107d476bf5b5192b9f7
  - path: src/handlers/tool.ts
    sha256: aef64ed903f1b14de3ff85a8a4836902efe2eac7ecaf6cc48d154a1ecb625293
  - path: src/capture-policy.ts
    sha256: a44267e09b73f22f89a8a7c6b0ac9c9fa93d93d47d9a7f5696aef75c405ce9f8
  - path: src/constants.ts
    sha256: b61cbd789b0461dcc404457960844add968b17ce7d3f08e8342e3ca2ba48c30b
  - path: src/limits.ts
    sha256: 70351f5b94c89a094ed20ce220783330d69ff274a5a68c0e4cd5b03cfcacd9cc
  - path: src/redaction.ts
    sha256: 60e62a1d9f669f19f89583f74d9152db3bd6e8b9bc0acdd3f7f2fb254429f70d
  - path: src/source-metadata.ts
    sha256: fa42d258db7ae87936258a057ac0532c0939b16c8bb75da021a7b854686d62ee
  - path: src/utils.ts
    sha256: fc50dab22371592296fa59c3cb33fb98f6ebd3fe8a36cc10c5d5bc2f1b5fde66
  - path: src/types.ts
    sha256: 765ba0e144942793072ead95db235a42fca967548adf22e2633cbe38b32a8c4e
  - path: test/index.test.ts
    sha256: 78871aea43e59a22d4df205b5a25854c1a5c6ef09964649224d8c413d2ebadc8
  - path: test/capture-policy.test.ts
    sha256: 950c53e81b9ed2346da6675704c50a91119849e146de018138a44524a1779bd4
  - path: test/limits.test.ts
    sha256: f272cd452baedeb3f12a1c405f6abb323e77c6bb2f68cd7f2360f8d9f5a2b51a
  - path: test/utils.test.ts
    sha256: 130c826de79d0f41d9b90278eff1370ae911e1f78fef9e16ed2da646b4a3b6a9
  - path: test/state.test.ts
    sha256: 471fcaaac505569ad5d1dfaa30d786853a605948661464fc51407a0367e6944b
  - path: test/langfuse.test.ts
    sha256: eff75cc826eb7af432f9d112614e29c5a87421ced568206e93e25520e59157ae
  - path: test/system-prompt-capture.test.ts
    sha256: b30031519dc047eb8b8be1d6d44c54772a164d734264df613aacdfd081787227
---

# gooyoung/pi-langfuse upstream profile

## Contribution workflow

- Default branch: `main`; stable target `v1.5.14` resolves to `04d55a12556bdf4c4b8b208038198dc2fd8e571b` and matches checked upstream `main`.
- npm-only project; use tracked `package-lock.json` with `npm ci`.
- Required candidate checks: `npm run typecheck`, `npm test`, `npm pack --dry-run`, and diff checks.
- `AGENTS.md`, `DEVELOPMENT.md`, and `DEVELOPMENT_CN.md` now agree on `npm test`; the older direct `node --test` guidance is gone.
- No PR template, issue template, CLA/DCO, or repository AI-contribution policy observed at this target.
- Mutable state checked 2026-08-15T15:48:55Z: upstream permission `READ`; `stvhay/pi-langfuse` exists with `ADMIN`; upstream has open issue #17 and no open PRs; fork draft PRs #2-#5 remain open; no repository rulesets were present; branch-protection details remain unavailable through the API (HTTP 404).
- Publish workflow is release/tag driven on Node 24 and runs install, typecheck, tag validation, package inspection, then npm provenance publication. PR approval never authorizes release.

## Target changes relevant to this contribution

- v1.5.11 captures the final system prompt at `agent_start`, after later extension overrides.
- v1.5.12 capability-gates legacy trace REST fallback for Langfuse v4 `events_only`, isolates shutdown-step failures, bounds score shutdown independently, and keeps later shutdown steps running after one failure.
- v1.5.14 merges upstream PR #18: source metadata is now explicit opt-in, revision-only, and does not inspect repository names, remotes, URLs, usernames, branch names, or repo-local metadata files.
- Logical Pi session correlation and stable score entity/body IDs remain native; retry-stable ingestion envelope IDs are still absent.
- v1.5.14 still sends each `ingestBatch()` argument as one request and still lacks media-safe finite ordinary-string handling, so reviewed batching/media contributions remain candidates but must be rebuilt around current fallback, shutdown, and source-metadata seams.
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
- Q18V verifies the exact `stvhay/pi-langfuse` fork commit and `forks/pi-langfuse` gitlink as maintained source, plus the tracked patch as its derived projection onto the exact npm base. Fork/ref provenance, npm integrity, zero-fuzz apply/reverse, public `"./quality"` exports/types, rollback, and installed-package contract tests must pass before Q20 adoption. External-upstream submission is deferred under `pi-vzqq`; a future release may replace this projection but does not gate Q20.

## PR implications

- Rebuild against v1.5.14; never replay an older `src/langfuse.ts` wholesale.
- Preserve capability detection, `runShutdownStep()`, and revision-only source-metadata behavior while adding bounded ingestion or public quality ports.
- Keep media handling, batching, and quality ports separate in fork-local review candidates; combine only in the vendor/runtime lineage.
- Fork draft #5 is superseded: upstream PR [gooyoung/pi-langfuse#18](https://github.com/gooyoung/pi-langfuse/pull/18) merged as `f617432f5b67cdfb93e51080f2b876a474bc895a` and shipped in v1.5.14.
- Reviewer prose should list repository-required checks and behavior evidence, not private workflow artifacts.
