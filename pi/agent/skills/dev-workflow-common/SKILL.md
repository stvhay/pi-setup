---
name: dev-workflow-common
description: Use only when another workflow skill requests shared Pi development conventions.
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

## Development completion contract

- Approval to implement includes staging and one local atomic commit of task-owned changes unless the user explicitly narrows that approval. Explicit `do not commit` instructions override this default.
- Initial implementation approval may preauthorize exact reversible local Git setup and cleanup: named task branches/worktrees and their post-integration removal. Tracked/config-controlled deletions included in that scope may be staged without another approval.
- Before staging, inspect the diff and status. Never stage unrelated pre-existing changes; if task-owned and unrelated changes cannot be separated safely, preserve the work and ask with exact paths.
- Stop instead of acting on ambiguous ownership, unrelated changes, untracked runtime data, backups, unknown/non-config-controlled data, active worktrees, remote refs, remote deletion, force/reset/clean, or history rewrite. These are outside reversible local authority.
- Deletion preview (not a second approval): before committing, show each exact staged deletion and its recovery source. Fail if any deleted path was not tracked at the recovery commit.

```bash
git status --short --untracked-files=all
recovery_sha=$(git rev-parse HEAD)
git diff --cached --name-status --diff-filter=D --no-renames
git diff --cached --name-only --diff-filter=D --no-renames -z |
  while IFS= read -r -d '' path; do
    git cat-file -e "$recovery_sha:$path" || exit 1
    printf '%s <- %s:%s\n' "$path" "$recovery_sha" "$path"
  done
```

- For preauthorized post-integration cleanup, take `worktree_path`, `branch`, and `integration_target` only from exact approved scope. Verify repository identity, path/branch association, task ownership, inactive ownership, clean status including untracked files, and integrated recovery SHA. Run the guarded non-force block as one unit; any mismatch or command refusal stops before later mutations. Preview precedes removal.

```bash
(
  set -euo pipefail
  : "${worktree_path:?approved worktree path is required}"
  : "${branch:?approved local branch is required}"
  : "${integration_target:?approved integration target is required}"
  test "$(git -C "$worktree_path" rev-parse --path-format=absolute --git-common-dir)" = \
    "$(git rev-parse --path-format=absolute --git-common-dir)"
  actual_branch=$(git -C "$worktree_path" symbolic-ref --quiet --short HEAD)
  test "$actual_branch" = "$branch"
  test -z "$(git -C "$worktree_path" status --short --untracked-files=all)"
  recovery_sha=$(git -C "$worktree_path" rev-parse HEAD)
  git merge-base --is-ancestor "$recovery_sha" "$integration_target"
  printf '%s %s <- %s\n' "$worktree_path" "$branch" "$recovery_sha"
  git worktree remove "$worktree_path"
  git branch -d "$branch"
)
```

- After verification, commit task-owned changes. Do not close the Bead or claim completion while task-owned changes remain uncommitted unless committing is explicitly prohibited or blocked; record that blocker and resumption path instead.
- For direct work, record `agnt improve outcome <id> <outcome>`, then run `agnt work direct-closeout <id> --reason "<reason>"`. This second local commit records shared portable Beads state separately: explicit export, target closeout parity, and all legitimate `.beads/issues.jsonl` rows. It refuses tracked non-Beads changes and never stages or commits them.
- Outside exact preauthorized cleanup, branch/worktree deletion requires explicit approval. Push, merge, deploy, remote deletion, history rewrite, Beads deletion/remote/history changes, hooks, and force/reset/clean remain explicitly gated; direct closeout never pushes.

## Plan directory

Use the helper:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
```

Override with `PI_PLANS_DIR` when needed.

## Peer orchestration

For interactive work, keep policy in `agnt` and execution in Archimedes:

1. Run `~/.pi/agent/bin/agnt route --task <task> --risk <level> --budget <budget>`.
2. Call the `subagent` tool with `agent` omitted and the routed target as `model`.
3. Use one `tasks` array for independent parallel peers.
4. Persist returned outputs under `.pi/peer-runs/<topic>/` only when downstream work needs artifacts.

```json
{
  "tasks": [
    { "task": "<focused read-only prompt A>", "model": "<routed target A>", "cwd": "<repository>" },
    { "task": "<focused read-only prompt B>", "model": "<routed target B>", "cwd": "<repository>" }
  ]
}
```

Use `mode: "one-shot"` for cold complete packets and normal agentic mode for peers that need tools or project context. Default peer roles should come from curated task/model policy, not hard-coded Claude assumptions.

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
- Replace platform-specific Task assumptions with routed unnamed `subagent` calls or explicit manual execution; use subagent `mode: "one-shot"` for cold packets.
- Do not assume native WebSearch/WebFetch, AskUserQuestion, TodoWrite, MCP, hooks, background bash, or plan mode.
- Prefer concise prompts and artifacts that can be found with `rg`.
