---
profile_version: 1
repository: https://github.com/gooyoung/pi-langfuse
last_checked_utc: '2026-10-21T19:13:06.816722Z'
target_ref: v1.7.0
source_commit: 1c4dd956597af272d1869ce897e922d7702845fe
status: historical-published-baseline
quality_port_status: maintained-fork-local-verified
quality_port_verified_utc: '2026-10-21T19:13:06.816893Z'
npm_published_utc: '2026-10-08T02:13:34.481Z'
npm_integrity: sha512-dXMv4NLySMzOfIBmaSNUsu83HQNh3N4qxjgD9l5hvmWARSJ75W2YnD1dfIoRi9QUb2LnJsmSVHqJV9ENDL5K8w==
maintained_fork_base: 1c4dd956597af272d1869ce897e922d7702845fe
maintained_fork_head: 0ba150f5bd38c1e282feec5a488a918e6076063b
maintained_fork_branch: vendor/pi-setup-170
superproject_gitlink: 0ba150f5bd38c1e282feec5a488a918e6076063b
derived_patch: patches/pi-packages/pi-langfuse-1.7.0.patch
derived_patch_sha256: d41b50c3bfd1477f6eaa5299597a0699f9bd028d4f66b8dde8b422f0a57b6909
package_proof: scripts/verify-pi-langfuse-package-patch.sh
recheck_every_use:
- permissions
- fork-state
- templates
- branch-protection-and-ci
- issue-requirements
source_files:
- path: README.md
  sha256: cb7044694ce480fd7451988d00b7ee25d4ce5e26c9f2ecaea344dfca81039541
- path: README_CN.md
  sha256: 31d0e1dff316ea88313956e60cd54c07805e9c72845e2a57b0d52367898b2831
- path: AGENTS.md
  sha256: c8caf0f08c18b2558102c1876d5d1e4fe4fb5364a17bffa9fc346e71528a0de9
- path: DEVELOPMENT.md
  sha256: 10491dfd28f9917142d4d53893beff0a76140e6bcca90d45eda4dbd83655c4ba
- path: DEVELOPMENT_CN.md
  sha256: d898f94f7769957d2f59850b9f7d649139b05789d6f87e830aa30fbc7b3dc268
- path: package.json
  sha256: 951815c4884df9114ef8abc2b94bda445dd7c5eeb9622f8a88cb0cbe57f915ec
- path: package-lock.json
  sha256: f90648551a1bb2a59f558376ac5801fa138799ec901a1454d18589e271e8e5da
- path: .github/workflows/publish.yml
  sha256: c5e0be88634700712947da8645490c3ec4a87e304ca9c4fde9020869fa40c672
- path: index.ts
  sha256: 0887c9791103cee92bd408a79e273f8bef8e04c8cafed1a225d8247def13e812
- path: src/state.ts
  sha256: 92a91881eab368d54f9610a3df91c196addc86c1a06d056ee71c4a4a3fd2e2b2
- path: src/config.ts
  sha256: 273c9355e5622437c6748d12d60517c2d986756b67c794b681a4b09b3f2c1cc5
- path: src/commands.ts
  sha256: d188d2a114cffa759f4fe4ce1c343bdc7ee87c76108ab94ea5ee5b448801b8a8
- path: src/langfuse.ts
  sha256: 40e79f3cc9a522bbc80121848ed57272ff447b9a3b32439f0d9f3e54cbd1b02c
- path: src/handlers/agent.ts
  sha256: f7c58665dc20b572173b8a45d06afada1b5d2037d301d3f13302970dd2fe674c
- path: src/handlers/generation.ts
  sha256: ee56991ae3ea9afab24c66c1bb27ada8b7475e6762a12a40285b0d8c75526ea7
- path: src/handlers/tool.ts
  sha256: feb8e789b42c71b968c7e3f6550e3f71cd22b0e6824b883945090f9fe3319a25
- path: src/capture-policy.ts
  sha256: eaf5d0fb9907c8cd6e9efb04756321f02e06b71d574ff0163339ef0344cc44d4
- path: src/constants.ts
  sha256: b61cbd789b0461dcc404457960844add968b17ce7d3f08e8342e3ca2ba48c30b
- path: src/limits.ts
  sha256: 70351f5b94c89a094ed20ce220783330d69ff274a5a68c0e4cd5b03cfcacd9cc
- path: src/redaction.ts
  sha256: 0907100e672654317c1045acadb6264d0e163c9624855b9cae744b29a27636dd
- path: src/source-metadata.ts
  sha256: fa42d258db7ae87936258a057ac0532c0939b16c8bb75da021a7b854686d62ee
- path: src/utils.ts
  sha256: 06a37700225f04102fd6861f0146adad64327b21d74eb8124a685f042aaa8849
- path: src/types.ts
  sha256: 4ab9471733eee2e14a2f26f2ee679b0acc6fb2db79f83f0e2c23d749378c69a9
