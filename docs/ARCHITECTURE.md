# Architecture

pi-setup is configuration-as-code for a reusable Pi agent environment. It has
one deployable artifact (the `pi/` tree), one orchestration CLI (`agnt`), and
a feedback loop that lets routing and prompts improve from observed outcomes.
For the narrative overview, start with [The agnt System](AGNT-SYSTEM.md). For
the feedback loop, see [Self-Improvement Loop](SELF-IMPROVEMENT.md).

## Repository vs runtime

```text
pi-setup/ (this repo, source of truth)
├── pi/                  deployable Pi config  ──rsync──▶  ~/.pi (runtime copy)
├── .beads/              Beads work graph export/config; local DB ignored
├── docs/                architecture, procedures, design decisions, audits
├── scripts/             deploy, layout checks, behavioral eval suite
├── tests/               pytest for agnt/agent-instructions internals
└── .pi/                 project-local plans/runs/scratch (not deployable)
```

- `scripts/bootstrap-pi-config.sh` deploys `pi/` → `~/.pi` (dry-run by
  default). Runtime secrets/state (`auth.json`, `sessions/`, `trust.json`,
  `~/.pi/metrics/`, caches) are rsync-excluded and survive deploys.
- Edits go in this repo, then deploy. The live `~/.pi` is never the place to
  change config; `rsync --delete` will overwrite it.
- Two instruction levels share one filename: the repo root `AGENTS.md` is
  *project* instructions for working on pi-setup itself; `pi/agent/AGENTS.md`
  is the *global* instruction file every Pi session loads after deploy.

## Layers (data flows top to bottom, evidence flows back up)

```text
catalog.json      model families -> venues, cost classes, watt/rate facts
      │
tasks/*.md        routing policy per task (preferred/qualified/avoid targets)
      │
agnt route        constraint filter (enabledModels, modality, context window,
      │           local-ok) + budget ranking + outcome-history demotion
      │
agnt invoke       runs `pi --mode json --no-session`; emits metric records
      │
.pi/metrics/      per-project raw records ──consolidate──▶ ~/.pi/metrics/
      │                                                       (global store)
      └───────────── outcome annotations feed back into `agnt route` ─────┘
```

### Model catalog (`pi/agent/catalog.json`)

A **family** is one set of weights (or a close equivalent) reachable through
several **venues**: a local Ollama host, a remote Olla-compatible GPU endpoint,
or OpenRouter. The catalog is the single source for venue facts: cost class,
modalities, context window, reasoning capability, GPU-watt assumptions, and
OpenRouter opportunity-cost rates for subscription-backed models. `agnt` and
`agent-instructions` read it via the shared `bin/_agnt_common.py`; no model
facts live in code. OpenRouter cash pricing stays in `models.json` because Pi
itself reads provider config there.

### Work, tasks, prompts, skills, roles, and tools

The context system uses small orthogonal primitives. See
[Self-Improvement Principles](SELF-IMPROVEMENT-PRINCIPLES.md) for the design
rationale.

- **Work item / bead**: durable task-graph node. Answers "what unit of work is
  scheduled, blocked, or complete?" Beads is the canonical agent-facing work
  queue for dependencies, approvals, blockers, closeout, and maintenance
  checkpoints. GitHub issues are not mirrored now; any future integration should
  follow the [GitHub Adapter Decision](GITHUB-ADAPTER.md) and remain an adapter
  rather than a second source of truth.
- **Invocation/result message**: structured interface between orchestration and
  workers. Answers "what should run now?" and "what happened with what
  evidence?" Invocation v1 records ticket metadata, selected model/thinking,
  dispatch/session/memory policy, todo seeds, and worktree snapshots. Result v1
  records evidence, follow-ups, session/transcript/memory refs, approval/decision
  refs, health checks, and closeout checks.
- **Task** (`pi/agent/tasks/*.md`): operational routing label (`review`,
  `orchestration`, …) with preferred/qualified/avoid target lists in
  frontmatter. Answers "which model or execution default?" A task named
  `orchestration` is a routing category, not the orchestration engine itself.
- **Prompt / action template** (`pi/agent/actions/*.md`, with provenance notes
  under `pi/agent/prompt-patterns/`): explicit invocation pattern. Answers
  "what action is being started now, with which arguments?" Actions select
  tasks, skills, roles, effects, and output contracts.
- **Skill** (`pi/agent/skills/*/SKILL.md`): reusable capability package —
  method, domain expertise, references, helper scripts, or any mix of prose and
  code. Answers "what method or capability should be loaded?"
- **Role** (`pi/agent/AGENTS.d/roles/*.md`): delegated-worker stance and output
  contract (code-reviewer, verifier, …). Answers "how should this peer behave
  and report?" Roles may reference relevant skills, but reusable workflow
  belongs in skills and model preference policy belongs in tasks.
- **Tool/eval/gate** (`pi/agent/bin/`, `pi/agent/evals/`, scripts):
  deterministic operation or check. Answers "what should code perform or
  verify instead of prose?"

### Instruction composition (`agnt instructions` / `agent-instructions`)

Append-only concatenation of context packages: a root file (`AGENTS.md`,
`SKILL.md`, `SOUL.md`) plus supplements in a sibling `<stem>.d/` directory.
Default composition order: global `pi/agent/AGENTS.md` → global model/role
overlays → discovered project instruction files (`AGENTS.md`, `AGENT.md`,
`CLAUDE.md` from git root to cwd) → project overlays, deduplicated.

