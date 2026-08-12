---
name: subagent-driven-development
description: Use when implementation-plan tasks can be explored or executed independently with peers or isolated worktrees.
---

# Subagent-Driven Development

Pi uses Archimedes subagents for isolated peer execution with live TUI progress. The main session routes models with `agnt route`, calls `subagent` with `agent` omitted, composes optional role/model context with `agnt instructions`, and—when implementation is approved—assigns each writing peer an isolated git worktree.

Announce: "I'm using the subagent-driven-development skill to coordinate peer-driven parallel development."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Core rule

Never let multiple workers edit the same checkout in parallel. Read-only/advisory peers may share a checkout. Any peer that writes implementation code must use its own branch/worktree.

## Modes

### Mode A: Advisory peers — default

Use this by default for:

- plan review
- independent investigations
- debugging hypotheses
- patch proposals
- implementation strategy comparisons
- code review before the orchestrator edits

Peers are read-only unless the user explicitly approves write/worktree execution. Peer outputs go under `.pi/peer-runs/<topic>/`. The orchestrator verifies claims and applies any changes manually.

### Mode B: Worktree implementation — explicit approval required

Use this only when the user explicitly approves parallel implementation in isolated worktrees. An initial approved scope is sufficient when it names parallel mode plus each exact path, branch, base, worker/write set, and cleanup boundary.

Each implementation worker gets:

- role/model context when useful, generated with `agnt instructions --role implementation-worker --context provider/model`
- its own branch
- its own worktree under `.worktrees/`
- exact task text
- allowed files
- forbidden files
- verification commands
- commit/report requirements

The orchestrator reviews and integrates task branches one at a time.

## Safety gates

Before any write or dispatch that may write:

```bash
git status --short
git branch --show-current
git rev-parse --show-toplevel 2>/dev/null || pwd
git worktree list 2>/dev/null || true
```

Stop before implementation if:

- current branch is `main` or `master` and same-branch execution has not been explicitly approved
- working tree has unrelated uncommitted changes
- plan path is missing or ambiguous
- tasks write the same file
- tasks depend on each other but are requested in parallel
- tasks share mutable external resources
- verification commands are missing for implementation work
- the user requested implementation but did not approve worktrees

### Shared environment contract

Before any parallel run, explicitly check whether tasks share mutable resources outside git:

- databases or local service state
- `/tmp` files, sockets, ports, queues, caches, or logs
- credentials, cloud resources, external APIs, or rate-limited services
- generated artifacts outside the repository

If tasks share mutable external state, do not parallelize them unless each worker gets an isolated test environment or the user approves a specific coordination plan.

Do not push, merge, reset, clean, or commit in the orchestrator branch without explicit approval. Remove worktrees or delete local task branches without another approval only when the initial approved scope names exact cleanup and the shared completion contract proves ownership, clean tracked/untracked state, integration, and recovery SHA.

## Step 1: Load plan or problem statement

If a plan path is provided, read it completely. If no plan is provided, resolve the plan directory and list candidates:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
find "$PLANS_DIR" -maxdepth 1 -type f -name '*plan.md' | sort
```

Extract:

- tasks/domains
- dependencies
- target files
- verification commands
- specs or docs to inspect
- likely docs impact

If there is no written plan and the user asks for implementation, recommend `writing-plans` first unless the task is very small.

## Step 2: Build a task graph

Classify each task/domain:

- `advisory-ok` — safe for read-only peer investigation/proposal
- `worktree-implementation-ok` — can be implemented independently in a separate worktree
- `serial-only` — must be done by the orchestrator or via `executing-plans`
- `blocked` — missing context or unsafe

File overlap check:

```bash
# Use the plan's Files sections if present; otherwise inspect likely target paths with rg/find.
rg -n '^### Task|^- (Create|Modify|Test):|`[^`]+`' <plan-file>
```

If two implementation tasks modify the same path, mark them `serial-only`. Do not parallelize them even if the plan says independent.

## Step 3: Choose execution mode

Report the classification before dispatch:

```markdown
## Parallelization Review

**Mode:** Advisory peers | Worktree implementation | Serial recommended
**Plan/problem:** <path or summary>

### Task graph
| Task/domain | Classification | Files | Reason |
|---|---|---|---|

