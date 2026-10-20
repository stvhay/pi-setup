# Resumable Work and Global Delegation Implementation Plan

**Issue:** pi-v0hy — planning deliverable; create/link implementation Bead(s) before code changes
**Design:** [2026-10-20-resumable-work-global-delegation-design.md](2026-10-20-resumable-work-global-delegation-design.md)
**Date:** 2026-10-20
**Branch:** Planning on `main`; implementation uses task-owned checkout/branch under effective authority

**Goal:** Let agents execute larger coherent development/delivery objectives across sessions and Beads without routine copy/paste or repeat approvals, using user-authorized automatic full-delivery delegation across all projects.

**Architecture:** Keep Beads as durable work state and preserve one Bead per session attempt. Add a focused lifecycle service with checkpoints and recoverable transition records, plus a shared standing-authority resolver with trusted user-origin activation and concrete execution receipts. Pi extensions own UI/session launch; existing helpers and provider/deployment adapters own concrete effects. Workflow skills consume the same authority contract and plan substantive verifiable deliverables rather than microtasks.

**Execution status:** Design and plan only. No implementation, live policy activation, deployment, push, release, or production operation was performed by pi-v0hy. This plan describes future interfaces explicitly; it does not claim they exist.

## Acceptance criteria

- [ ] Same-Bead continuation, partial/failure resume, A->B->A switching, dependency detours, and claimed-target continuation work without `/new` or pasted instructions on supported TUI runtime.
- [ ] Existing history/outcomes remain immutable; successful Bead closeout retains verification and portable-state parity. Switching does not imply success or ancestor acceptance.
- [ ] Dirty work survives; foreign/live competing sessions cannot be displaced; claim/link and launch failures reconcile without duplicate claims/sessions.
- [ ] Multiple eligible Beads are chosen deterministically inside delegated assignment; no work produces bounded idle/blocked output rather than a loop.
- [ ] One authenticated owner policy automatically applies to all current/future assigned projects without per-project/environment enrollment prompts or mass repository edits.
- [ ] Standing authority survives session and Bead transitions; assignment constraints, explicit rejections, revocation, platform rules, and narrow exact grants retain their meaning.
- [ ] Ordinary Git/PR/main/release/local-live/staging/production delivery can proceed without repeat approval when identity, assignment, downstream effects, verification, and recovery requirements hold.
- [ ] Unknown/foreign targets, forged policy activation, protected-review bypass, unresolved effect outcomes, and excluded destructive/access/spend changes cannot gain authority through auto-enrollment.
- [ ] Current partial/failed attempts, legacy ledgers, old exact grants, and pending decisions remain recoverable without silently rewriting their history.
- [ ] Root instructions and planning/execution/delegation/review/finishing skills consistently favor larger end-to-end scopes and continuous verified execution; no artificial file/line/minute/task-count split requirement.
- [ ] New policy, transition, and receipt formats have explicit invariants, compatibility behavior, tests, and operator diagnostics.
- [ ] Tests demonstrate autonomous positive paths, not only rejection paths. Runtime limitations and unenforced arbitrary-shell boundaries are accurately documented.

## Verification commands

Existing project commands, run from repository root after implementation:

