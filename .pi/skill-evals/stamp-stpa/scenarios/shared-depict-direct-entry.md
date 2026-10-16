# Scenario: shared-depict-direct-entry

## Prompt
R17: Direct CAST, STPA or STPA-Sec request includes Depict diagram; contrast analysis without diagram. M4: Extend existing STPA control model with adversarial feedback analysis.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): Generic Depict grammar copied across STPA output reference and CAST/Sec bodies; local copies can drift.

## Expected with skill
One grammar at stamp-base/references/depict.md; specialists read exact shared reference only for diagrams, keeping method examples/annotations and schemas.

## Assertions
- No compulsory whole-base load/routing loop. Preserve CAST incident overlays and Sec trust-boundary limitation. Preserve YAML fields, method IDs and safe-control reminders. No grammar load needed without diagram.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
