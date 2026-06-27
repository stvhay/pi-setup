# Modeling Safety Control Structures

## Basic Structure

A safety control structure is a hierarchy of controllers enforcing safety constraints. Each level provides:
- **Control actions** (downward): Commands, policies, procedures, standards
- **Feedback** (upward): Reports, audits, incidents, performance data

```
┌─────────────────────────────────────┐
│   Government/External Oversight     │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│      Corporate Management           │
│  (Executive, Safety, Engineering)   │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│      Operations Management          │
│    (Plant/Site, Safety Dept)        │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│    Operators / Process Control      │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│      Physical Process               │
│   (Equipment, Automation)           │
└─────────────────────────────────────┘
```

## Controller Components

Every controller (human or automated) contains:

1. **Goal:** What the controller is trying to achieve
2. **Responsibilities:** Assigned duties for enforcing constraints
3. **Authority:** Control actions available to fulfill responsibilities
4. **Process Model:** Understanding of current state of controlled process
5. **Feedback:** Information about effect of control actions

Accidents often result from process model inconsistent with actual state.

## Modeling Process

### Start High-Level

Begin with abstract structure showing major controller types:
- Regulatory bodies
- Corporate management
- Operations management  
- Direct controllers (operators, automation)
- Physical process

### Refine as Investigation Proceeds

Add detail as you learn more:
- Split "management" into specific functions (safety, engineering, operations)
- Add suppliers, contractors, maintenance
- Include communication channels between peer controllers

### Document Responsibilities

For each controller, list safety responsibilities relevant to the hazard. Sources:
- Organizational charts
- Job descriptions
- Regulations
- Safety management system documentation
- Interviews (what they believe their responsibilities are)

Discrepancies between documented and believed responsibilities are diagnostic.

## Common Control Structure Patterns

### Development vs. Operations

Most systems have parallel structures:

```
┌──────────────────┬──────────────────┐
│   Development    │    Operations    │
├──────────────────┼──────────────────┤
│ Design authority │ Operating org    │
│ Hazard analysis  │ Safety mgmt      │
│ Manufacturing    │ Maintenance      │
└────────┬─────────┴────────┬─────────┘
         │                  │
         └────────┬─────────┘
                  │
         Physical System
```

Communication between development and operations is often a failure point.

### Multiple Oversight Bodies

When multiple regulators or oversight bodies exist:
- Document each body's scope
- Identify overlapping responsibilities
- Look for gaps where no one is clearly responsible

### Contractor/Supplier Relationships

Include any external parties with safety-relevant roles:
- Component suppliers
- Maintenance contractors  
- Training providers
- Consultants

## Visualizing Flaws

After analysis, annotate the control structure to show:
- **Dotted lines:** Missing or inadequate control/feedback
- **Red:** Flawed interactions that contributed to accident
- **Gray:** Components that should exist but don't

This visualization communicates findings more effectively than text alone.

## Common Control Structure Deficiencies

### Missing Feedback
- No way for higher levels to know what's actually happening
- Feedback exists but isn't used
- Feedback is filtered or distorted before reaching decision-makers

### Unclear Responsibilities  
- Multiple controllers think someone else is responsible
- Responsibilities documented but not understood
- Authority doesn't match responsibility

### Coordination Failures
- Controllers at same level don't communicate
- Conflicting directions from multiple controllers
- No mechanism to resolve conflicts

### Model Mismatch
- Controller's model of process state is incorrect
- Model was correct initially but system has changed
- Assumptions underlying model never validated