- path: test/index.test.ts
  sha256: 5824fd5a7f0557709cbb2c5163109a93fbe4500bc111f9b81b6406ccfaa34885
- path: test/capture-policy.test.ts
  sha256: 98b32cadbe1c9913f09c7d75101880c63fb652c3c5c1ff433c6b7040e025e984
- path: test/limits.test.ts
  sha256: f272cd452baedeb3f12a1c405f6abb323e77c6bb2f68cd7f2360f8d9f5a2b51a
- path: test/utils.test.ts
  sha256: 86dcff0614235c3aa847d7a6ed9a299ae4f9eab094f077612e4f423b1bef4a9b
- path: test/state.test.ts
  sha256: 4d2097295c7a691ecf59fff957d0d0761882bdabd68e6a1421e470779052e066
- path: test/langfuse.test.ts
  sha256: 5b884af77e5d5009b50bcf3f4bbb0f1eb24bb0accbe38c436f0c970500f9378d
- path: test/system-prompt-capture.test.ts
  sha256: b30031519dc047eb8b8be1d6d44c54772a164d734264df613aacdfd081787227
publication_status: published
published_recovery_head: e5596e8df6136b07db143025ef400d325454b958
---

# gooyoung/pi-langfuse upstream profile

## Current maintained candidate — pi-ox9n

The frontmatter hashes and identities describe the published `pi-7zn8` baseline, not the local `pi-ox9n` candidate. Current source is committed as `f1024ce99d1fe3a360d3f220db75467aaad30894` in `forks/pi-langfuse` and published to its existing vendor branch under approval `pi-mhd9`; its generated runtime descriptor is `patches/pi-packages/langfuse-runtime/release.json`. Langfuse 6 with the maintained OTel 3 port targets server 4.59.0+. v4 OTLP, batch scores and bounded v2 readers replace legacy trace ingestion/polling. A lock-controlled isolated release replaces shared-tree patching; actual-state legacy transition is explicit, with no automatic migration mechanism. Public quality declarations remain part of the compiled projection.

Use npm 12.2.1 and the maintained English `DEVELOPMENT.md`; the historical workflow below does not override it. Current evidence is under `.pi/reviews/pi-ox9n/final-review/`: four discovered issues independently confirmed and fixed, 272 hermetic consumer tests plus strict types, and real fresh/reused updater plus Pi loader/privacy/quality proof. Stale integration fixtures were corrected. Under approval `pi-3f0v`, policy-preserving instruction compression clears the pre-existing size gate (105 context tests pass); complete root gates and integration status are recorded in pi-ox9n. No live service verification or deployment is implied. Publication approval `pi-mhd9` is consumed; any further push needs new exact approval.

## Historical 1.7.0 published vendor candidate

`pi-7zn8` ports retained contracts onto upstream `v1.7.0` without rewriting old fork history.
Local head `0ba150f5bd38c1e282feec5a488a918e6076063b` is one commit above the exact npm source.
The staged gitlink and derived production patch match this candidate. Approval `pi-x4j7` authorized
create-only publication; `vendor/pi-setup-170` was pushed and its exact remote SHA verified on
2026-10-21. Evidence: `.pi/reviews/pi-7zn8/vendor-publication-result.json`. Live deployment remains
unapproved; this is not whole-upgrade release acceptance.
The 1.5.14 record below remains historical recovery evidence, not the current candidate status.

- Native adoption: ingestion splitter, nested tools/own usage, provider identity, attempt/settled lifecycle,
  system-state/cache telemetry, v4 child propagation, canonical cache keys and TTL/reasoning splitting.
- Retained patches: shared hard 3,000,000-byte requests, stable score-envelope retries, oversized-event
  continuation, generation-input-only media, REST sanitization, private tool bytes/errors, quality ports,
  valid-first cache counts and explicit zeros. Aggregate fallback skipping is opt-in, not default.
- Local fork gates: SDK 1.3.0, typecheck and 181 tests passed. Exact npm projection proof verifies
  whole production inventory, forward/reverse/idempotence and 113 installed-package tests, including
  the actual managed wrapper's path ceiling, public quality port and subscription alias/restore chain.
- Evidence: `.pi/reviews/pi-7zn8/langfuse-installed-proof.log`, `langfuse-local-gate.json` and
  `langfuse-peer-review.json`. npm tarball integrity verified; provenance attestation not rechecked.
- Known dependency audit: 26 production findings (4 high), inherited upstream dependency family;
  no automatic OTel major upgrade. Final whole-upgrade release gates remain pending.
- Recovery: retain published `vendor/pi-setup-1514` at `e5596e8d` and the old projection at root
  `76bf0dde8ed341de7ef69053eed227b66552dfd3`. Reinstall that exact old npm base before its patch;
  reverting config alone does not undo package changes. Live rollback needs separate approval.

## Historical 1.5.14 contribution workflow

