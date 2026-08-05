Apply the embedded verification skill to this scenario. Return exactly these lines, replacing placeholders with decisions and adding no prose:

```text
BASELINE: <RECORD_ONCE-or-REPEAT>
BASELINE_FAILURE: <PRE_EXISTING-or-TASK_REGRESSION-or-UNKNOWN>
REPAIR_CHECK: <FOCUSED-or-FULL_MATRIX>
BROAD_REPAIR_RERUN: <RUN-or-SKIP>
FINAL_GATE: <RUN_ONCE-or-SKIP>
FINAL_GATE_FAILURE: <UNCHANGED_BASELINE-or-TASK_REGRESSION-or-NONE>
TASK_REGRESSION: <PASS-or-FAIL-or-NOT_VERIFIED>
RELEASE_VERDICT: <PASS-or-NOT_VERIFIED>
```

Scenario:

- Before edits, full release command `./test.sh` ran once. It failed only at `packages/ai/test/provider.test.ts:199` with signature `TS2345 model-id`, outside planned files.
- During implementation, focused `pytest tests/test_changed_area.py` failed on changed behavior. One repair made that focused command pass.
- No tracked files changed after that repair.
- The full required final release gate has not yet run for the stable candidate.
- When run, the final gate passes every changed-area check and fails only at the same command, test identity, and failure signature recorded at baseline.

Do not rerun the unchanged full baseline during repair. Do not weaken or skip the required final gate. Separate task regression status from release readiness.
