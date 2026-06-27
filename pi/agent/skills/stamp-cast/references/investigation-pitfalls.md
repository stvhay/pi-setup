# Why Traditional Investigation Fails

This reference explains why traditional accident investigation approaches limit learning and lead to ineffective recommendations.

## Five Major Pitfalls

Traditional investigation suffers from:
1. Root cause seduction
2. Hindsight bias
3. Unrealistic views of human error
4. Focus on blame
5. Inappropriate causality models

## Root Cause Seduction

Humans have a psychological need for simple explanations. John Carroll calls this "Root Cause Seduction"—we want one cause we can fix and move on.

**The result:** Playing whack-a-mole. We fix symptoms while systemic causes persist. Enormous resources expended with little return.

### Example: Flixborough (1974)

A temporary bypass pipe ruptured, killing 28 people. Investigators focused on determining which of two pipes ruptured first.

**The official conclusion:** "A coincidence of unlikely errors in the design and installation of a modification...such a combination is very unlikely ever to be repeated."

**What was missed:** Running the plant without a qualified engineer on site, allowing unqualified personnel to make engineering modifications without safety evaluation, storing dangerous chemicals close to hazardous areas.

The Court of Inquiry stated that "shortcomings in day-to-day operations of safety procedures...had no bearing on the disaster." Others disagreed, and Flixborough led to major regulatory changes in Britain.

### The Whack-a-Mole Trap

When superficial analysis leads to superficial fixes:
- So many incidents occur they can't all be investigated deeply
- Only superficial analysis of a few is attempted
- Systemic factors persist
- More incidents occur

**The alternative:** Investigate a few incidents in depth, fix systemic factors, and the number of incidents decreases by orders of magnitude.

## Hindsight Bias

After knowing an accident occurred, it's psychologically impossible to understand how someone didn't predict it. Everything seems obvious in retrospect.

**Clue you're succumbing to hindsight bias:** Using "should have," "could have," or "if only."

### Example: SO2 Release

Investigation concluded: "The Board Operator should have noticed the rising fluid levels in the tank."

**What the operator actually had:**
- Turned off control valve; light indicated closed
- Flow meter showed no fluid flowing
- High-level alarm didn't sound (broken for 18 months)
- One alarm did sound, but had been going off spuriously monthly
- Another serious alarm went off elsewhere, which they investigated instead

The investigators, knowing the outcome, expected the operator to know what they couldn't have known.

### Avoiding Hindsight Bias

Instead of asking "What did they do wrong?" ask:
- **Why did it seem like the right thing to do at the time?**
- What information did they have?
- What was competing for attention?
- What pressures existed?

## Unrealistic Views of Human Error

Most investigations assume operator error causes most accidents. This assumption becomes self-fulfilling: start looking for operator error, find operator error, blame operator.

### The Bad Apple Theory

The "bad apple" theory—that accidents are caused by unreliable individuals—arose 100 years ago and was scientifically discredited 70 years ago. It persists because it's convenient.

### Typical Responses to "Human Error"

| Response | Why It Fails |
|----------|--------------|
| Punish the operator | Creates fear, hides information, next operator faces same conditions |
| Retrain operators | Doesn't address why error was predictable |
| Add more rules/procedures | May be impossible to follow or create new errors |
| Add more automation | May introduce new error types, reduce situational awareness |

### The Systems View

**Human error is a symptom, not a cause.** All behavior is affected by context.

To change human behavior, change the system:
- Examine equipment design
- Analyze procedure usefulness and appropriateness
- Identify goal conflicts and production pressures
- Evaluate safety culture impact

### The Following Procedures Dilemma

Operators face an impossible choice:
1. **Follow procedures rigidly** → May lead to unsafe outcomes when procedures don't fit reality; blamed for inflexibility
2. **Adapt procedures** → May take actions leading to incidents; blamed for violations

Procedures are written for idealized systems. Operators deal with actual systems that have drifted from design assumptions.

