# agnt command reference

`agnt` is the deterministic command surface for Pi routing, context composition, action templates, run artifacts, Beads-backed work, metrics, evals, and context-health checks. Domain logic lives in `agnt_lib`; this CLI adapts it for humans, CI, and headless callers. For the conceptual overview, see [The agnt System](../../../docs/AGNT-SYSTEM.md).

Commands are designed to compose with normal Unix idioms: stdin when no file is supplied, stdout for primary output, stderr for diagnostics, and `-o` for files/directories when needed.

`agent/bin/bd` transparently delegates to the installed Beads CLI. For `bd prime` only, it removes the exact Beads-internal `Git authority: no git operations in this context` line because repository Git authority comes from project instructions, not Beads sync mode. Other commands, output, diagnostics, and exit codes pass through unchanged.

```bash
agnt [command [args]] [subcommand ...] [filename]
```

## Discovery

- `agnt -h`
- `agnt COMMAND -h`
- `agnt tasks`
- `agnt tasks --models`

Task definitions live in `tasks/*.md` and provide model-routing hints. A task is an operational label for routing; a skill is a workflow or method.

## Research

- `agnt web-search "query" [-n N] [--category it|science|news|...]`
  - Searches via the configured backend and uses its default category unless one is explicit.
  - Prints `cat: <category>` in output.

- `agnt web-fetch URL [--max-chars N] [--raw]`
  - Fetches a URL, reports status/final URL/content type, and extracts simple readable text for HTML.

## Model orchestration

- `agnt route --task TASK [--risk low|medium|high] [--budget cheap|balanced|quality] [--access auto|self-contained|repository] [--context-tokens N] [--modality text|image|audio|video] [--estimated-input-tokens N --estimated-output-tokens N --max-marginal-usd USD --metered-justification quality-benefit|missing-capability] [--monthly-paid-spend USD] [--ignore-history]`
  - Recommends a model, fallback models, thinking level, execution mode, context policy, and whether fanout is useful. Subscription-backed models rank before metered models when capability is comparable.
  - `--access repository` means repository access requires agentic execution; `--access self-contained` keeps cold packet work tool-disabled and one-shot. All metered candidates are excluded unless positive token estimates, aggregate `--max-marginal-usd`, and `quality-benefit` or `missing-capability` justification are supplied. Catalog rates estimate marginal cost and fanout cannot exceed aggregate estimate budget. Admitted metered repository children receive request, token, cost, and duration limits; admitted one-shot children receive provider output and duration limits because one in-flight provider request cannot enforce `maxCostUsd`.
  - Uses the existing task files as policy, filters by `agent/settings.json` `enabledModels` plus runtime constraints, and includes metrics hints when available. `contextPolicy: fresh` means a selected metered OpenRouter model must run through a new `subagent`, not as a root-conversation continuation.
  - For `review`, emits approved risk-specific `reviewPolicyTargets` plus deterministic monthly spend state: Astra at medium effort and high effort for high risk, Terra as subscription-backed challenger, Kimi K2.7 Code for explicitly budgeted medium-risk diversity, and Opus 5.5 for explicitly budgeted high-risk independent review. Without complete metered evidence, actual fanout stays subscription-only even when policy targets name a paid specialist. Spend counting includes OpenRouter, configured metered venues, and positive provider-reported spend from retired venues while excluding configured subscription targets. `AGNT_REVIEW_PAID_SPEND_USD` supplies an operator floor, `--monthly-paid-spend` accepts authoritative override, and reserve/hard-cap thresholds keep only subscription-backed Astra. K3 is escalation-only.
  - `--ignore-history` is reserved for deterministic policy evaluation; normal routing uses outcome history.
  - Outcome history is aggregated by model family (`agent/catalog.json`) across the global consolidated store and local pending metrics; candidates whose family shows more negative than positive outcomes over at least 5 invocations are demoted with an explicit reason.

For interactive delegation, call Archimedes `subagent` with `agent` omitted and add a single/per-child `route` object. Route fields map to `agnt route`: required `task`; optional `risk`, `budget`, `contextTokens`, `modality`, `sourceAccess`, input/output token estimates, `maxMarginalUsd`, metered justification, and `ignoreHistory`. Wrapper resolves and validates every route before child launch, intersects caller and route limits by taking each stricter value, strips local routing fields, and adds a trusted route receipt to each aligned child result. Route intent is mutually exclusive with manual `agent`, `model`, `mode`, `thinking`, `sourceAccess`, `routingTask`, or cost evidence; command failure, no candidate, malformed selection, mode-incompatible limits, and unbounded metered agentic `auto` selection return an error without launching children. Direct `agnt route` plus manual copy-then-launch remains supported for policy inspection.

Use `tasks` for parallel peers and put route intent on each routed child. Existing manual/inherited launches remain unchanged. Every metered route requires explicit justification, positive estimates, marginal budget, and route-generated bounds; parallel one-shot and repository estimates must fit aggregate `maxMarginalUsd`. Single/per-child `outputContract` values are `inline`, `artifact`, `status-only`, and `pass-no-findings`; choose `artifact` for deferred full results, `status-only` for deterministic checks, `inline` when content is needed now, and `pass-no-findings` only when explicitly requested. Omitted contracts remain `unknown`. Tracked observer generates one payload-free `invocationId` per child and uses trusted receipts for safe route task, provider/model, effective mode, and thinking. Before returning, parent writes full final, partial, and error output under `agnt runtime-path delegated-results`; tool content/details and telemetry gain bounded refs plus payload-free persistence status. Failed children expose normalized termination evidence. Named-profile projections still mark provider, target, and thinking unavailable because Archimedes does not expose those effective values.

