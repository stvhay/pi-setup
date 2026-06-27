---
name: dev-workflow-common
description: Shared Pi development workflow conventions. Hidden helper skill for other workflow skills; use only when another skill asks you to read it.
disable-model-invocation: true
---

# Dev Workflow Common

Shared conventions for Pi development workflow skills. Keep this file small and searchable.

## Filesystem-first context

Prefer durable, greppable artifacts over chat-only state:

- Plans/designs: project-local `.pi/plans/` by default.
- Scratch peer outputs: project-local `.pi/peer-runs/`, `.pi/council/`, `.pi/redteam/`, `.pi/research/` as appropriate.
- Use `rg`, `find`, `git grep`, `git diff`, and exact paths instead of pasting large context into prompts.
- Keep instructions DRY: reference files and commands by path rather than duplicating long text.
- Do not leave avoidable generated artifacts (`__pycache__`, temporary logs, build output) unless they are intentionally part of the task.

## Knowledge graph

If `graphify-out/graph.json` exists, use it to map code structure before broad exploration:

```bash
agnt graphify query "<keyword>"     # lexical label match + BFS expansion
agnt graphify explain "<symbol>"    # one node's callers/dependents with file:line
agnt graphify path "<A>" "<B>"      # shortest connection between two nodes
```

- Queries are lexical, not semantic. Use short identifier/concept keywords (`query "route"`), never sentence-form questions. Run 2-3 keyword probes rather than one long query.
- Treat results as a map of `file:line` locations to read next, not as answers. Verify against source files before acting.
- The graph is built at the last commit (`built_at_commit` in `graph.json`); uncommitted edits and newly added symbols are absent. Use it for pre-change structure and impact analysis, not to inspect brand-new code.

## Task tiers

Choose ceremony by risk, not habit:

- **Tiny:** obvious one-file/doc/config change. Inline design, edit, focused verify, summarize. No plan file unless requested.
- **Normal:** small feature/bugfix. Concise approved design; use a combined design-plan artifact when useful.
- **Large/risky:** architecture, public API, data/security, multi-file uncertainty. Use separate design, plan, checkpoints, review, docs validation.
- **Parallelizable:** independent domains with disjoint files and verification. Use advisory peers by default; use worktrees only with explicit approval.

Hard gates still apply: approval before implementation in design workflows, branch/dirty-tree checks before edits, fresh verification before completion, and approval for destructive/remote git actions.

## Plan directory

Use the helper:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
```

Override with `PI_PLANS_DIR` when needed.

## Peer orchestration

Use `agnt` instead of embedding long `pi --print` commands:

```bash
~/.pi/agent/bin/agnt invoke provider/model "prompt"
~/.pi/agent/bin/agnt invoke --fanout -o .pi/peer-runs/<name> provider/model prompt.md
~/.pi/agent/bin/agnt tasks --models
```

Default peer roles should come from the user's curated task/model set, not from hard-coded Claude assumptions.

## Web research

Use backend-agnostic helpers:

```bash
~/.pi/agent/bin/agnt web-search "query"
~/.pi/agent/bin/agnt web-fetch URL
```

`agnt web-search` reports `cat: <category>` in its output. Cite only fetched/verified URLs.

## Skill adaptation rules

When porting older Claude Code skills to Pi:

- Replace `.claude/...` paths with `.pi/...` unless there is a project-specific reason not to.
- Replace Task/subagent assumptions with `agnt invoke`, `agnt invoke --fanout`, or explicit manual execution.
- Do not assume native WebSearch/WebFetch, AskUserQuestion, TodoWrite, MCP, hooks, background bash, or plan mode.
- Prefer concise prompts and artifacts that can be found with `rg`.
