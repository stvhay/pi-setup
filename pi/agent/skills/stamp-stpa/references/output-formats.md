# STPA Output Formats

Load this reference when machine-readable analysis or a control-structure diagram is requested.

## Machine-readable schema

```yaml
stpa_analysis:
  system:
    name: string
    boundary: string
    losses:
      - id: L-1
        description: string
    hazards:
      - id: H-1
        description: string
        losses: [L-1]

  control_structure:
    controllers:
      - id: string
        type: human | automated
        controls: [process_ids]
        feedback_from: [process_ids]
    processes:
      - id: string
        description: string
    control_actions:
      - from: controller_id
        to: process_id
        action: string
    feedback_paths:
      - from: process_id
        to: controller_id
        information: string

  unsafe_control_actions:
    - id: UCA-1
      controller: controller_id
      type: not_provided | provided | wrong_timing | wrong_duration
      action: string
      context: string
      hazards: [H-1]

  causal_scenarios:
    - uca: UCA-1
      scenario: string
      category: feedback | process_model | control_path | algorithm

  safety_requirements:
    - id: SR-1
      requirement: string
      addresses: [UCA-1]
      verification: string
```

Use this schema for agent handoff, stored analysis, or machine-actionable output. For human-readable work, present control structure, hazards, scenarios, and constraints hierarchically.

## Depict control-structure notation

When a diagram is requested, read `~/.pi/agent/skills/stamp-base/references/depict.md` for the shared grammar; no whole-base skill load is needed. Machine-readable-only output does not need the diagram reference.

Example:

```text
person microwave food: open, start, stop / beep : heat
person food: eat
```

Depict shows structure only. Keep unsafe control actions, causal scenarios, and safety requirements in YAML or prose.
