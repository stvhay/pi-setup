# The agnt System

`agnt` is a lightweight orchestration/control layer around Pi. It does not replace Pi; it gives Pi sessions a more explicit operating system for model routing, context assembly, delegated work, artifacts, metrics, and safety gates.

## Problem statement

A normal agent chat can do useful work, but the important control state is often implicit:

- Which work item is being handled?
- Which model should run it, and why?
- Which instructions, role, and skills should the worker see?
- What side effects are allowed?
- What evidence did the worker produce?
- Which follow-up work became ready?
- Did this model/workflow perform well enough to influence future routing?

If that state stays in chat, later humans, tools, and agents cannot reliably inspect it, retry it, audit it, or improve it.

`agnt` moves that state into files and deterministic commands.

## Design thesis

Agent work becomes safer and more useful when orchestration is explicit:

```text
work graph -> invocation artifact -> worker run -> result artifact -> state transition
```

The system favors small, inspectable primitives over hidden automation. The default development path is a direct Pi session: establish a Bead before changing code, then inspect, edit, and verify in the current session. For work that benefits from delegation or strict dispatch gates, the preserved optional path uses Beads for durable work state, `.pi/runs` for execution evidence, and a project-local loopback runner for scheduling/executor lifecycle.

## Core primitives

### Work items

Beads records durable work state: open, ready, blocked, in progress, closed, or deferred. Beads is the canonical agent-facing work graph for this repository. GitHub issues may become an adapter/export surface, but they are not a second source of truth.

### Routing tasks

A task is an operational routing label such as `review`, `planning`, `research`, or `orchestration`. Task files define preferred, qualified, and avoided model targets. They answer: **which model or execution default should handle this kind of work?**

### Skills

A skill is a reusable capability package: method, domain expertise, workflow, references, helper tools, or some combination. Skills answer: **what method should be loaded when doing this work?**

### Roles

A role defines a delegated worker’s stance and output contract, such as code reviewer, verifier, researcher, or implementation worker. Roles answer: **how should this peer behave and report?**

### Action templates

An action template is a verb-like invocation pattern. It binds routing task, skills, role, allowed effects, and output contract. Actions answer: **what work is being explicitly started now?**

### Run artifacts

Run artifacts live under `.pi/runs/<run-id>/` and contain `invocation.yaml`, `result.yaml`, and output files. They answer: **what was requested, what happened, and what evidence supports it?** Worker sessions are recorded by default for inspectable execution history. Observational memory may provide session-local recall, but it is advisory until promoted into Beads or `.pi/runs` evidence.

### Metrics and evals

Metrics record best-effort model usage and outcomes. Code-review metrics can link a validated structured finding artifact, separating discovery from fresh-context confirmation, refutation, or unresolved evidence. Evals check routing, instruction composition, actions, and workflow behavior. Together they let policy improve from evidence without treating telemetry as tracked source code or model confidence as ground truth.

## What agnt commands do

`agnt` is a front controller for several related command families:

- `agnt route` recommends a model for a task, risk level, budget, context size, and modality.
- `agnt invoke` runs one or more ephemeral Pi peers and records metrics by default; `--one-shot` disables tools and ambient context expansion for complete embedded packets.
- `agnt review` validates and summarizes structured discovery/adjudication findings.
- `agnt instructions` composes global, project, model, and role context packages.
- `agnt action` lists, validates, and renders action templates.
- `agnt runs` creates, validates, invokes, and updates invocation/result bundles.
- `agnt work` connects Beads work items to action/run artifacts, plan/tree views, daemon lifecycle, service-backed runner clients, health checks, and maintenance checkpoints.
- `agnt approvals` creates and resolves Beads-backed questions and approval gates.
- `agnt gateway` exposes a constrained ticket control surface for Pi extensions without raw shell/Beads passthrough.
- `agnt metrics` annotates, consolidates, prunes, and reports invocation metrics.
- `agnt eval` runs deterministic or model-backed checks.
- `agnt doctor` checks local operational readiness before agents rely on tools, providers, Beads, Node, or project config.
- `agnt context-health` checks active context for drift, unsafe weakening, and entropy signals.
- `agnt lessons` captures, pushes, pulls, and triages reusable lessons learned as JSONL records.

See the [agnt command reference](../pi/agent/bin/README.md) for syntax and examples.

## Work lifecycle

The normal coding lifecycle is:

```bash
bd show <bead-id>  # a Bead must exist before code edits
# inspect, edit, and run focused tests directly in Pi
```

A delegated run is an explicit optional workflow and can be manual and gated:

```bash
bd ready
agnt work tree --epic <epic-id> --json
agnt work plan <bead-id> --action review --target <path> --dry-run
agnt work run <bead-id> --action review --target <path> --claim
```

