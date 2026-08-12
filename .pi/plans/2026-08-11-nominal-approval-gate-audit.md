# Nominal Approval Gate Audit

**Bead:** `pi-c65z.1` — Map duplicate approval gates in nominal workflows

**Parent:** `pi-c65z` — Collapse nominal development work to one approval

**Date:** 2026-08-11

**Status:** Current-state audit and target design; not active policy

## Decision summary

Use one informed scope approval for a bounded nominal workflow. After that approval, deterministic checks may execute already-authorized reversible local actions; they must stop rather than ask again when an invariant fails. Ask again only when scope, stakes, policy, environment identity, reversibility, or uncertainty materially changes.

This audit does not itself authorize worktree creation, integration, cleanup, push, deployment, or other currently gated actions. Active system/developer policy and project `AGENTS.md` remain authoritative until successor Beads revise and validate those rules. A generic `pi.approved=true` marker is not proof that a particular push, deployment, deletion, or integration was approved.

## Counting method and authority

A count is one distinct human authorization decision. Initial scope approval counts as one. Repeated confirmation for an action already named in that scope counts again. Read-only inspection, deterministic validation, model review, test execution, outcome recording, and fail-closed stops do not count. Same-trigger, same-stakes actions may share one approval; materially different stakes may not.

Authority order for this design:

1. Active system/developer policy and explicit current human constraints.
2. Project instructions in `AGENTS.md`.
3. Deployed global-source instructions in `pi/agent/AGENTS.md`.
4. Durable Beads decision/approval records.
5. Workflow skills and architecture documents.
6. Deterministic helper behavior and tests.

Lower layers may narrow behavior or stop safely. They may not silently widen authority granted by a higher layer.

## Representative approval counts

Each scenario starts with an approved, bounded Bead; known repository and target identity; task-owned scope; no secrets; no production effects; no unrelated changes; and passing required checks.

| Representative workflow | Current approvals | Target approvals | Current duplicate checkpoints removed by target | Extra approval that remains an escalation |
|---|---:|---:|---|---|
| Direct-main/current-checkout development | **1** | **1** | None. Project instructions already make direct work normal and include one task-owned local commit. | Scope expansion, ambiguous ownership, policy conflict, remote/destructive action, or unknown environment: **+1 or stop**. |
| Feature worktree through local integration and cleanup | **4**: scope, create, integrate, cleanup | **1** | Separate worktree-creation, local-integration, and task-owned cleanup approvals. | Dirty/ambiguous base, conflict repair outside scope, untracked data, remote deletion, history rewrite, or unexpected target divergence: **+1 or stop**. |
| Parallel worktrees through serialized local integration and cleanup | **4**: scope, parallel create/dispatch, integrate, cleanup | **1** | Separate parallel-mode/worktree, integration, and cleanup approvals; same-stakes worktrees batch once. | Overlapping writes, shared mutable environment without isolation, conflict repair, stale/unknown lock ownership, or unexpected target divergence: **+1 or stop**. |
| Upstream-PR candidate through verified user-fork staging | **2**: scope, push/public staging | **1** | Separate fast-forward push/staging confirmation, but only after root policy is revised to match exact standing safeguards. | Fork creation, force/non-fast-forward push, upstream-repository draft, reviewer request, Ready state, merge, release, deletion, or history rewrite: **+1 or human-only/stop**. |
| Verified local-live Pi config or explicitly designated test/staging deployment | **2**: scope, deploy | **1** | Separate deployment approval for target already named in initial scope. | Production, unknown target, secrets change, destructive rollback, or unexpected remote/environment identity: **+1 or stop**. |
| Direct closeout plus one ready-Bead handoff | **0 incremental**; enclosing direct flow remains **1** | **0 incremental**; enclosing flow remains **1** | None. Current closeout and handoff are deterministic lifecycle operations after successful work. | Partial/failed outcome, dirty tracked state, ownership mismatch, unresolved blocker, multiple materially different next items, or unavailable fresh-session preconditions: **selection/stop**, not silent continuation. |

### Upstream publication boundary

“Upstream-PR candidate” above ends at a draft in the user's verified existing fork. Creating a fresh draft against the upstream repository is external communication with possible notifications and remains a separate informed approval under `preparing-upstream-pr`. Marking Ready, requesting reviewers, merging, releasing, and signing human attestations remain human-owned or separately gated; they are not part of the one-approval nominal envelope.

## Action matrix

