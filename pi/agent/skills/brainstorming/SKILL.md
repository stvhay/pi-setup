---
name: brainstorming
description: Use when creating features, building components, adding functionality, or modifying behavior — any creative work that benefits from exploring intent, requirements, and alternatives before implementation begins.
---

# Brainstorming Ideas Into Designs

Turn an idea into an approved design before implementation. Scale ceremony to risk; do not skip the approval gate.

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Hard gate

Do **not** implement, scaffold, create files, edit files, write code, or invoke implementation skills until you have presented a design and the user has approved it.

Before approval, allowed tool use is read-only project discovery only: `read` and harmless `bash` inspection commands such as `pwd`, `find`, `rg`, `git status`, `git diff`, and `git log`. Do not use `write` or `edit` before approval.

In non-interactive / `--print` contexts, you usually cannot obtain real user approval. Therefore stop after presenting the design and approval question unless the prompt explicitly says approval has already been granted.

## Filesystem-first context

Use shell tools to understand the project without bloating chat context:

```bash
pwd
git status --short
git branch --show-current
find . -maxdepth 3 -type f | sort | head -200
rg -n "TODO|FIXME|SPEC|Architecture|Design" README.md docs .pi AGENTS.md CLAUDE.md 2>/dev/null || true
git log --oneline -5 2>/dev/null || true
```

Read only the files that matter. Prefer exact paths and small excerpts.

## Recommended workflow

1. **Clarify the request**
   - Identify goal, users, constraints, non-goals, success criteria.
   - Batch independent questions in one message.
   - If enough context exists, present assumptions instead of asking obvious questions.

2. **Check project/work state**
   - Surface dirty work, current branch, and likely issue/PR context.
   - If `gh` is available and the project uses GitHub, optionally find/create an issue, but do not block brainstorming on it.
   - If on `main`/`master`, recommend a branch or worktree before implementation. Do not force it.

3. **Explore alternatives**
   - Present 2-3 approaches.
   - Include trade-offs and a recommendation.
   - Keep YAGNI pressure high.

4. **Consider boundaries**
   - Identify affected subsystems/files.
   - Look for nearby `SPEC.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`.
   - If work crosses unrelated boundaries, recommend splitting.

5. **Present design for approval**
   - Scale detail to complexity.
   - Cover: approach, files/components, data/control flow, errors, tests, documentation impact.
   - Ask for approval or changes before planning/implementation.

6. **Record only what is useful**
   - Tiny changes: keep the approved design in the response.
   - Normal changes: use a concise combined design-plan artifact if it helps execution.
   - Large/risky changes: save a design doc under `$PLANS_DIR/YYYY-MM-DD-<topic>-design.md` using `~/.pi/agent/bin/agnt plans-dir`.

7. **Transition to planning**
   - Tiny changes may proceed after approval with inline verification commands.
   - Normal changes may use `writing-plans` to create a combined design-plan.
   - Large/risky changes should use `writing-plans` for a separate implementation plan.

## Design doc template

Use this for substantial/risky work. For tiny or normal work, shorten it aggressively.

```markdown
# Design: <topic>

**Issue:** #<number> — <title> OR None
**Date:** YYYY-MM-DD
**Branch:** <branch-name>

## Goal

<One paragraph.>

## Context

<Relevant project facts, with paths.>

## Non-goals

- <What this deliberately does not do.>

## Options considered

### Option A: <name>
- Pros:
- Cons:

### Option B: <name>
- Pros:
- Cons:

## Recommended design

<Chosen approach and rationale.>

## Files and boundaries

- `path`: <role/change>

## Testing strategy

- <Tests/verification commands.>

## Documentation impact

- <Docs to update or "None".>

## Open questions

- <Remaining decisions, if any.>
```

## Good behavior

- Ask fewer, better questions.
- Use existing project docs and grep before asking the user.
- Keep designs concise unless the risk/complexity demands detail.
- Record substantial decisions in `.pi/plans/`; avoid artifact churn for tiny changes.
- Do not hide uncertainty; list assumptions explicitly.
