# pi-pvcg implementation checkpoint

## State

**Pre-closeout snapshot:** implementation was in progress when this checkpoint was written; subsequent gate results, commit and closure are recorded canonically on pi-pvcg. This snapshot does not assert release readiness. Current checkout is `main` at `4674c05a82553e46762b5722e581eab4da851121`. An unrelated externally authored Craft release-pin commit advanced HEAD from `58c3b9f4013cf76752a96f2e069733aa3c2f6706`; its four files are disjoint from this task's dirty changes and remain untouched. Task-owned changes are uncommitted. No owner policy was activated, no live config was deployed, no remote effect occurred, and no session outcome/ownership history was rewritten. Close only after the final candidate gates and task-owned commit; no deployment or activation is implied.

Recover current scope from `bd show pi-pvcg` and `.pi/plans/2026-10-21-continuation-friction-plan.md`. Owner approved the keep/simplify/defer assessment; original four-package remaining-work mandate is superseded, not completed. Historical milestones below describe earlier candidates, not current acceptance. Preserve unrelated untracked plans dated 2026-08-18 (telemetry preproduction) and 2026-10-01 (Laya chat shadow routing).

## Current narrowed candidate (2026-10-21)

- `handoff_bead(progress=...)` persists useful current progress in one call via bounded stdin, with scope injected from ownership. Recovery returns the exact checkpoint; new progress cannot replace reserved checkpoint/transition state. No transcript copying.
- First ordinary `direct-start --scope-bead OTHER` captures an explicitly approved work set without handcrafted authority JSON. Selected Beads must exist/unfinished; existing assignment identities/effects cannot widen. Real-Git A→B→A journey passed without preconfigured queue.
- Root and planning/execution guidance now support coherent unfinished continuation, not closeout-only handoff or routine microtask pauses. Written skill scenarios and deterministic guidance checks added.
- Fresh independent narrowed review: `runtime:delegated-results/5f9a6913-8306-4083-8a62-336692eae756/child-0.json`, succeeded/exit 0, no findings; 111 tests and actual custom-host execve. Saved `.pi/reviews/pi-pvcg-narrowed/{report.md,findings.json}`.
- Separate installed Pi 1.3.0 TUI verifier actually replaced a disposable process, same PID/new boot, exact child/parent lineage, attachment before kickoff, preserved staged/unstaged/untracked bytes and partial outcome; no model calls/network. External Beads stubbed, real lifecycle/domain services. Evidence `/tmp/pi-pvcg-runtime.YhL2QEcP/`. This is not live user deployment or parent restart.
- Parent inspection of native argv found existing restart helper dropped CLI restrictions. Red-tested, then preserved parsed tool/project/context/model/resource options without old payload/session selectors. Review `eb6883cf-1d13-4834-a409-12cd57e90aa4/child-0.json` raised cross-checkout prompt/preload rebinding; four local red tests fixed by refusing custom cwd-sensitive launch options before staging/shutdown. Normal cross-checkout launches remain supported. Independent closure verified F1/F2; adjacent F3 (empty/quoted-tilde prompt reinterpretation on same cwd) was red-reproduced and fixed by keeping original tokens. Fresh F3 review `2495e506-c0c4-4a68-aef6-b9512821866e/child-0.json` succeeded/exit 0, three actual SDK resource-loader probes passed. Restart/handoff selection: 77 passed. Current actual Pi TUI proof: `/tmp/pi-pvcg-runtime-release.55cXGE/`, 21/21 checks, candidate copies exact; private copy `.pi/reviews/pi-pvcg-narrowed/runtime-proof/`. Final full gates remain next.
- Owner additionally approved small fixes for two old full-gate failures. Compact discovery descriptions without changing 8,000/1,000 thresholds; distinguish inline script commands from bare filename references. Pinned Craft skill/promotion state remains byte-for-byte unchanged. Context selection 106 passed; layout/Craft hashes, shell/Ruff/diff pass. Latest runtime/handoff/restart selection 73 passed before final positive control addition.

