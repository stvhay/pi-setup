# Scenario: behavior-preserving refactor

## Prompt
Tests pass, but parser repeats the same three null checks in four callers. Refactor it without changing behavior. Keep the diff minimal and run focused tests.

## Expected weak baseline
Requirement-simplification review over-triggers, blocks direct work for a product-requirement interview, creates a quantitative roadmap, or asks the user to reconsider behavior that must remain unchanged.

## Expected with skill
This skill does not trigger. Agent uses ordinary test-driven/code-simplification workflow, traces all callers, applies the smallest shared fix, and verifies behavior.

## Assertions
- Does not start requirement archaeology.
- Does not ask product-requirement decision questions.
- Does not create a requirement scoreboard or architecture review artifact.
- Preserves behavior and uses focused verification.
