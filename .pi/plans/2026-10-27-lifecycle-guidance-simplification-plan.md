# Lifecycle and Guidance Simplification Implementation Plan

**Issue:** `pi-pvjr` — implementation authorized; fresh owning session claimed through direct-start. Do not reopen completed `pi-sq8l` or relabel its session. Related: `pi-ys12` (snapshot/gitlink defect), `pi-p5wp` (stranded implementation).
**Design:** Staged repair of existing lifecycle, selected by user on 2026-10-27. Earlier [workspace architecture](2026-10-25-bead-owned-workspaces-architecture.md) and [transition plan](2026-10-25-bead-owned-workspaces-transition-plan.md) remain deferred alternatives, not implementation prerequisites or current operational guidance.
**Date:** 2026-10-27
**Branch:** Planning on `main`, inspected HEAD `068fd6402700337ba280e083c542f0615a24d609`; no execution branch/worktree created.

**Goal:** Make ordinary start, continuation and completion work without misleading ownership errors, ineffective fresh-session loops or contradictory instructions, while preserving actual ownership, authority and dirty work.

**Architecture:** Retain existing `direct-start`, `direct-closeout`, `handoff_bead`, schema-1 lifecycle journal, quality ledger and process-replacement adapter. Put shared eligibility/recovery decisions in `agnt_lib/work_lifecycle.py`; Python/TypeScript adapters report those decisions instead of inventing policy. Remove duplicated conditions and inappropriate content inspection before adding narrowly required behavior. Guidance describes the supported implementation, not an aspirational second workflow.

**Authority:** Implementation subsequently approved under `pi-pvjr`; its notes record exact same-checkout/dependency exception `pi-fhh6`. Work in existing main checkout, preserve pre-existing unrelated files, and retain the approved dependency graph for source edits/local tests. No live deployment/restart, push, remote access, manual closure or owner/journal override. Earlier task-specific exceptions do not carry forward.

## Acceptance criteria

- [ ] Source, rendered instructions, tool guidance and generated project guidance agree on unfinished, unassigned, terminal and unresolved-transition cases.
- [ ] Ownership registration does not recursively read or hash working-file contents, including unborn repositories, large files and submodules.
- [ ] Actual ownership conflicts remain blocked; storage, snapshot, authority and checkout errors retain distinct actionable diagnoses.
- [ ] Readiness and preparation agree for unchanged state; races still trigger fresh validation before effects.
- [ ] An assigned task can resume in its shared checkout without an unrelated task owner veto; existing cross-Bead isolation and authority constraints remain.
- [ ] Approved same-Bead relocation uses the existing reserved-child transition, preserving source files, session headers, scope, outcomes and quality-store binding.
- [ ] Non-success terminal tasks can relinquish their own execution and permit next work without inventing success or rewriting history; unrelated sessions cannot release them.
- [ ] Genuine pending/unknown effects recover only their exact reservation. Pre-reservation rejection never claims an uncertain launch exists.
- [ ] Supported TUI journeys require no user `/new`, session-ID repair or journal surgery. Unsupported hosts return a truthful bounded capability result; headless auto-launch is not promised.
- [ ] Runtime fixes and matching guidance ship together on each explicitly approved affected host; local tests/deployment do not stand in for remote verification.

## 1. Findings that determine scope

Private historical evidence: `/Users/hays/.pi/improvement/reviews/ownership-history-20261027/report.md` and adjacent extraction/query artifacts. Keep raw history private; use synthetic equivalent fixtures in tracked tests. Do not turn every historical refusal into a defect or combine different deployed versions into one failure rate.

Current-source findings independently verified for this plan:

