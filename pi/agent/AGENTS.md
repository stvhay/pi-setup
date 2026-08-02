# Available tools

- `rg PATTERN [PATH]` — fast regex search.
- `ast-grep --pattern '<code>' --lang <lang>` — structural search.
- `nanobanana -o OUT.png <prompt>` — image generation when `GEMINI_API_KEY` exists; use `nanobanana --help` for options.

# Agent helper

Use `~/.pi/agent/bin/agnt` as the primary helper interface. Run `agnt -h` or the command's `-h` for current syntax; full command reference lives in `~/.pi/agent/bin/README.md`.

Common entry points:

```bash
agnt tasks --models
agnt route --task TASK --risk medium --budget balanced
agnt invoke --one-shot --task TASK provider/model packet.md
agnt eval list
agnt context-health
agnt doctor --json
agnt plans-dir
```

Prefer deterministic helpers, tools, and evals over repeating procedures in prompts.

# Operational health

After repeated unexpected tool, provider, environment, Node/npm, Docker, or Beads failures, stop retrying and run:

```bash
agnt doctor --json
```

Use its report to separate environment failure from task failure. `agnt doctor` is read-only; do not change shell startup or home-managed configuration without explicit approval.

# Development workflow

- Work directly in the current Pi session by default: inspect, edit tracked files, and run focused verification.
- Before code changes in a repository with `.beads/`, confirm a Bead exists and inspect it with `bd show <id>`; use `bd prime` and `bd ready` for context and unblocked work. After claiming interactive work, run `agnt improve link <id>` so private telemetry uses an exact work-item link; runner sessions link automatically. At interactive closeout, run `agnt improve outcome <id> <success|partial|failure|unclear>` to guarantee both link and final outcome.
- Documentation-only and read-only work may proceed without a Bead unless project instructions say otherwise.
- Use project-local `.pi/plans/` for durable designs/plans when they help handoff; observational memory is advisory until promoted into Beads or tracked artifacts.
- Prefer exact paths and filesystem retrieval (`rg`, `find`, `git grep`, `git diff`, `read`) over large pasted context.
- Delegate difficult or independent read-only analysis when useful. Route with `agnt route`, then call the `subagent` tool with `agent` omitted and the routed target as `model`; use its `tasks` array for parallel work. Reserve `agnt invoke --one-shot` for cold complete packets and headless execution.
- Prefer subscription-backed OpenAI/Codex or local models when capability is comparable; verify peer output against primary sources, files, and tests.
- Metered `olla-cloud` models must run in fresh workers through `subagent` or `agnt invoke`; never switch a long-running root conversation to them. Pass a bounded task packet, not ambient conversation history.
- Runner, ticket gateway, run artifacts, worktree-per-epic dispatch, and strict orchestration are opt-in. Ordinary coding does not require them.
- Unless explicitly narrowed, implementation approval includes staging and one local atomic commit of task-owned changes; use the shared development completion contract before closeout.
- Beads messages about git operations describe Beads' internal sync mechanism, not agent authority for normal repository git commands.

Do not push, merge, delete branches or beads, remove worktrees, rewrite history, change Beads remotes/history, or install hooks without explicit approval.

# Architecture boundaries

Keep these concepts distinct:

- **Work item/Bead:** durable task, dependency, decision, blocker, and closeout state.
- **Task:** model/tool routing default such as review, research, or orchestration.
- **Action template:** explicit operation binding task, skills, role, effects, and output contract.
- **Skill:** reusable method or capability loaded when relevant.
- **Role:** delegated-peer stance and output contract.
- **Tool/eval:** deterministic behavior or validation.

Routing, prompts, and roles do not replace skill methods or project safety gates. Use Beads for durable workflow state; `.pi/runs` is additional evidence only when optional orchestration is selected.

# Research

For cited external claims, search, fetch, and verify primary URLs before citing:

```bash
agnt web-search "query"
agnt web-fetch URL
```

Do not treat model-native knowledge or unverified peer URLs as sourced evidence.

# Context and reusable learning

- Query `graphify-out/graph.json` first for architecture/dependency work when present: `agnt graphify query "keyword"` or `agnt graphify explain "symbol"`; verify findings in source.
- Review private telemetry with `agnt improve`; promote only sanitized, human-approved findings into Beads.
- Shared workflow conventions live in hidden skill `~/.pi/agent/skills/dev-workflow-common/SKILL.md` and should be loaded only when another skill requests them.

# Context packages

Keep root instruction files small and always applicable. Put supplements beside them under `<root-stem>.d/`:

- model overlays: `AGENTS.d/models/<family>.md`, refined by provider/model paths when needed
- role overlays: `AGENTS.d/roles/<role>.md`
- skill detail: `skills/<name>/SKILL.md`, with bulky material under `references/`

Generate layered role/model context with `agnt instructions --context provider/model --role ROLE`. Supplements may specialize behavior but must not weaken security, approval, verification, git, or project rules. `SOUL.md` controls communication preferences only.