| Workflow / action | Authority source | Current checkpoint | Stakes and reversibility | Duplicate or conflict | Target coverage and escalation |
|---|---|---|---|---|---|
| All: informed scope approval | `pi/agent/skills/brainstorming/SKILL.md` § Hard gate; `pi/agent/bin/agnt_lib/approvals.py`; `pi/agent/extensions/beads-ask-bridge.ts` | One human approval before writes | Defines allowed effects and exclusions; local changes are usually recoverable, but vague authority is unsafe | Bead existence alone is sometimes mistaken for approval; current target metadata reduces approval to a generic boolean | Retain. Preview exact action, workflow class, repository/target, write set, allowed effects, excluded effects, consequences, recovery, verification, closeout, and stop conditions. Scope or stakes change escalates. |
| Direct: `bd prime` / ready inspection / `direct-start` | `pi/agent/AGENTS.md` § Development workflow; `pi/agent/bin/agnt_lib/work.py::direct_start` | No human approval | Read/claim/session-link state; idempotent or retryable | Lifecycle setup can be mistaken for implementation authorization | Approved Bead identity plus deterministic Bead validation and one-session/one-Bead ownership. Conflict starts fresh session or stops. |
| Direct: edit current checkout | `AGENTS.md` § Workflow; `docs/ORCHESTRATION-LOOP.md` § Decision; `pi/agent/skills/executing-plans/SKILL.md` § Branch and dirty-tree policy | Initial scope approval; no second approval when project direct-work authority and exact write scope apply | Local tracked edits are revertible; unrelated dirty state risks loss or accidental commit | `executing-plans` says generic implementation authority is not same-checkout authority, while project policy makes direct current-session work the default | Treat project direct-work rule plus exact initial write scope as same-checkout authority. Stop on unrelated tracked changes, ambiguous ownership, protected policy, or scope expansion. |
| Direct: stage and commit task-owned changes | `AGENTS.md`; `pi/agent/AGENTS.md`; `pi/agent/skills/dev-workflow-common/SKILL.md` § Development completion contract | Included in explicit implementation approval | Local commit is recoverable without rewriting published history | `executing-plans` says not to commit without explicit approval; no conflict when initial decision explicitly approves implementation because project policy includes one local atomic commit | Initial scope covers one task-owned atomic commit. Deterministic staged-path check excludes unrelated files. Amend/reset/rewrite or extra unrelated commits escalate. |
| Direct: verification and review | `AGENTS.md` § Verification; `verification-before-completion`; `finishing-a-development-branch` | No human approval | Read-only or test-local effects; catches defects | Phase checkpoints may become conversational approval theater | Execute documented focused/final checks. Failures stop or reopen scope; non-trivial/risky review is evidence, not authority. |
| Feature: create branch/worktree | `pi/agent/skills/using-git-worktrees/SKILL.md`; `pi/agent/bin/agnt_lib/worktree_policy.py::epic_worktree_spec` and `resolve_epic_worktree` | Separate approval when epic worktree does not exist | Local branch/path creation is reversible; wrong base/path can contaminate work | Hard-coded `needs-approval` duplicates a sufficiently exact initial workflow approval | Initial scope may cover exact branch, path, and base. Before creation require clean known base, ignored local path, non-protected task branch, path/branch non-collision, and no unrelated work. Any mismatch stops. Successor: `pi-c65z.2`. |
| Parallel: select Mode B and create isolated worktrees | `pi/agent/skills/subagent-driven-development/SKILL.md` § Mode B and Safety gates | Separate explicit parallel-worktree approval | Multiple writers raise coordination and integration risk; isolation is locally reversible | Duplicates initial approval when that approval already names parallel mode, workers, write sets, worktrees, and integration | Batch same-stakes worktrees in initial approval. Require one writer per worktree, exact clean base, disjoint write sets, no shared mutable resource unless isolated, and verification per task. Overlap/unknown sharing stops. Successors: `pi-c65z.2`, `pi-c65z.3`. |
| Feature/parallel: task commits | `pi/agent/skills/dev-workflow-common/SKILL.md`; `subagent-driven-development` worker contract | Covered by implementation approval | Local and recoverable; preserves reviewable units | Some skill prose says workers commit while orchestration branch commit remains separately gated | Initial scope names branch/worktree commit authority. Staged-path and branch checks stop unrelated or orchestrator-checkout commits. |
| Feature/parallel: local integration | `AGENTS.md`; `pi/agent/AGENTS.md`; `pi/agent/skills/subagent-driven-development/SKILL.md` § Integrate one branch at a time | Separate approval unless workflow already approved integration | Mutates shared target; recoverable before push but conflicts can widen scope | Root blanket merge gate and later integration prompt duplicate an exact initial local-integration grant | Initial approval may cover exact local target and listed task commits after stable review. Require serialized mutation, clean unchanged target, exact source SHAs, conflict-free application, no unexpected divergence, and focused/full verification. Conflict or repair outside write set escalates. Successor: `pi-c65z.3`. |
| Feature/parallel: remove worktrees and local task branches | `AGENTS.md`; `pi/agent/AGENTS.md`; `using-git-worktrees` § Core rules; `subagent-driven-development` § Cleanup plan | Separate cleanup approval | Deletes local names/filesystem views; recoverable only if commits and no untracked work survive | Fixed cleanup gate duplicates initial authorization for exact task-owned, fully integrated assets | Initial scope may cover exact paths/branches. Require clean worktree, integrated/recoverable commit, no untracked or uncommitted data, no active owner, exact task ownership, and local-only deletion. Unknown data, force deletion, remote refs, history rewrite, or shared worktree escalates. Successor: `pi-c65z.2`. |
| Upstream: prove necessity and approve candidate scope | `pi/agent/skills/preparing-upstream-pr/SKILL.md` § Hard gates and Workflow 1 | Initial human agreement/approval | Starts public-contribution work and maintenance burden; no remote effect yet | Can duplicate generic design and implementation approvals if treated as separate decisions | One initial approval covers justified upstream candidate, implementation, local commit, review, and bounded fork staging only when all are previewed. Local alternative or unresolved upstream policy stops. |
| Upstream: verify fork/ref and normal push | `AGENTS.md`; `pi/agent/AGENTS.md`; `preparing-upstream-pr/SKILL.md` § Standing user-fork staging authorization; `references/pr-mechanics.md` | Project policy requires explicit push approval; specific skill says no per-action approval for guarded staging | Public remote mutation; follow-up commit can correct content, but publication and history remain observable | Direct conflict: project/global push gate and `docs/AGNT-SYSTEM.md` deny inherited push authority, while specific skill claims standing authorization | Current effective count retains separate approval. Target removal requires exact policy revision and invariants: verified existing user fork, reviewed clean scope, exact head/destination, absent-or-ancestor remote ref, no force/tags/release, no unrelated commits, and post-push SHA equality. Otherwise stop/escalate. Successor: `pi-c65z.5`. |
| Upstream: create/update fork-local draft | `preparing-upstream-pr/SKILL.md` § Stage on user's fork; `references/pr-mechanics.md` § Fork-local staging draft | Specific skill: no further approval; finishing skill generically says PR creation needs approval | Public review surface; edits/history remain observable | Specific upstream authorization conflicts with generic finishing rule, though preparing-upstream-pr is the more specific workflow; project push conflict still blocks preceding step | Include only with guarded fork-staging scope. Require fork-local base/head, reviewer-facing body only, no private data, no reviewers/mentions, open draft verification, and exact files/commits. Any upstream-repository target escalates. |
| Upstream: fresh upstream draft | `preparing-upstream-pr/SKILL.md` § Prepare the fresh upstream draft; `references/pr-mechanics.md` § Fresh upstream draft | Separate express approval | External communication; public immediately and may notify watchers | Not a duplicate: stakes change from user-fork staging to upstream publication | Keep separate informed approval with final title/body/refs/commits, visibility and notification consequence. Ready/reviewer requests/merge/release remain human-only or separately gated. |
| Config: validate tracked source | `AGENTS.md` § Repository and deployment policy; `scripts/check-pi-config.sh` | No approval | Read-only/local test effects | Verification can be mislabeled as deploy authority | Require passing documented checks and tracked `pi/` source. Failure stops. |
| Config: preview and identify destination | `scripts/update-pi-config.sh --dry-run`; destination guards in `validate_dest` | No mutation approval needed for dry run; current apply still needs separate deployment approval | Preview exposes managed deletions/installs; destination error could cause data loss | `AGENTS.md` permits deployment when requested or needed for verification, while `docs/ORCHESTRATION-LOOP.md` requires explicit approval for deployments | Conservative current policy uses separate deploy approval. Target initial scope must name verified local `~/.pi` or explicitly designated test/staging identity. Unsafe destination override, production, or unknown identity escalates. Successor: `pi-c65z.6`; decision: `pi-sjud`. |
| Config: apply deployment | `scripts/update-pi-config.sh`; `pi/README.md` § Deploy or update; `docs/ORCHESTRATION-LOOP.md` § Consequences | Separate current deployment approval | `rsync --delete`, exact package reconciliation, local runtime behavior change, optional evaluator sync; recovery exists but is not a single atomic rollback | Deployment gate duplicates initial scope only for a known approved environment with reviewed preview and rollback | Target initial scope covers verified local-live and explicitly designated test/staging only. Require exact source/destination, dry-run review data, preserved secret/state excludes, exact package versions/patches, backup/restore behavior, post-deploy check, and rollback evidence. Production/unknown/secrets/destructive rollback escalates. |
| Closeout: record outcome and close Bead | `pi/agent/AGENTS.md`; `dev-workflow-common`; `pi/agent/bin/agnt_lib/work.py::direct_closeout`; `tests/test_agnt.py` | No incremental approval | Closes durable work and commits portable Beads state; retryable but externally visible in repository history | Older/manual close prompts would duplicate deterministic completion contract | Keep automatic after task-owned commit. Require matching session/Bead/outcome, accepted outcome, no tracked non-Beads changes, canonical/export parity, only `.beads/issues.jsonl` staged, and verified portable-state commit. Failure leaves repair state. |
| Closeout: hand off one ready Bead | `pi/agent/AGENTS.md`; `pi/agent/extensions/bead-handoff.ts`; `pi/agent/bin/agnt_lib/work.py::handoff_check`; `tests/test_bead_handoff.py` | No incremental approval for one unambiguous ready successor | Replaces current process/session; staged child contains no transcript and failed replacement preserves recovery | Asking again after clean closeout duplicates already-selected work graph | Require recorded outcome, closed source, ready distinct target, persisted TUI session, and successful fresh-session staging. Multiple materially different ready items use one bounded selection; failed/partial/dirty closeout never hands off. Successor: `pi-c65z.4`. |