At this snapshot, no task commit or successful closeout yet. Next: stable candidate/full gates, then task-owned atomic commit and closeout if all narrowed acceptance passes. Consult the later canonical Bead outcome for completion, not historical remaining-work wording below.

## Owner amendment

The owner relaxed historical input-channel traceability at rollout. The design now records this amendment. Historical import may rely on recorded consent and must label provenance honestly (`historical-consent`, `inputOrigin=not-retained`), without pretending it is `human-ui`. Do not ask for renewed consent solely to reconstruct that historical channel. This does not authorize arbitrary policy widening, erase assignment restrictions/rejections/revocation, or bypass current deployment/platform gates.

## Implemented source

- `pi/agent/bin/agnt_lib/authority.py`: owner-global private state, explicit historical admission, immutable assignment scope, policy narrowing, revocation, bounded decisions, canonical Git common-directory identity, local dispatch resolution, and worker revalidation.
- `pi/agent/authority/full-delivery.json` and `SPEC.md`: tracked ceiling/template and honest trust/enforcement contract. Shipping the template activates nothing.
- `pi/agent/extensions/standing-authority.ts`: inspection/check tool plus explicit owner inspection/import commands. No startup activation/project scan.
- `pi/agent/bin/agnt`, `orchestration.py`, `runs.py`: new authority command; optional standing-assignment dispatch; separate standing run envelope; exact-grant/quality-claim isolation; actual worker repository/effect checks.
- `scripts/update-pi-config.sh`: anchored `/authority/` exclusion preserves private owner state while still deploying `agent/authority/` template. Disposable-destination regression test added.
- `pi/agent/bin/agnt_lib/work_lifecycle.py` and sibling spec: private checkpoints, repository-shared execution ownership, prepare/stage/launch/attach/cancel/recover, dirty-work hashes, A→B→A isolation, bounded unchanged-progress loops, and uncertain-effect recovery. Now wired to `agnt work`, direct-start/closeout, quality attempt readers, and Pi handoff.
- `extensions/lib/work-continuation.ts`, `bead-handoff.ts`, `lib/run-agnt-json.ts`: reserved child staging, source/parent/header binding, private launch-compensation capability, process replacement, automatic child attachment before tools, pending source discovery, and headless manifests. Disposable actual Pi TUI replacement is now verified; live parent-session replacement/deployment is not.
- `beads-footer.ts` and `work status`: distinguish yielding/paused/historical execution from immutable session linkage. Conflict guidance now offers checkpointed continuation, not `/new` first.
- `decision_rebinding.py`, sibling spec, `approvals.py`, and `beads-ask-bridge.ts`: recover an existing pending decision with current ownership and process-bound UI proof, re-present canonical scope, and require a fresh human answer. Private hashed resolver history preserves original metadata/grants. New question fingerprints include mode/custom-response contract; legacy mode needs explicit one-time UI verification.
- `delivery.py` and sibling spec: private owner-global effect reservations/receipts, per-resource/source retry bounds, revocation and uncertainty reconciliation, inherited native writer leases, and fresh observation distinct from immutable terminal history.
- `worktree_policy.WorktreeCreationAdapter`: tested native private task-worktree creation, dirty-source preservation, exact ref/path/commit observation, and surviving native-writer lease retention. Now wired to continuation CLI and Pi host reservation/recovery; orchestrated epic creation remains unfinished.
- Git identity/snapshot hardening: inherited `GIT_*` cannot redirect identity, configured foreign roots fail closed, nested directories normalize to one physical checkout owner, and nested-session parent/child validation retains exact file lineage.
- Direct-start lazily reuses private assignment or captures local-only single-Bead intent under active owner admission. Checkpoints cannot downgrade that scope to legacy direct authority.
- New tests: `tests/test_authority.py`, `tests/test_standing_authority.py`, `tests/test_work_lifecycle.py`, `tests/test_work_continuation.py`, `tests/test_continuation_extension.py`. Test-wide lifecycle/authority roots are isolated from live runtime.
- `tests/test_pi_packages.py`: isolated HOME in one package-discovery fixture. Standalone SDK reproducer showed live `~/.agents` discovery leaking into the fixture despite explicit `agentDir`; this is test isolation, not changed package behavior.
- Contract/status documentation: command README, `docs/AGNT-SYSTEM.md`, approved design amendment.