The explicitly selected project-local service path adds startup health and a REST client boundary:

```bash
agnt doctor --profile orchestrator-startup --json
agnt work daemon start --json --concurrency 1
agnt work runner status --json
agnt work runner tick --dry-run --json --limit 1
```

Behind that flow, `agnt`:

1. reads the Beads work item;
2. validates `metadata.pi` and dispatch policy;
3. selects a model/thinking level through routing policy, not ad hoc override;
4. creates a run bundle under `.pi/runs/` with ticket, worktree, session, memory, and todo-seed snapshots;
5. invokes a recorded Pi worker session from that artifact;
6. captures response, stderr, metrics, session refs, and evidence;
7. updates the result artifact with approvals, decisions, health checks, closeout checks, follow-ups, and artifacts; and
8. mutates Beads only when the caller supplied explicit flags such as `--claim`, `--close-bead`, or explicit maintenance/approval commands.

This makes retries, review, and handoff possible without reconstructing intent from chat.

## Safety model

`agnt` is intentionally gated. It does not assume every useful command should become autonomous.

Important gates include:

- dry-run planning before dispatch;
- declared allowed effects in action/run artifacts;
- read-only-by-default peer review patterns;
- explicit flags for Beads mutation;
- Beads-backed approval/decision records for human gates;
- one worktree per epic for implementation dispatch, with dirty/protected-branch refusal;
- health and closeout checks for missing evidence, unresolved approvals, stale sessions, orphaned runs, raw-tool bypass markers, and dirty worktrees;
- explicit approval for destructive git actions, remote writes, deployments, hook installation, and other irreversible changes;
- fresh verification evidence before completion claims;
- risk-specific, month-to-date spend gates for paid review and no automatic K3 review route;
- evidence-first finding adjudication that ignores reviewer confidence and consensus as escalation signals;
- instruction checks that reject safety-gate weakening phrases.

The safety model is layered: user preferences, roles, skills, prompts, and model overlays can specialize behavior, but they must not weaken project approval, verification, git, or security gates.

## Feedback loop

The system separates runtime telemetry from tracked policy:

```text
capture metrics -> annotate outcomes -> consolidate summaries -> adjust routing/prompts -> eval -> commit policy
capture lessons -> push to lesson server -> triage into Beads -> implement/eval -> commit policy
```

Raw metrics, lesson inboxes, observational-memory ledgers, and global telemetry stay out of git. Git tracks the durable policy changes they justify: task routing edits, model catalog updates, prompt overlays, docs, tools, Beads work, and evals. Maintenance due signals are derived from Beads, git, `.pi/runs`, health reports, context-health warnings, and recorded session volume rather than hidden counters.

This means the system can learn from observed model behavior while preserving an auditable source-of-truth boundary.

## Relationship to Pi

Pi provides the agent runtime, providers, sessions, extensions, and normal interaction surface. `agnt` wraps Pi for repeatable orchestration tasks:

- choosing a model;
- composing context;
- launching peers or recorded worker sessions;
- bridging ask/approval UI to durable Beads decisions;
- capturing artifacts, metrics, transcripts, and session refs;
- validating workflow invariants.

Use Pi directly for ordinary interactive work, including implementation and verification, after confirming a Bead exists for any code-changing task. Use `agnt` when work should be routed, delegated, measured, replayed, reviewed, or connected to run artifacts. The runner and orchestrator-only tool surface are opt-in rather than startup requirements.

## Stable vs experimental

Relatively stable:

- repository/runtime separation;
- `agnt route`, `invoke`, `instructions`, `metrics`, and basic evals;
- Beads as the repository’s canonical agent-facing work graph;
- action/run artifact schemas at their current v1 level;
- the single-user project-local runner service boundary, CLI client commands, and opt-in orchestrator startup gate.

Still evolving:

- explicit idempotency keys and richer duplicate-run detection;
- richer result extraction from worker transcripts;
- GitHub or other external adapters;
- conventions for larger multi-worker runs, production soak operation, notifications, and remote/multi-project dashboards.

## Where to read next

- [Architecture](ARCHITECTURE.md) — implementation map and subsystem boundaries.
- [Project-Local Runner Service](RUNNER-SERVICE.md) — service lifecycle, REST API, leases, drain, and status/security model.
- [Run Artifacts](RUN-ARTIFACTS.md) — invocation/result schemas and commands.
- [Orchestration Loop Decision](ORCHESTRATION-LOOP.md) — why the system uses a Beads-first gated workflow plus project-local service boundary.
- [Self-Improvement Loop](SELF-IMPROVEMENT.md) — metrics, routing feedback, prompt overlays, and eval-gated policy changes.
- [agnt command reference](../pi/agent/bin/README.md) — command syntax and examples.
