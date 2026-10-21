# Continuation friction implementation plan

**Issue:** pi-pvcg
**Design:** Approved keep/simplify/defer assessment in current session; narrows `.pi/plans/2026-10-20-resumable-work-global-delegation-design.md` and its original implementation plan.
**Date:** 2026-10-21
**Branch:** main (existing direct same-checkout work under project policy)

## Goal and boundary

Reduce interruptions, commands, repeated approvals and lost context in four journeys: partial resume, dirty A→B→A, pending-decision recovery, and reuse/revocation of valid authority. Keep implemented safeguards and separate exact experiment grants. Do not add a scheduler, generalized delivery command surface, provider adapters or another state manager. Preserve all existing work and both unrelated plans. No deletion, deployment, global authority activation, remote effects or live parent-session replacement is authorized by this plan.

Original broader deliverables remain deferred, not completed: push/PR/release/deployment adapters, universal native-effect receipts, dependency detours and expanded epic/worker orchestration. Existing concrete worktree receipt machinery remains because safe dirty switching uses it. Existing reproduced correctness fixes remain.

## Architecture

Keep `handoff_bead` as normal entry point. Pass concise curated progress directly through that tool into the existing checkpoint journal, using stdin rather than another scratch JSON file; capture scope from existing ownership, never from progress text. Beads remains canonical work/decision state, Pi session history stays immutable, quality records attempt history, and lifecycle owns transfer state. Normal assignment must express the actual approved work set without custom authority JSON; capture it before immutable execution ownership is bound and never infer scope from every ready Bead. Use existing authority/assignment checks, not a new intent-classification framework.

## Acceptance

- Partial resume saves current objective/decisions/completed work/next steps/blockers/verification/path references through one handoff call; no transcript copy, false success, authority override or lost dirty state.
- Recovered reservations cannot silently replace checkpoint content, child identity or target. Headless calls remain read-only.
- Normal assignment supports an explicit approved set of Beads and local isolation without JSON preparation or repeated enrollment prompts. Existing narrower scopes and revocation remain binding; unselected work is not enrolled.
- Dirty A→B→A retains checkouts, scope and outcomes. Pending decisions recover their original question and require fresh answers; applicable completed approvals retain exact target/effects.
- Tracked root/workflow instructions describe continuation consistently and favor coherent risk-sized batches, not ritual microtasks or mandatory pauses after every batch.
- Focused regressions, independent review, required full checks and a disposable actual process-replacement journey pass before completion. Distinguish real Pi TUI verification from SDK/intercepted-replacement tests. No live rollout claim.

## Ordered implementation

### 1. Useful checkpoint at existing handoff boundary
Files: `pi/agent/extensions/bead-handoff.ts`, `pi/agent/extensions/lib/work-continuation.ts`, `pi/agent/bin/agnt_lib/work_lifecycle.py`, continuation CLI/SDK tests and lifecycle SPEC.
Add red CLI and SDK cases for curated progress, immutable scope, reservation conflicts and headless behavior. Add typed progress to existing handoff tool; use bounded stdin input to existing checkpoint command and inject captured assignment in domain service. Preserve existing full checkpoint-file compatibility. Verify focused suites before next boundary.

### 2. Normal assignment and dirty switching
Files: `pi/agent/bin/agnt_lib/work.py`, `authority.py`, `work_lifecycle.py`, direct-start/authority/continuation/isolation tests and specs.
Express explicitly approved work scope in normal direct-start workflow, captured before claim/link. Reuse unambiguous existing assignment; never expand an existing narrower record or checkpoint scope. Include only local effects required by retained journeys, no external delivery permission. Add ordinary-command A→B→A and negative scope/revocation journeys. Stop if this requires a new general authorization subsystem.

### 3. Consistent instructions and journey acceptance
Files: tracked `pi/agent/AGENTS.md`, relevant repository-owned workflow skills and their small baseline scenarios, `pi/agent/bin/README.md`, `docs/AGNT-SYSTEM.md`, affected context tests.
Replace contradictory closeout-only handoff rules with one normal continuation path and concise progress expectations. Keep real approval, verification, ownership and destructive-operation gates. Read skills before editing. No broad skill rewrite. Review changed boundaries and current combined candidate, verify disposable native replacement, then run final gates and local atomic task-owned commit/closeout only if acceptance passes.

## Verification

Inherit prior full baseline: 1467 passed / 2 failed (discovery budget and crafting command-reference parser); later focused authority matrix 689 passed. Neither is final acceptance. Preserve signing isolation for disposable repos and owner signing policy for real commits.

```bash
.venv/bin/python -m pytest tests/test_work_continuation.py tests/test_continuation_extension.py tests/test_work_lifecycle.py tests/test_work_isolation.py -q
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

Canonical progress/evidence stays on pi-pvcg. This document specifies implementation, not a second task tracker. Existing checkpoint remains recovery context; new scope supersedes its old remaining-work list. Completion requires all narrowed acceptance, not original deferred packages.
