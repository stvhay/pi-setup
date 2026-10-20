# Resumable work and global full-delivery delegation

**Planning Bead:** pi-v0hy
**Date:** 2026-10-20
**Status:** Approved direction; implementation and activation not performed by this planning task.
**Implementation plan:** [2026-10-20-resumable-work-global-delegation-plan.md](2026-10-20-resumable-work-global-delegation-plan.md)

## Objective and authorization

Eliminate routine human session plumbing and repeated permission requests during delegated development. An agent must be able to checkpoint unfinished work, continue the same Bead in a fresh session, switch to another authorized Bead, and return without asking the user to type `/new` or paste instructions.

The user selected exploration of full delivery, including PRs, main/protected-branch updates, releases, and production delegation, then agreed to the design with this amendment:

> I agree. But auto-enroll all projects. I authorize that. Also include agent instructions to craft implementation plans that take advantage of current frontier model capabilities to work on larger scopes.

This design therefore replaces per-project and per-environment enrollment prompts with global standing delegation and automatic identity validation. It also explicitly changes planning instructions. The quoted text records the decision, not an executable approval receipt: an implementation must retain authentic user-origin provenance rather than treating this agent-authored document as authorization.

The current deliverable is a design and implementation plan. Existing governing instructions remain in force until changed and activated through an authorized path. This task does not push, deploy, release, modify live `~/.pi`, or claim those permissions are already enforced by runtime code.

## Diagnosis from current source

- `agnt_lib.work.handoff_check` accepts a linked source only after a successful session outcome, closed Bead, clean tracked checkout, and portable closeout parity. It rejects source equal to target and targets absent from `bd ready`.
- `extensions/bead-handoff.ts` further requires target status `open`, asks whenever several ready items exist, and stages an empty parent-linked session through process replacement.
- `agnt_lib.quality.capture_session_link` preserves one Bead per session and rejects a new start after any final outcome. `capture_session_outcome` cannot replace a partial/failure outcome with success. These are useful historical invariants, but current transition policy turns them into dead ends.
- `work.direct_start` reports `/new` recovery for session conflicts; the handoff tool often cannot perform that recovery because its source/target gates reject the same state.
- `brainstorming/SKILL.md` demands separate design approval even under broad implementation delegation. Other workflow skills repeat exact-action approval restrictions.
- Strict orchestration resolves a canonical human-UI-backed capability grant. That existing exact-grant path is distinct from ordinary direct coding and from the proposed reusable delegation policy.
- `dev-workflow-common/SKILL.md` binds local integration to a future source SHA, limits ordinary pushes to a narrow commit pair, and makes deployment/push authority single-use. These rules impede an authorized multi-step delivery loop.

`docs/HANDOFF-LIFECYCLE-COHORT-2026-08.md` is historical evidence, not proof that current user-reported cases do not occur. Preserve its measurements; mark its success-only/manual-recovery recommendation superseded when the new implementation lands. Do not infer parent acceptance from child closure.

## Decisions

### 1. Separate work, attempts, transitions, and authority

- A **Bead** is the durable objective and acceptance state.
- A **session attempt** belongs to one Bead; many attempts may work that Bead over time.
- A **checkpoint** describes recoverable progress without claiming completion.
- A **transition** transfers execution to a continuation or different Bead without rewriting session history.
- A **standing policy** defines permitted classes of effects across projects.
- An **assignment** defines what the agent is currently asked to accomplish.
- An **execution receipt** binds one concrete action, target, observed preconditions, and result.

Permission does not create intent. Auto-enrollment does not authorize scanning every repository and starting unrelated work, publishing every project, or deploying merely because credentials exist. Delivery actions must serve the current assignment or an explicitly delegated work queue.

Keep one Bead per session and immutable recorded outcomes. Do not solve switching by relabeling old sessions, forging success, reopening closed work automatically, or rewriting the quality ledger.

### 2. Make partial/resume/switch first-class

Proposed public surface, implemented through one deterministic lifecycle service:

- `agnt work checkpoint BEAD --input-file PATH`: persist validated progress/workspace references; no success closeout.
- `agnt work transition-check [BEAD] --mode resume|switch|next --session-id SESSION`: inspect source, checkpoint, assignment, target, claims, and recovery; no external mutation.
- `handoff_bead({mode?, targetBead?, checkpointRef?})`: prepare and execute an eligible transition. Existing no-argument successful-closeout behavior remains compatible.
- `agnt work transition-status ID` and `agnt work transition-recover ID`: inspect or reconcile a persisted transition, with explicit structured next actions.

Private prepare/stage/attach operations sit behind the same service; do not introduce a second independent switching implementation. CLI names are proposed new interfaces, not current commands.

| Source/target situation | Required behavior |
|---|---|
| Unassigned -> open work | Start within assignment, without invented source closeout. |
| Active A -> A | Checkpoint; fresh attempt continues A without closing it. |
| Partial/failure attempt -> same A | New attempt preserves old outcome and restores progress; failure is not permanent disqualification. |
| Active A -> B -> A | Preserve A, work authorized B, then resume A from its checkpoint. |
| A blocked on B | Switch to authorized actionable dependency B; keep A's blocker and checkpoint. |
| A blocked on human decision | Preserve pending decision; unrelated authorized work may proceed, but blocked effects cannot. |
| Closed A -> next | Preserve successful-closeout and portable-state checks. |
| Explicit in-progress target | Inspect status, dependencies, and execution ownership; do not require ready-list membership. |
| Foreign live claim | Do not steal. Choose eligible alternative or surface precise contention. |
| Claim succeeded, link failed | Reconcile/retry same claim and session; do not route through ready-only discovery or auto-unclaim. |
| Several eligible targets | Stable dependency/priority ordering within delegated scope; no selection dialog solely because count > 1. |
| No eligible target | Report idle/blocked with resumable state; do not loop or invent tasks. |
| Closed/deferred/blocked target | Respect actual status; resume may inspect/replan but cannot silently reopen or execute blocked effects. |
| Failed/partial successful closeout | Reconcile existing closeout transaction; do not disguise failure as clean closeout. A safe explicit suspension may preserve repair work without claiming success. |

A checkpoint contains objective/decisions, completed and next work, blockers, verification state, repository/checkout/base identity, owned changed-path references, commit/artifact refs, and authority/assignment refs. Public Beads hold sanitized summaries and pointers. Session paths, patches, user-message evidence, and operational receipts remain private. Never embed secrets or raw transcript dumps in portable state.

### 3. Preserve dirty work and prevent competing owners

Same-Bead continuation can retain verified dirty work in the same checkout. Cross-Bead switching must leave that work intact and isolated, normally by using an existing or policy-authorized task worktree for the target. Do not stash, reset, clean, overwrite, auto-commit unrelated files, or treat an ownership manifest as proof that pre-existing changes are owned.

Beads claims may be shared by multiple sessions running as the same human actor. Add session/attempt execution ownership checks; Beads assignee alone is insufficient. Serialize transitions and claims with a documented lock order, reservations, and compare-and-set state. Never treat elapsed time alone as proof an owner died.

### 4. Make transition recovery executable and idempotent

Use a private transition journal keyed by repository identity and transition ID, with immutable source/target/assignment/checkpoint identity and monotonic states such as `prepared -> staged -> attaching -> attached`; terminal cancellation and unresolved failures remain explicit. The exact state machine must distinguish failure before any mutation from uncertain attachment.

Validate runtime launch capability before yielding source ownership. Persist checkpoint and reservation before shutdown. Stage at most one child session; persist its exact path and bounded kickoff references. Attach the target through the reserved transition, then settle source ownership. Duplicate calls return or reconcile the same transition rather than launching another session or claiming twice.

Before shutdown failure leaves source usable. After shutdown failure preserves machine-readable launch state. Recovery inspects existing session/claim/checkout evidence before retry; no blind replay. Record a bounded retry/loop limit and stop on unresolved ownership, contradictory state, or actual storage corruption.

