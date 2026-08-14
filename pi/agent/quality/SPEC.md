# Harness Quality Observe Kernel

## Purpose

Provide one Git-tracked quality control plan, one deterministic local entry point for quality assessment, one bounded private semantic-review contract, typed agent/interview/decision result adapters, and one shared actionable Finding/EvidenceRef core. Current policy supports only `disabled` and `observe`; it cannot authorize or perform external effects.

## Core Mechanism

`control-plan.json` defines five activities. `durable_activity_snapshots()` maps bounded Beads, Git, run, health, context, and eligible-session signals into those activities. `agnt_lib.quality.assess()` validates a bounded snapshot, fingerprints snapshot and policy, and appends one immutable receipt to private runtime state. `apply()` reloads that receipt and current policy, then records a no-op result or one private review assignment. `quality_status()` reports policy identity and private record counts.

`validate_finding()` and `validate_evidence_ref()` define only fields shared by actionable findings. Review, health, and improvement adapters retain their domain fields; this contract does not replace their enclosing result schemas. Public adapters may carry only core fields plus an explicit safe extension allowlist, so raw private evidence stays behind bounded EvidenceRefs. Improvement schema-3 packets expose one private EvidenceRef per session and deterministically emit one colocated ReviewAssignment. That assignment fixes scope, rubric, private evidence, demonstrated-capability and provider-authorization constraints, output, one-attempt stop rules, and empty effect authority. Policy-v4 results must cite the exact assignment and packet evidence. Policy-v1/v2/v3 decisions remain readable through compatibility validation, with unknown evidence stage preserved where older formats omitted it.

Assigned-agent results normalize to `review` evidence only after domain validation and exact assignment/evidence binding. Transient `ask` results normalize in memory to session-retained `answer` constraints. Durable ticket questions and approvals normalize to pointer-backed `answer` or `authorization` constraints in Beads metadata; neither implies `acceptance`, and normalized results carry no effect authority. Approval requests fingerprint kind, target, question, context, options, default, and informed preview; resolution verifies that identity against an append-only Beads provenance event, so changed approved scope requires a new request.

**Key files:**
- `pi/agent/quality/control-plan.json` — versioned activity policy.
- `pi/agent/bin/agnt_lib/quality.py` — validator, deterministic receipt logic, private stores, and CLI.
- `pi/agent/extensions/archimedes.ts` — thin transient-ask adapter; normalization runs through `agnt_lib` over stdin.
- `pi/agent/langfuse/improvement-review.md` — private contextual-review rubric and result contract.
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
| `durable_activity_snapshots(...)` | Derive exact snapshots for all five activities while preserving unknown, lower-bound, and duplicate-suppression state. |
| `validate_evidence_ref(value)` | Require one bounded opaque pointer plus source, availability, provenance, integrity, sensitivity, and retention metadata. Raw content and unknown fields are rejected. |
| `validate_finding(value, public=False, public_extensions=None)` | Require shared identity, activity/source, category, severity, claim, status, EvidenceRefs, verification, and proposed intervention while leaving private domain extensions to their owner. Public extensions must be explicitly allowlisted. |
| `build_review_assignment(...)` / `validate_review_assignment(value)` | Build or validate one deterministic, private, 20-item-maximum assignment with no effect authority and one review attempt. |
| `normalize_assigned_review_result(assignment, result)` | After domain validation, bind one completed assigned-agent result to its exact assignment evidence and return typed `review` evidence with no authority. |
| `normalize_ask_result(result)` | Validate one portable `ask` answer and return a session-retained `answer` constraint without persistence or authority. |
| `normalize_ticket_decision_result(decision_bead, decision)` | Return a durable pointer-backed `answer` or `authorization` constraint from resolved Beads decision metadata; never infer acceptance or effects. |
| `improvement.review_assignment(packet)` | Bind a current private scan packet to the existing non-mutating `review` action and policy-v4 rubric. |
| `improvement.validate_decisions(packet, result)` | Validate an exact assignment-bound policy-v4 result or normalize historical policy-v1/v2/v3 private findings without copying evidence bodies or guessing missing stage. |
| `improvement.review_gap_result(packet, status)` | Record unavailable, timed-out, privacy-uncertain, or schema-invalid review as one explicit human route with no findings or retry. |
| `assess(snapshot, activity, ...)` | Persist and return one deterministic receipt with zero or one `workPacket`. |
| `apply(receipt_id, ...)` | Reload current policy and a persisted receipt; record only disabled/no-op state or one private assignment. |
| `quality_status(...)` | Return current policy fingerprint and private receipt/application/assignment counts. |
| `agnt quality capture` | Append a validated invocation/result lifecycle fact. |
| `agnt quality normalize-ask` | Normalize a bounded stdin array of transient ask results and return session-only constraints without persistence. |
| `agnt quality assess` | Parse one exact JSON snapshot or collect durable local signals, then emit a decision receipt. |
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
| INV-5 | Durable collection maps historical checkpoint labels to current activities for reads and duplicate suppression, preserves unknown/lower-bound evidence, and emits only `quality:<activity>` labels on new packets. | Explicit compatibility map, gap-bearing snapshots, open-activity suppression, and canonical packet label generation. |
| INV-6 | Review and health findings share one validated core and bounded EvidenceRef contract without losing review metrics fields or health diagnostics. | Shared quality validators plus thin review/health adapters; finding statuses are reused by metrics. |
| INV-7 | Improvement review, promotion, and cohort paths consume shared Findings tied to private packet EvidenceRefs; legacy policy-v1/v2/v3 packets remain readable and missing event-to-change stage stays explicit. | Schema-3 session refs, shared findings, compatibility normalization to `evidenceStage: unknown`, and shared IDs through promotion/monitoring. |
| INV-8 | Each current private packet emits at most one deterministic ReviewAssignment. It binds at most 20 exact EvidenceRefs to one rubric, existing non-mutating review action, demonstrated-capability and provider-authorization constraints, result schema, one attempt, and empty effect authority. Completed results cover every assigned session exactly once. | Assignment fingerprint validation, exact action contract and session-set validation, private file permissions, assignment-bound policy-v4 results, and unknown-field rejection. |
| INV-9 | Assigned-agent review, transient interview, durable question, authorization, and acceptance semantics remain distinct. Review produces evidence; `ask` produces session-only answer constraints; ticket questions/approvals produce durable pointer-backed answer/authorization constraints; none of these adapters infers acceptance or effect authority. | Exact source-specific normalizers, fixed category mapping, empty normalized authority, and durable ticket result metadata. |