| Finding | Source | Consequence |
|---|---|---|
| Stale success-only handoff rule | `pi/agent/skills/project-init/references/audit-checklist.md`, BEADS-2/3 | Contradicts unfinished continuation in `pi/agent/AGENTS.md` and tool guidance. |
| Shell directory change mistaken for host relocation | `skills/using-git-worktrees/SKILL.md`, Steps 6–8; `work_lifecycle._source_session_file` | Shell `cd` does not update Pi header, tools, instructions or ownership. |
| Isolation guidance more restrictive than direct default | `skills/executing-plans/SKILL.md`, preconditions and checkout setup; shared AGENTS direct default | Routine work can be diverted into unnecessary worktree transitions. Preserve real overlapping-work safeguards, not blanket isolation. |
| Optional fields choose lifecycle route | `extensions/bead-handoff.ts`, tool execute | Any `progress`/`checkout`/`mode` forces continuation, even for unassigned or terminal sources. |
| Context conflates absent and closed work | `work_lifecycle.transition_context` returns `legacy` for both | Adapters cannot reliably select appropriate path or explain refusal. |
| Registration performs content snapshot | `LifecycleStore.claim` → `workspace_snapshot` | Metadata bookkeeping can fail on file size/type and read content unnecessarily. |
| Arbitrary ValueError becomes ownership conflict | `guard_session_link` → `work.direct_start` | File/snapshot/identity failures turn into another-work-item/final-outcome message. |
| Check and prepare duplicate different conditions | `transition_check`, `LifecycleStore.prepare` | Ready can become deterministic rejection with no state change. |
| Every transition rejection implies reconciliation | `work.cmd_work` transition exception response; `work-continuation.ts` reconcile wrapper | Pre-reservation refusal is described as uncertain attachment. |
| Terminal release assumes successful closeout | `release_completed`, `handoff_check`, `quality.session_handoff_source` | Cancelled/Wontfix/manual terminal states strand execution records or block next work. |

A byte comparison of 172 tracked/live AGENTS, overlay, skill Markdown and selected handoff-adapter files found **no drift on this Mac**. Contradictions therefore exist at source. That comparison does not prove Linux parity, loaded-session freshness, third-party guidance compatibility or consistency of every project-local AGENTS file.

Already fixed: direct shared-checkout closeout (`399567b`) and completed-owner handoff exclusion (`ec11e4f`). Keep their regressions; do not reimplement them. Historical schema/PATH/signing/deferred-child failures are useful diagnostic fixtures, not authority to alter databases, signing configuration or child dependencies.

## 2. Simplification contract

### One owner for each rule

- `pi/agent/AGENTS.md`: short shared behavioral invariants and normal workflow.
- `work_lifecycle.py` + sibling SPEC: executable ownership/continuation eligibility and recovery facts.
- `work.py`: CLI envelopes, native Beads/Git work; preserve domain decisions and safe native diagnostics.
- `bead-handoff.ts` / `lib/work-continuation.ts`: host capability, session staging/replacement and UI. No second eligibility classifier.
- Skills: task-specific procedures; link to shared contract rather than restating lifecycle policy.
- `project-init` templates/checklist: project additions and compatibility checks, not a frozen copy of an old global workflow.
- Beads notes/checkpoints: historical facts and references, not instructions that override current host state or permissions.

### Keep / remove / defer

**Keep:** immutable session/outcome history; one task per session and protected task ownership; captured scope/revocation; dirty-file preservation; clean tracked-tree successful closeout; canonical dependency/decision checks; exact transition recovery; existing host capability limits.

**Remove:** success prerequisite from unfinished continuation guidance; content snapshot from claim; blanket ValueError-to-ownership conversion; duplicate readiness policy; dispatch-by-incidental-argument presence; unconditional reconciliation prose; blanket worktree escalation and repeated `/new` advice.

**Defer:** schema 2, writer epochs/leases, new `work_bead` tool or enter/complete CLI, mandatory task worktrees, native deferred-switch host patch, automatic integration/pruning, generic recovery engine, cross-repository relocation and global journal sweep. No second state store, compatibility framework or host registry.

**Complexity gate:** every new helper/field must replace duplicated logic or satisfy an explicit acceptance row below. List removed branches/procedures alongside additions. No line-count quota that sacrifices validation; no generic abstraction for one caller.

### User-facing behavior table

| Observed state | Behavior |
|---|---|
| Unassigned source, ready target | Existing ready-work path; progress is context, never proof of source ownership. Reject incompatible options specifically, before writes. |
| Assigned unfinished task | Checkpoint/resume or scoped switch; no success, commit or closure prerequisite. |
| Assigned source with existing reservation | Recover exact reservation; incompatible target/mode/checkpoint stays blocked without new allocation. |
| Preparation rejected, no reservation | Return actual rejected condition and no transition ID; correct input/environment, not uncertain-launch recovery. |
| Same task, approved existing worktree | Existing child-session transition with target checkout/header; never relabel parent or treat shell `cd` as host switch. |
| Canonically closed source with matching successful closeout | Existing verified-closeout handoff. Incomplete export remains closeout repair, not new success. |
| Canonically closed source with recorded non-success disposition | Guarded owner-local terminal release/next-work path; retain exact outcome and close reason. No success-dependent delivery authority. |
| Missing/foreign owner or unknown in-flight effects | Specific conflict/recovery evidence; no timeout takeover, guessed release or repeated fresh-session prescription. |
| Host cannot launch | Explicit unsupported/host-required result; no fabricated launch. `/new` only where a genuinely unassigned target can start and host capability is the actual blocker. |

