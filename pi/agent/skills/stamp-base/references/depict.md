# Shared Depict Grammar

Load only when producing a Depict control-structure diagram. This reference owns generic notation for STPA, CAST and STPA-Sec, not their methods or schemas.

Depict maps directly to STAMP control concepts.

| Concept | Syntax | Example |
|---|---|---|
| Vertical hierarchy | names on separate lines | `supervisor` then `operator` then `process` |
| Horizontal peers | end line with `-` | `sensor_a sensor_b sensor_c -` |
| Control action | `controller process: action` | `pilot aircraft: pitch_cmd` |
| Feedback | `process controller: / feedback` | `aircraft pilot: / altitude` |
| Bidirectional | `a b: action / feedback` | `operator system: start / status` |
| Multiple labels | comma-separated | `ctrl proc: open, close, stop` |
| Nesting | `parent [ child ]` | `cockpit [ pilot copilot ]` |
| Placeholder | `_` | `ctrl _ proc` |
| Highlighting | `@red` suffix | `ctrl proc: unsafe_action @red` |
| Separator | `;` | `a; b; c` |

Names may include hyphens, asterisks, parentheses and angle brackets: `shift-supervisor`, `controller*`, `valve(stuck)`, `sensor<failed>`.

Depict shows structure, not analysis. Keep method-specific hazards, incident annotations, trust-boundary limitations, causal scenarios and requirements in the specialist's examples, tables, YAML or prose. The schemas are not interchangeable.