## Failure Modes

| ID | Symptom | Cause | Handling |
|---|---|---|---|
| FAIL-1 | Control plan load fails. | Missing, unknown, malformed, duplicate, empty, or out-of-range plan fields. | Reject whole plan; emit no receipt. |
| FAIL-2 | Assessment fails. | Snapshot shape, evidence reference, gap, activity, JSON, or size is invalid. | Reject input with sanitized CLI error; persist nothing. |
| FAIL-3 | Apply fails or returns `blocked`. | Receipt is absent/malformed, private store is unsafe, or current policy fingerprint differs. | Fail closed; create no assignment or external effect. |
| FAIL-4 | Finding or evidence normalization fails. | Required common metadata is missing/invalid, verification cites unknown evidence, a pointer is unsafe, or a public finding carries an unapproved extension. | Reject the finding; never copy raw private evidence onto the public path. |
| FAIL-5 | Improvement finding cites unavailable or foreign packet evidence. | EvidenceRef differs from every exact private packet session ref, current packet ref metadata was altered, or a legacy JSON pointer escapes packet sessions. | Reject before marker, monitoring, approval preview, or public promotion. |
| FAIL-6 | Contextual review is unavailable, times out, has uncertain privacy, or returns invalid schema/evidence. | No demonstrated authorized reviewer completes the one allowed attempt, or returned data fails assignment validation. | Emit an explicit assignment-bound gap and `human` route; write no markers, findings, grants, effects, or automatic paid retry. |
| FAIL-7 | A result changes category/authority or an approval is resolved against changed scope. | Result fields do not match their source contract, assignment IDs differ, selected options are foreign, or current request identity no longer matches its append-only Beads provenance event. | Reject normalization or approval; issue a new exact preview/request for changed scope. |

## Adapter Boundaries

