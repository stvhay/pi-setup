# Harness Quality Observe Kernel

## Purpose

Provide one Git-tracked quality control plan and one deterministic local entry point for quality assessment. Current policy supports only `disabled` and `observe`; it cannot authorize or perform external effects.

## Core Mechanism

`control-plan.json` defines five activities. `agnt_lib.quality.assess()` validates a bounded snapshot, fingerprints snapshot and policy, and appends one immutable receipt to private runtime state. `apply()` reloads that receipt and current policy, then records a no-op result or one private review assignment. `quality_status()` reports policy identity and private record counts.

**Key files:**
- `pi/agent/quality/control-plan.json` — versioned activity policy.
- `pi/agent/bin/agnt_lib/quality.py` — validator, deterministic receipt logic, private stores, and CLI.
- `tests/test_quality.py` — behavioral contract.
- `tests/test_context_architecture.py` — adapter-boundary and documentation checks.

Private runtime files use `0700` directories and `0600` files:

```text
quality/
  ledger.jsonl
  receipts.jsonl
  applications.jsonl
  assignments/<receipt-id>.json
```

## Public Interface

| Interface | Contract |
|---|---|
| `validate_control_plan(value)` | Accept only exact root/activity fields, five ordered activity IDs, `disabled`/`observe`, bounded inputs/evidence, and valid budgets. |
| `load_control_plan(plan_path=None)` | Load and validate tracked policy or an explicit test/operator path. |
| `assess(snapshot, activity, ...)` | Persist and return one deterministic receipt with zero or one `workPacket`. |
| `apply(receipt_id, ...)` | Reload current policy and a persisted receipt; record only disabled/no-op state or one private assignment. |
| `quality_status(...)` | Return current policy fingerprint and private receipt/application/assignment counts. |
| `agnt quality capture` | Append a validated invocation/result lifecycle fact. |
| `agnt quality assess` | Parse one exact JSON snapshot and emit a decision receipt. |
| `agnt quality apply` | Apply one persisted current receipt under observe-only policy. |
| `agnt quality status` | Report current policy and private-store counts. |

Assessment snapshot fields are exactly `schemaVersion`, `triggered`, `evidenceRefs`, `gaps`, and `signals`. Snapshot bodies are fingerprinted, not copied into receipts or assignments.

## Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| INV-1 | One plan contains exactly `capture`, `work-learning`, `architecture-coherence`, `capability-calibration`, and `quality-system-review`; each activity has the 13 declared fields. | Structural validator and tracked plan test. |
| INV-2 | Identical snapshot, activity, and policy yield identical receipt IDs, dedupe keys, and receipt bodies; persistence is idempotent. | Canonical JSON plus SHA-256 and append-under-lock. |
| INV-3 | Assessment emits at most one packet. Apply performs no Beads or workspace mutation and exposes no effect authority; observe may write one private assignment only. | Singular `workPacket`, empty `allowedEffects`, and local adapter boundary. |
| INV-4 | Apply re-reads current policy and accepts only a persisted receipt. Disabled, stale-policy, missing-authority, and non-triggered decisions cannot create an assignment. | Receipt lookup and policy fingerprint comparison before private apply. |

## Failure Modes

| ID | Symptom | Cause | Handling |
|---|---|---|---|
| FAIL-1 | Control plan load fails. | Missing, unknown, malformed, duplicate, empty, or out-of-range plan fields. | Reject whole plan; emit no receipt. |
| FAIL-2 | Assessment fails. | Snapshot shape, evidence reference, gap, activity, JSON, or size is invalid. | Reject input with sanitized CLI error; persist nothing. |
| FAIL-3 | Apply fails or returns `blocked`. | Receipt is absent/malformed, private store is unsafe, or current policy fingerprint differs. | Fail closed; create no assignment or external effect. |

## Adapter Boundaries

- Beads remains durable work and human-authority store. Observe kernel neither reads grants nor mutates Beads.
- Repository workspace remains source of policy only. `apply()` never edits workspace files.
- No scheduler, daemon, service, polling loop, or background process lives here.
- No model-facing typed tool is added; external callers use stable `agnt quality ... --json` CLI commands.
- Reviewer output is not authority. Assignment packets contain no allowed effects.

## Decision Framework

| Situation | Action | Spec item |
|---|---|---|
| Policy mode is `disabled` | Persist receipt; apply records disabled no-op. | INV-4 |
| Policy mode is `observe` and trigger is true | Emit one packet; apply records one private assignment. | INV-2, INV-3 |
| Trigger is false | Emit receipt without packet; apply records not-due no-op. | INV-3 |
| Policy changed after assessment | Return blocked policy mismatch. | INV-4, FAIL-3 |
| Evidence is incomplete | Preserve explicit gaps and unknown authority; never widen effects. | INV-3 |

## Testing

| Spec item | Verification |
|---|---|
| INV-1, FAIL-1 | `tests/test_quality.py::test_inv1_control_plan_has_exact_five_activity_contract`, `test_fail1_control_plan_rejects_missing_unknown_and_invalid_fields` |
| INV-2 | `tests/test_quality.py::test_inv2_assessment_is_deterministic_and_emits_at_most_one_packet` |
| INV-3 | `tests/test_quality.py::test_inv3_apply_is_private_observe_only_and_idempotent` |
| INV-4 | `tests/test_quality.py::test_inv4_disabled_and_stale_policy_cannot_create_assignment` |
| FAIL-2, FAIL-3 | Malformed snapshot, receipt, and application tests prefixed `test_fail2_` / `test_fail3_` in `tests/test_quality.py` |
| CLI/boundaries | `tests/test_quality.py::test_quality_assess_apply_status_cli_contract`, quality checks in `tests/test_context_architecture.py` |

Focused command:

```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_cli_nameerrors.py tests/test_context_architecture.py -k 'quality or runner'
```

## Dependencies

| Dependency | Type | Contract |
|---|---|---|
| `agnt_lib.runtime_paths` | Internal | Resolve private runtime directory; environment cannot redirect it into repository. |
| `fcntl`, `hashlib`, `json`, `pathlib` | Standard library | Locked append, deterministic identity, validation, and safe paths. |
| Pi lifecycle and direct-work adapters | Internal callers | Supply capture facts; remain outside policy authority. |
| External scheduler | External caller | May invoke CLI; owns cadence and retries. |
