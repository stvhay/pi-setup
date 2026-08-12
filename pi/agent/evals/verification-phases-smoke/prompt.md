Apply the embedded verification skill to these scenarios. Return exactly these lines, replacing placeholders with decisions and adding no prose:

```text
BASELINE: <RECORD_ONCE-or-REPEAT>
BASELINE_FAILURE: <PRE_EXISTING-or-TASK_REGRESSION-or-UNKNOWN>
REPAIR_CHECK: <FOCUSED-or-FULL_MATRIX>
BROAD_REPAIR_RERUN: <RUN-or-SKIP>
FINAL_GATE: <RUN_ONCE-or-SKIP>
FINAL_GATE_FAILURE: <UNCHANGED_BASELINE-or-TASK_REGRESSION-or-NONE>
TASK_REGRESSION: <PASS-or-FAIL-or-NOT_VERIFIED>
RELEASE_VERDICT: <PASS-or-NOT_VERIFIED>
STALE_FOCUSED_EVAL: <RERUN-or-KEEP>
TASK_PATHS: <STAGE_ALL-or-LEAVE_UNSTAGED>
CACHED_BOUNDARY: <INSPECT-or-SKIP>
UNTRACKED_BOUNDARY: <INSPECT-or-SKIP>
DIFF_FORMAT: <RUN_BEFORE_GATE-or-RUN_AFTER_GATE>
NOMINAL_COMPLETE_GATES: <number>
POST_GATE_MUTATION: <INVALIDATE_AND_RERUN-or-KEEP_GATE>
```

Baseline-failure scenario:

- Before edits, full release command `./test.sh` ran once. It failed only at `packages/ai/test/provider.test.ts:199` with signature `TS2345 model-id`, outside planned files.
- During implementation, focused `pytest tests/test_changed_area.py` failed on changed behavior. One repair made that focused command pass.
- No candidate files changed after that repair.
- The full required final release gate has not yet run for the stable candidate.
- When run, the final gate passes every changed-area check and fails only at the same command, test identity, and failure signature recorded at baseline.

Candidate-boundary scenario:

- Focused eval passed, then its expected assertion changed. Its evidence is stale because its expected assertion changed.
- Task renamed tracked `checks/old-case.md` to untracked `checks/new-case.md`. Before staging this appears as a tracked deletion plus an untracked addition. Both path states belong to task.
- Other task-owned modifications are unstaged. Known unrelated untracked cache data must stay excluded and untouched.
- Complete gate has not run. After candidate stabilization, refreshed focused eval and all pre-gate checks pass, and candidate remains unchanged through complete gate.
- In nominal flow, report how many complete gates run for that stable candidate.
- After successful complete gate, task-owned eval assertion changes again. Decide status of prior gate evidence.

Do not rerun unchanged full baseline during repair. Do not weaken or skip the required final gate. Separate task regression status from release readiness.
