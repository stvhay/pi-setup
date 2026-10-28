# Shared tools

Across projects; project `AGENTS.md` adds repository-specific rules. Use `rg PATTERN [PATH]` (search), `ast-grep --pattern '<code>' --lang <lang>` (structural search), `nanobanana -o OUT.png <prompt>` (images, when `GEMINI_API_KEY` exists).

# agnt

`~/.pi/agent/bin/agnt` is deterministic human/CI/headless adapter. See `~/.pi/agent/bin/README.md` or command help.

Discover with `agnt tasks --models`, `agnt route --task TASK --risk medium --budget balanced`, `agnt eval list`, `agnt context-health`, or `agnt plans-dir`; prefer deterministic helpers/evals to prompt procedures.

# Workflow

- Default: direct current-session work. Batch independent reads; serialize mutations, approvals, and safety gates. Update progress at phase boundaries.
- After repeated unexpected tool/provider/environment/Node/npm/Docker/Beads failures, stop retrying and run read-only `agnt doctor --json`; shell startup or home-managed config changes need approval.
- Beads is canonical; GitHub issues are external adapters/exports. Before code changes, run `bd prime`, `bd ready`, `bd show <id>`, then `agnt work direct-start <id> [--claim]`; `--claim` claims/links one session/Bead without run bundles/worktrees. For public interface, persistent state, security boundary, dependency or cross-cutting changes: outcome, affected boundary, smallest implementation, verification. Ask one targeted question (options and a recommendation) when interpretations differ materially.
- Commit task-owned code, then `agnt work direct-closeout <id> --outcome success --reason "<reason>"`. Non-success/repair: `agnt improve outcome <id> <partial|failure|unclear>`. Verifies owner/outcome/closure; dirty tracked code blocks. Tracked export: export/verify/commit shared portable Beads state. Wholly untracked, ignored `.beads/`: local-only, no export/stage/commit. Ambiguity blocks; never auto-publish/untrack; never pushes. Keep objective, decisions, constraints, blockers, verification, next-work refs in Beads or exact tracked/private artifacts.
- For unfinished work, `handoff_bead` saves `progress`/refs; `targetBead` switches within scope. Keep dirty work/outcomes; no transcripts or false success. Recover pending decisions; reconcile uncertain effects. Closed non-success departure needs its owner, captured scope, closure proof, settled effects and clean existing target. Preserve outcomes/dirt; never sweep owners or create destinations. After successful closeout, omit target. `/new` is human fallback only for unavailable runtime, never ownership override.
- Use applicable skills for design/planning/verification/review/docs/branch finishing. Read-only/docs need no Bead unless policy requires one. Plans: `.pi/plans/`. Observational memory is advisory until promoted.
- Filter verbose tool results before model context; preserve failures and required proof. Before architecture/dependency work, query `graphify-out/graph.json`, then verify source.
- Route unnamed `subagent` once via `route`: repository access is agentic; self-contained cold packets use one-shot mode. `agnt route --task review --access repository`; `--access self-contained`. Use `artifact` for deferred full results, `status-only` for deterministic checks, `inline` when content is needed now; `pass-no-findings` only when explicitly requested.
- Subscription-backed peers normally omit request/token/cost caps. Use `maxIdleMs` only for an identified liveness risk; routine reviews have no caller deadline, and reserve `maxDurationMs` for metered/hard bounds. Metered OpenRouter runs only in fresh subagents with estimates, justification, and aggregate budget; repository routes add request/token/cost limits. Keep subscription OpenAI/Codex as controller; verify peers.
- Ticket gateway, run artifacts, worktree-per-epic dispatch, and strict orchestration are opt-in. With standing policy, first direct-start uses repeatable `--scope-bead <id>` for approved work; never infer ready-work scope or widen assignments.
- Unless narrowed, implementation approval includes staging and one local atomic commit of task-owned changes under shared completion contract; Beads sync wording does not govern repository Git authority.
- Initial implementation approval may cover exact reversible named local branches/worktrees, post-integration removal, and staged tracked/config-controlled deletions. Before cleanup/deletion, show exact paths/branches and commit-SHA recovery. Stop on unrelated changes, ambiguous ownership, untracked runtime data, backups, remote refs/deletion, force/reset/clean, or history rewrite.
- Initial implementation approval may cover one exact local `agnt work integrate` action when target checkout/branch, expected target HEAD, and source SHA are named. Helper serializes and rechecks scope, aborts conflicts, and stops on divergence; alternate integration needs approval.
- Initial implementation approval may cover one verified local-live or named test/staging deployment when it binds Bead, source-selection rule, resolved target identity, exact preview/effect bounds, verification, rollback, and stop conditions. Production, unknown/mismatched targets, secrets changes, destructive rollback, or scope/preview drift need new approval; rejection/cancellation/timeout fails closed.
- Initial implementation approval may cover one ordinary branch push after successful closeout when it binds remote/branch identity, approved base SHA, bounded candidate-selection rule, expected remote state, and final gates. First attempt consumes authority. Protected/production push, PR, force, tags, release, merge, deletion, and history rewrite remain excluded.
- Outside exact preauthorized setup, integration, cleanup, named non-production deployment, and ordinary push, require explicit approval for push, branch/worktree deletion, local merge, and deployment. Never force/reset/clean, delete Beads, alter Beads remotes/history, install hooks, remotely delete, or rewrite history.

# Decisions

- Use transient `ask` only for current-session clarification/exploration. Set `selectionMode` and allow typed custom input.
- Use durable `ticket_question` only when answer must survive handoff/resumption or block a Bead; explore transiently first and persist final blocker only. Use `ticket_approval` for consequential actions with informed action/scope, consequences, reversibility, and closeout evidence, creating durable Beads blocker before UI confirmation. Approvals are not questions.
- With no interactive UI, never guess or answer for humans; report blocked state, leaving a durable blocker when resumption matters.

# Context

Keep work item/Bead, routing task, action template, skill, role, and tool/eval distinct. Routing/prompts/roles never replace skills or gates. Beads: durable state; private runs: optional evidence.

Universal roots; family overlays at `<root-stem>.d/models/<family>.md`, refined with slash-style provider/model paths; roles at `<root-stem>.d/roles/<role>.md`; skills at `skills/<name>/SKILL.md`, bulky references alongside. Generate: `agnt instructions --context provider/model --role ROLE`. Overlays may specialize but never weaken security, approval, verification, Git, or project rules. `SOUL.md`: communication only.

# Research

External citations: `agnt web-search` then `agnt web-fetch`; cite verified primary URLs. Review private telemetry via `agnt improve`; only sanitized, human-approved findings enter Beads. Load hidden `dev-workflow-common` only at another skill's request.
