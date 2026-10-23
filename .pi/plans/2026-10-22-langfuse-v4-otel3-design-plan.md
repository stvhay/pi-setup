# Langfuse v4 / OTel 3 remediation design and execution plan

**Issue:** pi-ox9n — Remediate Langfuse production dependency advisories and verify installed delivery
**Date:** 2026-10-21 (historical filename retained for existing references)
**Branch:** root `upgrade/plugins-2026-10`; existing Langfuse fork `vendor/pi-setup-170`
**Status:** Approved implementation in progress. Bead pi-ox9n holds canonical progress, gates, and remaining work.

## Objective and approved decisions

Deliver current, audited Langfuse dependencies and supported v4 endpoints without losing privacy, media shaping, quality public ports, cache-zero semantics, stable retry IDs, bounded requests or modern Pi lifecycle behavior. Prove actual fresh and reused installed delivery, not just fork source/lockfiles.

User decisions in this session:

1. Work pi-ox9n after CLOSED pi-7zn8. Recover only those Beads and their referenced artifacts; no prior transcript recovery. `bd prime`, `bd ready`, `agnt work direct-start pi-ox9n --claim` ran before experiments. Do not reopen pi-7zn8.
2. **Rejected** temporary OTel 2/API 1.9 exception. Investigate maintaining Langfuse SDK changes for OTel 3 instead. No older-version exception is approved.
3. Target **self-hosted Langfuse >=4.59.0**; include **full v4 endpoint migration** in telemetry and both quality readers. No server upgrade, backend mutation or deployment authorized.
4. **Approved isolated, lock-controlled Langfuse runtime delivery**, proposed destination `<DEST>/runtime/pi-langfuse/releases/<content-hash>`. Keep maintained fork as canonical source, preserve published history and vendor publication gate. Source/test/local task commits authorized. No live deployment, runtime deletion, publication or push authorized.
5. Approved bounded development-parent compatibility ports for latest dependencies, preserving inference wire behavior/privacy and rebuilding relevant shipped copies. This does not authorize global Pi changes.
6. **Scope correction (latest user direction): complete the migration, but an automatic migration mechanism is out of scope. Do not categorically fail closed on unsupported legacy states. Favor a smaller, maintainable, efficient codebase; simplification and removing duplication are worthwhile, automation and added capabilities are not.** This supersedes the earlier blanket legacy-state rejection and the automatic migration machinery developed during implementation.

### Revised completion boundary

- Deliver the current dependency graph, v4 telemetry/readers/scores, and the isolated runtime with the smallest build/install and wrapper/settings integration needed to use it.
- Complete a bounded, explicit transition for the actual legacy state. Investigate and resolve encountered differences case by case; do not require them to fit an automatic whitelist or expand a compatibility framework to handle them.
- An unfamiliar layout is not itself a blocker. Concrete uncertainty about ownership, destructive effects, credentials, or authorization still requires resolving that uncertainty before acting; this is not permission to overwrite unrelated data.
- Remove automatic legacy discovery/retirement/recovery orchestration from the shipping design. Existing experiments remain evidence, not requirements or sunk-cost reasons to retain code. Review `scripts/langfuse-legacy-{ownership,transaction}.py`, `scripts/migrate-pi-langfuse-shared.py`, the historical profile registry and their dedicated tests for removal from the candidate; retain only genuinely necessary small pieces without duplication. Preserve useful private evidence before removing task-owned source.
- Simplify within the changed subsystem: eliminate unused dependencies/code and redundant representations or validation paths where behavior and safety remain covered. Do not broaden this into unrelated repository cleanup or introduce new frameworks.
- Verification must establish the actual fresh/reused transition and preserved behavior. A generic legacy-state matrix, automatic crash-recovery system, or capability for arbitrary future migrations is not an acceptance criterion.
- Keep normal source/integrity validation, targeted regression tests, final review/gates, and separate publication/deployment/integration approvals. Scope reduction does not waive security or change authority.

