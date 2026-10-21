# Pending-decision UI recovery

## Purpose

Re-present an existing pending Beads question/approval after Pi loses its in-memory resolver secret. Recovery changes the authorized UI binding, not the question, preview, exact grant, blocker, or original request fingerprint. Rebinding is not consent.

## Interfaces

- `pending_decision(id, beads_runner=...)` reads canonical pending metadata and validates unchanged request/preview provenance and any pending exact grant.
- `rebind_pending_decision(id, resolver=..., beads_runner=...)` requires current target ownership, records a private resolver-hash binding, and returns the original request for display. The Python seam is trusted; the CLI validates existing process-bound UI proof before calling it.
- `agnt approvals recover-context ID --json` reads canonical pending scope for the owning trusted UI. `agnt approvals rebind ID --json` accepts no resolver flags or ordinary proof files. Both use existing private parent-process IPC/pending-tool-call proof. Only verified legacy questions need `--legacy-selection-mode single|multi` on their first binding.
- `ticket_decision_resolve` automatically recovers a missing/stale in-memory binding. Approvals redisplay canonical action, context, scope, consequences, recovery, and exact grant. Questions present original choices plus custom input and take the fresh human answer, not the agent's suggested answer.
- Existing `resolve_beads_approval_request` uses the effective private binding when present, revalidates canonical preview and current ownership, then follows the existing resolution/grant path.

## Invariants

1. Only `pending` decisions may rebind. Rejected, cancelled, timed-out, answered, and approved records are not silently reopened.
2. Rebind performs no Beads create/update/close/dependency mutation. Existing blockers remain until actual resolution.
3. Original `resolverBinding`, `requestFingerprint`, `grantFingerprint`, preview, and grant ceiling remain unchanged. Fresh positive resolution still requires actual human UI proof; standing authority is not an answer.
4. New binding invalidates the previous resolver for this request. Missing private state preserves legacy approval bindings; legacy questions require explicit mode recovery before any positive answer. Corrupt or mismatched state never falls back to the original resolver. Every positive resolution rechecks `pending` under the shared lock, so a competing answer/rejection is not overwritten. Direct and rebound question answers both validate request provenance.
5. Session changes during recovery or interaction invalidate the UI result. Headless callers cannot manufacture positive recovery through CLI flags.
6. Current session must own the target's immutable quality link and, when present, active lifecycle execution. Ambiguous legacy ownership stops.
7. New request fingerprint version 2 includes question selection mode and custom-response allowance. Version-1 fingerprints remain readable without rewriting provenance. A legacy question's unprotected mode is not represented as historically verified: first recovery asks the human to verify its current mode explicitly before binding. Declining leaves the existing blocker pending. Private mode capture prevents later mode drift and avoids repeating this extra check on subsequent recovery. Question flows always permit custom answers; conflicting custom-response metadata stops for clarification rather than silently widening the question.

## Persistence and locking

Files live under the canonical repository's private lifecycle root, in `decision-bindings/`. Filenames hash the decision ID. Schema-1 records retain decision/request identity, the question's captured selection mode (null for approvals), and append-only binding history (`sessionFingerprint`, `secretFingerprint`, timestamp). Raw session IDs, resolver secrets, and user answers are not copied into this private history.

An envelope fingerprint detects accidental corruption. Files are owner-private, bounded to 4 MiB, symlink-checked, atomically replaced and fsynced. Fingerprints are not authentication against a hostile same-OS writer.

Supported rebind and resolve mutations share a per-decision file lock acquired before canonical state reads. Lock order begins with decision-binding, then lifecycle/quality/authority/Beads as needed. Lifecycle mutation callbacks must not invoke UI decision mutation while holding the lifecycle journal lock. Direct external Beads edits are not intercepted by this workflow.

Legacy decisions without an original UI binding can recover through a fresh trusted UI only when canonical request provenance and current ownership validate. No legacy request/comment is rewritten to claim a different original origin.

## Failure and recovery

- Changed preview/request, expired/revoked exact grant, non-pending decision, missing owner, or malformed private state: reject without answering or creating another blocker.
- Crash after private binding write but before interaction: decision remains pending; a later trusted UI may rebind again.
- Cancellation or rejection: existing resolution semantics remain blocking; recovery does not convert them to approval.
- Unavailable UI: preserve decision and blocker; do not infer an answer.

This module does not supersede approval-only blockers under standing policy, move session ownership, or launch a child through an unresolved dependency. These remain separate lifecycle/authority concerns. It is not a sandbox against arbitrary same-user code or private-file mutation.

## Tests

```bash
.venv/bin/python -m pytest tests/test_decision_rebinding.py tests/test_decision_rebinding_extension.py tests/test_approvals.py tests/test_quality.py -q
```

Coverage includes unchanged original request/grant ceilings, structured/custom human answers, old-secret rejection, foreign ownership, pending-state recheck under lock and before positive resolution, versioned mode provenance, explicit one-time legacy-mode verification, scope corruption, invalid private state, missing process proof, canonical redisplay, and session change during confirmation. Tests use disposable private state and SDK-loaded UI fixtures; no live human decision was rebound.
