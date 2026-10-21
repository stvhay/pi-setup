# Current Pi Plugin Upgrade Implementation Plan

**Issue:** pi-7zn8 — Upgrade Pi plugins and SDK while reducing maintained patches
**Design:** approved in session 2026-10-21; latest releases with behavior-preserving patch reduction
**Date:** 2026-10-21
**Branch:** upgrade/plugins-2026-10

## Goal and boundaries

Upgrade configured Pi packages to reviewed current releases, align test SDK to live 1.3.0, and keep only necessary custom patch behavior. Work in tracked source, not ~/.pi. Preserve old fork history and unrelated plans. Approval includes task-owned local commits; no push, merge, live deployment, Craft binaries, secrets changes, or broad refactoring.

Base superproject: 76bf0dde8ed341de7ef69053eed227b66552dfd3.
Original fork gitlinks: Langfuse e5596e8df6136b07db143025ef400d325454b958; Archimedes 8590ec0e1063811f86d1417ded9c2aeb48fd73b6.
Fetched upstream targets: Langfuse v1.7.0 = 1c4dd956597af272d1869ce897e922d7702845fe; Archimedes v2.11.1 = a44f94267239db0ef5d36d18d93391bf9d51c182.
Other targets: pi-observational-memory 3.1.4; pi-caveman 1.0.11; already-current clipboard 0.3.9 and BetterWright 2.9.0.

## Architecture and invariants

Keep exact npm bases plus reviewed production-only fork projections. Prefer native Pi event transport and accounting rather than retain redundant old internals. Preserve subagent isolation/limits, first-stop termination evidence, bounded outputs, public result/model contracts, privacy constraints, Langfuse quality ports, and keyed Beads status layout. Changes to default-enabled components, bridge delegation or telemetry capture must not silently widen capabilities.

Read-only peer artifacts (advisory, verify source before acting):
- /Users/hays/.pi/runtime/75fbac316d90bbaa8a2ba2635364e7d83992b94391eb3f1b2b203ce44e61aba3/delegated-results/37600878-d30b-49e8-9f1f-94a34b53a420/child-0.json
- /Users/hays/.pi/runtime/75fbac316d90bbaa8a2ba2635364e7d83992b94391eb3f1b2b203ce44e61aba3/delegated-results/230a147d-ce77-474e-b80b-02bed1c4c267/child-1.json

## Acceptance

- Current exact patched npm bases, matching local fork projections and pinned package integrities.
- SDK 1.3.0 tests exercise actual modern package interfaces, not old mocks only.
- Observational memory config retained and compatible; other configured Git packages reviewed at explicit heads before any later live refresh.
- Custom limits/isolation/results/privacy/quality/footer contracts retained or retired with equivalent executable proof.
- Package proofs establish zero-fuzz forward/reverse application, idempotence and byte-exact production projections.
- Full repo and fork checks, independent review, updated docs and retained/retired patch inventory.
- Existing runtime untouched; no push/merge/deploy without separate approval.

## Task 1 — baseline and SDK / uncomplicated packages

Files: package.json, package-lock.json, pi/agent/settings.json, tests/test_pi_packages.py, affected SDK-facing tests/extensions, pi/README.md.
Run existing baseline once before edits. Update pin/config assertions first and observe expected failures. Update SDK lock using npm with scripts disabled; then npm ci --ignore-scripts. Bump memory pin; keep unpinned packages unpinned but record verified target versions/heads for later deployment. Preserve package filters.
Focused: .venv/bin/python -m pytest tests/test_pi_packages.py tests/test_agent_os_compat.py tests/test_subagent_workaround.py.

## Task 2 — Langfuse projection [depends on SDK]