## Removed-checkpoint coverage

No checkpoint is removed merely because an action is “local.” Each target removal needs both exact initial authority and the listed deterministic invariant set.

| Removed checkpoint | Initial approval must name | Deterministic invariant that replaces repeated confirmation | Fail-closed escalation |
|---|---|---|---|
| Worktree creation | Workflow mode, exact base, branch, path, write set | Clean known base; ignored path; expected non-protected branch; no collision; no unrelated dirt | Dirty/ambiguous base, path collision, branch mismatch, or unknown ownership |
| Parallel dispatch | Worker/task partition, allowed files, worktrees, integration target | One writer per worktree; disjoint write sets; isolated mutable resources; verification per task | Overlap, shared external state, missing test command, or dependent tasks sent in parallel |
| Local integration | Exact target and source commits; allowed integration method | Serialized lock/semaphore; clean unchanged target; exact SHAs; conflict-free apply; focused then final checks | Conflict, divergence, stale/unknown lock, scope-widening repair, or failed check |
| Local worktree/branch cleanup | Exact local paths/branches and recovery SHAs | Integrated/recoverable commit; clean worktree; no untracked data; no active owner; local-only target | Unknown data/owner, force needed, remote ref, history rewrite, or failed integration proof |
| Verified fork push/staging | Existing user fork, remote branch, reviewed head, fork-local draft | Ownership verified; absent/ancestor remote ref; fast-forward/no force; clean reviewed scope; exact post-push SHA; no reviewers/mentions | Fork creation, non-fast-forward, unexpected ref/body, upstream target, or disclosure/privacy failure |
| Known local/test deployment | Exact environment identity, source, destination, managed effects, rollback | Passing repo checks; dry-run; safe destination; preserved secret/state excludes; exact packages/patches; post-deploy verification | Production/unknown identity, unsafe override, secrets, broad deletion, failed check, or no rollback |

