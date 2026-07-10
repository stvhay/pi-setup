# Invocation and Result Artifacts

Pi agent work uses durable run artifacts for nontrivial delegated or scheduled
work. Chat remains a UI; these files are the inspectable handoff between a work
item, a worker, verification, and downstream work.

Runtime run bundles live under `.pi/runs/<run-id>/` and are gitignored by
default. Curated examples may be documented elsewhere, but ordinary run records
are local runtime state.

## Bundle shape

```text
.pi/runs/<run-id>/
├── invocation.yaml
├── result.yaml
└── artifacts/
```

`agnt runs create` and `agnt action render` write JSON content to the `.yaml`
files. JSON is a YAML subset, keeps the helper dependency-free, and preserves
stable filenames for future richer YAML support.

## `invocation.yaml` v1

```yaml
schemaVersion: 1
id: 20260627-010203-pi-8su-3
bead: pi-8su.3
action: review
routingTask: review
inputRefs:
  - docs/RUN-ARTIFACTS.md
skills:
  - documentation-standards
role: documentation-reviewer
model: null
selectedModel: null
thinkingLevel: null
modelSelection: null
ticketMetadata: null
ephemeralTodoSeed: []
worktree: null
dispatchPolicy: null
sessionPolicy: recorded
memoryPolicy: auto
allowedEffects:
  - read_workspace
  - write_artifacts
acceptanceCriteria: []
outputContract: findings-with-evidence
createdAt: 2026-06-27T01:02:03Z
```

Fields:

- `bead`: optional work-graph node that initiated the run.
- `action`: verb-like prompt/action template id.
- `routingTask`: model/tool routing category.
- `inputRefs`: file paths, bead ids, URLs, or other inspectable inputs.
- `skills`: reusable capability packages the worker should use.
- `role`: delegated-worker output contract.
- `selectedModel`, `thinkingLevel`, and `modelSelection`: policy-selected model, thinking level, score, and reasons. `agnt work run` rejects direct model overrides.
- `ticketMetadata`: snapshot of source bead identity and metadata validation.
- `ephemeralTodoSeed`: optional live-UX todo seed. Archimedes todos are transient; durable outcomes belong in Beads and `.pi/runs`.
- `worktree`: dispatch worktree snapshot. Implementation work uses one worktree per epic: `.worktrees/epic/<epic-id>-<slug>` on branch `epic/<epic-id>-<slug>`.
- `dispatchPolicy`: action, routing task, role, allowed effects, risk, budget, model policy, session policy, memory policy, and closeout policy.
- `sessionPolicy`: `recorded` by default for worker sessions, or `no-session` when explicitly allowed.
- `memoryPolicy`: `auto` by default. Observational memory is advisory recall/context; promote important findings into Beads or `.pi/runs` before closeout.
- `allowedEffects`: declared side-effect budget for the run.
- `outputContract`: concise result shape name or path.
- `acceptanceCriteria`: criteria copied from the source bead when the bundle is
  created through `agnt work`; workers should address them in their result
  evidence.

## `result.yaml` v1

```yaml
schemaVersion: 1
invocationId: 20260627-010203-pi-8su-3
status: needs-human
summary: Invocation artifact created; worker has not run yet.
evidence: []
artifacts:
  - artifacts
followUps: []
metricsRef: null
sessionRef: null
transcriptRef: null
memorySummaryRef: null
approvalRefs: []
decisionRefs: []
healthChecks: []
closeoutChecks: []
completedAt: null
```

Allowed statuses:

- `succeeded`
- `failed`
- `blocked`
- `needs-human`
- `superseded`

Closeout-related fields:

- `sessionRef` / `transcriptRef`: recorded Pi worker session references.
- `memorySummaryRef`: optional promoted observational-memory summary reference.
- `approvalRefs` / `decisionRefs`: Beads decisions that must be resolved before closeout.
- `healthChecks` / `closeoutChecks`: named checks with passing statuses before bead closure.
- `followUps`: Beads ids for downstream work. Follow-up text in chat or memory is not reconciled until it becomes a Beads item.

## Commands

Create a generic run bundle:

```bash
agnt runs create \
  --action review \
  --routing-task review \
  --input-ref docs/RUN-ARTIFACTS.md \
  --skill documentation-standards \
  --role documentation-reviewer \
  --bead pi-8su.3
```

Render a prompt/action template into a run bundle:

```bash
agnt action render review \
  --target docs/RUN-ARTIFACTS.md \
  --bead pi-8su.3
```

Invoke a worker from a run bundle and update `result.yaml` automatically:

