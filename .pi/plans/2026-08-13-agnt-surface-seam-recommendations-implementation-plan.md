# agnt Surface-Seam Recommendations Implementation Plan

**Issues:** `pi-mal2` → `pi-wx1v` → `pi-kh85` → `pi-z49l` → `pi-fvyo`
**Design:** `.pi/plans/2026-08-13-agnt-surface-seam-audit-results.md`
**Date:** 2026-08-13
**Branch:** `main` (direct-work default; one Bead and fresh Pi session per slice)

**Goal:** Implement all five accepted audit follow-ups while deleting duplicate surface area, preserving headless/CI and safety boundaries, and keeping unpinned package sources intentionally rolling.

**Architecture:** Keep deterministic behavior in `pi/agent/bin/agnt_lib`, CLI entrypoints as human/CI/headless adapters, and Pi extensions as lifecycle/UI/session adapters. Add no typed tools, dependencies, TypeScript copies of Python policy, background services, or speculative abstractions. Implement behavior/interface changes before compacting always-loaded instructions so final guidance is written once against final CLI behavior.

**Acceptance Criteria:**
- [ ] `pi/agent/AGENTS.md` is at most 44 lines and 7,500 characters including one trailing LF, reducing audited global instruction characters by at least 30% and global-plus-project characters by at least 20%, while all audited safety gates remain explicit.
- [ ] `agnt review validate` remains canonical and still emits validation plus summary; `agnt review summary` is absent from parser, workflow skill, tests, and command docs.
- [ ] `agnt work next` is absent from parser, tests, and command docs; shared `select_next_ready` behavior remains for default Bead selection.
- [ ] `agnt work direct-closeout BEAD --outcome success --reason REASON` requires literal explicit `success`, records that value through existing improvement domain logic, reads it back before Git/Beads closeout, and never infers or defaults success.
- [ ] Missing, `partial`, `failure`, and `unclear` direct-closeout outcomes fail before Git or Beads mutation; existing handoff checks continue rejecting non-success outcomes.
- [ ] `agnt improve outcome` remains available for non-success and manual/repair recording.
- [ ] Compatibility docs mark every unpinned configured package source as intentionally rolling and label exact versions/commits as dated observations; `pi/agent/settings.json` remains unpinned and unchanged.
- [ ] No rejected audit follow-up is implemented: no `route_and_subagent`, typed work mutation, runtime-path/provider-circuit tool, TypeScript domain copy, or length-only module split.
- [ ] Every implementation slice records RED/GREEN evidence, receives active Ponytail guidance and a final Ponytail diff review, passes focused tests, and closes through its own approved Bead.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
git diff --cached --check
```

---

## Approval, Bead, and execution boundaries

Planning does not authorize implementation. Before each task below:

1. Obtain explicit approval for that exact slice; public command deletion and always-loaded instruction replacement must not inherit approval from another slice.
2. Select the corresponding Bead above, then run `bd prime`, `bd ready`, `bd show <id>`, and `agnt work direct-start <id> [--claim]` before edits.
3. Keep one logical Pi session on one Bead. Do not parallelize Tasks 2–5: they share `pi/agent/bin/README.md`, `tests/test_agnt.py`, `tests/test_context_architecture.py`, `pi/agent/bin/agnt_lib/work.py`, or `pi/agent/AGENTS.md`.
4. Preserve unrelated working-tree state. Current planning baseline includes a user-owned unstaged decision in `.pi/plans/2026-08-13-agnt-surface-seam-audit-results.md`; never stage or overwrite it as part of an implementation slice unless ownership is explicitly expanded.
5. Commit only task-owned files after fresh verification. Close each Bead before starting the next.

Closeout command changes during this plan:

- Before Task 4 lands: `agnt improve outcome <id> success`, then `agnt work direct-closeout <id> --reason "<reason>"`.
- After Task 4 lands: `agnt work direct-closeout <id> --outcome success --reason "<reason>"`; use `agnt improve outcome` separately only for non-success or manual/repair recording.

## Mandatory Ponytail implementation contract

At start of every implementation session, activate `/ponytail full`; if host does not inject canonical body, invoke `/skill:ponytail`. Keep it active through all detailed work.

For each task:

1. Read complete affected flow and grep every caller before editing.
2. Apply Ponytail ladder in order: delete need, reuse repository behavior, stdlib/native, installed dependency, one line, then minimum new code.
3. Prefer deletion and direct reuse. Add no helper unless two real callers or one safety boundary already justify it.
4. Never simplify away outcome validation, ownership checks, bounded retries, parity/export checks, Git staging isolation, approval semantics, or error handling that prevents data loss.
5. After focused GREEN, invoke `/ponytail-review` against task-owned diff. Apply valid `delete`, `stdlib`, `native`, `yagni`, or `shrink` findings; rerun focused checks. Record `Lean already. Ship.` when nothing can be cut.
6. Add a `ponytail:` ceiling comment only if implementation deliberately accepts a real known limitation. Do not add comments for ordinary straightforward code.

## Baseline once per slice

Record current status and focused baseline before changing files:

```bash
git status --short --untracked-files=all
git diff --stat
git diff --cached --stat
```

Run task-specific focused tests listed below once. Record exact command, exit code, and any existing failure signature. Do not repeatedly rerun unchanged broad baseline during repair.

### Task 1: Document intentional rolling package policy [Independent]

**Context:** User selected rolling releases for unpinned configured packages. Current compatibility matrix mixes pinned versions with stale unpinned snapshots and can read as a version guarantee. Clarify policy without changing package settings or adding pinning machinery.

**Files:**
- Modify: `docs/extension-web-compatibility.md`
- Modify: `tests/test_agent_os_compat.py`
- Read only: `pi/agent/settings.json`
- Source evidence: `.pi/plans/2026-08-13-agnt-surface-seam-audit-results.md`

**Ponytail target:** Documentation plus one extension of existing matrix-coverage test. No config change, package resolver, lockfile logic, or new test helper.

**Steps:**
1. Extend `test_compatibility_matrix_covers_every_configured_package` first so each unpinned source (`git:github.com/langfuse/skills`, `git:github.com/mattpocock/skills`, `git:github.com/DietrichGebert/ponytail`, `npm:pi-caveman`, `npm:betterwright`) must have a row explicitly marked rolling/intentional. Keep assertion small and table-oriented.
2. Run focused test and confirm RED because current rows do not state one consistent rolling policy.
3. Rename matrix version column to distinguish policy from observed evidence. Keep exact versions for pinned sources; mark unpinned sources `Rolling` and label exact observed versions/commits as snapshots dated 2026-08-13 where useful.
4. Use audit observations for stale rows: Ponytail `2ed6c52`, Caveman `1.0.8`, BetterWright `1.8.2`. Do not claim those values remain current after updates.
5. State once near matrix that rolling sources may advance under normal package updates and that compatibility claims tied to observations are dated, not pins.
6. Confirm `git diff -- pi/agent/settings.json` is empty.
7. Run focused GREEN, then `/ponytail-review`; apply only doc/test reductions that preserve policy clarity.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agent_os_compat.py::test_compatibility_matrix_covers_every_configured_package
rg -n 'Rolling|rolling|2026-08-13' docs/extension-web-compatibility.md
git diff --exit-code -- pi/agent/settings.json
```

