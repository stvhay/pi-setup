# agnt command reference

`agnt` is the primary command surface for Pi orchestration helpers: routing, peer invocation, context composition, action templates, run artifacts, Beads-backed work, the project-local runner service, metrics, evals, and context-health checks. For the conceptual overview, see [The agnt System](../../../docs/AGNT-SYSTEM.md); for service lifecycle and API details, see [Project-Local Runner Service](../../../docs/RUNNER-SERVICE.md).

Commands are designed to compose with normal Unix idioms: stdin when no file is supplied, stdout for primary output, stderr for diagnostics, and `-o` for files/directories when needed.

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
  - Recommends a model, fallback models, thinking level, and whether fanout is useful.
  - Uses the existing task files as policy, filters by `agent/settings.json` `enabledModels` plus runtime constraints, and includes metrics hints when available.
  - For `review`, emits a risk-specific `reviewPolicyTargets` fanout and a deterministic monthly spend state. It counts OpenRouter plus catalog venues marked `billingClass: metered`, while excluding local and subscription-backed GPT opportunity cost. It uses `AGNT_REVIEW_PAID_SPEND_USD` as an operator floor, accepts an authoritative `--monthly-paid-spend` override, removes Kimi at the `$18` reserve threshold, and routes only to local Gemma at the `$20` hard cap. K3 is not an automatic review candidate.
  - Outcome history is aggregated by model family (`agent/catalog.json`) across the global consolidated store and local pending metrics; candidates whose family shows more negative than positive outcomes over at least 5 invocations are demoted with an explicit reason. Evidence gathered on one venue applies to every venue of the same weights.
  - `agnt recommend` is an alias.

- `agnt invoke [--one-shot] [--timeout-seconds N] [--task TASK] [--risk-category LABEL] [--thinking-level LEVEL] [--outcome OUTCOME] [--human-override] [--fallback-used] [--preflight] [--no-metrics] [--metrics-dir DIR] provider/model [filename]`
  - Runs one ephemeral Pi peer. Metrics are on by default, so `agnt` uses `pi --mode json --no-session`, preserves normal stdout, and writes raw token/cost/wall-clock metrics to `DIR` or `<git-root>/.pi/metrics/invocations/`.
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

Metrics use `schemaVersion: 1` and are best-effort: when Pi/provider usage is unavailable, metrics JSON records `usageSource: "unavailable"` and `usage: null`. New records include a stable `recordId`; old records remain loadable. When usage is available but the provider reports zero/missing dollars for a known subscription-backed or OpenRouter model, `agnt` fills `usage.cost` with an OpenRouter-price opportunity-cost estimate and marks it with `usage.costSource: "openrouter-assumed"` and `usage.costEstimated: true`. This keeps subscription GPT usage comparable without routing GPT calls through OpenRouter.

Local models keep cash/API `usage.cost.total` at zero with `usage.costSource: "local-free"`. For known local equivalents, metrics add a separate `usage.opportunityCost` using an OpenRouter proxy model rather than pretending that local inference spent API dollars. Local calls also get a rough marginal GPU electricity estimate in `usage.localCompute`, using `AGNT_LOCAL_GPU_WATTS` when set. Otherwise `olla-local/*` defaults to an assumed remote Olla marginal GPU draw of 208W, `ollama/*` defaults to an assumed local workstation draw of 34.2W, and `AGNT_USE_NVIDIA_SMI=1` opts into sampling `nvidia-smi` on the current host. Electricity price uses `AGNT_ELECTRICITY_USD_PER_KWH` or the default `$0.1304/kWh`. Raw metrics live under `.pi/metrics/` and are ignored by git.

Use `agnt invoke` and `agnt invoke --fanout` for all peer calls; they capture metrics by default. The old `pi-peer`/`pi-fanout` wrappers were removed because they bypassed metrics capture.

## Common routing flow

Example:

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

- `agnt prompt eval EVAL_ID [--dry-run] [--models provider/model[,provider/model...]] [-o DIR]`
  - Convenience wrapper around `agnt eval run` for prompt-related evals.

- `agnt prompt import-pattern-note --name NAME --source-url URL --source-license LICENSE --pattern TEXT --rewrite TEXT [--notes TEXT]`
  - Writes a provenance note under `agent/prompt-patterns/` without copying external prompt text.
  - Use this for GPL/community prompt repositories: record the pattern and an original Pi-specific rewrite, not the source prompt.

## Action templates and run artifacts

- `agnt action list`
  - Lists verb-like action templates from `agent/actions/*.md`.

- `agnt action validate`
  - Validates that action templates reference existing routing tasks, skills, roles, allowed effects, and output contracts.

- `agnt action render ACTION [--target REF ...] [--bead ID] [--role ROLE] [--model TARGET] [--dry-run]`
  - Renders an action template into an invocation artifact bundle under `.pi/runs/` unless `--dry-run` is supplied.

- `agnt runs create ...`
  - Creates a generic invocation/result run bundle. Optional orchestration fields include selected model/thinking, ticket metadata, ephemeral todo seed, worktree, dispatch policy, session policy, and memory policy. See [Run Artifacts](../../../docs/RUN-ARTIFACTS.md) for schema details.

- `agnt runs invoke .pi/runs/<run-id> [--model provider/model] [--no-metrics]`
  - Reads `invocation.yaml`, invokes a worker, writes prompt/response/stderr/metrics artifacts, and updates `result.yaml`.

