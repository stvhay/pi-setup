# agnt command reference

`agnt` is the deterministic command surface for Pi routing, context composition, action templates, run artifacts, Beads-backed work, metrics, evals, and context-health checks. Domain logic lives in `agnt_lib`; this CLI adapts it for humans, CI, and headless callers. For the conceptual overview, see [The agnt System](../../../docs/AGNT-SYSTEM.md).

Commands are designed to compose with normal Unix idioms: stdin when no file is supplied, stdout for primary output, stderr for diagnostics, and `-o` for files/directories when needed.

`agent/bin/bd` transparently delegates to the installed Beads CLI. For `bd prime` only, it removes the exact Beads-internal `Git authority: no git operations in this context` line because repository Git authority comes from project instructions, not Beads sync mode. Other commands, output, diagnostics, and exit codes pass through unchanged.

```bash
agnt [command [args]] [subcommand ...] [filename]
```

## Discovery

- `agnt -h`
- `agnt COMMAND -h`
- `agnt tasks`
- `agnt tasks --models`

Task definitions live in `tasks/*.md` and provide model-routing hints. A task is an operational label for routing; a skill is a workflow or method.

## Research

- `agnt web-search "query" [-n N] [--category it|science|news|...]`
  - Searches via the configured backend and uses its default category unless one is explicit.
  - Prints `cat: <category>` in output.

- `agnt web-fetch URL [--max-chars N] [--raw]`
  - Fetches a URL, reports status/final URL/content type, and extracts simple readable text for HTML.

## Model orchestration

- `agnt route --task TASK [--risk low|medium|high] [--budget cheap|balanced|quality] [--context-tokens N] [--modality text|image|audio|video] [--monthly-paid-spend USD] [--ignore-history]`
  - Recommends a model, fallback models, thinking level, context policy, and whether fanout is useful. Subscription-backed models rank before metered models when capability is comparable.
  - Uses the existing task files as policy, filters by `agent/settings.json` `enabledModels` plus runtime constraints, and includes metrics hints when available. `contextPolicy: fresh` means a selected metered OpenRouter model must run through a new `subagent`, not as a root-conversation continuation.
  - For `review`, emits the approved risk-specific `reviewPolicyTargets` fanout and a deterministic monthly spend state: Terra at high thinking by default, Kimi K2.7 Code for medium-risk diversity, and Opus 5 for high-risk independent review. It counts OpenRouter, configured metered venues, and positive provider-reported spend from retired venues while excluding configured subscription targets. It uses `AGNT_REVIEW_PAID_SPEND_USD` as an operator floor, accepts an authoritative `--monthly-paid-spend` override, and keeps only subscription-backed Terra at the `$18` reserve and `$20` hard-cap thresholds. K3 is escalation-only.
  - `--ignore-history` is reserved for deterministic policy evaluation; normal routing uses outcome history.
  - Outcome history is aggregated by model family (`agent/catalog.json`) across the global consolidated store and local pending metrics; candidates whose family shows more negative than positive outcomes over at least 5 invocations are demoted with an explicit reason.

For interactive delegation, run `agnt route`, then call the Archimedes `subagent` tool with `agent` omitted and the selected target as `model`. Use its `tasks` array for parallel peers. Optional single/per-child `outputContract` values are `inline`, `artifact`, `status-only`, and `pass-no-findings`; omitted contracts remain `unknown`. The tracked observer generates one payload-free `invocationId` per child at tool start and reuses it in the projection, metric, and parent-owned result artifact. Before returning, the parent writes full final, partial, and error output under `agnt runtime-path delegated-results`; tool content/details and telemetry gain a bounded `runtime:delegated-results/...` ref plus payload-free persistence status. Failed children also expose bounded termination reason/source/effective deadline even when usable partial output exists. Projections and metrics carry matching provider, model, target, effective thinking level, objective execution outcome, and output contract. Quality evaluators receive only a bounded parent-result view plus contract and artifact persistence/content status/count, never raw refs or filesystem paths. Config-less workers use thinking `default` because Archimedes supplies no thinking override. Parallel indexes are metadata, not identity. Named-profile projections mark provider, target, and thinking unavailable, and their metrics remain skipped because Archimedes does not expose those effective values.