**Traditional approach:** Tell people to follow procedures, enforce them, assign blame for violations.

**Systems approach:** Monitor the gap between written procedures and practice, understand why it exists, update procedures accordingly.

## Blame is the Enemy of Safety

**Blame is a legal concept, not an engineering one.**

The goal of courts is to establish liability. The goal of engineering is to understand why accidents occur so they can be prevented.

### How Blame Hinders Learning

- People hide information to avoid blame
- Analysis stops at proximate actors (operators) who can't deflect attention
- Spotlight falls on aspects least likely to provide useful information
- Systemic factors are ignored

### Accusatory vs. Explanatory

| Accusatory (WHO + Why) | Explanatory (WHAT + Why) |
|------------------------|--------------------------|
| "The flight crew's failure to use engine anti-icing" | "Engine anti-icing was not used and was not required based on operations manual criteria for 'wet snow'" |
| Focuses on who was responsible | Focuses on what happened and why |
| Generates narrow recommendations | Generates broad recommendations |
| Stops investigation | Encourages further questions |

**The word "failure" is pejorative.** It implies judgment and terminates investigation.

Compare:
- "The captain's failure to reject the takeoff" (conclusion, judgment made)
- "The captain did not reject the takeoff" (observation, invites "why?")

### Things That Don't "Fail"

**Software doesn't fail.** It executes exactly as written. The question is why unsafe software was created—usually requirements flaws.

**Humans don't fail** (unless their heart stops). They react to situations. The question is why the situation made that reaction seem correct.

**Companies don't fail** (unless they go bankrupt). They're made of thousands of people. The question is why learning didn't occur—was information captured, retrievable, used?

## Inappropriate Causality Models

### The Chain of Events Model

Traditional analysis models accidents as chains of failure events:

```
E1 → E2 → E3 → E4 → Accident
```

This is Heinrich's Domino Model (1932) and underlies the Swiss Cheese Model.

### Limitations

**Arbitrary root cause selection:** Any event in the chain could be selected. The chain usually stops at a convenient person to blame—typically an operator near the time of loss.

**Example: Bhopal**

Event chain:
1. Worker washes pipes without slip blind
2. Water leaks into MIC tank
3. Operator doesn't open relief valve (gauges broken)
4. Explosion occurs
5. Relief valve opens
6. Protection devices don't prevent release
7. Wind carries MIC into populated area

The worker was identified as the "root cause" and put in jail.

**But why didn't he insert the slip blind?** He knew valves leaked but said it wasn't his job—that was maintenance's job, but the maintenance sheet had no such instruction. The shift supervisor who should have overseen this had been eliminated in cost-cutting.

**Systemic factors affecting all events:**
- Financial pressure led to cost-cutting
- Maintenance personnel cut in half
- Skilled workers left, replaced by unskilled
- Training standards reduced
- A safety audit two years prior identified all these issues but nothing was fixed

### The Independence Assumption

The chain model assumes events are independent except through direct causation. In reality, systemic factors affect all events simultaneously. The same financial pressure that led to the missing slip blind also led to broken gauges, non-functional protection devices, and inadequate staffing.

### Swiss Cheese Limitations for Investigation

While useful for communication, Swiss Cheese:
- Implies barriers are static with fixed "holes"
- Assumes barriers are independent
- Maintains linear causation model
- Focuses on "how" not "why"
- Suggests adding barriers rather than understanding why existing ones degraded

## Goals for Improved Investigation

Accident investigation should:

1. **Explain, not accuse** — Focus on what and why, not who
2. **Seek understanding, not root causes** — Accept multicausality
3. **Reconstruct pre-accident mental models** — Understand why actions seemed correct
4. **Identify systemic factors** — Look for what affected all components
5. **Generate system recommendations** — Change context, not just behavior
6. **Enable learning** — Create blame-free environment for information sharing

The goal is not to find someone responsible for the tragedy but to prevent future tragedies.
