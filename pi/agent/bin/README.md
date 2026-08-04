# agnt command reference

`agnt` is the primary command surface for Pi orchestration helpers: routing, peer invocation, context composition, action templates, run artifacts, Beads-backed work, the project-local runner service, metrics, evals, and context-health checks. For the conceptual overview, see [The agnt System](../../../docs/AGNT-SYSTEM.md); for service lifecycle and API details, see [Project-Local Runner Service](../../../docs/RUNNER-SERVICE.md).

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

- `agnt web-search "query" [-n N] [--category auto|default|it|science|news]`
  - Searches via the configured backend.
  - Prints `cat: <category>` in output.

- `agnt web-fetch URL [--max-chars N] [--raw]`
  - Fetches a URL, reports status/final URL/content type, and extracts simple readable text for HTML.

## Model orchestration

- `agnt invoke --list [TASK]`
  - Lists preferred/qualified models for one task or all tasks.

- `agnt route --task TASK [--risk low|medium|high] [--budget cheap|balanced|quality] [--context-tokens N] [--modality text|image|audio|video] [--local-ok] [--monthly-paid-spend USD]`
  - Recommends a model, fallback models, thinking level, context policy, and whether fanout is useful. Subscription-backed models rank before metered models when capability is comparable.
  - Uses the existing task files as policy, filters by `agent/settings.json` `enabledModels` plus runtime constraints, and includes metrics hints when available. `contextPolicy: fresh` means the selected Olla/OpenRouter model must run through a new `subagent` or `agnt invoke` worker, not as a root-conversation continuation.
  - For `review`, emits a Codex-first risk-specific `reviewPolicyTargets` fanout and a deterministic monthly spend state. It counts OpenRouter plus catalog venues marked `billingClass: metered`, while excluding local and subscription-backed GPT opportunity cost. It uses `AGNT_REVIEW_PAID_SPEND_USD` as an operator floor, accepts an authoritative `--monthly-paid-spend` override, and keeps only subscription-backed Codex plus local Gemma at the `$18` reserve and `$20` hard-cap thresholds. Kimi is not an automatic review candidate; K3 is escalation-only.
  - Outcome history is aggregated by model family (`agent/catalog.json`) across the global consolidated store and local pending metrics; candidates whose family shows more negative than positive outcomes over at least 5 invocations are demoted with an explicit reason. Evidence gathered on one venue applies to every venue of the same weights.
  - `agnt recommend` is an alias.

For interactive delegation, run `agnt route`, then call the Archimedes `subagent` tool with `agent` omitted and the selected target as `model`. Use its `tasks` array for parallel peers. The tracked observer generates one payload-free `invocationId` per child at tool start, reuses it in the completed projection and local metric, and records unnamed-peer usage under the resolved private `metrics/invocations` directory without storing prompt or response bodies. Parallel indexes are metadata, not identity. Named-profile metrics are skipped because Archimedes does not expose their final provider.

- `agnt runtime-path KIND`
  - Returns bounded JSON containing safe private directory for runtime kind such as `runs` or `metrics/invocations`. Resolver uses project `.pi/<kind>` only when Git proves path ignored and untracked; otherwise it uses mode-`0700` `~/.pi/runtime/<sha256>/<kind>`. Hash keys canonical Git common directory, including linked worktrees, or canonical working directory outside Git.

- `agnt invoke [--one-shot] [--timeout-seconds N] [--task TASK] [--risk-category LABEL] [--thinking-level LEVEL] [--outcome OUTCOME] [--human-override] [--fallback-used] [--preflight] [--no-metrics] [--metrics-dir DIR] provider/model [filename]`
  - Runs one ephemeral Pi peer. Metrics are on by default, so `agnt` uses `pi --mode json --no-session`, preserves normal stdout, and writes raw token/cost/wall-clock metrics to `DIR` or resolved private `metrics/invocations` directory.
  - `--one-shot` also disables tools, skills, context-file discovery, and prompt templates, supplies a compact read-only system prompt, and defaults to a 180-second subprocess timeout. Use `--timeout-seconds` to override it. Use one-shot only when `filename` embeds the complete task context; it prevents agentic tool loops from multiplying provider requests.
  - Metrics include routing fields when supplied plus `invocationMode` and counted `providerRequests`: task, risk category, thinking level, context size, estimated input tokens, outcome, human override, and fallback-used flags.
  - Use `--no-metrics` to use the older `pi --print --no-session` path and skip metrics.
  - Reads prompt from `filename`, `@filename`, argv text, or stdin.
  - `--preflight` runs a focused `agnt doctor` check before calling the model; failures abort and warnings are printed to stderr.