`maxOutputTokens` bounds one provider response, not visible final-answer length; reasoning may consume that allowance before the visible final answer. Do not derive a low token cap from requested characters. Subscription-backed one-shot calls normally omit it, while the tracked wrapper keeps the 16,384-token metered one-shot backstop. An explicit lower cap remains appropriate for a bounded experiment or known spend/risk ceiling. One-shot rejects cumulative `maxTotalTokens` and `maxCostUsd`; they cannot constrain a provider request already in flight. One-shot already has one provider turn, so omit `maxProviderRequests`. Subscription-backed agentic work also omits request/token/cost caps unless an explicit bounded experiment or runaway risk requires one.

| `outputContract` | Use | Low-failure prompt pattern |
|---|---|---|
| `inline` | Required result must be visible to parent. | Request schema-valid JSON or concise prose, with both finding/item count and character target. Keep provider allowance above visible target plus reasoning; do not add a low ad hoc cap. |
| `artifact` | Complete final response may be larger than bounded parent projection; parent persists it. | Ask child to return complete result in final response. Do not ask tool-disabled one-shot child to write a local file. |
| `status-only` | Parent needs completion state, not full findings. | Request one explicit `OK` or `ERROR` line and use lower thinking when task permits; short final text alone is not reason to lower provider allowance. |
| `pass-no-findings` | `PASS` is valid when no defect exists, but concrete findings must survive. | Request `PASS` or a small bounded finding list; never force filler when no finding exists. |

Classify failures from explicit evidence. `terminationReason=output-limit` plus `terminationSource=caller` identifies an applied caller ceiling; `wrapper` identifies the configured metered default; `provider` identifies a lower/native provider stop and may have no exact known limit. Provider/context/network failures retain their provider or process evidence and must not be relabeled from output shape. Malformed or incomplete JSON alone proves no failure source; it only makes a structured result invalid. Full partial output remains in parent-owned delegated artifacts.

- `agnt runtime-path KIND`
  - Returns bounded JSON containing safe private directory for runtime kind such as `runs` or `metrics/invocations`. Resolver uses project `.pi/<kind>` only when Git proves path ignored and untracked; otherwise it uses mode-`0700` `~/.pi/runtime/<sha256>/<kind>`. Hash keys canonical Git common directory, including linked worktrees, or canonical working directory outside Git.

- `agnt provider-circuit status [--provider PROVIDER]`
- `printf '%s' "$ERROR" | agnt provider-circuit record --provider PROVIDER`
- `agnt provider-circuit success --provider PROVIDER`
  - Tracks exact provider venues, not model families. Deterministic quota, credit, authentication, and availability errors open circuits for 30 minutes, 30 minutes, 15 minutes, and 2 minutes respectively; all TTLs have a one-hour hard cap. Successful calls close an open venue circuit, while expiry is pruned lazily.
  - Routing excludes every candidate on an open provider and reports bounded reason/expiry metadata; other providers serving the same model family remain eligible. Private mode-`0600` state is lock-serialized and atomically replaced under a mode-`0700` runtime directory. It stores only provider, reason enum, and timestamps; it never stores raw provider errors, targets, prompts, outputs, URLs, or credentials.

Metrics use `schemaVersion: 2` and are best-effort. Each invocation gets one UUID `invocationId` before execution; the ID is random and never derived from prompt, output, target, or child index. Records normalize `parentSessionId`, optional `childSessionId` for exact delegated-trace lookup, `workItem`, `provider`, `model`, `target`, `thinkingLevel`, objective `executionOutcome` (`succeeded`, `failed`, or `unavailable`), delegated `outputContract` (or `unknown`), `status` (`succeeded` or `failed`), `failureClass` (`provider`, `process`, `timeout`, or null), optional bounded `providerFailureClass`, sanitized termination reason/source/limit/observed/effective deadline, usage, duration, and bounded artifact refs. Human outcome annotations remain separate and cannot mutate execution. `recordId` remains a backward-compatible selector, and schema-v1 records without v2 fields remain loadable with execution and output contract `unknown`. When Pi/provider usage is unavailable, metrics JSON records `usageSource: "unavailable"` and `usage: null`. When usage is available but the provider reports zero/missing dollars for a known subscription-backed or OpenRouter model, `agnt` fills `usage.cost` with an OpenRouter-price opportunity-cost estimate and marks it with `usage.costSource: "openrouter-assumed"` and `usage.costEstimated: true`. This keeps subscription GPT usage comparable without routing GPT calls through OpenRouter.

