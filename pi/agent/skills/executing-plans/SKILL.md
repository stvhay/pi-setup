---
name: executing-plans
description: Use when you have a written implementation plan to execute with batch checkpoints, verification evidence, and safe branch gates.
---

# Executing Plans

Implement an existing plan as a controlled workflow. This skill is for execution, not design discovery.

Announce: "I'm using the executing-plans skill to implement this plan."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Safety protocol checklist

Before any edit, explicitly confirm in the response or working notes:

- [ ] Plan path resolved and read from the project filesystem.
- [ ] Current branch checked; either not `main`/`master`, or project instructions/current user explicitly authorize same-branch execution and that authorization is documented.
- [ ] Working tree checked; unrelated changes are understood or execution is stopped.
- [ ] First batch selected and limited to clear, verifiable task(s).
- [ ] Verification command(s) identified before implementation.
- [ ] Stop conditions understood: unclear plan, failed verification, unsafe git/file operation, missing dependency, or spec conflict.

If any item cannot be checked, stop before editing and report `STOPPED` or `BLOCKED`.

## Core principles

- Load the plan from the filesystem and review it before editing.
- Execute risk-based batches: one task for unclear/risky work; grouped batches for clear independent low-risk tasks.
- Verify every completed task with fresh shell evidence.
- Stop at checkpoints based on risk and user intent; continuous execution is allowed only when explicitly requested and safe.
- Stop rather than guessing when the plan, branch state, dependencies, or verification are unclear.

## Inputs

Accept any of these plan references:

- Explicit path: `./.pi/plans/2026-05-30-feature-plan.md`
- Plan topic/name: search the project plans directory
- No path: list candidate plans and ask the user to choose

Resolve project plan directory with:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
printf 'Plans dir: %s\n' "$PLANS_DIR"
find "$PLANS_DIR" -maxdepth 1 -type f -name '*plan.md' | sort
```

Do not use `~/.pi/plans` as the project plan directory.

## Pre-flight safety gate

Before editing files, run:

```bash
git status --short
git branch --show-current
git rev-parse --show-toplevel 2>/dev/null || pwd
```

### Branch gate

Default rule: prefer not to execute implementation plans on `main` or `master`.

Same-branch execution is allowed only when one of these is true:

- project instructions explicitly authorize routine local same-branch work; or
- the current user explicitly approves same-branch execution in this conversation.

If current branch is `main` or `master` and neither condition is true:

1. Stop before editing.
2. Report the branch and working tree state.
3. Recommend creating a feature branch or worktree.
4. Ask for explicit approval or branch/worktree instructions.

Example stop wording:

```markdown
STOPPED: current branch is `main`. I will not execute implementation steps on main without project/user same-branch authorization.

Options:
1. Create/switch to a feature branch or worktree.
2. Reply `approve executing on main` if this is intentional.
```

If project instructions or the user authorize same-branch execution, record the authorization in the execution report and proceed only if the dirty-tree and safety gates are clean. Same-branch authorization does not authorize unrelated dirty-work handling, destructive file/git operations, remote actions, pushing, merging, resetting, cleaning, or rewriting history.

### Dirty tree gate

If the working tree has unrelated uncommitted changes:

- Stop and ask how to handle them.
- Do not stash, discard, reset, or commit without explicit approval.

If changes are clearly the plan itself or approved in-progress work, note them and continue.

## Step 1: Load and review the plan

1. Read the plan file completely.
2. Extract:
   - goal
   - acceptance criteria
   - verification commands
   - task list and dependencies
   - files each task will touch
3. Check for missing context:
   - ambiguous steps
   - missing tests/verification
   - conflicts between tasks
   - unsafe operations
   - likely docs impact
4. Inspect relevant files with `rg`, `find`, `git diff`, and `read` before editing.
5. If concerns are significant, stop and report them before implementation.

Report format before implementation:

```markdown
## Plan Review

**Plan:** `<path>`
**Branch:** `<branch>`
**Batch:** Task N OR Tasks N-M

### Acceptance criteria
- <criterion>

### Concerns / assumptions
- <concern or `None`>

