# Approval Session Binding Design-Plan

**Issue:** pi-rxo3.34 — Bind approval UI to invoking Pi session
**Design:** Approved in session on 2026-08-15
**Date:** 2026-08-15
**Branch:** main

**Goal:** Fail closed before showing approval UI in an unbound session and replace forgeable CLI resolver flags with process-bound proof.

**Architecture:** Each bridge instance binds session ID/file/generation and revalidates after request/UI awaits. Approval tools execute sequentially. Each request gets a 256-bit in-memory secret; Beads stores only session/secret SHA-256 fingerprints. Accepted resolution must match both fingerprints, arrive over a parent-authenticated child socket, and attest a currently pending ticket tool call on the active session branch. Restart/reload clears secrets, so old pending gates must be reissued before positive resolution; negative outcomes remain available.

**Acceptance Criteria:**
- [ ] Concurrent bridge instances cannot show UI for another session.
- [ ] Missing or stale binding returns the existing durable pending blocker before UI.
- [ ] `--resolver-kind human-ui --resolver-session <known-id>` cannot approve or answer.
- [ ] Parent-authenticated, request-secret, pending-tool attestation permits human-confirmed approval and records only non-sensitive fingerprints.
- [ ] Session replacement during request/UI await cannot restore or use stale resolver state.
- [ ] Existing preview, blocker, cancellation, and Beads provenance behavior remains intact.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_approvals.py -q
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Add failing approval binding tests

**Files:**
- Modify: `tests/test_approvals.py`

**Steps:**
1. Add CLI tests proving resolver flags alone fail and inherited-FD proof succeeds.
2. Add bridge tests with two session contexts proving stale/unbound instances never call UI or resolution.
3. Run focused tests and confirm expected failures.

### Task 2: Enforce process and session binding

**Files:**
- Modify: `pi/agent/extensions/beads-ask-bridge.ts`
- Modify: `pi/agent/extensions/lib/run-agnt-json.ts`
- Modify: `pi/agent/bin/agnt_lib/approvals.py`

**Steps:**
1. Track bridge instance session lifecycle.
2. Return pending/throw before dialog when context is not bound.
3. Pass request-secret and pending-tool attestation over a parent-authenticated child socket, reject resolver CLI flags/forged sockets, revalidate session generation after awaits, and persist only hashed binding/audit metadata.
4. Run focused approval tests.

### Task 3: Verify candidate

**Files:**
- Review all task-owned changes and this plan.

**Steps:**
1. Run focused tests and stable diff checks.
2. Run project verification matrix.
3. Stage, commit, and close `pi-rxo3.34` through direct closeout.
