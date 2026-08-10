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
- `pi/agent/evals/` and `scripts/eval-workflow-compliance.sh` — the gates

## The loop

```text
metrics -> annotate -> consolidate -> route hints/demotion
                              -> policy edit -> eval -> commit
Langfuse sessions -> private scan -> human review -> private marker
                  -> sanitized Bead -> implementation -> matched monitoring
Beads/git/runs/health signals -> maintenance due -> checkpoint bead -> closeout
```

### 1. Capture

Every `agnt invoke` writes a metric record (model, family, task, tokens,
cost, latency) to the resolved private `metrics/invocations` directory.
The tracked observer converts interactive Archimedes unnamed `subagent` results
to the same schema. Projection, parent-owned artifact, and metric records share
invocation, provider, model, target, effective thinking, and optional output
contract dimensions; missing/legacy contracts are `unknown`. Config-less workers
record thinking `default` because Archimedes passes no thinking override. Metrics
store usage, timing, payload lengths, bounded artifact refs, and contract—not
prompt or response bodies. Named-profile projections mark unavailable dimensions
explicitly, while metrics remain skipped because Archimedes does not expose their
effective provider or thinking level.

`subagent-result` quality evaluation receives a bounded view of parent-held
output plus objective outcome, declared contract, artifact persistence/content
status, and ref count. Parent metadata also carries validated `effectiveMode` and
a declared child-trace expectation derived from Archimedes's resolved execution
evidence. Agentic children with a usable foreign key are expected available;
isolated one-shot children are expected unavailable. It does not receive raw refs
or filesystem paths. Requested status-only and PASS/no-findings responses are
judged against that contract; missing required inline/artifact output remains
visible as poor quality independently of objective execution outcome.

The Langfuse extension records private interactive telemetry. Evaluator-ready
result projections share the Pi session ID, allowing sampled outcome scores to
join the root agent trace without heuristic matching. `agnt improve` reads
bounded cohorts and writes private packets under `~/.pi/improvement/`.
Runner sessions correlate from run bundles; interactive work must call
`agnt improve link <bead>` after claim and `agnt improve outcome <bead> <outcome>`
at closeout. One logical Pi session belongs to one Bead. After current Bead
closeout, agents call `handoff_bead` with the next ready Bead ID. The tool validates
source closeout and target readiness, then starts a parent-linked session without
copying the transcript. `/new` remains the human fallback when automated handoff
is unavailable. Quitting and resuming may retain the same session. Link and outcome
commands fail closed rather than overwrite conflicting canonical ownership. The
outcome command idempotently backfills the same-Bead
link and records an explicit final outcome, which overrides sampled evaluator
guesses only when its Bead metadata matches correlation. Private evidence stays
outside git and committed Beads.

### 2. Annotate (the human/orchestrator signal)

Label outcomes as a side effect of normal work — the review and verification
skills include this step:

```bash
~/.pi/agent/bin/agnt metrics annotate latest --outcome accepted
~/.pi/agent/bin/agnt metrics annotate <recordId> --outcome rejected --notes "hallucinated findings"
```

