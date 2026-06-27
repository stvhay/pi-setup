---
name: writing-plans
description: Use when you have an approved design, spec, or requirements for a multi-step task, before touching implementation code.
---

# Writing Implementation Plans

Create a concrete, greppable implementation plan from an approved design when the work needs one. Scale planning to task risk.

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

Announce: "I'm using the writing-plans skill to create the implementation plan."

## When to create a plan file

- **Tiny changes:** do not require a plan file unless requested; record inline verification commands instead.
- **Normal changes:** a combined design-plan artifact is preferred when one file can capture both decisions and tasks.
- **Large/risky changes:** create a separate implementation plan from the approved design.

Do not use planning as permission to implement. Implementation still requires approval or an explicit implementation request.

## Plan location

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
printf 'Plans dir: %s\n' "$PLANS_DIR"
```

Use exactly this helper. Do **not** save project plans under `~/.pi/plans`; that is not the project plans directory.

Save plans to one of:

```text
$PLANS_DIR/YYYY-MM-DD-<topic>-plan.md
$PLANS_DIR/YYYY-MM-DD-<topic>-design-plan.md
```

If asked to create a plan file, you must actually write the file with the `write` tool or shell redirection. Do not merely print the plan and claim it was saved. After writing, verify with:

```bash
test -f "$PLAN_FILE" && wc -l "$PLAN_FILE"
```

If you did not write and verify the file, say the plan is drafted but not saved. A claimed path is not evidence; only `test -f` output is evidence.

## Context gathering

Use shell tools first:

```bash
git status --short
git diff --stat
find . -name SPEC.md -o -name README.md -o -path './docs/*.md' | sort
rg -n "<important term>|TODO|FIXME" . --glob '!node_modules' --glob '!vendor' 2>/dev/null || true
```

If `graphify-out/graph.json` exists, map the affected subsystem with `agnt graphify explain "<symbol>"` (short keyword labels) before reading broadly; it surfaces dependents that belong in the plan's file list. See the knowledge-graph section of `dev-workflow-common`.

Read only the relevant files. Put paths in the plan so implementers can find context with `rg`/`read` rather than relying on chat history.

## Task sizing

Each task should be independently executable by the current session or by a fresh `agnt invoke` prompt. Avoid "see previous task" dependencies except where explicitly declared.

Good tasks:

- Have exact files and commands.
- Include enough context to work from the filesystem.
- Are small enough to test and commit independently.
- Make dependencies explicit.

## Plan header

Every standalone plan starts with:

```markdown
# <Feature Name> Implementation Plan

**Issue:** #<number> — <title> OR None
**Design:** <path/to/design.md> OR None
**Date:** YYYY-MM-DD
**Branch:** <branch-name>

**Goal:** <one sentence>

**Architecture:** <2-4 sentences>

**Acceptance Criteria:**
- [ ] <Specific verifiable condition>
- [ ] <Specific verifiable condition>

**Verification Command(s):**
```bash
<exact command(s) that prove completion>
```

---
```

## Combined design-plan

For normal work, a combined artifact may replace separate design and plan files. Include only the useful parts: goal, chosen approach, files, tasks, acceptance criteria, and verification commands. Do not duplicate the full design template unless the risk warrants it.

## Verification command quality

Verification commands must be boring and likely to exist. Prefer simple commands such as `test -f`, `rg -n`, `grep -n`, project test scripts, and documented CI commands. Do not invent unusual flags. When unsure, run `<command> --help` or use a simpler POSIX command before recording it.

Examples:

```bash
test -f CONTRIBUTING.md
rg -n "^## Test Commands" CONTRIBUTING.md
```

Avoid fragile or exotic commands unless the project already uses them.

## Task template

````markdown
### Task N: <name> [Independent|Depends on: Task M]

**Context:** <What this task does and where it fits. Include exact paths and relevant docs/specs.>

**Files:**
- Create: `path/to/new-file`
- Modify: `path/to/existing-file`
- Test: `path/to/test-file`

**Steps:**
1. Write/update tests first when behavior changes.
2. Run the focused test and confirm the expected failure if using TDD.
3. Implement the smallest change that satisfies the test/requirement.
4. Run focused verification.
5. Run broader verification if this touches shared behavior.
6. Commit if this repository/workflow expects incremental commits.

**Focused verification:**
```bash
<exact command>
```

**Expected result:** <What output/status proves success.>
````

## Dependency and conflict checks

Before marking tasks independent:

1. Scan each task's `Files` list.
2. If two tasks modify the same file, add an explicit dependency or split differently.
3. If tasks cross unrelated subsystems, recommend separate issues/PRs.

Include this section when conflicts exist:

```markdown
## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `path` | Task 1, Task 3 | Task 3 depends on Task 1 |
```

## Peer execution notes

If the plan benefits from peer review or parallel execution, include commands such as:

```bash
~/.pi/agent/bin/agnt invoke olla-local/qwen3:8b @path/to/plan.md "Review Task 2 for missing context"
~/.pi/agent/bin/agnt invoke --fanout -o .pi/peer-runs/<topic> @path/to/plan.md "Review this implementation plan"
```

Do not require peer execution for every plan. Use it when it reduces risk.

## Handoff

End with:

```markdown
## Execution Handoff

Plan saved to: `<path>` (verified with `test -f`)
Recommended next skill: `test-driven-development` for behavior changes; `verification-before-completion` before claiming completion.
```

Do not automatically start implementation unless the user asked for that. Ask or proceed based on the surrounding conversation.

## Principles

- DRY, YAGNI, TDD where behavior changes.
- Exact paths over prose.
- Exact commands over vague verification.
- Keep large context in files and retrieve with `rg`.
- Avoid brittle acceptance criteria based on test name counts; prefer behavior or explicit named checks.
