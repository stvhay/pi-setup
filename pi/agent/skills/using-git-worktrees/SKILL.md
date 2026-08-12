---
name: using-git-worktrees
description: Use when feature work or parallel implementation needs isolation in a separate Git worktree.
---

# Using Git Worktrees

Set up isolated git workspaces safely. Worktrees let multiple branches share one repository while keeping file edits separate.

Announce: "I'm using the using-git-worktrees skill to set up an isolated workspace."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Core rules

- Do not create worktrees from a dirty or ambiguous base unless the user approves the exact base.
- An initial approved scope may name the exact base, branch, path, and task ownership for reversible local creation. When it does, create that worktree without another approval after deterministic checks pass.
- That same initial approved scope may cover post-integration removal without another approval only for the exact path and local branch after capturing the recovery SHA, proving integration, confirming no active owner, and finding no tracked or untracked changes.
- Push, merge, remote-ref mutation/deletion, force/reset/clean, and history rewrite remain separately gated. Unknown ownership, runtime data, backups, or failed checks stop cleanup.
- Prefer project-local `.worktrees/` and ensure it is ignored by git.
- Use worktrees for implementation isolation; read-only advisory peers do not require a separate worktree.

## Step 1: Inspect repository state

```bash
git status --short
git branch --show-current
git rev-parse --show-toplevel
git worktree list 2>/dev/null || true
```

If the working tree has unrelated uncommitted changes, stop and ask how to proceed.

## Step 2: Choose worktree directory

Priority order:

1. Exact path named by approved scope
2. Existing `.worktrees/`
3. Existing `worktrees/`
4. Project instruction preference in `AGENTS.md`
5. Ask the user

Inspection commands:

```bash
ls -d .worktrees 2>/dev/null || true
ls -d worktrees 2>/dev/null || true
rg -n "worktree|worktrees" AGENTS.md README.md docs 2>/dev/null || true
```

If no preference exists, recommend `.worktrees/`.

## Step 3: Verify ignore policy

For project-local directories, verify the directory is ignored before adding worktrees:

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

If the chosen directory is not ignored:

1. Add it to `.gitignore` only when that path is inside approved write scope; otherwise stop and ask.
2. Show the diff.
3. Commit under the implementation approval's task-owned atomic-commit authority.
4. Proceed after the ignore rule is in place.

Global directories outside the project do not need project `.gitignore` coverage.

## Step 4: Name branch and path

Branch names should be descriptive and safe for git:

```text
<type>/<slug>
<type>/<issue>-<slug>   # when a GitHub issue exists
```

Allowed types:

- `feature`
- `fix`
- `docs`
- `chore`
- `refactor`
- `test`

Examples:

```text
feature/worktree-safety
docs/42-update-readme
fix/submodule-pointer
```

For `.worktrees/`, mirror the branch path:

```text
.worktrees/<type>/<slug>
.worktrees/<type>/<issue>-<slug>
```

## Step 5: Choose base branch

Prefer the repository default branch, not the current feature branch, when starting unrelated work.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}
```

If no remote exists, use a local base explicitly:

```bash
git show-ref --verify --quiet refs/heads/main && DEFAULT_BRANCH=main || DEFAULT_BRANCH=master
```

For work that must branch from current `HEAD`, require that exact base in the initial approved scope or ask before creation.

## Step 6: Create the worktree

Existing remote-tracking default branch:

```bash
git show-ref --verify --quiet "refs/remotes/origin/$DEFAULT_BRANCH"
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "origin/$DEFAULT_BRANCH"
```

Do not fetch or otherwise mutate remote-tracking refs unless separately authorized; use the already-inspected exact base from approved scope.

Local-only default branch:

```bash
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "$DEFAULT_BRANCH"
```

Then verify location:

```bash
cd "$WORKTREE_PATH"
pwd
git branch --show-current
git status --short
```

## Step 7: Isolate environment setup

Before dependency setup, avoid inheriting parent checkout state:

```bash
unset VIRTUAL_ENV
export UV_LINK_MODE=copy
```

Run only project-appropriate setup commands. Detect before running:

```bash
[ -f package.json ] && npm install
[ -f Cargo.toml ] && cargo build
[ -f requirements.txt ] && pip install -r requirements.txt
[ -f pyproject.toml ] && command -v uv >/dev/null && uv sync
[ -f go.mod ] && go mod download
```

Do not install dependencies if the user asked for no setup or if the command is expensive/risky without approval.

## Step 8: Verify baseline

### Baseline once

Run the documented relevant matrix once in the new worktree and record exact command, test identity, and failure signature. Do not repeat the same broad baseline during implementation.

Use documented project commands first:

```bash
rg -n "test|lint|typecheck|verify|ci" README.md CONTRIBUTING.md AGENTS.md docs package.json pyproject.toml Makefile .github 2>/dev/null || true
```

Run the relevant baseline verification. If none is documented, report `NOT_VERIFIED` rather than inventing one.

If baseline verification fails, stop and report:

- command
- exit status
- key failure output and signature
- whether the failure appears pre-existing
- options: investigate, proceed under an already-approved exception, or remove the worktree

A new or unclassified failure blocks edits. An unchanged baseline failure may proceed only under explicit plan/user authority and never makes a required final gate pass. Do not remove the worktree unless the initial approved scope covers exact cleanup or later approval does.

### Focused repair

During implementation, run focused tests for changed behavior and repaired findings. Do not rerun the complete baseline merely to rediscover a recorded failure.

### Final candidate gate

At closeout, run every required complete release command once after tracked changes stabilize. Any tracked candidate change invalidates that gate and requires a new complete run.

## Step 9: Preauthorized cleanup

After verified integration, use the shared completion contract's deletion preview. Recheck exact path/branch, task ownership, active-owner state, full status with untracked files, integration ancestry, and recovery SHA. Then use only non-force `git worktree remove` and `git branch -d`. Run without another approval only when initial approved scope names this cleanup; any mismatch or refusal stops.

## Report format

```markdown
## Worktree Ready

**Path:** `<path>`
**Branch:** `<branch>`
**Base:** `<base>`
**Directory ignored:** yes/no

### Setup
- `<command>` → PASS/SKIPPED/FAIL

### Baseline verification
- Baseline once: `<command>` → PASS/FAIL/NOT_VERIFIED
- Focused repair plan: `<commands or NOT_VERIFIED>`
- Final candidate gate: `<commands reserved for stable candidate>`
- Unchanged baseline failures: `<none or exact signatures>`

### Next step
- <implementation plan, peer dispatch, or user decision needed>
```

## Integration

Pairs with:

- `executing-plans` — execute a written plan in an isolated checkout
- `subagent-driven-development` — create one worktree per independent implementation task
- `finishing-a-development-branch` — verify, summarize, and gate cleanup/merge actions

## Common mistakes

- Creating worktrees inside a tracked directory.
- Branching unrelated work from a feature branch by accident.
- Skipping baseline verification.
- Repeating the full baseline after every focused repair.
- Removing a worktree another session may be using.
- Forgetting that submodules are separate repositories; create worktrees from the correct repository root.
