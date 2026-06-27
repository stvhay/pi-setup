# Self-Improvement Principles

This document is a design reference for changing the Pi configuration and its
agent workflows. It is not default runtime context. Load or cite it when
refactoring workflows, adding context mechanisms, evaluating self-improvement
changes, or deciding whether behavior belongs in prose, tools, evals, or task
state.

Self-improvement should make future work clearer and safer. It should not
accumulate vague instructions, hidden state, or overlapping abstractions.

## Core goals

Lessons learned by the agent system should remain:

- generalized at the right level of abstraction;
- efficiently findable by humans, tools, and models;
- reliably loaded only when relevant;
- separated by concern;
- free of conflicting directions;
- clean of stale material;
- resistant to intent drift; and
- correct, concise, and testable where practical.

## Pi context mechanisms

This repository manages reusable configuration for the Pi coding agent. The
tracked `pi/` tree is the deployable source of truth; live `~/.pi` is runtime
state. Prefer Pi idioms unless there is a clear reason to introduce a new
mechanism.

Important mechanisms:

- **Tasks** route work to model/tool defaults.
- **Skills** package reusable capabilities, methods, references, and helper
  tools for on-demand loading.
- **Prompts / prompt patterns** initiate explicit, argument-driven actions or
  preserve reusable prompt structures for evaluation before adoption.
- **Roles** define delegated-worker stance and output contracts.
- **Extensions and tools** provide deterministic behavior and lifecycle
  integration.
- **Packages** bundle related Pi assets for sharing or deployment.
- **SOUL.md** captures communication preferences only. It is not model
  identity, safety policy, workflow policy, or an override for project gates.

## Minimal architectural primitives

Use the fewest primitives needed, and make each primitive answer a different
question.

| Primitive | Question it answers | Notes |
|---|---|---|
| **Work item / bead** | What unit of work is scheduled, blocked, or complete? | The durable task-graph node. GitHub, if used, should be an adapter/export layer rather than a second agent-facing source of truth. |
| **Invocation message** | What work should a worker do now, with what context and allowed effects? | The clean interface between orchestration and workers. |
| **Result message** | What happened, with what evidence and downstream effects? | Should be structured enough for humans, tools, and later agents to inspect. |
| **Routing task** | Which model or execution default should handle this? | Examples: `review`, `planning`, `implementation`, `research`, `orchestration`. Do not use routing tasks as workflow docs. |
| **Prompt / action template** | What action is being explicitly initiated? | Verb-like. May select routing task, skills, roles, tools, and output contract. |
| **Skill / capability package** | What reusable method, expertise, references, or helper tools should be available? | Noun-like. A skill may be prose-heavy, tool-heavy, or mixed. It should not be the durable task state. |
| **Role** | How should a delegated worker behave and report? | Independent output contract, usually for subagents/peers. Roles should not become full workflows. |
| **Tool** | What deterministic operation should code perform instead of prose? | Orthogonal component usable by prompts, skills, orchestrators, and evals. |
| **Artifact** | What durable evidence or output lets downstream work continue? | Plans, reports, patches, metrics, verification logs, transcripts, and generated files. |
| **Eval / gate** | How do we check behavior or prevent unsafe transitions? | Prefer executable checks for invariants and regressions. |

A routing task named `orchestration` is only a model-selection category.
Orchestration as a system mechanism is the loop that selects ready work,
constructs invocation messages, dispatches workers, validates result messages,
updates artifacts/state, and schedules follow-up work.

## Natural language and formal mechanisms

Agent behavior can be implemented with natural language, formal language, or a
mix.

- Use **natural language** for judgment, heuristics, domain knowledge,
  trade-offs, and procedures that are still evolving.
- Use **formal mechanisms** for deterministic routing, validation, data
  extraction, metrics, queue operations, context generation, and repeated
  boilerplate.
- Expect smooth transitions. A capability may begin as prose in a skill, gain
  helper scripts, then move mostly into tools and evals while keeping a small
  skill shim for discovery and usage guidance.

Operational rule:

> If behavior must be repeatable, observable, or safely automated, prefer a
> tool, schema, eval, or state transition over more prose.

## Inspectable work backbone

Agent work should be represented by durable, inspectable, standard artifacts.
Chat is a user interface, not the system of record.

A production-grade agent workflow should tend toward this backbone:

```text
work graph -> invocation messages -> worker runs -> result messages -> artifacts -> state transitions
```

For nontrivial work, preserve enough information to answer:

- What was requested?
- Which context, model, role, skills, and tools were used?
- What side effects were allowed?
- What changed?
- What evidence supports the result?
- What downstream work became ready, blocked, or superseded?