**Expected result:** Every configured source remains covered; all unpinned sources are explicitly intentional rolling inputs; settings remain unchanged.

### Task 2: Remove duplicate `review summary` [Depends on: Task 1 for sequential Bead execution only]

**Context:** `cmd_review` sends both `validate` and `summary` through identical code and output. Review workflow invokes both, paying duplicate command and instruction cost.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/review.py`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/agent/skills/requesting-code-review/SKILL.md`
- Modify: `tests/test_review.py`

**Ponytail target:** Pure deletion. Keep `summarize_review_findings` because `review validate` and metrics use it; remove only duplicate CLI adapter and second workflow invocation.

**Steps:**
1. Update tests first:
   - prove `review validate` still returns `valid` plus `summary`;
   - prove `summary` is not accepted/registered;
   - prove requesting-code-review workflow contains one canonical `agnt review validate` call and no `agnt review summary` call.
2. Keep the workflow-text assertion in `tests/test_review.py`, which already owns review CLI behavior and repository paths; do not widen this slice into context-architecture tests.
3. Run focused tests and confirm RED against duplicate command/workflow.
4. In `cmd_review`, register and accept only `validate`. Do not add aliases, deprecation wrappers, compatibility flags, or a replacement command.
5. Delete `review summary` from command reference and workflow skill. Document that `review validate` emits summary in the same payload.
6. Search active source/docs/tests and require no exact `agnt review summary` occurrence outside historical plans/audit artifacts.
7. Run focused GREEN, then `/ponytail-review`. Best expected review outcome: no replacement code, net line deletion.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_review.py
! rg -n 'agnt review summary' pi/agent/bin/README.md pi/agent/skills/requesting-code-review/SKILL.md tests pi/agent/bin/agnt_lib
```

**Expected result:** One CLI leaf and one model workflow command removed; canonical validation payload unchanged.

### Task 3: Remove shallow `work next` [Depends on: Task 2]

**Context:** `agnt work next` has no executable caller. Direct workflow uses `bd ready`; handoff uses stricter `work handoff-check`. Shared default selection remains needed by `get_bead(None)` for plan/start/run paths.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Modify: `pi/agent/bin/README.md`
- Modify: `tests/test_agnt.py`

**Ponytail target:** Delete parser and dispatch branches only. Reuse existing `select_next_ready`; do not replace it, inline it into every caller, or add a new readiness abstraction.

**Steps:**
1. Replace `test_cmd_work_next_selects_ready_non_epic` with minimal behavior tests written first:
   - `work next` is not registered;
   - `get_bead(None)` still selects first ready non-epic item.
2. Run those tests and confirm absence test is RED while shared-selection test protects retained behavior.
3. Delete `next` parser registration and `args.command == "next"` dispatch block.
4. Keep `select_next_ready` and `get_bead(None)` unchanged unless test evidence requires a smaller correction.
5. Delete command reference entry. Add no deprecation alias because audit found no executable caller.
6. Search active source/docs for command absence and shared helper presence.
7. Run focused GREEN, then `/ponytail-review`; expected net deletion.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py -k 'work_next or get_bead_without_id'
! rg -n 'agnt work next|add_parser\("next"|args\.command == "next"' pi/agent/bin/README.md pi/agent/bin/agnt_lib/work.py
rg -n 'select_next_ready|def get_bead' pi/agent/bin/agnt_lib/work.py
```

