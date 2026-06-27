# Documentation Coherence Evaluation

**Date:** 2026-06-26
**Scope:** `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/*.md`, `pi/README.md`, `pi/agent/bin/README.md`, `pi/agent/prompt-patterns/README.md`.

## Verdict

The concern is fair. The documentation contains strong material, especially in `docs/ARCHITECTURE.md`, `docs/RUN-ARTIFACTS.md`, and `docs/SELF-IMPROVEMENT-PRINCIPLES.md`, but the top-level structure does not yet teach the project coherently. The README is an index plus procedures, not a reader-oriented introduction. It names pieces before explaining why those pieces matter.

The largest gap is the absence of a narrative document for the `agnt` system itself. `agnt` is the conceptual center of the interesting work, but it is currently split across architecture, command reference, run artifacts, orchestration-loop decision, and self-improvement docs. A new reader has to infer the thesis.

## Evidence collected

- Markdown docs in scope: 13 files, including 7 `docs/*.md` files.
- The scoped docs use backticked paths for internal references, not Markdown links. The link check found no Markdown links in the top-level project docs because there were effectively none to check.
- Command/path quick check passed for the main documented surfaces: `scripts/check-pi-config.sh`, `scripts/bootstrap-pi-config.sh`, `scripts/eval-workflow-compliance.sh`, `pi/agent/bin/agnt`, `pi/agent/bin/agent-instructions`, `pi/agent/actions`, `pi/agent/evals`, `pi/agent/tasks`, `pi/agent/AGENTS.d/roles`, and `pi/agent/prompt-patterns/README.md`.
- `agnt -h`, `agnt action -h`, `agnt runs -h`, `agnt work -h`, `agnt metrics -h`, and `agnt instructions -h` confirm the main command families documented in `pi/agent/bin/README.md` exist.
- Potential correctness issue: docs mention a tracked `.githooks` pre-commit hook, but no `.githooks` path was found in the repository.

## Major findings

### 1. README lacks a clear thesis and reader contract

`README.md:3-5` says the repository is reusable Pi configuration and tells readers to choose a path. That is accurate but undersells and under-explains the repository.

A new reader needs to know, in this order:

1. This is configuration-as-code for a Pi coding-agent environment.
2. It also includes `agnt`, a lightweight orchestration/control plane around Pi.
3. The system makes agent work more inspectable through Beads, action templates, run artifacts, routing policy, metrics, evals, and composed context.
4. The repository can be approached as either deployable config or as an agent-systems design/implementation project.

The current README starts with procedures (`README.md:9-42`) before building that mental model. The result feels like a checklist whose purpose is not yet obvious.

### 2. The top-level README mixes audiences too early

`README.md` currently interleaves:

- end-user setup (`README.md:9-42`),
- contributor workflow (`README.md:44-55`),
- architecture doc index (`README.md:57-65`),
- repository layout (`README.md:67-77`),
- conceptual summary (`README.md:79-86`),
- operational procedures (`README.md:88-139`).

Those are all valid topics, but the sequence is not pedagogical. The conceptual summary arrives after setup and doc navigation, so readers lack context when they encounter Beads, `agnt`, Graphify, metrics, and workflow evals.

Recommended order:

1. What this is.
2. Why it exists.
3. System map / core ideas.
4. Audience paths.
5. Quick start for deployment.
6. Quick start for development.
7. Documentation map with real links.
8. Verification and safety notes.

### 3. Internal references are not actual links

The user's nit is correct. In `README.md:42` and `README.md:59-65`, internal docs are written as backticked paths, not Markdown links. The same pattern appears throughout `docs/ARCHITECTURE.md`, `docs/SELF-IMPROVEMENT.md`, `pi/README.md`, and `pi/agent/bin/README.md`.

This hurts navigation and reinforces the feeling that the README is a list of file names rather than a documentation root.

Recommended standard:

```md
[Architecture](docs/ARCHITECTURE.md)
[Run artifacts](docs/RUN-ARTIFACTS.md)
[agnt command reference](pi/agent/bin/README.md)
```

Use backticks only when the path itself is the concept being discussed, not when the reader is meant to navigate.

### 4. The `agnt` system is described, but not as a system

The pieces are documented:

- `docs/ARCHITECTURE.md:103-118` describes `agnt` as a front controller.
- `docs/ARCHITECTURE.md:120-138` describes the inspectable work backbone.
- `docs/RUN-ARTIFACTS.md` describes invocation/result artifacts.
- `docs/ORCHESTRATION-LOOP.md` describes the gated command loop.
- `docs/SELF-IMPROVEMENT.md` describes the metrics feedback loop.
- `pi/agent/bin/README.md` describes the command surface.

But there is no single narrative answering:

- What problem does `agnt` solve?
- Why not just use Pi directly?
- What are its primitives?
- How does a unit of work flow through the system?
- What safety properties does the design aim to preserve?
- What is novel or experimental here?
- What parts are stable vs evolving?

This is the most important documentation gap.

Recommendation: add `docs/AGNT-SYSTEM.md` or `docs/AGNT.md` as a conceptual overview, then link it prominently from the README before the command reference.

### 5. `docs/ARCHITECTURE.md` is strong but too dense for first contact

`docs/ARCHITECTURE.md` is accurate and compact. Its layer diagram (`docs/ARCHITECTURE.md:29-43`) and primitive taxonomy (`docs/ARCHITECTURE.md:57-87`) are useful.

However, it assumes the reader is already invested. It moves quickly through catalog, tasks, route, invoke, metrics, instruction composition, run artifacts, and safety gates. It is a good architecture reference, not an onboarding narrative.

