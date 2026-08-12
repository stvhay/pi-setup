# Scenario: Stable candidate boundary before final gate

## Prompt

Apply verification-before-completion after one baseline and focused implementation work.

Task changed a tracked eval expectation after its focused eval last passed. Task also renamed tracked `checks/old-case.md` to new untracked `checks/new-case.md`; neither side is staged. Known unrelated untracked cache data must stay untouched. Decide what must happen before complete gate, how many complete gates nominal stable flow runs, and what a later task-owned assertion edit does to successful gate evidence.

## Expected weak baseline

Agent runs complete gate before staging and boundary inspection, then discovers stale focused evidence or omitted rename and repeats expensive gate.

## Expected with skill

Agent treats focused eval evidence as stale, reruns it, stages every task-owned path state, inspects cached and untracked boundaries, runs diff/format checks, then runs complete gate once. Any later candidate change invalidates gate and requires another complete gate.

## Assertions

- Must rerun focused eval after its expectation changes.
- Must stage task-owned additions, modifications, renames, and deletions before complete gate.
- Must inspect cached diff and untracked files without staging or deleting unrelated cache data.
- Must run diff/format checks before complete gate.
- Nominal stable candidate runs one complete gate.
- Post-gate task-owned mutation invalidates gate and requires another complete gate.
