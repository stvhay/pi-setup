# Pi Setup

Pi Setup is configuration-as-code for a Pi coding-agent environment, plus an experimental orchestration layer called `agnt`.

The repository has two jobs:

1. keep reusable Pi configuration in version control; and
2. make agent work more inspectable, routable, and verifiable through explicit work state, context composition, run artifacts, metrics, and evals.

The tracked [`pi/`](pi/README.md) tree is the deployable source of truth. The default Pi runtime directory, `~/.pi`, is generated runtime state.

## Why this exists

Plain agent sessions are easy to start but hard to audit. Important state often lives in chat: what work was selected, which model ran, what context it saw, what evidence supports the result, and what should happen next.

This project pushes that state into files and tools:

- **Pi config** defines reusable instructions, skills, roles, settings, providers, and model catalog data.
- **`agnt`** acts as a small orchestration/control CLI around Pi.
- **Beads** records durable work items, dependencies, blockers, approvals, closeout, and maintenance checkpoints.
- **Action templates and run artifacts** turn “ask a worker” into inspectable invocation/result files with session, approval, health, and evidence refs.
- **Tasks, skills, and roles** separate model routing, reusable methods, and delegated-worker behavior.
- **Metrics, health checks, maintenance cadence, and evals** let routing and prompts improve from evidence without tracking runtime telemetry in git.

For the narrative overview, read [The agnt System](docs/AGNT-SYSTEM.md). For implementation structure, read [Architecture](docs/ARCHITECTURE.md).

## System at a glance

```text
tracked pi/ config ──deploy──▶ ~/.pi runtime
       │
       ├── tasks / skills / roles / actions
       │          │
       │          ▼
Beads work graph ──▶ agnt route/invoke/runs/work ──▶ Pi worker runs
       ▲                         │                         │
       │                         ▼                         ▼
       └──── approvals/blockers ◀ run artifacts ◀── results + evidence
       ▲                         │                         │
       └──── maintenance beads ◀─ health + metrics + recorded sessions
```

## Choose your path

### I want to use this configuration

Prerequisites depend on which parts you use:

- Pi must be installed for deployment/runtime use.
- `direnv` + Nix are optional but recommended for this repository’s development shell.
- `bd`/Beads is required for the repository workflow.
- Provider keys, such as OpenRouter, are needed only for providers you call.

Quick start:

```bash
direnv allow                         # optional, if using direnv
scripts/check-pi-config.sh           # validate tracked config
scripts/bootstrap-pi-config.sh --dry-run
scripts/bootstrap-pi-config.sh --apply
agnt --help                          # after ~/.pi/agent/bin is on PATH
```

Deployment details live in [Pi Config](pi/README.md).

### I want to work on this repository

Use Beads as the agent-facing work graph:

```bash
bd prime      # workflow context
bd status     # work graph summary
bd ready      # unblocked work
bd show <id>  # inspect one bead
```

Then follow [Contributing](CONTRIBUTING.md) for planning, verification, review, and branch-readiness expectations.

### I want to understand or extend the agent system

Start with [The agnt System](docs/AGNT-SYSTEM.md). Then use the documentation map below.

## Documentation map

### Start here

- [The agnt System](docs/AGNT-SYSTEM.md) — conceptual overview of the orchestration/control layer: problem, design thesis, primitives, work lifecycle, safety model, approvals, runner, health, and feedback loop.
- [Architecture](docs/ARCHITECTURE.md) — implementation map: repository/runtime separation, routing, invocation, metrics, instruction composition, Beads-first orchestration, quality gates, and safety gates.
- [agnt command reference](pi/agent/bin/README.md) — command families and common flows.

### Operate the system

- [Pi Config](pi/README.md) — deployable config contents, deployment behavior, provider credentials, and excluded runtime state.
- [Run Artifacts](docs/RUN-ARTIFACTS.md) — invocation/result artifact schema and the `agnt runs` / `agnt work` workflow.
- [Contributing](CONTRIBUTING.md) — repository workflow, test commands, and development environment.

### Understand design decisions

- [Orchestration Loop Decision](docs/ORCHESTRATION-LOOP.md) — why the current production path is a gated command loop plus explicit project-local runner rather than an installed service.
- [Self-Improvement Loop](docs/SELF-IMPROVEMENT.md) — how metrics, health, Beads, and recorded sessions trigger maintenance while telemetry stays untracked.
- [Self-Improvement Principles](docs/SELF-IMPROVEMENT-PRINCIPLES.md) — design principles for context architecture, tasks, skills, roles, prompts, tools, artifacts, and evals.
- [GitHub Adapter Decision](docs/GITHUB-ADAPTER.md) — why Beads remains canonical and GitHub issues are treated as a future adapter surface.

### Audits and historical evaluations

- [Self-Improvement Configuration Evaluation](docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md) — point-in-time audit of the configuration and recommended next improvements.

## Repository layout

```text
pi-setup/
├── pi/          # deployable Pi configuration source
├── docs/        # concepts, architecture, procedures, decisions, and audits
├── scripts/     # checks, deployment helpers, and behavioral evals
├── tests/       # pytest coverage for agnt/agent-instructions internals
├── .beads/      # tracked Beads work graph export/config; local DB ignored
└── .pi/         # project-local plans/runs/scratch; not deployable config
```

## Common procedures

### Configure provider credentials

Provider keys belong in the shell environment or ignored local env files, never in git. For OpenRouter:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

With direnv, prefer an ignored file such as `.envrc.local.d/openrouter.sh`.

### Run Graphify

This config includes the Graphify Pi skill under [`pi/agent/skills/graphify/`](pi/agent/skills/graphify/). Use `/graphify .` in Pi, or run the CLI through `agnt`:

```bash
agnt graphify --help
agnt graphify extract . --no-cluster
agnt graphify query "How is routing implemented?"
```

`agnt graphify` uses an installed `graphify` binary when present and otherwise falls back to `uv tool run --from graphifyy graphify`. It never installs hooks implicitly. Manage hooks explicitly with `agnt graphify hooks install|status|uninstall`; install and uninstall require approval in agent workflows because hooks change repository behavior.

### Verify changes

Fast local checks:

```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agent-instructions --check
pi/agent/bin/agnt action validate
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt work health --json
pi/agent/bin/agnt work maintenance due --json
pi/agent/bin/agnt prompt inventory >/tmp/agnt-prompt-inventory.json
python -m json.tool /tmp/agnt-prompt-inventory.json >/dev/null
git diff --check
```

Workflow compliance evals run real models:

```bash
./scripts/eval-workflow-compliance.sh          # smoke suite
./scripts/eval-workflow-compliance.sh --list
./scripts/eval-workflow-compliance.sh --case writing_plans_creates_plan
./scripts/eval-workflow-compliance.sh --full
./scripts/eval-workflow-compliance.sh --full --parallel 3
```

## Private and generated state

Do not track runtime secrets, sessions, caches, onboarding state, trust state, API keys, local metrics, or ordinary run artifacts. The deploy helper preserves runtime state such as:

- `agent/auth.json`
- `agent/sessions/`
- `agent/mcp-cache.json`
- `agent/mcp-onboarding.json`
- `agent/trust.json`