- Default branch: `main`; stable target `v1.5.14` resolves to `04d55a12556bdf4c4b8b208038198dc2fd8e571b` and matches checked upstream `main`.
- npm-only project; use tracked `package-lock.json` with `npm ci`.
- Required candidate checks: `npm run typecheck`, `npm test`, `npm pack --dry-run`, and diff checks.
- `AGENTS.md`, `DEVELOPMENT.md`, and `DEVELOPMENT_CN.md` now agree on `npm test`; the older direct `node --test` guidance is gone.
- No PR template, issue template, CLA/DCO, or repository AI-contribution policy observed at this target.
- Mutable state checked 2026-08-15T15:48:55Z: upstream permission `READ`; `stvhay/pi-langfuse` exists with `ADMIN`; upstream has open issue #17 and no open PRs; fork draft PRs #2-#5 remain open; no repository rulesets were present; branch-protection details remain unavailable through the API (HTTP 404).
- Publish workflow is release/tag driven on Node 24 and runs install, typecheck, tag validation, package inspection, then npm provenance publication. PR approval never authorizes release.

## Historical 1.5.14 target changes

- v1.5.11 captures the final system prompt at `agent_start`, after later extension overrides.
- v1.5.12 capability-gates legacy trace REST fallback for Langfuse v4 `events_only`, isolates shutdown-step failures, bounds score shutdown independently, and keeps later shutdown steps running after one failure.
- v1.5.14 merges upstream PR #18: source metadata is now explicit opt-in, revision-only, and does not inspect repository names, remotes, URLs, usernames, branch names, or repo-local metadata files.
- Logical Pi session correlation and stable score entity/body IDs remain native; retry-stable ingestion envelope IDs are still absent.
- v1.5.14 still sends each `ingestBatch()` argument as one request and still lacks media-safe finite ordinary-string handling, so reviewed batching/media contributions remain candidates but must be rebuilt around current fallback, shutdown, and source-metadata seams.
- Tool byte metadata is computed from `captured.toolInput` and `captured.toolOutput` after capture policy replacement. Disabled tool capture therefore measures an unavailable serialization marker rather than the bounded pre-policy representation; any correction must keep exact counts separately controlled and version the metadata semantics.
- Maintained commits `1d705405` and `e5596e8d` preserve valid explicit zero cache-read/cache-write usage and supported aliases, including fallback past invalid aliases; absent or wholly invalid cache fields remain absent.

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

## Historical maintained quality ports

- Normative contract and full Q18V record: `.pi/plans/2026-08-15-pi-langfuse-quality-port-contract.md`.
- Verified source: immutable [`stvhay/pi-langfuse@e5596e8d`](https://github.com/stvhay/pi-langfuse/commit/e5596e8df6136b07db143025ef400d325454b958), three commits above upstream/npm base `04d55a12556bdf4c4b8b208038198dc2fd8e571b`. Published branch `vendor/pi-setup-1514` and the `forks/pi-langfuse` gitlink resolved to the same head during verification; quality-port ancestor `94fa7f0c` remains unchanged.
- Verified deployment projection: `patches/pi-packages/pi-langfuse-1.5.14.patch` at SHA-256 `0fa6010e0bbc010d7f9c27e15b88203ea1ce55a4b41259723afc76a5f65186ec`, applied to integrity-pinned `pi-langfuse@1.5.14` and byte-compared with the maintained fork.
- Public package subpath: `pi-langfuse/quality`; required factories are `createObservationCapturePort` and `createServiceEvidencePort`. Package-visible TypeScript exports include every contract type.
- `scripts/verify-pi-langfuse-package-patch.sh` verifies npm metadata/tarball integrity, fork/gitlink lineage, zero-fuzz apply/idempotence/reverse, exact fork projection, and all 15 installed-package quality contract tests.
- Q18V verifies the quality-port ancestor `94fa7f0c`; the current head adds only the tested cache-usage producer fix above that contract. Q20 may bind the current pin and public import without waiting for an upstream release.
- Authorization, Bead closeout, result acceptance, and pi-setup quality policy remain outside the package contract. External-upstream submission is deferred under `pi-vzqq`; a future release may replace this projection but does not gate Q20.

## Historical PR implications

- Rebuild against v1.5.14; never replay an older `src/langfuse.ts` wholesale.
- Preserve capability detection, `runShutdownStep()`, and revision-only source-metadata behavior while adding bounded ingestion or public quality ports.
- Keep media handling, batching, and quality ports separate in fork-local review candidates; combine only in the vendor/runtime lineage.
- Fork draft #5 is superseded: upstream PR [gooyoung/pi-langfuse#18](https://github.com/gooyoung/pi-langfuse/pull/18) merged as `f617432f5b67cdfb93e51080f2b876a474bc895a` and shipped in v1.5.14.
- Reviewer prose should list repository-required checks and behavior evidence, not private workflow artifacts.
