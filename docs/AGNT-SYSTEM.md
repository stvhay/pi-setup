# The agnt System

`agnt` is a small control layer around Pi. Pi remains the interactive runtime; `agnt` supplies repeatable routing, context composition, artifacts, metrics, and optional orchestration.

## Problem

A capable model runtime does not by itself define:

- which model should handle a task;
- which instructions and skills should enter a worker context;
- how delegated results become durable evidence;
- when an agent may act versus request a human decision; or
- how outcomes should change future routing policy.

Encoding those choices in prompts makes them hard to inspect and easy to drift. `agnt` keeps durable policy in tracked files and leaves ordinary work in Pi.

## Design thesis

Use the smallest surface that fits the work:

1. Work directly in the current Pi session by default.
2. Track code-changing work in Beads.
3. Route delegated work with `agnt route`, then execute it through Pi's `subagent` tool.
4. Select optional run bundles only when durable orchestration evidence is needed.
5. Keep private runtime data out of Git; commit only reviewed policy and code changes.

Concern seams stay explicit: `agnt_lib` owns deterministic domain logic; the `agnt` CLI adapts it for humans, CI, and headless callers; Pi extensions own lifecycle, UI, session, and provider integration; typed tools are thin agent-facing adapters. Do not duplicate domain logic across these surfaces.

## Core primitives

These concepts remain separate:

- **Bead:** durable work item, dependency, blocker, decision, and closeout state.
- **Task:** routing policy for model selection and risk/budget constraints.
- **Action:** explicit operation binding a task, skills, role, effects, and output contract.
- **Skill:** reusable method loaded when relevant.
- **Role:** delegated-worker stance and reporting contract.
- **Tool or eval:** deterministic operation or validation.

A prompt or role does not replace a skill method, Bead state, approval gate, or verification command.

## Context composition

`agnt instructions` composes global instructions, project instructions, and optional model/role supplements from least to most specific. Skills stay discoverable by compact metadata and load their full method only when triggered.

This keeps the root context small while preserving exact project and safety rules. See [Architecture](ARCHITECTURE.md) for file boundaries and data flow.

## Delegation

Interactive delegation uses one path:

1. Run `agnt route` for task, risk, budget, and source access policy.
2. Use `--access repository` when the child needs filesystem evidence; repository access requires agentic mode.
3. Use `--access self-contained` and `mode: "one-shot"` only for a complete cold packet.
4. Call `subagent` with `agent` omitted and copy route-generated model, mode, access, and any metered evidence/limits.
5. Prefer qualified subscription routes. Metered agentic repository work requires explicit quality/capability justification, estimated cost, aggregate budget, and bounded children.
6. Use the `tasks` array for parallel peers.

The tracked subagent observer records compatible payload-free metrics and persists complete child results under private runtime storage. Internal eval and run-bundle workers retain a headless Pi primitive because they execute outside a live Pi tool context; that primitive is not a second public peer command.

## Normal lifecycle

For direct coding:

1. Run `bd prime` and inspect ready work.
2. Confirm or create a Bead, then link the current session with `agnt work direct-start`. Session/Bead authority is an append-only private local quality ledger; matching Langfuse scores are best-effort evidence only.
3. Inspect, edit, and verify in Pi.
4. Commit task-owned changes.
5. Run `agnt work direct-closeout <id> --outcome success --reason "<reason>"` to append and read back local explicit success, close the Bead, export and verify `.beads/issues.jsonl`, and create its separate portable-state commit. Langfuse unavailability does not block this path. Use `agnt improve outcome` separately for non-success or manual/repair recording.
6. Hand off ready follow-up work in a fresh session when needed.

For optional orchestration, action templates may create private run bundles containing invocation metadata, result evidence, artifacts, and metric references. `agnt runs invoke` and `agnt work run` execute those bundles through the internal headless worker. See [Run Artifacts](RUN-ARTIFACTS.md).