`maxOutputTokens` bounds one provider response, not visible final-answer length; reasoning may consume that allowance before the visible final answer. Do not derive a low token cap from requested characters. Subscription-backed one-shot calls normally omit it, while the tracked wrapper keeps the 16,384-token metered one-shot backstop. An explicit lower cap remains appropriate for a bounded experiment or known spend/risk ceiling. One-shot rejects cumulative `maxTotalTokens` and `maxCostUsd`; they cannot constrain a provider request already in flight. One-shot already has one provider turn, so omit `maxProviderRequests`. Subscription-backed agentic work also omits request/token/cost caps unless an explicit bounded experiment or runaway risk requires one.

### Managed JSON result migration

Archimedes 2.11.1 script calls return `{ mode, results }` when a native report exists, rather than the old text string. Check each result's `executionOutcome`; a fulfilled call can contain failed/unavailable runs. Managed batches retain any-failed-child `isError` behavior, but available JSON evidence still reaches script callers. Output contracts now pass through the native executor as well as the managed artifact/report boundary. Pre-dispatch errors and single failures without a native report still reject through the text-error path.

`outputStatus` is `included`, `truncated`, `omitted`, or `unavailable`. Inline/unspecified answers share one 12,000-character budget in request order; later answers can be empty with `truncated` status. Non-inline contracts omit answer bodies for both single and parallel JSON. `artifact.status` and opaque `artifact.refs` report persistence; `terminationEvidence` carries normalized reason/source/limit/observed/usage state. Full bodies remain in private artifacts and internal details. Missing artifacts require evidence recovery, not blind replay. Neither `succeeded` nor `pass-no-findings` proves review quality.

```javascript
const report = await tools.subagent({
  task: "Review changed authorization checks; cite concrete defects.",
  route: { task: "review", sourceAccess: "repository" },
  outputContract: "artifact",
});
for (const run of report.results) {
  if (run.executionOutcome !== "succeeded") {
    throw new Error(run.error ?? run.terminationEvidence?.reason ?? "Child failed");
  }
  if (run.artifact?.status !== "persisted") throw new Error("Result artifact unavailable");
  text({ refs: run.artifact.refs, outputStatus: run.outputStatus });
}
```

Resolve opaque refs with the existing `agnt runtime-path delegated-results` flow. Do not parse them as filesystem paths or treat execution status as an acceptance decision.

| `outputContract` | Use | Low-failure prompt pattern |
|---|---|---|
| `inline` | Required result must be visible to parent. | Request schema-valid JSON or concise prose, with both finding/item count and character target. Keep provider allowance above visible target plus reasoning; do not add a low ad hoc cap. |
| `artifact` | Complete final response may be larger than bounded parent projection; parent persists it. | Ask child to return complete result in final response. Do not ask tool-disabled one-shot child to write a local file. |
| `status-only` | Parent needs completion state, not full findings. | Request one explicit `OK` or `ERROR` line and use lower thinking when task permits; short final text alone is not reason to lower provider allowance. |
| `pass-no-findings` | `PASS` is valid when no defect exists, but concrete findings must survive. | Request `PASS` or a small bounded finding list; never force filler when no finding exists. |

Classify failures from explicit evidence. `terminationReason=output-limit` plus `terminationSource=caller` identifies an applied caller ceiling; `wrapper` identifies the configured metered default; `provider` identifies a lower/native provider stop and may have no exact known limit. Provider/context/network failures retain their provider or process evidence and must not be relabeled from output shape. A nonzero child exit without valid stronger evidence uses `terminationReason=process-error` and `terminationSource=worker`. Malformed or incomplete JSON alone proves no failure source; it only makes a structured result invalid. Full partial output remains in parent-owned delegated artifacts.

- `agnt runtime-path KIND [KIND ...]`
  - Returns bounded JSON containing safe private directory for one runtime kind, or a `paths` map for multiple kinds. Batched resolution shares Git identity discovery but rechecks every kind. Resolver uses project `.pi/<kind>` only when Git proves path ignored and untracked; otherwise it uses mode-`0700` `~/.pi/runtime/<sha256>/<kind>`. Hash keys canonical Git common directory, including linked worktrees, or canonical working directory outside Git.

- `agnt provider-circuit status [--provider PROVIDER]`
- `printf '%s' "$ERROR" | agnt provider-circuit record --provider PROVIDER`
- `agnt provider-circuit success --provider PROVIDER`
  - Tracks exact provider venues, not model families. Deterministic quota, credit, authentication, and availability errors open circuits for 30 minutes, 30 minutes, 15 minutes, and 2 minutes respectively; all TTLs have a one-hour hard cap. Successful calls close an open venue circuit, while expiry is pruned lazily.
  - Routing excludes every candidate on an open provider and reports bounded reason/expiry metadata; other providers serving the same model family remain eligible. Private mode-`0600` state is lock-serialized and atomically replaced under a mode-`0700` runtime directory. It stores only provider, reason enum, and timestamps; it never stores raw provider errors, targets, prompts, outputs, URLs, or credentials.

Metrics use `schemaVersion: 2` and are best-effort. Each invocation gets one UUID `invocationId` before execution; the ID is random and never derived from prompt, output, target, or child index. Records normalize `parentSessionId`, optional `childSessionId` for exact delegated-trace lookup, `workItem`, safe routing `task`, `provider`, `model`, `target`, `thinkingLevel`, `invocationMode`, objective `executionOutcome` (`succeeded`, `failed`, or `unavailable`), delegated `outputContract` (or `unknown`), `status` (`succeeded` or `failed`), `failureClass` (`provider`, `process`, `timeout`, or null), optional bounded `providerFailureClass`, sanitized termination reason/source/limit/observed/effective deadline, usage, duration, and bounded artifact refs. Human outcome annotations remain separate and cannot mutate execution. `recordId` remains a backward-compatible selector, and schema-v1 records without v2 fields remain loadable with execution and output contract `unknown`. Handoff records share the private store but compact to only schema, `kind=handoff`, normalized stage/result class, and duration; summaries count them separately from model invocation/routing totals. When Pi/provider usage is unavailable, metrics JSON records `usageSource: "unavailable"` and `usage: null`. When usage is available but the provider reports zero/missing dollars for a known subscription-backed or OpenRouter model, `agnt` fills `usage.cost` with an OpenRouter-price opportunity-cost estimate and marks it with `usage.costSource: "openrouter-assumed"` and `usage.costEstimated: true`. This keeps subscription GPT usage comparable without routing GPT calls through OpenRouter.

