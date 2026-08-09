# Langfuse v4 Migration Evaluation

**Issue:** pi-4tg9.16 — Evaluate migration to Langfuse v4 write mode
**Date:** 2026-08-09
**Branch:** `docs/langfuse-v4-migration-evaluation`

**Goal:** Decide whether this deployment can move to Langfuse v4 without losing telemetry, queries, evaluators, exports, or rollback.

**Decision:** **No-go for remote migration now.** Keep self-hosted Langfuse 3.225.1 unchanged. Prepare application and infrastructure follow-ups, then request separate approvals for the v4 server upgrade, dual-write validation, and final `events_only` cutover.

## Acceptance Criteria

- [x] Current server, SDK, ingestion, read, evaluator, and score compatibility are inventoried.
- [x] Representative bounded v2 observations and metrics reads are attempted without mutation.
- [x] Query benefits and response-shape differences are documented from current primary sources.
- [x] Migration stages, infrastructure prerequisites, rollback boundary, and irreversible actions are explicit.
- [x] No remote server, write-mode, evaluator, export, or project setting changes occur.
- [x] Atomic application and infrastructure follow-ups are filed before this evaluation closes.

## Current State

| Area | Evidence | Status |
|---|---|---|
| Server | Authenticated health endpoint reports self-hosted Langfuse 3.225.1. | v3; v4 APIs unavailable |
| Modern reads | A bounded 24-hour probe received HTTP 404 from both `/api/public/v2/observations` and `/api/public/v2/metrics`; the bounded legacy observations positive control returned data. | Blocked on v4 read path |
| Trace ingestion | `pi-langfuse` uses OpenTelemetry through Langfuse JS packages. Live runtime lock resolves `@langfuse/client`, `@langfuse/otel`, and `@langfuse/tracing` 5.9.1 with integrity metadata. | Compatible with v3 and v4 real-time threshold |
| Declared SDK floor | `pi-langfuse` 1.5.10 declares `@langfuse/* ^5.3.0`; current npm 1.5.11 still declares that range. | Does not guarantee documented v4 real-time floor 5.4.0 |
| Trace fallback | `forks/pi-langfuse/src/langfuse.ts` polls deprecated `GET /api/public/traces/{id}` and sends `trace-create`, `span-create`, and `generation-create` events to deprecated `POST /api/public/ingestion` when visibility fails. | Incompatible with v4 `events_only` |
| Improvement reads | `pi/agent/bin/agnt_lib/langfuse.py` reads deprecated traces and observations with offset pagination; scores already use `/api/public/v3/scores`. | Incompatible with v4 `events_only` |
| Evaluators | Read-only drift check passes. Current project has two enabled observation-target rules and no detected legacy target. | Application manifest ready; UI audit still required |
| Exports/integrations | Project-scoped credentials cannot enumerate organization-scoped blob exports; PostHog and Mixpanel require project UI inspection. | Manual audit required |
| Infrastructure | ClickHouse, PostgreSQL, Redis, Helm topology, storage headroom, retention, backup, and worker-health configuration are outside this repository and were not inspected. | Remote operations blocker |

Private probe evidence remains under `~/.pi/improvement/v4-evaluation/` with directory mode 0700 and file mode 0600. It contains no committed payloads or identifiers.

## Compatibility and Benefits

Langfuse v4 replaces trace/observation read-time joins with an observations-first table. For this project:

- Observations API v2 raises the page limit from 100 to 1,000, uses cursor pagination, and lets callers request only required field groups. This can remove the current offset-pagination and whole-row costs.
- V2 returns observation rows rather than trace objects. The improvement scanner must group by `traceId`, identify logical roots with `isRootObservation`, and reconstruct root input/output from the root observation.
- V2 input/output values are raw strings. The scanner must parse only where required and preserve absent-field versus null semantics.
- Metrics API v2 can aggregate cost, token, latency, volume, and score data without downloading rows. It cannot group by high-cardinality session or trace IDs, so it cannot replace session-level joins.
- Scores API v3 and score ingestion are already supported by current code and remain supported on v4.
- Observation-level evaluator rules are the required v4 shape; the tracked rules already use it.

