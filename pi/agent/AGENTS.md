# Tools

- Use `rg PATTERN [PATH]` for search, `ast-grep --pattern '<code>' --lang <lang>` for structural search, and `nanobanana -o OUT.png <prompt>` for image generation when `GEMINI_API_KEY` exists.

# Agent helper

`~/.pi/agent/bin/agnt` is deterministic human/CI/headless adapter. Keep deterministic domain logic in `agnt_lib`; extensions own Pi lifecycle, UI, session, and provider integration; typed tools stay thin. Avoid duplicate logic; see `~/.pi/agent/bin/README.md` or command help.

Discover with `agnt tasks --models`, `agnt route --task TASK --risk medium --budget balanced`, `agnt eval list`, `agnt context-health`, `agnt doctor --json`, or `agnt plans-dir`; prefer deterministic helpers/evals to prompt procedures.

# Workflow

- Work directly in current Pi session by default. Batch independent reads; serialize mutations, approvals, and safety gates. Update progress at phase boundaries.
- After repeated unexpected tool, provider, environment, Node/npm, Docker, or Beads failures, stop retrying and run read-only `agnt doctor --json`; do not alter shell startup or home-managed config without approval.
- Before code changes, run `bd prime`, `bd ready`, then `agnt work direct-start <id> [--claim]`; it claims only with `--claim` and links one session to one Bead without run bundles/worktrees. Before changing a public interface, persistent state/format, security boundary, dependency, or cross-cutting mechanism, state outcome, affected boundary, smallest implementation, and verification. Ask one targeted question with options and a recommendation only when interpretations differ materially; otherwise proceed within that boundary.
- Close direct work only after committing task-owned changes: run `agnt work direct-closeout <id> --outcome success --reason "<reason>"`; use `agnt improve outcome <id> <partial|failure|unclear>` only for non-success or manual repair. It records explicit success, verifies matching session ownership/outcome, rejects tracked non-Beads changes, closes, exports/verifies `.beads/issues.jsonl`, commits only shared portable Beads state, and never pushes. Preserve objective, decisions, constraints, blockers, verification, and next-work refs in Beads or exact tracked/private artifacts.
- After successful closeout, call `handoff_bead` without target; it auto-selects sole ready non-epic work or asks once, then starts fresh parent-linked session containing only referenced state. Explicit target is allowed only from persisted unassigned TUI or after successful closeout. Non-success/partial/failed closeout stops; `/new` is human fallback.
- Read-only/docs work needs no Bead unless policy says otherwise. Store plans in `.pi/plans/`; observational memory stays advisory until promoted.
- Prefer exact paths and `rg`/`find`/`git grep`/`git diff`/`read`. Query existing `graphify-out/graph.json` before architecture/dependency work, then verify source.
- Delegate independent read-only work when useful: run `agnt route --access repository`, then unnamed `subagent` with route-generated `routingTask`, model, mode, access, and thinking; repository access is agentic. Self-contained cold packets use `--access self-contained` and one-shot mode; use `tasks` for parallel work.
- Subscription-backed peers normally omit request/token/cost caps. Add caps only for explicit bounded experiments or liveness risk. Use metered OpenRouter only for bounded diversity, specialist review, or explicit canary work, always in fresh subagents; metered repository inspection requires route-generated justification, estimates, aggregate budget, and per-child limits. Keep subscription OpenAI/Codex as root/default controller and verify peer claims against source/tests.
- Ticket gateway, run artifacts, worktree-per-epic dispatch, and strict orchestration are opt-in; ordinary coding does not require them.
- Unless narrowed, implementation approval includes staging and one local atomic commit of task-owned changes under shared completion contract; Beads sync wording does not govern repository Git authority.
- Initial implementation approval may cover exact reversible named local branches/worktrees, post-integration removal, and staged tracked/config-controlled deletions. Before cleanup/deletion, show exact paths/branches and commit-SHA recovery. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs/deletion, force/reset/clean, or history rewrite.
- Initial implementation approval may cover one exact local `agnt work integrate` action when target checkout/branch, expected target HEAD, and source SHA are named. Helper serializes and rechecks scope, aborts conflicts, and stops on divergence; alternate integration needs approval.
- Initial implementation approval may cover one verified local-live or named test/staging deployment when it binds Bead, source-selection rule, resolved target identity, exact preview/effect bounds, verification, rollback, and stop conditions. Production, unknown/mismatched targets, secrets changes, destructive rollback, or scope/preview drift need new approval; rejection/cancellation/timeout fails closed.
- Initial implementation approval may cover one ordinary branch push after successful closeout when it binds remote/branch identity, approved base SHA, bounded candidate-selection rule, expected remote state, and final gates. First attempt consumes authority. Protected/production push, PR, force, tags, release, merge, deletion, and history rewrite remain excluded.
- Outside exact preauthorized setup, integration, cleanup, named non-production deployment, and ordinary push, require explicit approval for push, branch/worktree deletion, local merge, and deployment. Never force/reset/clean, delete Beads, alter Beads remotes/history, install hooks, remotely delete, or rewrite history.

# Human decisions

- Use transient `ask` only for current-session clarification/exploration. Set `selectionMode` and allow typed custom input.
- Use durable `ticket_question` only when answer must survive handoff/resumption or block a Bead; explore transiently first and persist final blocker only. Use `ticket_approval` for consequential actions with informed action/scope, consequences, reversibility, and closeout evidence, creating durable Beads blocker before UI confirmation. Approvals are not questions.
- With no interactive UI, never guess or answer for human; report blocked state and leave durable blocker when later resumption matters.

# Concepts and context

Keep work item/Bead, routing task, action template, skill, role, and tool/eval distinct; routing, prompts, and roles do not replace skills or gates. Beads hold durable state; private runs are optional evidence.

Keep root instructions universal. Put family overlays at `<root-stem>.d/models/<family>.md`; refine with slash-style provider/model paths. Put roles under `<root-stem>.d/roles/<role>.md`, and skills under `skills/<name>/SKILL.md` with bulky references beside them. Generate layered context with `agnt instructions --context provider/model --role ROLE`; overlays may specialize but never weaken security, approval, verification, Git, or project rules. `SOUL.md` controls communication only.

# Research and learning

For cited external claims, use `agnt web-search` then `agnt web-fetch`; cite verified primary URLs. Review private telemetry with `agnt improve`; promote only sanitized, human-approved findings to Beads. Load hidden `dev-workflow-common` only when another skill requests it.
