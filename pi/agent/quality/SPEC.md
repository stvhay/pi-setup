# Harness Quality Governance Kernel

## Purpose

Provide one Git-tracked quality control plan, one deterministic local entry point for quality assessment, one versioned coarse risk/utility decision tree, one bounded private semantic-review contract, typed agent/interview/decision/editor/takeover result adapters, one shared actionable Finding/EvidenceRef core, and at most 12 decision-linked core metrics. Current policy supports `disabled`, `observe`, and bounded `canary`; `autonomous` remains reserved for Q15. Canary effects require an exact resolved human grant, bounded reversible effect, target revalidation, proof, atomic rollout claim, and an existing dispatch adapter; the kernel never edits workspace directly.

## Core Mechanism

`control-plan.json` defines five activities, the 12-metric ceiling, and a versioned risk policy with coarse bands, hard guards, adaptive resource ceilings, and canary requirements. `durable_activity_snapshots()` maps bounded Beads, Git, run, health, context, and eligible-session signals into those activities. `agnt_lib.quality.assess_risk()` computes expected loss (`failure probability × consequence`) and expected utility (`benefit + information value − expected loss − resource cost`) without persistence or authority. Hard guards, uncertainty, and resource ceilings dominate positive utility; unknown measurement cannot claim autonomous budget. `agnt_lib.quality.assess()` validates a bounded snapshot, fingerprints snapshot and policy, and appends one immutable receipt to private runtime state. `apply()` reloads that receipt and current policy, then records a no-op, one private review assignment, or one bounded canary dispatch through an existing adapter. `derive_core_metrics()` computes metric observations from supplied receipts, results, annotations, and monitoring without writing another store. Unknown and lower-bound observations are never decision-eligible; privacy and unauthorized-mutation metrics are zero-tolerance guards. `quality_status()` reports policy identity and private record counts.

`validate_finding()` and `validate_evidence_ref()` define only fields shared by actionable findings. Review, health, and improvement adapters retain their domain fields; this contract does not replace their enclosing result schemas. Public adapters may carry only core fields plus an explicit safe extension allowlist, so raw private evidence stays behind bounded EvidenceRefs. Improvement schema-3 packets expose one private EvidenceRef per session and deterministically emit one colocated ReviewAssignment. That assignment fixes scope, rubric, private evidence, demonstrated-capability and provider-authorization constraints, output, one-attempt stop rules, and empty effect authority. Policy-v4 results must cite the exact assignment and packet evidence. Policy-v1/v2/v3 decisions remain readable through compatibility validation, with unknown evidence stage preserved where older formats omitted it.

### Canary claim/dispatch/settle

Canary application uses one append-only `claims.jsonl` state machine. Canary packets carry separate `authorizationEvidence` preconditions and `executionEvidence` required-proof refs; structural refs alone prove neither existence nor freshness. An injected evidence resolver must return the exact ref with explicit availability and freshness/expiry before claim and resolve execution proof during settlement. `claim` holds the private `fcntl` lock only while reserving one receipt/grant allowance and returns an explicit token containing `claimId`, receipt, allowance, policy/grant, target, action, bounded effects, required proof labels, and the evidence contract. `dispatch(packet, claimToken)` runs after that lock is released; the token is passed explicitly, and no process-global reentrancy marker or effect-wide lock is used. Dispatcher signatures must expose that token as a second positional or keyword-only parameter; tokenless or uninspectable adapters are rejected before claim.

Work/run adapters preserve the token as invocation `provenance.claimContext` and result `claimContext`, resolve its exact active ledger row, then bind it to the invocation before worker execution. Canonical action mapping is `edit -> implement`; current run action IDs `implement`, `review`, `verify`, `plan`, `research`, and `finish` otherwise map identically. Canonical effect mapping is `workspace.write -> edit_files`; current run effect IDs `read_workspace`, `write_artifacts`, `edit_files`, `write_workspace`, `update_beads`, `external_read`, `external_write`, `push`, `deploy`, and `delete_files` otherwise map identically. Mapped claim effects must equal the invocation `allowedEffects` set exactly; unknown effects, duplicate mapped effects, and extra invocation effects fail closed. Canonical work-target identity is compact sorted-key JSON of `{"schemaVersion":1,"workItem":<work item or Bead>,"worktree":<worktree snapshot or null>,"inputRefs":<ordered invocation refs>}`. `targetFingerprint` must equal its SHA-256 fingerprint. Any action, effect, or target mismatch blocks before worker invocation.

