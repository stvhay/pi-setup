---
name: using-git-worktrees
description: Use when starting feature work that needs isolation from the current checkout, before executing implementation plans on a feature branch, or when preparing isolated worktrees for peer/worktree-driven implementation.
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
- Do not remove worktrees, delete branches, push, merge, reset, clean, or rewrite history without explicit approval.
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

1. Existing `.worktrees/`
2. Existing `worktrees/`
3. Project instruction preference in `AGENTS.md`
4. Ask the user

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

1. Add it to `.gitignore`.
2. Show the diff.
3. Commit only if implementation approval includes committing, or ask for approval.
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

For work that must branch from current `HEAD`, state that assumption and ask for approval if it is not obvious.

## Step 6: Create the worktree

Remote-backed default branch:

```bash
git fetch origin "$DEFAULT_BRANCH" --quiet
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "origin/$DEFAULT_BRANCH"
```

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

Use documented project commands first:

```bash
rg -n "test|lint|typecheck|verify|ci" README.md CONTRIBUTING.md AGENTS.md docs package.json pyproject.toml Makefile .github 2>/dev/null || true
```

Run the relevant baseline verification. If none is documented, report `NOT_VERIFIED` rather than inventing one.

If baseline verification fails, stop and report:

- command
- exit status
- key failure output
- whether the failure appears pre-existing
- options: investigate, proceed anyway, or remove the worktree

Do not remove the worktree without approval.

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
- `<command>` → PASS/FAIL/NOT_VERIFIED

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
- Removing a worktree another session may be using.
- Forgetting that submodules are separate repositories; create worktrees from the correct repository root.
