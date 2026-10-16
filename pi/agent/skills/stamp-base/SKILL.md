---
name: stamp-base
description: Use when routing STAMP analysis or when shared foundations are needed before STPA, CAST, or STPA-Sec.
---

# STAMP Foundations

## Overview

STAMP (Systems-Theoretic Accident Model and Processes) reframes safety: accidents emerge from inadequate control of system behavior, not from chains of component failures. Instead of asking "what broke?", ask "what constraints were missing or inadequate?"

This base skill provides:
- Theoretical foundations for all STAMP analysis
- Routing to the appropriate methodology skill
- Shared concepts used across STPA, CAST, and STPA-Sec

## Routing by requested outcome

Choose the requested outcome and object before a method. “Failure,” “risk,” “review” and “root cause” alone do not select STAMP. Honor an explicit named method; offer alternatives without silently substituting STPA for fault trees or STPA-Sec for STRIDE.

| Requested output | Read selected skill |
|---|---|
| Software diagnosis/repair | `~/.pi/agent/skills/systematic-debugging/SKILL.md` |
| Completed-work learning | `~/.pi/agent/skills/retrospective/SKILL.md` |
| Agent/harness lifecycle decision across runs | `~/.pi/agent/skills/agent-retrospective-loop/SKILL.md` |
| Recovery UX after agent failure | `~/.pi/agent/skills/failure-choreography/SKILL.md` |
| Argument/plan critique | `~/.pi/agent/skills/redteam/SKILL.md` |
| Concrete diff correctness | `~/.pi/agent/skills/requesting-code-review/SKILL.md` |
| Prospective safety hazards/constraints | `~/.pi/agent/skills/stamp-stpa/SKILL.md` |
| Systemic incident/near-miss explanation | `~/.pi/agent/skills/stamp-cast/SKILL.md` |
| Adversarial control/feedback analysis | `~/.pi/agent/skills/stamp-stpa-sec/SKILL.md` |

Ask one targeted question only if interpretations materially change the deliverable. Timing/adversarial scope select a STAMP method only after systemic control analysis is established. Stabilize an active incident before analysis. Theory-only work stays here.

Carry scope, evidence, requested output and constraints. Reuse an already-loaded specialist; direct specialist entry needs no base preload or return routing loop. Ask before expanding scope; the selected skill's approval/stop gates still apply.

## The Paradigm Shift

If you're new to STAMP, here's what this methodology does:

**If you're familiar with fault trees, event chains:**
STAMP flips the question. Instead of "what failed?" (component fault tree), we ask "what constraints prevented the hazard?" (control structure analysis). This captures how systems migrate toward danger over time.

**If you're familiar with systems thinking, control loops:**
STAMP formalizes your intuition. Every system has controllers (human and automated), controlled processes, feedback, and control actions. Accidents happen when control is inadequate.

**If you're designing something new:**
For prospective systemic hazards, read `~/.pi/agent/skills/stamp-stpa/SKILL.md` to derive control constraints before losses occur.

**If you're investigating an incident:**
For systemic incident explanation, read `~/.pi/agent/skills/stamp-cast/SKILL.md` to analyze why the control structure failed.

## Core Concepts

See [references/stamp-foundations.md](references/stamp-foundations.md) for:
- Accidents as emergent properties
- The control structure model
- Four conditions for safe control
- Causation categories
- Why "human error" is the wrong terminus
- Migration to hazard

## Training & Onboarding

For users new to STAMP, see [references/training-intro.md](references/training-intro.md):
- Mapping STAMP to familiar concepts (fault trees, control loops)
- Quick paths for different user contexts (safety, incident response, compliance)
- Handling resistance and common objections

## Quick Reference

| Traditional Framing | STAMP Reframing |
|---------------------|-----------------|
| "Component failed" | "Control constraint was missing or inadequate" |
| "Human error" | "Why did the system make that error likely?" |
| "Root cause found" | "What feedback/constraints would prevent recurrence?" |
| "Add more barriers" | "Fix the control structure" |
| "Calculate failure probability" | "Map control loops and find gaps" |

**Four conditions for safe control:**
1. Goals align with safety (not just production)
2. Control actions available (authority + means)
3. Process model accurate (controller understands reality)
4. Feedback adequate (timely, accurate information)

## Output Formats

STAMP analysis serves different audiences. See [references/output-formats.md](references/output-formats.md) for:
- **Executive Summary** — Decision-focused, business impact
- **Engineering Specification** — Actionable requirements with traceability
- **Incident Report** — Compliance-ready, methodology-documented
- **Quick Brief** — Verbal settings, alignment conversations

For Depict diagrams, read `references/depict.md` for shared grammar. Specialists retain their own examples, limitations and schemas; diagram-free analysis need not load it.

## Combined Workflows

Only when the next analytical outcome is requested/approved, use the exact specialist paths above:
- **STPA → STPA-Sec**: Run STPA first for safety hazards, then STPA-Sec to add adversarial scenarios to the same control structure
- **STPA-Sec → STPA**: Start with security threats, then extend to full safety analysis
- **CAST → STPA / STPA-Sec**: After incident analysis, run prospective analysis on the redesigned control structure

Carry boundary, losses/hazards, controllers, actions/feedback, stable IDs, evidence, assumptions and unresolved questions. Reuse the control model, but schemas are not interchangeable. Preserve existing constraints; a new method adds its distinct analysis, not an automatic full pipeline.

## Related Skills

- **stamp-stpa** — Prospective hazard analysis (what could go wrong?)
- **stamp-cast** — Retrospective incident analysis (what went wrong?)
- **stamp-stpa-sec** — Security-focused analysis (adversarial scenarios)
