# Self-Improvement Loop

How this setup learns from model usage while keeping private evidence out of
tracked policy and Beads. It improves routing, prompts, tools, and monitoring.
For broader workflow/context design principles, see
[Self-Improvement Principles](SELF-IMPROVEMENT-PRINCIPLES.md).

Principle: telemetry is runtime state; policy is config. Consolidated metrics
live in `~/.pi/metrics/`; raw records use the resolver-selected private metrics
directory and are never tracked. Project `.pi/metrics/` is used only when Git
proves it safe, with a repository-keyed `~/.pi/runtime/` fallback otherwise.
What git tracks — and what makes the learning auditable — are the policy files
the metrics justify changing:

- `pi/agent/tasks/*.md` — preferred/qualified/avoid model lists per task
- `pi/agent/catalog.json` — model families, venues, cost facts
- `pi/agent/AGENTS.d/models/<family>.md` — per-model prompt overlays
- `pi/agent/evals/` — deterministic gates
- `scripts/eval-workflow-compliance.sh` — opt-in model-backed behavioral canary

## The loop

```text
metrics -> annotate -> consolidate -> route hints/demotion
                              -> policy edit -> eval -> commit
direct lifecycle -> local quality ledger -> best-effort Langfuse projection
Langfuse sessions -> private scan + ReviewAssignment -> authorized contextual review
                  -> validated result -> private marker -> sanitized Bead
                  -> implementation -> matched monitoring
Beads/git/runs/health signals -> quality assess -> observe assignment or bounded canary packet -> receipt
```

## Trigger and receiver ownership

`pi/agent/quality/control-plan.json` is the sole quality trigger and receiver owner. Closeout capture is minimal: root-session settlement and explicit work-item outcome record bounded local facts but do not independently launch a retrospective, lifecycle review, extraction pass, or simplification. Aggregate review is signal-plus-backstop: deterministic signals may make an activity due, and an external caller may supply a bounded backstop snapshot, but this repository stores no clock or schedule. Specialized skills keep their judgment methods and explicit direct invocation; skills do not schedule themselves, choose another receiver, grant mutation authority, or maintain another finding/work registry.

### 1. Capture

Internal eval/run workers write metric records (model, family, task, tokens,
cost, latency) to the resolved private `metrics/invocations` directory.
The tracked observer converts Archimedes unnamed `subagent` results
to the same schema. Projection, parent-owned artifact, and metric records share
invocation, provider, model, target, effective thinking, and optional output
contract dimensions; missing/legacy contracts are `unknown`. Config-less workers
record thinking `default` because Archimedes passes no thinking override. Metrics
store usage, timing, payload lengths, bounded artifact refs, contract, and sanitized
termination reason/source/effective deadline—not prompt or response bodies.
Named-profile projections mark unavailable dimensions
explicitly, while metrics remain skipped because Archimedes does not expose their
effective provider or thinking level.

`subagent-result` quality evaluation receives a bounded view of parent-held
output plus objective outcome, declared contract, artifact persistence/content
status, and ref count. Parent metadata also carries validated `effectiveMode` and
a declared child-trace expectation derived from Archimedes's resolved execution
evidence. Failed-child projections retain bounded termination evidence alongside
partial output, while complete output and errors remain in parent-owned artifacts.
Agentic children with a usable foreign key are expected available;
isolated one-shot children are expected unavailable. It does not receive raw refs
or filesystem paths. Requested status-only and PASS/no-findings responses are
judged against that contract; missing required inline/artifact output remains
visible as poor quality independently of objective execution outcome.

The local private quality ledger owns direct session/Bead links and explicit
outcomes. `quality-lifecycle.ts` calls `agnt quality capture` at root session
startup and after agent settlement with session/Bead IDs plus bounded invocation
or result EvidenceRefs; it never sends prompt, output, or tool payload bodies to
the local CLI. An unassigned startup is re-resolved after settlement because
`agnt work direct-start` normally links work after Pi starts. Explicit task
outcomes remain owned by outcome/closeout commands, not inferred from a settled
agent turn.

