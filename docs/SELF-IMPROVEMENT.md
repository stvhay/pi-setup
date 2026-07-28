# Self-Improvement Loop

How this setup learns from model usage while keeping private evidence out of
tracked policy and Beads. It improves routing, prompts, tools, and monitoring.
For broader workflow/context design principles, see
[Self-Improvement Principles](SELF-IMPROVEMENT-PRINCIPLES.md).

Principle: telemetry is runtime state; policy is config. Metrics live in
`~/.pi/metrics/` and per-project `.pi/metrics/` and are never tracked. What
git tracks — and what makes the learning auditable — are the policy files the
metrics justify changing:

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
cost, latency) to `<git-root>/.pi/metrics/invocations/`. Interactive Archimedes
unnamed `subagent` results are converted to the same schema by the tracked
observer. The observer stores usage, timing, and payload lengths—not prompt or
response bodies. Named-profile results are skipped because Archimedes does not
expose their final provider.

The Langfuse extension records private interactive telemetry. Evaluator-ready
result projections share the Pi session ID, allowing sampled outcome scores to
join the root agent trace without heuristic matching. `agnt improve` reads
bounded cohorts and writes private packets under `~/.pi/improvement/`.
Runner sessions correlate from run bundles; interactive work must call
`agnt improve link <bead>` after claim. Private evidence stays outside git and
committed Beads.

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
For review, risk-specific fanout and month-to-date marginal-spend gates apply
before model output exists: Kimi is removed at the reserve threshold and paid
review stops at the hard cap. These deterministic gates do not use model
self-confidence.
The demotion is visible in the `reasons` field. Persistent patterns deserve a
policy edit: move the model in the relevant `tasks/*.md` frontmatter and
commit with the evidence summarized in the message
(`agnt metrics status` gives the aggregate).

### 5. Private review and safe promotion

```bash
agnt improve link <bead>                                  # current private session
agnt improve scan --since <ISO> --limit 5 --dry-run --json
agnt improve scan --since <ISO> --limit 5 --json
agnt improve review <report> <decisions>          # preview
agnt improve review <report> <decisions> --apply  # private session markers
agnt improve promote <report> <decisions> --finding <id>          # preview
agnt improve promote <report> <decisions> --finding <id> --apply  # approved Bead
```

`link` writes an idempotent private session score containing only the public
work-item ID. `scan` uses bounded reads, exact links, payload-free tool-error
signals, and skips sessions already reviewed under the current policy.
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
   # behavioral, costs model calls — for the affected workflow only:
   ./scripts/eval-workflow-compliance.sh --case <case>
   ```

4. Commit overlay + eval together, citing the observed failure.
5. Deploy with `scripts/update-pi-config.sh`.

Existing examples: `AGENTS.d/models/gpt-4.1-mini.md` (plans-dir discipline,
from eval failures) and `AGENTS.d/models/gemma4-31b.md` (reviewer evidence
discipline, from review smoke tests).

## Rules

- Never tracked: metric records, private improvement packets, raw session data, and observational-memory ledgers. Never deployed over: `~/.pi/metrics/` and `~/.pi/improvement/` are rsync-excluded by the update script.
- Overlays specialize behavior; they must not weaken approval, verification,
  git, or security gates (`agent-instructions --check` scans for this).
- Edit prompts in this repo and deploy; do not hand-edit deployed `~/.pi`
  copies — the next update overwrites them.
