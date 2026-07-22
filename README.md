# Pi Setup

Pi Setup is an opinionated configuration-as-code environment for the Pi coding agent, together with `agnt`, its routing and workflow-control CLI.

The tracked [`pi/`](pi/README.md) tree is the deployable source of truth. It defines Pi's instructions, providers, models, skills, roles, actions, extensions, packages, and evaluation tools. The default runtime directory, `~/.pi`, contains the deployed copy plus preserved local state such as credentials and sessions.

Ordinary development happens directly in Pi: inspect, edit, and verify in the current session. Use `agnt` on demand to route work, compose context, launch peers, review evidence, diagnose the environment, and evaluate policy. Structured run bundles and the project-local runner are explicit opt-in paths.

Review the tracked settings, provider assumptions, and model policy before deploying them into your environment.

## What you get

| Layer | What it provides |
| --- | --- |
| **Pi configuration** | Global instructions, settings, model/provider data, tasks, actions, skills, roles, extensions, packages, and evals under `pi/`. |
| **`agnt` controls** | Model routing, context composition, peer invocation, evidence-backed review, operational health, metrics, lessons, and deterministic evals. |
| **Durable work and evidence** | Beads for work state, `.pi/plans/` for plans, runtime metrics for outcomes, and optional `.pi/runs/` bundles for replayable execution evidence. |
| **Optional orchestration** | Manual artifact-backed dispatch, Beads-backed approvals, constrained gateways, and a project-local runner for scheduled or unusually strict work. |
| **Feedback loop** | Runtime metrics and lessons inform reviewed, eval-gated changes to tracked routing, prompts, tools, and policy. Telemetry does not edit policy automatically. |

For the narrative overview, read [The agnt System](docs/AGNT-SYSTEM.md). For subsystem boundaries and data flow, read [Architecture](docs/ARCHITECTURE.md).

## How the system fits together

```text
tracked pi/ policy ──deploy──▶ ~/.pi runtime
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
              direct Pi work             agnt controls
              inspect/edit/test     route/invoke/context/review/doctor
                    │                           │
                    └────── durable state and evidence ──────┘
                          Beads / plans / metrics
                                      │
                             optional run bundles
                               ┌──────┴──────┐
                               │             │
                         manual dispatch   optional runner

runtime evidence and lessons ──review + eval──▶ tracked policy changes
```

Pi is the interactive runtime. `agnt` is a front controller around Pi, not a replacement for it. Manual `agnt runs` or `agnt work run` execution does not require the runner service; the service adds an explicitly started scheduling and executor boundary.

Two instruction files serve different scopes:

- [`AGENTS.md`](AGENTS.md) governs work on this repository.
- [`pi/agent/AGENTS.md`](pi/agent/AGENTS.md) becomes the global Pi instruction package after deployment.

The global policy requires a Bead before code edits in projects that have adopted a `.beads/` work graph. This repository also uses Beads for meaningful work. Read-only and documentation-only work may proceed without one unless project instructions require it.

## Deploy and use the configuration

Prerequisites depend on the features you use:

- Pi is required for deployment and runtime use.
- `direnv` and Nix are optional but recommended for this repository's development shell.
- `bd`/Beads is required for this repository's workflow.
- Provider credentials are required only for providers you call; see [Pi Config](pi/README.md#provider-credentials).

From the repository root:

```bash
direnv allow                         # optional, if using direnv
scripts/check-pi-config.sh           # validate tracked configuration
scripts/bootstrap-pi-config.sh --dry-run
scripts/bootstrap-pi-config.sh --apply
```

Deployment replaces the managed runtime copy from tracked `pi/` while preserving excluded credentials, sessions, trust state, metrics, and caches. Do not hand-edit managed files under `~/.pi`; edit `pi/`, verify, and deploy again. See [Pi Config](pi/README.md) for package installation, credentials, optional endpoints, and excluded-state details.

After `~/.pi/agent/bin` is on `PATH`, inspect the everyday control surface:

```bash
agnt doctor --json
agnt tasks
agnt route --task review --risk medium --budget balanced
agnt invoke --list review
agnt instructions --roles
```

Use the [agnt command reference](pi/agent/bin/README.md) for complete syntax and examples.

## Work on this repository

Use Beads as the agent-facing work graph:

```bash
bd prime      # load workflow context
bd ready      # list unblocked work
bd show <id>  # inspect one work item
```

Create or inspect a Bead before making code changes, then work directly in the current Pi session by default. Follow [Contributing](CONTRIBUTING.md) for planning, verification, review, and branch-readiness requirements.

## Core concepts

The context and work system uses small, separate primitives:

| Primitive | Responsibility |
| --- | --- |
| **Work item / Bead** | Records what durable work is ready, blocked, approved, or complete. |
| **Task** | Selects the model or execution policy for a class of work. |
| **Action** | Starts a named operation with a task, skills, role, allowed effects, and output contract. |
| **Skill** | Supplies a reusable method, workflow, domain capability, reference set, or helper tool. |
| **Role** | Defines how a delegated peer should behave and report. |
| **Tool / eval / gate** | Performs or verifies deterministic behavior that should not depend on prose alone. |
| **Artifact** | Records an invocation, result, plan, finding, metric, or other evidence for inspection and handoff. |

These concepts compose; they do not replace one another. See [Self-Improvement Principles](docs/SELF-IMPROVEMENT-PRINCIPLES.md) for the design rationale.

## Optional orchestration and integrations

The default deployment does not start a runner or require structured run bundles.

- [Run Artifacts](docs/RUN-ARTIFACTS.md) documents manual `agnt runs` and `agnt work` invocation/result bundles under `.pi/runs/`.
- [Project-Local Runner Service](docs/RUNNER-SERVICE.md) documents the explicitly started, loopback-only service for scheduling and executor lifecycle.
- [Lesson Server](lesson-server/README.md) is an optional service for aggregating and triaging lessons captured by `agnt lessons`.
- [Knowledge graphs](pi/agent/bin/README.md#knowledge-graphs) documents the optional Graphify integration and its explicit hook-management commands.
- [Pi Config](pi/README.md#optional-service-endpoints) documents optional search and model-provider endpoints.

The [Orchestration Loop Decision](docs/ORCHESTRATION-LOOP.md) explains why direct Pi coding remains the default.

## Repository layout

```text
pi-setup/
├── pi/            # deployable Pi configuration source
├── docs/          # concepts, architecture, procedures, decisions, and audits
├── scripts/       # checks, deployment helpers, and behavioral evals
├── tests/         # pytest coverage for agnt/agent-instructions internals
├── lesson-server/ # optional lesson aggregation and triage service
├── .beads/        # Beads work graph export/config; local DB ignored
└── .pi/           # project-local plans/runs/scratch; not deployable config
```

## Documentation map

### Deploy and operate

- [Pi Config](pi/README.md) — deployable contents, deployment behavior, credentials, endpoints, and excluded runtime state.
- [agnt command reference](pi/agent/bin/README.md) — command families, syntax, and common flows.
- [Contributing](CONTRIBUTING.md) — repository workflow, verification commands, and development environment.

### Understand the architecture

- [The agnt System](docs/AGNT-SYSTEM.md) — problem, design thesis, primitives, lifecycle, safety model, feedback loop, and relationship to Pi.
- [Architecture](docs/ARCHITECTURE.md) — implementation map for deployment, routing, invocation, context composition, evidence, quality gates, and safety gates.
- [Self-Improvement Principles](docs/SELF-IMPROVEMENT-PRINCIPLES.md) — design principles for tasks, skills, roles, prompts, tools, artifacts, and evals.
- [Self-Improvement Loop](docs/SELF-IMPROVEMENT.md) — how metrics and lessons become reviewed, eval-gated policy changes.

### Optional orchestration and services

- [Run Artifacts](docs/RUN-ARTIFACTS.md) — invocation/result schemas and manual artifact-backed workflows.
- [Project-Local Runner Service](docs/RUNNER-SERVICE.md) — service lifecycle, REST boundary, leases, drain, health, and security model.
- [Orchestration Loop Decision](docs/ORCHESTRATION-LOOP.md) — rationale for direct work by default and optional strict orchestration.
- [Lesson Server](lesson-server/README.md) — optional lesson aggregation and triage service.

### Decisions and historical evaluations

- [GitHub Adapter Decision](docs/GITHUB-ADAPTER.md) — why Beads remains canonical and GitHub issues are a possible adapter surface.
- [Self-Improvement Configuration Evaluation](docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md) — point-in-time audit and recommended improvements.

## Security and runtime state

Keep credentials, API keys, sessions, caches, trust state, onboarding state, metrics, and ordinary run artifacts out of git. Store provider keys in the shell environment or ignored local env files. See [Excluded runtime state](pi/README.md#excluded-runtime-state) for the preserved paths and deployment behavior.
