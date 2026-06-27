# Critique of Traditional Safety Methods

This reference explains why traditional probabilistic and barrier-based safety methods are inadequate for complex sociotechnical systems, and when to advocate for control-theoretic alternatives.

## The Fault Tree Fallacy

**Fault Tree Analysis (FTA)** models accidents as Boolean combinations of component failures. It assumes:
- Components fail independently
- Failure modes are known in advance
- Probabilities can be assigned to failure events
- Combining probabilities yields system failure probability

### Where Fault Trees Fail

**Component interactions**: FTA cannot capture accidents where components function correctly but interact unexpectedly. The Mars Polar Lander crashed because correctly-functioning software interpreted leg deployment vibration as touchdown. No component failed.

**Software**: Software doesn't fail probabilistically—it executes exactly as written. The problem is specification, not reliability. FTA treats software as a binary component (works/fails) but software hazards arise from unhandled cases, not random failures.

**Human operators**: Humans don't fail like components. Their behavior is context-dependent, goal-directed, and adaptive. Treating human error as an independent failure event with assignable probability misses why the error occurred.

**Coupling**: FTA assumes independence. In complex systems, failures propagate through shared resources, common cause, and feedback loops. Calculated probabilities based on independence assumptions are wrong, often by orders of magnitude.

**Unknown hazards**: FTA requires knowing all failure modes in advance. In novel or evolving systems, the hazards are precisely what you don't know yet. FTA finds what you put in; it cannot discover emergent hazards.

### When FTA Is Appropriate

FTA remains useful for:
- Well-understood component reliability analysis
- Hardware failure combination analysis
- Meeting regulatory requirements that mandate it
- Communication with stakeholders familiar with the method

Use it for component-level analysis within a larger STAMP framework, not as the primary safety method.

## The Swiss Cheese Model's Holes

James Reason's Swiss Cheese Model (SCM) visualizes accidents as trajectories passing through aligned holes in multiple defensive barriers. It has intuitive appeal and is widely taught.

### Where Swiss Cheese Fails

**Static barriers**: SCM implies barriers exist and have fixed "holes." In practice, barriers are processes performed by humans and systems whose behavior varies with context. The "holes" are not fixed—they emerge from system dynamics.

**Independence assumption**: SCM implies barriers are independent. In reality, barriers often share resources, personnel, or pressures. The same production pressure that creates a hole in one layer affects all layers.

**Linear causation**: SCM maintains the chain-of-events model. The trajectory metaphor implies a linear accident path. Complex accidents involve feedback loops, not linear progressions.

**Barrier-focused mitigation**: SCM suggests adding more barriers. But barriers without feedback degrade over time. Adding barriers without understanding why existing ones failed typically doesn't improve safety—the new barriers will develop holes for the same reasons.

**Stops analysis at proximate cause**: SCM explains how an accident penetrated defenses, not why the defenses were degraded. It doesn't naturally extend to organizational and design-level causes.

### When to Use SCM

SCM is useful for:
- Initial communication with audiences unfamiliar with systems thinking
- High-level visualization of defense-in-depth concept
- Rapid initial categorization of defense failures

Transition to STAMP/STPA for actual analysis.

## Probabilistic Risk Assessment Limitations

**Probabilistic Risk Assessment (PRA)** calculates system failure probability by combining component failure rates, human error probabilities, and common cause factors. It's mandated in nuclear, aerospace, and other industries.

### Where PRA Falls Short

**Probability assignment**: What's the probability of a software specification error? Of a manager deciding to launch despite engineer concerns? Of an operator misunderstanding a display? These aren't random variables—they're context-dependent outcomes. Assigning probabilities creates false precision.

**Rare event extrapolation**: PRA extrapolates from component failure data to predict rare system failures. But the most dangerous accidents often involve combinations never seen before. You cannot extrapolate from history to novel failure modes.

**Static analysis of dynamic systems**: PRA typically analyzes the system at a point in time. Systems migrate toward hazard over time as safety margins erode. A PRA showing acceptable risk at commissioning may not reflect current risk after years of accumulated workarounds.

**The organizational blind spot**: PRA struggles to incorporate organizational factors—regulatory capture, safety culture degradation, budget pressures. These are often dominant in major accidents but resist probabilistic treatment.

**Success theater**: PRA can show acceptable calculated risk while real risk is high. Pre-Challenger PRA showed acceptable O-ring failure probability based on past success. The actual risk was driven by factors (temperature dependence, normalization of deviance) outside the PRA model.

### When PRA Is Valuable

PRA works well for:
- Systems with well-characterized component failure rates
- Comparison of design alternatives (relative ranking)
- Identifying dominant failure contributors
- Meeting regulatory requirements

Use PRA outputs as inputs to STAMP analysis, not as the final word on safety.

## The "Human Error" Problem

All traditional methods treat human error as a cause. STAMP treats it as an effect.

### Traditional View
- Identify human action that led to accident
- Classify error type (slip, mistake, violation)
- Assign blame or recommend training/procedures
- Calculate human error probability for PRA

### STAMP View
- Identify the control action that was unsafe
- Trace why that action was taken given the controller's information and model
- Identify feedback, design, or organizational factors that made the error likely
- Design system changes that make the error impossible, detectable, or recoverable

**The critical difference**: Traditional analysis asks "who made the error?" STAMP asks "why did the system state make that error predictable?"

### Reframing Common "Human Errors"

| Traditional Attribution | STAMP Reframing |
|------------------------|-----------------|
| Operator failed to follow procedure | Procedure conflicted with production pressure; no feedback indicated deviation was hazardous |
| Pilot lost situational awareness | Displays failed to provide state information; workload design prevented attention allocation |
| Maintenance error | Procedure was ambiguous; verification step didn't catch error; time pressure from schedule |
| Management decision error | Safety information filtered before reaching decision-makers; incentives misaligned |

## Integrating Methods

STAMP doesn't completely replace traditional methods; it reframes them:

- Use **FTA** for component failure analysis within a STAMP control structure
- Use **PRA** for quantitative comparison of alternatives where probabilities are meaningful
- Use **HAZOP** as a structured prompt for identifying hazards (but trace causes via STAMP)
- Reference **Swiss Cheese** for initial stakeholder communication, then deepen analysis

The key is recognizing when traditional methods answer the wrong question, and using STAMP to ask the right one: not "what failed?" but "why did the control structure allow hazardous behavior?"
