# Approval Provenance History Purge Implementation Plan

**Issue:** pi-ffrh.7 — Keep approval provenance private
**Design:** `.pi/plans/2026-07-27-langfuse-continuous-improvement-design-plan.md`
**Date:** 2026-07-28
**Branch:** main

**Goal:** Remove legacy private approval resolver/run identifiers from reachable Git and local Dolt history after the current-state fix, without changing unrelated source or Bead content.

**Architecture:** Use one deterministic JSONL sanitizer for Git history and equivalent SQL for Dolt history. Rehearse both rewrites against private copies first. Preserve private 0600 backups until the user verifies the rewritten remote and explicitly authorizes backup deletion. Updating the configured Git remote requires a separate exact approval because commit IDs change and collaborators must resynchronize.

**Acceptance Criteria:**
- [ ] Every reachable Git commit contains no approval `requestingRun`, approval resolver `sessionId`, target human-approval resolver `sessionId`, or `Requesting run:` description line.
- [ ] Rewritten Git trees differ only in `.beads/issues.jsonl` and only by those allowlisted removals.
- [ ] Current code, tests, branches, and Bead IDs remain intact after rewrite.
- [ ] Local Dolt history contains no matching approval provenance fields or description lines.
- [ ] Configured remote `main` is force-updated only with an exact lease against the preflight remote commit.
- [ ] Private backups remain outside the repository with mode 0600 until separate deletion approval.
- [ ] Collaborator resynchronization and limits of remote cache/fork erasure are reported explicitly.