**Expected result:** Shallow public command disappears; optional orchestration default selection continues skipping epics.

### Task 4: Deepen explicit-success direct closeout [Depends on: Task 3]

**Context:** Current workflow requires separate success recording before direct closeout, while direct closeout itself accepts any recorded outcome. Move only explicit literal success recording behind direct-closeout. Keep non-success/manual outcome recording separate and preserve all closeout, ownership, telemetry, Beads, and Git safety checks.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/agent/skills/dev-workflow-common/SKILL.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `tests/test_agnt.py`
- Modify: `tests/test_improvement.py`
- Modify: `tests/test_context_architecture.py`

**Ponytail target:** Reuse `record_session_outcome`; add only the same thin current-session wrapper pattern already used by `link_current_session`. No new outcome service, class, typed tool, schema, or duplicated Langfuse/Beads logic.

**Steps:**
1. Write failing tests before production changes:
   - CLI requires `--outcome success`; omission and `partial`, `failure`, `unclear` reject before `direct_closeout` or any mutation;
   - domain `direct_closeout` rejects every non-success value even when called directly;
   - explicit success calls one current-session outcome wrapper before ownership readback and before Git/Beads mutation;
   - outcome-write failure stops before ownership, Git, and Beads work;
   - readback must match same Bead and exact `success` before preflight;
   - existing `test_handoff_check_rejects_non_success_outcome` remains unchanged and green.