Model overlays resolve **family first, then venue**:
`AGENTS.d/models/<family>.md` (family ids from the catalog) applies to every
venue of the same weights; slash-style `AGENTS.d/models/<provider>/...` files
refine one venue. `--check` validates structure and scans all composed files
for gate-weakening phrases.

### Orchestration CLI (`pi/agent/bin/agnt`)

Front controller for: `route` (recommend model + thinking level for
task/risk/budget, JSON with explicit reasons and rejected candidates),
`invoke` (single or `--fanout` parallel peers, metrics on by default),
`metrics` (status/annotate/consolidate/import-session), `eval`
(filesystem-defined deterministic evals), `instructions`, `prompt`, `action`,
`runs`, `work`, `approvals`, `gateway`, `benchmark`, `web-search`/`web-fetch`,
`plans-dir`, `risk`.

Design constraint: `agnt` is a front controller, not the home for subsystem
logic. Command implementations live under `pi/agent/bin/agnt_lib/` (`routing`,
`invoke`, `metrics`, `evals`, `tasks`, `prompt`, `actions`, `runs`, `work`, and
`benchmark`) and share catalog/frontmatter helpers through `_agnt_common.py`.
New shared behavior should move into those importable modules, or a new
`agnt_lib` module when the seam is clear; avoid adding another independent
model/catalog/parser table inside the executable. The orchestration additions
follow that seam: metadata validation in `orchestration.py`, approval flow in
`approvals.py`, ticket gateway in `gateway.py`, runner compatibility wrappers in
`runner.py`, runner protocol/state contracts in `runner_protocol.py`, the
loopback service in `runner_service.py`, REST clients and daemon lifecycle in
`runner_client.py`, scheduling in `runner_scheduler.py`, startup policy in
`startup_policy.py`, worktree policy in `worktree_policy.py`, health checks in
`health.py`, and maintenance cadence in `maintenance.py`.

### Inspectable work backbone

The orchestration shape is a transparent work pipeline:

```text
work graph -> invocation messages -> worker runs -> result messages -> artifacts -> state transitions
```

Chat is a UI, not the system of record. Every code-changing task requires a
Bead before edits begin. The default execution path is direct Pi inspection,
editing, and verification in the current session. Nontrivial work should leave
durable artifacts — plans, reports, patches, metrics, verification logs, or
optional run records — with enough structure for a human, tool, or later agent
to inspect, retry, verify, or continue the work. Current pieces are: `.beads/`
for work graph export/config, `.pi/plans/` for plans, optional `.pi/runs/` for
invocation/result artifacts, `.pi/metrics/` for runtime telemetry, `agnt action render` and
`agnt runs` for message artifacts, `agnt work` for dry-run bead dispatch plans,
plan trees, daemon lifecycle, service-backed runner client operations, health
checks, and maintenance checkpoints, `agnt approvals` for durable human
decisions, `agnt gateway` for constrained Pi extension access and service-backed
runner visibility, `agnt invoke` for peer dispatch, `agnt runs invoke` / `agnt
work run` for invocation-backed worker execution, `agnt context-health` for
context entropy checks, and `pi/agent/evals/` for gates. See the
[Orchestration Loop Decision](ORCHESTRATION-LOOP.md) and
[Project-Local Runner Service](RUNNER-SERVICE.md) for the explicitly selected
Beads-first gated workflow and its project-local loopback service boundary.

### Metrics and feedback

Raw per-invocation records land in `<git-root>/.pi/metrics/invocations/`
(project-local, gitignored). `agnt metrics consolidate` appends compact records
to the durable global store `~/.pi/metrics/agent-invocations.jsonl`; run it
manually or from a locally installed hook. `agnt route` aggregates outcomes by
family across pending and consolidated metrics and demotes families with
negative track records. `agnt work maintenance due` derives self-improvement
triggers from Beads, git, run artifacts, health reports, context-health warnings,
and recorded session volume. Git never tracks telemetry; it tracks the policy
changes and maintenance checkpoint Beads the telemetry justifies.

## Quality gates

Three test tiers, cheapest first:

1. `tests/` (pytest) — pure-function coverage of catalog lookups, routing
   ranks, cost attribution, overlay resolution. Free, instant.
2. `agnt eval run routing-smoke|role-context-smoke` — deterministic CLI-level
   checks of routing policy and instruction composition. Free, instant.
3. `scripts/eval-workflow-compliance.sh` — behavioral cases running real
   models in throwaway git repos, asserting filesystem effects (no writes
   before approval, plans actually created, stops on main, …). Costs model
   calls; smoke subset by default.

Layout/safety checks: `scripts/check-pi-config.sh` (required files present,
no secrets/submodule regression, action validation, context-health strict check,
and prompt inventory), `agent-instructions --check`. Optional orchestration
state is checked separately with `agnt work audit|health` when that path is used.

## Safety model

Layered gates, none overridable by overlays or `SOUL.md` (communication style
only): a Bead before every code-changing task, approval before implementation in
design workflows, fresh shell evidence before completion claims, read-only-by-
default peer work, explicit approval for destructive/remote git actions, and the
suspicious-phrase scan on composed instructions. When orchestration is explicitly
selected, Beads-backed human decisions, recorded worker sessions, one worktree
per epic, and run health/closeout checks add stricter optional gates.
