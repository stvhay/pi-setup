---
name: executing-plans
description: Use when you have a written implementation plan to execute with batch checkpoints, verification evidence, and safe branch gates.
---

# Executing Plans

Implement a filesystem plan as a controlled workflow. Use this for execution, not design discovery.

Announce: "I'm using the executing-plans skill to implement this plan."

Read shared conventions when needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Pre-edit gate

Confirm all before editing:

- plan path resolved and read from project filesystem
- current branch and repository root checked
- execution checkout established: a non-main branch/worktree or explicit same-checkout authority for `main`/`master`
- working tree checked; unrelated changes understood through human decision
- relevant baseline established once or explicitly inherited, with failures classified
- first risk-sized batch and its verification selected
- stop conditions understood

Stop before edits if any item is unresolved.

## Branch and dirty-tree policy

When starting from `main` or `master`:

1. Treat the current checkout as the orchestration checkout.
2. Never switch the orchestration checkout to a feature branch or write implementation files there unless same-checkout execution is explicitly authorized.
3. Require authority that specifically permits editing the shared checkout; generic implementation or commit authority is not same-checkout authority.
4. Load `using-git-worktrees` when isolated local implementation is authorized; create a separate feature branch/worktree and run every edit and verification command there.
5. Recheck that the orchestration checkout remains on `main`/`master` and clean at each checkpoint.

A branch switch in the same checkout is not isolation because untracked and ignored filesystem state stays shared. If neither a safe execution worktree nor explicit same-checkout authority is available, stop before edits.

Same-checkout execution remains allowed when project instructions or the current user specifically authorize it. Record that authority; it does not authorize remote, destructive, or unrelated-work operations. Prune the worktree only after integration is verified and applicable cleanup authority explicitly permits removal; otherwise leave it intact.

When unrelated changes exist:

1. Identify exact paths and likely ownership.
2. Ask how to handle them.
3. Continue only after the user authorizes leaving them untouched or provides another safe resolution.
4. Never stash, reset, clean, delete, move, or commit them without explicit approval.

Approved plan files or clearly related in-progress changes are not blockers; note them.

## Load and review plan

Resolve plan directory with:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
printf 'Plans dir: %s\n' "$PLANS_DIR"
find "$PLANS_DIR" -maxdepth 1 -type f -name '*plan.md' | sort
```

Read the chosen plan completely. Extract:

- goal and acceptance criteria
- tasks and dependencies
- files touched by each task
- exact verification commands
- documentation impact

Inspect relevant files and nearest `SPEC.md`. Stop if observed code conflicts with the plan, required context is missing, or execution would require an unapproved risky action.

## Verification phases

- **Baseline once:** establish or inherit one relevant work-item/worktree matrix before edits; record exact failures.
- **Focused repair:** use the smallest runnable proof during implementation and after fixes. Do not repeat an unchanged broad baseline.
- **Final candidate gate:** after all plan tasks stabilize, run every required full release command once; rerun only when the tracked candidate changes.

An unchanged baseline failure is not a task regression, but it cannot turn a red required release gate into PASS.

## Execute risk-sized batches

Default to one task when work is risky, ambiguous, or shares files. Group tasks only when they are clear, independent, and separately verifiable. Continuous execution is allowed when the user requested it, but all stop conditions remain active.

Before each batch:

```bash
pwd
git branch --show-current
git status --short
find .. -name SPEC.md -print 2>/dev/null | sort
```

For each task:

1. Read current target files and applicable specs.
2. Write a failing test first for behavior changes.
3. Make the smallest coherent change.
4. Run focused verification and inspect output.
5. Record command and result.
6. Recheck scope before the next batch.

Do not skip verification because a change appears obvious.

## Stop conditions

Stop immediately on:

- new or unclassified failed verification
- failed focused repair proof
- missing dependency
- plan/spec/code conflict
- unclear requirement
- unexpected dirty-tree change
- broader design requirement
- destructive or remote operation without explicit approval

Report exact task, command/evidence, and safe options. Do not guess around the blocker.

## Checkpoints

After each risk-sized batch, report:

```markdown
## Execution Checkpoint

**Plan:** `<path>`
**Completed:** <task>
**Remaining:** <tasks>
**Changes:** <paths and short summaries>
**Verification:** `<command>` → PASS/FAIL with evidence
**Issues/deviations:** <none or details>
```

Pause for feedback unless the original request approved continuous execution and remaining work stays low-risk and clear.

## Acceptance verification

After all tasks:

1. Re-read plan acceptance criteria.
2. Confirm focused repair evidence for every changed behavior.
3. Run the complete final candidate gate once.
4. Compare any failure to the recorded baseline command, test identity, and signature.
5. Check documentation impact.
6. Run `git diff --check`, `git diff --stat`, and `git status --short`.
7. Mark each criterion PASS, FAIL, or NOT_VERIFIED with evidence.

No completion claim without fresh evidence.

## Git boundary

Do not push, create a PR, merge, delete branches, remove worktrees, reset, clean, rewrite history, or commit unless explicitly approved. Plan execution authority alone does not grant those actions.

## Final states

End execution with exactly one state:

- `STOPPED` — no implementation; include reason/options
- `CHECKPOINT` — batch verified; remaining work awaits feedback
- `BLOCKED` — attempted but cannot safely proceed
- `COMPLETE` — every acceptance criterion has fresh passing evidence

After verified completion, recommend `finishing-a-development-branch` unless the user already requested finishing workflow.