Use unnamed `subagent` calls with route intent for peers. Set route `sourceAccess: "self-contained"` for cold complete packets and use `tasks` with one route per child for parallel dispatch. Internal eval/run workers keep the same metrics schema without exposing a second public peer command.

## Common routing flow

Repository inspection example selects and launches in one tool call (subscription default, no request/token/cost caps):

```json
{ "task": "<focused prompt>", "route": { "task": "research", "risk": "medium", "budget": "balanced", "sourceAccess": "repository" } }
```

Parallel peers carry one route per child:

```json
{ "tasks": [
  { "task": "<first prompt>", "route": { "task": "research", "sourceAccess": "repository" } },
  { "task": "<second prompt>", "route": { "task": "review", "sourceAccess": "repository" } }
] }
```

Run `agnt route --task research --risk medium --budget balanced --access repository` separately only when recommendation details must be inspected before launch.

Bounded metered repository routing adds explicit evidence inside route intent:

```json
{ "task": "<focused prompt>", "route": {
  "task": "research", "risk": "high", "budget": "quality", "sourceAccess": "repository",
  "estimatedInputTokens": 50000, "estimatedOutputTokens": 10000,
  "maxMarginalUsd": 0.10, "meteredJustification": "quality-benefit"
} }
```

One-call routed launches derive selected estimate, evidence, and hard limits internally. Caller limits may only tighten them; top-level `maxMarginalUsd` can impose a stricter aggregate parallel budget.

Cold subscription review has no caller liveness limit:

```json
{"task":"<complete packet contents>","route":{"task":"review","risk":"medium","budget":"balanced","sourceAccess":"self-contained"}}
```

Paid candidate eligibility is explicit and starts conservatively; this example may still select subscription Astra, while requested fanout details show any admitted metered challenger:

```json
{"task":"<complete packet contents>","route":{"task":"review","risk":"medium","budget":"balanced","sourceAccess":"self-contained","estimatedInputTokens":12000,"estimatedOutputTokens":2000,"maxMarginalUsd":0.10,"meteredJustification":"quality-benefit"}}
```

Metered one-shot calls retain route-generated `maxOutputTokens` and absolute `maxDurationMs`. Provider daily cap remains hard backstop because one-shot cost cannot be stopped after request launch.

For structured review findings:

```bash
agnt review validate .pi/reviews/<id>/findings.json
agnt metrics annotate <recordId> --findings-file .pi/reviews/<id>/findings.json --outcome accepted
```

`agnt review validate` validates the tracked discovery/adjudication contract and emits its summary in the same payload. Findings begin `unverified`; `confirmed`, `refuted`, and `unresolved` require verifier family, method, and evidence. Confidence is not part of the schema. Findings-linked metric summaries report status counts and confirmed-findings-per-dollar when cost is available.

## Prompt tooling

- `agnt prompt inventory [--kind KIND] [--paths-only]`
  - Lists tracked prompt/instruction artifacts such as `AGENTS.md`, skills, model/role supplements, action templates, and eval prompts.

## Action templates and run artifacts

- `agnt action list`
  - Lists verb-like action templates from `agent/actions/*.md`.

- `agnt action validate`
  - Validates that action templates reference existing routing tasks, skills, roles, allowed effects, and output contracts.

- `agnt action render ACTION [--target REF ...] [--bead ID] [--role ROLE] [--model TARGET] [--dry-run]`
  - Renders an action template into an invocation artifact bundle under resolved private runs directory unless `--dry-run` is supplied.

- `agnt runs create ...`
  - Creates a generic invocation/result run bundle. Optional orchestration fields include selected model/thinking, ticket metadata, ephemeral todo seed, worktree, dispatch policy, session policy, and memory policy. See [Run Artifacts](../../../docs/RUN-ARTIFACTS.md) for schema details.

- `agnt runs invoke <runtime-runs-dir>/<run-id> [--model provider/model] [--no-metrics]`
  - Reads `invocation.yaml`, invokes a worker, writes prompt/response/stderr/metrics artifacts, and updates `result.yaml`.

- `agnt runs update <runtime-runs-dir>/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--artifact PATH ...] [--follow-up ID ...] [--metrics-ref PATH] [--session-ref REF] [--approval-ref ID] [--decision-ref ID] [--health-check name=passed] [--closeout-check name=passed]`
  - Enriches `result.yaml` with evidence, artifacts, follow-up beads, metrics refs, session/transcript/memory refs, approval/decision refs, health/closeout checks, and terminal statuses.

- `agnt runs validate <runtime-runs-dir>/<run-id> [--require-followups-exist]`
  - Validates required `invocation.yaml` and `result.yaml` fields. With `--require-followups-exist`, every `result.yaml.followUps[]` id must resolve to a Beads item.

- `agnt work direct-start BEAD [--claim] [--scope-bead OTHER ...]`
  - Under active standing policy, repeat `--scope-bead OTHER` before first start for an explicitly approved multi-Bead work set. No separate authority JSON or project enrollment prompt. Only selected unfinished Beads are captured; local isolation is included for multiple Beads, not external delivery. Existing assignments are reused without changing their effects; mismatched/overlapping scopes fail rather than widen. Omit the flag for ordinary single-Bead work. The flag records actual assigned intent, not permission to scan/claim arbitrary ready work.
  - Starts ordinary direct work by validating and showing the Bead, validating session ownership under the private ledger lock, then optionally claiming it only when `--claim` is explicit before appending the session link. Beads 1.3.1's native claim CAS runs on every explicit claim, including retries: own claims are idempotent and foreign live claims are rejected.
  - One logical session belongs to one Bead. A conflicting prior link or outcome is not overwritten. Langfuse projection is best effort; projection failure appears as `langfuse-projection-unavailable` evidence without blocking authoritative local capture. After successful current Bead closeout, call `handoff_bead` without a target; sole ready non-epic work continues automatically, while several choices use one selection. `/new` is the human fallback when the tool is unavailable. Quitting and resuming may retain the same logical session.
  - Conflicting, finalized, missing or malformed session authority stops before claim. Claim failure writes no session link. The two stores are not one transaction: a crash/storage failure after claim may leave the claim without a link. Repair storage and retry the same session/Bead; never automatically unclaim or route claimed work through ready-only handoff. A conflicting session returns `handoff_bead` checkpoint/switch or ownership-reconciliation guidance; `/new` is only an unavailable-runtime fallback, never an ownership override. Returns bounded stage/recovery JSON, no run bundle or worktree.

