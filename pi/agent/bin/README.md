# Pi local helper commands

Use `agnt` as the primary command surface for local agent helpers. Commands are designed to compose with normal Unix idioms: stdin when no file is supplied, stdout for primary output, stderr for diagnostics, and `-o` for files/directories when needed.

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

- `agnt route --task TASK [--risk low|medium|high] [--budget cheap|balanced|quality] [--context-tokens N] [--modality text|image|audio|video] [--local-ok]`
  - Recommends a model, fallback models, thinking level, and whether fanout is useful.
  - Uses the existing task files as policy, filters by `agent/settings.json` `enabledModels` plus runtime constraints, and includes metrics hints when available.
  - Outcome history is aggregated by model family (`agent/catalog.json`) across the global consolidated store and local pending metrics; candidates whose family shows more negative than positive outcomes over at least 5 invocations are demoted with an explicit reason. Evidence gathered on one venue applies to every venue of the same weights.
  - `agnt recommend` is an alias.

- `agnt invoke [--task TASK] [--risk-category LABEL] [--thinking-level LEVEL] [--outcome OUTCOME] [--human-override] [--fallback-used] [--no-metrics] [--metrics-dir DIR] provider/model [filename]`
  - Runs one ephemeral Pi peer. Metrics are on by default, so `agnt` uses `pi --mode json --no-session`, preserves normal stdout, and writes raw token/cost/wall-clock metrics to `DIR` or `<git-root>/.pi/metrics/invocations/`.
  - Metrics include routing fields when supplied: task, risk category, thinking level, context size, estimated input tokens, outcome, human override, and fallback-used flags.
  - Use `--no-metrics` to use the older `pi --print --no-session` path and skip metrics.
  - Reads prompt from `filename`, `@filename`, argv text, or stdin.

- `agnt invoke --fanout [--task TASK] [--no-metrics] [-o DIR] [prompt-or-file]`
  - Runs the task's preferred models and writes output artifacts to `DIR`.
  - With default metrics, writes `<model>.metrics.json` for each peer, `metrics.summary.json`, and central raw invocation metrics.

- `agnt invoke --fanout [--no-metrics] [-o DIR] provider/model [filename]`
  - Runs one model and writes output artifacts to `DIR`.

- `agnt invoke --fanout [--no-metrics] [-o DIR] provider/model filename [provider/model filename ...]`
  - Runs multiple provider/model + prompt-file pairs in parallel.

Metrics use `schemaVersion: 1` and are best-effort: when Pi/provider usage is unavailable, metrics JSON records `usageSource: "unavailable"` and `usage: null`. New records include a stable `recordId`; old records remain loadable. When usage is available but the provider reports zero/missing dollars for a known subscription-backed or OpenRouter model, `agnt` fills `usage.cost` with an OpenRouter-price opportunity-cost estimate and marks it with `usage.costSource: "openrouter-assumed"` and `usage.costEstimated: true`. This keeps subscription GPT usage comparable without routing GPT calls through OpenRouter.

Local models keep cash/API `usage.cost.total` at zero with `usage.costSource: "local-free"`. For known local equivalents, metrics add a separate `usage.opportunityCost` using an OpenRouter proxy model rather than pretending that local inference spent API dollars. Local calls also get a rough marginal GPU electricity estimate in `usage.localCompute`, using `AGNT_LOCAL_GPU_WATTS` when set. Otherwise `olla-local/*` defaults to an assumed remote Olla marginal GPU draw of 208W, `ollama/*` defaults to an assumed local MacBook GPU draw of 34.2W, and `AGNT_USE_NVIDIA_SMI=1` opts into sampling `nvidia-smi` on the current host. Electricity price uses `AGNT_ELECTRICITY_USD_PER_KWH` or the default `$0.1304/kWh`. Raw metrics live under `.pi/metrics/` and are ignored by git.

Use `agnt invoke` and `agnt invoke --fanout` for all peer calls; they capture metrics by default. The old `pi-peer`/`pi-fanout` wrappers were removed because they bypassed metrics capture.

## Metrics

Example routing flow:

```bash
agnt route --task review --risk medium --budget cheap --local-ok
agnt invoke --task review --risk-category medium --thinking-level default <selected-provider/model> prompt.md
```

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
  - Creates a generic invocation/result run bundle. See `docs/RUN-ARTIFACTS.md` for schema details.

- `agnt runs invoke .pi/runs/<run-id> [--model provider/model] [--no-metrics]`
  - Reads `invocation.yaml`, invokes a worker, writes prompt/response/stderr/metrics artifacts, and updates `result.yaml`.

- `agnt runs update .pi/runs/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--artifact PATH ...] [--follow-up ID ...] [--metrics-ref PATH]`
  - Enriches `result.yaml` with evidence, artifacts, follow-up beads, metrics refs, and terminal statuses.

- `agnt runs validate .pi/runs/<run-id> [--require-followups-exist]`
  - Validates required `invocation.yaml` and `result.yaml` fields. With `--require-followups-exist`, every `result.yaml.followUps[]` id must resolve to a Beads item.

- `agnt work next --json`
  - Reads Beads ready work and selects the first non-epic ready bead when available.

- `agnt work plan [BEAD_ID] --action ACTION --target REF --dry-run`
  - Builds a dry-run dispatch plan from a bead plus action template. It does not invoke a model or mutate Beads.

- `agnt work start [BEAD_ID] [--action ACTION] [--target REF ...] [--claim]`
  - Creates a run bundle for a bead/action and copies bead acceptance criteria into `invocation.yaml`. It mutates Beads only when `--claim` is supplied.

- `agnt work run [BEAD_ID] [--action ACTION] [--target REF ...] [--model provider/model] [--claim] [--close-bead]`
  - Creates a run bundle, invokes a worker from `invocation.yaml`, updates `result.yaml`, and closes the bead only when `--close-bead` is supplied, invocation succeeds, evidence exists, and follow-up ids resolve to Beads.

- `agnt work audit [--json] [--scan-root PATH ...]`
  - Reports Beads queue counts and required-work signals in docs/run artifacts; fails when the queue is empty but required future work appears unresolved.

- `agnt work finish .pi/runs/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--close-bead]`
  - Updates `result.yaml`; closes the invocation bead only when `--close-bead` is supplied and status is `succeeded` with evidence and reconciled follow-up ids.

## Context health

- `agnt context-health [--strict]`
  - Checks active Pi context for stale helper names, gate-weakening phrases, oversized unallowlisted skills, and overlapping skill descriptions.
  - `--strict` exits nonzero when failures are found; warnings are reported for entropy signals.

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

To consolidate metrics automatically before commits, install the tracked hook once per clone:

```bash
git config core.hooksPath .githooks
```

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
