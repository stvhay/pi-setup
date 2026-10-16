---
name: stamp-stpa
description: Use for prospective safety hazards, STPA, fault-tree or Swiss-cheese analysis; not generic critique.
---

# STAMP/STPA Systems Safety Analysis

STAMP treats losses as inadequate control of system behavior, not only chains of component failures. Ask which constraints, control actions, process models, or feedback paths are inadequate.

## Route correctly

Use STPA for prospective system-safety hazards and control constraints, not generic design critique. Honor an explicit named method; a requested fault tree or Swiss-cheese analysis is not silently replaced. Offer STPA as an optional extension.

| Requested output | Read selected skill |
|---|---|
| Investigate a specific systemic incident | `~/.pi/agent/skills/stamp-cast/SKILL.md` |
| Adversarial control/feedback scenarios | `~/.pi/agent/skills/stamp-stpa-sec/SKILL.md` |
| Argument/plan critique | `~/.pi/agent/skills/redteam/SKILL.md` |
| Software repair | `~/.pi/agent/skills/systematic-debugging/SKILL.md` |

Past incidents may inform prospective hazards without switching to CAST. Ask only when the requested deliverable is materially ambiguous; timing alone is not a router. Stabilize active incidents first. For shared theory only, read `~/.pi/agent/skills/stamp-base/references/stamp-foundations.md`; direct STPA entry needs no base gateway.

Carry scope, losses/hazards, control model, IDs, evidence and assumptions. Ask before expanding into another method; schemas are not interchangeable. Reuse loaded instructions and preserve prior constraints.

## Scope checkpoints

Ask only when uncertainty changes analysis:

- system boundary or unacceptable losses unclear
- controllers, authority, sensors, or feedback are unknown
- prospective versus retrospective framing is unresolved
- security threats require STPA-Sec
- multiple control-structure models produce materially different results

Do not checkpoint after every methodology step.

## Core analytical posture

1. **Define losses and hazards.** Hazards are system states that can cause stakeholder losses under worst-case environmental conditions.
2. **Model control structure.** Include human and automated controllers, controlled processes, control actions, feedback, and relevant environment.
3. **Find inadequate control.** Identify missing, unsafe, mistimed, or prolonged control actions.
4. **Trace scenarios.** Examine flawed process models, feedback, control paths, algorithms, coordination, and organizational pressures.
5. **Derive constraints.** Requirements must constrain behavior and trace to hazards or unsafe control actions.

Four conditions for safe control:

1. goals include safety constraints
2. controller has authority and means
3. process model matches reality
4. feedback is timely and accurate

Never stop at "human error." Ask what system design, incentives, process model, or missing feedback made the action reasonable or likely.

## Minimum workflow

### Step 1 — Frame system

- purpose and boundary
- stakeholders
- unacceptable losses (`L-*`)
- system hazards (`H-*`) linked to losses

### Step 2 — Model control structure

Map:

- controllers: human, automated, organizational
- controlled processes
- control actions
- feedback paths
- controller process models

Use [references/output-formats.md](references/output-formats.md) when a Depict diagram is requested.

### Step 3 — Identify unsafe control actions

For each control action, test four categories:

1. not provided when needed
2. provided when unsafe
3. wrong timing/order
4. applied too long or stopped too soon

Record controller, action, context, and linked hazards.

### Step 4 — Build causal scenarios

For each UCA, ask why it could occur:

- missing, delayed, wrong, or filtered feedback
- incorrect or stale process model
- flawed algorithm or decision rule
- control-path failure or actuator mismatch
- coordination and communication gaps
- conflicting goals, authority, incentives, or resource pressure
- system migration and normalization of deviance

### Step 5 — Derive constraints and verification

Write specific safety constraints or requirements (`SR-*`) linked to UCAs/hazards. State how design, test, monitoring, audit, or operations will verify each one.

Use [references/output-formats.md](references/output-formats.md) for machine-readable output.

## Time-boxing

| Time | Minimum useful output |
|---|---|
| 30 minutes | boundary, top losses/hazards, control sketch, key UCAs |
| 2 hours | losses, hazards, control structure, and UCA pass |
| Half day | causal scenarios, constraints, and verification plan |

State the achievable depth and scope down instead of pretending completeness.

## Reframing traditional analysis

Acknowledge the user's need, then add the control-theoretic view:

| Traditional request | STPA response |
|---|---|
| "What is the root cause?" | Identify control decisions and feedback gaps that made the state possible. |
| "It was human error." | Ask what system context made the action likely. |
| "Add another barrier." | First explain why existing controls degraded or failed. |
| "Give failure probability." | Use probabilities for suitable random failures; map contextual software/human control limits. |
| Existing fault tree/PRA | Reuse domain knowledge, then expose interactions and control gaps it misses. |

Offer STPA as an enhancement, not a ritual correction. Do not invent probabilities or claim traditional methods are useless in every context.

## Output quality

Human-readable analysis should present:

1. scope, stakeholders, losses, and hazards
2. control structure
3. unsafe control actions
4. causal scenarios
5. traceable safety requirements and verification
6. assumptions and unresolved information

Keep identifiers stable. Every hazard links to loss; every UCA links to hazard; every requirement links to a UCA or hazard.

## References

- `~/.pi/agent/skills/stamp-base/references/stamp-foundations.md` — shared theory when needed
- [references/stpa-methodology.md](references/stpa-methodology.md) — detailed STPA procedure
- [references/examples.md](references/examples.md) — worked examples
- [references/traditional-methods-critique.md](references/traditional-methods-critique.md) — comparison with event-chain methods
- [references/output-formats.md](references/output-formats.md) — YAML schema and Depict notation
