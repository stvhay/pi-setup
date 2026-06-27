# STAMP Training Introduction

This module helps users unfamiliar with STAMP understand the paradigm shift before diving into analysis.

## Who Is This For?

Use this material when the user:
- Asks "what is STAMP?" or "how is this different from traditional safety analysis?"
- Seems unfamiliar with systems-theoretic thinking
- Uses traditional framing (fault trees, root causes, human error as terminus)
- Needs conceptual grounding before methodology

## The Core Insight

**Traditional safety thinking:** Accidents happen when things break. Find what broke, fix it, add barriers.

**STAMP thinking:** Accidents happen when control is inadequate. Systems don't need to "break" to fail—they drift toward hazard through normal operation. Find where control was missing or inadequate, strengthen the control structure.

## Mapping to Familiar Concepts

### For Safety Practitioners (Fault Trees, Risk Matrices)

You know how to trace failure chains: Component A fails → Component B fails → Accident.

**STAMP's shift:** Instead of asking "what failed?", ask "what constraints should have prevented this hazardous state?" The answer often isn't a broken component—it's missing feedback, conflicting goals, or drifting mental models.

| You're Used To | STAMP Equivalent |
|----------------|------------------|
| Fault tree | Control structure diagram |
| Failure probability | Control adequacy analysis |
| Root cause | Multiple contributing factors (no single root) |
| Barrier | Safety constraint |
| Human error (terminus) | Human error (starting point for "why?") |

**Key insight:** Fault trees assume independence between events. Real systems have shared resources, common pressures, and coupled feedback. STAMP captures these.

### For Systems Architects (Control Loops, Feedback)

You already think in control loops. STAMP formalizes this for safety.

Every system has:
- **Controllers** (human and automated decision-makers)
- **Controlled processes** (what's being managed)
- **Control actions** (commands, authority, resources flowing down)
- **Feedback** (sensor data, reports, information flowing up)

**STAMP's insight:** Accidents happen when any of these four conditions fail:
1. Controller's goals don't include safety
2. Controller lacks authority/means to act
3. Controller's model of the process is wrong
4. Feedback is missing, delayed, or incorrect

**Your advantage:** You already draw these diagrams. STAMP just asks: "Where could control be inadequate?"

### For Incident Responders (Under Pressure)

You need answers fast. Someone's asking "what happened?" and "who's responsible?"

**STAMP's value:** It gives you defensible analysis. Single "root causes" get challenged; control structure analysis holds up because it shows the system of decisions, not just one person's action.

**Quick path:**
1. Sketch who controlled what (5 min)
2. Identify where feedback was missing (10 min)
3. Explain why actions seemed correct at the time (15 min)
4. You now have a systemic explanation, not a blame target

**Handling pressure:** "I can give you something more defensible than a root cause: the control structure gaps that made this incident likely. That's what will hold up when stakeholders push back."

### For Compliance Managers (Audits, Artifacts)

You need documentation that satisfies regulators. They may ask for "root cause" or "failure probability."

**STAMP's output maps to compliance needs:**

| Regulator Wants | STAMP Provides |
|-----------------|----------------|
| Root cause analysis | Multi-factor causal analysis (more thorough) |
| Corrective actions | Safety requirements with verification criteria |
| Risk assessment | Hazard analysis with control structure mapping |
| Evidence of due diligence | Systematic methodology with traceable artifacts |

**Handling requests:** "I can give you something that exceeds root cause requirements: a systematic analysis showing all contributing factors and specific control improvements. Auditors prefer thoroughness."

## Common Resistance and Responses

| They Say | You Respond |
|----------|-------------|
| "This is too complicated" | "Start with just the control structure sketch. That alone reveals gaps traditional analysis misses." |
| "We don't have time for this" | "Quick version: sketch controllers, identify missing feedback, explain why actions seemed right. 30 minutes." |
| "Our regulator wants root cause" | "STAMP gives you more than root cause—it gives you the system of causes. That's more defensible." |
| "We already know it was human error" | "That's where we start, not where we stop. What made that error likely? That's where the fixes are." |
| "Just add more training" | "Training erodes under pressure. Let's find controls that make the safe path the easy path." |

## Starting Points by Context

| Context | Start Here |
|---------|------------|
| Designing new system | stamp-stpa → identify hazards before they're built in |
| Investigating incident | stamp-cast → understand why control was inadequate |
| Security threat modeling | stamp-stpa-sec → map adversarial scenarios to control paths |
| General safety concern | stamp-base routing → "Has loss already occurred?" |

## Minimum Viable Understanding

If you take away one thing:

> **Accidents aren't caused by broken parts. They're caused by inadequate control. Find where control is missing—in goals, authority, process models, or feedback—and you find where to improve the system.**

That's STAMP. Everything else is methodology for applying this insight systematically.