## Verification and review

Initial baseline: approvals/orchestration, 64 passed. Missing `tests/test_runtime_paths.py` was a mistaken baseline filename, not a product failure; relevant tests live in `test_runtime_artifacts.py`.

TDD: observed expected failures for missing authority/lifecycle services, command/consumer APIs, deployment preservation, worker-scope bugs, and lifecycle ownership/recovery defects before fixes. Latest lifecycle-only run: 21 passed. New authority/consumer tests passed individually and in the broad focused run.

Earlier foundation-focused command:

```bash
.venv/bin/python -m pytest tests/test_authority.py tests/test_standing_authority.py tests/test_work_lifecycle.py tests/test_approvals.py tests/test_orchestration.py tests/test_runs.py tests/test_worktree_policy.py tests/test_agent_os_compat.py tests/test_pi_packages.py tests/test_agnt.py tests/test_update_pi_config.py -q
```

Result: **458 passed, 1 failed**. Failure: `tests/test_agnt.py::test_context_health_reports_skill_discovery_budget`, assertion `751 > 1000`. `agnt context-health` reports 7,249 used / 8,000 limit, remaining 751, warning threshold 1,000. `git diff --quiet HEAD -- pi/agent/skills pi/agent/bin/agnt_lib/context_health.py tests/test_agnt.py` exits 0: all inputs to this failure are unchanged by this attempt. Do not claim a green release gate or weaken the assertion silently. Resolve during planned instruction consistency work.

At that foundation milestone, whole-project Ruff, `scripts/check-pi-config.sh`, `bash -n scripts/*.sh`, and `git diff --check` passed. Later full-suite results appear below; no task-owned commit or closeout performed.

Read-only `agnt doctor --json` after unexpected verification/environment findings: no failures; degraded solely because Beads embedded doctor cannot verify full database health. Query/conventions checks passed. No repair/config mutation attempted.

Independent boundary reviews produced concrete findings, reproduced with focused tests and fixed:

- authority: foreign worker checkout, artifact-only scope launching source-edit worker, ignored rejected decision refs;
- lifecycle: multiple owners of one checkout, blind retry after uncertain attach, post-stage source writes; follow-up coverage also blocks a new target reservation on another Bead's checkout;
- malformed explicit approval refs now fail closed instead of falling back to standing authority.

Private review refs:

- `runtime:delegated-results/ebd28ed3-afa8-461f-a037-ccd5a7e4c44d/child-0.json`
- `runtime:delegated-results/40368a2b-6a46-41c5-81f5-2e996c234c9c/child-0.json`

These were core reviews, not final acceptance review. Re-run independent boundary review after real adapters are connected.

## Latest continuation-adapter milestone

Focused lifecycle/CLI/SDK/handoff matrix: **62 passed**, independently rerun under isolated HOME by reviewer. Covers partial resume, A→B→A, immutable outcomes, dirty source/target preservation, scope binding, lazy direct assignment, startup attachment, headless manifest, curated progress retention, claimed target outside ready queue, known failure compensation, unknown launch refusal, child parent/file identity, and bounded unchanged-progress loops.

