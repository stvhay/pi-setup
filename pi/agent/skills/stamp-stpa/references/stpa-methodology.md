# STPA Methodology

STPA (System-Theoretic Process Analysis) is the hazard analysis technique derived from STAMP. It identifies hazardous scenarios by systematically examining the control structure for unsafe control actions and their causes.

## Step 0: Define Purpose and Scope

Before beginning STPA, establish:

**System boundary**: What's included in the analysis? Typically includes the physical system, operators, automation, and relevant organizational levels.

**Losses**: What outcomes are unacceptable? Include:
- Human losses (death, injury)
- Equipment/environmental damage
- Financial losses
- Mission failure
- Reputation/regulatory consequences

**Hazards**: System states or conditions that, combined with certain environmental conditions, lead to losses. Hazards are *states*, not events. Example: "Aircraft violates minimum separation" is a hazard; "Mid-air collision" is a loss.

## Step 1: Model the Control Structure

Create a hierarchical diagram showing:
- All controllers (human and automated)
- All controlled processes
- Control actions (downward arrows)
- Feedback (upward arrows)

### Control Structure Elements

**Controllers**: Entities that regulate behavior of controlled processes
- Human: operators, supervisors, managers, regulators
- Automated: software, PLCs, interlocks, automated systems

**Controlled Processes**: Systems or processes being regulated
- Physical processes (reactor, vehicle, patient)
- Human processes (other operators' behavior)
- Organizational processes (subordinate units)

**Control Actions**: Commands/actions from controllers
- Direct control (turn valve, send command)
- Indirect control (set policy, allocate resources, grant approval)

**Feedback**: Information flowing to controllers
- Sensor data, displays, reports
- Verbal communication
- Written procedures, documentation

### Modeling Tips

- Include all levels (operational, tactical, strategic)
- Show both technical and organizational controllers
- Identify shared or redundant control paths
- Mark feedback delays where significant
- Note where controllers share responsibility

## Step 2: Identify Unsafe Control Actions (UCAs)

For each control action, systematically examine four types of unsafe control:

| Type | Question |
|------|----------|
| Not providing | Is there a scenario where NOT taking this action leads to a hazard? |
| Providing causes hazard | Is there a scenario where taking this action causes a hazard? |
| Wrong timing/order | Can the action be hazardous if taken too early, too late, or out of sequence? |
| Wrong duration | Can the action be hazardous if stopped too soon or applied too long? |

### UCA Structure

Every Unsafe Control Action has four parts:

| Part | Description | Example |
|------|-------------|---------|
| **Source Controller** | The controller that provides (or should provide) the action | Driver, ACC, Pilot, Software Controller |
| **Type** | Whether action is provided, not provided, or has timing/duration issues | does not provide, provides, provides too late |
| **Control Action** | The specific command or action | brake command, Park cmd, go-around |
| **Context** | Conditions that make this action (or lack of action) hazardous | when obstacle ahead, before exiting vehicle, when unstabilized |

Plus **traceability** to the hazard it can cause: `[H-1]`

### UCA Format

Document each UCA using the four-part structure:
```
UCA-[ID]: [Source Controller] [Type] [Control Action] when [Context] [Hazard]
```

Example:
```
UCA-1: Flight crew does not initiate go-around when aircraft is unstabilized below 1000 feet [H-1]
        └─Controller─┘ └──Type──┘ └──Control Action──┘ └────────────Context────────────────┘
```

More examples:
```
UCA-2: Driver does not provide Park cmd before exiting vehicle on slope [H-2]
UCA-3: ACC provides brake command when road is clear and no obstacle ahead [H-3]
UCA-4: Pump delivers dose too early, before lockout period expires [H-1]
```

### Context Matters

UCAs are context-dependent. "Pilot initiates thrust reverser" is:
- Safe: after touchdown on runway
- Unsafe: during flight (causes hazard)
- Unsafe: before touchdown (causes hazard)

Analyze across operational modes, system states, and environmental conditions.

## Step 3: Identify Causal Scenarios

For each UCA, trace the reasons it could occur. The causal scenario diagram below shows all paths that can lead to unsafe control:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CONTROLLER                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Inadequate Control Algorithm                                             │    │
│  │ • Flaws in creation, modification, adaptation                           │    │
│  │ • Software/logic errors                                                  │    │
│  │ • Inadequate safety margins                                              │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ Process Model Inconsistent with Process                                  │    │
│  │ • Incorrect beliefs about:                                               │    │
│  │   - Current process state         - Required vs actual control action   │    │
│  │   - How process is changing       - How process behaves                 │    │
│  │ • Flaw in model update: never received, incorrect, not sent, delayed    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    │ Control Actions
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Control path issues:                                                             │
│ • Inadequate operation (action not executed, incorrectly executed)              │
│ • Inappropriate, missing, or delayed communication                               │
│ • Conflicts (multiple controllers sending conflicting commands)                  │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          CONTROLLED PROCESS                                      │
│                                                                                  │
│ Component failures, changes over time, unhandled disturbances                   │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    │ Feedback
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Feedback path issues:                                                            │
│ • Sensor failure or incorrect sensor operation                                   │
│ • Inadequate sensor (wrong type, range, resolution)                             │
│ • Missing feedback (no sensor, feedback not sent)                               │
│ • Delayed feedback                                                               │
│ • Measurement inaccuracies                                                       │
│ • Feedback corrupted or modified                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Use the STAMP causal categories:

### Why Might a Needed Control Action Not Be Taken?

1. **Controller doesn't know action is needed**
   - Feedback not provided by system design
   - Feedback delayed
   - Sensor failure
   - Display failure or obscured
   - Operator distracted or task-saturated

2. **Controller knows but doesn't act**
   - Conflicting goals (production vs. safety)
   - Inadequate training
   - Procedure doesn't require action
   - Authority unclear

3. **Action taken but not executed**
   - Actuator failure
   - Communication path broken
   - Action blocked by interlock (correctly or incorrectly)

### Why Might an Unsafe Control Action Be Taken?

1. **Controller has incorrect process model**
   - Training error
   - Previous feedback was incorrect
   - Feedback stopped but process changed
   - Interface design creates false understanding
   - Reliance on automation that failed silently

2. **Controller follows incorrect procedure/policy**
   - Procedure conflicts with safety
   - Procedure outdated
   - Procedure ambiguous

3. **Controller makes mode confusion error**
   - System in different state than believed
   - Automation mode not apparent

### Why Might Timing/Duration Be Wrong?

- Feedback delays
- Processing delays
- Incorrect time constants in controller's model
- Lack of timing feedback
- Communication queue delays

## Step 4: Generate Safety Requirements

Transform each causal scenario into a safety constraint or requirement:

| Causal Scenario | Safety Requirement |
|-----------------|-------------------|
| Pilot may not notice unstable approach due to task saturation | SR-1: System shall provide automated unstable approach warning below 1000 feet |
| Controller's model may drift as system degrades | SR-2: Maintenance status shall be visible to operators on primary display |

Requirements should be:
- **Traceable** to specific UCAs and scenarios
- **Verifiable** in the implemented system
- **Actionable** for designers

## Step 5: Develop Controls/Mitigations

For each safety requirement, identify potential design solutions:

**Eliminate the hazard**: Change design so the hazardous state is impossible

**Prevent hazard**: Add constraints that prevent hazardous control actions
- Interlocks
- Software constraints
- Physical constraints

**Reduce hazard exposure**: Limit time in or near hazardous states

**Provide information**: Improve feedback to controllers
- Displays, warnings, alerts
- Training
- Procedures

**Mitigate consequences**: Reduce harm if hazard occurs
- Damage-limiting design
- Emergency response

## Iteration

STPA is iterative:
- As design evolves, update control structure and repeat analysis
- New UCAs may emerge from design changes
- Mitigations may introduce new control actions requiring analysis
- Organizational analysis may reveal higher-level control flaws

## Analysis Output

Deliver:
1. Control structure diagram
2. Table of UCAs with traceability to hazards
3. Causal scenarios for each UCA
4. Safety requirements traceable to scenarios
5. Recommended controls/mitigations with rationale