Use routed unnamed `subagent` calls for peers. Set `mode: "one-shot"` for cold complete packets and use its `tasks` array for parallel dispatch. Internal eval/run workers keep the same metrics schema without exposing a second public peer command.

## Common routing flow

Interactive example:

```bash
agnt route --task research --risk medium --budget balanced
```

```json
{ "task": "<focused prompt>", "model": "<selected-provider/model>" }
```

Cold review example:

```bash
agnt route --task review --risk medium --budget balanced --fanout-size 3
```

```json
{"task":"<complete packet contents>","model":"<selected-provider/model>","mode":"one-shot","thinking":"<routed level>","limits":{"maxDurationMs":300000}}
```

For structured review findings:

```bash
agnt review validate .pi/reviews/<id>/findings.json
agnt review summary .pi/reviews/<id>/findings.json
agnt metrics annotate <recordId> --findings-file .pi/reviews/<id>/findings.json --outcome accepted
```

`agnt review` validates the tracked discovery/adjudication contract. Findings begin `unverified`; `confirmed`, `refuted`, and `unresolved` require verifier family, method, and evidence. Confidence is not part of the schema. Findings-linked metric summaries report status counts and confirmed-findings-per-dollar when cost is available.

## Prompt tooling

- `agnt prompt inventory [--kind KIND] [--paths-only]`
  - Lists tracked prompt/instruction artifacts such as `AGENTS.md`, skills, model/role supplements, action templates, and eval prompts.

## Action templates and run artifacts

- `agnt action list`
  - Lists verb-like action templates from `agent/actions/*.md`.

- `agnt action validate`
  - Validates that action templates reference existing routing tasks, skills, roles, allowed effects, and output contracts.

- `agnt action render ACTION [--target REF ...] [--bead ID] [--role ROLE] [--model TARGET] [--dry-run]`
  - Renders an action template into an invocation artifact bundle under resolved private runs directory unless `--dry-run` is supplied.

- `agnt runs create ...`
  - Creates a generic invocation/result run bundle. Optional orchestration fields include selected model/thinking, ticket metadata, ephemeral todo seed, worktree, dispatch policy, session policy, and memory policy. See [Run Artifacts](../../../docs/RUN-ARTIFACTS.md) for schema details.

- `agnt runs invoke <runtime-runs-dir>/<run-id> [--model provider/model] [--no-metrics]`
  - Reads `invocation.yaml`, invokes a worker, writes prompt/response/stderr/metrics artifacts, and updates `result.yaml`.

- `agnt runs update <runtime-runs-dir>/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--artifact PATH ...] [--follow-up ID ...] [--metrics-ref PATH] [--session-ref REF] [--approval-ref ID] [--decision-ref ID] [--health-check name=passed] [--closeout-check name=passed]`
  - Enriches `result.yaml` with evidence, artifacts, follow-up beads, metrics refs, session/transcript/memory refs, approval/decision refs, health/closeout checks, and terminal statuses.

- `agnt runs validate <runtime-runs-dir>/<run-id> [--require-followups-exist]`
  - Validates required `invocation.yaml` and `result.yaml` fields. With `--require-followups-exist`, every `result.yaml.followUps[]` id must resolve to a Beads item.

- `agnt work direct-start BEAD [--claim]`
  - Starts ordinary direct work by validating and showing the Bead, optionally claiming it only when `--claim` is explicit and the Bead is not already in progress, then idempotently linking the current Pi session.
  - One logical session belongs to one Bead. A conflicting prior link or outcome is not overwritten. After successful current Bead closeout, call `handoff_bead` without a target; sole ready non-epic work continues automatically, while several choices use one selection. `/new` is the human fallback when the tool is unavailable. Quitting and resuming may retain the same logical session.
  - Returns JSON with each stage, safe retry guidance after partial failure, and no run bundle or worktree creation.

