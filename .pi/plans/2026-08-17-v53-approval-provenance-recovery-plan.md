# v53 Approval Provenance Recovery Implementation Plan

**Issue:** pi-f955 — Support v53 approval provenance and recover Beads
**Design:** Approved inline design: canonical append-only Bead comments replace v65-only provenance events
**Date:** 2026-08-17
**Branch:** main

**Goal:** Preserve fail-closed approval and capability-grant identity checks on Beads v1.2.2/schema v53, then recover this workspace from schema v65 without losing work state.

**Architecture:** Write canonical `agnt-provenance-v1` JSON envelopes as Bead comments and read them through `bd comments <id> --json`. Beads v1.2.2 exposes comment add/list but no comment mutation or deletion; comments remain versioned and are included in JSONL exports. Missing, malformed, foreign-source, or conflicting provenance fails closed. Before rollback, copy the three existing provenance records into equivalent comments; preserve v65 data and binaries in private backups.

**Acceptance Criteria:**
- [ ] Approval-request fingerprints and capability-grant transitions use schema-v53 comment commands only.
- [ ] Missing, malformed, conflicting, changed, expired, and revoked records retain fail-closed behavior.
- [ ] Request provenance is appended before the decision becomes a blocker.
- [ ] CI uses a checksum-pinned Beads v1.2.2 binary and exercises the real comment-backed approval seam.
- [ ] Documentation identifies append-only Bead comments as the approval identity ledger.
- [ ] Existing v65 provenance rows are backfilled exactly once into comments.
- [ ] Private binary/database backups verify before migration.
- [ ] Local database reports migration cursor v53 and standard/approval Beads workflows pass under v1.2.2.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_approvals.py tests/test_beads_workspace.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
git status --short
```

---

### Task 1: Add comment-ledger tests [Independent]

**Context:** Replace mocked `bd provenance` expectations with canonical comment envelopes while preserving FAIL-7 and FAIL-12 behavior.

**Files:**
- Modify: `tests/test_approvals.py`
- Modify: `tests/test_beads_workspace.py`

**Steps:**
1. Change the fake Beads adapter to model `comments add` and `comments <id>`.
2. Add focused assertions for canonical envelope shape, create/comment/block order, duplicate tolerance, malformed/conflicting comment rejection, and grant-state monotonicity.
3. Add a real-CLI compatibility smoke using the CI-pinned binary surface.
4. Run focused tests and confirm expected RED failures against current production code.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_approvals.py tests/test_beads_workspace.py
```

**Expected result:** Tests fail only because production still calls `bd provenance` or orders the blocker before the comment.

### Task 2: Implement comment-backed provenance [Depends on: Task 1]

**Context:** Keep approval payloads and validators unchanged; replace only persistence/read transport.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/approvals.py`

**Steps:**
1. Encode one prefixed canonical JSON envelope containing `schemaVersion`, `source`, and existing payload.
2. Append with `bd comments add <decision> <envelope>`.
3. Read with `bd comments <decision>` and parse only exact prefixed records.
4. Reject malformed prefixed records, unexpected sources, missing request identity, conflicting fingerprints, and regressive/foreign grant states.
5. Reorder creation to create decision, append request provenance, then create blocker.
6. Run focused tests to GREEN; refactor only duplicated transport code.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_approvals.py
```

**Expected result:** Approval tests pass without any `bd provenance` command.

### Task 3: Pin compatibility and align docs [Depends on: Task 2]

**Context:** Current CI pin 1.1.0 does not exercise the required backend. v1.2.2 is the target recovery binary.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_beads_workspace.py`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `pi/agent/quality/SPEC.md`
- Modify if needed: `pi/agent/bin/README.md`

**Steps:**
1. Verify v1.2.2 release asset checksum from the published asset/checksum file.
2. Pin CI version and checksum.
3. Update architecture/spec wording from provenance events to append-only provenance comments without weakening invariants.
4. Run focused tests, Ruff, config checks, and diff checks.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_approvals.py tests/test_beads_workspace.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
git diff --check
```

**Expected result:** Source and docs agree on v53-compatible comment ledger; checksum pin is exact.

### Task 4: Review, full verify, and commit [Depends on: Task 3]

**Context:** Approval storage is a security boundary. Review source/test claims before any live mutation.

**Steps:**
1. Inspect complete diff and run security-focused peer review if routing is available.
2. Run full documented verification.
3. Stage only task-owned files and create one atomic implementation commit.

**Expected result:** Clean task-owned commit; no deployment or database mutation yet.

### Task 5: Preview and approve live recovery [Depends on: Task 4]

**Context:** Local-live Pi deployment, binary replacement, provenance backfill, and schema-cursor rollback are consequential single-use actions.

**Steps:**
1. Resolve host/user, canonical `/Users/hays/.pi`, real bd path, exact v1.2.2 asset/checksum, database path, candidate commit, deployment dry-run, backup paths, and rollback commands.
2. Show exact effects and stop conditions in one informed approval gate.
3. Stop if identity, source, preview, checksum, database schema, or existing provenance count differs.

**Expected result:** Exact approval exists before mutation.

### Task 6: Backfill, deploy, and recover [Depends on: Task 5]

**Context:** Backfill while v1.2.1 can still read `provenance_events`; upgrade every local binary before cursor rollback so v1.2.1 cannot remigrate v53 to v65.

**Steps:**
1. Backfill each existing provenance row into one canonical comment and verify payload parity.
2. Deploy candidate tracked Pi config through `scripts/update-pi-config.sh` and verify byte/state parity.
3. Create and verify private copies of current bd binary and `.beads` database.
4. Replace the real bd binary with checksum-verified v1.2.2.
5. Stop Beads processes; delete only `schema_migrations.version > 53` and commit that database change with explicit recovery author, per upstream runbook.
6. Verify cursor v53, issue/comment counts, backfilled fingerprints, `bd prime`, `bd ready`, `bd show pi-f955`, approval-focused smoke, and repository checks.
7. Retain backups; no cleanup or deletion.

**Expected result:** v1.2.2 operates normally on schema cursor v53; approval ledger remains verifiable; backups remain available.

### Task 7: Close direct work [Depends on: Task 6]

**Steps:**
1. Record exact verification and backup recovery references in `pi-f955` without secrets.
2. Run `agnt work direct-closeout pi-f955 --outcome success --reason "..."`.
3. Verify portable Beads commit and clean tracked state.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-17-v53-approval-provenance-recovery-plan.md`
Recommended next skill: `test-driven-development`; `verification-before-completion` before completion claims.