Implementation remains dependency-first. Latest stable direct/transitive runtime AND development versions are targets, not merely versions allowed by upstream ranges. A clean audit is not currency proof. If a coherent supported graph requires a retained older dependency, obtain an explicit version/reason/revisit exception. Do not fabricate compatibility with broad overrides or ambient type shims.

## Baseline state and provenance at plan creation

- Root HEAD at inspection: `85e075806634fa501d092b6b869491ff486dba57`.
- Langfuse fork clean at published `0ba150f5bd38c1e282feec5a488a918e6076063b`; upstream npm 1.7.0 source `1c4dd956597af272d1869ce897e922d7702845fe`.
- No maintained source, fork, installer, wrapper or settings changes made during investigation. Only Beads, private investigation artifacts and this plan changed.
- Preserve unrelated untracked plans:
  - `.pi/plans/2026-08-18-telemetry-preproduction-contract-design-plan.md`
  - `.pi/plans/2026-10-01-laya-chat-shadow-routing-design-plan.md`
- Prior pi-7zn8 publication grants are consumed. No history rewrite or reuse of old approval.
- Baseline completed after plan approval: all 13 commands ran; 12 passed, root pytest failed its existing instruction-size budget (1 failed/1572 passed). Evidence `.pi/reviews/pi-ox9n/baseline/gate.json` and logs. Exact failure `tests/test_context_architecture.py:26`: `((7451 + 6835) * 5) <= (15784 * 4)` is false. No maintained source edits preceded this baseline. Do not weaken policy/test or claim release readiness. Fork typecheck/full tests, root install/layout/shell/Ruff, routing/role evals, both prior installed proofs and vendor pins passed. No final release gate yet.

## Investigation evidence

Everything below is under `.pi/reviews/pi-ox9n/` unless noted.

### Dependency evidence

- `baseline-production-audit.json`: 26 affected production package entries (4 high, 22 moderate).
- `unique-production-advisories.json`: 9 unique advisories (5 high, 3 moderate, 1 low). Do not confuse unique advisory severities with package rollup counts.
- `baseline-full-audit.json`: 27 entries including 1 additional low development entry.
- `latest-direct-metadata.json`, `compatibility-metadata.json`: npm registry facts.
- `latest-resolution-probe/resolution.log`: strict all-latest graph fails ERESOLVE: published `@langfuse/otel@6.0.1` requires core `^2.0.1`, conflicting with core 3.0.0. OTel 2.12.0 requires API <1.10.0.
- `compatible-resolution-probe/`: diagnostic-only OTel 2 graph, audit zero. **NOT approved/adopted.**
- `development-resolution-probe/`: latest Pi SDK 1.4.0, TypeScript 7.0.2, tsx 4.23.15 with diagnostic OTel 2 graph; audit zero but 41 older development entries remain. Its ten OTel production older entries are also rejected, not the selected graph.
- `development-resolution-probe/path-aware-older-version-inventory.json` corrects name-only parent attribution in `older-version-inventory.json`. Prefer `resolvedParents`; four name-only false associations were AWS token-providers, nested agent-base/https-proxy-agent, and proper-lockfile's nested retry.
- `development-peer.md/json`: independently classified exact pins, same-major candidates and cross-major parent migrations. Source/edge claims checked; compatibility remains unverified.

Latest production target: Langfuse client/core/tracing/otel 6.0.1; OTel API 1.10.0, core/resources/context-async-hooks/sdk-trace/sdk-metrics/sdk-logs 3.0.0, exporter-trace-otlp-http/otlp-exporter-base/otlp-transformer 0.300.0, semantic-conventions 1.43.0, mustache 4.2.0. Recheck currency before final selection.

### OTel 3 source feasibility