`settle(claimToken, result)` reacquires the short private lock and appends exactly one terminal transition from `claimed` to `dispatched`, `failed`, `uncertain`, or `revoked`; successful execution proof binds claim ID, target fingerprint, effect set, and required evidence contract. Repeated settlement returns the existing terminal result without another row or dispatch.

A pre-dispatch crash, timeout, adapter exception, or uncertain settlement is `uncertain` and blocks retry; a hard process kill can leave `claimed`, which is also unresolved and fail-closed. No stale-claim reaper retries a `claimed` or `uncertain` receipt. Noncritical failures remain settled `failed` claims and consume the error budget scoped to the exact decision Bead plus grant fingerprint; the same receipt never retries, and only a later receipt may use remaining allowance. Explicit unknown, critical, drift, expiry, missing-proof, or stop-rule results are `revoked` and trigger best-effort durable grant revocation. Claims provide at-most-one dispatch attempt, not exactly-once external effect. Exactly-once effect requires an adapter idempotency key or transaction using `claimId`.

Assigned-agent results normalize to `review` evidence only after domain validation and exact assignment/evidence binding. Transient `ask` results normalize in memory to session-retained `answer` constraints. Durable ticket questions and approvals normalize to pointer-backed `answer` or `authorization` constraints in Beads metadata; neither implies `acceptance`, and normalized results carry no effect authority. Approval requests fingerprint kind, target, question, context, options, default, and informed preview; capability approvals additionally store an exact action/effects/model/thinking/toolset/context-policy/proof/rollout/expiry envelope and fingerprint. Resolution verifies identity against an append-only Beads provenance event and reads only resolved human-UI decision state; changed or conditional scope requires a new request, while expiry and revocation can only remove effects.

Langfuse annotation queues normalize to bounded `review` evidence through current queue, queue-item, v3 score, and score-config API fields. Output retains opaque refs, reviewer refs, score-config types, queue scope, completeness, and gaps; score values, comments, corrected outputs, project IDs, subjects, and user IDs stay behind refs. Queue evidence never implies acceptance or authorization.

Editor/Nvim review artifacts and BetterWright human-takeover results normalize through one metadata-only boundary. Inputs bind a canonical relative artifact path, declared sensitivity, scope, EvidenceRefs, human adapter/session provenance, category, state, gaps, and optional safe resumption path. `partial`, `lost`, and `uncertain` stay distinct; interrupted takeovers require a resumption path. Saving or manually executing work never implies acceptance or authorization.

**Key files:**
- `pi/agent/quality/control-plan.json` — versioned activity policy.
- `pi/agent/bin/agnt_lib/quality.py` — validator, deterministic receipt logic, private stores, and CLI.
- `pi/agent/extensions/archimedes.ts` — thin transient-ask adapter; normalization runs through `agnt_lib` over stdin.
- `pi/agent/bin/agnt_lib/langfuse.py` — bounded current-API service reads for queues, annotation scores, and score configs.
- `pi/agent/langfuse/improvement-review.md` — private contextual-review rubric and result contract.
- `tests/test_quality.py` — behavioral contract.
- `tests/test_context_architecture.py` — adapter-boundary and documentation checks.

Private runtime files use `0700` directories and `0600` files:

```text
quality/
  ledger.jsonl
  receipts.jsonl
  applications.jsonl
  claims.jsonl
  assignments/<receipt-id>.json
```

## Public Interface

