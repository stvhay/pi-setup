# Deployment and test efficiency

**Issue:** pi-j3es
**Date:** 2026-09-06
**Branch:** fix/deploy-test-efficiency
**Approval:** User selected both fixes. Local source, tests, docs, branch and commits only; no live deployment, remote evaluator writes, or push.

## Goal and design

Use existing deployment script for deterministic operations rather than model-built shell procedures. Keep reusable Pi guidance separate from this repository's deploy/test instructions. Local config deployment must not implicitly reconcile remote Langfuse resources; existing `agnt langfuse apply` remains explicit. Preserve destination checks, private state, package patch guards and failure handling.

Deployment script gains actual itemized rsync preview, managed-config-only backup, canonical source/target reporting and source/live config checks. Backup excludes credentials, sessions, packages and runtime stores; package reinstall recovery remains separate. No automatic destructive rollback. Retain evidence on failure and document rollback limits.

Tests first lose inherited live credentials and config/target overrides. Profile safely; reduce whole-config copies for synthetic deployment cases using existing `PI_CONFIG_SOURCE` seam, retaining real-source integration coverage. No new parallel-test dependency or timeout-only performance fix.

## Evidence before changes

Recent local sessions: deployment apply tool ~1.6s versus 5m49s total, 33 calls; full pytest 1025 passed in 203.67s after a 120s timeout; deploy tests 32 passed in 93.24s. `tests/test_update_pi_config.py:run_update` inherits environment and script invokes real Langfuse apply when credentials exist. Unsafe original benchmark intentionally not repeated. Graphify queried but stale; source verified.

## Tasks

1. Add regression proving deploy test helper removes ambient credentials/config overrides; isolate helper before safe baseline with `--durations=15`. Inspect remaining slow tests, change only measured bottlenecks.
2. Add failing deployment behavior checks: actual dry-run/no mutation, local-only with credential config preserved, backups/private exclusions, pre/post check failure paths. Extend existing script and adjust synthetic fixtures; retain actual-source integration.
3. Align `AGENTS.md`, `README.md`, `pi/README.md`, `CONTRIBUTING.md`, and relevant architecture text without duplicating generic workflow rules. Document one-script procedure, explicit remote command, backup/rollback limits, focused feedback versus final full gate.
4. Review stable candidate; run focused and full deterministic verification; commit task-owned changes and direct-closeout. Preserve unrelated untracked telemetry plan.

## Verification

```bash
.venv/bin/python -m pytest tests/test_update_pi_config.py tests/test_langfuse_evaluators.py --durations=15
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt eval run quality-process-smoke
git diff --check
git diff --cached --check
```

Full run bounded at 600s during investigation, not retried unchanged. Test doubles must prevent external package/network actions. Tests invoking deployment always target temporary `.pi` directories.

## Implementation evidence

- Isolation regression failed on inherited environment, then passed after filtering credentials/target overrides. Safe full baseline: 1026 passed in 128.79s. Deployment suite: 17.15s after isolation, 15.57s after minimal source fixtures (before added backup/verification checks).
- Eight new deployment safety/behavior cases failed before implementation. Focused deployment/evaluator/context checks now pass: 118 passed in 32.26s.
- Independent discovery plus fresh verifier confirmed and fixed recovery overwriting newer runtime changelog state. Regression failed before fix, then passed using the same atomic preservation function in deployment and generated recovery script.
- Existing limitation retained: preview is not an authorization receipt. Caller must recheck exact source/target/effects and obtain new approval on drift; no new authority protocol was approved. Recovery requires separate approval and restores managed config only, not installed package versions or npm manifests.
- Review evidence: `.pi/reviews/pi-j3es/review.md` (private). Final matrix and commit references belong in Bead closeout notes, not a post-gate candidate change.

## Execution handoff

Plan saved here; use TDD and verification-before-completion. No live deployment or push authorized. Final candidate verification and direct closeout remain required.