- `sdk-investigation/packs.json` and `packs/`: exact npm archives with SHA512 integrity verified before safe extraction.
- `sdk-investigation/upstream-v6.0.1/`: read-only upstream clone at Langfuse tag v6.0.1, commit `d979228b7b4d55a5334d49600e99d2d36cae4add`.
- `sdk-investigation/otel3-source-probe/`: disposable source-copy experiment, **not installed @langfuse/otel package proof**.
- Necessary SDK source changes proved so far:
  - Four imports: `@opentelemetry/sdk-trace-base` -> `@opentelemetry/sdk-trace` in `span-processor.ts`, `MediaService.ts`, `span-filter.ts`, `size-limited-span-exporter.ts`.
  - `new SimpleSpanProcessor(exporter)` -> `new SimpleSpanProcessor({ exporter })`.
  - `new BatchSpanProcessor(exporter, options)` -> `new BatchSpanProcessor({ exporter, ...options })`.
  - Package peer metadata must match implementation; peer-only widening is broken.
- Consumer changes required: `BasicTracerProvider` -> `TracerProvider` from sdk-trace; `AsyncHooksContextManager` removed in OTel 3, use `AsyncLocalStorageContextManager`; import resources directly instead of sdk-node re-export.
- `red-unmodified.log`: missing sdk-trace-base proves source import incompatibility.
- `red-imports-only.log`: removed AsyncHooksContextManager export.
- `red-constructors.log`: both export modes fail with undefined exporter/shutdown after import-only adaptation.
- `green-source-port.log`: 3 custom contracts PASS (both export modes, real Langfuse observations, parenting, masking, default filtering, flush/shutdown, environment resources).
- `upstream-tests.log`: 58 copied upstream contracts in six files PASS. Includes loopback HTTP ingestion headers/compression, app-root/filter and size-limited exporter tests. Tests adapted only for new provider/import names and source paths. Not full upstream SDK suite.
- `typecheck.log`: source TypeScript 7 check PASS with real SDK declarations and `skipLibCheck:false`; no ambient compatibility shims.
- `installed-tree.json`, `final-audit.json`: actual source-probe dependency install, npm ls valid and audit zero. Processor remains local source import, not distributed package; no fresh/reused product delivery claim.

### Runtime reachability limits

At baseline, maintained `getRuntime()` imported sdk-node only for its resources re-export and instantiated BasicTracerProvider, not NodeSDK. Langfuse's default transport is OTLP HTTP, not a gRPC server. This explains an avoidable dependency chain, not universal non-exploitability. The probe confirms direct OTel 3 resources preserve env attributes without NodeSDK. No live process/network exposure was measured.

### Reported migration warnings

User reported delayed OTLP ingestion, ingestion API calls lacking an SDK header, and deprecated endpoint calls. Baseline source mapping (before remediation):

- Baseline fork's installed Langfuse 5.3 exporter sets SDK headers, but not `x-langfuse-ingestion-version: 4`.
- `forks/pi-langfuse/src/langfuse.ts:234–286` custom ingestion has Authorization/Content-Type only, writes `/api/public/ingestion`.
- Same file `:665–740`: legacy `/traces?limit=1` capability probe and `/traces/{id}` visibility polling.
- Same file fallback writes trace/span/generation records through ingestion; score flush shares that endpoint.
- `forks/pi-langfuse/src/quality.ts:701+`: `/traces`, `/observations` readers.
- `pi/agent/bin/agnt_lib/langfuse.py:153+`: legacy observation/trace lists and bounded trace-discovery metadata.
- v3 score reads are supported. Legacy **score-create** ingestion is not itself deprecated; avoid false claims. Moving custom score writes to supported score batches is a justified consolidation, not proof every old score request will break.
- Live emitter attribution is NOT verified; source matches warnings but deployed version is unknown.

