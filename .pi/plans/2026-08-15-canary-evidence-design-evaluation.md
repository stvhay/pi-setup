# Canary Evidence Design Evaluation

**Bead:** `pi-rxo3.17.5`

**Scope:** Current Q14 claim/dispatch/settle implementation and referenced tests/docs. No production code changed.

## Verdict

Current design is materially more robust than predecessor described in Q14: durable claims replace effect-wide locking and process-global ownership, dispatch runs outside claims lock, explicit claim tokens cross adapter boundaries, uncertainty blocks retries, and documentation avoids exactly-once claims without adapter idempotency.

Verdict is **NEEDS WORK before Q14 run-adapter provenance can be treated as fully satisfied**. Core claim state machine is appropriate and fail-closed, but existing run adapter does not bind valid claim context to actual invocation action, effects, or target. Settlement also repeats external evidence resolution while holding claims lock, creating avoidable operability and terminal-state inconsistency.

## Acceptance assessment

| Requirement | Result | Evidence |
|---|---|---|
| Split authorization/execution evidence | PASS | Packet validation separates both sets in `pi/agent/bin/agnt_lib/quality.py:2660-2703`; authorization evidence resolves before claim at `:3662-3687`; execution evidence binds claim, target, effects, and freshness at `:3402-3440`. |
| Resolver-backed freshness/availability | PASS with settlement risk | Resolver requires exact ref, availability, and freshness/expiry at `quality.py:2492-2553`. Repeated settlement resolution causes finding R2. |
| Atomic claim and idempotent settlement | PASS | Claim reservation and grant-budget accounting occur under lock at `quality.py:3259-3326`; terminal settlement is append-only and repeated settlement returns existing result at `:3329-3400`. |
| Dispatch outside claim lock | PASS | `_claim_canary()` returns before `_invoke_dispatcher()` runs at `quality.py:3703-3768`; recursive/concurrent tests cover this boundary. |
| Policy/grant/target revalidation | PASS | Initial checks occur at `quality.py:3640-3696`; post-claim preflight repeats policy, grant, target, and authorization-evidence checks at `:3708-3764`. |
| Fail-closed crash/unknown/drift behavior | PASS with settlement risk | Exception/unknown/drift classification and revocation are implemented at `quality.py:3768-3822`; focused crash, retry, drift, expiry, stop-rule, and proof tests pass. R2 can leave an ordinary evidence-resolution failure as `claimed` rather than a persisted terminal state. |
| Run-adapter provenance binding | FAIL | Finding R1. `runs.py:444-501` verifies token against claim ledger and grant provenance, but not against invocation action/effects/target. |
| Exactly-once claim restraint | PASS | `pi/agent/quality/SPEC.md:15-17` and `docs/SELF-IMPROVEMENT.md:454` state at-most-one dispatch attempt and require adapter idempotency/transaction semantics for exactly-once effects. |

## Residual risks

### R1 — Important — claim context is not bound to actual run invocation

`pi/agent/bin/agnt_lib/runs.py:444-501` validates deterministic token identity, active claim state, decision Bead, and grant fingerprint. It never compares:

- `claimContext.action` with invocation `action`;
- `claimContext.effects` with invocation `allowedEffects` or dispatch policy;
- `claimContext.targetFingerprint` with work item/worktree/target identity.

`pi/agent/bin/agnt_lib/work.py:548-647` forwards claim context into a bundle without that binding. Existing tests prove preservation and forged-token rejection (`tests/test_runs.py:373-488`, `tests/test_agnt.py:2748-2807`) but do not test invocation mismatch. The `test_start_work_passes_explicit_claim_context_to_run_provenance` fixture itself uses claim effect `workspace.write` with the review action's different effect vocabulary.

Executable reproducer passed a ledger-valid `edit`/`workspace.write` claim to an `implement` invocation allowing `edit_files`; `_revalidate_invocation_authority()` returned `None`. A valid claim can therefore attest one action/target while run tooling executes another. Normal action-template and grant checks reduce current exploitability, but adapter boundary does not enforce Q14's exact action/effect/target invariant.

**Required follow-up:** Define one canonical mapping between quality effect/action identity and run invocation identity, then reject mismatches before worker invocation. Add action, effect, and target mismatch tests. This is a correctness/security fix, not behavior-preserving simplification.

### R2 — Important — execution evidence resolves repeatedly and under claims lock

Successful apply resolves execution evidence before settlement at `pi/agent/bin/agnt_lib/quality.py:3792-3798`, then `settle()` resolves it again while holding exclusive claims lock at `:3348-3362`; `_execution_proof_refs()` invokes injected resolver at `:3437`. Slow or reentrant resolvers extend or deadlock settlement lock. Volatile resolver results can pass first resolution, fail second, and leave only `claimed` state.

Executable reproducer returned fresh execution evidence on first read and missing evidence on second. Result was `blocked/claim-uncertain`, execution evidence was read twice, and `claims.jsonl` contained only `claimed`. This is fail-closed but conflicts with FAIL-13's terminal persistence intent and makes recovery/operator diagnosis harder.

**Required follow-up:** Resolve and classify execution result once outside claims lock into a validated immutable settlement payload. Under lock, verify active token/state and append terminal row only. Add volatile-resolver and resolver-reentrancy tests.

## Simplification decision

**Bounded simplification audit warranted.** Do not redesign state machine or merge authorization and execution evidence.

Candidates:

1. Consolidate `_execution_proof_refs()` and overlapping success checks in `_canary_failure_reason()` into one execution-result validator/classifier.
2. Move injected evidence resolution outside `_locked_store(..., exclusive=True)`; keep settlement lock limited to read/transition/append.
3. Pass one validated settlement payload through `_apply_canary()` to `settle()` so evidence is not resolved twice.

Boundaries:

- Preserve public claim token fields, append-only states, receipt/grant budget semantics, fail-closed retry behavior, and exactly-once disclaimer.
- Keep R1 separate until canonical run/action/effect/target mapping is specified; equality across current vocabularies would be incorrect.
- No broad quality-kernel cleanup. Audit only execution-proof classification and settlement lock scope.

Follow-up Beads:

- `pi-rxo3.17.6` — bind canary claim context to run invocation.
- `pi-rxo3.17.7` — simplify canary execution-proof settlement.

## Verification

- `.venv/bin/python -m pytest tests/test_quality.py tests/test_agnt.py tests/test_runs.py -k 'canary or revoke or dispatch or effect or claim or settle or evidence'` → **67 passed, 219 deselected**.
- Run-adapter mismatch reproducer → `_revalidate_invocation_authority()` returned `None` for mismatched valid claim/invocation action and effects.
- Volatile execution-evidence reproducer → two execution-evidence reads, result `blocked/claim-uncertain`, persisted states `['claimed']`.
- Independent read-only reviewer confirmed R1 and R2 and independently reported focused suite **67 passed**.