Outcomes: `accepted`, `rejected`, `verified-pass`, `verified-fail`,
`escalated`. Unlabeled records stay `unknown` and carry no routing signal.

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
agnt improve link <bead>                                  # claim-time correlation
agnt improve outcome <bead> <success|partial|failure|unclear> # closeout correlation + outcome
agnt improve scan --since <ISO> --limit 5 --max-traces 500 --dry-run --json
agnt improve scan --since <ISO> --limit 5 --max-traces 500 --json
agnt improve review <report> <decisions>          # preview
agnt improve review <report> <decisions> --apply  # private session markers
agnt improve promote <report> <decisions> --finding <id>          # preview
agnt improve promote <report> <decisions> --finding <id> --apply  # approved Bead
```

`link` writes an idempotent private session score containing only the public
work-item ID after bounded reads prove existing canonical link/outcome ownership
is absent or belongs to the same Bead. `outcome` refreshes that same-Bead link and
adds one idempotent categorical session score. Conflicts expose only
`handoff_bead` recovery plus the `/new` human fallback, not prior owner or session
IDs. Scans keep objective
`executionOutcome`, sampled `apparentOutcome`, and explicit human outcome distinct.
An explicit human outcome is authoritative only when its Bead metadata matches the
session correlation; historical mismatches are ignored as outcomes and counted as
`mismatched-work-item-outcome` capture gaps. Otherwise deterministic failure maps
final outcome to `failure` and unavailable execution maps it to `unclear` before
sampled apparent judgment is considered.
Useful partial output remains visible as apparent quality, but cannot turn failed
execution into successful final outcome. `scan` traverses pages
in its bounded time window up to the operator trace cap (default 500) and reports that
cap, valid API total when available, scanned/attributable/unattributed lower bounds,
and explicit completeness/continuation state. Repeated pages stop as incomplete.
Selected sessions retain 20-trace and 500-observation-per-trace caps with
capture-gap markers. Private scan packets use schema 2; safe scan summaries and
review decisions remain schema 1, review policy remains `v1`, and historical
schema-1 packets remain reviewable. For the exact
`pi-langfuse-1.5.7-dual-null-dual-26` TOOL fingerprint, scans report both tool
payload-byte aggregates as unavailable (`null`) and record rule status plus
matched/examined observation counts under `payloadByteMetadata.toolIo`. Missing
or invalid nonfingerprint metadata makes only the affected aggregate unavailable;
no TOOL observations still report zero. Gaps distinguish
`inferred-tool-payload-bytes`, `missing-tool-payload-bytes`, and the preserved
`observation-limit`. Non-null payload-byte values are bounded-preview estimates,
not raw payload sizes. Raw Langfuse records remain unchanged, and packets never
copy tool payloads. Scans use exact links and payload-free tool-error signals.
Each private session feature also includes schema-1 `errorTaxonomy`: count-only
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
guessed. The same count-only
health appears per private session; safe cohort summaries never include child
session IDs and scanning adds no per-child Langfuse calls.

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
Scans skip sessions already reviewed under the current policy.
`review --apply` writes idempotent private Langfuse markers. `promote`
accepts only allowlisted, generalized text and requires durable approval of the
exact preview before creating a committed Bead. Private trace IDs, URLs, user
content, excerpts, and absolute paths never enter the Bead.

### 6. Maintenance cadence from durable signals

Use maintenance commands to decide when self-improvement work is due:

```bash
agnt work maintenance due --json
agnt work maintenance create-beads --dry-run --json
# after reviewing the proposed checkpoint beads:
agnt work maintenance create-beads --apply --json
```

The due report derives signals from durable project state: closed implementation
beads since the last maintenance checkpoint, commits since that checkpoint,
failed/blocked run artifacts, repeated human blockers, context-health warnings,
rail-guard health warnings/failures, and recorded session volume. It suppresses
modes that already have open maintenance beads.

Maintenance labels include:

- `maintenance:design-review`
- `maintenance:architecture-review`
- `maintenance:simplification`
- `maintenance:workflow-retro`
- `maintenance:context-health`

Read-only maintenance reviews use `action: maintenance` and may be auto-created
by an idle runner. Simplification/refactor implementation beads use
`action: implement` with `approved: false`; creating the checkpoint does not
authorize edits. Close maintenance checkpoints like normal Beads: record evidence,
represent follow-ups as Beads, and pass closeout checks.

### 7. Prompt feedback (deliberate, eval-gated)

When a model family shows a repeatable behavioral failure:

1. Write or edit the family overlay `pi/agent/AGENTS.d/models/<family>.md`
   (family ids come from `catalog.json`). Venue-specific files under
   `AGENTS.d/models/<provider>/...` are only for venue-specific quirks.
2. Add a `contains` assertion for the overlay to
   `pi/agent/evals/role-context-smoke/eval.json` (or a new instructions
   eval) so composition is regression-tested.
3. Re-run the gates:

   ```bash
   pi/agent/bin/agnt eval run role-context-smoke
   .venv/bin/python -m pytest tests/
   # behavioral, costs model calls — tracked candidate before deployment:
   ./scripts/eval-workflow-compliance.sh --skill-mode candidate --case <case>
   # post-deployment smoke uses live skills explicitly:
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