Primary docs captured: `langfuse-v6-migration.md`, `deprecated-api-migration.md`, `langfuse-compatibility.md`. URLs:
- https://langfuse.com/docs/observability/sdk/upgrade-path/js-v5-to-v6
- https://langfuse.com/faq/all/deprecated-api-migration
- https://langfuse.com/docs/compatibility

Important semantics: v6 removes trace IO setters and legacy methods; root observation carries IO. Observations v2 uses cursors, explicit field groups, raw-string IO, bounded start times, and observation rows rather than trace objects. Cloud's documented legacy cutoff is 2026-11-16, but selected deployment is self-hosted; do not present Cloud's deadline as proof of this server's behavior.

## Approved architecture and boundaries

### Maintain source and exact projections

Keep consumer changes in `forks/pi-langfuse`, not an independent root overlay that bypasses fork publication requirements. Preserve old published commits; append history. Root gitlink/projections move only with required publication evidence, requested separately at an immutable verified candidate.

Maintain a narrowly scoped OTel 3 port of upstream Langfuse 6.0.1. Prefer a small licensed source package under the consumer fork (proposed `vendor/langfuse-otel/`) over a new full SDK fork if equivalent reproducibility/tests can be proved. Package must retain ESM/CJS/declaration contracts and provenance. Decide exact build packaging with a bounded experiment; do not hand-edit generated dist or pretend a source-import probe proves installed distribution. Exact upstream source + patch + pinned build inputs + deterministic generated inventory required.

### Isolated delivery

- Projected consumer and its locked dependency tree become an immutable content-addressed release under `<DEST>/runtime/pi-langfuse/releases/<content-hash>`.
- Actual patched SDK package is an installation input, not a peer-range override or borrowed node_modules symlink.
- Use frozen install and explicit runtime peer validation. Pi host packages must not be bundled into runtime; Pi docs say host supplies them. Test chosen production install mechanics. Do not use `--legacy-peer-deps` to hide OTel incompatibility; ordinary Pi host-peer suppression is a distinct contract and must not suppress runtime compatibility evidence.
- Wrapper and quality module resolve from the exact same verified release. No shared npm fallback. Keep extensions disabled on the package entry so wrapper registers once.
- Stage and verify code, dependency lock/inventory, and hashes before activation. Reused release must match; corruption fails closed, not silent repair.
- Keep release preparation and settings/wrapper activation simple and explicit, using the existing deployment path where practical. Preserve the matching prior release/config and sufficient recovery evidence; do not add automatic migration or recovery orchestration. No release/backup pruning by default.
- Existing shared npm Langfuse may leave unreachable vulnerable dependencies. Inspect the actual state and carry out a bounded one-time transition with understood ownership, exact files/manifest/lock effects, recovery evidence and unchanged unrelated package bytes. Resolve shared dependencies or unfamiliar layouts case by case rather than imposing a blanket unsupported-state rejection. Do not blindly prune/update, discard unrelated changes, or perform live runtime deletion under current authority.
- Actual deployment remains separately approved; all installer development runs use named temporary test destinations, not ~/.pi.

### Full v4 endpoint migration

- Default OTLP HTTP export must send version 4 header, SDK provenance and real v6 semantics; verify on local HTTP receiver for both compression modes.
- Remove legacy trace/observation ingestion and legacy capability/visibility endpoints from executed paths. Header-only fix on `/ingestion` is not migration.
- Preserve reliable delivery with stable original trace/span IDs, finite byte bounds, sanitized fallback data, explicit partial failure and deadline-bounded shutdown. Determine tested v4 delivery/retry mechanism before retiring old fallback. Do not treat read-side visibility delay as transport-failure proof; do not simply delete fallback guarantees.
- Move custom scores to supported batch score writes if consolidating with v6, preserving entity IDs across retries, partial rejection handling, request count/byte limits and no raw-media retention.
- Replace fork/Python readers with bounded Observations v2 cursors and explicit field groups. Reconstruct trace rows from observations without inventing totals/completeness, leaking additional IO or counting every child as a trace. Preserve quality public method names, response completeness/gaps and cancellation/time limits. Verify downstream improvement/session joins and zero/missing usage semantics.
- No remote evaluators, traces or credentials changed by code verification.