- `agnt work direct-closeout BEAD --reason REASON`
  - Runs only after task-owned implementation changes are verified and committed and `agnt improve outcome BEAD OUTCOME` has recorded matching session ownership.
  - Refuses tracked non-Beads changes, closes the Bead idempotently, explicitly exports canonical regular issues through `bd export --readonly`, and verifies target `status`, `closed_at`, and `close_reason` parity before replacing `.beads/issues.jsonl`.
  - Stages and creates a second local commit containing only `.beads/issues.jsonl`. The shared portable-state commit preserves all legitimate exported Bead rows; unrelated untracked files remain untouched. It never pushes.
  - Returns bounded stage JSON. Failure after closure is `partial` and safe to retry; a retry repairs export, staging, or commit without discarding shared rows.

- `agnt work integrate --target-branch BRANCH --expected-head SHA --source-sha SHA [--timeout-seconds N]`
  - Consumes only exact local-integration authority already present in approved scope; command does not create or broaden approval. Run it from named target checkout.
  - Uses POSIX `fcntl.flock` on target-ref-scoped lock under Git's common directory, so linked worktrees share one semaphore. Random owner token plus opaque lock ID define ownership; lock evidence and persistent metadata omit repository paths, refs, command arguments, and content. Integration results intentionally retain approved source/target object IDs for verification. Kernel releases ownership on process death; next holder marks stale advisory metadata recovered without PID/time-based lock stealing. Timeout and cancellation fail closed; no daemon runs.
  - Clears ambient `GIT_*` overrides, pins the approved worktree, disables hooks/fsmonitor/signing/signature enforcement for helper Git calls, and rejects command-bearing custom merge/filter/branch-options configuration. Rechecks target branch, expected target HEAD, exact source commit, clean tracked/untracked status, and absence of merge state after lock acquisition. Runs one local `git merge --no-edit --no-verify`. Success requires source ancestry, same target branch, clean status, and no merge state.
  - Conflict runs only `git merge --abort` and verifies exact baseline restoration. Divergence, dirty state, timeout, cancellation, failed abort, or failed verification stops without alternate strategy. Process death or keyboard interruption releases the semaphore; a successor still must pass exact HEAD/clean-state checks, so interrupted mutation cannot silently continue. Exit `0` means integrated/already integrated; `3` means safe stop/conflict; `2` means invalid request or unavailable integration environment.
  - `git worktree lock` is not used: it prevents administrative prune/move/remove but does not serialize commands inside a worktree. Git's index/ref lockfiles protect individual writes, not the full preflight/merge/verification transaction.

- `agnt work handoff-check [BEAD] --session-id SESSION`
  - Internal preflight for tracked Bead handoff extension. It requires one linked successful session outcome and closed source Bead. Without `BEAD`, it selects sole ready non-epic work or returns bounded choices; an explicit or selected target must exist in `bd ready` before fresh-session staging or process replacement.
  - Returns bounded JSON containing source/target Bead IDs or ready choices, status, and outcome; it does not copy transcript content, stage session, or replace process itself.

- `agnt work next --json`
  - Reads Beads ready work and selects the first non-epic ready bead when available.

- `agnt work plan [BEAD_ID] --action ACTION --target REF --dry-run`
  - Builds a dry-run dispatch plan from a bead plus action template. It does not invoke a model or mutate Beads.

- `agnt work tree [BEAD_ID|--epic EPIC_ID] [--json] [--runs-dir DIR]`
  - Builds a Beads plan/dependency tree with metadata validation, blocker refs, approval refs, active run refs, and run context.

- `agnt work start [BEAD_ID] [--action ACTION] [--target REF ...] [--claim]`
  - Creates a run bundle for a bead/action and copies bead acceptance criteria into `invocation.yaml`. It records ticket metadata, dispatch policy, selected model/thinking, session/memory policy, todo seed, and worktree snapshot. It mutates Beads only when `--claim` is supplied.

- `agnt work run [BEAD_ID] [--action ACTION] [--target REF ...] [--preflight] [--claim] [--close-bead]`
  - Creates a run bundle, invokes a policy-selected worker from `invocation.yaml`, updates `result.yaml`, and closes the bead only when `--close-bead` is supplied, invocation succeeds, evidence exists, approval/decision refs are resolved, health/closeout checks pass, and follow-up ids resolve to Beads.
  - Direct `--model` overrides are rejected for work dispatch; tune routing with Beads metadata policy instead.
  - `--preflight` runs a focused operational doctor before dispatch.