- `agnt work status --session-id SESSION`
  - Reads canonical `in_progress` Beads and private local session-work correlation without mutation, returning deterministic priority/ID-ordered JSON for presentation adapters.
  - Returns no private session data beyond the linked public Bead ID. Missing correlation is unassigned; malformed ledger or query state uses a bounded error shape with empty items.

- `agnt work direct-closeout BEAD --outcome success --reason REASON`
  - Runs only after task-owned implementation changes are verified and committed. It checks execution ownership and read-only Git preflight before appending literal explicit `success`, then reads back matching session ownership/outcome before Beads closure or Git writes. Pending continuation blocks success recording under the same lifecycle lock used by reservation. Failed preflight leaves unfinished outcome unchanged; success is never inferred. Langfuse projection remains best effort and non-authoritative.
  - Uses captured assignment, never new enrollment. Requires `beads-write`, `repo-write`, and `git-commit` under standing authority before success; rereads canonical blockers/decisions and rejects a conflicting prior close reason. Active admission without captured scope fails closed. Rechecks remaining effects before native writes; later denial preserves partial state and returns `repair.safeToRetry=false`. Inactive-policy legacy direct permission stays separate.
  - Use `agnt improve outcome` separately for `partial`, `failure`, `unclear`, or manual/repair recording. Non-success does not permit closeout; checkpointed continuation creates a new attempt without overwriting that outcome.
  - Refuses tracked non-Beads changes, closes the Bead idempotently, exports canonical regular issues through `bd export --readonly` stdout to an open temporary file, and verifies target `status`, `closed_at`, and `close_reason` parity before replacing `.beads/issues.jsonl`. A verified no-follow directory descriptor binds temporary creation, replacement and cleanup; changed paths cannot redirect them into another directory. Detected namespace drift stops staging. Receipt-backed reconciliation of ambiguous close/export/commit outcomes remains unfinished.
  - Stages and creates a second local commit containing `.beads/issues.jsonl` and, when already tracked, `.beads/interactions.jsonl`. Audit changes must be append-only status-closure records for this exact Bead and reason; history edits, unrelated records, malformed appends and conflicting staged content are rejected. Untracked audit/runtime files remain untouched. It never pushes.
  - Committed legacy audit rows remain byte-for-byte history. Dirty non-closure rows require verified reconciliation by their originating owner before closeout, never deletion/untracking or inference from matching Bead ID. Beads 1.3.1 sidecars are optional/incomplete; current handoff has no status writer. Auto-export is throttled and not a portable-state guarantee; Dolt history and remote sync remain separate.
  - Verifies the same committed portable parity and clean tracked checkout required by handoff before reporting success. Returns bounded stage JSON; failure after closure is `partial`. A retry can commit validated closure audit appends left by an earlier attempt without discarding shared rows.

- `agnt work integrate --target-branch BRANCH --expected-head SHA --source-sha SHA [--timeout-seconds N]`
  - Consumes only exact local-integration authority already present in approved scope; command does not create or broaden approval. Run it from named target checkout.
  - Uses POSIX `fcntl.flock` on target-ref-scoped lock under Git's common directory, so linked worktrees share one semaphore. Random owner token plus opaque lock ID define ownership; lock evidence and persistent metadata omit repository paths, refs, command arguments, and content. Integration results intentionally retain approved source/target object IDs for verification. Kernel releases ownership on process death; next holder marks stale advisory metadata recovered without PID/time-based lock stealing. Timeout and cancellation fail closed; no daemon runs.
  - Clears ambient `GIT_*` overrides, pins the approved worktree, disables hooks/fsmonitor/signing/signature enforcement for helper Git calls, and rejects command-bearing custom merge/filter/branch-options configuration. Rechecks target branch, expected target HEAD, exact source commit, clean tracked/untracked status, and absence of merge state after lock acquisition. Runs one local `git merge --no-edit --no-verify`. Success requires source ancestry, same target branch, clean status, and no merge state.
  - Conflict runs only `git merge --abort` and verifies exact baseline restoration. Divergence, dirty state, timeout, cancellation, failed abort, or failed verification stops without alternate strategy. Process death or keyboard interruption releases the semaphore; a successor still must pass exact HEAD/clean-state checks, so interrupted mutation cannot silently continue. Exit `0` means integrated/already integrated; `3` means safe stop/conflict; `2` means invalid request or unavailable integration environment.
  - `git worktree lock` is not used: it prevents administrative prune/move/remove but does not serialize commands inside a worktree. Git's index/ref lockfiles protect individual writes, not the full preflight/merge/verification transaction.

- `agnt work handoff-check [BEAD] --session-id SESSION`
  - Internal preflight for tracked Bead handoff extension. A linked session requires one successful outcome and cleanly closed source Bead. A session with zero ownership and outcome records may hand off without closeout; malformed, conflicting, incomplete, or non-success ownership still fails closed.
  - Without `BEAD`, it selects sole ready non-epic work or returns bounded choices. Every explicit or selected target must exist in `bd ready` before fresh-session staging or process replacement.
  - Returns bounded JSON containing closed or unassigned source state, target Bead ID or ready choices, status, and any linked outcome; it does not copy transcript content, stage session, or replace process itself.