## Execution tasks

### 1. Settle selected graph and package the dependency port

Files: fork `package.json`, `package-lock.json`, new vendor source/build/provenance/tests; root package/fixture manifests only where actual SDK integration requires updates. Read relevant package docs and Pi SDK docs before changes.

1. Run documented current fork/root baseline once; save commands, exits and failures. Existing audit baseline need not be repeated unchanged.
2. Build a path-aware inventory for selected OTel 3 graph, not the rejected OTel 2 diagnostic graph.
3. Investigate 41 older development entries. First same-major cohort, with exact parent API/contracts and real Pi 1.4 tests; then residual cross-major clusters. Do not blindly override all versions or claim latest because audit is clean. If this expands into broad Pi/provider maintenance, obtain bounded scope decision rather than silently creating a system-wide Pi fork.
4. Port SDK source with regression-first tests already demonstrated in probe; package real ESM/CJS/types. Verify upstream focused contracts against built/installed package, not source aliases.
5. Resolve peer metadata coherently; refresh locks deliberately. Audit and currency-inventory both runtime and build/dev trees. No ambient declarations hiding signature breaks.

### 2. Port consumer bootstrap and v4 telemetry

Files: `forks/pi-langfuse/src/langfuse.ts`, `src/types.ts`, `src/handlers/agent.ts`, affected helpers/tests, `types/langfuse-runtime-shims.d.ts` (replace/remove broad shims only after genuine type checks).

Test first: actual OTel 3 initialization/context coexistence/env resources; version4 HTTP headers; root IO; stable retry trace/span/score IDs; bounded batch splitting including oversize event and later valid entries; partial errors; cancellation/deadline; privacy/media and cache-zero behavior; no deprecated endpoints. Preserve real Pi lifecycle/nested tool tests with current SDK.

### 3. Migrate quality and Python readers

Files: fork `src/quality.ts`, `test/quality.test.ts`; root `pi/agent/bin/agnt_lib/langfuse.py`, `tests/test_langfuse_evaluators.py`, relevant `tests/test_improve*.py`, quality fixtures/consumers/specs discovered from imports.

Test first: v2 fields/time bounds/cursor progress, repeated/malformed cursor, truncated grouping, absent versus null/raw IO, zero/missing usage, root detection, session correlation and bounded failure. Preserve `ServiceEvidencePort` names and `BoundedEvidencePage` contract, including honest `totalAvailable` omission. Score/annotation APIs remain supported; do not change them merely because warnings mention deprecated reads.

### 4. Implement isolated delivery and projections

Files: `scripts/update-pi-config.sh`, new bounded runtime install/build helper as needed, `scripts/apply-pi-package-patches.sh`, `scripts/verify-pi-langfuse-package-patch.sh`, `scripts/check-vendor-pins.sh` only to accurately validate append-only provenance, `patches/pi-packages/`, `pi/agent/settings.json`, `pi/agent/extensions/langfuse-config-env.ts`, layout checks and package/update tests.

First remove the out-of-scope automatic migration architecture and consolidate duplicated implementation within this task. Keep the minimal reproducible build/install path and integrate wrapper/settings activation. Document and verify the explicit transition for the actual legacy installation; resolve differences without building a general legacy-state engine.

Test source/dependency preparation before activation, read-only preview, actual fresh/reused regular installed trees, unchanged reuse, failed installation, source/integrity/path checks, recovery evidence, preservation of unrelated state, and real Pi loading with single registration. Retain useful historical npm integrity and exact patch provenance as evidence, not as a new automatic supported-version registry. No source-only/symlinked test substitution; no requirement to ship the experimental journal/coordinator or its generic failure matrix.