- Beads remains durable work and human-authority store. Observe kernel neither reads grants nor mutates Beads.
- Repository workspace remains source of policy only. `apply()` never edits workspace files.
- No scheduler, daemon, service, polling loop, or background process lives here.
- No model-facing typed tool is added; external callers use stable `agnt quality ... --json` CLI commands.
- Reviewer output is not authority. ReviewAssignment and result schemas reject grant, mode, authority, and effect claims. The existing `review` action may read workspace evidence and write a private result artifact, but cannot mutate workspace, Beads, or external state.
- `ask` normalization is pure and session-local: the Pi adapter sends answer JSON to the deterministic CLI over stdin and returns `qualityResults` in the same tool result. Durable question/approval normalization happens only in dedicated Beads decision handling; `ticket_gateway` remains limited to list/show/tree/create_draft.
- Request fingerprints bind approval resolution to created kind, target, prompt/context, choices/default, informed preview, and an append-only Beads provenance event. A changed, recomputed, missing, or unverifiable fingerprint cannot approve; callers create a new request rather than editing old authority.
- Private review requires demonstrated reviewer capability. Human and local/self-hosted review are eligible classes; any other provider requires explicit authorization before packet access.
- Finding extensions remain owned by review, health, improvement, and later domain adapters. Shared validation does not create a universal result schema.
- Improvement keeps event, incident, pattern, change, and unknown distinct from finding verification status and intervention type.
- Private EvidenceRefs may cross a public finding boundary as tagged opaque pointers; copied evidence bodies and non-allowlisted extensions may not.

## Decision Framework

| Situation | Action | Spec item |
|---|---|---|
| Policy mode is `disabled` | Persist receipt; apply records disabled no-op. | INV-4 |
| Policy mode is `observe` and trigger is true | Emit one packet; apply records one private assignment. | INV-2, INV-3 |
| Trigger is false | Emit receipt without packet; apply records not-due no-op. | INV-3 |
| Policy changed after assessment | Return blocked policy mismatch. | INV-4, FAIL-3 |
| Evidence is incomplete | Preserve explicit gaps and unknown authority; never widen effects. | INV-3 |
| Review is unavailable, timed out, privacy-uncertain, or invalid | Stop after one attempt and return an explicit human route without findings or effects. | FAIL-6 |

## Testing

| Spec item | Verification |
|---|---|
| INV-1, FAIL-1 | `tests/test_quality.py::test_inv1_control_plan_has_exact_five_activity_contract`, `test_fail1_control_plan_rejects_missing_unknown_and_invalid_fields` |
| INV-2 | `tests/test_quality.py::test_inv2_assessment_is_deterministic_and_emits_at_most_one_packet` |
| INV-3 | `tests/test_quality.py::test_inv3_apply_is_private_observe_only_and_idempotent` |
| INV-4 | `tests/test_quality.py::test_inv4_disabled_and_stale_policy_cannot_create_assignment` |
| INV-5 | `tests/test_quality.py::test_inv5_durable_activity_snapshots_map_signals_and_suppress_legacy_duplicates` plus lower-bound, unknown, checkpoint, and label compatibility cases |
| INV-6 | `tests/test_quality.py::test_shared_finding_and_evidence_ref_validate_common_contract` plus review and health adapter checks in `tests/test_review.py` and `tests/test_health.py` |
| INV-7 | `tests/test_improvement.py::test_inv7_current_improvement_finding_uses_shared_core_and_private_evidence_refs`, `test_inv7_policy_v2_packet_normalizes_without_guessing_evidence_stage`, and scan/promotion/monitoring checks |
| INV-8 | `tests/test_quality.py::test_inv8_review_assignment_is_bounded_private_and_non_authorizing`, `tests/test_improvement.py::test_inv8_current_review_is_assignment_bound_and_cannot_claim_effects`, and private scan artifact checks |
| INV-9 | `tests/test_quality.py::test_inv9_assigned_agent_review_result_is_typed_evidence_only`, `test_inv9_transient_ask_result_is_session_constraint_not_acceptance`, and durable result checks in `tests/test_approvals.py` |
| FAIL-2, FAIL-3 | Malformed snapshot, receipt, and application tests prefixed `test_fail2_` / `test_fail3_` in `tests/test_quality.py` |
| FAIL-4 | `tests/test_quality.py::test_public_finding_rejects_copied_raw_private_evidence` |
| FAIL-5 | `tests/test_improvement.py::test_fail5_improvement_finding_rejects_evidence_from_another_packet` plus unsafe legacy pointer cases |
| FAIL-6 | `tests/test_improvement.py::test_fail6_review_failures_route_human_once_without_retry` and `test_fail6_invalid_or_private_unsafe_result_becomes_explicit_human_route` |
| FAIL-7 | `tests/test_approvals.py::test_fail7_changed_approval_preview_requires_new_request` plus malformed review/ask result checks in `tests/test_quality.py` |
| CLI/boundaries | `tests/test_quality.py::test_quality_assess_apply_status_cli_contract`, `tests/test_ticket_gateway.py`, and quality checks in `tests/test_context_architecture.py` |

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
