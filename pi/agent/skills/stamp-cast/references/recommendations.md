# Generating Recommendations

Once the analysis is complete, generating recommendations should be straightforward—each identified flaw in the control structure implies a recommendation to fix it.

## Core Principle

**Recommendations must strengthen the control structure, not just add rules for operators.**

The goal is systemic improvement, not blame assignment. If your recommendations focus primarily on retraining operators or adding procedures, you haven't analyzed deeply enough.

## Why CAST Generates More Recommendations

CAST typically generates more recommendations than traditional analysis. This is a feature, not a bug:

- Traditional analysis seeks a "root cause" and generates 1-3 recommendations
- CAST identifies multiple control structure flaws, each requiring a fix
- More recommendations = more learning = fewer future accidents

**Objection:** "Too many recommendations is overwhelming."

**Response:** This is a logistics problem, not a reason to learn less. Prioritize and phase implementation—don't omit valid recommendations because they're inconvenient.

## Prioritization Criteria

Not all recommendations require immediate implementation:

| Category | Characteristics | Timeline |
|----------|-----------------|----------|
| **Immediate** | Low effort, high impact, prevents recurrence | Days to weeks |
| **Short-term** | Moderate effort, clear path, addresses proximate factors | Weeks to months |
| **Long-term** | Significant effort, systemic change, addresses organizational factors | Months to years |

Difficulty of implementation is not an excuse to omit a recommendation. A recommendation to "establish new oversight agency" may take years but should still be documented.

## Weak vs. Strong Recommendations

| Weak Recommendation | Why It Fails | Strong Alternative |
|--------------------|--------------|-------------------|
| Retrain operators | Doesn't address why error was likely; next operator faces same conditions | Redesign interface, improve feedback, fix procedure usability |
| Add more procedures | May be unfollowable, conflict with existing procedures, or add workload | Fix usability of existing procedures; eliminate conflicting requirements |
| Punish/discipline operator | Hides information, creates fear, next person faces same context | Change the system context that made error predictable |
| "Use the reporting system" | Ignores why they don't use it | Fix reporting system's usability; ensure feedback loop |
| Add more automation | May introduce new error types, reduce situational awareness | Human-centered design; appropriate automation with feedback |
| "Be more careful" | Not actionable; doesn't change anything | Specific design changes that make care unnecessary |

## The Human Error Trap

**Human error is a symptom, not a cause.**

When you find yourself writing a recommendation that targets operator behavior, stop and ask:

1. Why did this action seem correct to them at the time?
2. What information was missing or misleading?
3. What pressures or incentives influenced the behavior?
4. What design changes would make the error impossible, detectable, or recoverable?

Transform the recommendation from "operators should..." to "the system should..."

### Reframing Examples

| Operator-Focused | System-Focused |
|------------------|----------------|
| "Pilots should monitor altitude more carefully" | "Provide automated altitude alerting; redesign display to make altitude deviations salient" |
| "Maintenance should follow procedures" | "Redesign procedures for actual conditions; provide verification steps; eliminate time pressure" |
| "Operators should use incident reporting" | "Redesign reporting interface; provide feedback on reports; allocate time for reporting" |

## Three Requirements for Effective Implementation

Recommendations without follow-through are worthless. Every recommendation needs:

### 1. Assigned Responsibility

- Who specifically is responsible for implementation?
- Do they have authority and resources?
- Is there accountability for completion?

### 2. Verification

- How will you know it was implemented?
- What evidence demonstrates completion?
- Who verifies?

### 3. Effectiveness Feedback

- How will you know if it worked?
- What metrics or indicators will you track?
- When will you evaluate?

## Continuous Improvement Loop

Subsequent accidents provide feedback on previous recommendations:

- Was the original analysis flawed?
- Were assumptions about effectiveness incorrect?
- Did other changes thwart the intended improvement?
- Did the fix create unforeseen consequences?

Use CAST on future incidents to evaluate whether previous recommendations were effective. This closes the learning loop.

## Common Recommendation Patterns

### For Feedback Failures
- Add sensors, displays, or alerts
- Redesign information presentation
- Reduce noise/false alarms that cause alert fatigue
- Ensure feedback reaches decision-makers

### For Process Model Flaws
- Improve training with realistic scenarios
- Provide real-time state information
- Design interfaces that make system state obvious
- Update documentation to match actual system

### For Coordination Failures
- Clarify responsibilities explicitly
- Design communication channels
- Create coordination mechanisms
- Resolve conflicting authority

### For Systemic Pressures
- Realign incentives with safety
- Allocate adequate resources
- Address production pressure at source
- Establish safety as genuine priority (not just slogan)

## Avoid Jury-Rigging

Short-term fixes should not delay comprehensive solutions.

It's appropriate to implement immediate mitigations while developing permanent fixes. But don't let "we put in a workaround" become an excuse for never addressing the underlying control structure flaw.

## Output Format

For each recommendation:

```
Recommendation: [Specific action]
Addresses: [Which control structure flaw this fixes]
Assigned to: [Responsible party]
Verification: [How to confirm implementation]
Effectiveness measure: [How to know if it worked]
Priority: [Immediate / Short-term / Long-term]
```
