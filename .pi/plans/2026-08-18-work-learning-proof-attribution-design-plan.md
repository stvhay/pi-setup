# Work-Learning Proof and Attribution Design and Implementation Plan

**Issue:** None
**Design:** None
**Date:** 2026-08-18
**Branch:** `main`

**Goal:** Make observe-only work-learning reviews produce valid, checkable proof and attributable delegated-result evidence without broadening telemetry payloads, enabling source capture, raising scan caps, or adding another evidence store.

**Architecture:** Keep current producers and private packet pipeline. `pi-langfuse` preserves explicit zero cache fields at generation capture; `subagent-error-workaround.ts` emits already-known trusted route dimensions and worker timing; `improvement.py` retains those allowlisted fields and exact evaluator linkage. Shared Finding limits, one-attempt review semantics, privacy defaults, truthful unavailable states, and the 500-trace operator cap remain authoritative.

## Score Targets

- **Proof: target 8/8** across the four fixed replay cases. A `2` requires correct, bounded, reviewer-checkable evidence. An explicit unavailable state earns `2` only when source, reason, integrity, and evidence reference are present; unknown without those facts remains `0`.
- **Delegated attribution: target 4/4 across the two applicable delegated replay cases**, plus **100% of newly captured delegated projections** having either complete attribution or an explicit unavailable reason. Do not award points for non-delegated cases.
- **Tool dimension: target 4/8 in this scope.** Reaching 8/8 would require root-tool choice/necessity evidence for non-delegated work, broadening telemetry and privacy scope without evidence that it is needed.
- Keep overall replay totals secondary. No score may improve by relabeling missing evidence as success or by excluding a difficult case.

**Acceptance Criteria:**
- [ ] Review rubric states the shared maximum of 16 distinct EvidenceRefs per finding; a 20-session assignment can be completed with findings citing representative subsets while all sessions remain covered exactly once.
- [ ] Explicit zero `cacheRead`/`cacheWrite` values survive generation capture; absent or invalid provider fields remain unavailable rather than inferred as zero.
- [ ] New delegated projections retain bounded provider/model/target/routing task/mode/thinking/output-contract dimensions and worker elapsed time from existing observer evidence, or an explicit unavailable status.
- [ ] Capture-observation latency is no longer exposed as child worker latency.
- [ ] Evaluator outcomes join to one exact delegated projection when observation linkage exists; missing or ambiguous linkage remains explicit.
- [ ] Private packets still exclude task/output bodies from new fields, and safe summaries still exclude private identifiers and timing.
- [ ] Fixed replay pack scores Proof 8/8 and delegated attribution 4/4; 100% of applicable projections satisfy complete-or-explicit-unavailable attribution.
- [ ] Source metadata remains opt-in/off, scan cap remains 500, one-attempt review behavior remains unchanged, and no scheduler, dependency, parallel registry, or new telemetry stream is added.

**Verification Command(s):**
```bash
# pi-langfuse fork
npm --prefix forks/pi-langfuse exec -- tsx --test test/utils.test.ts
npm --prefix forks/pi-langfuse run typecheck
npm --prefix forks/pi-langfuse test

# package projection and focused parent behavior
scripts/verify-pi-langfuse-package-patch.sh
.venv/bin/python -m pytest \
  tests/test_improvement.py \
  tests/test_subagent_workaround.py \
  tests/test_package_patches.py

# full project gate
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

## Suggested Work Graph

Use separate implementation Beads because work crosses three independently testable boundaries:

1. **Review-result contract clarity** — rubric/tests only.
2. **Cache usage producer semantics** — maintained `pi-langfuse` fork plus version-locked package projection.
3. **Delegated projection proof** — parent observer/scanner/tests/docs.
4. **Replay verification** — depends on 1–3; private post-deployment evidence only after separate deployment approval.

No Beads are created by this plan. Implementation approval must name exact Beads and any fork branch/push/deployment scope.

### Task 1: Align review EvidenceRef contract [Independent]

**Context:** Shared Finding validation caps each finding at 16 EvidenceRefs, while review assignments may contain 20 sessions. Keep both limits; make representative-subset behavior explicit so a reviewer does not emit a terminal schema-invalid result.

**Files:**
- Modify: `pi/agent/langfuse/improvement-review.md`
- Modify: `tests/test_improvement.py`

**Steps:**
1. Add a focused rubric assertion requiring the exact 16-reference cap and stating that session coverage and finding evidence coverage are separate.
2. Add a 20-session current-policy fixture where every session receives one decision, one cohort finding cites 16 distinct packet refs, and validation succeeds.
3. Add the adjacent 17-reference rejection case and preserve fail-closed `schema-invalid`/human routing with no retry or marker.
4. Update rubric: findings cite at most 16 distinct packet EvidenceRefs; use the smallest representative subset meeting the claim; every assigned session still appears exactly once.
5. Do not change `MAX_EVIDENCE_REFS`, assignment size, review attempts, or apply semantics.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py -k 'evidence_ref or review_rubric or current_review'
```