2. Run focused tests and confirm expected RED failures come from missing required outcome/deepened recording.
3. In `improvement.py`, add `record_current_session_outcome(bead_id, outcome)` beside `link_current_session`, delegating directly to existing `record_session_outcome(_client_from_env(), session_id=current_session_id(), beads_runner=_beads, ...)`.
4. In `work.py`, import that wrapper. Change domain signature to require `outcome`; reject anything other than literal `success` before side effects.
5. Record explicit success, then call existing bounded `current_session_closeout_source` readback. Require returned Bead and outcome to match request before Git inspection. Keep existing bounded visibility retry, error bounding, dirty-tree rejection, Beads close, export/parity, stage isolation, and portable-state commit unchanged.
6. Add required parser argument `--outcome` with only `success` accepted; pass it to domain function. Do not provide a default.
7. Update every direct call/test. Use `rg -n 'direct_closeout\('` to avoid a sibling path retaining old signature.
8. Update user/operator/workflow docs:
   - normal successful path uses one explicit-success closeout command;
   - `agnt improve outcome` remains for `partial|failure|unclear` and manual/repair use;
   - failed/non-success work stops without closeout or handoff.
9. Run focused GREEN, then `/ponytail-review`. Reject any suggested cut that weakens validation, outcome readback, bounded retries, parity, or staging isolation.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py -k 'direct_closeout or handoff_check_rejects_non_success'
.venv/bin/python -m pytest tests/test_improvement.py -k 'session_outcome or closeout_handoff_source'
.venv/bin/python -m pytest tests/test_context_architecture.py -k 'direct_lifecycle or approved_implementation'
rg -n 'direct-closeout|improve outcome' pi/agent/AGENTS.md pi/agent/bin/README.md pi/agent/skills/dev-workflow-common/SKILL.md docs/AGNT-SYSTEM.md docs/SELF-IMPROVEMENT.md
```

**Expected result:** Successful closeout remains explicit but becomes one command; non-success paths cannot close or hand off; implementation reuses existing improvement logic.

### Task 5: Apply compact always-loaded instructions [Depends on: Tasks 2–4]

**Context:** Audit produced a reviewed 44-line compact target. Apply it only after CLI behavior settles, adapting closeout syntax from Task 4 and preserving every audited safety gate. Root project `AGENTS.md` stays unchanged.

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify: `tests/test_context_architecture.py`
- Modify: `tests/test_model_config.py`
- Read only: `AGENTS.md`
- Source draft/checklist: `.pi/plans/2026-08-13-agnt-surface-seam-audit-results.md` under `## Compact target instruction draft` and `### Measurement and gate retention`

**Ponytail target:** Replace duplicate prose with reviewed compact draft; do not add an overlay, second reference file, generated instruction layer, or test-only copy of whole document.

**Steps:**
1. Write compactness/retention tests first:
   - count with `len(text.splitlines())` and `len(text)` including one trailing LF;
   - require at most 44 lines and 7,500 characters;
   - retain semantic assertions for deterministic domain/adapter seams, doctor stop rule, Bead/session lifecycle, explicit-success closeout, handoff, repository/self-contained delegation, bounded metered OpenRouter use, approvals, Git/integration/deployment/push gates, no-UI fail-closed behavior, concept separation, research sourcing, and context layering.