- `agnt work audit [--json] [--scan-root PATH ...]`
  - Reports Beads queue counts and required-work signals in docs/run artifacts; fails when the queue is empty but required future work appears unresolved.

- `agnt work health [--json] [--strict-checkout] [--runs-dir DIR]`
  - Runs read-only rail-guard checks over run artifacts, Beads refs, approvals, decisions, follow-ups, stale sessions, dirty current/epic worktrees, raw-tool bypass markers, orphaned runs, and failed health/closeout checks.

- `agnt work maintenance due --json`
  - Reports self-improvement modes due from durable signals: Beads, git commits, runs, health/context warnings, human blockers, and a bounded count of sessions not reviewed under the current improvement policy. Telemetry failure leaves improvement-review due state unknown; incomplete discovery warns that the count may be understated.

- `agnt work maintenance create-beads --dry-run --json | --apply --json`
  - Previews or explicitly creates maintenance checkpoint Beads. Dry-run is non-mutating. `--apply` is required for live Beads creation. Simplification/refactor implementation specs are created with `approved: false`.

- `agnt work finish <runtime-runs-dir>/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--close-bead]`
  - Updates `result.yaml`; closes the invocation bead only when `--close-bead` is supplied and status is `succeeded` with evidence, reconciled follow-up ids, resolved approval/decision refs, and passing health/closeout checks.

## Approvals and ticket gateway

- `agnt approvals request --kind question|approval --target-bead ID --question TEXT --context TEXT --option TEXT ... [--selection-mode single|multi] --preview-* ...`
  - Creates a durable Beads decision/approval record, adds a blocking dependency to the target bead, and records approval/decision refs in the requesting run when supplied. Questions require selection mode and record that typed custom responses are available.

- `agnt approvals resolve DECISION_ID --outcome approved|answered|rejected|cancelled|timed-out [--answer TEXT] [--structured-answer] [--selected-option TEXT ...] [--custom-input TEXT]`
  - Records the human outcome and public-safe UI resolver kind in Beads, never the private Pi session or requesting-run ID. Answered questions may persist predefined selections and typed input separately while retaining a readable answer summary; `--structured-answer` preserves an explicit empty multi-selection. Structured question fields cannot approve an action. Approved/answered decisions close the decision bead; rejected/cancelled/timed-out decisions keep visible blockers.

- `agnt gateway --payload JSON`
  - Executes strict ticket-gateway operations (`list`, `show`, `tree`, `create_draft`) for Pi extensions. Payloads are enum-based and reject shell-like/raw-command fields. Use dedicated `ticket_question`, `ticket_approval`, and `ticket_decision_resolve` tools for human decisions.

## Langfuse evaluator configuration

- `agnt langfuse check [--quiet] [--manifest PATH]`
  - Compares tracked evaluator and live-observation rule definitions with configured Langfuse project. Read-only; exits `1` on drift and `2` when configuration cannot be checked.
- `agnt langfuse apply [--quiet] [--manifest PATH]`
  - Creates missing evaluator versions and creates or updates managed rules. It never deletes unmanaged Langfuse resources.

Definitions live in `agent/langfuse/evaluators.json`. Credentials come from `LANGFUSE_*` variables or private `agent/pi-langfuse/config.json`.

## Operational health

- `agnt doctor [--json] [--strict] [--check CHECK ...] [--skip CHECK ...]`
  - Checks local Pi/agnt operational readiness: core binaries, Python, git root, Beads, Node LTS policy, provider env vars, and core config parsing.
  - Reports JSON with check status, evidence, redacted env-var presence, warnings, and suggested actions.
  - `--strict` exits nonzero when required checks fail. The doctor is read-only and never edits shell startup files.
  - After repeated tool, provider, or environment failures, run `agnt doctor` and fix the environment instead of retrying blindly.

- `agnt doctor node [--json]`
  - Runs the Node-focused check. It detects the active `node`, Node major, nvm/fnm/asdf/Nix/Homebrew hints, and suggests LTS remediation.
  - The doctor is read-only. It never edits home shell files; suggestions respect conventions such as `~/.local/etc/profile.d/`, chezmoi/yadm, and Nix/Home Manager.

