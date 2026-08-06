---
name: finishing-a-development-branch
description: Use when completed implementation needs branch readiness, documentation, review, PR, merge, or cleanup guidance.
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

## Closeout routing

Load this skill first as sole closeout coordinator. Select companion skills only when their phase triggers:

| Companion skill | Trigger | Selection / subsumption |
|---|---|---|
| `verification-before-completion` | Every closeout and after any closeout fix | **Required.** Load once; reuse the recorded baseline, run focused checks after fixes, and run one complete gate for each final candidate; never subsumed. |
| `documentation-standards` | Documentation requested, impacted, or uncertain | Load in validate mode; otherwise coordinator documentation check subsumes generic docs prose. |
| `requesting-code-review` | Non-trivial or risky diff, merge/PR preparation, or required review | Load; otherwise coordinator scope check handles trivial closeout. |
| `code-simplification` | Verification passed and simplification is requested or clearly useful in touched files | Load only now; otherwise coordinator scope check subsumes generic cleanup advice. |
| `session-to-skill-extractor` | Substantial non-trivial wrap-up or Bead close | Load once at final wrap-up; skip routine summaries. |

Load each selected companion when its phase begins, not all at start. If a selected skill is already loaded and unchanged in this session, reuse its current instructions instead of rereading. Reload only after content changes or an explicit diagnostic reread.

Reuse or establish one relevant baseline before optional closeout phases. Do not repeat the full baseline during repair: simplification, review, or documentation fixes require focused executable checks. Run the complete required matrix once after the candidate stabilizes. A tracked final-candidate change invalidates the final gate and requires one new complete gate.

`writing-clearly-and-concisely` is subsumed by this coordinator's concise report contract; do not load it solely for closeout prose. Generic cleanup advice is subsumed by scope checks, but `code-simplification` remains required when its trigger matches. Safety, approval, verification, documentation, and review gates are never subsumed when applicable.

## Workflow

1. **Inspect branch/project state**
2. **Reuse or establish the baseline once**
3. **Optionally simplify**
4. **Validate documentation**
5. **Request code review**
6. **Run focused repair checks and inspect scope**
7. **Run the final candidate gate once**
8. **Prepare PR/merge or local project summary**
9. **Run substantial-wrap-up extraction when triggered**
10. **Ask for approval before any remote/destructive action**

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

## Step 2: Reuse or establish the baseline once

Load `verification-before-completion`. Reuse baseline evidence recorded for this work item/worktree, or establish the project-specific baseline once if none exists. This phase is mandatory.

Find project-specific verification first:

```bash
rg -n "test|lint|typecheck|quality|verify|ci" README.md CONTRIBUTING.md docs package.json pyproject.toml Makefile .github 2>/dev/null || true
```

Run the relevant command(s) only when baseline evidence is absent. If no command is discoverable, report `NOT_VERIFIED` and ask for the command. Record exact failures before proceeding.

A new or unclassified baseline failure blocks work. An unchanged baseline failure may follow an already-approved plan, but it cannot make a required final gate pass.

## Step 3: Optionally simplify

After baseline status is understood and focused change checks pass, load `code-simplification` only when its matrix trigger matches. Keep changes inside touched files and run focused repair checks after any edit.

## Step 4: Validate documentation

Use `documentation-standards` in validate mode for documentation-impacting changes. If uncertain whether docs are impacted, report `NOT_SURE` rather than PASS. Public API/user-visible changes usually require docs unless the project has no user-facing docs or the user explicitly says documentation is unnecessary.

Documentation status can be:

- `PASS` — docs are current or no docs are needed, with reason
- `NEEDS_DOCS` — block PR-ready status unless user explicitly defers with reason
- `NOT_SURE` — ask user or inspect more

If deferred, record:

```markdown
**Documentation deferred:** <reason>
```

## Step 5: Request code review

Use `requesting-code-review` for non-trivial diffs unless the user requested no file creation/artifacts. Follow its Codex-first direct OpenRouter matrix and spend gates; local and Olla routes are inactive.

If artifact creation is not allowed, either skip peer review with a note or run only direct peer calls whose outputs are summarized in the response without writing `.pi/reviews`.

Review status can be:

- `PASS` — continue
- `NEEDS_WORK` — block PR-ready status until addressed or explicitly deferred
- `NOT_SURE` — inspect/ask

Verify serious review findings against the code before treating them as blockers.

## Step 6: Run focused repair checks and inspect scope

After any simplification, review, or documentation fix, run the smallest executable checks proving the repaired behavior and affected neighbors. Do not rerun the broad matrix unless the change widens to that scope. Then inspect scope coherence:

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

## Step 7: Run the final candidate gate once

After all tracked candidate changes stabilize, run every required release command once. Compare failures to recorded baseline evidence. A tracked change after this gate creates a new final candidate and requires a new complete gate. If any required gate remains red, report `NOT_VERIFIED` even when the task-specific regression status is PASS.

## Step 8: Prepare PR / project summary

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
- Baseline once: `<command>` → PASS/FAIL/NOT_VERIFIED
- Focused repair: `<command>` → PASS/FAIL/NOT_VERIFIED
- Final candidate gate: `<complete matrix>` → PASS/FAIL/NOT_VERIFIED
- Unchanged baseline failures: `<none or exact matches>`

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

## Step 9: Extract substantial learning when triggered

At substantial non-trivial wrap-up or Bead close, load `session-to-skill-extractor` once. Routine summaries skip extraction.

## Step 10: Optional actions after approval

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
