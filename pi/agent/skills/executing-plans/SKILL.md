---
name: executing-plans
description: Use to execute approved plans with evidence and checkpoints.
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
- execution checkout follows shared direct/isolation policy and any narrower user scope
- working tree checked; unrelated ownership and edit overlap understood
- relevant baseline established once or explicitly inherited, with failures classified
- first risk-sized batch and its verification selected
- stop conditions understood

Stop before edits if any item is unresolved.

## Branch and dirty-tree policy

Follow shared `AGENTS.md` direct-work default and narrower project/user constraints. A checkout explicitly reserved for orchestration must stay on its approved branch and baseline. Do not edit or switch that checkout without exact same-checkout authority.

Inspect path ownership and overlapping writes before choosing isolation. Unrelated untracked files alone do not require isolation; preserve known unrelated files without staging them. Ask only when ownership, overlap or authority is unresolved. Never stash, reset, clean, delete, move, or commit unrelated work without explicit approval. Approved task plans are not blockers.

Load `using-git-worktrees` when isolation is needed and authorized. A branch switch or shell `cd` is not a Pi session transition; validate host checkout/header/ownership before implementation there. Read-only peers need no implementation ownership.

Prune only after integration is verified. When initial approved scope names the exact path/branch cleanup, show clean tracked/untracked status and recovery SHA, then remove with non-force Git commands without another approval; otherwise leave the worktree intact.

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
- **Stable candidate boundary:** after focused checks pass, refresh stale focused evidence, stage every task-owned path state, inspect cached and untracked scope, and run diff/format checks.
- **Final candidate gate:** only after the stable candidate boundary passes, run every required full release command once; rerun only when the candidate changes.

An unchanged baseline failure is not a task regression, but it cannot turn a red required release gate into PASS.

## Execute risk-sized batches

Execute coherent, verifiable batches within approved scope. Shared files call for serialized edits, not automatically smaller user-visible tasks. Continue through routine phase boundaries without reconfirmation; pause for the stop conditions below. Keep all safety and verification gates.

Before each batch:

```bash
pwd
git branch --show-current
git status --short
find . \( -name SPEC.md -o -name '*.SPEC.md' \) -print | sort
```

Consult `docs/specs/MANIFEST.md` when present, then read relevant sibling `<module>.SPEC.md` and governing directory/root `SPEC.md` files.

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
- remote operation or destructive action outside exact preauthorized reversible-local scope

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

Report progress without a routine approval pause while approved work remains clear. If context is exhausted or assigned work must switch, use `handoff_bead` with current concise `progress` and exact artifact references. Leave unfinished Beads open and outcomes unchanged; preserve dirty work. Existing reservations recover their original checkpoint instead of accepting replacement progress. Resolve real blockers or uncertain effects before advancing; `/new` is not an ownership override.

## Acceptance verification

After all tasks:

1. Re-read plan acceptance criteria.
2. Confirm focused repair evidence for every changed behavior.
3. Apply `verification-before-completion`'s stable candidate boundary: stage all task-owned path states, inspect cached and untracked scope, and run diff/format checks.
4. Run the complete final candidate gate once.
5. Compare any failure to the recorded baseline command, test identity, and signature.
6. Check documentation impact.
7. Recheck status and cached diff; any candidate change invalidates the gate.
8. Mark each criterion PASS, FAIL, or NOT_VERIFIED with evidence.

No completion claim without fresh evidence.

## Git boundary

Plan execution authority alone grants no Git mutation. Initial approved scope may include the task-owned commit plus exact local branch/worktree creation and post-integration cleanup defined by the shared completion contract. Run that cleanup without another approval only after ownership, exact path/branch, clean tracked/untracked state, integration, and recovery checks pass. Push, PR creation, merge, remote deletion, force/reset/clean, and history rewrite remain separately gated.

## Final states

End execution with exactly one state:

- `STOPPED` — no implementation; include reason/options
- `CHECKPOINT` — batch verified; remaining work awaits feedback
- `BLOCKED` — attempted but cannot safely proceed
- `COMPLETE` — every acceptance criterion has fresh passing evidence

After verified completion, recommend `finishing-a-development-branch` unless the user already requested finishing workflow.