## Approval design contract

Initial approval should be one short decision with expandable evidence, not a wall of text.

### Preview

- **Action:** named workflow and bounded effect set.
- **Scope:** Bead, repository, write set, base/target, optional worktree/fork/deployment identity, and explicit exclusions.
- **Consequences:** immediate mutation plus downstream integration, publication, deployment, or handoff effects.
- **Reversibility:** exact recovery source and limits; public history/notifications are never described as fully reversible.
- **Closeout:** verification, review, commit, Beads closeout, cleanup/handoff, and retained evidence.

These fields already exist and are required by `approval_request_payload()` and `ticket_approval`.

### Rejection, cancellation, timeout, and modification

Current approval mechanics create a durable blocker before showing UI. Approval requires human-UI provenance, closes the decision, and records target provenance. Rejection, cancellation, and timeout keep the blocker visible and mark any run blocked; no target action should execute. There is no automatic deadline/default execution path, so timeout fails closed.

Scope modification must use a revised preview and new approval. Current resolver code does **not** enforce this: an arbitrary answer can accompany `outcome="approved"`, after which the target still receives generic `pi.approved=true`. Until structured grant validation exists, any conditional, partial, or edited approval must be resolved as rejected/cancelled and re-issued rather than treated as authority for either the original or narrowed scope.

### Batch rule