| Interface | Contract |
|---|---|
| `validate_control_plan(value)` | Accept only exact root/activity fields, five ordered activity IDs, supported `disabled`/`observe`/`canary` modes, the versioned risk policy, bounded inputs/evidence, and valid budgets. |
| `load_control_plan(plan_path=None)` | Load and validate tracked policy or an explicit test/operator path. |
| `durable_activity_snapshots(...)` | Derive exact snapshots for all five activities while preserving unknown, lower-bound, and duplicate-suppression state. |
| `validate_evidence_ref(value)` | Require one bounded opaque pointer plus source, availability, provenance, integrity, sensitivity, and retention metadata. Raw content and unknown fields are rejected. |
| `validate_finding(value, public=False, public_extensions=None)` | Require shared identity, activity/source, category, severity, claim, status, EvidenceRefs, verification, and proposed intervention while leaving private domain extensions to their owner. Public extensions must be explicitly allowlisted. |
| `build_review_assignment(...)` / `validate_review_assignment(value)` | Build or validate one deterministic, private, 20-item-maximum assignment with no effect authority and one review attempt. |
| `normalize_assigned_review_result(assignment, result)` | After domain validation, bind one completed assigned-agent result to its exact assignment evidence and return typed `review` evidence with no authority. |
| `normalize_ask_result(result)` | Validate one portable `ask` answer and return a session-retained `answer` constraint without persistence or authority. |
| `normalize_ticket_decision_result(decision_bead, decision)` | Return a durable pointer-backed `answer` or `authorization` constraint from resolved Beads decision metadata; never infer acceptance or effects. |
| `normalize_capability_grant(value)` / `capability_grant_fingerprint(value)` | Validate one exact capability envelope and fingerprint its immutable ceiling fields, excluding only mutable revocation state. |
| `resolve_capability_grant(decision_bead)` | Read one resolved human-UI approval decision, automatically mark pending grants active or expired, and return no effects after expiry/revocation. |
| `resolve_canonical_capability_grant(decision_bead)` / `resolve_orchestration_metadata(...)` | Resolve one exact grant with bounded Beads lookup at orchestration boundary; malformed, unavailable, changed, expired, revoked, or non-human-UI state fails closed, while compatibility fields remain non-authoritative. |
| `normalize_langfuse_annotation_result(...)` | Convert at most 16 current-API annotation rows into opaque private EvidenceRefs with reviewer, score-config, scope, completeness, gaps, and empty authority. |
| `normalize_external_result(result)` | Validate one editor review or BetterWright takeover artifact with safe relative paths, sensitivity-bounded EvidenceRefs, exact provenance/state, and empty authority. |
| `improvement.import_langfuse_annotation_evidence(client, queue_id)` | Read one optional Langfuse queue through the bounded service port and preserve unavailable or truncated reads as explicit gaps. |
| `improvement.review_assignment(packet)` | Bind a current private scan packet to the existing non-mutating `review` action and policy-v4 rubric. |
| `improvement.validate_decisions(packet, result)` | Validate an exact assignment-bound policy-v4 result or normalize historical policy-v1/v2/v3 private findings without copying evidence bodies or guessing missing stage. |
| `improvement.review_gap_result(packet, status)` | Record unavailable, timed-out, privacy-uncertain, or schema-invalid review as one explicit human route with no findings or retry. |
| `assess_risk(request, ...)` | Return one deterministic coarse risk/utility result with hard-guard, uncertainty, resource-budget, and canary checks; never persist or authorize. |
| `assess(snapshot, activity, ...)` | Persist and return one deterministic receipt with zero or one `workPacket`. |
| `apply(receipt_id, ...)` | Reload current policy and a persisted receipt; record disabled/observe state or execute one canary packet through an injected existing dispatch adapter after grant, target, authorization-evidence freshness, policy, proof, budget, and effect revalidation. Canary adapters receive an explicit claim token and must not infer ownership from process state. |
| `validate_claim_token(value, directory=None, require_active=False)` | Validate the bounded claim context carried across adapters, including deterministic claim/allowance identity and receipt, grant, policy, target, action, effect, required-proof, and evidence-contract bindings; an adapter may also require an exact active durable claim. |
| `derive_core_metrics(...)` | Derive all 12 bounded metric observations from existing evidence sources; never persist a metric store and never treat unknown/lower-bound data as success. |
| `settle(claim_token, result, ...)` | Idempotently append one terminal claim transition under a short private lock; malformed, stale, deleted, mismatched, or incomplete execution evidence fails closed. |
| `quality_status(...)` | Return current policy fingerprint and private receipt/application/assignment counts. |
| `agnt quality capture` | Append a validated invocation/result lifecycle fact. |
| `agnt quality normalize-ask` | Normalize a bounded stdin array of transient ask results and return session-only constraints without persistence. |
| `agnt quality normalize-result` | Normalize one editor/takeover result from stdin without persistence, native UX ownership, acceptance, or authority. |
| `agnt improve annotations <queue> --json` | Import one bounded optional Langfuse queue without persistence, bodies, acceptance, or authority. |
| `agnt quality assess` | Parse one exact JSON snapshot or collect durable local signals, then emit a decision receipt. |
| `agnt quality apply` | Apply one persisted current receipt; CLI/default tracked policy is observe-only. Programmatic canary callers supply target and existing dispatch adapters; CLI does not invent one. |
| `agnt quality status` | Report current policy and private-store counts. |