```bash
agnt runs invoke .pi/runs/<run-id> --model olla-cloud/gpt-4.1-mini
```

`agnt runs invoke` reads `invocation.yaml`, renders a worker prompt, writes
`artifacts/prompt.md`, `artifacts/<model>.response.md`,
`artifacts/<model>.stderr.txt`, optional metrics artifacts, and updates
`result.yaml` with status, evidence, artifact refs, and `metricsRef`.

Update and validate a run bundle manually:

```bash
agnt runs update .pi/runs/<run-id> \
  --status succeeded \
  --summary "Verified with tests" \
  --evidence "pytest tests/ → PASS" \
  --artifact artifacts/report.md \
  --follow-up pi-next.1 \
  --metrics-ref .pi/metrics/example.metrics.json \
  --session-ref pi-session-id:run-123 \
  --approval-ref pi-decision.1 \
  --decision-ref pi-decision.1 \
  --health-check pytest=passed \
  --closeout-check followups=passed

agnt runs validate .pi/runs/<run-id>
agnt runs validate .pi/runs/<run-id> --require-followups-exist
```

Use `--require-followups-exist` before treating follow-up refs as reconciled;
it fails when any `result.yaml.followUps[]` id is not present in Beads.

Run bead-backed work through the gated work surface:

```bash
agnt work run pi-e4t.1 \
  --action verify \
  --target docs/RUN-ARTIFACTS.md \
  --claim \
  --close-bead
```

`agnt work run` creates a run bundle, invokes a worker from `invocation.yaml`,
writes output/metrics artifacts, updates `result.yaml`, and closes the bead only
when `--close-bead` is supplied, the invocation succeeds, result evidence is present, health/closeout checks pass, approval/decision refs are resolved, and any `followUps` resolve to Beads.

Start and finish bead-backed work manually through the gated work surface:

```bash
agnt work start pi-e4t.1 --action verify --target docs/RUN-ARTIFACTS.md --claim
agnt work finish .pi/runs/<run-id> \
  --status succeeded \
  --summary "Verified and complete" \
  --evidence "scripts/check-pi-config.sh → PASS" \
  --close-bead
```

`agnt work plan` remains dry-run only. `agnt work start` writes run artifacts;
`--claim` is required to mutate the bead. `agnt work finish` updates
`result.yaml`; `--close-bead` is required to close the bead and only works for
`succeeded` results that include evidence, have reconciled follow-up bead ids,
resolved approval/decision refs, and passing health/closeout checks. `agnt work
run` combines start + invoke + optional close while preserving those gates.

Run the same dispatch path through the project-local service:

```bash
agnt work daemon start --json --concurrency 1
agnt work runner status --json
agnt work runner tick --dry-run --json --limit 1
agnt work daemon stop --json --drain
```

`agnt work daemon start|stop|status` owns the service lifecycle.
`agnt work runner status|pause|resume|tick` calls the service REST API. The
service writes transient coordination state under `.pi/runner/`; run evidence
still belongs in `.pi/runs/<run-id>/`.

Audit queue and rail-guard health before trusting closeout:

```bash
agnt work audit --json
agnt work health --json
```

The audit reports Beads open/ready/deferred counts and scans docs/run artifacts
for required future-work signals. It fails when Beads has no open/deferred work
while those signals remain, which prevents “0 ready” from being mistaken for
production readiness.

The health report checks run artifacts, Beads refs, approvals, decisions,
follow-ups, stale sessions, stale runner locks and heartbeats, active run
snapshots, dirty current/epic worktrees, raw-tool bypass markers, orphaned runs,
and failed health/closeout checks. Legacy completed v1 artifacts may warn on
historical missing refs; current format closeout blockers fail.

## Side-effect convention

Common effects:

- `read_workspace`
- `write_artifacts`
- `edit_files`
- `update_beads`
- `external_write`

Read-only delegated roles may write run artifacts, but should not use effects
such as `edit_files`, `external_write`, `push`, `deploy`, or `delete_files`.
Those effects require explicit approval and stronger verification gates.

## Relationship to beads and plans

- Beads hold work state, dependencies, approvals, blockers, maintenance checkpoints, and closeout.
- `.pi/plans/` holds larger design/implementation plans.
- `.pi/runs/` holds per-run invocation/result evidence and recorded session refs.
- Observational-memory ledgers are session-local recall aids; promote important findings into Beads or `.pi/runs` before relying on them.
- Beads should reference relevant plan/run paths in notes, metadata, or issue
  descriptions when downstream work depends on them.