- `agnt work plan [BEAD_ID] --action ACTION --target REF --dry-run`
  - Builds a dry-run dispatch plan from a bead plus action template. It does not invoke a model or mutate Beads.

- `agnt work tree [BEAD_ID|--epic EPIC_ID] [--json] [--runs-dir DIR]`
  - Builds a Beads plan/dependency tree with metadata validation, blocker refs, approval refs, active run refs, and run context.

- `agnt work start [BEAD_ID] [--action ACTION] [--target REF ...] [--claim]`
  - Creates a run bundle for a bead/action and copies bead acceptance criteria into `invocation.yaml`. It records ticket metadata, dispatch policy, selected model/thinking, session/memory policy, todo seed, and worktree snapshot. It mutates Beads only when `--claim` is supplied.
  - Native claim checks controller authority before preparation and immediately around the write. Exact worker grants do not supply controller `beads-write`; current scope/ownership and explicit-gate revocation are checked separately. Read-only action names cannot bypass native-write checks. Scope is not enrolled or widened here.

- `agnt work run [BEAD_ID] [--action ACTION] [--target REF ...] [--preflight] [--claim] [--close-bead]`
  - Creates a run bundle, invokes a policy-selected worker from `invocation.yaml`, updates `result.yaml`, and closes the bead only when `--close-bead` is supplied, invocation succeeds, evidence exists, approval/decision refs are resolved, health/closeout checks pass, and follow-up ids resolve to Beads.
  - Direct `--model` overrides are rejected for work dispatch; tune routing with Beads metadata policy instead.
  - `--preflight` runs a focused operational doctor before dispatch.

- `agnt work audit [--json] [--scan-root PATH ...]`
  - Reports Beads queue counts and required-work signals in docs/run artifacts; fails when the queue is empty but required future work appears unresolved.

- `agnt work health [--json] [--strict-checkout] [--runs-dir DIR]`
  - Runs read-only rail-guard checks over run artifacts, Beads refs, approvals, decisions, follow-ups, stale sessions, dirty current/epic worktrees, raw-tool bypass markers, orphaned runs, and failed health/closeout checks.

- `agnt work finish <runtime-runs-dir>/<run-id> --status STATUS --summary TEXT [--evidence TEXT ...] [--close-bead]`
  - Updates `result.yaml`; closes the invocation bead only when `--close-bead` is supplied and status is `succeeded` with evidence, reconciled follow-up ids, resolved approval/decision refs, and passing health/closeout checks.
  - Native close also rechecks current controller scope, canonical constraints, ownership and exact worker gate. Canonical grant `targetBead` must match the actual work item at admission, worker launch and native effects. Older envelopes without a target require fresh canonical matching; history is not rewritten. Denial preserves result evidence. Native Beads uncertain-effect receipt recovery and orchestration worker-session transfer remain unfinished.

## Standing authority foundation

- `agnt authority template` — print tracked policy and fingerprint; does not activate it.
- `agnt authority inspect` — report owner-global inactive/active/revoked state.
- `agnt authority import-historical --input-file PATH` — explicit owner-authorized migration of recorded consent; preserves `historical-consent` / `inputOrigin=not-retained` provenance, never fabricates `human-ui`. Does not replace or un-revoke an existing admission.
- `agnt authority assign --input-file PATH` — record immutable current intent, not project enrollment. Input fields: `assignment_id`, `repository`, `beads`, `effects`, `intent_ref`, optional `denied_effects`.
- `agnt authority check ASSIGNMENT --input-file PATH` — check a resolved action; return `active` or `blocked`, execute nothing. Consumers must inspect JSON status; command success alone is not permission.
- `agnt authority revoke --reason TEXT` — block future use without deleting historical records.

Private owner state is `~/.pi/authority/`; the distinct tracked template is `agent/authority/full-delivery.json`. Neither installation nor project text activates authority. `/authority` inspects; `/authority-import <path>` explicitly imports an authorized historical record. The `standing_authority` model tool exposes inspection/checking only. Historical input-channel traceability was explicitly relaxed for migration during pi-pvcg; this is not a claim of cryptographic provenance or permission for arbitrary future widening.

Optional orchestration can select a private assignment with `metadata.pi.standingAssignment`. Local implementation requires `repo-write`; worker invocation revalidates actual repository, Bead, effects, and revocation. Explicit approval references keep the exact-grant path and cannot fall back to standing permission after rejection. Generic external writes need concrete delivery adapters. Quality experiments still require their original exact grants.

Source changes are not live rollout. Owner narrowed pi-pvcg to continuation and approval friction: useful partial resume, dirty switching, pending-decision recovery, and valid-authority reuse/revocation. New external delivery adapters, universal effect recovery, dependency detours and expanded epic/worker orchestration are deferred, not completed. See [authority contract](../authority/SPEC.md).

## Pending decision recovery

`ticket_decision_resolve` recovers a missing/stale UI binding for an existing pending decision, checks current target ownership, and redisplays canonical scope. A question takes a fresh human selection/custom answer; standing authority and agent suggestions are not answers. No new Bead/blocker is created.

The trusted bridge uses `agnt approvals recover-context ID --json` and `agnt approvals rebind ID --json` with private process-bound proof, not ordinary resolver flags. Legacy unprotected question modes require one explicit UI verification before first binding; subsequent recovery reuses that durable mode constraint. New requests fingerprint selection mode/custom-answer policy. Every positive resolution checks pending state and immutable question scope, including the direct path. Original exact grants and request fingerprints remain unchanged. See [decision recovery contract](agnt_lib/decision_rebinding.SPEC.md).

## Checkpointed continuation

Normally supply concise current `progress` directly to `handoff_bead`: objective, decisions, completed work, next steps, blockers, verification, task-owned relative paths and exact artifact references. The same call persists the checkpoint; no scratch JSON or transcript copy. Scope comes from execution ownership, never progress text.