**Expected result:** A 20-session review can complete under the documented contract; 17 finding refs still fail closed.

### Task 2: Preserve explicit zero cache usage in pi-langfuse [Independent]

**Context:** `forks/pi-langfuse/src/utils.ts::extractUsage` currently omits zero-valued cache fields. Scanner policy correctly distinguishes missing from present zero, so fix the producer rather than weakening scanner validation.

**Files:**
- Modify: `forks/pi-langfuse/src/utils.ts`
- Modify: `forks/pi-langfuse/test/utils.test.ts`

**Steps:**
1. Import `extractUsage` in `test/utils.test.ts` and add RED cases for explicit zero, absent fields, supported zero-valued aliases, and nonzero cache usage.
2. Implement presence-sensitive extraction: preserve valid explicit zero/nonzero cache values; omit fields when no supported provider key exists; do not coerce absent, Boolean, negative, fractional, non-finite, or nonnumeric values into valid zero.
3. Reuse current extraction path; add no new usage object, dependency, or provider-specific branch.
4. Run focused test, typecheck, and full fork suite.
5. Commit the fork change on one named local branch. Stop before push; portability requires a separate exact fast-forward push approval.

**Focused verification:**
```bash
npm --prefix forks/pi-langfuse exec -- tsx --test test/utils.test.ts
npm --prefix forks/pi-langfuse run typecheck
npm --prefix forks/pi-langfuse test
```

**Expected result:** Explicit cache zero remains present; absent/invalid cache usage remains absent; existing input/output/total behavior stays unchanged.

### Task 3: Emit worker proof on delegated projections [Independent]

**Context:** `subagent-error-workaround.ts` already owns invocation start, result `progressSummary.durationMs`, trusted route dimensions, output contract, and termination evidence. Reuse those facts in `subagent-result` metadata instead of inventing another timing or routing source.

**Files:**
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Modify: `tests/test_subagent_workaround.py`

**Steps:**
1. Add RED assertions that single, parallel, routed, inherited, failed, and named-agent projections carry bounded worker timing and existing effective dimensions.
2. Record `workerElapsedMs` from validated result progress when available, otherwise bounded parent wall elapsed; include a source/status field so fallback is visible.
3. Keep existing receipt-preferred provider/model/target/routing-task/mode/thinking/output-contract values. Named-agent unavailable dimensions remain unavailable, never guessed from runtime result text.
4. Reuse one tool-result end timestamp for metrics and projections where practical; do not add timers or lifecycle state.
5. Assert new metadata contains no task, output, artifact path, credential, or raw route receipt.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_subagent_workaround.py
```

**Expected result:** Every new delegated projection contains trusted dimensions and worker timing, or explicit unavailable evidence, with privacy behavior unchanged.

### Task 4: Retain attributable projection evidence in scans [Depends on: Task 3]

**Context:** `_projection_records` currently retains lineage/mode plus Langfuse observation timing, while `_features` strips evaluator subject linkage. Keep private IDs private, but retain enough bounded evidence to join one evaluator outcome to one projection and distinguish capture latency from worker duration.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `tests/test_improvement.py`
- Modify: `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Add RED fixtures for complete routed metadata, named-agent unavailable dimensions, malformed dimensions, exact observation-targeted score linkage, missing linkage, and ambiguous linkage.
2. Allowlist and validate projection dimensions already emitted by Task 3. Invalid or secret-shaped values become explicit unavailable states and never enter safe summaries.
3. Retain `workerElapsedMs` plus source/status. Rename newly scanned observation timing to `captureLatencySeconds`; stop emitting ambiguous projection `latencySeconds`. Historical packets remain readable because projection fields are additive/optional consumers.
4. Add evaluator subject linkage only when bounded score `observationId` matches exactly one retained `subagent-result`; otherwise set `projectionLinkStatus` to `unavailable` or `ambiguous` without guessing by order or timestamp.
5. Keep current session-level evaluator outcomes for compatibility; add only bounded linkage/status fields needed for attribution.
6. Verify safe cohort summaries contain no IDs, private timestamps, task/output text, repository identity, or new dimension values.
7. Update docs with timing semantics, complete-or-explicit-unavailable attribution, and score-link rules.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py -k 'projection or evaluator or cohort_health or privacy'
```

**Expected result:** Poor/weak delegated outcomes can be joined to exact trusted execution dimensions when evidence exists; unavailable linkage remains truthful.

### Task 5: Project and verify pi-langfuse fork delta [Depends on: Task 2]

**Context:** Parent repository must keep exact `pi-langfuse@1.5.14` installation reproducible. Do not reference an unpublished fork commit from the superproject.

**Files:**
- Modify: `forks/pi-langfuse` gitlink
- Modify: `patches/pi-packages/pi-langfuse-1.5.14.patch`
- Modify: `.pi/upstream-profiles/github.com--gooyoung--pi-langfuse.md`
- Modify if marker/hash expectations require it: `scripts/verify-pi-langfuse-package-patch.sh`
- Modify tests if marker/hash expectations require it: `tests/test_package_patches.py`

**Steps:**
1. Review fork diff and verification from Task 2.
2. Obtain separate approval for one exact fast-forward push of the named fork commit to maintained vendor branch; no force, PR, tag, release, merge, or publication.
3. After verified remote equality, advance the gitlink and regenerate the smallest exact npm-base patch containing production/package files only.
4. Update profile commit/hash evidence and marker checks; do not hand-edit installed `~/.pi`.
5. Prove patch apply/reverse and exact package projection.

**Focused verification:**
```bash
scripts/verify-pi-langfuse-package-patch.sh
.venv/bin/python -m pytest tests/test_package_patches.py tests/test_update_pi_config.py tests/test_pi_packages.py
```

**Expected result:** Fresh exact npm source receives explicit-zero behavior through the tracked, reversible package patch.

### Task 6: Replay fixed evidence cases [Depends on: Tasks 1, 4, 5]

**Context:** Do not create a scoring subsystem. Reuse the four fixed historical case shapes and score them with the existing 0/1/2 rubric after deterministic fixtures pass. Live proof is optional until separately approved deployment.

**Replay cases:**
1. Linked successful root with no delegation.
2. Mixed-model delegated review containing one non-excellent quality outcome.
3. Delegated run with a bounded time-limit termination.
4. Unlinked session with unknown final outcome.

**Steps:**
1. Freeze expected evidence for each case before viewing post-change scores.
2. Score Proof: available or unavailable outcome/linkage must carry source, reason, integrity, and packet EvidenceRef to earn `2`.
3. Score delegated attribution only for cases 2 and 3. Each must have exact or explicit-unavailable route/model/mode/thinking/contract/timing/score linkage to earn `2`.
4. Require Proof 8/8, delegated attribution 4/4, and 100% complete-or-explicit-unavailable newly generated delegated projections.
5. If deterministic fixtures pass but no deployed cohort exists, label result `synthetic`; do not claim live validation.
6. A live post-deployment bounded scan requires separate local-live deployment approval and must retain raw evidence privately.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py tests/test_subagent_workaround.py
```

