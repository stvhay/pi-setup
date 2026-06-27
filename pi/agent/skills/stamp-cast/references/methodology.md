# CAST Methodology Detail

## Step 1: Assembling Basic Information

### Defining System Boundary

The system includes everything under control of designers and operators. The environment includes factors affecting the system but outside their control (weather, external market conditions, etc.).

State explicitly:
- What is inside the system boundary
- What is in the environment
- Who are the stakeholders defining "loss"

### Identifying Hazards

**Correct hazard specification:**
- State at system level, not component level
- Describe system state, not component failure
- Must be controllable by designers/operators

**Examples:**

| Wrong (component-level) | Right (system-level) |
|------------------------|---------------------|
| Engine failure | Aircraft lacks sufficient propulsion for flight |
| Brake failure | Vehicle violates minimum separation |
| Operator error | System releases toxic chemicals |
| Valve malfunction | Reactor pressure exceeds safe limits |

### Deriving Safety Constraints

For each hazard, derive constraints at three levels:

1. **Prevention:** System must not enter hazardous state
2. **Mitigation:** If hazard occurs, measures must reduce impact
3. **Response:** Means must exist to treat/address consequences

Example for "Explosion in chemical plant":
1. Runaway reactions must be prevented
2. If explosion occurs, containment must limit damage
3. Emergency response must be available for injuries

### Documenting Events

Create event timeline without blame language. For each event, generate questions:

| Event | Questions |
|-------|-----------|
| Scheduled maintenance stop | Was MOC (Management of Change) followed? |
| Unforeseen reactions occurred | Were they foreseeable? Were there precursors? |
| Automatic protection triggered | Was interaction with other systems anticipated? |
| Pressure exceeded relief capacity | Was rapid pressure rise scenario analyzed? |

**Avoid:**
- "Failed to..." 
- "Should have..."
- "Negligently..."
- Any assignment of culpability

**Use:**
- "Did not..."
- "[Action] occurred/did not occur"
- Neutral description of what happened

### Analyzing Physical Process

Document for the physical/technical level:

1. **Requirements:** What was the physical system supposed to do to prevent hazard?
2. **Controls:** What physical controls existed (interlocks, relief valves, barriers)?
3. **Failures:** What physical components failed (if any)?
4. **Unsafe interactions:** What unexpected interactions occurred between components?
5. **Design deficiencies:** What physical controls were missing or inadequate?
6. **Context:** Environmental or situational factors affecting physical system

Most accidents involve unsafe interactions rather than simple failures. Look for:
- Design assumptions violated by actual conditions
- Interactions between protection systems that defeat both
- Physical states not anticipated in design

## Event Chain Limitations

Traditional event chains (domino model, Swiss cheese) are useful for initial timeline but have critical limitations:

1. Assume linear causality (A→B→C) when actual causation is networked
2. Assume event independence when systemic factors affect multiple events
3. Stop at "root cause" rather than explaining why events occurred
4. Miss contextual factors that made events possible

Use events as starting point for generating questions, not as final causal explanation.