`agnt work checkpoint BEAD [--input-file PROGRESS.json|-]` is the lower-level interface; `-` reads bounded JSON from stdin (64 KiB). It saves measured workspace and progress without closing work or replacing an outcome. Omitted progress preserves earlier curated facts; it cannot invent current findings. Do not combine new progress with an existing checkpoint or transition recovery. `transition-recover ID` returns the actual referenced checkpoint for the child to read.

`agnt work transition-check [BEAD] --mode resume|switch|next --session-id SESSION [--checkpoint-ref REF] [--checkout PATH]` returns a read-only readiness/idle manifest. `transition-context --session-id SESSION` discovers source or child reservations; `transition-status ID` and `transition-recover ID` inspect exact persisted state. Host-only prepare/stage/launch/attach/cancel details are in the [lifecycle contract](agnt_lib/work_lifecycle.SPEC.md).

`handoff_bead` supports optional `progress`, `mode`, `checkpointRef`, `checkout`, and `transitionId`, alongside `targetBead`. Unfinished linked work defaults to resume, or assignment-scoped switch for a different target. Cross-Bead switching uses an existing isolated checkout or assignment-authorized native creation. Existing isolation reservations recover through the same receipt; changed requests conflict rather than silently retargeting. Recorded cancellation settles without deleting worktrees or replaying effects. `/handoff-bead resume|switch|next [BEAD]` and `/handoff-bead recover ID` share the adapter. Closed/unassigned ready-work handoff remains separate.

Supported TUI runtime stages a fresh parent-linked child, preserves dirty files and historical outcomes, and attaches before child tools run. Run-level tool/project/context restrictions survive replacement; old prompts, attachments and session selectors do not replay. Cross-checkout switches with custom prompt overrides, Node launch options or unknown extension flags stop before staging/shutdown rather than reinterpret relative options. Preserve that reservation and reconcile runtime setup; do not bypass the guard. Headless continuation returns a read-only host-required manifest. Blocked isolation never stages a child; slash commands display recovery status. Uncertain launch is not replayed; known pre-exec compensation, including lost launch acknowledgement before shutdown, requires the original host's private capability. These are tested source adapters, not evidence of live rollout.

## Approvals and ticket gateway

- `agnt approvals request --kind question|approval --target-bead ID --question TEXT --context TEXT --option TEXT ... [--selection-mode single|multi] --preview-* ...`
  - Creates a durable Beads decision/approval record, appends its canonical fingerprint as a reserved provenance comment before adding the target blocker, and records approval/decision refs in the requesting run when supplied. Questions require selection mode and record that typed custom responses are available. Direct CLI requests remain unbound blockers; only the Pi ticket tools can add a session/tool-call-attested resolver binding.

- `agnt approvals resolve DECISION_ID --outcome approved|answered|rejected|cancelled|timed-out [--answer TEXT] [--structured-answer] [--selected-option TEXT ...] [--custom-input TEXT]`
  - Records the human outcome and public-safe UI resolver kind in Beads, never raw Pi session identifiers or resolver secrets. Approved/answered outcomes require the active Pi ticket tool's parent-authenticated socket proof, matching request-secret/session fingerprints, and a currently pending ticket tool call; direct resolver flags and unbound CLI calls fail closed. Restart/reload recovers the existing pending gate through the trusted bridge and redisplays its original scope for a fresh human answer; do not create a replacement blocker. Answered questions may persist predefined selections and typed input separately while retaining a readable answer summary; `--structured-answer` preserves an explicit empty multi-selection. Structured question fields cannot approve an action. Approved/answered decisions close the decision bead; rejected/cancelled/timed-out decisions keep visible blockers.

- `agnt gateway --payload JSON`
  - Executes strict ticket-gateway operations (`list`, `show`, `tree`, `create_draft`) for Pi extensions. Payloads are enum-based and reject shell-like/raw-command fields. Use dedicated `ticket_question`, `ticket_approval`, and `ticket_decision_resolve` tools for human decisions.

## Langfuse evaluator configuration

- `agnt langfuse check [--quiet] [--manifest PATH]`
  - Compares tracked evaluator and live-observation rule definitions with configured Langfuse project. Read-only; exits `1` on drift and `2` when configuration cannot be checked.
- `agnt langfuse apply [--quiet] [--manifest PATH]`
  - Creates missing evaluator versions and creates or updates managed rules. It never deletes unmanaged Langfuse resources.

Definitions live in `agent/langfuse/evaluators.json`. Credentials come from `LANGFUSE_*` variables or private `agent/pi-langfuse/config.json`.

## Operational health

- `agnt doctor [--json] [--strict] [--check CHECK ...] [--skip CHECK ...]`
  - Checks local Pi/agnt operational readiness: core binaries, Python, git root, Beads, Node LTS policy, provider env vars, and core config parsing.
  - Reports JSON with check status, evidence, redacted env-var presence, warnings, and suggested actions. `passed` is false for degraded or failed reports; CLI `--strict` still exits nonzero only on failures.
  - Beads profile is 1.3.1. Version mismatch, malformed JSON, unsupported doctor, or unhealthy checks cannot prove health. Embedded full doctor stays degraded/unverified; supported list/conventions checks report limited evidence, not database integrity. No install, repair or migration occurs.
  - `--strict` exits nonzero when required checks fail. The doctor is read-only and never edits shell startup files.
  - After repeated tool, provider, or environment failures, run `agnt doctor` and fix the environment instead of retrying blindly.

- `agnt doctor node [--json]`
  - Runs the Node-focused check. It detects the active `node`, Node major, nvm/fnm/asdf/Nix/Homebrew hints, and suggests LTS remediation.
  - The doctor is read-only. It never edits home shell files; suggestions respect conventions such as `~/.local/etc/profile.d/`, chezmoi/yadm, and Nix/Home Manager.

## Context health