## 3. Implementation batches

Implement serially: most batches share lifecycle/adapter files. Use one implementation scope, or a few dependency-linked outcome-sized Beads if context/repository boundaries require it—not one ticket/approval per helper. Existing unrelated plans and work remain untouched.

### Batch A — Freeze behavior and reconcile guidance

**Files:** `pi/agent/AGENTS.md`; `skills/project-init/references/audit-checklist.md`, `skills/project-init/templates/AGENTS.md`; `skills/using-git-worktrees/SKILL.md`, `skills/executing-plans/SKILL.md`, `skills/dev-workflow-common/SKILL.md`; `extensions/bead-handoff.ts` guidance; relevant sections of `pi/agent/bin/README.md`, `pi/README.md`, `work_lifecycle.SPEC.md`; tests `test_context_architecture.py`, `test_beads_workspace.py`, `test_bead_handoff.py`.

1. Establish current source/installed-host baseline and existing task authority. Resolve implementation dependency policy once; upgrade supported graph or obtain a new exact exception. Do not reuse pi-sq8l grants or silently expand into dependency migration.
2. Convert acceptance rows into shared synthetic journey fixtures using existing test helpers. Keep previous shared-checkout regressions. Add focused failing assertions for actual contradictions, not broad snapshots of prose.
3. Correct BEADS-2/3 to distinguish unfinished continuation from successful-closeout handoff. Remove copies of the obsolete success-only rule.
4. Make worktree instructions distinguish Git creation, shell cwd and persisted Pi context. No blanket requirement to isolate because unrelated untracked files exist; inspect overlap and preserve them. Do not advertise relocation support until Batch D passes.
5. Make execution guidance inherit shared direct/isolation choice; keep explicit approval for actual integration/deployment/deletion. Read-only peers do not claim implementation ownership.
6. Audit generated context, selected role overlays, tool descriptions/kickoffs, `bd prime` output and project-init output together. Raw Beads quickrefs do not override Pi closeout policy; do not install hooks or patch third-party prompts as a shortcut.
7. Read `skill-creator` before changing skills. Replace contrary text at its owner; do not append another exception paragraph everywhere. Historical plans are explicitly deferred, not silently treated as current rules.

**Verify:** `.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_beads_workspace.py tests/test_bead_handoff.py -q`; render `agnt instructions --context openai-codex/gpt-6-astra --sources` and with existing role `implementation-worker`. Inspect rendered output, not source alone. Guidance matching future runtime changes lands with those batches, never ahead of unsupported behavior.

### Batch B — Make registration metadata-only and errors truthful

**Files:** `agnt_lib/work_lifecycle.py` (`claim`, `guard_session_link`); `work.py` (`direct_start`, closeout failures); `quality.py`/`improvement.py` only where error propagation requires it; lifecycle SPEC; tests `test_work_lifecycle.py`, `test_work_continuation.py`, `test_agnt.py`, `test_closeout_authority.py`.

1. RED tests: claim an unborn Git repo containing a synthetic unreadable/large file and ignored sentinel; claim an existing repo with submodule/gitlink changes. Assert file bodies are never opened and real same-Bead/session conflicts still reject before Beads claim/link.
2. Replace `workspace_snapshot(checkout)["checkout"]` in claim with existing `checkout_identity(checkout)`. Keep snapshot behavior at checkpoint/transition boundaries; do not weaken those checks to make claim pass.
3. Raise the existing ownership-conflict type only for actual owner/session conflicts. Remove catch-all conversion of ValueError. Preserve safe original causes for storage, header, checkout and validation failures; no exception-class hierarchy or message-regex classifier.
4. Reuse existing response stages/repair fields; add only a small stable reason discriminator if callers need it. Distinguish busy same-Bead, finalized session, checkout mismatch, invalid/missing context, authority denial and non-ownership error. Do not expose secrets or entire native stderr.
5. Preserve bounded/redacted useful Beads/Git diagnostics for native close/export/stage failures, including deferred children and signing errors. Error specificity does not permit force-close or unrelated commits.
6. Link remaining checkpoint/gitlink work to existing `pi-ys12`; metadata-only registration does not falsely claim to solve all snapshot behavior. Add its checkpoint case to release verification if the chosen rollout includes such repositories.