Earlier full-suite run: **1326 passed, 4 failed** in 227.96s. Log: `/tmp/pi-pvcg-pytest-current.log` (temporary, not durable).
- Previously known skill discovery remaining `751 > 1000` assertion remains.
- New-to-full-run pre-existing reference assertion: `skills/crafting-apps/SKILL.md:10: missing scripts/update-pi-config.sh --craft`. Skills were unchanged at this run; resolve with planned skill/documentation consistency work, not by weakening checker.
- Two real-Beads tests expected native claim failure; new lifecycle guard correctly refuses earlier. Tests now assert skipped claim/no link, and separately assert real native foreign-actor CAS still rejects. Rerun: **2 passed**. Successful closeout and next-Bead start also verified with real disposable Beads/Git fixtures.

At that continuation milestone, whole-project Ruff, config layout, shell syntax, and `git diff --check` passed. Subsequent full-suite results appear below. No full green release gate yet.

New independent review sequence:
- `runtime:delegated-results/0877ee69-f424-4b40-a146-057938a15038/child-0.json`: shutdown request failure stranded yielding source. Reproduced, fixed with bounded known-pre-exec compensation.
- `runtime:delegated-results/a2e8261b-26f6-4c5d-8ddd-2fe5f4e271a6/child-0.json`: compensation CLI trusted bare reason, and child parent linkage unchecked. Reproduced both; fixed with transition/source-bound secret over private IPC and persisted source-header identity.
- `runtime:delegated-results/393c57b0-6c75-4eca-8bfc-3095cb0ad001/child-0.json`: **PASS**, both findings closed; 62 focused tests passed, no adjacent concrete regression found. Not a whole-feature acceptance review or live deployment proof.

Capability boundary: host creates per-launch 256-bit secret; only scope-bound hash persists. Ordinary CLI flags/wrong proof cannot cancel unknown launch. Async transport uses private FD3; exit callback uses stdin private marker. Model-facing tool inputs/results never carry secret. Arbitrary same-user code/private-file mutation remains outside sandbox claims. Missing legacy source identity fails boundedly instead of silently attaching.

## Latest pending-decision milestone

Latest boundary matrix: **223 passed**, including decision service/SDK, approvals, quality, standing authority, continuation CLI and continuation SDK. Whole-project Ruff and diff whitespace checks passed. Independent final focused review reran the same 223 tests with disposable HOME/runtime and found no remaining P1/P2 defects. No live human decision, policy admission, process restart, deployment, or remote effect was performed.

New source details:
- Per-decision lock serializes rebind and resolve before canonical reads; current ownership is checked again for rebound answers. Positive resolution always requires `pending`, preventing a competing answer/rejection from being overwritten.
- Both direct and recovered question answers validate immutable provenance. New request fingerprint version 2 includes `selectionMode` and `customResponseAllowed`; legacy fingerprints remain readable, never silently rewritten.
- Legacy questions cannot bypass mode verification through the original resolver. Trusted UI first confirms current mode explicitly; decline leaves original blocker pending. Private mode capture survives another UI restart, detects later mode/custom-policy drift, and avoids repeated mode prompts. This is question-scope recovery, not renewed global rollout consent.
- `recover-context` is read-only; both it and `rebind` require existing private process UI proof. CLI flags alone do not confer authority. Ordinary negative resolution/revocation semantics remain available.

Independent reviews (all findings locally reproduced red before fixes):
- `runtime:delegated-results/24a0c6b3-23e8-4566-a9e2-7c81a5c6a7f9/child-0.json`: competing resolution overwrite and unprotected question selection mode.
- `runtime:delegated-results/4e81e04a-0f67-4a09-b560-85259ccd7fa5/child-0.json`: direct question path bypassed newly versioned fingerprint; fixed direct and legacy paths.
- `runtime:delegated-results/0ea47b4a-3490-4e9d-9305-0c45ae4b399a/child-0.json`: **PASS**, no P1/P2 findings in focused follow-up. Not full-feature acceptance or live UI proof.

Subsequent full-suite results appear below. Discovery-budget and crafting-apps reference failures remain unresolved.