Bounded root prompt/output projection remains best effort. Missing pi-langfuse
package, registration, service capture, or observer becomes an explicit gap and
cannot block local capture, direct start, status, or closeout. Evaluator-ready
result projections share the Pi session ID, allowing sampled outcome scores to
join the root agent trace without heuristic matching when Langfuse is available.
`agnt improve` reads bounded Langfuse cohorts and writes private packets under
`~/.pi/improvement/`; it does not become direct-work authority.
Runner sessions correlate from run bundles; interactive work links through
`agnt work direct-start`. Successful closeout uses
`agnt work direct-closeout <bead> --outcome success --reason <reason>`; use
`agnt improve outcome <bead> <partial|failure|unclear>` separately for non-success
or manual/repair recording. One logical Pi session belongs to one Bead. After
current Bead successful closeout, agents call `handoff_bead` without a target. A persisted TUI
session with zero ownership records may hand off directly; linked sessions retain
successful-outcome and clean-closeout requirements. Tool continues sole ready
non-epic work automatically or asks once when several choices exist, then revalidates
selection. It stages one empty parent-linked session, gracefully replaces Pi process,
and sends bounded Bead references plus `bd prime`, `bd ready`, and claiming
`direct-start` instructions. Fresh work retrieves only referenced durable state;
source transcript is not copied. `/new` remains human fallback when automated
handoff is unavailable.
Quitting and resuming may retain same session. Link and outcome
commands fail closed rather than overwrite conflicting local ownership or
malformed ledger state. Direct closeout appends explicit success locally and
reads it back before Git or Beads work. Outcome recording idempotently backfills
the same-Bead link; best-effort Langfuse projection overrides sampled evaluator
guesses only when its Bead metadata matches correlation. The ledger stores only
bounded structural rows—never prompts, responses, secrets, absolute paths, or
public Bead descriptions—and stays outside git and committed Beads.

### 2. Annotate (the human/orchestrator signal)

Label outcomes as a side effect of normal work — the review and verification
skills include this step:

```bash
~/.pi/agent/bin/agnt metrics annotate latest --outcome accepted
~/.pi/agent/bin/agnt metrics annotate <recordId> --outcome rejected --notes "hallucinated findings"
```

Outcomes: `accepted`, `rejected`, `verified-pass`, `verified-fail`,
`escalated`. Unlabeled records stay `unknown` and carry no routing signal.

Optional Langfuse human annotation imports use current documented queue and v3
score APIs:

```bash
~/.pi/agent/bin/agnt improve annotations <queue-id> --json
```