Assessment snapshots require `schemaVersion`, `triggered`, `evidenceRefs`, `gaps`, and `signals`; canary snapshots additionally bind a risk request, grant reference, target identity, bounded effect, and (when using the split contract) both `authorizationEvidence` and `executionEvidence`. Snapshot bodies are fingerprinted, not copied into receipts or assignments.

## Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| INV-1 | One plan contains exactly `capture`, `work-learning`, `architecture-coherence`, `capability-calibration`, and `quality-system-review`; each activity has the 13 declared fields. | Structural validator and tracked plan test. |
| INV-2 | Identical snapshot, activity, and policy yield identical receipt IDs, dedupe keys, and receipt bodies; persistence is idempotent. | Canonical JSON plus SHA-256 and append-under-lock. |
| INV-3 | Assessment emits at most one packet. Observe may write one private assignment; canary may dispatch one bounded reversible effect only through an existing adapter after canonical grant and proof checks. The kernel never edits workspace directly. | Singular `workPacket`, exact effect/grant/target contracts, atomic `claims.jsonl`, and adapter boundary. |
| INV-4 | Apply re-reads current policy and accepts only a persisted receipt. Disabled, stale-policy, missing-authority, and non-triggered decisions cannot create an assignment. | Receipt lookup and policy fingerprint comparison before private apply. |
| INV-5 | Durable collection maps historical checkpoint labels to current activities for reads and duplicate suppression, preserves unknown/lower-bound evidence, and emits only `quality:<activity>` labels on new packets. | Explicit compatibility map, gap-bearing snapshots, open-activity suppression, and canonical packet label generation. |
| INV-6 | Review and health findings share one validated core and bounded EvidenceRef contract without losing review metrics fields or health diagnostics. | Shared quality validators plus thin review/health adapters; finding statuses are reused by metrics. |
| INV-7 | Improvement review, promotion, and cohort paths consume shared Findings tied to private packet EvidenceRefs; legacy policy-v1/v2/v3 packets remain readable and missing event-to-change stage stays explicit. | Schema-3 session refs, shared findings, compatibility normalization to `evidenceStage: unknown`, and shared IDs through promotion/monitoring. |
| INV-8 | Each current private packet emits at most one deterministic ReviewAssignment. It binds at most 20 exact EvidenceRefs to one rubric, existing non-mutating review action, demonstrated-capability and provider-authorization constraints, result schema, one attempt, and empty effect authority. Completed results cover every assigned session exactly once. | Assignment fingerprint validation, exact action contract and session-set validation, private file permissions, assignment-bound policy-v4 results, and unknown-field rejection. |
| INV-9 | Assigned-agent review, transient interview, durable question, authorization, and acceptance semantics remain distinct. Review produces evidence; `ask` produces session-only answer constraints; ticket questions/approvals produce durable pointer-backed answer/authorization constraints; none of these adapters infers acceptance or effect authority. | Exact source-specific normalizers, fixed category mapping, empty normalized authority, and durable ticket result metadata. |
| INV-10 | Langfuse human scores, score comments, and corrected outputs remain bounded private `review` evidence. Normalized output carries only opaque evidence/reviewer/subject/config refs, config types, scope counts, completeness, gaps, and empty authority. | Authenticated current-API reads, 16-row caps, exact queue/subject/config binding, hashed refs, body omission, and fixed category/authority output. |
| INV-11 | Editor review and human-takeover results cross one metadata-only boundary with exact source/category, relative artifact path, scope, EvidenceRefs, human adapter/session provenance, state, gaps, and empty authority. Partial/lost/uncertain takeover state retains a safe resumption path. | Exact-field validation, sensitivity ordering, source/category/adapter binding, canonical relative paths, and fixed non-authorizing output. |
| INV-12 | The control plan contains exactly the approved 12 metric definitions. Derived observations retain numerator, denominator, state, and decision eligibility; unknown/lower-bound evidence is never eligible, and privacy/unauthorized-mutation guards are zero-tolerance. | Control-plan validation, pure `derive_core_metrics()`, existing evidence-source inputs, and no metric-store writes. |
| INV-13 | Risk assessment is versioned and component-based: expected loss is failure probability × consequence; expected utility includes benefit, information value, and resource cost; hard guards and uncertainty dominate utility; normal and high-consequence resource ceilings are enforced; canary requests bind hypothesis, evidence, stop rule, and error budget. | `assess_risk()` and control-plan risk-policy validation. |
| INV-14 | A capability grant fingerprints exactly action, effects, model, thinking, toolset, context policy, proof, rollout ceiling, and expiry. Only resolved human-UI Bead state can activate it; state updates cannot alter its fingerprinted ceiling. | Capability-grant validator, append-only request fingerprint, resolved decision lookup, and bounded revocation update. |
| INV-15 | One canary receipt or grant allowance yields at most one debit and one dispatch attempt. Claims and settlement are atomic under short private `fcntl` locks; dispatch runs outside locks; claimed, uncertain, or revoked claims fail closed. Dispatch requires exact action/effects, target fingerprint, fresh authorization evidence, required execution evidence, current policy/grant/budget, and a bounded result; critical failure, drift, expiry, missing proof, unknown result, or stop-rule breach revokes the grant. Explicit run adapters preserve claim context and reject any canonically mapped action, exact effect-set, or work-target mismatch before worker execution; exactly-once external effect requires adapter idempotency or transaction semantics. | `claims.jsonl`, split evidence contracts, explicit claim tokens, validated `claimContext`, action/effect mapping, canonical work-target fingerprint, double pre-dispatch revalidation, idempotent settlement, local revocation guard, run authority checks, and canary apply tests. |

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
| FAIL-8 | Langfuse annotation evidence is unavailable, partial, unbound, or claims authority. | Queue/service reads fail or truncate, items remain pending, score/config/subject/reviewer bindings are missing, or imported fields claim acceptance, authorization, mode, grant, or effects. | Return unavailable/partial evidence with fixed gaps when provenance is still safe; reject malformed or authority-bearing input; never infer completion or effects. |
| FAIL-9 | Editor/takeover result normalization fails. | Artifact or resumption path is absolute, non-canonical, or escaping; evidence exceeds artifact sensitivity; provenance/state is malformed; raw evidence or nested authority fields are embedded. | Reject whole result, persist nothing, and leave native editor/browser ownership and resumption external. |
| FAIL-10 | A quality metric cannot be decided. | Source evidence is missing, unknown, lower-bound, or incomplete; a zero-tolerance guard lacks complete coverage. | Return explicit non-eligible state; never convert missingness into zero or success. |
| FAIL-11 | Risk assessment cannot safely recommend an effect. | A hard guard fails or is unknown, uncertainty is high, measurement is unknown/exceeded, or a canary request lacks its bounded learning contract. | Disable or route human; reject malformed canary requests; never trade a guard for positive utility. |
| FAIL-12 | Capability grant is malformed, changed, conditional, expired, revoked, or lacks human-UI decision provenance. | Envelope fields, fingerprint, proof, rollout ceiling, expiry, revocation state, or append-only request identity is invalid. | Reject or update state fail-closed; return empty effects and require a new exact approval. |
| FAIL-13 | Canary claim or effect cannot be safely settled. | Claim is already consumed/uncertain, policy/grant/target drifted, required proof is absent, result is unknown/critical, or revocation is unavailable. | Persist `uncertain` or `revoked` claim state before external revocation, block sibling grants by exact decision/fingerprint, return existing terminal settlement on repeats, and never dispatch again from the affected local authority. |