## Latest delivery/native-isolation milestone

Full suite after identity/lifecycle/rebinding hardening and initial delivery core: **1389 passed, 2 failed** in 247.42s. Temporary log: `/tmp/pi-pvcg-pytest-receipts.log`. Only known discovery-budget (`751 > 1000`) and crafting-apps command/reference assertions remain. No new full-suite regression appeared. This run preceded the new native adapter and fresh-read API; do not present it as final candidate verification.

Latest focused delivery/native/legacy-worktree matrix: **43 passed** in 9.51s. Whole-project Ruff and `git diff --check` passed. TDD included missing native adapter, failed native ref lookup incorrectly proving absence, and missing fresh-observation API; all now pass.

Native tests use disposable Git repositories and isolated HOME. They prove source dirty files survive creation, collisions/source drift block writes, unsafe project filters/core.worktree are refused, and native Beads reads the common current database rather than stale exported worktree data. A controlled owner-global fixture filter holds real Git while issuing Python call aborts: original descriptors close, Git retains inherited resource leases, competing reconciliation reports busy, then completion reconciles without replay. This is a native writer/caller-abort fixture, not a real Pi restart or deployed behavior.

`observe_current` is read-only and lease-guarded. It reports current provider state separately from historical receipt phase; revocation does not prohibit reconciliation reads. Terminal history stays immutable even when current state changes.

Independent review refs:
- `runtime:delegated-results/b692a943-2620-498d-a55e-52078ad3915a/child-0.json`: delivery-core **PASS**, 26 tests; native processes/consumer integration explicitly excluded.
- `runtime:delegated-results/815cf4ee-2b73-4ff7-8dac-0c6d1d0681c0/child-0.json`: native-adapter **PASS**, 41 tests; no P1/P2 in scope. Fresh-read method and final two tests followed this review; final integrated review remains required.

Current creation adapter trusts Git executable and owner system/global configuration like existing local integration, while refusing project command-valued configuration. No public arbitrary-action JSON executor exists. No activation, deployment, remote operation, real Pi restart, commit or closeout occurred.

Next consumer boundary: reserve target execution ownership **before** native worktree creation; recover through the same receipt and fresh exact observation; yield/launch only after actual target workspace is bound. Keep headless readiness read-only, preserve uncertain native writes, and do not synthesize human consent for blockers. Native worktree helper alone is not completion of automatic isolation or full delivery.

## Latest claim-authority milestone

Further inspection found native Beads claim effects missing from continuation authorization and direct-start preflight. Both were reproduced red. Standing continuation now requires `work-transition` and `beads-write`; requested direct claims require `beads-write` before ownership reservation, claim or quality linkage. No-claim linkage and inactive-policy legacy behavior remain compatible. Ambiguous assignment now reports authority inspection, not an unrelated session conflict.

Two additional red race tests revoked policy after initial validation but before quality's native claim callback. Direct linking now captures scope before entering quality and supplies fresh validation inside the quality transaction; child attachment likewise rechecks immediately before native claim. No lifecycle lock is reacquired under quality. Documented order is lifecycle → quality → authority → Beads; authority service has no quality/lifecycle dependency.

Evidence: broad lifecycle/CLI/improvement/quality/rebinding/SDK selection **593 passed, 1 known budget test deselected** (before final ambiguity diagnostic test). Real disposable Beads start/closeout matrix **2 passed**. Independent focused follow-up **403 passed**, including final ambiguity regression, with no P1/P2 findings: `runtime:delegated-results/5d091b21-d38a-4119-b3d6-3926d822ab42/child-0.json`. It also reviewed fresh receipt observation. Latest whole-project Ruff, config layout, shell syntax and whitespace checks passed.

At that milestone, native automatic-isolation wiring had not started. The later milestone below supersedes that state. Other standing consumers (including orchestration claim/closeout effects), blocked-decision/dependency journeys and assignment intake still require integrated assessment. Do not treat these focused reviews as whole-feature acceptance.

