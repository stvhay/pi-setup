# Standing delivery authority

## Purpose

Separate an owner's reusable permission ceiling from current assigned intent and concrete execution preconditions. This foundation does not activate itself, enroll repositories, execute delivery effects, or replace exact quality experiment grants.

**Implementation:** `../bin/agnt_lib/authority.py`, `full-delivery.json`, `../extensions/standing-authority.ts`.

## Admission and trust boundary

The tracked template grants nothing by installation. Owner state lives at `~/.pi/authority/state.json`, outside repository runtime discovery. Deployment preserves `/authority/` while updating the distinct `agent/authority/` template.

`import-historical` is an explicit owner-authorized migration operation. It accepts an exact historical record containing `kind=historical-consent`, `owner`, `policy`, `consent`, `evidenceRefs`, and `inputOrigin=not-retained`. The owner authorized relaxing historical input-channel traceability during pi-pvcg implementation. Import therefore preserves recorded consent without claiming that Pi retained authenticated interactive-input provenance. The operator must bind the record to the intended owner and reviewed scope; a string or fingerprint is not a cryptographic authenticity proof.

Import does not run on extension load, assignment, inspection, or action checks. The model-facing tool exposes only inspection and checking; `/authority-import <path>` is an explicit owner command. An existing admission is immutable, repeat import is idempotent, and import cannot replace or un-revoke it. A future widening/reactivation path requires new owner authority and is not provided by this migration interface.

Trusted code running as the same OS user can modify private files or call Python APIs. This is workflow enforcement, not a sandbox against arbitrary shell, hostile host extensions, or same-user filesystem rewriting. Callers must establish real intent, project constraints, target association, platform checks, effect closure, verification, and recovery. Caller-supplied `verified`/precondition fields are resolved adapter evidence, not an authenticity mechanism. Do not present the checker as independent discovery of an external target.

## Public Interface

| Interface | Contract |
|---|---|
| `agnt authority template` | Print tracked policy and fingerprint; no admission. |
| `agnt authority inspect` | Print active/inactive/revoked status and opaque fingerprints; no consent text. |
| `agnt authority import-historical --input-file PATH` | Explicitly migrate owner-authorized historical consent. No generic `approved` flag. |
| `agnt authority assign --input-file PATH` | Record immutable assigned intent, not project enrollment. |
| `agnt authority check ASSIGNMENT --input-file PATH` | Return `active` or `blocked` plus bounded reason; execute nothing. |
| `agnt authority revoke --reason TEXT` | Permanently block future checks under this admission without deleting history. |
| `standing_authority` tool | Inspect, or check an existing assignment/action file. Never activate or assign. |
| `resolve_local_assignment` | Resolve local implementation scope from a private assignment; reject unresolved generic external writes. |
| `revalidate_standing_envelope` | Re-read authority at worker invocation; bind actual repository, Bead, and effects. |

Assignment input uses `assignment_id`, `repository`, `beads`, `effects`, `intent_ref`, and optional `denied_effects`. Private storage uses corresponding `id`, `repository`, `beads`, `effects`, `intentRef`, and `deniedEffects` fields. Canonical Git common-directory identity includes sibling worktrees; non-Git projects use their canonical directory. Discovery ignores inherited `GIT_*` and rejects configured roots that disagree with the requested repository. Registering intent does not schedule work and does not activate a policy.

Action fields: `repository`, `bead`, nonempty `effects`, `target` (`identity`, `repository`, `verified`), `preconditions` (`identity`, `platform`, `effectClosure`), and optional `decisionRefs`. Verification and recovery remain execution-adapter obligations. Effect names are explicit in `full-delivery.json`; ambiguous `external_write`, `push`, `deploy`, and `delete_files` are not mapped by the local dispatch adapter.

Private schema version 1 has `revision`, `admission`, `revocation`, and `assignments`. Admission fingerprints bind the exact recorded scope; assignment fingerprints bind immutable restrictions. Lock order is consumer journal then authority. A POSIX advisory lock serializes each read-modify-write. Updates use private temporary files, fsync, atomic replace, and directory fsync. Missing state is inactive; unsupported or malformed state is not permission. No session ledger is rewritten.

## Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| INV-1 | One admission applies to all assigned current/future projects, without project files or enrollment prompts. | Private owner store; explicit assignment intersection. |
| INV-2 | Historical provenance stays honest and bound to reviewed policy. | Exact record schema, fingerprint, immutable admission. |
| INV-3 | Assignment restrictions persist across sessions; assignment IDs cannot overwrite intent or exclusions. | Immutable private records. |
| INV-4 | Revocation is visible to sibling readers and cannot be bypassed by reimport. | Fresh locked reads; permanent revocation field. |
| INV-5 | Current policy may narrow, never widen, the admitted ceiling. | Effect subset and exclusion superset checks. |
| INV-6 | Project discovery cannot redirect the owner root. | Home-owned fixed default, no project/root environment override. |

## Failure Modes

| ID | Condition | Behavior |
|---|---|---|
| FAIL-1 | Missing owner admission | Inactive/blocked; no implicit import. |
| FAIL-2 | Foreign assignment/target, excluded effect, or unsatisfied precondition | Blocked; no mutation. |
| FAIL-3 | Corrupt, unsupported, non-private, or symlinked state | Fail closed; retain state for diagnosis. |

## Consumers and compatibility

Orchestration may name `metadata.pi.standingAssignment`; the name is a selector, not authority. A local implementation worker requires `repo-write` because its existing tools can edit source. Standing run envelopes contain `source.kind=standing-policy` and the resolved action, not counterfeit `human-ui`, `decisionBead`, or grant-token fields. At invocation the actual worktree must belong to the assigned repository and requested effects must remain within the stored action.

Explicit approval references always select the legacy exact-grant path; invalid or rejected exact grants never fall back to standing permission. Decision refs are re-read and pending/rejected/unavailable records block dispatch. Standing envelopes cannot authorize quality `claimContext` experiments. Routing/model/thinking choices do not become new approval dimensions.

Direct-start lazily reuses an existing unambiguous private assignment or records a local-only single-Bead assignment when owner admission is active. Before first start, repeatable `--scope-bead ID` captures the actual approved multi-Bead work set without separate authority JSON; canonical Beads must exist and remain unfinished. Multiple selected Beads include local `worktree-create`, not push/deployment effects. Existing overlapping scopes cannot be merged or widened; an exact-set existing assignment retains its restrictions. Registration is serialized and cannot overwrite an existing assignment identity. CLI scope is a trusted caller's intent capture, not proof of human origin; it must not be populated from all ready work. Lifecycle checkpoint/launch/attachment consumers bind that scope and recheck revocation; progress text cannot change scope.

Continuation worktree creation now uses assignment-scoped delivery receipts with ownership reservation before effects. Orchestrated native claim/close now checks controller scope independently of worker permission, holds lifecycle ownership through callbacks and rechecks canonical/local exact-gate revocation. Exact grants retain and validate canonical `targetBead` at admission, native effects and worker launch; legacy envelopes require fresh target matching without history rewrite. **Deferred under the owner's 2026-10-21 narrowed scope:** orchestrated worker-session/epic-worktree consumers, universal receipt-aware Beads/closeout recovery, policy-covered approval-blocker reconciliation and other delivery adapters. Completion now targets useful resume, dirty switching, existing-decision recovery and valid-authority reuse/revocation through normal commands; broader autonomous delivery is not claimed. Direct closeout now checks captured scope and canonical constraints before success and rechecks local effects before native writes; partial denial preserves state instead of inviting automatic retry. This is not receipt-backed closeout reconciliation. Existing successful-closeout handoff remains available alongside the new continuation adapter. Neither foundation tests nor simulated process replacement establish live activation or autonomous full delivery.

## Testing

```bash
.venv/bin/python -m pytest tests/test_authority.py tests/test_standing_authority.py tests/test_approvals.py tests/test_orchestration.py tests/test_runs.py -q
.venv/bin/python -m pytest tests/test_update_pi_config.py::test_update_preserves_owner_authority_but_deploys_policy_template -q
```

`test_authority.py` links INV/FAIL IDs inline. Consumer tests cover worker checkout binding, Git worktree identity, effect narrowing, decision rejection, revocation, and exact-grant separation. Deployment tests use disposable destinations, never live owner state. External identity verification and the authenticity of operator-authorized migration remain operational obligations.