```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

If locked Node dependencies are absent, follow project setup with `npm ci --ignore-scripts`; do not install unrelated dependencies or alter shell/home configuration. Focused tests below include proposed new files, which must be created before those commands are expected to pass. Do not run paid model canaries, production actions, or live deployment as ordinary test gates.

## Implementation approach and task sizing

Use four substantial, independently verifiable work packages. Each includes code, tests, and its relevant contract docs. Their boundaries follow persistent state, runtime ownership, concrete delivery effects, and shared instructions—not model-era assumptions about small tasks. The currently routed capable controller should carry a complete package through verification before yielding; parallel read-only investigation/review is useful, but shared-file mutations remain serialized.

Do not turn the steps below into one Bead per test, file, helper, or tool call. Use one feature Bead or a small parent/child graph when independent outcomes or ownership justify it. A work package may span multiple sessions through its checkpoint; session turnover does not change its acceptance criteria or authority. Automated verification milestones are not human approval stops.

## Source map and constraints

Read the design and current versions of:

- `pi/agent/bin/agnt_lib/work.py`: `handoff_check`, `direct_start`, `direct_closeout`, orchestration dispatch.
- `pi/agent/bin/agnt_lib/quality.py`: session link/outcome locking, exact grants, claim tokens; preserve quality-system experiment semantics.
- `pi/agent/bin/agnt_lib/improvement.py`: session link/outcome projection and recovery descriptions.
- `pi/agent/extensions/bead-handoff.ts`, `lib/process-replacement.ts`, `beads-footer.ts`: launch, process replacement, and visible work state.
- `pi/agent/bin/agnt_lib/approvals.py` and `pi/agent/extensions/beads-ask-bridge.ts`: canonical provenance and pending decision session bindings.
- `pi/agent/bin/agnt_lib/orchestration.py`, `worktree_policy.py`, `runs.py`, `invoke.py`: authority consumers, dispatch claims, and workers.
- `pi/agent/bin/agnt_lib/integration.py`: target-scoped lock and guarded local integration.
- `pi/agent/bin/agnt_lib/runtime_paths.py`: repository identity and private storage resolution; currently project-scoped, not a global policy-authority store.
- `pi/agent/bin/agnt`, `agnt_lib/__init__.py`: command registration/exports; there is no `agnt_lib/cli.py`.
- `pi/agent/quality/SPEC.md`: distinguish exact experimental grants from reusable user delivery delegation.
- `pi/agent/AGENTS.md`, root `AGENTS.md`, `pi/agent/skills/dev-workflow-common/SKILL.md`: currently active source-policy constraints.
- `pi/README.md`, `pi/agent/bin/README.md`, `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`, `docs/ORCHESTRATION-LOOP.md`, `docs/RUN-ARTIFACTS.md`.

Query existing `graphify-out/graph.json` before additional architecture exploration, then verify source; its handoff/approval graph is older than current code. `docs/specs/MANIFEST.md` and sibling lifecycle/authority specs were absent during planning. Add targeted specs rather than inventing a full documentation registry.

Before changing extension APIs, read complete installed Pi `docs/extensions.md` and relevant linked session/TUI/SDK docs and examples under `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/`. Verify current native capabilities; do not assume a lifecycle handler can call command-only session replacement.

### Task 1: Global standing-authority vertical slice [Independent foundation]

**Outcome:** One trusted, reusable full-delivery policy automatically applies in a never-enrolled project and produces explainable effective authority for both direct work and orchestration, without creating an approval Bead per ordinary task.

**Files:**
- Create: `pi/agent/bin/agnt_lib/authority.py`
- Create: `pi/agent/authority/full-delivery.json`
- Create: `pi/agent/authority/SPEC.md`
- Create: `pi/agent/extensions/standing-authority.ts`
- Create: `tests/test_authority.py`
- Create: `tests/test_standing_authority.py`
- Modify: `pi/agent/bin/agnt`, `pi/agent/bin/agnt_lib/__init__.py`
- Modify: `pi/agent/bin/agnt_lib/runtime_paths.py`, `approvals.py`, `orchestration.py`, `work.py`, `worktree_policy.py`, `runs.py`, `invoke.py`
- Modify: `pi/agent/extensions/beads-ask-bridge.ts`
- Modify: `pi/agent/quality/SPEC.md`, `pi/agent/bin/README.md`, `docs/AGNT-SYSTEM.md`, `docs/ORCHESTRATION-LOOP.md`, `docs/RUN-ARTIFACTS.md`
- Test: `tests/test_approvals.py`, `tests/test_orchestration.py`, `tests/test_runs.py`, `tests/test_worktree_policy.py`, `tests/test_agent_os_compat.py`, `tests/test_pi_packages.py`

**Contract and implementation steps:**
1. Write failing behavioral tests for all-project automatic applicability, assignment restriction, trusted activation, revocation, and direct/orchestrated equivalence. Include two unrelated temporary repositories and a future-created repository; no enrollment files or prompts may be needed.
2. Define small typed contracts: standing policy, user-origin activation, assignment scope, resolved action/target, and effective authority decision. Keep routing/model/thinking choices separate except for actual provider/privacy/spend constraints. Use a versioned discriminated authority source for standing policy versus legacy exact grants; never forge legacy `human-ui` or claim-token fields.
3. Add an owner-global private authority root, distinct from per-repository runtime state. Track the reviewed policy template, not user transcripts, activation secrets, revocation journal, or private target identities. Default automatic project application is active only when the owner-global policy fingerprint is authentically authorized.
4. Implement trusted admission in the Pi boundary. Bind this approved scope to genuine user-message evidence and its resolved design context; arbitrary model-supplied refs/flags or an agent-authored design file are insufficient. Use current authenticated parent/tool infrastructure where suitable, without weakening legacy proof validation. Global activation must not ask the owner to authorize every project or target again. Document exact trust assumption and installation/migration path.
5. Implement deterministic `agnt authority` inspection/check/revocation surfaces with bounded JSON reasons. Specific new subcommands/schema should follow the minimal service API; document actual names before wiring callers. Resolution intersects policy, assignment, explicit task constraints, trusted narrow project rules, platform restrictions, and action preconditions. Permission alone never schedules new work.
6. Preserve legacy exact grant semantics. Orchestration can consume valid standing authority instead of requiring one canonical approval reference for every implementation. Existing quality `claimContext` paths continue to enforce their original envelopes and at-most-one experiment semantics; ordinary delivery must not counterfeit or weaken those tokens.
7. Rebind/re-present pending durable questions through trusted UI after session changes without losing identity or creating duplicate blockers. Never infer a positive answer. Distinguish a policy-superseded approval-only requirement from an answered/rejected decision; preserve original history and specific user restrictions.
8. Document policy widening, narrowing, revocation, expiry, ownership, and failure behavior. Activate no live policy during unit tests. Update package/layout checks if adding a tracked authority directory or extension changes validated layout.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_authority.py tests/test_standing_authority.py tests/test_approvals.py tests/test_orchestration.py tests/test_runs.py tests/test_worktree_policy.py tests/test_agent_os_compat.py tests/test_pi_packages.py -q
```