**Verify:** `.venv/bin/python -m pytest tests/test_work_lifecycle.py tests/test_work_continuation.py tests/test_agnt.py tests/test_closeout_authority.py -q`. Assert no Beads/quality/journal mutation on rejected preflight, and no content reads during successful registration.

### Batch C — One continuation decision, truthful adapter routing

**Files:** `work_lifecycle.py` (`transition_context`, `transition_check`, `prepare`, transition CLI results); `work.py`; `extensions/bead-handoff.ts`, `lib/work-continuation.ts`; tests `test_work_continuation.py`, `test_work_lifecycle.py`, `test_continuation_extension.py`, `test_bead_handoff.py`.

1. RED table-driven tests for unassigned, unfinished, finalized-success, finalized-non-success, pending reservation and malformed context, with/without progress and other options.
2. Have domain inspection distinguish real source states rather than collapsing unassigned and closed to `legacy`. Preserve legacy reconciliation when evidence is actually insufficient. Adapt tool and slash-command dispatch to the same result.
3. Let explicit transition IDs/modes keep their exact meaning; progress alone must not select continuation or create ownership. Do not silently discard incompatible options or checkpoint progress.
4. Extract only the shared pure eligibility checks needed by both readiness and preparation. Preparation reruns them under existing journal lock with fresh authority/workspace facts. No claim that read-only readiness reserves anything.
5. Reuse state/transition fields to distinguish rejected-before-reservation, reserved, launch-requested/unknown and attached. Remove generic uncertain-attachment recovery from no-reservation errors in both Python and TypeScript.
6. Repair same-Bead same-checkout resume to follow already-supported shared-direct ownership semantics. Unrelated checkout occupants must not veto a matching owner's resume. Retain cross-Bead isolation, foreign target ownership, pending reservation and snapshot guards.
7. Keep existing bounded retries only for genuinely uncertain attachment. Do not introduce automatic replay of unknown effects or a fresh transition ID on retry.

**Verify:** `.venv/bin/python -m pytest tests/test_work_lifecycle.py tests/test_work_continuation.py tests/test_continuation_extension.py tests/test_bead_handoff.py -q`. Include two accepted direct owners → each resume/close, plus readiness/prepare parity on unchanged state and expected rejection after injected drift.

### Batch D — Support already-approved same-task relocation through existing transition

**Files:** `work_lifecycle.py` (`prepare`, stage/attach validation and authorization); `lib/work-continuation.ts` only if existing launch arguments need correction; worktree/execution guidance; tests `test_work_continuation.py`, `test_work_isolation.py`, `test_continuation_extension.py`.

1. RED reproduction: task linked in main, approved sibling worktree exists, same-Bead continuation to it. Test current deterministic identity rejection and readiness mismatch.
2. Permit relocation only through an owning-source transition to a verified existing checkout in the same canonical repository and captured authority. No shell-only rebinding, foreign-owner adoption or new schema.
3. Reuse existing source checkpoint, target workspace snapshot, reserved child/header, sourceQualityDirectory and attachment callback. Move execution checkout binding only at successful child attachment; retain source evidence and files unchanged.
4. Reject target collisions, source/target drift, wrong repository/header, revoked authority and unresolved source effects. Cancellation restores the original owner; lost acknowledgement uses existing exact-reservation reconciliation.
5. Do not copy/stash/commit/merge source dirt. Child progress identifies where source work remains; acceptance includes returning safely. Relocation is not proof source work has been integrated.
6. Exercise actual existing process-replacement adapter against disposable persisted sessions. If its current host interface cannot safely deliver this contract, report the precise capability gap and return for design decision; do not quietly start the deferred host patch project.

**Verify:** `.venv/bin/python -m pytest tests/test_work_continuation.py tests/test_work_isolation.py tests/test_continuation_extension.py -q`. Native fixture journey checks tool cwd, project instructions, session header, ledger binding and normal target closeout—not only journal dictionary values.

### Batch E — Separate terminal execution from successful work

**Files:** `work_lifecycle.py` (`release_completed`, context); `work.py` (`handoff_check`, closeout release); `quality.py` (`session_handoff_source` callers, not immutable history); `bead-handoff.ts`; lifecycle SPEC and shared guidance; tests `test_work_lifecycle.py`, `test_work_continuation.py`, `test_bead_handoff.py`, `test_closeout_authority.py`, `test_quality_lifecycle.py`, `test_beads_workspace.py`.