Thinking calibration uses observable task features, never model self-confidence: phase, effect severity, ambiguity, novelty, reversibility, testability, and source breadth. Unknown, consequential, architecture, implementation, security, and final-verification work stays high/xhigh. Only exact mechanical inventory, formatting, and documentation profiles may be replayed below high. The tracked [thinking-level calibration](../pi/agent/evals/thinking-level-calibration/README.md) requires quality parity and measured latency benefit before task defaults change; current evidence changed no defaults.

## Human decisions and safety

Direct Pi work uses normal workspace tools. Structured orchestration remains opt-in.

Consequential actions use dedicated Beads-backed tools:

- `ticket_question` for durable blocking questions;
- `ticket_approval` for informed approval gates; and
- `ticket_decision_resolve` for recording human outcomes.

The generic ticket gateway lists and inspects work, creates drafts, and shows trees; it does not duplicate human decision flows. Assigned-agent review results normalize to evidence. Transient `ask` answers pass over stdin to deterministic normalization and return as session-local constraints, while durable questions and approvals store pointer-backed `answer` and `authorization` constraints in Beads. Editor/Nvim review and BetterWright human-takeover results cross `agnt quality normalize-result` only as scope-bound metadata with safe relative artifact/resumption paths, sensitivity-bounded EvidenceRefs, human/session provenance, and explicit completed/partial/lost/uncertain state. Native editor/browser UX and policy stay external; saving or manually executing work is neither acceptance nor authorization. These categories never imply result acceptance, and normalized records grant no effects. Approval requests fingerprint full request identity, including informed preview and target, then verify it against an append-only Beads provenance event; approving changed or unbound scope requires a new preview/request. Capability approvals optionally store one exact action/effects/model/thinking/toolset/context-policy/proof/rollout/expiry envelope in the decision Bead. Only resolved human-UI decision state can activate that ceiling; expiry or revocation updates state below it and returns no effects. Orchestration resolves one canonical approval reference with bounded Beads lookup before dispatch; copied `metadata.pi.approved` and `humanApproval` can neither substitute for nor widen active grant state. `resolve_orchestration_metadata` retains compatibility output while exposing canonical authority for downstream migration.

An exact initial implementation approval may cover reversible local branch/worktree setup, task-owned commits, one guarded local integration bound to target checkout/branch plus expected target HEAD/source SHA, verified cleanup, tracked/config-controlled deletions, verified local-live or explicitly designated test/staging deployment, and one ordinary branch push after successful Bead closeout under project policy. Push authority must bind canonical remote/branch identity, approved base SHA, bounded candidate-selection rule, and expected remote state; requires clean tracked and final-gate/portable-state evidence; permits only one normal new or fast-forward branch refspec; is consumed by the first attempt; and verifies remote SHA equality. Rejection, cancellation, timeout, identity mismatch, changed scope, unexpected divergence, failed closeout, or failed verification blocks mutation. PR actions, protected/production branches, force, tags, releases, merges, remote deletion, destructive rollback, history rewrite, hook installation, and other separately gated actions remain outside inherited approval. Production and unknown targets require a new explicit approval.

## Feedback loop

Both subagent and internal headless workers emit the same normalized metric shape. Private consolidation and review can then adjust routing policy, prompts, model metadata, or evals:

```text
execute -> record -> annotate -> consolidate -> review -> change policy -> eval
```

Telemetry is evidence, not authority. Human outcome labels remain separate from objective execution status, and raw prompts, outputs, IDs, URLs, credentials, and private traces stay outside tracked source.

## Relationship to Pi

Pi provides sessions, providers, tools, extensions, skills, and interaction. Archimedes provides subagent transport and live progress. Beads provides durable work state. `agnt` provides deterministic policy, checks, artifacts, and headless adapters; it does not replace Pi or own long-lived runtime automation.

## Further reading

- [Architecture](ARCHITECTURE.md) — subsystem boundaries and data flow.
- [Command Reference](../pi/agent/bin/README.md) — exact CLI syntax.
- [Run Artifacts](RUN-ARTIFACTS.md) — invocation and result contracts.
- [Self-Improvement Loop](SELF-IMPROVEMENT.md) — metrics and policy feedback.