- `agnt context-health [--strict] [--max-skill-lines N] [--overlap-threshold N] [--skill-discovery-limit N] [--skill-discovery-warning-remaining N]`
  - Checks root/overlay guidance, routing tasks, and all loadable skill Markdown for stale helpers and gate-weakening phrases.
  - Fails on unsupported multiline skill descriptions or discovery metadata above the default 8,000-character budget.
  - Warns at or below the configurable remaining-character threshold (default 1,000), reporting used, limit, remaining, threshold, and the five largest skill contributors.
  - Also warns on oversized unallowlisted skills and overlapping skill descriptions.
  - `--strict` exits nonzero when failures are found; warnings remain entropy signals.

## Private quality kernel

- `agnt quality capture --payload JSON --json`
  - Appends one schema-validated `invocation` or `result` fact to private `quality/ledger.jsonl`. Required fields are `schemaVersion`, `recordType`, `sessionId`, `beadId`, and `evidenceRefs`; `result` also requires `outcome` (`success`, `partial`, `failure`, or `unclear`). Evidence refs require an allowlisted `artifact`, `invocation`, `observation`, `result`, `run`, or `trace` prefix. Unknown fields, unsafe refs, raw bodies, URLs, credentials, JWTs, secrets, and paths are rejected.
- `agnt quality normalize-result [--payload JSON] --json`
  - Normalizes one editor/Nvim review or BetterWright human-takeover result without persistence. Exact metadata binds a canonical relative artifact path and sensitivity, scope, EvidenceRefs, human adapter/session provenance, category, state, gaps, and optional safe resumption path. Partial/lost/uncertain takeovers require resumption metadata. Absolute or escaping paths, public/private sensitivity leaks, raw evidence, and nested authority claims fail closed; save/manual execution never implies acceptance or authorization.
- `agnt quality assess --activity capture|work-learning|architecture-coherence|capability-calibration|quality-system-review (--snapshot JSON | --collect) --json`
  - Validates the tracked five-activity control plan and an exact snapshot with `schemaVersion`, `triggered`, `evidenceRefs`, `gaps`, and `signals`. `--collect` derives durable Beads, Git, run, health, context, and eligible-session signals; optional `--root`, `--runs-dir`, and `--no-beads` bound collection. Same snapshot, activity, and policy produce the same receipt and dedupe key. Snapshot bodies are fingerprinted, not copied into receipts.
  - Collected work preserves unknown and lower-bound evidence, suppresses duplicates carrying current or legacy labels, and emits only `quality:<activity>` on new work packets. Legacy `maintenance:*` labels are read-only compatibility inputs.
- `agnt quality apply --receipt ID --json`
  - Revalidates one persisted receipt against current policy. `disabled`/`observe` records only a no-op or one private assignment. A reviewed `autonomous` policy may create or deduplicate one sanitized Bead through the existing Beads adapter only when an exact active grant allows `create-bead` + `update_beads`; deterministic target identity and Q14 claim/settlement prevent another dispatch.
  - Scheduler-facing assess/apply JSON adds stable `resultClass` (`no-op`, `review`, `human`, `applied`, or `blocked`) and explicit `gaps`. `blocked` exits 3; `human` exits 4. Caller supplies signal or periodic-backstop snapshots and owns cadence; no scheduler, sleep, poll, or service exists here.
- `agnt quality status --json`
  - Reports current mode, policy identity, and private receipt/application/assignment counts.

All quality runtime writes are bounded and private (`0700` directories, `0600` files). Invalid input or unsafe private state returns a sanitized JSON error and exit 2. Omit `--payload` or both `--snapshot` and `--collect` to read JSON from stdin. See `pi/agent/quality/SPEC.md` for invariants and failure modes.

## Private improvement review

- `agnt improve link BEAD [--json]`
  - Idempotently links the current private Pi session to one exact public work-item ID in the local quality ledger, preferring canonical `PI_SESSION_ID` and falling back to the `PI_SESSION_FILE` stem. Existing local link/outcome ownership for another Bead fails closed with `handoff_bead` recovery and a `/new` human fallback instead of being overwritten. `agnt work direct-start` normally handles this for interactive work. Matching Langfuse score projection is best effort.
- `agnt improve outcome BEAD success|partial|failure|unclear [--json]`
  - Idempotently backfills the same-Bead local work-item link and records an explicit final session outcome, then best-effort projects matching Langfuse scores. Ordinary successful direct work records `success` through `agnt work direct-closeout`; use this command separately for non-success or manual/repair recording. Scans keep objective execution and sampled apparent judgment separate, prefer only projected explicit outcomes whose Bead metadata matches session correlation, and otherwise prevent failed or unavailable execution from being promoted by a positive apparent score. Historical projection mismatches become count-only `mismatched-work-item-outcome` capture gaps.
- `agnt improve scan [--since ISO] [--until ISO] [--limit N] [--max-traces N] [--recheck] [--dry-run] [--json]`
  - Reads up to `--max-traces` traces (default 500) and writes a schema-3 private packet plus one deterministic policy-v4 ReviewAssignment under `~/.pi/improvement/`; `--limit` is capped at 20 and `--dry-run` writes nothing. Assignment scope, EvidenceRefs, rubric, demonstrated-capability and provider-access constraints, result contract, one-attempt stop rules, and empty effect authority are fixed. Safe output reports only opaque assignment ref and write status. A fixed five-minute settlement lag excludes active ingestion. Discovery reads through a bounded five-minute lookahead so a child completed before the watermark can still join its later parent projection; only traces at or before the watermark enter root selection. The private packet records requested end, watermark, and read cutoff; pass its `scan.until` back as `--until` to replay the settled cohort. Safe schema-1 output reports only lag/exclusion state and count-only discovery/classification health, never packet path or private timestamps.
  - Exact discovered agentic child sessions are excluded before root eligibility, review-score coverage, and `--limit` selection. Projection observations fetched for classification are cached for selected roots. Incomplete discovery, truncated projection observations, and malformed declarations remain lower bounds rather than guessed roots or children. Selected roots remain capped at 20 traces and 500 observations per trace.
  - Private features report distinct execution/apparent/final outcomes, allowlisted error taxonomy, and existing projection IDs plus timing. Required generation usage dimensions are `input`, `cacheRead`, and `output`: present zero is valid; a missing, Boolean, negative, non-finite, or fractional value makes only its token aggregate null and adds `missing-usage`. Count-only cohort health separates lifecycle, usage, release/source provenance, payload-byte, and limit-termination coverage from missing and present-zero states without emitting raw provenance or termination values. Tool payload normalization remains downstream and never copies payloads. Private packets also project promoted-finding matches; safe output contains no raw prompts, tool I/O, IDs, paths, or projection timing.