**Expected result:** Automatically applicable authority returns allowed only for delegated intent and resolved allowed effects; forged activation, wider project text, revoked policy, specific rejection, expired exact grant, and foreign/unknown target cases return bounded denial without effect. No recurring human UI appears in ordinary authorized paths.

### Task 2: End-to-end resumable Bead lifecycle [Depends on: Task 1]

**Outcome:** Supported TUI sessions checkpoint, resume, switch, and recover automatically, preserving unfinished work and effective authority.

**Files:**
- Create: `pi/agent/bin/agnt_lib/work_lifecycle.py`
- Create: `pi/agent/bin/agnt_lib/work_lifecycle.SPEC.md`
- Create: `tests/test_work_lifecycle.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`, `quality.py`, `improvement.py`
- Modify: `pi/agent/extensions/bead-handoff.ts`, `pi/agent/extensions/lib/process-replacement.ts`, `pi/agent/extensions/beads-footer.ts`
- Modify: `pi/agent/bin/README.md`, `pi/README.md`, `pi/agent/quality/SPEC.md`, `docs/ARCHITECTURE.md`
- Test: `tests/test_bead_handoff.py`, `tests/test_process_restart.py`, `tests/test_agnt.py`, `tests/test_quality.py`, `tests/test_improvement.py`