Files: forks/pi-langfuse; patches/pi-packages; scripts/apply-pi-package-patches.sh; scripts/verify-pi-langfuse-package-patch.sh; scripts/update-pi-config.sh; pi/agent/extensions/langfuse-config-env.ts; pi/agent/bin/agnt_lib/improvement.py; corresponding tests/docs.
Start new local vendor line from immutable upstream without rewriting old branches; request exact Git setup if necessary. Port contract tests before custom production edits. Reuse native chunk splitter with hard 3,000,000-byte shared ingestion ceiling and oversized-event continuation/stable score retry IDs. Preserve generation-input-only valid media, REST media omission, privacy-safe tool bytes/errors and shutdown budgets. Retain quality.ts public port. Keep upstream codemode/actual-provider/retry/cache/system-state telemetry. Preserve valid-first zero/missing usage semantics with canonical cache keys; make historical consumer accept both aliases without double counting. Constrain new path-capture switch in managed wrapper. Verify fallback-total ceiling semantics before adopting a delivery change.
Run fork npm run typecheck and npm test; expand exact installed-package proof beyond quality to ingestion/media/tool/cache behavior.

## Task 3 — Archimedes projection [depends on SDK; serialize shared root edits]

Files: forks/pi-archimedes; five existing patch families; scripts/verify-pi-archimedes-package-patches.sh; applicator/deployment scripts; pi/agent/extensions/archimedes.ts; subagent-error-workaround.ts; related tests/docs.
Use native pi.events and /events export; retire singleton /bus transport. Retain public subagent agents/types/config ports, execution profiles/limits/output caps/guards, stream reconstruction and result evidence. Integrate upstream schema split, accepted-todo forwarding, outcome model and native accounting without contradictory success states or cost duplication. Block bridge path from bypassing custom enforcement. Preserve one-shot isolation under Pi 1.3 including MCP. Retain bounded outputs and align structuredContent/details/contracts. Preserve keyed sorted/footer row semantics via small adaptation to upstream layout. Preserve typed ask input and settings controls. Review new default-enabled sudo/web/onboarding before adoption; no unapproved privilege/capability expansion.
Run focused fork tests and per-package typechecks, all fork tests and installed projection proof. Document any non-additive live-cost display difference rather than silently change it.

## Task 4 — moving package review and documentation

Read-only compare installed Git package heads to current remote defaults (Langfuse skills, Matt Pocock skills, Ponytail). Preserve unpinned policy and resource filters unless discovered incompatibility requires decision. No ~/.pi checkout mutation. Record desired deployment heads/versions and risks. Update README, pi/README.md, patches README and relevant upstream profiles; exact retained/retired inventory.

## Task 5 — stable candidate and closeout