## Latest native-isolation/closeout milestone

Native continuation CLI now supports `needs-isolation`, reserved `isolating` transitions, immutable action/receipt binding, `transition-isolate`, fresh native observation, and safe cancellation. Ownership is reserved before receipt publication or Git effects. Started/uncertain effects reconcile without replay; revocation allows observation but no advancement. Source/target snapshots include branch, logical index/status, and material files hidden by index flags. Copied source-session flags cannot authorize another session; pending transitions block completed ownership release and closeout success.

Closeout now validates checkout/session context and read-only Git preflight before recording success. Canonical success and reservation share lifecycle→quality ordering; finalized source attempts cannot create unfinished continuations. Git closeout/audit calls strip inherited redirects, check physical checkout identity, and retain ordinary repository hooks. Attachment's nested quality callback checks external authority without re-entering quality, avoiding a locally diagnosed intermediate deadlock.

Independent review `runtime:delegated-results/d94fb1e3-ae93-4d65-818b-da94bfedd9e7/child-0.json` found two concrete defects, both locally reproduced red:
1. Cancellation could release ownership before receipt publication completed. Publication/binding now share cancellation's lifecycle lock. Additional red crash test found that cancelling an unbound receipt then crashing could restart the effect; durable `cancelRequested` now requires finishing cancellation, never new preparation.
2. Child attachment read source outcome from its own checkout-dependent quality directory. Transition identity now binds `sourceQualityDirectory`; production-resolver tests cover global and ignored project-local storage without rewriting parent rows. Additional red tests now protect explicit source-directory writes from a sibling and detect an existing target's local unresolved legacy attempt.

Latest controller matrix: **650 passed, 1 known discovery-budget case deselected in 80.82s**, across isolation/continuation/lifecycle/SDK/handoff/delivery/native-worktree/quality/work/improvement tests. Whole-project Ruff, config layout, shell syntax and diff whitespace checks passed. No full-suite rerun after these changes; earlier 1389-pass/two-failure result is not final candidate evidence.

Fresh follow-up output refuted both original findings and reported six passing independent probes plus the same **650 passed, 1 deselected** matrix. Evidence: `runtime:delegated-results/254d2b53-d736-4aea-8c09-2011e49fb9a6/child-0.json`; structured reports and packets are under `.pi/reviews/20261020-205108-native-isolation-closeout/`. Both reports validate. **Invocation limitation:** follow-up artifact records `executionOutcome=failed`, exit 1 despite complete valid final output. Retain useful refutation evidence, but do not label that invocation a clean successful review; final clean integrated review remains required. Read-only doctor found no failures (known Beads health-verification warning only). Parent attempt remains linked to pi-pvcg with outcome null.

No task commit, closeout, live policy admission, deployment, remote effect, or real Pi restart occurred. At that milestone the next consumer was Pi-host isolation recovery; the following milestone supersedes that gap. Broader authority/closeout effects and final acceptance remain unfinished.

## Latest Pi-host recovery milestone

Host now advances an existing isolation receipt once, or finishes durable cancellation intent without restarting effects. It accepts only exact exit-2 structured blocked results as reconciliation; other command failures remain errors. Explicit changed mode/target/checkpoint/checkout conflicts rather than launching stale intent. Reservation identity is checked after isolation/stage/launch. Headless pending recovery stays read-only. Slash commands display blocked outcomes. Missing fresh state is labelled last-observed, not current. Lost launch acknowledgement before shutdown compensates with `launch-request-failed` and original private capability; CLI reason alone cannot cancel uncertain launch.

Independent review `runtime:delegated-results/1f2d5212-fd34-4d2f-b059-9694d795b33a/child-0.json` found HR-001: crash between reservation persistence and child-path binding stranded valid recovery. Reproduced locally before fixes. New `transition-bind-child` checks source session/file/checkout and ownership under lock, binds only existing child's deterministic private path, and creates no child/file/receipt/native effect. Host permits validated null-to-bound repair before strict launch checks; other identity changes reject. Cancellation after revocation remains possible, while later staging/native advancement still requires authority.