### 5. Documentation, independent review, final gates and closeout

Docs: fork README/AGENTS as appropriate, root README, `pi/README.md`, `patches/pi-packages/README.md`, relevant architecture/spec/upstream profile and this plan.

- Describe minimum server, v4 endpoint semantics, maintained SDK port, runtime isolation, exact pins/build proof and recovery; separate dependency currency/security from live status.
- Independent review after implementation; do not reuse investigation reviews as final code review.
- Commit fork task changes only after actual fork/typecheck/contract gates. Ask separate exact publication approval; never bypass existing vendor publication gate.
- Stage task-owned root candidate only, run complete gates on unchanged candidate, commit local atomic task changes. Then `agnt work direct-closeout pi-ox9n --outcome success --reason "..."` only if every acceptance criterion passes.
- If blocked/unfinished, keep Bead open and save exact progress/artifacts. Do not report success or close to enable handoff.

## Verification commands

Existing commands to preserve; new focused helpers must be documented and executed after implementation:

```bash
# NPM_CLI must be an absolute path to verified npm 12.2.1 npm-cli.js.
(cd forks/pi-langfuse && node "$NPM_CLI" ci --ignore-scripts && node "$NPM_CLI" run typecheck && node "$NPM_CLI" test)
(cd forks/pi-langfuse && node "$NPM_CLI" audit --omit=dev --json)
(cd forks/pi-langfuse && node "$NPM_CLI" audit --json)
npm ci --ignore-scripts
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
scripts/verify-pi-langfuse-package-patch.sh
scripts/verify-pi-archimedes-package-patches.sh
scripts/check-vendor-pins.sh
```

Current source-probe reproduction (not release gates):

```bash
cd .pi/reviews/pi-ox9n/sdk-investigation/otel3-source-probe
node_modules/.bin/tsx --test port.test.ts
node_modules/.bin/vitest run
node_modules/.bin/tsc -p tsconfig.json
npm ls --all --json
npm audit --json
```

Run probe/contract subprocesses with LANGFUSE_*, PI_LANGFUSE_* and OTEL_* environment variables stripped, as done in saved logs. No inherited live credentials. E2E with actual backend needs separate authorized scope.

## Advisory review synthesis

`delivery-peer.md/json` verified current shared-root reification, weak package-only recovery and symlinked proof gaps; isolation approved. **Rejected recommendations:** root-owned overlay bypassing maintained fork/publication gate; treating legacy-peer-deps as dependency compatibility evidence.

`development-peer.md/json` verified 41 older dev entries and path-aware parent corrections. Same-major/major groupings are investigation priorities, not approvals or compatibility claims. Both peer metrics annotated with verification and limitations.

## Execution context

The Bead contains current implementation and verification evidence. Dependency/SDK ports, both readers, v4 transport/scores, legacy transport retirement, isolated release preparation, and wrapper resolution have been implemented with focused and installed-package evidence. Earlier registry failures were superseded by saved zero-vulnerability audits; the final candidate still needs fresh combined gates.

The automatic legacy ownership/retirement/journal/coordinator was removed from the shipping candidate; private experimental evidence remains. Minimal updater/settings activation now passes actual temporary-destination fresh/reused installation and Pi-loader/privacy/quality contracts. Legacy shared data remains untouched: an actual live transition needs a separate exact preview and approval, not general migration machinery. The fork is locally committed at `f1024ce99d1fe3a360d3f220db75467aaad30894`; its operational publication verifier passes. Four independently verified implementation-review findings were fixed. Approval `pi-3f0v` separately permits bounded, policy-preserving compression of the two existing instruction files; independent review and 105 context tests verify that repair. The exact fork commit was subsequently published under single-use approval `pi-mhd9`; the vendor-pin gate passes. Root final gates and main integration status are tracked in pi-ox9n, alongside current evidence and decisions. No live deployment/publication/push/integration authority is added by these implementation proofs.
