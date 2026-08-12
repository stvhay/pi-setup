# Available tools

- `rg PATTERN [PATH]` — fast regex search.
- `ast-grep --pattern '<code>' --lang <lang>` — structural search.
- `nanobanana -o OUT.png <prompt>` — image generation when `GEMINI_API_KEY` exists; use `nanobanana --help` for options.

# Agent helper

Use `~/.pi/agent/bin/agnt` as the deterministic human/CI/headless helper interface. Keep domain logic in `agnt_lib`; Pi extensions own lifecycle, UI, session, and provider integration; typed tools are thin agent-facing adapters. Do not duplicate domain logic across these surfaces. Run `agnt -h` or the command's `-h` for current syntax; full command reference lives in `~/.pi/agent/bin/README.md`.

Common entry points:

```bash
agnt tasks --models
agnt route --task TASK --risk medium --budget balanced
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
- Batch independent read-only tool calls in one turn. Keep ordered mutations, approvals, and safety gates serial.
- Update progress at phase boundaries; prefer harness/tool execution state over model-authored progress-only turns.
- Before code changes in a repository with `.beads/`, use `bd prime` and `bd ready` for context, then start interactive work with `agnt work direct-start <id> [--claim]`. This validates and shows the Bead, claims only with the explicit flag when needed, and links the current session; it does not create run bundles or worktrees. One logical Pi session belongs to one Bead. At interactive closeout, first commit task-owned implementation changes, then run `agnt improve outcome <id> <success|partial|failure|unclear>` and `agnt work direct-closeout <id> --reason "<reason>"`. Direct closeout requires matching session ownership/outcome and no tracked non-Beads changes; it closes the Bead, explicitly exports and verifies `.beads/issues.jsonl`, then commits only that shared portable Beads state, including legitimate mixed Bead rows, and never pushes. After current Bead closeout, call `handoff_bead` with the next ready Bead ID; it starts a fresh parent-linked session without copying the transcript. If the tool is unavailable, `/new` is the human fallback. Quitting and resuming may retain the same session.
- Documentation-only and read-only work may proceed without a Bead unless project instructions say otherwise.
- Use project-local `.pi/plans/` for durable designs/plans when they help handoff; observational memory is advisory until promoted into Beads or tracked artifacts.
- Prefer exact paths and filesystem retrieval (`rg`, `find`, `git grep`, `git diff`, `read`) over large pasted context.
- Delegate difficult or independent read-only analysis when useful. Route with `agnt route`, then call the `subagent` tool with `agent` omitted and the routed target as `model`; use `mode: "one-shot"` for cold complete packets and its `tasks` array for parallel work.
- Do not give subscription-backed subagents or reviewers default `maxProviderRequests`, `maxTotalTokens`, or `maxCostUsd` limits. One-shot already has one provider turn; omit its redundant request cap. Omit request caps for subscription-backed agentic work by default. Add request or duration caps only for an explicit bounded experiment or identified liveness/runaway risk, and label them as caller limits.
- Keep subscription-backed OpenAI/Codex as the root and default controller. Use direct metered OpenRouter models only for bounded diversity, specialist review, or explicit canary work; verify peer output against primary sources, files, and tests.
- Metered `openrouter` models must run in fresh workers through `subagent`; never switch a long-running root conversation to them. Use `mode: "one-shot"` for reviews and pass a bounded task packet, not ambient conversation history. Only tracked Codex and OpenRouter routes are configured.
- Ticket gateway, run artifacts, worktree-per-epic dispatch, and strict orchestration are opt-in. Ordinary coding does not require them.
- Unless explicitly narrowed, implementation approval includes staging and one local atomic commit of task-owned changes; use the shared development completion contract before closeout.
- Initial implementation approval may preauthorize exact reversible local Git setup and cleanup: named task branches/worktrees, post-integration removal, and staged deletion of tracked/config-controlled assets. Before cleanup or deletion, show exact paths/branches and commit-SHA recovery sources. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs, remote deletion, force/reset/clean, or history rewrite.
- Initial implementation approval may preauthorize one exact local integration through `agnt work integrate` when it names target checkout/branch, expected target HEAD, and source commit SHA. The helper serializes the target, rechecks scope under lock, aborts conflicts, and stops on divergence; any alternate integration strategy requires explicit approval.
- Initial implementation approval may preauthorize deployment to verified local-live and explicitly designated test/staging environments as one single-use action when it binds the Bead, source-selection rule, resolved target identity, exact preview and effect bounds, verification, rollback, and stop conditions. Production, unknown/mismatched targets, secrets changes, destructive rollback, and scope/preview changes require new explicit approval; rejection, cancellation, or timeout fails closed.
- Initial implementation approval may preauthorize one ordinary branch push after successful Bead closeout when it binds exact remote and branch identity, approved base SHA, bounded candidate-selection rule, expected remote state, final gates, and fail-closed checks. First push attempt consumes authority. Protected or production branch pushes, PR actions, force, tags, releases, merges, deletion, and history rewrite remain outside that authority.
- Beads messages about git operations describe Beads' internal sync mechanism, not agent authority for normal repository git commands.

Outside that exact initial scope, push, branch/worktree deletion, local merge, and deployment require explicit approval. Do not merge outside guarded integration, deploy outside verified non-production boundaries, force/reset/clean, delete branches or beads, rewrite history, change Beads remotes/history, or install hooks without explicit approval. Remote deletion and history rewrite remain explicitly gated.

# Human questions and approvals

- Use transient `ask` for clarification or exploration needed only in the current interactive session.
- Use durable `ticket_question` when the answer must survive handoff, block a Bead, or support later resumption. Do not chain durable questions for ideation; explore transiently, then persist only the final blocking decision when needed.
- For either question path, set `selectionMode` explicitly to `single` or `multi` and keep a typed custom response available.
- No interactive UI: never guess or select for the human. Report human input unavailable and remain blocked; when later resumption is required, leave a durable blocker open.
- Approvals are not questions. Use `ticket_approval` with informed scope, consequences, reversibility, and closeout evidence for consequential actions.

# Architecture boundaries

Keep these concepts distinct:

- **Work item/Bead:** durable task, dependency, decision, blocker, and closeout state.
- **Task:** model/tool routing default such as review, research, or orchestration.
- **Action template:** explicit operation binding task, skills, role, effects, and output contract.
- **Skill:** reusable method or capability loaded when relevant.
- **Role:** delegated-peer stance and output contract.
- **Tool/eval:** deterministic behavior or validation.

Routing, prompts, and roles do not replace skill methods or project safety gates. Use Beads for durable workflow state; private run artifacts are additional evidence only when optional orchestration is selected.

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