- `agnt invoke --fanout [--task TASK] [--no-metrics] [-o DIR] [prompt-or-file]`
  - Runs the task's preferred models and writes output artifacts to `DIR`.
  - With default metrics, writes `<model>.metrics.json` for each peer, `metrics.summary.json`, and central raw invocation metrics.

- `agnt invoke --fanout [--no-metrics] [-o DIR] provider/model [filename]`
  - Runs one model and writes output artifacts to `DIR`.

- `agnt invoke --fanout [--no-metrics] [-o DIR] provider/model filename [provider/model filename ...]`
  - Runs multiple provider/model + prompt-file pairs in parallel.

Metrics use `schemaVersion: 2` and are best-effort. Each invocation gets one UUID `invocationId` before execution; the ID is random and never derived from prompt, output, target, or child index. Records normalize `parentSessionId`, `workItem`, `provider`, `model`, `target`, `status` (`succeeded` or `failed`), `failureClass` (`provider`, `process`, `timeout`, or null), `usage`, `durationMs`, and up to 16 relative `artifactRefs` of at most 256 characters. `recordId` remains a backward-compatible selector, and schema-v1 records without v2 fields remain loadable. When Pi/provider usage is unavailable, metrics JSON records `usageSource: "unavailable"` and `usage: null`. Catalog venues marked `billingClass: free` stay at zero cost with `usage.costSource: "catalog-free"`. Otherwise, when usage is available but the provider reports zero/missing dollars for a known subscription-backed or OpenRouter model, `agnt` fills `usage.cost` with an OpenRouter-price opportunity-cost estimate and marks it with `usage.costSource: "openrouter-assumed"` and `usage.costEstimated: true`. This keeps subscription GPT usage comparable without routing GPT calls through OpenRouter.

Local models keep cash/API `usage.cost.total` at zero with `usage.costSource: "local-free"`. For known local equivalents, metrics add separate `usage.opportunityCost` using metered family rates rather than pretending local inference spent API dollars. Local calls also get a rough marginal GPU electricity estimate in `usage.localCompute`, using `AGNT_LOCAL_GPU_WATTS` when set. Otherwise `olla-local/*` defaults to an assumed remote Olla marginal GPU draw of 208W, and `AGNT_USE_NVIDIA_SMI=1` opts into sampling `nvidia-smi` on the current host. Electricity price uses `AGNT_ELECTRICITY_USD_PER_KWH` or default `$0.1304/kWh`. Raw metrics live under resolved private runtime directory.

Use routed unnamed `subagent` calls for interactive peers. Use `agnt invoke --one-shot` for cold complete packets and `agnt invoke` for headless or artifact-backed execution. Both paths capture compatible metrics. The old `pi-peer`/`pi-fanout` wrappers remain removed.

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
agnt invoke --one-shot --task review --risk-category medium <selected-provider/model> complete-packet.md
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

- `agnt prompt import-pattern-note --name NAME --source-url URL --source-license LICENSE --pattern TEXT --rewrite TEXT [--notes TEXT]`
  - Writes a provenance note under `agent/prompt-patterns/` without copying external prompt text.
  - Use this for GPL/community prompt repositories: record the pattern and an original Pi-specific rewrite, not the source prompt.

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
  - Returns JSON with each stage, safe retry guidance after partial failure, and no run bundle, runner, or worktree creation.

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

- `agnt work daemon start|stop|status --json`
  - Manages the project-local runner service lifecycle. `start` launches one loopback service for the project root; `stop --drain` asks it to finish active work and stop accepting new work; `stop --force` is explicit operator-only shutdown.

- `agnt work runner status|pause|resume|tick [--json]`
  - Calls the project-local runner service REST API. If no service is running, these commands return a JSON error suggesting `agnt work daemon start --json`. `tick --dry-run --json` explains planned dispatch/blocker/maintenance actions without mutation.

- `agnt work audit [--json] [--scan-root PATH ...]`
  - Reports Beads queue counts and required-work signals in docs/run artifacts; fails when the queue is empty but required future work appears unresolved.