Recommendation: keep it as the architecture reference. Do not overload it with the missing `agnt` narrative. Link to it from the new `AGNT-SYSTEM.md` for implementation details.

### 6. `pi/agent/bin/README.md` is useful but organized as a command inventory, not a task guide

The `agnt` command reference is mostly correct and comprehensive. It confirms the existence of the main command families.

Readability issues:

- It has two `## Metrics` sections (`pi/agent/bin/README.md:60` and `pi/agent/bin/README.md:145`). The first is really an example routing flow.
- The first paragraph calls these “local agent helpers” (`pi/agent/bin/README.md:3`), which undersells `agnt` as the primary orchestration/control surface.
- Some commands are documented before the conceptual workflow that makes them meaningful.

Recommendation: split into:

1. one short “How to use this reference” intro,
2. common flows (`route -> invoke`, `action -> runs`, `work -> run`, `metrics -> annotate/consolidate`),
3. command reference.

### 7. Correctness issue: tracked pre-commit hook appears stale or absent

Two docs claim automatic metrics consolidation via a tracked pre-commit hook:

- `docs/ARCHITECTURE.md:142-145`
- `docs/SELF-IMPROVEMENT.md:50-53`
- `pi/agent/bin/README.md:166-170` says to install the tracked hook with `git config core.hooksPath .githooks`.

But no `.githooks` directory or hook file was found. Search found references to `.githooks`, but not the hook implementation.

Possible fixes:

- Add the tracked hook if this is intended behavior.
- Or revise docs to say consolidation is manual unless a project installs its own hook.

### 8. Audience fit is uneven

For a user who wants to deploy the config:

- `README.md` has enough commands, but it lacks prerequisites and expected outcomes. For example, it does not explain what Pi version/package is assumed, whether `bd` must already be installed, or what “healthy” means after `scripts/check-pi-config.sh`.

For a contributor:

- `CONTRIBUTING.md` is concise and useful.
- The README should link to it and say whether contributors need Beads, direnv/Nix, and the full workflow eval suite.

For a reader trying to understand the system:

- The material is rich but scattered. They need a guided path: `README -> AGNT-SYSTEM -> ARCHITECTURE -> RUN-ARTIFACTS -> ORCHESTRATION-LOOP -> SELF-IMPROVEMENT`.

For future agents:

- The docs are strong. They emphasize source-of-truth, artifacts, gates, and verification. Agent-facing instructions are more mature than human-facing onboarding.

### 9. Concepts are good but introduced too late and too compactly

The concept bullets in `README.md:79-86` are accurate, but they are compressed. They should move earlier and become a small system map.

A better map:

```text
Pi runtime config      -> deployable environment
agnt                  -> orchestration/control CLI
Beads                 -> durable work graph
Actions + runs        -> explicit invocation/result artifacts
Tasks/skills/roles    -> context and model-selection primitives
Metrics + evals       -> feedback and safety checks
```

Each entry should answer “why this exists,” not only “what it is.”

### 10. Some docs are historical/audit artifacts but are not labeled as such in navigation

`docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md` is a point-in-time audit. It is valuable, but it should not sit beside core docs without a label. Readers may treat it as current design guidance or wonder why recommendations are mixed with implemented facts.

Recommendation: in the README docs map, separate:

- Start here / conceptual docs
- Procedures
- Decisions / ADRs
- Audits / historical evaluations

## Recommended target documentation structure

### Root README

Purpose: orient all readers and route them.

Recommended sections:

1. `# Pi Setup`
2. `## What this is`
3. `## Why it exists`
4. `## System at a glance`
5. `## Quick start: deploy the config`
6. `## Quick start: work on the repo`
7. `## Documentation map`
   - Learn the system
   - Operate it
   - Extend it
   - Decisions and audits
8. `## Verification`
9. `## Private/generated state`

### New `docs/AGNT-SYSTEM.md`

Purpose: explain the novel core.

Recommended sections:

1. `# The agnt System`
2. `## Problem statement`
3. `## Design thesis`
4. `## Core primitives`
5. `## Work lifecycle`
6. `## Safety model`
7. `## Feedback loop`
8. `## How agnt relates to Pi, Beads, skills, and roles`
9. `## What is stable vs experimental`
10. `## Where to read next`

### `docs/ARCHITECTURE.md`

Purpose: reference architecture. Keep mostly as-is, but add links and point to `AGNT-SYSTEM.md` for narrative.

### `pi/agent/bin/README.md`

Purpose: command reference. Rename first `## Metrics` to `## Common routing flow`, de-duplicate sections, and add links back to conceptual docs.

### Decision/audit docs

Keep:

- `docs/GITHUB-ADAPTER.md`
- `docs/ORCHESTRATION-LOOP.md`
- `docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md`

But classify them as decisions/audits in README navigation.

## Priority fix list

1. Rewrite the first third of `README.md` around “what / why / system map,” before setup commands.
2. Convert internal doc references from backticked paths to Markdown links.
3. Add `docs/AGNT-SYSTEM.md` as the narrative explanation of the orchestration system.
4. Fix or remove the stale `.githooks`/tracked pre-commit hook claims.
5. Reorganize `pi/agent/bin/README.md` to remove duplicate Metrics headings and separate common flows from command inventory.
6. Label `docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md` as an audit/historical evaluation in the README.
7. Add a short prerequisites/assumptions section for deployment: Pi installed, direnv/Nix optional, `bd` available for repo workflow, provider keys optional by provider.

## Bottom line

The underlying documentation material is good, but the entry path is weak. The docs explain many parts correctly; they do not yet tell the story of the system. The highest-leverage improvement is to make `README.md` a true orientation document and add one narrative `agnt` overview that explains the project’s core idea before readers encounter commands and file paths.