Import reads at most 16 queue items and 16 `source=ANNOTATION` scores with
`details,subject,annotation`, plus queue score configs. Numeric/categorical/text/
boolean scores, score comments, and `CORRECTION`/`output` rows become private
opaque EvidenceRefs; values, comments, corrected outputs, project/subject IDs,
and reviewer IDs are not copied. Output keeps reviewer refs, score-config types,
queue scope counts, completeness, and fixed gaps. Unavailable, truncated,
pending, or incompletely bound queues stay `unavailable`/`partial`; imported
evidence has empty authority and never means acceptance or authorization. API
contracts: [Annotation Queues](https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues),
[Scores API v3](https://langfuse.com/docs/api-and-data-platform/features/scores-api),
and [Corrections](https://langfuse.com/docs/observability/features/corrections).

Code review also records finding-level verification instead of treating invocation
acceptance as defect evidence:

```bash
agnt review validate .pi/reviews/<id>/findings.json
agnt metrics annotate <recordId> \
  --findings-file .pi/reviews/<id>/findings.json \
  --outcome accepted
```

The tracked schema requires a concrete location, claim, failure scenario, and
evidence. Findings start `unverified`; `confirmed`, `refuted`, and `unresolved`
require fresh verifier method/evidence. Metrics aggregate those outcomes and
confirmed-findings-per-dollar by model. Reviewer confidence and agreement do not
control escalation.

### 3. Consolidate (durable, cross-project)

```bash
~/.pi/agent/bin/agnt metrics consolidate
```

Appends compact records to the global store
`~/.pi/metrics/agent-invocations.jsonl` (override: `AGNT_METRICS_OUTPUT`). Run
this manually or from a locally installed hook when you want pending metrics to
contribute to cross-project routing history.

### 4. Routing feedback (automatic)

`agnt route` aggregates outcome history **by model family** (so evidence from
one venue covers all venues of the same weights) and demotes any candidate
whose family shows more negative than positive outcomes over ≥5 invocations.
For review, approved risk-specific fanout and month-to-date marginal-spend
gates apply before model output exists: Terra leads, Kimi K2.7 provides bounded
medium-risk diversity, Opus 5 handles high-risk independent review, and Kimi K3
is escalation-only. Reserve and hard-cap states keep subscription-backed Terra
only. These deterministic gates do not use model self-confidence.
The demotion is visible in the `reasons` field. Persistent patterns deserve a
policy edit: move the model in the relevant `tasks/*.md` frontmatter and
commit with the evidence summarized in the message
(`agnt metrics status` gives the aggregate).

### 5. Private review and safe promotion

```bash
agnt improve link <bead>                                  # manual/repair correlation
agnt work direct-closeout <bead> --outcome success --reason <reason>
agnt improve outcome <bead> <success|partial|failure|unclear> # non-success/manual/repair outcome
agnt improve scan --since <ISO> --until <ISO> --limit 5 --max-traces 500 --dry-run --json
agnt improve scan --since <ISO> --until <ISO> --limit 5 --max-traces 500 --json
agnt improve review <report> <result>          # validate assignment-bound result
agnt improve review <report> <result> --apply  # private session markers
agnt quality assess --activity work-learning --snapshot <json> --json
agnt quality apply --receipt <receipt-id> --json               # granted public work
```

`link` appends an idempotent local `invocation` row containing only bounded
session/work-item identity and safe evidence refs after validating existing local
ownership. Direct closeout appends a local `result` with literal `success`, then
reads back that same-session/same-Bead value before any Git or Beads closeout
work. `outcome` remains available for non-success and manual/repair recording.
Both paths project matching categorical Langfuse scores best effort; projection
failure is an explicit evidence gap, not an authority failure. Conflicts expose
only `handoff_bead` recovery plus the `/new` human fallback, not prior owner or
session IDs. Scans keep objective
`executionOutcome`, sampled `apparentOutcome`, and explicit human outcome distinct.
An explicit human outcome is authoritative only when its Bead metadata matches the
session correlation; historical mismatches are ignored as outcomes and counted as
`mismatched-work-item-outcome` capture gaps. Otherwise deterministic failure maps
final outcome to `failure` and unavailable execution maps it to `unclear` before
sampled apparent judgment is considered.
Useful partial output remains visible as apparent quality, but cannot turn failed
execution into successful final outcome. `scan` traverses pages up to the operator
trace cap (default 500). A fixed five-minute settlement lag moves a requested active
end time back to an ingestion watermark. Discovery reads through at most one lag
interval after that watermark to join later parent projections, but only traces at
or before the watermark enter root selection. Private packets retain requested end,
watermark, and read cutoff; safe output exposes only lag and active-window-excluded
state. Reuse the packet's `scan.until` as `--until` to replay the same settled cohort.
Empty settled windows fail closed.

Each non-empty current scan also writes one deterministic private ReviewAssignment
beside the packet. Safe output exposes only its opaque artifact ref and write status.
The assignment binds at most 20 session EvidenceRefs to the tracked policy-v4
rubric and existing non-mutating `review` action. It requires demonstrated reviewer
capability and explicit provider authorization for private evidence, defines the
result fields, permits one attempt, and carries no effect authority. Human and
local/self-hosted review satisfy the default privacy classes; another provider must
be explicitly authorized before packet access.

Current results must cite the exact `assignmentId`, packet/report policy, and
session EvidenceRefs; completion covers every assigned session exactly once.
`reviewStatus` is `completed`, `unavailable`, `timed-out`,
`privacy-uncertain`, or `schema-invalid`. Non-completed or invalid output produces
an explicit gap and `human` route with no marker, finding, effect, or automatic
paid retry. Reviewer output cannot grant effects or set capability mode, grant,
or authority.

Discovery reports valid API totals, scanned/attributable/unattributed counts, root
and excluded-child session counts, classification completeness, and continuation
state. Exact agentic child sessions declared by bounded discovered projections are
removed before review-score coverage and root selection. Classification reads are
cached when their root is selected. Incomplete discovery, truncated observations,
and malformed declarations make cohort health a lower bound rather than forcing a
root/child guess. Repeated pages stop as incomplete. Selected root sessions retain
20-trace and 500-observation-per-trace caps with capture-gap markers. Private scan
packets use schema 3; safe scan summaries and review results remain schema 1,
current review policy is `v4`, and historical schema-1/2/3 packets with `v1`–`v3`
decisions remain reviewable. Safe output reports packet and assignment write status
but not private paths.
For the exact
`pi-langfuse-1.5.7-dual-null-dual-26` TOOL fingerprint, scans report both tool
payload-byte aggregates as unavailable (`null`) and record rule status plus
matched/examined observation counts under `payloadByteMetadata.toolIo`. Missing
or invalid nonfingerprint metadata makes only the affected aggregate unavailable;
no TOOL observations still report zero. Gaps distinguish
`inferred-tool-payload-bytes`, `missing-tool-payload-bytes`, and the preserved
`observation-limit`. Non-null payload-byte values are bounded-preview estimates,
not raw payload sizes. Raw Langfuse records remain unchanged, and packets never
copy tool payloads. Generation token aggregates require non-negative integral
`input`, `cacheRead`, and `output` fields. Present zero remains available; a missing,
Boolean, fractional, negative, or non-finite field nulls only its affected private
aggregate and adds `missing-usage`. A present empty `usageDetails` object is not
replaced by legacy `usage` fallback data.

Scans use exact links and payload-free tool-error signals. Each private session
feature also includes schema-1 `errorTaxonomy`: count-only
raw and unclassified-raw error health plus classified/actionable/non-actionable/
unknown signal totals,
primary classes (`expected`, `recovered`, `provider`, `infrastructure`, `agent`,
`unknown`), sources, and independent outcome-blocking state. Observation-class
precedence is explicit safe producer class, provider metadata, timeout/artifact
infrastructure metadata, process failure, evaluator error, then `unknown`;
fingerprinted tool failures contribute separate recovered/infrastructure/unknown
signals. Source precedence is explicit source, provider, artifact, evaluator,
tool, process, then unknown. Failed root `interactive-result` is always
outcome-blocking; otherwise an explicit Boolean is used or the state stays
unknown. Expected/recovered signals never increase actionable count; unknown is
retained rather than inferred. Raw observation counts and classified-signal
counts use separate denominators to avoid relabeling every error observation as
a mistake.

Each scan also emits the same nested schema-1 `cohortHealth` aggregate in the
safe schema-1 summary and private schema-2 packet. It covers only selected,
eligible sessions whose observations and scores were fetched; it does not add
Langfuse calls. Provider and model rows are session memberships, so a session
with multiple dimensions contributes once to each row and row totals may exceed
the observed-session count. Rows include final-outcome counts; missing or unsafe
dimensions stay in explicit unknown-session counts instead of being inferred or
copied. A session with both safe and unsafe dimension values contributes to its
safe membership row and its unknown count; `invalid-provider` and
`invalid-model` preserve that gap. Evaluator coverage reports sessions
with/without evaluator outcomes, outcome-record counts, and evaluator timeout
counts. Error class/source/blocking totals sum the existing per-session taxonomy,
and capture-gap totals use the existing fixed gap categories. Additive
`childTraces` totals classify parent projections by effective mode and by actual
bounded-discovery state: `available`, `expected-unavailable`, `missing`,
`ambiguous`, `incomplete`, or `unknown`. Exactly one completed or finalized
cancelled discovered root is available; a root with neither marker remains
incomplete. No discovered root is expected for an isolated one-shot child; it is a
missing gap only for a successful agentic child under complete discovery.
Malformed declarations, missing foreign keys, failed children without roots,
out-of-window child starts, and incomplete discovery remain unknown rather than
guessed. Private session features also retain allowlisted `subagent-result` projection
lineage and timing already supplied by Langfuse and Archimedes: observation, trace,
parent-observation, invocation, and child-session IDs; child index/mode/availability;
and start/end/latency. Parent identity remains the enclosing session ID. No second
lineage key is invented. Raw projection input/output is never copied. Safe cohort
summaries contain none of these IDs or times, and classification adds no per-child
Langfuse lookup.

Per-session `cost` remains the historical Langfuse nominal USD value. Additive
schema-1 `costAccounting` classifies each observed generation from enabled
tracked catalog targets: subscription generations contribute zero marginal USD,
metered generations contribute nominal USD, and missing or ambiguous billing
metadata leaves the session marginal value null. The count-only cohort `costs`
aggregate retains nominal USD, sums known marginal USD, counts billing classes
and unknown sessions, and marks marginal totals as lower bounds whenever any
session is unknown or cohort discovery/selection is incomplete. It never emits
provider, model, session, or trace identifiers.

`cohortHealth.completeness.lowerBound` is true when trace discovery is
incomplete, the session selection cap is reached, or any selected session hits
the trace, observation, or score cap. Score queries read one sentinel row beyond
the retained cap, retain only the configured rows, and add `score-limit` on
truncation. The aggregate reports eligible sessions available
within discovered traces plus every active cap: scan sessions, discovery traces,
discovery page size, traces per session, observations per trace, and score rows
per query. Aggregate provider/model rows are restricted to the tracked
`enabledModels` allowlist after bounded identifier and credential-prefix checks;
unconfigured, malformed, URL/path/hash/secret-shaped, and raw-ID labels count
only as unknown and never enter the safe summary. Existing private per-session
model evidence remains unchanged.
Safe `cohortHealth` also exposes count-only monitoring coverage without copying
raw provenance or termination values. `lifecycleCoverage` separates known
objective execution from missing outcomes. Each `usageCoverage` dimension counts
available, missing, and present-zero sessions independently; a session without a
generation is missing, not zero. `provenanceCoverage` counts release and source
revision availability without emitting either value. `payloadByteCoverage` keeps
available, unavailable, inferred-unavailable, and not-observed states separate
and counts zero only when byte metadata is available. `limitTerminations` counts
allowlisted limit reasons and whether source, limit, observed value, and usage
state form complete evidence. These aggregates use already-fetched traces and
observations and add no telemetry calls.

Scans skip sessions already reviewed under the current policy. Private schema-3
packets attach one shared, private, cohort-retained `EvidenceRef` to each session;
policy-v4 assignment-bound results use the shared Finding core plus improvement-owned
`errorRelevance`, `attribution`, `confidence`, `evidenceStage`,
`interventionType`, and sanitized `public` fields. Historical policy-v1/v2/v3
findings and schema-1/2/3 packets remain readable: validation normalizes older
private JSON pointers to packet EvidenceRefs and leaves unavailable
`evidenceStage` as `unknown` rather than guessing.

Promoting a finding stores a private cohort fingerprint derived from available
task, risk, role, model, and prompt dimensions. Existing promotion-state schemas
remain readable. Later scan packets list monitored finding IDs only in the private
packet and expose count-only monitoring status in safe stdout. A finding enters
monitoring only after its linked Bead closes. Five
distinct reviewed sessions from the exact stored post-change cohort mark it
`validated`; fewer remain monitoring. A reviewer marks explicit recurrence by
giving the new private finding a `relatedFindingId` from the packet's matched
monitoring list. `review --apply` checks the implementation boundary and cohort,
writes idempotent private Langfuse markers, and updates private monitoring state.
It never updates public work. Recurrent follow-up uses the new finding's normal
receipt-bound quality assessment and exact capability grant.

Legacy promotion preview remains a non-mutating import adapter. Public creation
accepts only allowlisted, generalized work content and runs through `quality
apply` with exact `create-bead` + `update_beads` authority. Private trace IDs,
URLs, user content, excerpts, and absolute paths never enter the Bead.

### 6. Settled-cohort and upstream monitor

Run this bounded method only when `work-learning` assessment selects it from a durable signal or caller-supplied backstop. Closeout alone never selects aggregate review. Keep each assigned pass within its declared evidence budget; current operator bounds are 20 selected root sessions and 500 discovered traces:

```bash
agnt improve scan --since <last-check-ISO> --until <now-ISO> \
  --limit 20 --max-traces 500 --dry-run --json
agnt improve scan --since <last-check-ISO> --until <now-ISO> \
  --limit 20 --max-traces 500 --json
```

Inspect safe `cohortHealth` first: lifecycle coverage, child linkage, error
classification, per-dimension usage availability/missing/zero counts, provenance
coverage, payload-byte state, limit-termination evidence, capture gaps, and
`completeness.lowerBound`. Absence is not success when discovery is incomplete,
a value is missing, or sample count is zero. Keep packet-level evidence under
`~/.pi/improvement/`; never paste private IDs, values, paths, prompts, outputs, or
telemetry URLs into Git or Beads.

Before recording a sanitized recurrent defect, search title, description, and
notes across open and closed Beads, then inspect the union:

```bash
bd search "<public-safe signature>" --status all
bd search --desc-contains "<public-safe signature>" --status all
bd search --notes-contains "<public-safe signature>" --status all
```

Link recurrence to matching work instead of creating a duplicate; create new work
only when all three searches and inspection show no existing owner. Scans and
reviews never change policy or code automatically; receipt-bound public work still
requires an exact active capability grant.

Check upstream adoption separately from telemetry using primary package/PR state:

```bash
npm view pi-langfuse version --json
npm view pi-archimedes version --json
for repo in gooyoung/pi-langfuse stvhay/pi-langfuse \
  danielcherubini/pi-archimedes stvhay/pi-archimedes; do
  gh pr list --repo "$repo" --state all --limit 100 \
    --json number,title,state,isDraft,mergedAt,mergeCommit,headRefOid
done
```

Compare published versions with exact pins in `pi/agent/settings.json` and source
commits in `.pi/upstream-profiles/`. Personal-fork PR state is staging evidence
only and never counts as upstream adoption. For each projection, match its tracked
candidate head/feature to an actual upstream PR and merge commit; no match means
not adopted. Merge alone does not retire a local projection. When an upstream fix
is merged, released, and the pinned package can supply equivalent behavior, open
or link a projection-removal review Bead. That review owns patch, wrapper,
documentation, and regression-test removal after verified package gates; the
monitor never edits or removes them itself. Record only sanitized package,
version, PR, and commit facts.

### 7. Quality activities from durable signals

Assess one control-plan activity, then apply its current receipt:

```bash
agnt quality assess --activity work-learning --collect --json
agnt quality assess --activity architecture-coherence --collect --json
agnt quality apply --receipt <receipt-id> --json
```

Collection derives bounded signals from durable project state: closed implementation
Beads, commits since the latest relevant quality checkpoint, failed/blocked run
artifacts, repeated human blockers, context-health warnings, rail-guard health
warnings/failures, and eligible sessions not reviewed under current improvement
policy. An external operator or scheduler may instead provide a bounded snapshot as
the backstop input; it owns invocation, not policy or receiver selection. Telemetry
failure leaves eligible-session state unknown. Incomplete bounded
discovery records a lower-bound gap even below threshold. Neither state becomes
success or silently due. Open work with current or historical labels suppresses a
duplicate activity packet.

New packets emit one activity label only: `quality:capture`,
`quality:work-learning`, `quality:architecture-coherence`,
`quality:capability-calibration`, or `quality:quality-system-review`. Historical
`maintenance:design-review`, `maintenance:architecture-review`,
`maintenance:simplification`, `maintenance:workflow-retro`,
`maintenance:context-health`, `maintenance:improvement-review`, and
`maintenance:lessons-harvest` labels remain read-compatible for checkpoint and
open-duplicate detection; no new work emits them.

Current tracked policy remains observe-only: it writes at most one private assignment with empty allowed effects. Separately reviewed `canary` and `autonomous` policies may dispatch one bounded packet through existing adapters after exact Beads grant, target, fresh authorization evidence, required execution evidence, proof, and budget checks. Autonomous `create-bead` + `update_beads` packets carry validated public work, derive a deterministic Bead target and execution-evidence ref, then create or deduplicate that exact Bead through the Beads adapter. Other effects still require an injected existing dispatcher. The kernel never edits workspace files or creates a competing authority store.

External callers receive `resultClass` (`no-op`, `review`, `human`, `applied`, or `blocked`) plus explicit gaps from assess/apply JSON. Signal triggers come from durable collection; periodic backstop snapshots come from the caller. Caller owns cadence and retry policy. Repository contains no scheduler, sleep, poll, loop, daemon, or service.

Canary effects use `claims.jsonl` as one durable claim/dispatch/settle state machine. Claim and terminal append hold short private locks; adapter dispatch and one-time execution-evidence resolution run outside them with an explicit `claimId` token carrying the exact required proof labels. Dispatcher signatures must expose a second positional or keyword-only claim-token parameter; tokenless or uninspectable adapters fail before claim. Existing work/run adapters accept that token as `claimContext`, preserve it under invocation `provenance` and result artifacts, and resolve the exact active durable claim before execution. They then map quality action `edit` to run action `implement` (`implement`, `review`, `verify`, `plan`, `research`, and `finish` otherwise map identically), map quality effect `workspace.write` to run effect `edit_files` (current run effect IDs otherwise map identically), and require exact effect-set equality. Target binding requires `targetFingerprint` to equal SHA-256 of compact sorted-key JSON containing schema version 1, work item/Bead, worktree snapshot, and ordered invocation input refs. Selected model and thinking must equal the grant, actual worker tools must stay within its toolset, and local revocation must be checked in the same claim store. Unknown mappings, duplicates, extra effects, or action/effect/target/model/thinking/toolset/revocation mismatch block before worker execution; ownership is never inferred from process-global state. Terminal states are `dispatched`, `failed`, `uncertain`, and `revoked`; a hard process kill may leave `claimed`, which is unresolved. There is no stale-claim retry or reaper: `claimed`, `uncertain`, and `revoked` claims fail closed, and a receipt is attempted at most once. Noncritical `failed` claims consume a grant-scoped error budget keyed by exact decision Bead plus grant fingerprint; later receipts can proceed only while that budget and rollout allowance remain. Exactly-once external effects require the adapter to use `claimId` as an idempotency key or equivalent transaction boundary.

### 8. Decision-linked quality metrics

`control-plan.json` carries one approved ceiling of 12 core metrics. Each definition
records owner, type, numerator, denominator, missingness, decision, cadence, gaming
risk, and retirement condition. `derive_core_metrics()` reads existing receipts,
results, annotations, and monitoring rows; it does not create a second metrics
store. Reports retain numerator, denominator, value, and explicit `known`,
`unknown`, or `lower-bound` state. Only known observations with complete
requirements are decision-eligible.

The two guard metrics, `privacy-violation-count` and
`unauthorized-mutation-count`, are zero-tolerance. Missing guard coverage is
unknown, not zero. Unknown, incomplete, and lower-bound evidence cannot support a
success claim, and metric values never authorize mutation or close Beads. Review
annotations and invocation summaries may expose the derived report, while source
artifacts remain owned by their existing private stores.

### 9. Prompt feedback (deliberate, eval-gated)

When a model family shows a repeatable behavioral failure:

1. Write or edit the family overlay `pi/agent/AGENTS.d/models/<family>.md`
   (family ids come from `catalog.json`). Venue-specific files under
   `AGENTS.d/models/<provider>/...` are only for venue-specific quirks.
2. Add a `contains` assertion for the overlay to
   `pi/agent/evals/role-context-smoke/eval.json` (or a new instructions
   eval) so composition is regression-tested.
3. Re-run deterministic gates. When this observed prompt failure needs direct
   behavior evidence beyond routine telemetry, also run the narrow manual canary:

   ```bash
   pi/agent/bin/agnt eval run role-context-smoke
   .venv/bin/python -m pytest tests/
   # manual behavioral canary; costs model calls:
   ./scripts/eval-workflow-compliance.sh --skill-mode candidate --case <case>
   # optional post-deployment comparison against live skills:
   ./scripts/eval-workflow-compliance.sh --skill-mode deployed --case <case>
   ```

4. Commit overlay + eval together, citing the observed failure.
5. Deploy with `scripts/update-pi-config.sh`.

No model overlay is currently configured. Add one only when recurring,
family-specific evidence survives review and gains matching eval coverage.

## Rules

- Never tracked: metric records, private improvement packets, raw session data, and observational-memory ledgers. Never deployed over: `~/.pi/metrics/` and `~/.pi/improvement/` are rsync-excluded by the update script.
- Overlays specialize behavior; they must not weaken approval, verification,
  git, or security gates (`agent-instructions --check` scans for this).
- Edit prompts in this repo and deploy; do not hand-edit deployed `~/.pi`
  copies — the next update overwrites them.