Full commands:
```
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
Run final complete gate after candidate stable, independent review, diff checks and task-owned staging. Preserve baseline signatures separately from regressions. Commit only task-owned source and call direct-closeout only after all acceptance and publication gates satisfied.

## Publication gate / blocker

scripts/check-vendor-pins.sh requires staged gitlinks already reachable on configured remote vendor branches; CI checks before submodule checkout. New custom fork commits cannot satisfy this without separately approved publication. Do not weaken/remove gate or commit unretrievable gitlinks. Continue local implementation/tests, then request exact bounded vendor push approval when remote identity, source SHAs, tests and expected refs are known. If approval denied/unavailable, retain unfinished local work and checkpoint; do not claim completion. Root integration/deployment remain separately gated.

## Progress checkpoint — SDK / memory phase

- Root branch created and pi-7zn8 claimed. No implementation commits yet.
- Baseline six commands passed, including 1,548 pytest tests. Evidence: `.pi/reviews/pi-7zn8/baseline.json` and baseline logs.
- package.json/package-lock.json now pin SDK 1.3.0; local repo node_modules installed with scripts disabled (npm audit reported zero vulnerabilities).
- Tracked memory pin now 3.1.4. README and compatibility row updated; historical RPC baseline explicitly distinguished from current test SDK.
- Test-first pin assertions failed as expected. SDK revealed changed `ExtensionRunner.emitBeforeAgentStart(trigger, systemPromptOptions)` signature and hoisted newer undici/brace-expansion; fixtures/assertions updated, no production workaround added.
- Focused repair: 16 passed (`sdk-memory-green.log`). All 1,548 tests then passed on SDK 1.3.0 (`sdk-full-pytest.log`). This is intermediate SDK-phase proof, NOT final upgrade gate.
- Fork worktrees remain untouched on their original branches: Langfuse `fix/pi-1dit-cache-zero`, Archimedes `work/pi-840u-idle-limit`. Upstream target tags fetched only. Start separate local vendor lines for porting; do not rewrite old branches.
- Git packages already equal remote default HEAD as of 2026-10-21: langfuse/skills `127253d0e26dfa77fb6d732d1b70c36625581eb4`; mattpocock/skills `5beb35b040e3de97e54fa9e386d7e42d15c295c2`; DietrichGebert/ponytail `09c434ab73ca43761c5d8b0c5d341926c2fba710`. No updates required. Live Matt Pocock checkout has modified package-lock.json; Ponytail has untracked package-lock.json. Preserve both; no live mutations authorized.
- Remaining: both fork migrations, downstream interfaces/consumers, regenerated projections/proofs, current rolling-package observations/delivery bounds, full verification/review. Caveman latest is 1.0.11 but live still 1.0.10; preserve unpinned declaration and defer actual refresh to authorized delivery.

## Progress checkpoint — Langfuse fork port (reserved child 805dc559)

- Resumed checkpoint `0960646f133a4cf09d327113141e745f`, transition `4680da2262f37b2fa5e808b037f6d385`; transition was already attached. Ran prime/show/recover/ready/direct-start. Prior outcomes and root dirty work preserved.
- User explicitly approved new local fork branches in existing checkouts: `forks/pi-langfuse` / `vendor/pi-setup-170` from `1c4dd956597af272d1869ce897e922d7702845fe`, and `forks/pi-archimedes` / `vendor/pi-setup-2111` from `a44f94267239db0ef5d36d18d93391bf9d51c182`. Local edits/tests/commits only; no merge, deletion, push, or deploy. Only Langfuse branch created so far.
- Langfuse local port committed as `0ba150f5bd38c1e282feec5a488a918e6076063b`; fork clean. Old custom branch/tip `e5596e8` preserved. No publication; root gitlink remains unstaged/uncommitted.
- Retained media-safe generation inputs, REST sanitization, private tool-byte/error states, quality public ports, valid-first cache aliases/zeros. Adopted upstream canonical cache keys, TTL/reasoning behavior, native ingestion splitter, nested tools, lifecycle and v4 propagation. Shared request cap is 3,000,000 bytes, including scores; oversized events do not block later events; score retries retain envelope IDs.
- Explicit delivery decision: no default aggregate fallback-size skip, preserving old fork behavior. Upstream total-size threshold remains an explicit opt-in. Shutdown still bounds elapsed delivery. Regression test covers 36 MB aggregate and oversized configured per-request budget.
- Fork dev SDK pinned to 1.3.0 and lock regenerated. Final staged-candidate typecheck and **181 tests PASS**, with telemetry env removed from test subprocess only. Evidence: `langfuse-local-gate.json`, `langfuse-final-typecheck.log`, `langfuse-final-tests.log` under `.pi/reviews/pi-7zn8/`.
- Independent read-only Astra review found no concrete new important defects; reran 124 focused fork tests and 15 consumer tests. Original report and normalized empty findings: `langfuse-peer-review.json`, `langfuse-review-findings.json` (schema validation passed). Review excludes unfinished package/deployment integration.
- Root `improvement.py` accepts canonical and historical cache-read keys, preferring valid canonical values without summing aliases. New alias tests observed RED; entire `tests/test_improvement.py` now **223 PASS**. Six session-link tests now use test-owned temporary checkouts instead of inspecting the live dirty submodule. Ruff and diff checks pass. These root changes remain uncommitted with prior SDK/memory work.
- Upstream dependency risk remains: initial fork npm install reported 28 vulnerabilities; after SDK update 27 total, 26 production (22 moderate, 4 high). See `langfuse-production-audit.json`; do not run automatic/force dependency fixes or claim release readiness. Some recommended fixes require an unrelated OTel major upgrade.
- **New handoff limitation:** installed and tracked `work_lifecycle.workspace_snapshot()` reject changed gitlink directories with `ValueError: unsupported changed workspace entry`. Read-only reproduction confirmed; filed `pi-ys12`. Do not hide/revert gitlinks or change outcomes to bypass this. No lifecycle production edit or live deployment authorized. Manual durable continuation details: `.pi/reviews/pi-7zn8/langfuse-checkpoint.json`.
- Archimedes remains untouched on `work/pi-840u-idle-limit` at `8590ec0e1063811f86d1417ded9c2aeb48fd73b6`.
- Next: constrain wrapper `LANGFUSE_CAPTURE_PATHS=false`; regenerate Langfuse production projection/proofs against npm1.7.0 (exact integrity/ancestry), then Archimedes port. Root pin remains old until integration artifacts are coherent. Complete docs, package proofs/full release gates/final review; exact remote publication approval still required before root gitlink commit. No successful closeout yet.

## Progress checkpoint — integration and Archimedes runtime

- Langfuse managed wrapper now forces `LANGFUSE_CAPTURE_PATHS=false`, including hostile saved/environment configs. Exact 1.7.0 production projection regenerated: `patches/pi-packages/pi-langfuse-1.7.0.patch`, SHA256 `a9c8028bd392bf242ebbf287d55655a74649731702e342a7c0e39c195a1f34de`.
- Langfuse npm integrity/source lineage/whole-file equality/reverse/idempotence proof passes **113 installed tests**, including actual wrapper/quality ports/privacy/subscription alias restoration. Root package/deployment tests **128 PASS**; layout/shell/Ruff/diffs pass. Profile/docs distinguish local candidate from unpublished state. Langfuse root gitlink **staged**, not committed; previous checkpoint's unstaged wording is historical.
- Approved Archimedes branch `vendor/pi-setup-2111` created at `a44f94267239db0ef5d36d18d93391bf9d51c182`. Old `work/pi-840u-idle-limit` untouched. Upstream baseline per-package typechecks and **2,511 tests PASS**. pnpm install used `--ignore-scripts`.
- Archimedes partial port remains **uncommitted**: 13 dev manifests pin SDK 1.3.0; retained public agents/types/config ports; policy/profile/limits/output caps; keyed footer over native layout; typed bounded stream reconstruction, cost splits, first-stop/error evidence; native accepted-todo forwarding, session-qualified sources, host event handle; spawn guard/one-shot isolation with new `--no-mcp`; ask idle leases plus native correlation/cancellation; deadline/idle controller and bridge bypass protection for contract-bearing execution.
- Explicit prompt-template macros remain available in one-shot mode, as historical approved contract requires (`f277470`, `docs/plans/done/2026-08-09-subagent-one-shot-output-caps-v2.md`). Do not add `--no-prompt-templates` as incidental cleanup. Other ambient resources stay disabled.
- Managed execution preserves failed output-limit/user-abort termination and clears contradictory native success outcomes. Plain upstream internal calls without managed execution retain native outcome semantics. Tool registration still needs execution/profile/limit fields wired: **helpers passing does not mean end-to-end managed enforcement is complete**.
- Latest intermediate Archimedes gate: all per-package typechecks + **2,668 tests PASS** (`archimedes-runtime-typecheck.log`, `archimedes-runtime-full.log`). Contract-first red/green logs cover footer, policy, stream, outcome reconciliation, spawn, execute and active-bridge bypass. Actual SDK 1.3.0 no-model subprocess smoke loads child guard and honors one-shot flags.
- **Human decision:** use native footer timing; footer totals update after result persistence, while live subagent progress keeps cost. No separate pending-cost footer/accumulator. Approved through transient ask after explaining no double counting and timing difference; no deployment authority added.
- Remaining: tool-schema/index dispatch wiring, bounded output/turn-token rendering, structuredContent and root workaround normalization, meta limit settings, ask payload compatibility, root native event adaptation and unwanted default-enabled plugin guards. Then exact Archimedes projections/proofs/docs, final independent review and complete gates. Publication still needs separate exact approval; no root implementation commit/closeout/deployment yet. Handoff gitlink bug `pi-ys12` remains unchanged.

## Progress checkpoint — complete local ports and root compatibility

- Both clean vendor candidates are committed locally: Langfuse `0ba150f5bd38c1e282feec5a488a918e6076063b` and Archimedes `59c57a18976f0d470bae8ae6d5704c6715f06ee6`. Their immutable gates passed 181 and 2,706 tests respectively plus typechecks. Substantive independent fork reviews passed; the earlier unsubstantiated Archimedes review is superseded by `archimedes-peer-review.json`.
- Exact npm production projections and upstream profiles now target Langfuse 1.7.0 / Archimedes 2.11.1. Both root gitlinks are staged, not committed. Langfuse installed proof passes 113 tests; Archimedes `--local-candidate` proof passes installed contracts plus actual SDK managed-report composition. Default remote availability gates remain intact and unfulfilled; local mode is not publication evidence.
- User chose managed JSON script results. Root schema/report normalization preserves native usage and execution facts, opaque artifact refs and termination evidence; non-inline bodies are omitted and inline answers share 12,000 characters. Full details/private artifacts survive. Native output contracts now reach the executor; routing-only fields remain local. Existing any-failed-child `isError` behavior remains, with available JSON still returned; native single/pre-dispatch failures without reports retain text-error rejection.
- Root uses native events; tracked settings disable new sudo/web tools and track no onboarding state. Native footer cost timing remains the explicit human decision above.
- Actual BetterWright 2.9.0 + Caveman 1.0.11 SDK composition exposed a whole-prompt freeze in `browser-permissions.ts`. Contract-first repair uses Pi 1.3 sections when no explicit forced prompt exists, retaining forced/legacy semantics and fail-closed policy checks. Twelve browser tests pass; actual package composition smoke now passes. Standalone Node smoke reports an existing module-type inference warning, not a failing runtime check.
- Actual observational-memory 3.1.4 config preserves every tracked setting and ratio threshold. Rolling Git heads still match remote defaults; user lockfile changes untouched. Compatibility docs record current observations without claiming live/browser/model acceptance.
- Latest root focused checks: 43 managed-result/wrapper tests and 37 package/browser/compatibility tests pass; Ruff/layout/shell/diff checks pass. Installed Archimedes proof rerun after forwarding repair passes. Full root final candidate gate and independent root review remain pending.
- Fork audit caveat remains as recorded above. No push, live deployment, root implementation commit or successful closeout. `pi-ys12` lifecycle gitlink handoff issue remains unmodified. Next: freeze/stage root candidate, independent boundary/projection review, exact vendor publication approval, then full final gates and task-owned root commit/closeout only if every gate passes.

## Progress checkpoint — root review and patch portability repair

- Staged root candidate `63ab0e6f...` received independent runtime and package reviews. Runtime review found no defects and independently exercised actual SDK codemode result/error/usage boundaries. Package review found Apple patch silently misreversing zero-context deletions. Fresh GPT-family adversarial verifier confirmed all three affected projections with exact integrity-checked npm fixtures; GNU patch was unaffected.
- Regenerated all six projections with three lines of context; fork commits/production bytes unchanged. Updated exact patch-hash pins. Current Langfuse patch SHA256 is `d41b50c3bfd1477f6eaa5299597a0699f9bd028d4f66b8dde8b422f0a57b6909`, superseding earlier zero-context checkpoint hash. Archimedes current hashes are in its tracked upstream profile and private `archimedes-2111-npm/patch-hashes.json`.
- Added actual-source round-trip tests for PATH/system patch, observed four intended red cases (format invariant plus Apple footer/subagent/Langfuse corruption), then all 31 package-patch tests passed. Both installed-package proofs now require PATH and distinct system-engine byte-exact reverse/reapply; fresh runs pass GNU 2.8 and Apple 2.0-12u11, plus 113 Langfuse / 859 Archimedes installed contracts and two managed-report tests.
- Scoped `.gitattributes` handles mandatory unified-diff context whitespace; added-source trailing whitespace and space-before-tab remain explicitly tested. Remote publication gates unchanged. Root package repair review/final complete gate remain pending; no publication/deployment/closeout occurred.
- Evidence: `root-runtime-peer-review.json`, `root-packages-peer-review.json`, `patch-portability-verifier.json`, `patch-portability-red.log`, `patch-portability-suite.log`, and refreshed installed-proof logs under `.pi/reviews/pi-7zn8/`.

## Progress checkpoint — partial publication, authentication blocker

- Repair review (`patch-portability-repair-review.json`) independently passed 12 exact-npm round trips across GNU/Apple patch, confirmed whitespace guards and unchanged remote gates, and found no new important defect. Staged reviewed candidate was `cd4f48cf...`; subsequent edits only record publication facts/tests.
- Approval `pi-x4j7` authorized one exact create-only attempt per vendor ref. Langfuse `vendor/pi-setup-170` published at `0ba150f5bd38c1e282feec5a488a918e6076063b` and was verified by fresh `ls-remote`. Archimedes was rejected for missing OAuth `workflow` scope. Approval `pi-2zxp` authorized one retry after human credential readiness; retry received the same rejection. Fresh reads confirm Archimedes ref remains absent. **All push grants consumed; no further push authorized.**
- Evidence: `vendor-publication-preflight.json`, `vendor-publication-result.json`, `archimedes-publication-retry-result.json`. Git credential-helper metadata identifies GitHub CLI; no raw credential config/token was printed or saved, no auth edit or alternate route attempted. GitHub API metadata calls timed out; doctor found no failures (only existing Beads health warning).
- Human must repair the credential actually used by Git (GitHub CLI workflow scope), then grant a new exact retry. Do not strip workflows, bypass auth checks, repush Langfuse, close unfinished work, or commit unretrievable Archimedes gitlink. No root implementation commit or live deployment. Local full verification continues; release readiness remains blocked.

## Local gate fixture correction

The first complete root gate passed npm/layout/shell/Ruff, then reported 1,565 passed / 8 failed. All eight direct-start/closeout tests inspected the developer checkout and hit existing `pi-ys12` (`unsupported changed workspace entry`) on staged gitlinks. Read-only reproduction confirmed a test-owned temporary checkout snapshots successfully. `tests/test_agnt.py` now isolates the three affected setup sites and supplies the closeout fixture's portable Beads file; all 189 tests in that module pass. Lifecycle production code remains unchanged. Original failure evidence is retained in `root-gate-before-fixture.json` and `root-pytest-before-fixture.log`; final gate must rerun on the new staged candidate.

## Publication resolved — final root candidate

- User reported authentication complete. Fresh preflight found unchanged staged candidate `9c60835e...`, clean Archimedes head `59c57a18976f0d470bae8ae6d5704c6715f06ee6`, correct HTTPS origin and absent target ref. New approval `pi-1c7e` authorized one exact create-only push. It succeeded; fresh `ls-remote` verified the exact remote SHA. Langfuse was not repushed. All push grants are consumed.
- Both vendor refs are now published; prior rejection/deferral paragraphs above are historical. Evidence: `archimedes-publication-auth-complete-result.json` and prior Langfuse publication record under `.pi/reviews/pi-7zn8/`. No credential edits, PR, release, merge, root push or live deployment performed by the agent.
- Previous unchanged local candidate passed all 1,573 tests, static checks, evals and installed proofs. Current edits update publication facts and their assertion only. Run a complete final gate on the newly staged candidate, including default Archimedes proof and vendor-pin gate, before the authorized atomic local root commit and direct closeout.
- Preserve unresolved separate lifecycle bug `pi-ys12`, inherited Langfuse dependency audit findings and unrelated plans/live lockfiles. Do not infer deployment or further push permission from this publication.

## Execution handoff

Continue directly in current session. Use handoff_bead with exact progress and evidence if context exhausted. Baseline and focused evidence belong under .pi/reviews/pi-7zn8/ (private/ignored). No false closeout for partial upgrade.
