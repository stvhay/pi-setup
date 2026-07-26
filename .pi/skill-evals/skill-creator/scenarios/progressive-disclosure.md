# Scenario: Progressive-disclosure skill maintenance

## Prompt
Update a 320-line skill whose description repeats its workflow. Keep it portable across capable coding models and preserve safety gates.

## Expected weak baseline
The agent edits prose immediately, applies a vendor-specific line-reduction target, removes examples and safety rules indiscriminately, or expands the custom YAML parser to support unnecessary metadata syntax.

## Expected with skill
The agent establishes baseline behavior, distinguishes repository-owned from package-owned skills, makes trigger metadata concise, keeps the top-level skill focused on decisions and invariants, moves bulky material into references, preserves schema/edge-case examples and safety gates, and reruns the same checks after the smallest change.

## Assertions
- Must identify positive and negative trigger cases before changing the description.
- Must prefer single-line trigger-only metadata supported by the repository parser.
- Must use progressive disclosure for bulky reference material.
- Must preserve security, destructive-action, accessibility, and verification constraints.
- Must treat vendor reduction percentages as evidence, not a target.
- Must not edit externally installed/package-owned skills without separate approval.
