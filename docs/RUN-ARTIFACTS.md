# Invocation and Result Artifacts

Pi agent work may use durable run artifacts for delegated or scheduled work.
They are optional in the default direct Pi workflow, where a Bead is required
before code edits but a run bundle is not. When selected, these files are the
inspectable handoff between a work item, a worker, verification, and downstream
work.

Runtime run bundles use directory returned by `agnt runtime-path runs`. Resolver
uses project `.pi/runs/` only when Git proves path is ignored, contains no
tracked files, and crosses no symlink. Otherwise it uses
`~/.pi/runtime/<sha256>/runs/`, keyed by canonical Git common directory (or
canonical working directory outside Git). Selected runtime directories use mode
`0700`; JSON output contains only schema version and resolved path.

This supports linked worktrees where `.git` is file, avoids dirtying projects
with different ignore policy, and keeps ordinary run records private runtime
state. Examples below use `<runtime-runs-dir>` and `<runtime-metrics-dir>` for
resolver-selected paths.

## Bundle shape

```text
<runtime-runs-dir>/<run-id>/
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
- `ephemeralTodoSeed`: optional live-UX todo seed. Archimedes todos are transient; durable outcomes belong in Beads and private run bundles.
- `worktree`: dispatch worktree snapshot. Implementation work uses one worktree per epic: `.worktrees/epic/<epic-id>-<slug>` on branch `epic/<epic-id>-<slug>`.
- `dispatchPolicy`: action, routing task, role, allowed effects, risk, budget, model policy, session policy, memory policy, and closeout policy.
- `sessionPolicy`: `recorded` by default for worker sessions, or `no-session` when explicitly allowed.
- `memoryPolicy`: `auto` by default. Observational memory is advisory recall/context; promote important findings into Beads or private run bundles before closeout.
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
agnt runs invoke <runtime-runs-dir>/<run-id> --model olla-cloud/gpt-4.1-mini
```

`agnt runs invoke` reads `invocation.yaml`, renders a worker prompt, writes
`artifacts/prompt.md`, `artifacts/<model>.response.md`,
`artifacts/<model>.stderr.txt`, optional metrics artifacts, and updates
`result.yaml` with status, evidence, artifact refs, and `metricsRef`.

Update and validate a run bundle manually:

```bash
agnt runs update <runtime-runs-dir>/<run-id> \
  --status succeeded \
  --summary "Verified with tests" \
  --evidence "pytest tests/ → PASS" \
  --artifact artifacts/report.md \
  --follow-up pi-next.1 \
  --metrics-ref <runtime-metrics-dir>/example.metrics.json \
  --session-ref pi-session-id:run-123 \
  --approval-ref pi-decision.1 \
  --decision-ref pi-decision.1 \
  --health-check pytest=passed \
  --closeout-check followups=passed

agnt runs validate <runtime-runs-dir>/<run-id>
agnt runs validate <runtime-runs-dir>/<run-id> --require-followups-exist
```

Use `--require-followups-exist` before treating follow-up refs as reconciled;
it fails when any `result.yaml.followUps[]` id is not present in Beads.

Optionally run bead-backed work through the gated work surface:

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
agnt work finish <runtime-runs-dir>/<run-id> \
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

For optional service lifecycle, scheduling, status, and runtime-state details,
see [Project-Local Runner Service](RUNNER-SERVICE.md). Run `agnt work audit
--json` and `agnt work health --json` before trusting orchestrated closeout.

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
- Resolved private runs directory holds per-run invocation/result evidence and recorded session refs.
- Observational-memory ledgers are session-local recall aids; promote important findings into Beads or private run bundles before relying on them.
- Beads should reference relevant plan/run paths in notes, metadata, or issue
  descriptions when downstream work depends on them.
