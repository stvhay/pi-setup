# Delivery receipt core

## Status and purpose

In-progress pi-pvcg source foundation. `DeliveryStore` coordinates recoverable effects through **trusted concrete adapters**. Core tests use a fake provider; `WorktreeCreationAdapter` adds disposable native Git/Beads tests. Continuation consumes native creation receipts and checks settled effects before terminal departure; orchestrated creation and a public execution CLI remain unconnected. This is not evidence of autonomous full delivery, live activation, or deployment.

The core keeps standing-policy authority separate from quality experiment grants. It is not a scheduler, deployment platform, or shell sandbox.

## Interfaces

- `prepare(assignment, adapter)` independently resolves current action, checks standing authority, and reserves all affected physical resources. Returns a prepared receipt, the existing identical reservation, or bounded denial.
- `execute(receipt, adapter)` re-resolves immutable facts and authority, observes desired state before issuing an effect, records `started` durably, rechecks authority, then invokes the adapter once. A started/uncertain receipt takes reconciliation only; it is never replayed by that call.
- `reconcile(receipt, adapter)` performs observation only. It remains available after revocation because observing an existing effect grants no new effects.
- `cancel(receipt, reason)` cancels only prepared or definitely-not-applied work. It cannot cancel uncertainty to bypass a resource reservation.
- `inspect(receipt)` reads historical receipt state; an applied receipt is not a fresh provider-health claim.
- `observe_current(receipt, adapter)` obtains a fresh bound observation under resource leases, including after revocation. It reports current status separately from `historicalStatus` and never rewrites terminal history or replays an effect.

Corrupt/unsafe private state and busy resource leases raise bounded `ValueError`. Unproven actions return `blocked`. Missing state is empty history, not permission or completion.

### Adapter contract

Adapters implement `kind`, `resolve()`, `execute(action, lease_fds=...)`, and `observe(action, attempted=...)`. They are host/provider implementation seams, **not model-provided callbacks or boolean attestations**. There is no generic execution command accepting caller-authored action JSON.

Resolved action schema 1 binds repository, Bead, effect closure, decision refs, stable target identity and physical resources, resolved artifact/source rule, deterministic material native facts, verification refs, recovery description, and literal satisfied identity/platform/effect-closure/verification/recovery preconditions. Execution compares the complete immutable action fingerprint again. Native facts must capture material versions/paths/conditions, not volatile timestamps or arbitrary request IDs.

Observations classify `applied`, `not-applied`, or `uncertain`, bound to the exact target/source with evidence refs. Exceptions, malformed data, mismatched identity, or missing evidence produce uncertainty, not proof of absence. Provider error text is not copied into receipts/results.

`not-applied` must prove terminal absence/quiescence. A missing provider object after a timeout is **not** sufficient if a request may still land. Concrete local-process adapters must preserve resource lease FDs in their effect processes so a host crash cannot release the lease while a local writer remains active. Remote adapters need provider-specific reconciliation/idempotency evidence; the core cannot infer it.

`assert_settled(assignment, bead)` reads the validated receipt journal and rejects terminal execution departure while that assignment/Bead has prepared, started, not-applied or uncertain effects. Applied/cancelled receipts and other Beads are not reclassified. Unreadable evidence fails closed. This inspection grants no effects or authority and does not settle receipts.

## Persistence and resource ownership

Default owner-global root: `~/.pi/runtime/delivery/`. Existing deployment runtime exclusions preserve it. No project enrollment or project file write occurs. The global root serializes distinct local clones/projects resolving to the same physical target.

Schema-1 `state.json` holds immutable receipt identity/action/authority snapshots and append-only phase/evidence events. The mutable envelope is fingerprinted, owner-private, symlink-checked, atomically replaced and fsynced, with a 16 MiB capacity bound. Capacity failure never silently drops history. Corrupt structure, fingerprints or illegal phase history fail closed. Checksums do not authenticate against a hostile same-OS writer.

Short journal locking covers reservation/history updates. Sorted physical resource leases cover observation/mutation. Resource contention fails immediately as busy; live ownership is not displaced by timeout or age. Lock order is resources → journal; no path holds journal while acquiring resources or invoking an adapter. Unrelated resources can proceed independently.

