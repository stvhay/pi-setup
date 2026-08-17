# Handoff and Lifecycle Cohort — August 2026

## Decision

Do not automate another handoff or Beads recovery case from this cohort. No observed case combines repeated operational frequency with a safe deterministic resolution.

Keep current fail-closed handoff behavior. Preserve explicit parent acceptance instead of closing an epic when its descendants close.

## Cohort

The bounded review classified 20 recent parented Bead closeouts and all 14 handoff attempt records available through `2026-08-17T01:29:54.929Z`. Later verification runs are outside this fixed cohort.

| Evidence | Classification | Result |
|---|---|---:|
| Recent parented Bead closeouts | Ordinary child closeout; parent still had open descendants | 19/20 |
| Recent parented Bead closeouts | Final descendant closed; parent remained open | 1/20 |
| Handoff attempt records | Synthetic validation failures from seven identical test-process pairs | 14/14 |
| Handoff attempt records | Operational handoff attempts | 0/14 |

The sole lifecycle candidate was `pi-rxo3`: all 41 descendants were closed while the epic remained `in_progress`. This gives the candidate a reproducible observed frequency of 1/20 closeouts (5%), not evidence that parent acceptance was complete.

The 14 handoff records were not an operational cohort. Each process emitted the same two immediate `attempt` → `validation failed` sequences produced by the focused rejection test. The local-live extension used by real handoffs did not contain the tracked stage recorder at collection time, so successful operational handoffs could not contribute records.

## Safety assessment

Automatic epic closure is not safe from descendant status alone. `agnt work direct-closeout` requires explicit success for the exact session-owned Bead, an explicit close reason, canonical/portable parity, and a dedicated portable-state commit. Closing an ancestor as a side effect would invent parent-level acceptance and bypass those checks. That conflicts with this task's fail-closed and no-force-close constraints.

No production change is justified. Existing manual recovery remains:

- review the epic's acceptance criteria, then close it explicitly when parent-level work is complete;
- use `/new`, then rerun `agnt work direct-start <id> --claim`, when automated handoff is unavailable.

## Follow-up threshold

Reconsider automation only after tracked telemetry is deployed through the approved local-live path and a new operational cohort shows a repeated failure class. Keep deterministic domain logic in `agnt_lib`; keep the Pi extension limited to lifecycle and UI adaptation.
