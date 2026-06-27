---
name: finishing-a-development-branch
description: Use when implementation is complete and you need branch/project readiness checks, PR preparation, or merge/cleanup guidance. Verifies, validates docs, reviews, summarizes, and stops at risky actions unless explicitly approved.
---

# Finishing a Development Branch

Finish development work safely. This skill is a readiness/checklist workflow, not an autopilot merge button.

Announce: "I'm using the finishing-a-development-branch skill to check branch readiness."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Safety gates

Do not push, create a PR, merge, delete branches, remove worktrees, force-clean files, or create persistent artifacts unless the user explicitly asks/approves that action in the current conversation.

Default behavior: verify, validate, optionally review, prepare a PR body, and present next-step commands/options. If the user says not to edit/create files, do not create `.pi/reviews`, `.pi/pr-body.md`, or other artifacts; keep outputs in the response or use temporary files under `/tmp` only when necessary.

## Workflow

1. **Inspect branch/project state**
2. **Run verification**
3. **Validate documentation**
4. **Request code review**
5. **Check scope and generated artifacts**
6. **Prepare PR/merge or local project summary**
7. **Ask for approval before any remote/destructive action**

Use local project-readiness mode when the project uses local Beads/issues plus atomic commits and no PR/remote workflow. In that mode, verify the tracked task is complete, summarize commits and evidence, and present safe next actions instead of forcing PR language.

## Step 1: Inspect branch state

Use shell tools:

```bash
git status --short
git branch --show-current
git remote -v
git log --oneline -10
```

Find base branch:

```bash
base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || true)
if [ -n "$base" ]; then
  git diff --stat "$base"...HEAD
  git diff --name-only "$base"...HEAD
else
  git diff --stat
  git diff --name-only
fi
```

If working tree has uncommitted changes, include them in the readiness report. Do not hide them.

## Step 2: Run verification

Use `verification-before-completion` or follow its gate directly.

Find project-specific verification first:

```bash
rg -n "test|lint|typecheck|quality|verify|ci" README.md CONTRIBUTING.md docs package.json pyproject.toml Makefile .github 2>/dev/null || true
```

Run the relevant command(s). If no command is discoverable, report `NOT_VERIFIED` and ask for the command.

Do not proceed to PR-ready status if verification fails.

## Step 3: Validate documentation

Use `documentation-standards` in validate mode for documentation-impacting changes. If uncertain whether docs are impacted, report `NOT_SURE` rather than PASS. Public API/user-visible changes usually require docs unless the project has no user-facing docs or the user explicitly says documentation is unnecessary.

Documentation status can be:

- `PASS` — docs are current or no docs are needed, with reason
- `NEEDS_DOCS` — block PR-ready status unless user explicitly defers with reason
- `NOT_SURE` — ask user or inspect more

If deferred, record:

```markdown
**Documentation deferred:** <reason>
```

## Step 4: Request code review

Use `requesting-code-review` for non-trivial diffs unless the user requested no file creation/artifacts. Prefer local model diversity:

- small diffs: `ollama/gemma4:31b` + `olla-local/qwen3:8b` or `olla-local/gemma4:e4b`
- riskier diffs: add `olla-local/deepseek-r1:14b` or `olla-cloud/gpt-4.1-mini`

If artifact creation is not allowed, either skip peer review with a note or run only direct peer calls whose outputs are summarized in the response without writing `.pi/reviews`.

Review status can be:

- `PASS` — continue
- `NEEDS_WORK` — block PR-ready status until addressed or explicitly deferred
- `NOT_SURE` — inspect/ask

Verify serious review findings against the code before treating them as blockers.

## Step 5: Scope and artifact check

Check scope coherence:

```bash
git diff --stat
git status --short
find . -name '__pycache__' -o -name '*.pyc' -o -name '.DS_Store' -o -name '*.log'
```

Flag:

- unrelated file changes
- generated artifacts
- untracked files that should be ignored or removed
- large diffs outside the stated task

Do not delete artifacts unless the user approves, but recommend cleanup commands when appropriate.

## Step 6: Prepare PR / project summary

Look for plan/design artifacts:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
find "$PLANS_DIR" -maxdepth 1 -type f \( -name '*-design.md' -o -name '*-plan.md' \) | sort
```

Prepare this summary. For local-only Beads/project workflows, title it `Project Readiness Report`, replace PR/base fields with task IDs and commits, and omit remote-only next actions.

```markdown
## Branch Readiness Report

**Branch:** <branch>
**Base:** <base or unknown>
**Verdict:** READY | NOT_READY | NOT_VERIFIED

### Verification
- `<command>` → PASS/FAIL/NOT_VERIFIED

### Documentation
- PASS / NEEDS_DOCS / NOT_SURE

### Review
- PASS / NEEDS_WORK / NOT_SURE / skipped because <reason>

### Scope / artifacts
- <findings>

### Suggested PR body

## Summary
- <what changed>

## Test Plan
- [x] `<verification command>`

## Documentation
- <doc status or deferral reason>

## Review
- <review status>

Closes #<issue>  <!-- only if known -->

### Next actions
1. <safe next command or option>
2. <ask user approval for push/PR/merge if desired>
```

## Optional actions after approval

Only after explicit user approval:

### Push branch

```bash
git push -u origin "$(git branch --show-current)"
```

### Create PR

```bash
gh pr create --title "<title>" --body-file .pi/pr-body.md
```

### Check PR CI

```bash
gh pr checks --watch --fail-fast
```

### Merge PR

Only merge after CI passes and user explicitly asks:

```bash
gh pr merge --squash
```

Be worktree-aware before deleting branches/worktrees. Prefer presenting cleanup commands instead of running them automatically.

## Rules

- Evidence before readiness claims.
- No remote/destructive actions without approval.
- Local review and documentation validation are first-class readiness checks.
- Keep PR bodies concise; link to `.pi/plans` artifacts by path when local, paste only if the user asks.
- If anything is uncertain, report `NOT_VERIFIED` or `NOT_SURE` instead of pretending.