- `agnt work health [--json] [--strict-checkout] [--runs-dir DIR]`
  - Runs read-only rail-guard checks over run artifacts, Beads refs, approvals, decisions, follow-ups, stale sessions, stale runner locks, dirty current/epic worktrees, raw-tool bypass markers, orphaned runs, and failed health/closeout checks.

- `agnt work maintenance due --json`
  - Reports self-improvement modes due from durable signals: Beads, git commits, runs, health/context warnings, human blockers, and recorded session volume.

- `agnt work maintenance create-beads --dry-run --json | --apply --json`
  - Previews or explicitly creates maintenance checkpoint Beads. Dry-run is non-mutating. `--apply` is required for live Beads creation. Simplification/refactor implementation specs are created with `approved: false`.

- `agnt work finish <runtime-runs-dir>/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--close-bead]`
  - Updates `result.yaml`; closes the invocation bead only when `--close-bead` is supplied and status is `succeeded` with evidence, reconciled follow-up ids, resolved approval/decision refs, and passing health/closeout checks.

## Approvals and ticket gateway

- `agnt approvals request --target-bead ID --question TEXT --context TEXT --option TEXT ... --preview-* ...`
  - Creates a durable Beads decision/approval record, adds a blocking dependency to the target bead, and records approval/decision refs in the requesting run when supplied.

- `agnt approvals resolve DECISION_ID --outcome approved|answered|rejected|cancelled|timed-out [--note TEXT]`
  - Records the human outcome and public-safe UI resolver kind in Beads, never the private Pi session or requesting-run ID. Run refs remain in private run artifacts. Approved/answered decisions close the decision bead; rejected/cancelled/timed-out decisions keep visible blockers.

- `agnt gateway --payload-json JSON`
  - Executes strict ticket-gateway operations (`list`, `show`, `tree`, `create_draft`, `request_approval`, `resolve_blocker`, `runner_status`) for Pi extensions. Payloads are enum-based and reject shell-like/raw-command fields.
  - `runner_status` is the stable model-facing service status surface. It returns absent-service state when no service is running, and redacted running/paused/draining state, leases, active work, budget, model/thinking, context, and cost when connected.

## Langfuse evaluator configuration

- `agnt langfuse check [--quiet] [--manifest PATH]`
  - Compares tracked evaluator and live-observation rule definitions with configured Langfuse project. Read-only; exits `1` on drift and `2` when configuration cannot be checked.
- `agnt langfuse apply [--quiet] [--manifest PATH]`
  - Creates missing evaluator versions and creates or updates managed rules. It never deletes unmanaged Langfuse resources.

Definitions live in `agent/langfuse/evaluators.json`. Credentials come from `LANGFUSE_*` variables or private `agent/pi-langfuse/config.json`.

## Operational health

- `agnt doctor [--json] [--strict] [--profile PROFILE] [--check CHECK ...] [--skip CHECK ...]`
  - Checks local Pi/agnt operational readiness: core binaries, Python, git root, Beads, Node LTS policy, provider env vars, and core config parsing.
  - `--profile orchestrator-startup` adds the strict opt-in gate used before background runner dispatch: `SEARXNG_URL` and a Beads workspace are required, provider env warnings are scoped to configured/enabled providers, and background dispatch is allowed only with zero failures and zero unacknowledged warnings. Normal direct Pi sessions do not run this profile.
  - Reports JSON with check status, evidence, redacted env-var presence, acknowledged warnings, and suggested actions.
  - Non-secret intent acknowledgements may live in project `.pi/doctor-intent.json` or global `~/.pi/agent/doctor-intent.json`, for example `{ "intentionallyAbsentEnv": { "ANTHROPIC_API_KEY": "not used" } }`.
  - `--strict` exits nonzero when required checks fail; with `orchestrator-startup`, it also exits nonzero for unacknowledged warnings. The doctor is read-only and never edits shell startup files.
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
  - Idempotently links the current private Pi session to an exact public work-item ID, using `PI_SESSION_FILE` or the exact `PI_SESSION_ID` fallback. `agnt work direct-start` normally handles this for interactive work; runner sessions link automatically.
