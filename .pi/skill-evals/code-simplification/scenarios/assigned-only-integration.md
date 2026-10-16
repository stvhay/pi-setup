# Scenario: assigned-only-integration

## Prompt
R11: Tests pass on nontrivial change, no simplification requested. Contrast explicit simplification request or architecture-coherence assignment.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): Integration section recommends post-verification simplification despite assigned/requested-only invocation rule.

## Expected with skill
Passing tests alone never select simplification; assigned/requested work respects effect bounds and re-verifies.

## Assertions
- Integration must say requested simplify, not unconditional verify → simplify. No control-plan edit or hiding.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