## Adapter Boundaries

- Beads remains durable work and human-authority store. The quality kernel never grants authority; canary approval handling reads exact grants only from resolved decision Beads, then revalidates them before an existing adapter dispatch.
- Repository workspace remains source of policy only. `apply()` never edits workspace files.
- No scheduler, daemon, service, polling loop, or background process lives here.
- No model-facing typed tool is added; external callers use stable `agnt quality ... --json` CLI commands.
- Reviewer output is not authority. ReviewAssignment and result schemas reject grant, mode, authority, and effect claims. The existing `review` action may read workspace evidence and write a private result artifact, but cannot mutate workspace, Beads, or external state.
- `ask` normalization is pure and session-local: the Pi adapter sends answer JSON to the deterministic CLI over stdin and returns `qualityResults` in the same tool result. Durable question/approval normalization happens only in dedicated Beads decision handling; `ticket_gateway` remains limited to list/show/tree/create_draft.
- Request fingerprints bind approval resolution to created kind, target, prompt/context, choices/default, informed preview, and, for capability approvals, the exact grant fingerprint and append-only Beads provenance event. A changed, recomputed, missing, conditional, or unverifiable fingerprint cannot approve; callers create a new request rather than editing old authority. Automatic activation, expiry, and revocation mutate state only, never ceiling fields.
- Langfuse remains optional evidence storage. Annotation import uses `GET /api/public/annotation-queues/{id}`, its bounded item page, `GET /api/public/v3/scores` with `details,subject,annotation`, and score-config reads. It adds no scheduler, persistence, retry loop, Beads mutation, or authority path.
- Nvim/editor and BetterWright own native interaction and policy. Quality accepts only their validated result metadata; it does not open editors, automate browsers, resume takeovers, or interpret save/manual execution as approval or acceptance.
- Private review requires demonstrated reviewer capability. Human and local/self-hosted review are eligible classes; any other provider requires explicit authorization before packet access.
- Finding extensions remain owned by review, health, improvement, and later domain adapters. Shared validation does not create a universal result schema.
- Improvement keeps event, incident, pattern, change, and unknown distinct from finding verification status and intervention type.
- Private EvidenceRefs may cross a public finding boundary as tagged opaque pointers; copied evidence bodies and non-allowlisted extensions may not.
- Work/run adapters carry canary ownership only through explicit `provenance.claimContext`; they validate active claim identity, grant binding, canonical action/effect mapping, and canonical work-target fingerprint before execution and never read a process-global reentrancy or ownership marker.