**Expected result:** Fixed cases meet stated targets without converting missing evidence into success or scoring non-applicable delegation.

### Task 7: Documentation, full verification, and closeout [Depends on: Tasks 1–6]

**Context:** Align user workflow and privacy claims after implementation stabilizes. Implementation does not imply deployment, push beyond the separately approved fork action, or autonomous promotion.

**Files:**
- Modify as needed: `docs/SELF-IMPROVEMENT.md`
- Modify as needed: `pi/agent/bin/README.md`
- All task-owned files above

**Steps:**
1. Document 16-ref finding cap, explicit-zero usage semantics, worker versus capture timing, attribution status, and replay targets.
2. State retained non-changes: source metadata off by default, 500-trace cap, observe-only authority, one attempt, no scheduler/new store.
3. Run focused matrices, fork full tests, package proof, and full project gate once on stable candidate.
4. Request read-only review focused on privacy, schema compatibility, missing-versus-zero semantics, and attribution spoofing; verify findings against source/tests.
5. Inspect/stage only task-owned paths, commit atomically per Bead boundaries, and use normal direct closeout. Do not deploy unless separately approved.

**Focused verification:**
```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

**Expected result:** All gates pass; docs describe exact evidence semantics; no runtime deployment or unauthorized external effect occurred.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `tests/test_improvement.py` | 1, 4, 6 | Run serially; Task 4 depends on Task 1 fixtures, Task 6 verifies stable behavior. |
| `docs/SELF-IMPROVEMENT.md` | 4, 7 | Task 7 performs final wording pass after Task 4 semantics stabilize. |
| `forks/pi-langfuse` | 2, 5 | Task 2 owns fork source commit; Task 5 owns publication proof, gitlink, and package projection. |

## Explicit Non-Goals

- No general root-tool identity or necessity capture in this change.
- No automatic source revision capture or `LANGFUSE_CAPTURE_SOURCE_METADATA` enablement.
- No scan-cap increase, scheduler, daemon, retry, new registry, or new telemetry backend.
- No raw prompts, outputs, tool I/O, score comments, repository identity, or absolute paths in tracked/public artifacts.
- No model/routing policy change based only on this evidence repair.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-18-work-learning-proof-attribution-design-plan.md`.
Recommended next skills: `test-driven-development` for each behavior-changing Bead; `verification-before-completion` before commits/closeout. Fork push and local-live deployment require separate exact approvals.
