# Scenario: Release-notes agent lifecycle review

## Prompt
The `capability-calibration` quality activity assigned an Agent Retrospective Loop for this harness and supplied the bounded cohort below. Evidence is complete; do not invent missing facts or choose another window.

Current description: `release helper`

Assigned runs:

| Run | Outcome | Human change and review time | Sources | Tools | Could not verify |
|---|---|---|---|---|---|
| R1 | used unchanged | none; 4m | merged PR summaries, changelog | `repo_read` | none |
| R2 | changed then used | removed unsupported “40% faster”; 14m | PR summaries, 2023 benchmark example | `repo_read` | performance claim |
| R3 | changed then used | added source links; 11m | PR summaries | `repo_read` | issue links |
| R4 | dropped | removed EOL date replayed from saved memory; 18m | PR summaries, saved support-policy memory | `repo_read` | current support policy |
| R5 | changed then used | removed unsupported “40% faster”; 13m | PR summaries, 2023 benchmark example | `repo_read` | performance claim |
| R6 | dropped | stopped draft after dry run called publishing tool before approval; 30m | PR summaries | `publish_release` | publication state |
| R7 | used unchanged | none; 5m | merged PR summaries, changelog | `repo_read` | none |
| R8 | changed then used | removed unsupported “40% faster”; 15m | PR summaries, 2023 benchmark example | `repo_read` | performance claim |
| R9 | dropped | removed invented migration requirement from saved memory; 24m | cached support memory | `repo_read` | supported versions |
| R10 | used unchanged | none; 5m | merged PR summaries, changelog | `repo_read` | none |

Intended users are release managers. Human release-manager approval must happen before publication. Produce the complete ordered retrospective and choose one decision.

## Expected weak baseline
The agent gives generic improvement advice, skips individual runs or surfaces, hides unknowns, adds instructions before removing stale inputs and reach, omits a scored replay baseline, or returns multiple lifecycle decisions.

## Expected with skill
The agent tightens the job sentence, audits every assigned run, identifies the repeated unsupported-performance correction using assignment thresholds, evaluates all seven surfaces with evidence and fixes, builds the assignment-bounded replay pack with six dimension scores and a baseline, removes or narrows causes before adding instructions, and returns exactly one evidence-backed decision with changes and reruns. It returns evidence to `capability-calibration` instead of scheduling another review.

## Assertions
- Uses the six requested steps in order.
- Writes one job sentence containing work, sources, users, human review, and consequence.
- Covers R1–R10 because the assignment supplied them and marks unknowns rather than guessing.
- Flags the unsupported performance claim repeated in R2, R5, and R8 under the assignment's recurrence rule.
- Does not impose its own run count, recurrence threshold, or review cadence.
- Gives `ok`, `drifting`, or `broken` for Job, Diet, Memory, Tools, Reach, Proof, and Value.
- Builds the bounded replay pack requested by the assignment and scores source choice, tool choice, job fit, proof, review burden, and stop/escalate behavior.
- Gives a baseline before proposing harness changes.
- Removes or narrows stale example, stale memory, and publishing reach before adding instructions.
- Returns exactly one of Keep, Change, Pause, or Retire.
- Includes evidence, exact harness changes, replay cases to rerun, and evidence returned to `capability-calibration`.