- `agnt improve review REPORT RESULT [--apply] [--json]`
  - Validates the policy-v4 result against exact assignment, packet EvidenceRefs, and shared Finding schema; completion must cover every assigned session exactly once. Unavailable, timed-out, privacy-uncertain, and invalid results become an explicit one-attempt human route with no marker, finding, effect, or paid retry. `--apply` writes idempotent private session markers and updates matched post-change monitoring only for a completed valid result. Five reviewed matches validate a finding; explicit recurrence uses a new finding's optional `relatedFindingId`. Monitoring remains private. Public work creation now goes through receipt-bound `quality apply`; historical policy-v1/v2/v3 results remain readable.

Private telemetry, IDs, excerpts, URLs, user content, and absolute paths stay out of committed Beads.

## Knowledge graphs

- `agnt graphify [ARGS...]`
  - Runs the Graphify CLI (`graphify`) if installed, otherwise falls back to `uv tool run --from graphifyy graphify`.
  - Never installs project-local Graphify refresh hooks implicitly.
  - `agnt graphify hook install|status|uninstall` passes through Graphify's native hook manager; install/uninstall requires user approval in agent workflows.
  - The tracked `graphify` Pi skill lives at `agent/skills/graphify/SKILL.md` and provides `/graphify` workflow guidance.

## Evals

- `agnt eval list`
  - Lists eval definitions under `agent/evals/*/eval.json`.

- `agnt eval run EVAL_ID [--dry-run] [--models provider/model[,provider/model...]] [-o DIR]`
  - Runs a filesystem-defined eval and writes `result.json` plus any model outputs under `.pi/eval-runs/<timestamp>-<eval>/` by default.
  - Route evals call `agnt route`; instruction evals call `agnt instructions`; pytest evals run bounded `tests/` node IDs without model calls; invoke evals use the internal headless worker and capture metrics automatically when not dry-run.
  - Invoke evals may set `skill` to a path relative to `eval.json`; its contents are embedded before the scenario for cold skill-behavior checks. Assertions support `nonEmptyOutput`, `contains`, and `notContains`.

## Metrics

- `agnt metrics status [--metrics-dir DIR]`
  - Prints pending raw metric count and aggregate totals as JSON.

- `agnt metrics annotate [selector|latest] [--outcome OUTCOME] [--risk-category LABEL] [--thinking-level LEVEL] [--human-override|--no-human-override] [--fallback-used|--no-fallback-used] [--notes TEXT]`
  - Appends annotation under resolved private `metrics` directory without mutating raw metric files.
  - Selectors may be `latest`, a `recordId`, a source file path, or a metrics filename basename.
  - Valid outcomes: `unknown`, `accepted`, `rejected`, `verified-pass`, `verified-fail`, `escalated`.

- `agnt metrics consolidate [--metrics-dir DIR] [--output FILE] [--stage] [--keep-raw]`
  - Appends one compact commit-level JSON line to the global runtime store `~/.pi/metrics/agent-invocations.jsonl` by default (`AGNT_METRICS_OUTPUT` or `--output` override). The store is untracked telemetry shared across projects; it feeds `agnt route` outcome hints. The auditable self-improvement record is the git history of policy files (tasks, catalog, model overlays), not the telemetry itself.
  - Applies annotations before summarizing/compacting records.
  - Moves consumed raw metrics to resolved private `metrics/consumed/<timestamp>/` unless `--keep-raw` is used.

- `agnt metrics reset [--metrics-dir DIR]`
  - Deletes pending raw metrics without appending an aggregate.

- `agnt metrics prune [--consumed-dir DIR]`
  - Deletes consumed raw metrics.

To consolidate metrics automatically before commits, install a local hook that runs `agnt metrics consolidate`. This repository does not currently ship a tracked `.githooks` hook; manual consolidation is the portable default.

## Instruction context

- `agnt instructions [ROOT.md] [--context PROVIDER/MODEL] [--role ROLE] [--roles] [--sources] [--check] [--no-project] [--project]`
  - With no `ROOT.md`, generates layered instructions from global `~/.pi/agent/AGENTS.md`, global model/role supplements, and discovered project instruction files from git root to current directory (`AGENTS.md`, `AGENT.md`, `CLAUDE.md`). This is the normal peer-prompt path.
  - With explicit `ROOT.md`, generates only that package unless `--project` is supplied; use this for package checks and special cases.
  - Model files first use catalog family overlays when available, for example `AGENTS.d/models/gpt-6.1-sol.md` for that family.
  - Provider/model-specific files use slash-style paths, for example `AGENTS.d/models/openrouter/minimax/minimax-m3.md`.
  - Loads model files from least to most specific: family overlay first, then provider/model overlays such as `openrouter.md` and `openrouter/minimax/minimax-m3.md`.
  - Uses append-only concatenation. Prefer moving optional context into role/model files over patching root instructions.
  - `--roles` lists available global/project role files and compact metadata; `--check` validates package structure and flags suspicious safety-gate weakening phrases.

## Workflow artifacts

- `agnt plans-dir`
  - Prints and creates the active plans directory.
  - Default: `<git-root>/.pi/plans` or `$PWD/.pi/plans` outside git.
  - `PI_PLANS_DIR` overrides.

## Supporting commands

Some implementation-specific scripts remain in this directory, but agent-facing instructions should prefer `agnt` unless they intentionally need a lower-level helper. The `agnt` executable is a front controller; command implementation code lives in importable `agnt_lib/` modules.
