# Telemetry Fidelity Implementation Plan

**Issue:** pi-04q7.3 — Repair invocation and handoff telemetry fidelity
**Design:** Bead `pi-04q7.3`
**Date:** 2026-08-16
**Branch:** main

**Goal:** Preserve safe routed invocation dimensions and count-only handoff stage outcomes in existing private telemetry.

**Architecture:** Extend existing Archimedes wrapper metadata and subagent metric producer; do not alter worker execution. Write bounded handoff records to existing private `metrics/invocations` runtime path, then isolate and aggregate them in existing metrics consumer.

**Acceptance Criteria:**
- [ ] Failed subagents always receive normalized termination evidence; routed task, effective thinking/mode, and output contract survive metric capture.
- [ ] Handoff attempts, stages, result classes, and durations are countable without Bead/session IDs or payloads.
- [ ] Legacy invocation metrics remain readable; handoff records do not affect routing totals.
- [ ] Privacy, telemetry, and project checks pass.

**Verification Commands:**
```bash
.venv/bin/python -m pytest -q tests/test_subagent_workaround.py tests/test_agent_os_compat.py tests/test_bead_handoff.py tests/test_agnt.py tests/test_output_redaction.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Lock subagent fidelity with RED tests

**Files:** `tests/test_subagent_workaround.py`, `tests/test_agent_os_compat.py`, `tests/test_agnt.py`

Add failing assertions for route metadata transport, effective result profile fields, safe process-error fallback, and payload exclusion. Run focused tests and confirm expected failures.

### Task 2: Preserve subagent dimensions

**Files:** `pi/agent/bin/agnt_lib/routing.py`, `pi/agent/extensions/archimedes.ts`, `pi/agent/extensions/subagent-error-workaround.ts`, `pi/agent/bin/README.md`

Expose and strip safe `routingTask` wrapper metadata, emit it from route examples, prefer effective execution profile values, and normalize nonzero missing reasons once at shared termination seam.

### Task 3: Lock handoff telemetry with RED tests

**Files:** `tests/test_bead_handoff.py`, `tests/test_agnt.py`

Add failing producer/privacy and consumer aggregation tests. Confirm handoff records contain only schema, kind, stage, result class, and duration.

### Task 4: Record and aggregate handoff stages

**Files:** `pi/agent/extensions/bead-handoff.ts`, `pi/agent/bin/agnt_lib/metrics.py`, `pi/agent/bin/README.md`

Instrument shared command/tool flow using best-effort private runtime records. Keep records out of invocation/routing totals and compact through an allowlist.

### Task 5: Verify, review, and close

Run focused then full project checks, review task-owned diff, commit once, and run direct closeout.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-16-telemetry-fidelity-plan.md`.
Recommended skills: `test-driven-development`, then `verification-before-completion`.
