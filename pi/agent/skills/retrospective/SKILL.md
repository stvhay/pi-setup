---
name: retrospective
description: Use after a development branch is complete or nearly complete to capture what worked, what caused friction, and which project or skill improvements should be saved or filed.
---

# Retrospective

Run a brief evidence-based session retrospective. This is non-blocking and does not gate merge or cleanup.

Announce: "I'm running a brief retrospective on this session."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Core rules

- Retrospectives are opt-in unless the user explicitly requested one.
- Analyze first; ask the user to validate or correct conclusions.
- Separate project-local improvements from upstream skill/tool improvements.
- Do not edit instructions, create issues, push, merge, or remove worktrees without explicit approval.
- Cite concrete evidence: commits, diffs, plans, verification output, review findings, and observed friction.

## When to use

Use after:

- `finishing-a-development-branch`
- a PR is prepared or created
- a difficult implementation is complete
- repeated workflow friction occurred
- the user asks what should be improved next

If invoked automatically by another workflow, ask:

```text
Would you like a brief retrospective on this session? It should take about 2 minutes.
```

If the user declines, respond: "Skipping retrospective. Session complete."

## Step 1: Gather evidence

Inspect branch and commits:

```bash
git status --short
git branch --show-current
git log --oneline -10
base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || true)
if [ -n "$base" ]; then
  git diff --stat "$base"...HEAD
  git diff --name-only "$base"...HEAD
else
  git diff --stat
  git diff --name-only
fi
```

Inspect plans:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
find "$PLANS_DIR" -maxdepth 1 -type f \( -name '*-design.md' -o -name '*-plan.md' \) | sort
```

If a PR exists and GitHub is available:

```bash
gh pr view --json title,body,additions,deletions,state,url 2>/dev/null || true
```

Review available artifacts when relevant:

```bash
find .pi/reviews .pi/peer-runs .pi/research -maxdepth 2 -type f 2>/dev/null | sort | tail -50
```

## Step 2: Compare plan vs actual

For relevant plans/designs, check:

- acceptance criteria met or changed
- tasks completed, skipped, or added
- verification promised vs verification run
- docs/review steps completed or deferred
- deviations from original design and why

Do not claim a plan was followed unless the files and commits support it.

## Step 3: Identify friction and improvements

Classify findings:

### What went well

- workflows or skills that saved time
- checks that caught real issues
- good model/provider choices
- effective planning or review artifacts

### Friction points

- failed or slow commands
- unclear skill instructions
- model compliance issues
- missing docs or verification commands
- submodule/worktree confusion
- repeated manual steps that could be scripted

### Proposed improvements

Project-local candidates:

- `AGENTS.md` policy updates
- README/CONTRIBUTING verification updates
- scripts or helper commands
- docs/specs updates

Upstream/config candidates:

- Pi skill instruction changes
- helper command improvements under `~/.pi/agent/bin` or `pi/agent/bin`
- model/provider configuration adjustments
- eval cases for repeated failures

For reusable Pi configuration lessons that should be aggregated across projects,
optionally capture a redacted lesson:

```bash
agnt lessons capture --kind friction --area <area> --summary "<lesson>" --evidence "<redacted evidence>"
```

## Step 4: Present analysis

Use this format:

```markdown
## Session Retrospective

### What Went Well
- <evidence-backed item>

### Friction Points
- <issue> — evidence: <command/file/event>

### Proposed Improvements

**Project-local**
- <improvement> — <rationale>

**Pi config / skill improvements**
- <skill/helper/config>: <improvement> — <rationale>

**Upstream issue candidates**
- <repo or unknown>: <issue title> — <rationale>

### Questions
- <only questions needed to resolve uncertainty>
```

## Step 5: Ask for decisions

After the user has the analysis, batch decisions in normal chat:

1. Is the analysis accurate, or what should be corrected?
2. Which project-local improvements should I save, and where?
3. Which config/skill improvements should I implement now vs defer?
4. Should I create Beads follow-up items now, defer them to a plan, or draft optional GitHub adapter/export issues?

Do not file issues or edit files until approved.

## Step 6: Act only after approval

### Save project-local improvements

Possible targets:

- `AGENTS.md`
- `README.md`
- `CONTRIBUTING.md`
- `docs/`
- `.pi/plans/` follow-up plan

Run focused verification after edits.

### Draft Beads follow-up items

Draft before creating:

```markdown
Title: <skill/helper>: <concise improvement>

### Context
<What session/task exposed this.>

### Problem
<What went wrong or was inefficient.>

### Suggested Improvement
<Specific proposed change.>

### Evidence
<Commands, files, outputs, or review artifacts.>
```

Create Beads items only with approval for state mutation:

```bash
bd create "<title>" --type task --priority 2 --body-file <file>
```

If an external GitHub issue is still needed, draft it as an adapter/export artifact and file only with explicit approval:

```bash
gh issue create -R <owner/repo> --title "<title>" --body-file <file>
```

Labels are optional. If Beads/GitHub creation fails, report the failure and keep the draft.

## Step 7: Completion report

```markdown
## Retrospective Complete

### Saved
- <files changed or none>

### Filed / drafted
- <issues or drafts>

### Deferred
- <follow-up ideas>

### Verification
- `<command>` → PASS/FAIL/NOT_VERIFIED
```

## Integration

Called by or pairs with:

- `finishing-a-development-branch`
- `documentation-standards`
- `requesting-code-review`
- `verification-before-completion`

This skill does not invoke other skills automatically. It may recommend follow-up work.