## Context health

- `agnt context-health [--strict] [--max-skill-lines N] [--overlap-threshold N] [--skill-discovery-limit N] [--skill-discovery-warning-remaining N]`
  - Checks root/overlay guidance, routing tasks, and all loadable skill Markdown for stale helpers and gate-weakening phrases.
  - Fails on unsupported multiline skill descriptions or discovery metadata above the default 8,000-character budget.
  - Warns at or below the configurable remaining-character threshold (default 1,000), reporting used, limit, remaining, threshold, and the five largest skill contributors.
  - Also warns on oversized unallowlisted skills and overlapping skill descriptions.
  - `--strict` exits nonzero when failures are found; warnings remain entropy signals.

## Private improvement review

- `agnt improve link BEAD [--json]`
  - Idempotently links the current private Pi session to one exact public work-item ID, preferring canonical `PI_SESSION_ID` and falling back to the `PI_SESSION_FILE` stem. Existing canonical link/outcome ownership for another Bead fails closed with `handoff_bead` recovery and a `/new` human fallback instead of being overwritten. `agnt work direct-start` normally handles this for interactive work.
- `agnt improve outcome BEAD success|partial|failure|unclear [--json]`
  - Idempotently backfills the same-Bead work-item link and records an explicit human final session outcome; run at interactive closeout. Scans keep objective execution and sampled apparent judgment separate, prefer only explicit outcomes whose Bead metadata matches session correlation, and otherwise prevent failed or unavailable execution from being promoted by a positive apparent score. Historical owner mismatches become count-only `mismatched-work-item-outcome` capture gaps.
- `agnt improve scan [--since ISO] [--until ISO] [--limit N] [--max-traces N] [--recheck] [--dry-run] [--json]`
  - Reads up to `--max-traces` traces (default 500) and writes a schema-2 private packet under `~/.pi/improvement/`; `--dry-run` writes nothing. A fixed five-minute settlement lag excludes active ingestion. Discovery reads through a bounded five-minute lookahead so a child completed before the watermark can still join its later parent projection; only traces at or before the watermark enter root selection. The private packet records requested end, watermark, and read cutoff; pass its `scan.until` back as `--until` to replay the settled cohort. Safe schema-1 output reports only lag/exclusion state and count-only discovery/classification health, never packet path or private timestamps.
  - Exact discovered agentic child sessions are excluded before root eligibility, review-score coverage, and `--limit` selection. Projection observations fetched for classification are cached for selected roots. Incomplete discovery, truncated projection observations, and malformed declarations remain lower bounds rather than guessed roots or children. Selected roots remain capped at 20 traces and 500 observations per trace.
  - Private features report distinct execution/apparent/final outcomes, allowlisted error taxonomy, and existing projection IDs plus timing. Required generation usage dimensions are `input`, `cacheRead`, and `output`: present zero is valid; a missing, Boolean, negative, non-finite, or fractional value makes only its token aggregate null and adds `missing-usage`. Tool payload normalization remains downstream and never copies payloads. Private packets also project promoted-finding matches; safe output contains no raw prompts, tool I/O, IDs, paths, or projection timing.
- `agnt improve review REPORT DECISIONS [--apply] [--json]`
  - Validates private review decisions. `--apply` writes idempotent private session markers and updates matched post-change monitoring. Five reviewed matches validate a finding; explicit recurrence uses a new finding's optional `relatedFindingId`. Monitoring remains private, and any recurrent public work still uses `promote` with exact human approval. Preview is default.
- `agnt improve promote REPORT DECISIONS --finding ID [--apply] [--approval ID] [--json]`
  - Renders an allowlisted public-safe Bead preview. `--apply` requires durable approval matching the exact preview.

Private telemetry, IDs, excerpts, URLs, user content, and absolute paths stay out of committed Beads.

## Knowledge graphs

- `agnt graphify [ARGS...]`
  - Runs the Graphify CLI (`graphify`) if installed, otherwise falls back to `uv tool run --from graphifyy graphify`.
  - Never installs project-local Graphify refresh hooks implicitly.
  - `agnt graphify hook install|status|uninstall` passes through Graphify's native hook manager; install/uninstall requires user approval in agent workflows.
  - The tracked `graphify` Pi skill lives at `agent/skills/graphify/SKILL.md` and provides `/graphify` workflow guidance.