Fresh clean follow-up `runtime:delegated-results/423c2437-3014-424f-976b-bb25b3420445/child-0.json` refuted HR-001 with **130 focused tests**, **41 independent probes**, and **19 adjacent probes** passing. Structured reports in `.pi/reviews/20261020-205108-native-isolation-closeout/host-findings.json` and `host-followup-findings.json` validate. This is scoped host-recovery evidence, not whole-feature acceptance or live restart.

Full pytest at the host-recovery milestone, before closeout-authority changes: **1467 passed, 2 failed in 290.48s**, log `/tmp/pi-pvcg-pytest-host-recovery-isolated.log`. Remaining failures unchanged: discovery budget `751 > 1000`; crafting-apps reference parser treats `scripts/update-pi-config.sh --craft` as filename. Earlier full attempt timed out at 600s in disposable Git commits; focused stack localized signer wait. Read-only doctor found no new failure. Four fixture families were red-tested with a fake failing signer, then locally disabled signing only in disposable repos; standing-authority fixture uses command-local signing=false. **Real user Git configuration and actual commit signing remain unchanged.** Fixture integration/runtime/vendor selection: 35 passed. Fresh Ruff, layout, shell syntax and diff checks passed after host review.

Parent work remains uncommitted/in progress. Next boundary: remaining standing-authority consumers (closeout and orchestration), broader assignment capture, other full-delivery adapters, frontier workflow guidance and final gates. Preserve exact quality grants and prior rejection history. No activation/deployment/remote-effect claim.

## Current closeout-authority boundary

`work_lifecycle.closeout_effect_guard` now uses immutable captured assignment rather than a new enrollment. `work.direct_closeout` checks `beads-write`, `repo-write`, and `git-commit` before recording success, rereads canonical blockers/decisions/close reason, and rechecks effects and physical portable target before native writes. Denials preserve already-applied work and report `safeToRetry=false`. Redirected portable directories were locally reproduced then rejected before success. Independent review CA-001 exposed a check-to-replace namespace race; a stronger local regression confirmed actual overwrite of a distinct foreign sentinel. Export now uses a verified no-follow directory descriptor, exclusive temporary-file creation, native stdout to an open file, and descriptor-relative replacement/cleanup. These operations stay on captured objects even if a parent namespace changes; downstream drift stops staging.

New `tests/test_closeout_authority.py` covers missing individual effects, revocation before close/export/replacement/commit, canonical dependency/closure changes, and successful scoped closeout. Missing-effect, redirected-directory, and canonical-change regressions were confirmed red. Latest ten-suite matrix: **655 passed, 1 known budget test deselected**; **14** new closeout-authority tests pass. Disposable real-Beads/legacy closeout selection: **48 passed** before the final two descriptor probes. Ruff and diff checks pass. Independent review invocation `runtime:delegated-results/8b1243cb-65ce-4d5b-a76d-2b94bb7784f9/child-0.json` succeeded with important CA-001. Original structured report needed schema normalization; validated controller report is `.pi/reviews/pi-pvcg-closeout-authority/findings.json`. Fresh independent follow-up `runtime:delegated-results/1631d453-9969-45d4-8088-143b94742499/child-0.json` succeeded (exit 0), refuted the namespace-write scenario against current code and found no new actionable defect. It ran 2 independent descriptor probes plus all 14 focused cases; report `/tmp/pi-closeout-ca001-followup-20261021/report.md`, validated `.pi/reviews/pi-pvcg-closeout-authority/followup-findings.json`. Scope excludes receipt recovery and whole-feature acceptance. Layout/shell/diff checks passed afterward. Existing closeout is not migrated to delivery receipts; ambiguous native effects, remaining orchestration/intake/delivery consumers and final acceptance remain unfinished.

