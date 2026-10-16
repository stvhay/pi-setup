# Scenario: advisory-owner-and-write-boundary

## Prompt
R15: Investigate two independent failures read-only, direct or development Mode A. R16: Implement in parallel with overlapping files, no worktree approval, or shared database/port.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): Mode A duplicates advisory steps; dispatching sends read-only proposals back to Mode A, forming ownership cycle.

## Expected with skill
Dispatching owns advisory procedure. Development Mode A loads exact owner; Mode B retains approved isolated write policy and serial integration.

## Assertions
- Peers cannot edit/commit read-only scopes. Carry task graph, evidence-complete packet, evidence/output schema and stops. Shared mutable state needs isolation or serial execution. No write dispatch without disjoint approved worktrees.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