## Migration and Rollback Contract

### Stage 0 — Application readiness

Complete both application follow-ups before any server mutation:

1. Add version-aware Observations API v2 reads with v3 compatibility and parity tests.
2. Make `pi-langfuse` trace visibility/fallback safe on v4 and enforce Langfuse JS 5.4.0 or newer.

### Stage 1 — Infrastructure audit and approval

Operations must verify:

- ClickHouse 25.12 minimum, with 26.4 recommended;
- PostgreSQL 15 minimum and Redis 7.0 minimum;
- deployment is not blocked by the Helm chart's bundled-ClickHouse limitation;
- enough ClickHouse capacity for the selected history strategy, including roughly 3x disk headroom for automated backfill;
- every producer meets its SDK floor;
- exports and integrations use, or can migrate to, enriched observations;
- no active legacy evaluator exists in the UI;
- backups, monitoring, rollback owner, maintenance window, and acceptance thresholds are named.

This stage requires a separate informed approval because it mutates remote infrastructure.

### Stage 2 — Reversible v4 validation

Upgrade the server using `legacy` or `dual`, not default `events_only`. Keep old tables receiving writes. `legacy` supports only a server-upgrade smoke because it writes no v4 events and must keep v4 reads disabled. Full validation requires `dual`; enable the v4 preview only after application readiness and dual-write health, then verify:

- v1 and v2 bounded read parity for representative sessions, roots, observations, usage, costs, and scores;
- direct real-time OTel ingestion from the resolved SDK;
- dual-write propagation health through the worker health endpoint;
- observation evaluator execution;
- export/integration behavior;
- selected historic-data strategy.

Rollback remains lossless while `legacy` or `dual` keeps old tables current. Reverting the server to latest v3 remains available during this phase.

### Stage 3 — Commitment gate

`events_only` is a separate consequential approval. After cutover, new data lands only in v4 tables; reverting to v3 misses post-cutover data. Truncating old trace/observation tables removes the final v3 read-path rollback and is irreversible. Do not combine cutover, old-table truncation, or scratch-table cleanup with the reversible validation approval.

## Future Approval Design

Do not open either approval until `pi-4tg9.43` and `pi-4tg9.44` close and `pi-4tg9.45` supplies the missing infrastructure evidence.

### Approval 1 — Reversible v4 validation

- **Action:** Upgrade the self-hosted server from v3 to an exact reviewed v4 release. Optionally start in `legacy` for server smoke, then use `dual` for v4 read-path validation; keep historic backfill deferred until dual-write health is proven.
- **Scope:** Show exact server image, infrastructure versions, migration variables, backup, maintenance window, health probes, expected write/storage overhead, representative parity checks, and named rollback owner. `legacy` alone cannot satisfy validation closeout. Exclude `events_only`, old-table truncation, export source removal, evaluator deletion, and scratch-table cleanup.
- **Modification options:** Start in `legacy` before `dual`, keep v4 preview disabled until dual is healthy, adjust timing, and defer backfill.
- **Consequence:** V4 adds tables and schema migrations. `dual` increases write load and storage while old tables remain current.
- **Reversibility:** Roll back to latest v3 without data loss while old tables receive all writes.
- **Timeout/default:** No automatic action; absent or expired approval cancels the change.
- **Closeout:** In `dual`, prove health, v1/v2 parity, real-time ingestion, evaluator/export behavior, history strategy, and a rehearsed rollback. If the deployment remains in `legacy`, report only server-smoke completion and keep validation open.

### Approval 2 — `events_only` commitment