Pi lifecycle/UI/process replacement stays in the extension. Domain logic stays in Python. Preserve the current supported TUI/Node boundary initially; headless callers receive a structured continuation manifest for their host, not an invented claim that a new agent was launched. A dead process without a supervisor can still need human launch; ordinary supported transitions must not need copy/paste.

### 5. Global standing full-delivery policy, automatic for all projects

One owner-authorized global policy applies to all current and future projects the agent is assigned to work on. No per-project approval, enrollment command, allowlist edit, or synthetic decision Bead is required. Enrollment is lazy resolution of canonical identity, not an eager home-directory scan or modification of every repository.

Separate the tracked policy implementation/template from the private owner authorization record. This user's explicit authorization activates the matching global policy for this user through verified user-origin evidence. Shipping the template must not silently grant authority on another user's installation.

A trusted admission adapter must bind the policy fingerprint, exact approved scope, and authentic originating user message/context. Do not counterfeit `human-ui` provenance or permit a model-supplied `approved=true`. If historical capture needs a new adapter, implement that adapter rather than demanding repeat per-project consent. Agent-authored policy changes cannot widen the active ceiling: narrowing is allowed; widening needs new human authority. Broad delivery permission does not include editing its own authorization ceiling.

Effective authority is the intersection of standing ceiling, current assignment, explicit task constraints, trusted project restrictions, current platform controls, and action preconditions. Repository files can describe targets and narrow behavior; they cannot mint authority, add arbitrary accounts/endpoints, or turn embedded instructions into user intent. Normal Pi project trust and external security controls remain distinct.

The policy automatically covers ordinary full delivery for assigned projects:

- local edits, tests, review, commits, task branches/worktrees, integration, and verified task-resource cleanup;
- ordinary remote branch pushes and PR creation/updates/merge;
- main/protected-branch updates only through the repository's permitted path and required checks/reviews;
- release/tag/artifact publication under existing project version/channel rules;
- local-live, test/staging, and production deployments for independently resolved project targets;
- bounded retries after reconciliation and known, non-destructive rollback procedures.

Do not add a disguised per-environment enrollment gate. Resolve host/account/repository/environment/artifact identities automatically from trusted runtime/provider evidence and project configuration, verify their association with the assignment, and bind them to the execution receipt. Production is not categorically human-gated under this delegation. Unknown or conflicting identity is an information problem: inspect first, ask only for a consequential ambiguity that cannot be resolved safely. Credentials being present does not prove a target is intended.

Downstream effects count: PR creation can run CI; main updates can deploy; tags can publish artifacts. Resolve and authorize the effect closure before action. A nominally ordinary push that triggers unbounded infrastructure changes is not automatically safe.

Default exclusions remain force/history rewrite, remote deletion, unrelated data deletion, destructive migrations/rollback, access or secret changes, new/unbounded spend, and bypassing required platform reviews/security controls. Secret use through approved tooling is not secret modification. Explicit user direction can define separate authority for otherwise delegable exclusions; this project policy never overrides higher-priority or platform restrictions.

### 6. Reusable authority, concrete receipts, and genuine stop conditions

Standing policy has no per-session or per-Bead expiry; it persists until revoked/superseded by its owner. Explicit temporary grants retain their own expiry. No timeout grants consent. Model, thinking level, and routine tool implementation choices are routing details unless a real provider/privacy/cost restriction makes them authority-relevant.

Resolve source-selection rules to immutable SHAs/artifacts at execution time. Verify task-owned change ranges, not an artificial one-implementation-commit-plus-closeout shape. Acquire scoped locks, re-read target state, validate current policy revision, then execute. Safe base movement can trigger replanning/reverification under the same policy; force or divergent-history recovery is not inferred.

