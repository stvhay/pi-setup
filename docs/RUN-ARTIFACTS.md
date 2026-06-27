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
completedAt: null
```

Allowed statuses:

- `succeeded`
- `failed`
- `blocked`
- `needs-human`
- `superseded`

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
  --metrics-ref .pi/metrics/example.metrics.json

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
  --model olla-cloud/gpt-4.1-mini \
  --claim \
  --close-bead
```

`agnt work run` creates a run bundle, invokes a worker from `invocation.yaml`,
writes output/metrics artifacts, updates `result.yaml`, and closes the bead only
when `--close-bead` is supplied, the invocation succeeds, result evidence is
present, and any `followUps` resolve to Beads.

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
`succeeded` results that include evidence and have reconciled follow-up bead ids.
`agnt work run` combines start + invoke + optional close while preserving those
gates.

Audit queue health before trusting an empty queue as complete:

```bash
agnt work audit --json
```

The audit reports Beads open/ready/deferred counts and scans docs/run artifacts
for required future-work signals. It fails when Beads has no open/deferred work
while those signals remain, which prevents “0 ready” from being mistaken for
production readiness.

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

- Beads hold work state and dependencies.
- `.pi/plans/` holds larger design/implementation plans.
- `.pi/runs/` holds per-run invocation/result evidence.
- Beads should reference relevant plan/run paths in notes, metadata, or issue
  descriptions when downstream work depends on them.