`bd prime`, `bd ready`, `bd show pi-pvcg`, and `agnt work direct-start pi-pvcg --claim` succeeded again; native response still shows old lease timestamps. HEAD remains `4674c05a82553e46762b5722e581eab4da851121`; no task commit, closeout, activation, deployment, or real restart.

## Orchestrated native-authority milestone

`work.start_work` and `finish_work` now separate native controller bookkeeping from worker permissions. Claim checks run before preparation and around native writes; close retains run evidence but denies unauthorized canonical closure. `guarded_standing_beads_effect` holds lifecycle ownership through known actor/phase/scope checks and callback. Read-only actions cannot skip existing scope; no enrollment/widening occurs here. Inactive ordinary legacy bookkeeping remains separate from standing authority. Exact worker gates are re-resolved, checked for local revocation, then final controller scope is checked; neither worker effects nor experiment claims are broadened/renewed.

Independent review found PVCG-AUTH-001 (exact-grant exemption bypassed controller guard), then PVCG-AUTH-002 (canonical targetBead discarded). Both were locally reproduced with four red regressions each and fixed. Canonical target now binds initial admission, stored run envelope, worker revalidation and native claim/close. Legacy missing-target snapshots require fresh canonical matching without history rewrite. Additional red probes covered queued revocation during gate read, missing exact snapshots and malformed referenced decisions. Tests now contain 37 new orchestrated-authority cases.

Parent matrix: **689 passed, 1 known discovery-budget case deselected** across ten suites, with whole-project Ruff/diff passing. Latest independent invocation `runtime:delegated-results/fa360015-7ee7-4d52-8ad0-c3c824c0d115/child-0.json` succeeded/exit 0 and refuted both findings with no adjacent actionable defect: **682 passed, 1 deselected**, plus target-binding probe, scoped Ruff/diff/schema checks. Its matrix uses SDK continuation-extension tests instead of parent's CLI continuation tests, explaining count difference. Review used disposable copied source, mocked Beads and isolated HOME; initial copied Node-dependency resolution failure was retained, then existing dependency symlink used without install. This is scoped verification, not live or full-feature acceptance.

Packets/reports/findings: `.pi/reviews/pi-pvcg-orchestration-authority/`. Final `target-followup-findings.json` validates (2 refuted, 0 unresolved); raw reviewer findings retained separately. Reviewer identity normalized from successful host receipt to openai-codex/gpt-5.6-terra; deterministic test method was not a separate reviewer family. Latest full suite remains the older 1467-pass/two-failure result, not this candidate. Doctor remains degraded only for unsupported full Beads database health, with no failures. Source remains dirty on HEAD `4674c05a82553e46762b5722e581eab4da851121`; no task commit/closeout, admission, deployment, real restart or remote effects.

Remaining within this boundary: orchestration worker-session reservation/transfer and epic creation, native Beads effect receipts/uncertain recovery. Broader four-package scope below remains unfinished.

## Continuation boundary

Follow the narrowed 2026-10-21 plan and current state at the top, not the historical four-package mandate. General external delivery adapters, universal effect recovery, dependency detours, policy-covered approval-blocker reconciliation and expanded epic/worker orchestration are deferred by the owner. Do not resume those merely because historical milestones call them unfinished. Current completion target is useful partial resume, dirty switching, existing-decision recovery and valid-authority reuse/revocation, with truthful verification and local commit/closeout.

Read the new authority/lifecycle specs before extending their boundaries. The lifecycle host must verify canonical status/claims, enforce one repository-scoped owner store across worktrees, authenticate child identity, revalidate authority before launch/attachment, and supply real attachment inspection. Callbacks/boolean observations are trusted adapter seams, not proof supplied by model text. Current libraries are not a shell sandbox and do not demonstrate live full-delivery operation.