- `agnt improve outcome BEAD success|partial|failure|unclear [--json]`
  - Idempotently backfills the work-item link and records an explicit final session outcome; run at interactive closeout. Scans prefer this score over sampled evaluator output.
- `agnt improve scan [--since ISO] [--limit N] [--max-traces N] [--recheck] [--dry-run] [--json]`
  - Reads up to `--max-traces` traces (default 500) from the bounded Langfuse window and writes a schema-2 private packet under `~/.pi/improvement/`; `--dry-run` writes nothing. The safe command summary remains schema 1, review decisions remain schema 1 with policy `v1`, and historical schema-1 packets remain reviewable. `traceDiscovery` reports the cap, API total when valid, scanned/attributable/unattributed lower bounds, completeness, and continuation state (`max-traces` or `non-advancing-page` when truncated). Selected sessions remain capped at 20 traces and 500 observations per trace with capture-gap markers. The exact `pi-langfuse-1.5.7-dual-null-dual-26` TOOL fingerprint produces null input/output byte aggregates and `payloadByteMetadata.toolIo` provenance; missing nonfingerprint metadata nulls only its affected side. Non-null payload-byte values are bounded-preview estimates, not raw payload sizes. Raw Langfuse records remain unchanged, and no tool payload is copied into the packet. Projected outcomes and payload-free tool-error signals join through the private session ID.
- `agnt improve review REPORT DECISIONS [--apply] [--json]`
  - Validates private review decisions. `--apply` writes idempotent private session markers; preview is default.
- `agnt improve promote REPORT DECISIONS --finding ID [--apply] [--approval ID] [--json]`
  - Renders an allowlisted public-safe Bead preview. `--apply` requires durable approval matching the exact preview.

Private telemetry, IDs, excerpts, URLs, user content, and absolute paths stay out of committed Beads.

## Knowledge graphs

- `agnt graphify [ARGS...]`
  - Runs the Graphify CLI (`graphify`) if installed, otherwise falls back to `uv tool run --from graphifyy graphify`.
  - Never installs project-local Graphify refresh hooks implicitly.
  - `agnt graphify hooks install|status|uninstall [--repo PATH]` explicitly manages best-effort `post-commit`, `post-merge`, and `post-checkout` hooks for a project; install/uninstall requires user approval in agent workflows.
  - The tracked `graphify` Pi skill lives at `agent/skills/graphify/SKILL.md` and provides `/graphify` workflow guidance.

## Evals

- `agnt eval list`
  - Lists eval definitions under `agent/evals/*/eval.json`.

- `agnt eval run EVAL_ID [--dry-run] [--models provider/model[,provider/model...]] [-o DIR]`
  - Runs a filesystem-defined eval and writes `result.json` plus any model outputs under `.pi/eval-runs/<timestamp>-<eval>/` by default.
  - Route evals call `agnt route`; instruction evals call `agnt instructions`; invoke evals call the same invocation path as `agnt invoke`, so metrics are captured automatically when not dry-run.
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
  - Model files first use catalog family overlays when available, for example `AGENTS.d/models/gemma4-31b.md` applies across Ollama, Olla, and OpenRouter venues for that family.
  - Provider/model-specific files use slash-style paths, for example `AGENTS.d/models/olla-cloud/gemma-4-31b-it.md`.
  - Loads model files from least to most specific: family overlay first, then provider/model overlays such as `olla-cloud.md` and `olla-cloud/gemma-4-31b-it.md`.
  - Uses append-only concatenation. Prefer moving optional context into role/model files over patching root instructions.
  - `--roles` lists available global/project role files and compact metadata; `--check` validates package structure and flags suspicious safety-gate weakening phrases.

- `agnt soul [SOUL.md] [--check]`
  - Emits or validates communication preferences from `SOUL.md` plus optional `SOUL.d/**/*.md` supplements.
  - `SOUL.md` affects style only; it must not weaken safety gates.

## Workflow artifacts

- `agnt plans-dir`
  - Prints and creates the active plans directory.
  - Default: `<git-root>/.pi/plans` or `$PWD/.pi/plans` outside git.
  - `PI_PLANS_DIR` overrides.

## Supporting commands

Some implementation-specific scripts remain in this directory, but agent-facing instructions should prefer `agnt` unless they intentionally need a lower-level helper. The `agnt` executable is a front controller; command implementation code lives in importable `agnt_lib/` modules.