**Verification Commands:**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git fsck --full
git status --short
bd doctor
```

---

## Safety boundaries

- Do not start without a new exact approval covering local Git rewrite, local Dolt rewrite, and configured-remote force update.
- Do not delete branches, Beads, tags, worktrees, or backups.
- Do not rewrite source files other than historical `.beads/issues.jsonl` blobs.
- Do not use broad text replacement. Parse each JSONL record and remove only:
  - `metadata.pi.approval.requestingRun`
  - `metadata.pi.approval.resolver.sessionId`
  - `metadata.pi.humanApproval.resolver.sessionId`
  - description lines beginning exactly `Requesting run:`
- Preserve key order, record order, Bead IDs, timestamps, status, notes, dependencies, and all unrelated fields.
- Do not claim complete erasure from forks, caches, clones, or provider retention systems outside repository control.

## Task 1: Capture immutable preflight evidence [Independent]

**Context:** Freeze expected refs before any rewrite. Abort if the remote changes after capture.

**Files:**
- Private only: `~/.pi/improvement/history-purge-<timestamp>/`

**Steps:**
1. Require clean Git and Dolt working states.
2. Record local branch refs, configured remote refs, current `main`, and remote `main` commit in a 0600 private manifest.
3. Record counts of unsafe Git commits/records and unsafe Dolt commits/records without storing identifier values in the manifest.
4. Record current test/eval baseline.

**Focused verification:**
```bash
test -z "$(git status --short)"
cd .beads/embeddeddolt/pi && dolt status
```

**Expected result:** Both stores are clean; private manifest records exact pre-rewrite refs and aggregate exposure counts.

## Task 2: Create private backups [Depends on: Task 1]

**Context:** Rewrites are destructive. Backups contain the legacy private data and must never enter Git or deployment.

**Steps:**
1. Create `git bundle --all` under the private purge directory.
2. Archive `.beads/embeddeddolt/pi` under the same private directory while no Dolt mutation is active.
3. Set directory mode 0700 and backup files mode 0600.
4. Verify Git bundle and archive readability.

**Focused verification:**
```bash
git bundle verify "$PRIVATE/git-before.bundle"
tar -tf "$PRIVATE/dolt-before.tar" >/dev/null
stat -c '%A %n' "$PRIVATE/git-before.bundle" "$PRIVATE/dolt-before.tar"
```

**Expected result:** Restorable private backups exist outside the repository with restrictive permissions.

## Task 3: Build deterministic private sanitizer and scanner [Depends on: Task 1]

**Context:** Temporary scripts live only in the private purge directory. They parse JSON; regex-only mutation is prohibited.

**Steps:**
1. Write a Python sanitizer that reads `.beads/issues.jsonl`, parses every line, performs only the four allowlisted removals, and writes compact JSONL preserving record/key order.
2. Write a scanner that exits nonzero if any allowlisted private field/line remains.
3. Write a structural comparator that proves each rewritten record equals the old record after applying only the allowlisted sanitizer.
4. Unit-test scripts against safe, unsafe, malformed, missing-file, string-metadata, and object-metadata fixtures.

**Focused verification:**
```bash
python3 "$PRIVATE/test_sanitizer.py"
```

**Expected result:** Sanitizer is deterministic, fail-closed on malformed JSON, and cannot alter unrelated fields.

## Task 4: Rehearse Git rewrite in an isolated clone [Depends on: Tasks 2 and 3]

**Context:** Use built-in `git filter-branch --tree-filter`; no new repository dependency is required. The rehearsal must cover all local branches and refs that execution would rewrite.

**Steps:**
1. Clone the local repository into the private purge directory with all source refs available.
2. Run `FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --tree-filter 'python3 <private-sanitizer>' -- --all` only in the rehearsal clone.
3. Run the historical scanner across every rewritten reachable commit.
4. Compare pre/post commits and prove all changed paths are `.beads/issues.jsonl`.
5. Check out rewritten `main` and run full project verification.

**Focused verification:**
```bash
git rev-list --all | python3 "$PRIVATE/scan_git_history.py"
git log --all --name-only --format= | sort -u
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/
git fsck --full
```

**Expected result:** Rehearsal removes only allowlisted approval provenance and passes all checks.

## Task 5: Rehearse Dolt rewrite in a private copy [Depends on: Tasks 2 and 3]

**Context:** Dolt provides `filter-branch`. SQL must remove the same fields and description line from every commit.

**Steps:**
1. Restore the Dolt backup into a private rehearsal directory.
2. Run `dolt filter-branch --all` with:
   - `JSON_REMOVE(metadata, '$.pi.approval.requestingRun', '$.pi.approval.resolver.sessionId', '$.pi.humanApproval.resolver.sessionId')`
   - `REGEXP_REPLACE(description, '\nRequesting run: [^\n]*', '')`
3. Verify every rewritten commit using `issues AS OF <commit>` queries.
4. Validate current data through `bd list` against the private copy and run `bd doctor` in read-only mode.
5. Confirm content hashes/sync state are valid; stop if Dolt reports stale hashes or schema inconsistency.

**Focused verification:**
```bash
cd "$PRIVATE/dolt-rehearsal/pi"
dolt status
dolt log -n 5 --oneline
```

**Expected result:** Rehearsal history is clean and current Beads remain readable without schema/hash warnings.

## Task 6: Request exact execution approval [Depends on: Tasks 4 and 5]

**Context:** Present rehearsal evidence before requesting destructive authority.

**Approval must state:**
- exact local refs to rewrite;
- exact preflight remote `main` commit used for `--force-with-lease`;
- configured remote and branch, without embedding private repository metadata in Beads;
- collaborator impact and required resynchronization;
- backup location class and retention policy, not its absolute path;
- inability to guarantee deletion from third-party forks, caches, or clones;
- no branch/tag/Bead deletion and no backup deletion.

**Expected result:** Execution remains blocked unless the exact approval is granted.

## Task 7: Execute local Git and Dolt rewrites [Depends on: Task 6]

**Steps:**
1. Recheck clean states and ensure current remote `main` still equals the approved preflight commit.
2. Execute the rehearsed Git rewrite against approved refs.
3. Execute the rehearsed Dolt rewrite against its only local branch.
4. Do not remove `refs/original`, reflogs, or backups yet.
5. Run all historical scanners and full project verification.

**Expected result:** Local current and historical stores are clean, backups remain, and no remote mutation has occurred yet.

## Task 8: Force-update configured remote main [Depends on: Task 7]

**Steps:**
1. Reconfirm remote `main` still matches the approved preflight commit.
2. Push only rewritten `main` using `--force-with-lease=main:<approved-old-commit>`.
3. Do not push local epic branches, backup refs, tags, or Dolt data.
4. Fetch remote `main` and compare it with rewritten local `main`.
5. Re-run the Git history scanner against fetched remote history.

**Expected result:** Configured remote `main` points to rewritten clean history; unrelated refs were not pushed.

## Task 9: Close out without deleting recovery data [Depends on: Task 8]

**Steps:**
1. Record public-safe aggregate verification in `pi-ffrh.7`; keep private hashes/ref maps in the purge directory.
2. Tell collaborators that commit IDs changed and old clones must be discarded or carefully resynchronized.
3. Report remote-provider limitations: inaccessible forks, caches, clones, and retention may still contain old objects.
4. Leave Git backup refs/reflogs and private backup files until a separate deletion approval.
5. Request separate approval before deleting backups, expiring reflogs, pruning objects, or removing `refs/original`.

**Expected result:** History purge is verified and reversible locally; destructive cleanup remains separately gated.

## Rollback

Before remote update, restore from private Git bundle and Dolt archive. After remote update, rollback requires another force-with-lease update and would reintroduce the removed data; do not roll back without explicit approval. Never use backup refs as normal development branches or push them.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-28-approval-provenance-history-purge-plan.md`

Recommended next skill: `executing-plans` after exact rewrite approval; `verification-before-completion` before any completion claim.
