---
name: retrospective
description: Use for assigned/requested retrospectives; not automatic closeout.
---

# Retrospective

Run a brief evidence-based session retrospective. This is non-blocking and does not gate merge or cleanup.

Announce: "I'm running a brief retrospective on this session."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Invocation and ownership

Invoke only from a `work-learning` activity assignment or explicit direct invocation. Branch, session, PR, or Bead completion alone is not a trigger. Control plan owns trigger timing and receiver selection.

- Use assignment scope and EvidenceRefs. For direct invocation, declare the bounded branch or session scope first.
- Analyze first; ask the user to validate or correct conclusions.
- Separate project-local improvements from upstream skill/tool improvements.
- Do not edit instructions, create issues, push, merge, or remove worktrees without explicit approval.
- Do not schedule another review or maintain a finding/work registry.
- Cite concrete evidence: commits, diffs, plans, verification output, review findings, and observed friction.

## Step 1: Gather evidence

Read only evidence named by the activity assignment. For direct invocation, inspect the current branch range:

```bash
git status --short
git branch --show-current
base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || true)
if [ -n "$base" ]; then
  git log --oneline "$base"..HEAD
  git diff --stat "$base"...HEAD
  git diff --name-only "$base"...HEAD
else
  git diff --stat
  git diff --name-only
fi
```

Inspect only relevant plans, verification results, and review artifacts. If an assigned PR is available, inspect its bounded metadata:

```bash
gh pr view --json title,body,additions,deletions,state,url 2>/dev/null || true
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

For cross-session patterns, use `agnt improve` separately. Keep private telemetry
out of retrospectives and committed Beads; promote only generalized,
human-approved findings.

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
