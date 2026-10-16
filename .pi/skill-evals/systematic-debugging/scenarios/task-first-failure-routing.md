# Scenario: task-first-failure-routing

## Prompt
R1: This test failed after yesterday’s change; find root cause. R2: Analyze a near-miss involving operator handoff, alarms and management controls. R3: Retrospect on this feature / review this harness across 20 runs. R4: Design recovery UI after partial agent failure. M1: Debug, then investigate systemic incident, then prevent recurrence.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): STAMP generic failure/root-cause rows can compete with software diagnosis; local outcome exclusions are missing.

## Expected with skill
Route software repair to debugging; systemic incident to CAST; completed-work learning to retrospective; cohort lifecycle review to agent-retrospective-loop; recovery UX to failure-choreography.

## Assertions
- No CAST from a failed-test keyword alone. No automatic retrospective at closeout. Stabilize active incident first. M1 advances only on requested scope; carry reproducer/evidence into systemic analysis, then approved preventive work.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