Resource IDs identify actual mutable provider objects, not Bead, adapter, or caller attempt labels. Every unresolved overlapping receipt blocks fresh intent on those resources. Per-resource/resolved-artifact causal keys cap mutation attempts at three across receipt IDs, cancellation, assignment labels, adapter labels, and expanded resource sets. Reconciliation reads do not consume mutation budget. A new artifact is a material change; a new request ID is not.

## State transitions

| Current | Allowed next states |
|---|---|
| prepared | started, applied, not-applied, uncertain, cancelled |
| started | applied, not-applied, uncertain |
| not-applied | started, applied, not-applied, uncertain, cancelled |
| uncertain | applied, not-applied, uncertain |
| applied / cancelled | terminal historical receipt |

A crash after effect issuance leaves `started`; next call observes before considering any later retry. Already-applied observation records success without another mutation. Known not-applied observations permit a separate bounded retry after fresh checks. Unknown outcomes remain reserved, even if the caller changes its adapter/assignment/request identity.

Revocation blocks queued/new mutations. It cannot undo an already-issued provider action. Reconciliation records actual outcomes without pretending cancellation reversed an external effect.

## Native worktree adapter

`worktree_policy.WorktreeCreationAdapter(repository, bead, decision_refs=...)` derives a private checkout below `~/.pi/runtime/worktrees/<repository-hash>/` and deterministic task branch. Actual Git common-directory, current commit, unoccupied path/ref/registration, safe configuration, and owner-private directories are checked before creation. The receipt binds both physical path and Git ref resources. Dirty source files are neither copied nor changed.

Native Git inherits resource lease FDs. The adapter strips inherited `GIT_*`, disables hooks/fsmonitor/submodule recursion, refuses project command-valued configuration and explicit `core.worktree`, and never forces, resets, prunes, removes, or adopts an existing branch. It deliberately does not set source `core.worktree` on creation: Git's nested checkout must target the new worktree. Git executable and owner system/global configuration are trusted, matching the existing local integration boundary.

Observation requires exact registered path/ref/object and clean target. Partial creation, wrong state, unsafe configuration and failed lookup remain uncertain. Proven native ref absence is distinct from lookup error. Already-issued native writers retain leases after caller unwinding, preventing observation/replay while checkout is in flight. Native Beads discovers the shared current database through Git common-directory discovery; no redirect/bootstrap rewrite is introduced.

Continuation CLI and Pi host consume this adapter through lifecycle reservations. Ownership and immutable action intent precede receipt publication; publication/binding share cancellation's lifecycle lock. Advancement requires fresh exact observation, and durable cancellation intent prevents restarting an effect after interrupted settlement. Orchestrated epic-worktree consumption remains unfinished.

## Verification and outstanding integration

```bash
.venv/bin/python -m pytest tests/test_delivery.py tests/test_worktree_delivery.py tests/test_worktree_policy.py -q
```

Current 27 core tests cover one-effect replay, already-applied observation, crash-after-effect, uncertainty/new-intent blocking, bounded retries across new IDs/resource sets, revocation, all preconditions, material fact/source drift, bound observations, independent resources, immediate live-holder busy response, bounded provider errors, version strictness, corrupt state, illegal phase history, and symlink refusal.

Native tests additionally cover dirty-source preservation, no duplicate creation, collisions, changed source commit, lookup uncertainty, unsafe project configuration, nested-checkout redirection refusal, real Git writer lease retention after issuing-call abort, and current shared Beads discovery. Latest core/native/legacy-worktree matrix: 43 passed. Independent scoped reviews found no P1/P2 in the 26-test core and subsequent 41-test native matrix; fresh-read API and final two test additions followed that review and remain subject to final acceptance review.

Still required: orchestrated worktree/dependency consumers; other concrete native/provider adapters; multiprocess cross-clone and replace/fsync crash injection; ordinary push/PR/main/release/local-live/staging/production fixtures; public command/receipt-reference integration; shared workflow guidance and full acceptance gates. Unsupported operations remain unsupported, not implicitly authorized.