1. RED cases: canonical cancelled/Wontfix task with retained partial/failure outcome; successful close/export interruption; manually closed task with missing evidence; another session attempting release; pending launch; dirty cancelled workspace.
2. Generalize existing release operation narrowly: lifecycle `completed` means that execution has ended, while quality outcome remains the separate success/non-success fact. Rename internal method to describe terminal release; update all callers/spec/tests. Reuse existing phase/schema only after proving no consumer treats phase alone as task success. Do not add parallel terminal flags or rewrite old outcomes.
3. Release non-success execution only from its owning host/session with matching header/checkout, canonical closed/disposition evidence, and no pending or unknown admitted effects. A closed Bead, dead PID, elapsed time or non-success outcome alone is insufficient. Missing/foreign ownership remains a specific genuine blocker.
4. Add this bounded terminal path to existing handoff operation, not a force/reconcile administration command. Target selection still requires actual user scope/current authority; completion of one task grants no broader scope.
5. Never synthesize success or a new successful attempt solely to unblock switching. Never allow this path to bypass export/commit repair after successful delivery or authorize success-dependent push/integration.
6. Preserve dirty cancelled work. Same-checkout next-work handoff still requires a safe clean workspace; an approved isolated target may be used through existing host transition. Do not auto-create, clean or delete anything. If isolated departure cannot use existing machinery safely, stop this case for explicit design resolution rather than misreport it as fixed.
7. Legacy terminal owners belonging to unavailable/different sessions are not swept or reclassified. New independent work must not inherit their checkout-wide veto; same-Bead ambiguous recovery remains protected and explicitly reported.

**Verify:** `.venv/bin/python -m pytest tests/test_work_lifecycle.py tests/test_work_continuation.py tests/test_bead_handoff.py tests/test_closeout_authority.py tests/test_quality_lifecycle.py tests/test_beads_workspace.py -q`. Verify original outcomes/owners/files byte-for-byte except the exact authorized terminal release.

### Batch F — End-to-end acceptance and matched-host rollout

**Files:** extend existing lifecycle/extension/native-Beads tests; `tests/test_context_architecture.py`; `pi/README.md` recovery instructions; deployment helper/tests only if a bounded multi-file delivery capability is actually needed. Reuse existing deployment machinery; do not turn its single-file allowlist into arbitrary-copy permission.

1. Run complete journeys below against final candidate using real temporary Git/Beads and persisted fixture sessions. Follow each successful start through continuation and completion. Existing test helpers, no new model-evaluation framework.
2. Independent review checks simplification, caller parity, terminal-success separation, locking and disclosure. Check every modified helper's callers, exported tools, fixtures, docs, role context and tests.
3. Stabilize/stage task-owned candidate, then run full project matrix once. Report plugin currency, dependency/security exceptions, source checks and deployed runtime separately. No inherited undici exception.
4. Before deployment, inventory each explicitly requested host: canonical source/destination, OS/account, actual Pi entrypoint/version, helper/extension/guidance hashes, Beads executable/version and project-local overlays. No remote access or writes implied by this plan.
5. Obtain exact deployment approval covering coherent changed files and rollback. Python helpers take effect next process; guidance/TypeScript extensions can remain cached until supported reload/restart. Inspect pending transitions before restarting; do not strand them by swapping incompatible adapters.
6. Verify installed hashes and one disposable start→resume/relocate→close journey on each approved host. Compare loaded/rendered guidance as well as files. Older immutable session messages remain history, not current guidance; do not edit them.
7. Re-read canonical status of specifically affected tasks before any recovery. A reported blocked task may already have been manually closed. Preserve its actual outcome; no redundant close/export/deploy replay.

## 4. Acceptance journeys and preservation controls

