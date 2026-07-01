# Self-Improvement Loop

How this setup learns from its own model usage, for both **routing** (which
model gets which task) and **prompts** (per-model instruction overlays). For
broader workflow/context design principles, see
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
capture -> annotate -> consolidate -> route hints/demotion
                                   -> overlay or task-policy edit -> eval -> commit
```

### 1. Capture (automatic metrics, deliberate lessons)

Every `agnt invoke` writes a metric record (model, family, task, tokens,
cost, latency) to `<git-root>/.pi/metrics/invocations/`. Always invoke peers
through `agnt invoke`; anything else leaves holes in the data.

Reusable workflow lessons are captured deliberately with `agnt lessons`:

```bash
agnt lessons capture \
  --kind friction \
  --area doctor \
  --summary "Provider failure caused repeated tool retries" \
  --evidence "provider env var was missing; agnt doctor would have caught it"
```

Lessons are JSONL runtime state, not tracked policy. The default local inbox is
`~/.pi/lessons/inbox.jsonl` (`AGNT_LESSONS_INBOX` overrides). Records include a
UUID, UTC date, hostname, project name, and project directory. Evidence is
best-effort redacted before it is written.

### 2. Annotate (the human/orchestrator signal)

Label outcomes as a side effect of normal work — the review and verification
skills include this step:

```bash
~/.pi/agent/bin/agnt metrics annotate latest --outcome accepted
~/.pi/agent/bin/agnt metrics annotate <recordId> --outcome rejected --notes "hallucinated findings"
```

Outcomes: `accepted`, `rejected`, `verified-pass`, `verified-fail`,
`escalated`. Unlabeled records stay `unknown` and carry no routing signal.

### 3. Consolidate (durable, cross-project)

```bash
~/.pi/agent/bin/agnt metrics consolidate
```

Appends compact records to the global store
`~/.pi/metrics/agent-invocations.jsonl` (override: `AGNT_METRICS_OUTPUT`). Run
this manually or from a locally installed hook when you want pending metrics to
contribute to cross-project routing history.

For lessons, push/pull through the lesson server:

```bash
export AGNT_LESSONS_URL=https://pi-lessons.st5ve.com
agnt lessons push
agnt lessons pull --status new -o /tmp/lessons.jsonl
```

The server exposes `POST /lesson` and `GET /lessons` and stores JSONL lessons.
It is an aggregation point only; accepted lessons become auditable when they are
triaged into Beads and implemented as tracked config/docs/tooling changes.

### 4. Routing feedback (automatic)

`agnt route` aggregates outcome history **by model family** (so evidence from
one venue covers all venues of the same weights) and demotes any candidate
whose family shows more negative than positive outcomes over ≥5 invocations.
The demotion is visible in the `reasons` field. Persistent patterns deserve a
policy edit: move the model in the relevant `tasks/*.md` frontmatter and
commit with the evidence summarized in the message
(`agnt metrics status` gives the aggregate).

### 5. Lesson triage into Beads

In this repository, turn useful lessons into Beads work instead of letting them
remain chat-only observations:

```bash
agnt lessons pull --status new -o /tmp/lessons.jsonl
agnt lessons triage --file /tmp/lessons.jsonl --draft-beads
# after reviewing the drafts:
agnt lessons triage --file /tmp/lessons.jsonl --create-beads
```

`--create-beads` is an explicit state mutation. It should only be used when the
lesson is specific enough to become work with context, problem, suggested
improvement, and evidence.

### 6. Prompt feedback (deliberate, eval-gated)

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
5. Deploy with `scripts/bootstrap-pi-config.sh --apply`.

Existing examples: `AGENTS.d/models/gpt-4.1-mini.md` (plans-dir discipline,
from eval failures) and `AGENTS.d/models/gemma4-31b.md` (reviewer evidence
discipline, from review smoke tests).

## Rules

- Never tracked: metric records, the global store, session data. Never
  deployed over: `~/.pi/metrics/` is rsync-excluded by the bootstrap script.
- Overlays specialize behavior; they must not weaken approval, verification,
  git, or security gates (`agent-instructions --check` scans for this).
- Edit prompts in this repo and deploy; do not hand-edit deployed `~/.pi`
  copies — the next `--apply` overwrites them.