**Contract and implementation steps:**
1. Test the design's lifecycle matrix before replacing success-only preflight. Preserve existing positive closeout and malformed-state protections; change only restrictions intentionally superseded by checkpoint/resume/switch.
2. Add versioned checkpoint and transition records, sanitized Bead summary/pointers, and session-attempt ownership. Preserve one Bead per session and final outcome immutability. Multiple sessions under the same Beads actor must not own execution simultaneously merely because `bd --claim` is actor-idempotent.
3. Implement direct checkpoint and transition-check/status/recovery operations. Existing `handoff-check` can delegate through a compatibility adapter. Explicit resume validates target independently of `bd ready`; automatic next-work selection remains assignment-scoped with stable dependency/priority ordering and deterministic tie-breaking.
4. Define lock ordering and prepare/reservation/stage/attach/settle invariants. Inject failures at every persistence/claim/session-launch boundary. Retry resumes the exact transition; no duplicate child, unsafe source unclaim, or stale-source write after target attach. Do not infer dead ownership solely from elapsed lease time.
5. Preserve dirty source work. Same-Bead continuation verifies checkout identity; cross-Bead work uses verified isolation when dirty paths remain. Test unrelated untracked files, concurrent edits, changed HEAD, and mismatched manifests. No implicit stash/reset/clean or WIP commit is needed just to continue the same Bead.
6. Extend `handoff_bead` with mode/target/checkpoint references; return structured recovery. Persist bounded kickoff state and reuse existing process-replacement seam rather than build a scheduler. Runtime preflight must precede source yield. UI cancellation before commitment leaves source usable; unsupported headless launch returns an honest host continuation manifest.
7. Replace `/new`-first conflict guidance in `work.py`, `quality.py`, `improvement.py`, tool descriptions, and footer state with the exact agent-executable next action. Keep manual launch as last resort for an unavailable runtime, not normal partial work.
8. Revalidate authority on attach/recovery. Pending decision, revoked policy, target claim conflict, no eligible work, and repeated A->B loops produce bounded resumable outcomes. Successful closure remains separate and cannot be fabricated to unlock a transition.
9. Update lifecycle specs/docs with concrete schemas, state table, lock order, compatibility, and recovery commands. Historical session/quality rows remain byte-for-byte history.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_work_lifecycle.py tests/test_bead_handoff.py tests/test_process_restart.py tests/test_agnt.py tests/test_quality.py tests/test_improvement.py -q
```

**Expected result:** Same-Bead fresh context, partial resume, A->B->A, dependency detour, and multiple-candidate selection run without user input in the supported harness fixture. Crash/duplicate/concurrency cases preserve work and never create competing execution or false success.

### Task 3: Full-delivery effects under reusable authority [Depends on: Tasks 1 and 2]

**Outcome:** Git/PR/release/deployment operations use standing permission and concrete execution receipts instead of future-SHA approvals and one-shot Bead-bound authority. The implementation provides truthful adapters, not a universal shell sandbox or a new deployment platform.

**Files:**
- Create: `pi/agent/bin/agnt_lib/delivery.py`
- Create: `pi/agent/bin/agnt_lib/delivery.SPEC.md`
- Create: `tests/test_delivery.py`
- Modify: `pi/agent/bin/agnt_lib/authority.py`, `integration.py`, `work.py`
- Modify: `pi/agent/bin/README.md`, `pi/README.md`, `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`
- Modify if actual adapter changes require it: `scripts/update-pi-config.sh`, `scripts/check-pi-config.sh`
- Test: `tests/test_agnt.py`, `tests/test_pi_packages.py`, `tests/test_authority.py`

**Contract and implementation steps:**
1. Add deterministic effect adapter contracts for resolve identity/preconditions, prepare, execute, observe/reconcile, and optional non-destructive rollback. Expose effective authority and receipt refs to normal Pi execution without forcing run bundles. Inventory existing provider/deployment tools before adding adapters; do not add a GitHub/cloud SDK or dependency merely to implement this policy.
2. Implement scoped immutable receipts and locks for attempts. Resolve source rules at execution time to task-owned verified commit ranges/artifacts; support more than one implementation commit. Recheck policy revision, assignment, target, and downstream effects just before mutation. Narrow locks to resources; serialize shared external writes.
3. Connect guarded local integration to authority-derived runtime HEAD/source values. Keep its safe-config, locking, clean-target, conflict-abort, and verification checks. A moved base can trigger re-evaluation/reverification under policy; never infer force/rebase/reset authority from divergence.
4. Support ordinary push/PR/main/release workflows through existing tools/adapters. Respect remote ownership, branch protection, required review/checks, version/channel rules, artifact identity, and CI-triggered effect closure. No force, remote deletion, tag overwrite, or review bypass. Use fake providers/local test remotes for behavioral tests; no real remote mutation during tests.
5. Support automatic target resolution for local-live/staging/production deployment associated with the assignment. No per-environment enrollment prompt. Read independent runtime/provider identity and bind canonical host/account/environment, intended artifact, managed effect bounds, prechecks, preview, health checks, and recovery. Unknown target or absent material version/channel intent triggers discovery or a targeted question, not guessed deployment.
6. Preserve source-of-truth `pi/` and existing local-live deployment script, dry-run, secret/runtime exclusions, and backup evidence. Add only the adapter changes needed for authority and receipts; do not rewrite the installer as a general deployment system.
7. Reconcile results into applied/not-applied/uncertain. Already-applied operations are recorded, not repeated. Definitely unapplied effects may retry under bounded policy after preconditions are revalidated. Uncertain effects stay blocked until resolved; new attempt IDs cannot bypass prior uncertainty. Exercise revocation during pending/queued operations and sibling-worker behavior.
8. Implement known non-destructive rollback only when its target/effects fall within standing policy and preserved evidence. Destructive recovery, secrets/access changes, unbounded/new spend, and unrelated deletion stay excluded. Bound retry count/time using operation facts, not model confidence.
9. Publish exact supported adapters and enforcement boundary. Where execution uses an unrestricted external tool/shell, expose plan/receipt checks and instruction integration honestly; do not claim arbitrary commands are mechanically intercepted. Missing adapter support must be reported as such, not silently treated as proof of permission or completion.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_delivery.py tests/test_authority.py tests/test_agnt.py tests/test_pi_packages.py -q
bash -n scripts/*.sh
```