Batch only actions sharing one Bead, trigger, stakes class, recovery model, and deterministic stop policy. Do not batch production with test/local deployment, upstream publication with fork staging, remote deletion with local cleanup, or force/history rewrite with fast-forward operations.

## Explicit current-policy conflicts and gaps

1. **Generic approval cannot currently grant remote/destructive effects.** `docs/AGNT-SYSTEM.md` says approval records do not grant push, merge, deployment, or history rewrite. Root/global instructions separately gate push, merge, branch deletion, worktree removal, and deployment. Target behavior remains inactive until those higher-priority sources are deliberately revised and tested.
2. **Fork staging authorization conflicts with project push policy.** `preparing-upstream-pr` permits guarded pushes and fork-local drafts without per-action approval; `AGENTS.md` and `pi/agent/AGENTS.md` require explicit push approval. Current effective behavior must stop for push approval. `pi-c65z.5` owns policy alignment.
3. **Deployment wording conflicts.** `AGENTS.md` allows deploy “when requested or needed for verification,” while `docs/ORCHESTRATION-LOOP.md` says deployments require explicit approval. Current conservative count is two. Human decision `pi-sjud` sets the target boundary, but `pi-c65z.6` must codify it before counts change.
4. **Worktree creation is hard-gated in code.** `resolve_epic_worktree()` returns `needs-approval` whenever the expected epic worktree is absent. Initial-scope preauthorization needs a validated action-specific approval reference or equivalent deterministic contract before this gate can be removed.
5. **Integration and cleanup remain blanket-gated.** Root/global instructions and skills require explicit merge, branch deletion, and worktree-removal approval. `pi-c65z.2` and `pi-c65z.3` must narrow these rules to exact reversible local assets and serialized integration; this audit does not do so.
6. **Approval metadata is too coarse for inheritance.** `resolve_beads_approval_request()` writes `pi.approved=true` and a decision reference, but does not encode allowed effects, repositories, branches, paths, environments, expiry, or stop conditions. Successors must validate scope from durable structured data or an exact immutable preview, not infer blanket authority from the boolean.
7. **Commit wording is only conditionally aligned.** Project/common instructions say implementation approval includes one local task-owned commit; `executing-plans` forbids commits without explicit approval. They agree only when the initial decision is explicitly implementation authority and has not been narrowed by `do not commit`.
8. **Direct-main authority is project-specific.** `executing-plans` requires specific same-checkout authority on `main`; this project's direct-work instruction supplies that default for bounded work. Other repositories without that instruction must not inherit this count.
9. **Conditional/partial approvals are not encoded safely.** `resolve_beads_approval_request()` accepts free-form answer text with an approved outcome and still writes generic target approval. Current callers must reject and re-issue any modified scope; successor validation must bind approval to exact structured effects before inheritance.

## Successor boundaries

- `pi-c65z.2`: encode exact reversible local create/commit/cleanup/deletion authority and recovery checks.
- `pi-c65z.3`: serialize shared-target integration and prove conflict/stale-holder behavior.
- `pi-c65z.4`: preserve zero-increment closeout-to-handoff for one unambiguous ready successor.
- `pi-c65z.5`: obtain exact human approval for revised ordinary-push policy, then align root/global/upstream sources and tests.
- `pi-c65z.6`: codify `pi-sjud` deployment classes, environment identity, preview, rollback, timeout/default, and stop conditions.
- `pi-c65z.7`: validate nominal **1** counts and every escalation path with deterministic tests/evals.

## Evidence index

- Authority and lifecycle: `AGENTS.md`, `pi/agent/AGENTS.md`, `docs/ORCHESTRATION-LOOP.md`, `docs/AGNT-SYSTEM.md`.
- Shared completion contract: `pi/agent/skills/dev-workflow-common/SKILL.md`.
- Direct and worktree workflows: `brainstorming`, `executing-plans`, `using-git-worktrees`, `subagent-driven-development`, and `finishing-a-development-branch` skills.
- Upstream workflow: `pi/agent/skills/preparing-upstream-pr/SKILL.md` and `references/pr-mechanics.md`.
- Deterministic work lifecycle: `pi/agent/bin/agnt_lib/work.py`, `worktree_policy.py`, `tests/test_agnt.py`, and `tests/test_bead_handoff.py`.
- Approval mechanism: `pi/agent/bin/agnt_lib/approvals.py`, `pi/agent/extensions/beads-ask-bridge.ts`, and `tests/test_approvals.py`.
- Deployment: `scripts/update-pi-config.sh`, `scripts/check-pi-config.sh`, `pi/README.md`, and resolved decision `pi-sjud`.
