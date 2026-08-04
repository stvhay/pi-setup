# Package Conversation Sanitizers Implementation Plan

**Issue:** pi-4tg9.6 — Record truthful tool payload byte metadata under privacy presets
**Design:** This file
**Date:** 2026-08-04
**Branch:** fix/pi-4tg9-6-derived-payload-metrics

**Goal:** Prevent raw provider and message-bearing events from reaching package-owned pi-langfuse handlers while preserving required conversation and generation metadata.

**Architecture:** Keep local extension handlers on the real `ExtensionAPI`. Give only pi-langfuse registration a proxy that wraps five sensitive events, constructs allowlisted fresh clones, discards package mutations/results, and reuses existing bounded text/media sanitizers.

**Acceptance Criteria:**
- [ ] Every provider payload alias is independently sanitized; alias-free input gets a sanitized `payload` fallback.
- [ ] Cyclic, nonobject, and unknown values never expose the raw provider event.
- [ ] Package `message_update`, `message_end`, `turn_end`, and `agent_end` handlers receive safe conversation clones with generation-close metadata but no tool or unknown structured content.
- [ ] Original events, local pre/post handlers, subscription zero-cost alias, and persisted runtime model remain unchanged.
- [ ] Focused/full tests, lint, evals, config checks, shell checks, and diff checks pass.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_langfuse_skill.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
scripts/check-pi-config.sh
bash -n scripts/*.sh
git diff --check
```

---

### Task 1: Add strict RED coverage

**Files:**
- Modify: `tests/test_langfuse_skill.py`

Add parameterized provider-alias and message-event tests, alias-free/nonobject/cycle coverage, package-only isolation checks, and no-mutation assertions. Run focused tests and confirm failures stem from current raw-event forwarding.

### Task 2: Implement minimum proxy sanitization

**Files:**
- Modify: `pi/agent/extensions/langfuse-config-env.ts`

Reuse bounded conversation helpers, add allowlisted scalar/usage/cost copying, and wrap only package registrations for five sensitive events. Run focused tests green.

### Task 3: Align composition docs and verify

**Files:**
- Modify: `pi/README.md`
- Modify: `docs/extension-web-compatibility.md`

Replace stale provider-only claims, then run full verification, review final diff, and create requested atomic commit without deploy, merge, or Bead close.
