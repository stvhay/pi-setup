---
name: subagent-driven-development
description: Use when executing or exploring implementation plans with independent tasks using Pi peers, advisory fan-out, and isolated per-task worktrees for true parallel implementation.
---

# Subagent-Driven Development

Pi does not have Claude Code Task subagents. In Pi, this workflow means **peer-driven development**: the main session orchestrates independent work using `agnt invoke`/`agnt invoke --fanout`, filesystem artifacts, optional `agnt instructions` role/model context, and—when implementation is approved—isolated git worktrees.

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

Use this only when the user explicitly approves parallel implementation in isolated worktrees.

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

Do not push, merge, reset, clean, remove worktrees, delete branches, or commit in the orchestrator branch without explicit approval.

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

1. Create a peer run directory:
   ```bash
   mkdir -p .pi/peer-runs/<topic>
   ```
2. Write focused prompts or use `agnt invoke --fanout` directly.
3. Include read-only constraints:
   - do not edit files
   - do not commit
   - provide exact file references
   - propose patches only as text if useful
4. Run peers:
   ```bash
   ~/.pi/agent/bin/agnt invoke olla-local/qwen3:8b "<prompt>" > .pi/peer-runs/<topic>/qwen-task-1.md
   ~/.pi/agent/bin/agnt invoke olla-local/gemma4:e4b "<prompt>" > .pi/peer-runs/<topic>/gemma-task-2.md
   ```
   Or:
   ```bash
   printf '%s\n' "<prompt>" > .pi/peer-runs/<topic>/prompt.md
   ~/.pi/agent/bin/agnt invoke --fanout -o .pi/peer-runs/<topic> olla-cloud/gpt-4.1-mini .pi/peer-runs/<topic>/prompt.md
   ```
5. Read outputs.
6. Verify concrete claims against files/tests.
7. Synthesize findings.

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

Example dispatch:

```bash
(
  cd .worktrees/<topic>-task-N
  ~/.pi/agent/bin/agnt invoke openai-codex/gpt-5.6-luna "<worker prompt>"
) > .pi/peer-runs/<topic>/task-N-worker.md
```

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

Worktrees and branches are durable until the user approves cleanup. When a task branch is integrated or abandoned, propose exact cleanup commands but do not run them without approval:

```bash
git worktree remove .worktrees/<topic>-task-N
git branch -d parallel/<topic>/task-N
```

If cleanup is unsafe because of uncommitted work, stop and report the path and status. Do not force-remove worktrees or force-delete branches unless the user explicitly approves the exact destructive command.

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