2. Update existing exact-phrase assertions only where compact wording intentionally changes. Do not delete a safety assertion merely to make target pass; assert stable semantic tokens or short required clauses instead of the old paragraph.
3. Run focused tests and confirm RED on old 103-line/10,739-character file.
4. Extract reviewed draft from audit, replace old successful-closeout sequence with final Task 4 syntax, and replace `pi/agent/AGENTS.md` in one edit. Do not modify project `AGENTS.md`.
5. Measure candidate with one trailing LF. If over limit, remove duplication or syntax examples already present in `pi/agent/bin/README.md`; never trim safety/approval semantics.
6. Validate candidate directly:

```bash
pi/agent/bin/agnt context-health --file pi/agent/AGENTS.md --path pi/agent/AGENTS.md --strict
pi/agent/bin/agnt instructions pi/agent/AGENTS.md --check --no-project
```

7. Run focused GREEN and routing/role evals.
8. Invoke `/ponytail-review`. Apply only reductions that keep retention tests and deterministic checks green.
9. Re-measure final text and record actual global and global-plus-project line/character reductions in Bead notes or exact tracked artifact.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_model_config.py
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
python3 - <<'PY'
from pathlib import Path
for path in (Path('pi/agent/AGENTS.md'), Path('AGENTS.md')):
    text = path.read_text(encoding='utf-8')
    print(path, len(text.splitlines()), len(text))
PY
```

**Expected result:** Smaller always-loaded surface documents final behavior once, all safety/architecture tests pass, and no command reference detail remains duplicated solely for convenience.

## File conflicts and required order

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/README.md` | 2, 3, 4 | Execute sequentially: duplicate review removal, then work-next removal, then closeout syntax. |
| `pi/agent/bin/agnt_lib/work.py` | 3, 4 | Task 4 depends on Task 3; one final parser/dispatch diff. |
| `tests/test_agnt.py` | 3, 4 | Task 4 starts from Task 3's green committed state. |
| `tests/test_context_architecture.py` | 4, 5 | Task 5 starts from Task 4's explicit-success lifecycle assertions and performs final compact wording pass. |
| `pi/agent/AGENTS.md` | 4, 5 | Task 4 changes behavior wording; Task 5 replaces full file against that final behavior. |

Task 1 is file-disjoint but still uses its own Bead/session and approval. Do not use worktrees or parallel agents for implementation: shared-file churn and five small bounded slices make sequential direct work simpler.

## Stable candidate and final gate for each slice

After focused GREEN and Ponytail review:

1. Stage only exact task-owned paths.
2. Inspect:

```bash
git status --short --untracked-files=all
git diff --cached --name-status --find-renames
git diff --cached
git diff
git ls-files --others --exclude-standard
git diff --check
git diff --cached --check
```

3. Confirm no task-owned path remains unstaged and unrelated audit/deployment/runtime artifacts remain excluded.
4. Run full project gate once on stable staged candidate:

```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

5. Any task-owned change after gate invalidates it; restage, refresh affected focused checks, and rerun complete gate.
6. Request read-only review for Task 4 and Task 5. Verify findings against source/tests and annotate reviewer metrics.
7. Commit one atomic task-owned change, record bounded outcome/evidence in Bead, and close using lifecycle command valid at that point in plan.

## Documentation validation

After each public-interface or workflow change, run documentation-standards in validate mode. Required alignment:

- `pi/agent/bin/README.md` — canonical CLI syntax and output.
- `docs/AGNT-SYSTEM.md` — direct lifecycle sequence.
- `docs/SELF-IMPROVEMENT.md` — success vs non-success/manual outcome recording.
- `docs/extension-web-compatibility.md` — rolling package policy and dated evidence.
- `README.md`, `docs/ARCHITECTURE.md`, and subsystem `SPEC.md` — update only if diff exposes a real stale contract; do not add implementation tours.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-13-agnt-surface-seam-recommendations-implementation-plan.md` (verify with `test -f`).

Recommended next skills: `executing-plans`, `test-driven-development`, mandatory active `ponytail` plus `/ponytail-review` per slice, `documentation-standards` for public/docs alignment, and `verification-before-completion` before every commit/closeout.