- `agnt runs update .pi/runs/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--artifact PATH ...] [--follow-up ID ...] [--metrics-ref PATH] [--session-ref REF] [--approval-ref ID] [--decision-ref ID] [--health-check name=passed] [--closeout-check name=passed]`
  - Enriches `result.yaml` with evidence, artifacts, follow-up beads, metrics refs, session/transcript/memory refs, approval/decision refs, health/closeout checks, and terminal statuses.

- `agnt runs validate .pi/runs/<run-id> [--require-followups-exist]`
  - Validates required `invocation.yaml` and `result.yaml` fields. With `--require-followups-exist`, every `result.yaml.followUps[]` id must resolve to a Beads item.

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

- `agnt work finish .pi/runs/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--close-bead]`
  - Updates `result.yaml`; closes the invocation bead only when `--close-bead` is supplied and status is `succeeded` with evidence, reconciled follow-up ids, resolved approval/decision refs, and passing health/closeout checks.

## Approvals and ticket gateway

- `agnt approvals request --target-bead ID --question TEXT --context TEXT --option TEXT ... --preview-* ...`
  - Creates a durable Beads decision/approval record, adds a blocking dependency to the target bead, and records approval/decision refs in the requesting run when supplied.

- `agnt approvals resolve DECISION_ID --outcome approved|answered|rejected|cancelled|timed-out [--note TEXT]`
  - Records the human outcome in Beads metadata/notes and updates run refs. Approved/answered decisions close the decision bead; rejected/cancelled/timed-out decisions keep visible blockers.

- `agnt gateway --payload-json JSON`
  - Executes strict ticket-gateway operations (`list`, `show`, `tree`, `create_draft`, `request_approval`, `resolve_blocker`, `runner_status`) for Pi extensions. Payloads are enum-based and reject shell-like/raw-command fields.
  - `runner_status` is the stable model-facing service status surface. It returns absent-service state when no service is running, and redacted running/paused/draining state, leases, active work, budget, model/thinking, context, and cost when connected.

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

- `agnt context-health [--strict]`
  - Checks active Pi context for stale helper names, gate-weakening phrases, oversized unallowlisted skills, and overlapping skill descriptions.
  - `--strict` exits nonzero when failures are found; warnings are reported for entropy signals.

## Lessons

- `agnt lessons capture --summary TEXT [--kind KIND] [--area AREA] [--evidence TEXT] [--tag TAG ...] [--payload-json JSON] [--out FILE]`
  - Appends one redacted JSONL lesson to the local inbox. Default: `~/.pi/lessons/inbox.jsonl` or `AGNT_LESSONS_INBOX`.
  - Adds UUID, UTC date, hostname, project name, and project directory provenance.

- `agnt lessons inbox [--file FILE] [--json]`
  - Prints the local lessons inbox as JSONL or a JSON envelope.

- `agnt lessons push [--url URL] [--file FILE] [--archive-dir DIR] [--dry-run]`
  - Posts local JSONL to `${AGNT_LESSONS_URL}/lesson` or the supplied `--url`.
  - Archives and clears pushed records only after a successful server response; preserves the inbox on failure.

- `agnt lessons pull [--url URL] [--status STATUS] [--since ISO] [--project NAME] [--hostname NAME] [--limit N] [-o FILE]`
  - Fetches `${AGNT_LESSONS_URL}/lessons` as JSONL. The current production server is `https://pi-lessons.st5ve.com`.

- `agnt lessons triage [--file FILE] [--status new] [--draft-beads] [--create-beads]`
  - Drafts Beads follow-up work from lessons. It creates Beads only with explicit `--create-beads`.

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

## Metrics

- `agnt metrics status [--metrics-dir DIR]`
  - Prints pending raw metric count and aggregate totals as JSON.

- `agnt metrics annotate [selector|latest] [--outcome OUTCOME] [--risk-category LABEL] [--thinking-level LEVEL] [--human-override|--no-human-override] [--fallback-used|--no-fallback-used] [--notes TEXT]`
  - Appends an annotation to `.pi/metrics/annotations.jsonl` without mutating raw metric files.
  - Selectors may be `latest`, a `recordId`, a source file path, or a metrics filename basename.
  - Valid outcomes: `unknown`, `accepted`, `rejected`, `verified-pass`, `verified-fail`, `escalated`.

- `agnt metrics consolidate [--metrics-dir DIR] [--output FILE] [--stage] [--keep-raw]`
  - Appends one compact commit-level JSON line to the global runtime store `~/.pi/metrics/agent-invocations.jsonl` by default (`AGNT_METRICS_OUTPUT` or `--output` override). The store is untracked telemetry shared across projects; it feeds `agnt route` outcome hints. The auditable self-improvement record is the git history of policy files (tasks, catalog, model overlays), not the telemetry itself.
  - Applies annotations before summarizing/compacting records.
  - Moves consumed raw metrics to `.pi/metrics/consumed/<timestamp>/` unless `--keep-raw` is used.

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
  - Provider/model-specific files use slash-style paths, for example `AGENTS.d/models/openrouter-localish/google/gemma-4-31b-it.md`.
  - Loads model files from least to most specific: family overlay first, then provider/model overlays such as `openrouter-localish.md`, `openrouter-localish/google.md`, `openrouter-localish/google/gemma.md`, `openrouter-localish/google/gemma-4-31b-it.md`.
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

- `agnt risk reset|check|status|<category>`
  - Tracks a session risk budget in JSON.
  - Default state: `<git-root>/.pi/risk-budget.json`.
  - `PI_RISK_BUDGET_FILE` overrides.

## Supporting commands

Some implementation-specific scripts remain in this directory, but agent-facing instructions should prefer `agnt` unless they intentionally need a lower-level helper. The `agnt` executable is a front controller; command implementation code lives in importable `agnt_lib/` modules.
