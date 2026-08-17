# Lifecycle Latency Design and Implementation Plan

**Issue:** pi-04q7.6 — Remove proven deterministic lifecycle latency
**Design:** Bead design
**Date:** 2026-08-16
**Branch:** main

**Goal:** Remove only largest repeated deterministic latency source proven material after metrics consolidation.

**Architecture:** Keep local ledgers and private-runtime checks authoritative. Prefer existing aggregate/caching seams; do not add services, schedulers, or deferred durability work.

## Scorable task

- Candidate: smallest change in route history, runtime-path resolution, or lifecycle projection.
- Evaluator: 30 isolated trials per before/after path; report p50 and p95 wall time.
- Primary metric: minimize p95 latency, with p50 as secondary evidence.
- Guardrails: exact output parity, focused tests, full deterministic project checks, unchanged fail-closed/private-runtime behavior.
- Budget: profile three named paths; implement at most one candidate.
- Acceptance threshold: repeated path improves p95 by at least 20 ms and 20%; otherwise close with evidence and no production code.
- Rollback: revert single task commit.

## Tasks

1. Consolidate pending invocation metrics, verify zero pending files, then benchmark route with and without history.
2. Profile route history, repeated `agnt runtime-path` resolution, and synchronous lifecycle projection using existing source/tests.
3. Write one failing regression/performance check for largest qualifying source, then make minimum production change. Skip implementation if no source qualifies.
4. Re-run identical benchmark and focused/full deterministic checks; record raw commands, p50, and p95.

**Changed implementation files:**
- `pi/agent/bin/agnt_lib/runtime_paths.py`
- `pi/agent/extensions/subagent-error-workaround.ts`
- focused tests under `tests/`

**Verification commands:**

```bash
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

## Results

Metrics maintenance consolidated 2,677 pending records into the existing global store; `agnt metrics status` then reported zero pending files.

Post-consolidation route history remained slower than `--ignore-history`: 128.051 / 149.755 ms p50/p95 versus 61.624 / 68.287 ms. `cProfile` attributed 52 ms of the 71 ms history path to repeated runtime resolution, but a safe route-only batch cut p95 by only 10.0%, below threshold, so those edits were removed.

Chosen repeated path: subagent artifact plus metric directory resolution.

| 30 isolated trials | p50 | p95 |
|---|---:|---:|
| Before: two `agnt runtime-path` processes | 149.234 ms | 165.622 ms |
| After: one batched `agnt runtime-path` process | 81.211 ms | 85.633 ms |
| Reduction | 68.023 ms (45.6%) | 79.989 ms (48.3%) |

Batching shares Git identity discovery but still performs symlink, `check-ignore`, `ls-files`, and private-mode checks for every requested kind. Batch failure falls back to original independent resolutions. An earlier global-cache candidate was rejected after a failing nested-repository reproducer showed stale identity could cross repository boundaries.

Lifecycle projection's injected immediate sink measured 0.004 ms p50 / 0.019 ms p95. A controlled 25 ms sink measured 26.079 ms p50 / 26.142 ms p95, confirming synchronous propagation but not production latency. No deferred projection change: actual remote p95 remains unmeasured.

Runnable deterministic regression/performance checks:

```bash
.venv/bin/python -m pytest \
  tests/test_agnt.py::test_runtime_path_command_batches_safe_kinds \
  tests/test_runtime_artifacts.py::test_runtime_directory_reuses_git_identity_but_rechecks_each_candidate \
  tests/test_runtime_artifacts.py::test_runtime_directory_refreshes_identity_when_nested_repository_appears \
  tests/test_subagent_workaround.py::test_subagent_result_batches_runtime_path_resolution -q
```
