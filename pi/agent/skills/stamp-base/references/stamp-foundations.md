# STAMP Theoretical Foundations

## The Paradigm Shift

Traditional safety engineering treats accidents as chains of failure events—component A fails, which causes component B to fail, which leads to the accident. This model (rooted in Heinrich's domino theory and evolved through fault trees and event sequences) assumes:
- Accidents have identifiable root causes
- Complex system behavior can be decomposed into component behaviors
- Failures are independent events that can be assigned probabilities
- Adding redundancy and barriers improves safety proportionally

STAMP rejects all of these assumptions for complex sociotechnical systems.

## Accidents as Emergent Properties

In complex systems, accidents emerge from interactions among components that are each functioning as designed. The Three Mile Island operators followed their training. The Challenger managers followed their procedures. The components didn't fail—the system behavior that emerged from their interactions led to loss.

**Key insight**: Safety is an emergent property that cannot be analyzed by decomposition. You cannot determine whether a system is safe by analyzing whether each component is safe. Safety exists (or doesn't) at the system level.

## The Control Structure Model

STAMP models systems as hierarchical control structures:

```
┌─────────────────────────────────────────────────┐
│           System Development                     │
│   (Congress, regulators, company management)     │
└──────────────────────┬──────────────────────────┘
                       │ Safety constraints, resources
                       ▼
┌─────────────────────────────────────────────────┐
│           System Operation                       │
│     (Operations management, supervisors)         │
└──────────────────────┬──────────────────────────┘
                       │ Operating procedures, training
                       ▼
┌─────────────────────────────────────────────────┐
│           Physical Operation                     │
│   (Operators, automation, physical equipment)    │
└─────────────────────────────────────────────────┘
```

Each level:
- **Imposes constraints** on the level below
- **Receives feedback** from the level below
- **Maintains a process model** of what it's controlling

## The Four Conditions for Safe Control

For a controller to maintain safe control, four conditions must hold:

1. **Goals must align with safety** - The controller's objectives must include safety constraints (not just production/efficiency)

2. **Control actions must be available** - The controller must have the authority and means to impose necessary constraints

3. **The process model must be accurate** - The controller's understanding of the controlled process must match reality

4. **Feedback must be adequate** - Information about the controlled process must reach the controller with sufficient accuracy and timeliness

When any condition fails, accidents become possible even without component failures.

## Causation Categories

STAMP identifies several categories of control flaws that lead to accidents:

### Inadequate Enforcement of Constraints
- Safety constraints not enforced at higher levels
- Inadequate control actions from controllers
- Control actions not followed by actuators/lower levels
- Inadequate coordination among controllers

### Inadequate Process Models
- Model doesn't match reality from the start
- Model correct initially but becomes incorrect over time (model drift)
- Feedback missing or inadequate to update model
- Feedback delays cause model to lag reality

### Inadequate Feedback/Communication
- Not provided in the system design
- Communication flaw (noise, delay, lost message)
- Information provided but not received/used
- Feedback generated too slowly to be useful

## Why "Human Error" Is the Wrong Terminus

When analysis identifies "human error" as a cause, it has identified a symptom, not a cause. The relevant questions become:
- What in the system design made that error predictable?
- What feedback was missing or misleading?
- What conflicting pressures existed (safety vs. production)?
- What mental model did the operator have, and why was it wrong?
- What constraints should have made the error impossible or recoverable?

The goal is not to find someone to blame but to understand why the system state was such that a reasonable person would take the action they took.

## Migration to Hazard

Systems rarely jump from safe to accident. Instead, they migrate toward hazard through:

1. **Performance pressure** - Optimization of efficiency erodes safety margins
2. **Normalization of deviance** - Small violations become accepted practice
3. **Documentation drift** - Procedures no longer match actual operations
4. **Model decay** - Understanding of the system degrades as personnel change
5. **Reduced redundancy** - "Nothing bad happened" justifies removing safeguards

This migration is invisible to traditional analysis until an accident reveals it.

## Implications for Design

STAMP-informed design:
- Identifies required safety constraints early (before component design)
- Designs control structures that can enforce those constraints
- Ensures feedback paths exist for all critical process states
- Anticipates model degradation and builds in model-updating mechanisms
- Treats human controllers as part of the system, not external error sources
- Designs for graceful degradation rather than binary success/failure