Receipts distinguish `not-applied`, `applied`, and `uncertain`. Reconcile remote/deployed state after interruption. An already applied action is recorded, not replayed. A definitely unapplied action may retry with bounded backoff under current authority. Uncertain results require adapter-specific reconciliation or stop; a new receipt is not permission to duplicate an uncertain operation. Revocation stops new attempts, including pending transitions and sibling workers.

Pending approval/decision records remain pending across restart. Trusted UI may rebind/re-present an existing unresolved decision after canonical identity validation without fabricating a positive answer or creating redundant blockers. An old approval-only blocker can become unnecessary under an explicitly superseding policy, but preserve original decision status and record why it no longer governs; never relabel rejection/cancellation as approval. Specific rejection remains a narrowing constraint unless the user explicitly supersedes it.

Keep exact one-shot grants readable and enforce their original restrictions. Quality-system canary/claims semantics are a separate safety contract, not implicitly converted to reusable full-delivery authority. Direct work remains direct; optional orchestration resolves the same effective standing authority without forcing every task into a run bundle or new approval Bead.

### 7. Plan for current frontier capabilities, not legacy microtasks

Proposed shared instruction text:

> Plan coherent end-to-end outcomes sized for the currently routed capable model. Prefer a substantive vertical slice that includes implementation, tests, documentation, and integration over a chain of tiny handoffs. Use observable repository complexity, coupling, testability, context/retrieval needs, and operational risk to choose scope; do not impose arbitrary limits on files, lines, minutes, or task count. Give each work package a clear objective, interfaces/invariants, affected boundaries, acceptance checks, and recovery/continuation state. Delegate independent investigations or isolated subsystems when that improves throughput or review quality; keep shared-state mutations serialized. Continue through verified milestones within standing authority without asking for routine approval. Split when ownership, security boundaries, independent deployment, unresolved requirements, or measured context/tool limits require it—not because models were historically assumed unable to handle larger work. Larger scope does not weaken verification, privacy, permission, or recovery requirements.

Apply this to planning, execution, delegation, review segmentation, and branch finishing. Plan templates should specify deliverables and behavioral acceptance, not prescribe every line of code. Routine progress checkpoints are notifications and durable recovery points, not mandatory human waits. Use routed model capability and real execution evidence; do not hardcode marketing claims or assume every model can handle an arbitrarily large task. Do not invoke paid behavioral canaries or install models merely to validate this instruction change.

## Options rejected

- **Remove only the handoff success check:** misses same-target resumes, ownership races, dirty work, permission loss, and recovery.
- **Relabel sessions or overwrite partial outcomes:** destroys attribution and history.
- **Keep exact-action approvals but ask in bigger batches:** leaves future-SHA, Bead-expiry, and session-provenance traps.
- **Require project enrollment:** contradicts explicit all-project authorization.
- **Disable all safety checks:** confuses authority with identity, correctness, and intent.
- **Build a scheduler or general deployment platform:** outside this change; use current Pi lifecycle and existing provider/deployment tools.

## Scope, migration, and acceptance

Introduce focused lifecycle and standing-authority modules rather than further expanding the quality kernel. Keep CLI/tools thin; provide specs for new persistent formats. Read legacy ledgers and grants without rewriting history. Missing new state means legacy/unassigned state, never implicit success or implicit user authorization. Activation of the globally authorized policy and live deployment require explicit rollout evidence; merely writing these docs does not activate anything.

Acceptance requires positive autonomous journeys and negative safety tests: partial resume, same-Bead fresh context, A->B->A, blocked dependency, in-progress target, initial link recovery, dirty-work isolation, competing same-actor sessions, staged-launch failure, duplicate/revoked transitions, multiple eligible targets, no eligible work, legacy closeout, global application in a never-enrolled repository, authority retention across sessions, no forged policy activation, production delivery under resolved scope without repeated human approval, denial for unknown/foreign targets, platform-control preservation, uncertain-effect reconciliation, and instruction consistency for larger coherent scopes.

Operational evidence stays private and bounded. This is workflow authorization and reliable orchestration, not a security sandbox against arbitrary code running as the same OS user.