### Decision
- <mode and rationale>
```

If tasks are not safe to parallelize, stop with `STOPPED` and recommend `executing-plans` or a serial batch.

## Mode A workflow: advisory peers

1. Route the advisory task:
   ```bash
   agnt route --task research --risk medium --budget balanced
   ```
2. Write focused prompts with read-only constraints:
   - do not edit files
   - do not commit
   - provide exact file references
   - propose patches only as text if useful
3. Call `subagent` once with `agent` omitted and one task entry per independent domain:
   ```json
   {
     "tasks": [
       { "task": "<focused read-only prompt A>", "model": "<routed target A>", "cwd": "<repository>" },
       { "task": "<focused read-only prompt B>", "model": "<routed target B>", "cwd": "<repository>" }
     ]
   }
   ```
4. Persist returned outputs under `.pi/peer-runs/<topic>/` only when handoff needs files.
5. Verify concrete claims against files/tests.
6. Synthesize findings.

Advisory output format:

```markdown
ADVISORY_DISPATCH

**Peer outputs:** `.pi/peer-runs/<topic>/`

### Findings
- <verified finding/proposal>

### Discarded / unverified
- <claim> — discarded because <reason>

### Recommended next step
- <manual edit, plan update, worktree implementation, or serial execution>
```

## Mode B workflow: isolated worktree implementation

Only proceed if the user explicitly approved worktree implementation.

### 1. Prepare worktrees

For each independent task:

```bash
git worktree add -b parallel/<topic>/task-N .worktrees/<topic>-task-N HEAD
```

Do not create worktrees on a dirty or ambiguous base unless the user approves the exact base.

### 2. Dispatch implementation workers

Run one worker per worktree. Prefer conservative models until evals show stronger autonomy is safe.

Worker prompt construction:

1. Generate role/model context:
   ```bash
   agnt instructions --role implementation-worker --context provider/model
   ```
2. Append task-specific constraints:
   ```text
   Worktree: <absolute path>
   Branch: <branch>
   Task: <full task text>
   Allowed files:
   - <paths>
   Forbidden files:
   - any path not listed above unless you stop and ask
   Verification:
   - <commands>
   ```

Route implementation work, then dispatch one task per worktree in a single `subagent` call. Omit `agent`; include generated role context in each worker prompt.

```bash
agnt route --task implementation --risk high --budget quality
```

```json
{
  "tasks": [
    { "task": "<role context + worker prompt N>", "model": "<routed target N>", "cwd": ".worktrees/<topic>-task-N" },
    { "task": "<role context + worker prompt M>", "model": "<routed target M>", "cwd": ".worktrees/<topic>-task-M" }
  ]
}
```

Persist worker reports under `.pi/peer-runs/<topic>/` when integration needs durable evidence.

### 3. Review each task branch

Do spec compliance before quality review.

Spec review prompt construction:

```bash
agnt instructions --role spec-reviewer --context provider/model
```

Append task branch, requirement, diff, worker report, and known expected breakage paths.

Quality review prompt construction:

```bash
agnt instructions --role quality-reviewer --context provider/model
```

Append task branch, diff, test output, and artifact paths.

If either review finds real blockers, fix within that task worktree or stop for user guidance. Do not integrate failing branches.

### 4. Cleanup plan

Worktrees and branches remain durable unless the initial approved scope names their exact post-integration cleanup or later approval does. For preauthorized cleanup, show exact path, local branch, integrated recovery SHA, and full tracked/untracked status; confirm no active owner; then run without another approval:

```bash
git worktree remove .worktrees/<topic>-task-N
git branch -d parallel/<topic>/task-N
```

If cleanup is unsafe because of uncommitted or untracked work, ambiguous ownership, missing integration proof, or missing recovery evidence, stop and report path/status. Never force-remove worktrees or force-delete branches under this authority; force, remote deletion, backups/runtime data, and history rewrite require separate approval.

### 5. Integrate one branch at a time

Integration is an orchestrator action. Before each integration:

```bash
git status --short
git diff --stat <base>..parallel/<topic>/task-N
```

Use merge or cherry-pick only with explicit user approval if the workflow has not already approved integration. After each integration, run focused verification. After all integrations, run full verification and use `finishing-a-development-branch`.

## When to choose serial execution instead

Use `executing-plans` rather than this skill when:

- tasks touch the same files
- task dependencies are tight
- the implementation requires one coherent design thread
- there is no clear verification per task
- worktree setup would be more overhead than benefit

## Final statuses

End with exactly one status label:

- `STOPPED` — unsafe or not approved; no implementation dispatch occurred
- `ADVISORY_DISPATCH` — read-only/advisory peers ran or prompts were prepared
- `WORKTREE_DISPATCH_READY` — worktree implementation is planned but awaits approval
- `CHECKPOINT` — a batch/worker completed and awaits review or integration
- `BLOCKED` — execution started but cannot safely continue
- `COMPLETE` — all tasks integrated and acceptance criteria verified