Proceeding with: <task names>
```

## Step 2: Execute one batch

Default batch size is one task for large/risky, ambiguous, or shared-file work.

Use a larger batch when all tasks are independent, touch different files, have clear verification, and the user approved continuous execution or the plan explicitly groups them.

For each task:

1. Re-check current directory and branch:
   ```bash
   pwd
   git branch --show-current
   git status --short
   ```
2. Load nearest `SPEC.md` if one exists for target files:
   ```bash
   find .. -name SPEC.md -print 2>/dev/null | sort
   ```
   Review invariants and public interface sections before editing. If specs conflict with the plan or are unclear, stop and report the conflict before editing.
3. Follow the task steps in order.
4. Prefer tests first when behavior changes.
5. Make the smallest coherent edit.
6. Run the focused verification command from the plan.
7. Capture exact command and pass/fail result.

Do not skip verification because a change looks obvious.

## Step 3: Checkpoint report

After each risk-based batch, report progress. Stop for feedback unless the user explicitly asked for continuous execution and the remaining tasks are still low-risk, clear, and independently verifiable.

```markdown
## Execution Checkpoint

**Plan:** `<path>`
**Completed:** Task N — <name>
**Remaining:** <count/list>

### Changes made
- `path` — <summary>

### Verification
- `<command>` → PASS/FAIL
  - Evidence: <short output or relevant line>

### Issues / deviations
- <none or details>

Ready for feedback. Reply `continue` to execute the next batch.
```

If the plan is linked to a GitHub issue and the user approved GitHub updates, you may comment with progress:

```bash
gh issue comment <N> --body "Progress: completed Task N/M for <plan>. Verification: PASS."
```

Do not require GitHub. Do not post to GitHub without explicit approval.

## Step 4: Continue or stop

Continue only when:

- user says to continue, or
- the original request explicitly approved continuous execution through the full plan.

For continuous execution, still pause on any failed command, unexpected diff, spec conflict, increased risk, or task that takes substantially longer than expected.

Stop immediately when:

- verification fails
- dependencies are missing
- the plan conflicts with observed code
- instructions are unclear
- implementation requires destructive git/file operations or remote actions
- broader design changes are needed

When blocked, report:

```markdown
## Blocked

**Where:** Task N — <name>
**Reason:** <specific blocker>
**Evidence:** `<command>` → <output/failure>
**Options:**
1. <safe option>
2. <safe option>
```

## Step 5: Verify acceptance criteria

After all tasks complete:

1. Re-read acceptance criteria from the plan header.
2. Run the plan's verification commands.
3. Check docs impact if user-visible behavior changed.
4. Summarize each criterion as PASS/FAIL/NOT_VERIFIED.

```markdown
## Acceptance Criteria Verification

- [x] <criterion> — PASS via `<command>`
- [ ] <criterion> — FAIL/NOT_VERIFIED because <reason>
```

Do not claim completion unless each acceptance criterion has fresh evidence.

## Step 6: Handoff to finishing

When all acceptance criteria pass, use or recommend `finishing-a-development-branch` for readiness checks.

If the user asked you to continue into finishing, invoke that workflow. Otherwise report:

```markdown
Implementation complete with acceptance criteria verified. Recommended next skill: `/skill:finishing-a-development-branch`.
```

Do not push, create a PR, merge, delete branches, remove worktrees, reset, clean, or commit unless explicitly approved.

## Integration

Related skills:

- `writing-plans` — creates executable plans under `.pi/plans/`
- `test-driven-development` — use for behavior-changing tasks
- `verification-before-completion` — use before any completion claim
- `documentation-standards` — use when public behavior, APIs, architecture, or workflows change
- `requesting-code-review` — use for non-trivial diffs
- `finishing-a-development-branch` — use after implementation and acceptance criteria pass

## Final response format

For any execution attempt, end with one of:

- `STOPPED` — no implementation performed; include reason and options
- `CHECKPOINT` — batch completed; include verification evidence and ask to continue
- `BLOCKED` — attempted but cannot proceed; include evidence and options
- `COMPLETE` — all tasks and acceptance criteria verified with evidence