**Expected result:** Fixtures complete task-branch push, permitted main/PR merge, release, local-live and production deployment without a human callback; negative cases refuse target spoofing, platform bypass, unauthorized downstream effects, revocation, duplicate uncertain effects, and destructive rollback. Local integration still passes existing concurrency/config/conflict tests.

### Task 4: Frontier-scale instructions, compatibility, and journey acceptance [Depends on: Tasks 1–3]

**Outcome:** Agents discover and consistently use the new workflow, plan larger coherent scopes, and do not reintroduce routine human gates through old skills or prompts.

**Files:**
- Modify: `pi/agent/AGENTS.md`, root `AGENTS.md`
- Modify: `pi/agent/skills/brainstorming/SKILL.md`, `writing-plans/SKILL.md`, `executing-plans/SKILL.md`, `dev-workflow-common/SKILL.md`
- Modify: `pi/agent/skills/subagent-driven-development/SKILL.md`, `using-git-worktrees/SKILL.md`, `finishing-a-development-branch/SKILL.md`, `requesting-code-review/SKILL.md`
- Modify as needed for consistent authority semantics: `pi/agent/skills/approval-confirmation/SKILL.md`, `delegation-oversight/SKILL.md`, `failure-choreography/SKILL.md`, `project-init/SKILL.md` and their relevant references/templates
- Modify: `pi/README.md`, `pi/agent/bin/README.md`, `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`, `docs/ORCHESTRATION-LOOP.md`, `docs/RUN-ARTIFACTS.md`
- Annotate: `docs/HANDOFF-LIFECYCLE-COHORT-2026-08.md` with a superseding-design link; retain historical data/claims as historical
- Create: `tests/test_delegated_work_journeys.py`
- Modify: `tests/test_context_architecture.py`, `tests/test_workflow_compliance.py`

**Contract and implementation steps:**
1. Load `skill-creator` before modifying skills; inspect its evaluation guidance. Load verification/finishing skills at completion. Do not infer a need for paid model evals from this instruction update.
2. Add the design's frontier-capable planning instruction to shared conventions and root context concisely. Update planning templates to describe substantial deliverables, invariants, interfaces, evidence, and recovery instead of mandatory line-by-line microtasks. No arbitrary file/line/minute/task-count ceiling. Use currently routed demonstrated capability rather than hardcoded model names or unsupported benchmark claims.
3. Remove unconditional design/review/batch-wait prompts when active delegation covers the work. Keep clarification for genuine consequential ambiguity, material scope expansion, hard external constraints, and ownership conflicts. Report verified milestones and continue by default inside assignment.
4. Align execution, peer/worktree setup, local integration/cleanup, finishing, PR/release/deployment, and handoff guidance with the shared resolver. Review segmentation follows behavioral coupling and evidence needs, not an arbitrary line threshold. Parallel peers still require isolated writing ownership; do not parallelize shared effects.
5. Preserve distinction between verification and permission. Larger scopes still require regression tests, independent review where warranted, boundary checks, and recoverable checkpoints. A plan is not a license to bypass explicit `do not commit/deploy/push` constraints or production platform controls.
6. Update project-init templates so new projects inherit global applicability without enrollment boilerplate. Existing project-specific restrictions are honored; do not bulk-edit other repositories to manufacture permission. Search context overlays/action templates/eval fixtures for conflicting legacy instructions and update only applicable task-owned sources.
7. Add deterministic scenario tests that compose helpers/extensions with temporary repositories and fake effect adapters: partial resume, A->B->A, context refresh, active claim collision, revocation during transition, blocked dependency, pending decision after restart, fresh global-policy project, and larger multi-step delivery. Assert zero approval/selection callbacks on authorized routine paths and precise escalation for genuine boundary failures.
8. Preserve old artifacts and exact grants. Mark obsolete instructional assertions intentionally superseded rather than weakening negative tests wholesale. Existing quality-system experiments stay bounded and compatible.
9. Run full verification, independent review of authority/lifecycle boundaries, and docs validation. Fix confirmed findings; do not claim reliability from model agreement alone. Real-model workflow canary remains optional only with explicit request or a justified proposal.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_delegated_work_journeys.py tests/test_context_architecture.py tests/test_workflow_compliance.py -q
scripts/check-pi-config.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