## Decision Framework

| Situation | Action | Spec item |
|---|---|---|
| Policy mode is `disabled` | Persist receipt; apply records disabled no-op. | INV-4 |
| Policy mode is `observe` and trigger is true | Emit one packet; apply records one private assignment. | INV-2, INV-3 |
| Policy mode is `canary` and trigger is true | Emit one packet; apply revalidates exact grant/policy/target/proof/budget, atomically claims allowance, and dispatches at most once through an existing adapter. | INV-13, INV-14, INV-15 |
| Trigger is false | Emit receipt without packet; apply records not-due no-op. | INV-3 |
| Policy changed after assessment | Return blocked policy mismatch. | INV-4, FAIL-3 |
| Positive utility with a failed or unknown hard guard | Disable or route human; utility does not override the guard. | INV-13, FAIL-11 |
| Normal or high-consequence resource share exceeds its ceiling | Reject canary/autonomous request or route bounded work to human; preserve guards. | INV-13, FAIL-11 |
| Canary learning contract is absent or irreversible | Reject request; require hypothesis, evidence, stop rule, error budget, and bounded reversibility. | INV-13, FAIL-11 |
| Evidence is incomplete | Preserve explicit gaps and unknown authority; never widen effects. | INV-3 |
| Review is unavailable, timed out, privacy-uncertain, or invalid | Stop after one attempt and return an explicit human route without findings or effects. | FAIL-6 |
| Langfuse queue is unavailable, truncated, pending, or incompletely bound | Return unavailable/partial review evidence plus fixed gaps; do not count it as acceptance or authorization. | INV-10, FAIL-8 |
| Editor review completes | Normalize scoped review evidence; file save grants no authority or acceptance. | INV-11 |
| Human takeover is partial, lost, or uncertain | Preserve state/gaps and require a safe resumption path; infer no success. | INV-11, FAIL-9 |
| Capability grant expires or is revoked | Update decision metadata below the stored ceiling and return no allowed effects. | INV-14, FAIL-12 |
| Capability scope changes or adds conditions | Reject old decision and require a new exact preview/request. | INV-14, FAIL-12 |

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
| INV-10 | `tests/test_quality.py::test_inv10_langfuse_annotations_are_bounded_review_evidence_only` plus annotation service-port and CLI checks in `tests/test_langfuse_evaluators.py` and `tests/test_improvement.py` |
| INV-11 | `tests/test_quality.py::test_inv11_editor_and_takeover_results_preserve_external_evidence_state` and `test_inv11_quality_cli_normalizes_external_result_without_persistence` |
| FAIL-2, FAIL-3 | Malformed snapshot, receipt, and application tests prefixed `test_fail2_` / `test_fail3_` in `tests/test_quality.py` |
| FAIL-4 | `tests/test_quality.py::test_public_finding_rejects_copied_raw_private_evidence` |
| FAIL-5 | `tests/test_improvement.py::test_fail5_improvement_finding_rejects_evidence_from_another_packet` plus unsafe legacy pointer cases |
| FAIL-6 | `tests/test_improvement.py::test_fail6_review_failures_route_human_once_without_retry` and `test_fail6_invalid_or_private_unsafe_result_becomes_explicit_human_route` |
| FAIL-7 | `tests/test_approvals.py::test_fail7_changed_approval_preview_requires_new_request` plus malformed review/ask result checks in `tests/test_quality.py` |
| FAIL-8 | `tests/test_quality.py::test_fail8_langfuse_annotation_partiality_and_authority_claims_fail_closed` and optional-service gap checks in `tests/test_improvement.py` |
| FAIL-9 | `tests/test_quality.py::test_fail9_external_result_rejects_unsafe_or_authorizing_artifacts` |
| INV-12, FAIL-10 | `tests/test_quality.py::test_inv12_core_metrics_are_decision_linked_and_bounded`, `test_inv12_unknown_and_lower_bound_metrics_cannot_count_as_success`, and `test_inv12_zero_tolerance_metrics_require_complete_evidence`; summary integration in `tests/test_review.py`. |
| INV-13, FAIL-11 | `tests/test_quality.py::test_inv13_risk_assessment_reports_components_and_normal_ceiling`, `test_fail11_hard_guard_blocks_positive_utility`, `test_inv13_high_consequence_ceiling_and_unknown_budget_fail_closed`, and `test_fail11_canary_requires_learning_contract_and_ceiling`. |
| INV-14, FAIL-12 | `tests/test_quality.py::test_inv14_capability_grant_fingerprint_excludes_only_mutable_state`, `test_fail12_expired_capability_grant_is_not_active`, exact Beads/bridge cases in `tests/test_approvals.py`, and canonical orchestration authority cases in `tests/test_orchestration.py`. |
| INV-15, FAIL-13 | `tests/test_quality.py::test_inv15_canary_revalidates_grant_target_and_dispatches_once`, concurrent receipt/grant and grant-budget cases, hard-process-crash and timeout retry suppression, policy/grant/target drift and expiry revocation, stop-rule/critical/unknown/missing-proof revocation, tokenless/uninspectable dispatcher rejection, explicit-token dispatch, idempotent settlement, forged claim context, split authorization/execution evidence, and `tests/test_runs.py` exact-binding plus action/effect/target mismatch cases. |
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
| Langfuse public API | Optional external evidence | Current annotation queue/items, v3 scores with detail/subject/annotation groups, and score configs; never authority or required startup state. |
| Nvim/editor and BetterWright | External human-action adapters | Own native UX/policy and return bounded relative artifact/result metadata; never authority or acceptance. |
| External scheduler | External caller | May invoke CLI; owns cadence and retries. |