- **Action:** Stop writes to legacy tables only after every producer, read consumer, evaluator, export, and historic-data gate passes.
- **Scope:** Show elapsed dual-validation period, complete backfill or retention rollover, no deprecated consumers, and exact rollback consequence. Exclude old-table truncation and scratch-table cleanup; each destructive cleanup requires its own later approval.
- **Modification options:** Defer cutover or extend dual validation; do not partially cut over producers.
- **Consequence:** Deprecated ingestion and read endpoints stop working. A v3 rollback misses all post-cutover data.
- **Reversibility:** Not losslessly reversible after new writes begin; treat as point of commitment.
- **Timeout/default:** No automatic action; absent or expired approval cancels the change.
- **Closeout:** Prove complete v4 ingestion/read/evaluation/export behavior and preserve old tables until a separately approved retention point.

## Planned Follow-ups

### Follow-up A — `pi-4tg9.43` Version-aware v2 improvement reads

**Scope:** `pi/agent/bin/agnt_lib/langfuse.py`, `pi/agent/bin/agnt_lib/improvement.py`, deterministic tests, and scanner docs.

**Acceptance:** Preserve schema-1 safe summaries and schema-2 private packets, privacy, bounded discovery, exact session/child joins, cursor continuation, trace/root grouping, raw-string parsing, cost/accounting semantics, and v3 operation. Prove synthetic v1/v2 parity, current v3 behavior, and live v2 parity during dual-write validation.

### Follow-up B — `pi-4tg9.44` V4-safe pi-langfuse ingestion

**Scope:** upstream/fork `pi-langfuse`, version-locked projection, deployment checks, and focused package tests.

**Acceptance:** Require Langfuse JS 5.4.0 or newer; retain OTel as authoritative ingestion; use capability-appropriate visibility; never attempt removed trace/span/generation REST ingestion on v4; preserve allowed score ingestion, shutdown deadlines, bounded payloads, media privacy, stable IDs, and explicit delivery diagnostics. Verify v3 and v4/dual behavior before rollout.

### Follow-up C — `pi-4tg9.45` Self-hosted dual-write migration

**Scope:** remote infrastructure and project configuration only after separate approval.

**Acceptance:** Record infrastructure versions/topology/capacity, producer inventory, UI evaluator/export audit, history strategy, backup/rollback plan, worker propagation health, representative v1/v2 parity, and a reversible `legacy` or `dual` deployment. Keep `events_only` and old-table truncation under later approvals.

## Verification

```bash
# Repository inventory and deterministic checks
rg -n '/api/public/(traces|observations|v3/scores)' pi/agent/bin/agnt_lib/langfuse.py
rg -n 'api/public/traces|api/public/ingestion|trace-create|span-create|generation-create' forks/pi-langfuse/src/langfuse.ts
pi/agent/bin/agnt langfuse check --quiet
.venv/bin/python -m pytest -q tests/test_beads_workspace.py tests/test_langfuse_evaluators.py tests/test_langfuse_skill.py tests/test_package_patches.py tests/test_pi_packages.py
scripts/check-pi-config.sh
git diff --check

# Private read-only evidence; no remote writes
.venv/bin/python ~/.pi/improvement/v4-evaluation/read_probe.py
```

## Verified Primary Sources

- [Langfuse v4 overview](https://langfuse.com/docs/v4)
- [Self-hosted v3 to v4 migration](https://langfuse.com/self-hosting/upgrade/upgrade-guides/upgrade-v3-to-v4)
- [Self-hosted compatibility matrix](https://langfuse.com/self-hosting/upgrade/versioning)
- [Deprecated API migration](https://langfuse.com/faq/all/deprecated-api-migration)
- [Observations API v2](https://langfuse.com/docs/api-and-data-platform/features/observations-api)
- [Metrics API v2](https://langfuse.com/docs/metrics/features/metrics-api)
- [SDK upgrade paths](https://langfuse.com/docs/observability/sdk/upgrade-path)

Every URL above returned HTTP 200 and was checked against the cited claim on 2026-08-09.

## Execution Handoff

Evaluation saved here. File the three atomic follow-ups, verify this document against Beads and source, then close pi-4tg9.16 as a no-go decision. Do not perform remote migration under this issue.