**Expected result:** Prompt/context checks and deterministic journeys agree with runtime behavior. Larger authorized tasks progress through design/implementation/review/delivery without routine approval gates, while explicit exclusions and failure evidence remain enforced. No test requires obsolete manual `/new` recovery for a supported routine case.

## File conflicts and execution order

| Shared surface | Tasks | Resolution |
|---|---|---|
| `work.py`, authority contracts, runtime identity | 1, 2, 3 | Serial implementation; one controller owns integration. |
| `quality.py`, session history, exact grants | 1 boundary, 2 lifecycle | Preserve separate contracts; never widen experimental claims to simplify delivery. |
| `pi/README.md`, command/system/architecture docs | All | Each package updates its contract; final consistency pass in Task 4. |
| `tests/test_agnt.py`, authority and package tests | 1–3 | Serial ownership; fresh focused tests after each shared edit. |
| Root instructions and workflow skills | 4 | Change together after runtime contract stabilizes; no competing prompt rewrites. |

Independent read-only peer reviews may inspect lifecycle races, authority provenance, and planning/instruction consistency in parallel. Writing peers require isolated worktrees and disjoint ownership; this plan does not require them for its own sake.

## Migration and rollout

1. Record implementation Bead/assignment and current baseline. Preserve the two unrelated untracked plans observed during planning: `.pi/plans/2026-08-18-telemetry-preproduction-contract-design-plan.md` and `.pi/plans/2026-10-01-laya-chat-shadow-routing-design-plan.md`.
2. Land schema readers, authority diagnostics, and tests before switching behavior. Read old session/outcome/grant data without rewriting it. Policy activation is a verified owner-global event, not a project-local `approved` flag.
3. Ship runtime and matching instructions together. Test fresh and resumed sessions against matching source/runtime versions so old tool guidelines do not claim unsupported modes.
4. During actual rollout, use the project deployment script and current applicable approval rules. Resolve canonical source/target/host/user, exact effects, preview, backups, health checks, and stop conditions. The planning task performs none of these mutations. Do not use the proposed future policy to bypass currently governing activation/deployment requirements.
5. Activate the exact globally authorized policy through the trusted user-origin admission path. This is one owner-level scope, not a new per-project/per-environment approval. Demonstrate application in a never-enrolled fixture/project without new approval or configuration writes there.
6. Verify supported local TUI continuation and local-live health. Production capability acceptance uses deterministic fake adapters; no real production deployment is necessary merely to prove policy support.
7. Preserve rollback evidence for managed source/runtime changes and schema compatibility. Revocation disables future effects/transitions without deleting checkpoints or rewriting historical outcomes. Never auto-run destructive rollback.

## Review and verification evidence

Review must cover both positive usability and negative boundaries:

- user intent and all-project default cannot be lost on handoff;
- trusted global activation cannot be forged by project text or agent output;
- policy reuse does not duplicate uncertain external actions;
- same-actor concurrent sessions cannot both attach;
- dirty/untracked work remains untouched;
- protected-branch and production controls remain real checks, not recurring assistant approval prompts;
- frontier-scale planning is an explicit instruction change, not merely an assertion in this plan.

Use routed subscription-backed peer review with no routine caller caps. Keep evidence in private review artifacts and sanitized findings in Beads. Final commands must run after the last relevant change. Do not treat this planning review as implementation verification.

## Execution handoff

Plan saved to: `.pi/plans/2026-10-20-resumable-work-global-delegation-plan.md` (verify with `test -f` at planning closeout).

Recover objective and approved decisions from `bd show pi-v0hy` and the linked design/plan, not a copied transcript. The implementation session must create/link its implementation Bead before edits, inspect current instructions, and load `executing-plans` plus `test-driven-development` for behavior changes. Use `verification-before-completion` before claims/commits and `finishing-a-development-branch` before closeout. This planning task does not start implementation automatically.