| ID | Journey | Required proof |
|---|---|---|
| J1 | Unassigned start in unborn repo, large/ignored files, changed gitlink | No content reads; correct registration or specific metadata error; no false conflict. |
| J2 | True same-Bead foreign owner / finalized same-session relabel | Refusal before claim/link; exact cause; no `/new` prescription as takeover. |
| J3 | Two direct tasks share checkout | Both start; own resume and close work; other owner/history unchanged. |
| J4 | Unassigned ready handoff with progress | State-based selection or precise incompatible-option refusal; no unfinished-source lie. |
| J5 | Dirty unfinished task A→B→A within captured scope | Existing isolation/snapshots preserve files, outcomes and decisions; no close-first rule. |
| J6 | Readiness then prepare, unchanged versus drifted facts | Same result when unchanged; specific race rejection when changed. |
| J7 | Rejection before reservation versus lost launch acknowledgement | No invented transition in former; exact existing recovery and no blind retry in latter. |
| J8 | Same-Bead main→existing worktree→source | Real child contexts match checkout; parent header/history and source dirt preserved. |
| J9 | Cancelled/Wontfix owner finishes; next approved work | Terminal release without success rewriting; safe clean/isolated destination. |
| J10 | Foreign/manual closure, absent owner proof or unknown effects | No guessed release; readable missing fact and real recovery target. |
| J11 | Native close succeeds, export/stage/commit fails | Retry missing closeout work with original reason/outcome; no fresh assignment bypass. |
| J12 | Dirty unrelated tracked work / deferred children / authority revoked | Existing refusal preserved with safe actionable cause, no force or scope widening. |
| J13 | Rendered global + role + project + tool + skill guidance | No success-only unfinished handoff, shell-cd host-switch promise or unconditional fresh-session repair. |
| J14 | Host capability/deployment mismatch | No claim of launch or remote repair based on local source tests; exact installed evidence. |

For supported normal journeys measure: manual session commands = 0; repeated approval for an already-approved identical action = 0; lost/rewritten work/history = 0; false ownership/uncertain-launch diagnoses = 0. Real approval changes, unsafe ownership and unsupported hosts remain explicit exceptions, not silently waived failures.

Use deterministic tests for routing/guidance contradictions and real state transitions. Static phrase assertions alone do not establish model behavior. One small actual-model canary may be recommended later for a named unresolved instruction-following question; not a prerequisite for deterministic repairs and not authorized here.

## 5. Verification commands

Focused commands appear per batch. Confirm new fixture names against actual implementation; avoid fragile assertions about a fixed total test count.

```bash
npm ci --ignore-scripts
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python scripts/check-python-tests.py
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
agnt instructions --context openai-codex/gpt-6-astra --sources
agnt instructions --context openai-codex/gpt-6-astra --role implementation-worker --sources
git diff --check
git diff --cached --check
```

Implementation baseline must be fresh. Today's prior repair passed 1,756 tests; that is historical evidence for `399567b`, not a pass for this unimplemented plan.

## 6. Dependencies, limits and exit

- Batches B–E modify `work_lifecycle.py`/`work.py`; C–E modify handoff adapters. Serialize writes; do not create competing parallel implementations.
- Guidance audit starts first, but each behavior promise lands with its tested runtime support. Final generated/loaded-context verification follows all batches.
- Existing `pi-ys12` owns full snapshot/gitlink repair; coordinate rather than duplicate. Broader telemetry attribution and arbitrary legacy orphan recovery are not prerequisites for core repair and are not claimed solved.
- Do not change same-task exclusivity, immutable outcomes, host identity, authority or snapshot trust boundaries merely to meet a zero-interruption metric.
- If safe relocation/terminal departure needs deferred host/schema architecture, stop at that concrete failed journey, retain green repairs, and ask one scoped design decision. Do not silently broaden this plan into the old migration project.
- Success means accepted journeys pass, contradictory guidance is removed, and approved affected-host deployment is verified. Source-only completion must be labeled source-only; unresolved legacy recovery remains a named limitation.

## Plan validation

Read-only source review completed 2026-10-27. Independent boundary review found no concrete defects in the proposed plan; validated findings: `.pi/reviews/lifecycle-guidance-plan/findings.json`, retained reviewer artifact `runtime:delegated-results/7ff08d8b-4310-4c17-b71f-46756f9b7a77/child-0.json`. Verified all ten explicitly referenced `tests/test_*.py` paths exist and all fourteen acceptance journeys are present. This is plan review, not implementation verification; runtime tests and remote deployment were not performed for this planning task.

## Execution Handoff

Plan saved to `.pi/plans/2026-10-27-lifecycle-guidance-simplification-plan.md`; verify with `test -f` and `wc -l` before handoff.

Initial setup completed under `pi-pvjr`/`pi-fhh6`; continue its actual owning execution, not another fresh claim. Current implementation evidence and remaining gates belong in `pi-pvjr` notes and their referenced artifacts. Read `test-driven-development` for behavior changes, `skill-creator` for skill edits and `verification-before-completion` before completion claims. This plan creates no deployment, cleanup or ownership-override authority.