## Evals

- `agnt eval list`
  - Lists eval definitions under `agent/evals/*/eval.json`.

- `agnt eval run EVAL_ID [--dry-run] [--models provider/model[,provider/model...]] [-o DIR]`
  - Runs a filesystem-defined eval and writes `result.json` plus any model outputs under `.pi/eval-runs/<timestamp>-<eval>/` by default.
  - Route evals call `agnt route`; instruction evals call `agnt instructions`; invoke evals use the internal headless worker and capture metrics automatically when not dry-run.
  - Invoke evals may set `skill` to a path relative to `eval.json`; its contents are embedded before the scenario for cold skill-behavior checks. Assertions support `nonEmptyOutput`, `contains`, and `notContains`.

## Metrics

- `agnt metrics status [--metrics-dir DIR]`
  - Prints pending raw metric count and aggregate totals as JSON.

- `agnt metrics annotate [selector|latest] [--outcome OUTCOME] [--risk-category LABEL] [--thinking-level LEVEL] [--human-override|--no-human-override] [--fallback-used|--no-fallback-used] [--notes TEXT]`
  - Appends annotation under resolved private `metrics` directory without mutating raw metric files.
  - Selectors may be `latest`, a `recordId`, a source file path, or a metrics filename basename.
  - Valid outcomes: `unknown`, `accepted`, `rejected`, `verified-pass`, `verified-fail`, `escalated`.

- `agnt metrics consolidate [--metrics-dir DIR] [--output FILE] [--stage] [--keep-raw]`
  - Appends one compact commit-level JSON line to the global runtime store `~/.pi/metrics/agent-invocations.jsonl` by default (`AGNT_METRICS_OUTPUT` or `--output` override). The store is untracked telemetry shared across projects; it feeds `agnt route` outcome hints. The auditable self-improvement record is the git history of policy files (tasks, catalog, model overlays), not the telemetry itself.
  - Applies annotations before summarizing/compacting records.
  - Moves consumed raw metrics to resolved private `metrics/consumed/<timestamp>/` unless `--keep-raw` is used.

- `agnt metrics reset [--metrics-dir DIR]`
  - Deletes pending raw metrics without appending an aggregate.

- `agnt metrics prune [--consumed-dir DIR]`
  - Deletes consumed raw metrics.

To consolidate metrics automatically before commits, install a local hook that runs `agnt metrics consolidate`. This repository does not currently ship a tracked `.githooks` hook; manual consolidation is the portable default.

## Instruction context

- `agnt instructions [ROOT.md] [--context PROVIDER/MODEL] [--role ROLE] [--roles] [--sources] [--check] [--no-project] [--project]`
  - With no `ROOT.md`, generates layered instructions from global `~/.pi/agent/AGENTS.md`, global model/role supplements, and discovered project instruction files from git root to current directory (`AGENTS.md`, `AGENT.md`, `CLAUDE.md`). This is the normal peer-prompt path.
  - With explicit `ROOT.md`, generates only that package unless `--project` is supplied; use this for package checks and special cases.
  - Model files first use catalog family overlays when available, for example `AGENTS.d/models/gpt-5.6-sol.md` for that family.
  - Provider/model-specific files use slash-style paths, for example `AGENTS.d/models/openrouter/minimax/minimax-m3.md`.
  - Loads model files from least to most specific: family overlay first, then provider/model overlays such as `openrouter.md` and `openrouter/minimax/minimax-m3.md`.
  - Uses append-only concatenation. Prefer moving optional context into role/model files over patching root instructions.
  - `--roles` lists available global/project role files and compact metadata; `--check` validates package structure and flags suspicious safety-gate weakening phrases.

## Workflow artifacts

- `agnt plans-dir`
  - Prints and creates the active plans directory.
  - Default: `<git-root>/.pi/plans` or `$PWD/.pi/plans` outside git.
  - `PI_PLANS_DIR` overrides.

## Supporting commands

Some implementation-specific scripts remain in this directory, but agent-facing instructions should prefer `agnt` unless they intentionally need a lower-level helper. The `agnt` executable is a front controller; command implementation code lives in importable `agnt_lib/` modules.