Useful run artifacts include:

```text
runs/<run-id>/
├── invocation.yaml      # action, refs, constraints, allowed effects
├── result.yaml          # status, summary, evidence, outputs, follow-ups
├── artifacts/           # plans, reports, patches, generated files
├── metrics.json         # latency, tokens, cost, model, retries
├── verification.yaml    # checks run and results
└── transcript.jsonl     # optional raw event/worker log
```

Not every small task needs every file, but the conceptual contract matters.
The system should be restartable, debuggable, auditable, and capable of
idempotent retries where practical.

## Side effects and gates

Work should declare its allowed side effects. Hidden side effects are design
debt.

Common effect levels:

- **Read-only:** inspect and report.
- **Proposal:** produce a plan, report, or patch without mutation.
- **Workspace mutation:** edit files in an approved workspace.
- **State mutation:** update beads, metrics, run artifacts, or local queues.
- **External mutation:** push, deploy, open PRs, modify remote systems, or call
  external write APIs.

Higher-effect work needs stronger gates. Destructive, remote, security, and
irreversible operations require explicit approval regardless of convenience.

## Roles, skills, and prompts

Keep these independent:

- A **prompt/action template** initiates work: `/review <target>`.
- A **routing task** selects execution policy: `review`.
- A **skill** supplies method or expertise: `stamp-stpa`,
  `documentation-standards`, `systematic-debugging`.
- A **role** defines delegated-worker behavior: `documentation-reviewer`,
  `verifier`, `implementation-worker`.
- A **tool** performs deterministic pieces: route, invoke, grep, validate,
  evaluate, record metrics.

Example:

```text
Action: review docs/example.md
Routing task: review
Skills: documentation-standards, stamp-stpa
Role: documentation-reviewer
Allowed effects: read-only
Result: structured findings with file/path evidence
```

Do not duplicate a full workflow in every role. Roles may reference relevant
skills, but the reusable method belongs in the skill and the delegated output
contract belongs in the role.

## Beads and the agent work graph

A lightweight dependency-driven work graph is the natural backbone for agent
self-improvement. This repository uses Beads for that role.

Preferred direction:

- Treat Beads as the canonical agent-facing work queue/task graph when a project has opted into `.beads/`.
- Let ready beads initiate orchestration runs.
- Hide GitHub issue synchronization behind hooks, plugins, or export/import
  tools when external tracking is needed.
- Avoid making agents reason about two competing task trackers.

A simple operating loop is:

```text
wait for ready bead
construct invocation message
route/select worker
run Pi worker
capture result artifacts
validate and update bead graph
repeat
```

Before adopting Beads in another project, pressure-test reliability,
inspectability, worktree behavior, idempotency, GitHub integration needs, and
agent usability.

## Self-review and workflow refactoring

Self-improvement must include routine workflow refactoring. Otherwise contexts
will grow, scopes will drift, roles will duplicate, and old lessons will become
stale.

A self-review process should check both informal and formal modules:

- context architecture remains coherent;
- concerns are separated without gaps or overlaps;
- routing between tasks, prompts, skills, roles, and tools is clear;
- user preferences stay separate from safety and workflow policy;
- stale or conflicting instructions are removed;
- repeated prose boilerplate is considered for tooling;
- new tools and evals are added when they reduce ambiguity or operational
  cost;
- model-specific overlays are justified by evidence and eval-gated;
- third-party solutions are preferred when they are current, maintained, and
  fit the design better than local invention.

When creating or changing workflows, produce durable artifacts: design notes,
plans, audit reports, evals, or issue/bead records. Avoid relying on chat-only
state.

## Design heuristics

Use these heuristics when changing the system:

1. **Minimize primitives.** Do not create a new kind of thing when an existing
   primitive has the right responsibility.
2. **Keep interfaces explicit.** Prefer invocation/result messages and
   artifacts over implicit conversational state.
3. **Move deterministic behavior into tools.** Leave prose for judgment and
   context.
4. **Prefer small, composable capabilities.** Split skills or roles when they
   have multiple reasons to change.
5. **Make discovery cheap.** Names, descriptions, frontmatter, and generated
   inventories should let models find the right context without reading too
   much.
6. **Eval-gate policy changes.** Prompt overlays, routing changes, and safety
   gates need tests or documented evidence.
7. **Preserve safety boundaries.** `SOUL.md`, roles, prompts, skills, and model
   overlays must not weaken approval, verification, git, security, or external
   action gates.
8. **Prefer artifacts over memory.** If downstream work needs it, write it to a
   standard place in a standard shape.
