# Langfuse Continuous Improvement Design and Implementation Plan

**Issue:** None — create a Bead before implementation begins
**Design:** Combined design and implementation plan from 2026-07-27 brainstorming
**Date:** 2026-07-27
**Branch:** main

**Goal:** Replace the unused lessons transport with a privacy-preserving Langfuse review loop that detects improvement candidates, marks sessions reviewed, and promotes only sanitized, human-approved work into Beads.

**Architecture:** Langfuse remains private telemetry and evidence storage. A small `agnt improve` command reads bounded Langfuse cohorts, joins runner sessions to runtime run/work-item context, writes private review packets under `~/.pi/improvement/`, and records idempotent session-review scores in Langfuse. Beads remains the committed public work graph: it receives only allowlisted, generalized improvement descriptions after human review; the private Langfuse score stores the Bead ID for reverse lookup. Git remains the source of truth for prompts, tools, evaluators, and regression tests.

**Acceptance Criteria:**
- [ ] `agnt improve scan` discovers eligible unreviewed sessions using bounded, paginated Langfuse APIs and writes private runtime reports, not repository artifacts.
- [ ] Review packets distinguish expected probes/test failures, recovered errors, wasted retries, outcome-blocking failures, infrastructure failures, and telemetry defects.
- [ ] Reports include model, fresh-input/cache/output tokens, cost, turns, tool-error signals, prompt/tool payload sizes, prompt fingerprint, evaluator outcomes, and work-item/run correlation when available.
- [ ] Reviewed sessions receive an idempotent Langfuse session score; repeated scans skip the same review-policy version unless explicitly rechecked.
- [ ] Public Bead previews use an allowlist schema and contain no Langfuse URLs/IDs, session/trace/observation IDs, excerpts, user content, absolute paths, secrets, or private runtime metadata.
- [ ] No improvement Bead is created without explicit human approval of the exact public preview.
- [ ] After approved creation, private Langfuse score metadata records the public Bead ID; private evidence never flows into Beads.
- [ ] Maintenance cadence uses eligible unreviewed Langfuse sessions and a generic `maintenance:improvement-review` checkpoint without exposing private evidence.
- [ ] Existing `agnt lessons`, lesson server code, and lesson documentation are retired only after the replacement passes focused and project verification.
- [ ] Prompt/tool/metric changes remain separate approved Beads with tracked evals; this system never edits policy automatically.
- [ ] Promoted findings enter private post-change monitoring; matched later cohorts mark them validated, pending, or recurrent without copying private evidence into Beads.

**Verification Command(s):**
```bash
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/test_improvement.py tests/test_langfuse_evaluators.py tests/test_maintenance.py tests/test_update_pi_config.py
.venv/bin/python -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt langfuse check --quiet
pi/agent/bin/agnt improve scan --dry-run --limit 5 --json >/tmp/agnt-improve-scan.json
python3 -m json.tool /tmp/agnt-improve-scan.json >/dev/null
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

## Scope

### In scope

1. Read current self-hosted Langfuse through supported legacy observations/traces APIs; do not require Langfuse v4 write mode.
2. Group observations by Pi session and bounded review cohort.
3. Correlate runner-created sessions with `.pi/runs` and Bead IDs using existing `run-<id>` session conventions.
4. Extract deterministic review signals before any model judgment.
5. Produce model-ready private review packets and validate reviewer decisions against a tracked schema/rubric.
6. Record reviewed/no-action/actions/needs-human/excluded status as private Langfuse session scores.
7. Generate public-safe Bead previews and require explicit human approval before creation.
8. Replace `maintenance:lessons-harvest` creation with privacy-safe `maintenance:improvement-review` cadence.
9. Retire unused lesson client/server after replacement verification.
10. Bootstrap calibration using a diverse human-reviewed sample before enabling recurring model-assisted review.

### Out of scope

- No automatic prompt, skill, role, routing, evaluator, or code edits.
- No automatic Bead creation from raw telemetry or model output.
- No raw Langfuse links, identifiers, excerpts, or evidence in Beads, tracked plans/docs, commit messages, or GitHub.
- No migration of prompt source-of-truth into Langfuse prompt management.
- No Langfuse dashboard/UI work.
- No Langfuse v4 upgrade or write-mode migration.
- No retrofit or fork of `pi-langfuse` unless correlation coverage proves insufficient after MVP.
- No retrospective assignment of work-item IDs to unlinked interactive sessions.
- No automatic transfer of private telemetry to a different external model provider; model-assisted review requires an approved local/self-hosted or explicitly authorized provider.
- No remote lesson-server shutdown, data deletion, DNS change, or deployment removal without separate explicit approval.

## Privacy and data-boundary invariants

Beads and `.beads/issues.jsonl` are committed artifacts and must be treated as public GitHub content.

| Store | Allowed | Forbidden |
|---|---|---|
| Langfuse | Session/trace/observation IDs, prompts, outputs, tool details, reviewer evidence, finding IDs, Bead IDs | Secrets beyond existing capture policy |
| `~/.pi/improvement/` | Private scan packets, review decisions, local correlation cache | Git tracking or deployment from `pi/` |
| Beads/Git | Generalized category, public-safe aggregate, tracked relative paths, proposed change, acceptance criteria | Langfuse URLs/IDs, excerpts, user text, absolute paths, private repo metadata, secrets |

Traceability direction:

```text
public Bead ID -> private Langfuse score metadata -> private sessions/traces
```

Beads do not store reverse pointers. Public promotion uses a strict field allowlist plus human semantic review; regex redaction alone is insufficient. If safety cannot be established, mark `needs-human` and create no Bead.

## Review model

### Session review states

Use one categorical Langfuse session score, working name `improvement_review_status`:

```json
{
  "value": "no-action|actions-created|needs-human|excluded",
  "metadata": {
    "schemaVersion": 1,
    "reviewPolicyVersion": "v1",
    "reviewedAt": "UTC timestamp",
    "findingIds": ["private-random-id"],
    "beadIds": ["pi-123"]
  }
}
```

Generate score identity deterministically from session ID and review-policy version. Prompt-bundle hash is evidence, not part of skip identity. Re-review requires an explicit `--recheck` or a new review-policy version.

Private finding lifecycle:

```text
detected -> reviewed -> promoted -> implemented -> monitoring -> validated|recurrent
```

The scanner derives implementation state from the linked public Bead and compares only matched post-change cohorts. Insufficient data remains `monitoring`; recurrence produces a new public-safe preview requiring human approval.

### Finding taxonomy

- `telemetry-defect`: metric/evaluator false positive, blind spot, missing correlation, or capture defect.
- `prompt-coordination`: conflicting, misplaced, duplicated, or missing instruction across prompt layers.
- `agent-mistake`: repeated behavioral failure attributable to agent behavior rather than infrastructure.
- `efficiency`: unnecessary turns, retries, uncached input, oversized prompt/tool payload, or avoidable cost.
- `work-item-retro`: acceptance, planning, verification, handoff, blocker, or closeout issue across one Bead.
- `model-specific`: confirmed failure signature isolated to a matched model/task/prompt cohort.

Error relevance classes:

- `expected-probe`
- `expected-test-failure`
- `recovered`
- `wasted-retry`
- `outcome-blocking`
- `infrastructure-failure`
- `telemetry-defect`

Raw `tool_is_error`, `total_tool_errors`, or nonzero exit status remains operational telemetry, never sufficient evidence of an agent mistake.

### Promotion thresholds

Create a public preview only when one condition holds:

- three confirmed instances across at least two independent work items;
- one confirmed high-severity/outcome-blocking defect;
- one systematic telemetry defect that materially distorts monitoring.

Model-specific prompt proposals additionally require matched task/risk/prompt cohorts and a tracked regression case. Unknown, infrastructure, and expected failures do not count as negative model outcomes.

## Command surface

Working command shape; keep final CLI no larger unless implementation proves a missing operation:

```bash
agnt improve scan [--since ISO] [--limit N] [--recheck] [--dry-run] [--json]
agnt improve review REPORT DECISIONS [--apply]
agnt improve promote REPORT --finding ID [--apply]
```

- `scan`: read Langfuse, normalize sessions, join runtime context, and write a private packet. No remote or Beads mutation.
- `review`: validate reviewer decisions. Default previews score writes; `--apply` writes private Langfuse review markers.
- `promote`: default prints exact public-safe Bead preview; `--apply` creates that Bead only after human approval, then writes its ID into private Langfuse metadata.

Do not add a second database, daemon, queue, or web service.

## Task Plan

### Task 0: Create implementation Bead and confirm API compatibility [Manual prerequisite]

**Context:** Code-changing work requires a Bead. Current self-hosted Langfuse rejects observations v2, so implementation must verify exact legacy read and session-score write contracts before coding around assumptions. Bead title/description must itself satisfy the public-safe policy.

**Files:**
- No tracked edits.
- Reference: this plan.

**Steps:**
1. Create one sanitized implementation Bead referencing this plan; do not include chat excerpts, Langfuse IDs, counts tied to private sessions, or URLs.
2. Inspect it with `bd show <id>` before edits.
3. Verify current instance supports bounded trace/legacy-observation reads and session score creation/update.
4. Record only endpoint capabilities—not credentials, payloads, IDs, or private examples—in implementation notes.
5. Stop and revise this plan if session-level reviewed markers cannot be stored in Langfuse.

**Focused verification:**
```bash
bd show <id>
pi/agent/bin/agnt langfuse check --quiet
```

**Expected result:** Public-safe implementation Bead exists; supported API paths and score behavior are known without exposing telemetry.

### Task 1: Extend Langfuse client for bounded telemetry and scores [Depends on: Task 0]

**Context:** `pi/agent/bin/agnt_lib/langfuse.py` currently manages evaluator configuration only. Reuse its stdlib `urllib` client and credential resolution; do not add a dependency or a second credential loader.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/langfuse.py`
- Create: `tests/test_improvement.py`
- Modify: `tests/test_langfuse_evaluators.py` only for shared client behavior

**Steps:**
1. Write failing tests for pagination, bounded time filters, HTTP errors, malformed responses, and redacted error output.
2. Add narrow client methods for traces, legacy observations, scores, and session-score writes using API paths verified in Task 0.
3. Normalize pagination behind iterators/functions; callers must supply bounds or limits.
4. Preserve existing evaluator sync behavior and startup checks.
5. Never log authorization headers, credentials, response bodies, or telemetry content on transport errors.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_langfuse_evaluators.py tests/test_improvement.py -q -k 'client or pagination or score'
```

**Expected result:** Mocked API tests cover bounded reads and idempotent score writes; evaluator sync remains unchanged.

### Task 2: Add private improvement runtime and deterministic scan [Depends on: Task 1]

**Context:** Private reports must never enter the repository. Default storage is `~/.pi/improvement/`, overrideable with `AGNT_IMPROVEMENT_DIR`; directory mode should be `0700` and report files `0600` where supported.

**Files:**
- Create: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `pi/agent/bin/agnt`
- Modify: `scripts/update-pi-config.sh`
- Modify: `.gitignore`
- Modify: `pi/.gitignore`
- Test: `tests/test_improvement.py`
- Modify: `tests/test_update_pi_config.py`

**Steps:**
1. Write failing tests for default/override paths, atomic writes, restrictive permissions, and no repository output.
2. Add `agnt improve scan` CLI wiring.
3. Query eligible sessions within explicit time/row bounds and skip matching review-policy scores.
4. Group traces/observations by session; retain private identifiers only in private reports.
5. Extract deterministic features: final outcome, tool call/error counts, repeated error signatures, turns, latency, fresh input/cache/output tokens, cost, instruction/tool/input sizes, model, prompt hash, evaluator scores/timeouts, and capture gaps.
6. Join runner sessions to existing `.pi/runs` using `run-<id>`/run-bundle data; mark unmatched sessions `unlinked` rather than guessing.
7. Write only aggregate counts/status to stdout; private payload goes to runtime report.
8. Exclude live `~/.pi/improvement/` from config deployment/rsync deletion.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py tests/test_update_pi_config.py -q -k 'scan or runtime or permission or join'
AGNT_IMPROVEMENT_DIR=/tmp/agnt-improvement-test pi/agent/bin/agnt improve scan --dry-run --limit 1 --json >/tmp/agnt-improve-scan.json
python3 -m json.tool /tmp/agnt-improve-scan.json >/dev/null
```

**Expected result:** Scan is bounded/read-only, reports private path plus safe counts, and writes no telemetry into Git-managed paths.

### Task 3: Add tracked review rubric and validated decision schema [Depends on: Task 2]

**Context:** Deterministic signals select candidates; they do not establish causality. A reviewer may classify candidates using a tracked rubric, but automatic transfer to a new external provider is prohibited. Initial operation should use human review or an approved local/self-hosted reviewer.

**Files:**
- Create: `pi/agent/langfuse/improvement-review.md`
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_improvement.py`
- Possibly modify: `pi/agent/tasks/research.md` only if routing policy needs an approved local reviewer target

**Steps:**
1. Define required reviewer JSON: session decision, finding category, error relevance, impact, attribution, confidence, evidence references internal to the private packet, and proposed intervention type.
2. Require `unknown` when evidence is insufficient; reviewer confidence is not proof.
3. Encode promotion thresholds and matched-cohort requirements in the rubric.
4. Add decision validation that rejects unknown fields, copied excerpts in public-summary fields, missing evidence references, unsupported categories, and malformed IDs.
5. Add `agnt improve review` preview behavior; default performs no score write.
6. Keep model execution outside the deterministic parser. Reviewer invocation must be explicit and provider-authorized.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py -q -k 'review or decision or rubric'
pi/agent/bin/agnt action validate
```

**Expected result:** Reviewer output is schema-validated and cannot directly mutate Langfuse, Beads, or tracked policy.

### Task 4: Add idempotent private reviewed-session markers [Depends on: Task 3]

**Context:** Reviewed state belongs beside private telemetry. Applying a review writes Langfuse scores only; it does not create Beads.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Modify: `pi/agent/bin/agnt_lib/langfuse.py`
- Test: `tests/test_improvement.py`

**Steps:**
1. Write failing tests for deterministic score IDs, repeated apply, mixed reviewed/unreviewed sessions, and explicit recheck.
2. Implement `agnt improve review REPORT DECISIONS --apply`.
3. Store review status, policy version, timestamp, private finding IDs, and later Bead IDs in score metadata.
4. Treat score-write failure as incomplete review; preserve private report/decisions for retry.
5. Never print score/session/trace IDs in normal command output.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py -q -k 'marker or idempotent or recheck'
```

**Expected result:** Applied sessions are skipped on repeat scans for the same policy version; failed writes remain retryable.

### Task 5: Add public-safe Bead preview and human-gated promotion [Depends on: Task 4]

**Context:** Beads are committed and public. Model-produced summaries and best-effort redaction are insufficient. Promotion must construct a new description from an allowlist, validate it, show the exact public text, and require explicit human approval before `bd create`.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_improvement.py`

**Steps:**
1. Define public fields: generalized title, category, affected tracked relative paths, sanitized aggregate, proposed intervention, acceptance criteria, and evaluation requirement.
2. Reject URLs, Langfuse/session/trace/observation terminology with identifiers, UUID-like private references, absolute/home paths, emails, secrets, copied excerpts, and non-allowlisted metadata.
3. Write tests with malicious/private fixtures proving unsafe previews cannot be applied.
4. Make `agnt improve promote` preview-only by default.
5. Require explicit approval of exact preview before `--apply`; do not let scheduled maintenance invoke promotion apply.
6. Create/update a Bead through existing Beads wrappers and deduplicate only through private finding state, not a private fingerprint committed to Beads.
7. After creation, update private Langfuse score metadata with Bead ID. If writeback fails, report private-link repair needed without changing public Bead text.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py -q -k 'public or privacy or promote or bead'
```

**Expected result:** Public specs are minimal and safe; no Bead mutation occurs without explicit approved apply.

### Task 6: Add post-change monitoring and replace lessons-harvest maintenance mode [Depends on: Tasks 2 and 5]

**Context:** Reuse existing maintenance cadence and runner. New maintenance Beads remain generic public checkpoints; private reports and findings stay in Langfuse/runtime. Linked closed improvement Beads also define post-change monitoring windows so the loop can detect validation or recurrence without exposing evidence.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/maintenance.py`
- Modify: `pi/agent/bin/agnt_lib/runner_scheduler.py` only if provider injection/report handling changes
- Modify: `tests/test_maintenance.py`
- Modify: `tests/test_runner_scheduler.py` only if scheduler contract changes

**Steps:**
1. Add `improvement-review` / `maintenance:improvement-review` configuration.
2. Preserve historical recognition of closed `maintenance:lessons-harvest` labels without creating new ones.
3. Replace all-time recorded-session threshold with eligible unreviewed Langfuse-session count; inject/query provider so unit tests remain network-free.
4. On Langfuse failure, emit warning and do not claim maintenance is not due.
5. For linked implemented/closed Beads, compare matched task/model/prompt cohorts after the implementation boundary; mark private finding state `monitoring`, `validated`, or `recurrent`.
6. Never infer success from absence of samples; require a configured minimum matched cohort and report insufficient data as pending.
7. Route recurrent findings back through the same public-safe preview and human promotion gate; never reopen/create Beads automatically.
8. Generate generic public maintenance description and acceptance text with no telemetry identifiers, excerpts, private paths, or findings.
9. Allow runner to auto-create/run only private review checkpoints. Promotion remains human-gated outside scheduled execution.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_maintenance.py tests/test_runner_scheduler.py -q -k 'improvement or maintenance'
pi/agent/bin/agnt work maintenance due --json >/tmp/agnt-maintenance-due.json
python3 -m json.tool /tmp/agnt-maintenance-due.json >/dev/null
```

**Expected result:** Cadence reflects unreviewed private telemetry and produces only public-safe generic maintenance work.

### Task 7: Calibrate taxonomy before recurring model-assisted review [Depends on: Tasks 3-6]

**Context:** Current raw error metrics mix expected tests/probes, recovered errors, infrastructure failures, and real mistakes. Automation must be calibrated against a diverse human-reviewed sample before its findings drive recurring work.

**Files:**
- Modify: `pi/agent/langfuse/improvement-review.md` only for evidence-backed rubric changes
- Modify/add: `pi/agent/evals/*` for durable sanitized regression cases
- Modify: `pi/agent/langfuse/evaluators.json` only if calibration supports an evaluator change
- Test: `tests/test_langfuse_evaluators.py` and relevant deterministic evals

**Steps:**
1. With explicit remote-review approval, select 30-50 diverse private sessions: errors, high-token sessions, weak outcomes, successful controls, multiple models, and linked/unlinked work.
2. Human-label without forcing the proposed taxonomy; cluster observed failure classes afterward.
3. Measure false positives/negatives for error relevance and actionable-finding detection.
4. Adjust rubric and thresholds using generalized results only; do not commit raw examples.
5. Convert confirmed, sanitizable failure patterns into tracked synthetic/regression eval cases.
6. Enable recurring model-assisted review only when review quality is acceptable; otherwise keep deterministic scan plus human review.

**Focused verification:**
```bash
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
.venv/bin/python -m pytest tests/test_langfuse_evaluators.py -q
```

**Expected result:** Recurring review rests on human calibration and durable sanitized evals, not judge confidence alone.

### Task 8: Retire lessons client/server after replacement soak [Depends on: Tasks 1-7]

**Context:** Remove duplicate, unused lesson transport only after `agnt improve` passes a bounded production scan, reviewed-marker apply, public-preview privacy test, and maintenance dry run. Preserve private historical data; remote decommission is separate.

**Files:**
- Delete: `pi/agent/bin/agnt_lib/lessons.py`
- Delete: `tests/test_lessons.py`
- Delete: `tests/test_lesson_server.py`
- Delete: tracked files under `lesson-server/`
- Modify: `pi/agent/bin/agnt`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/skills/retrospective/SKILL.md`
- Modify: `README.md`
- Modify: `.gitignore`

**Steps:**
1. Verify replacement soak and privacy acceptance criteria.
2. Count local/remote legacy records without printing contents. Preserve any non-smoke private records outside Git; do not upload or copy them into Beads.
3. Remove `agnt lessons` import, command help, handler, module, and tests.
4. Remove tracked lesson-server source and README references.
5. Remove stale retrospective/agent instructions that tell agents to capture lessons manually.
6. Keep remote server, database, DNS, and data untouched pending separate explicit decommission approval.
7. Confirm no deployed/startup scripts still reference lesson configuration.

**Focused verification:**
```bash
! rg -n 'agnt lessons|AGNT_LESSONS|pi-lessons|lesson-server' README.md docs pi/agent scripts tests --glob '!*.jsonl'
.venv/bin/python -m pytest tests/ -q
scripts/check-pi-config.sh
```

**Expected result:** Repository has one improvement path; no remote service or private data is deleted.

### Task 9: Align documentation and deployment policy [Depends on: Task 8]

**Context:** Document privacy boundary, command lifecycle, calibration requirements, and Git-vs-runtime ownership without adding bulky operational policy to default agent context.

**Files:**
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `docs/SELF-IMPROVEMENT-PRINCIPLES.md`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/agent/AGENTS.md` only for compact always-applicable guidance
- Modify: `README.md`

**Steps:**
1. Document Langfuse as private evidence, `~/.pi/improvement/` as private runtime, Beads as committed/public, and Git as policy/eval source-of-truth.
2. Document scan/review/promote commands and mutation boundaries.
3. Document work-item correlation limits for unlinked interactive sessions.
4. Document cache-aware token metrics and matched-cohort model comparisons.
5. Document that telemetry can propose monitoring-metric defects; evaluator/prompt changes still require Beads, tracked evals, approval, and verification.
6. Document provider authorization requirement for model-assisted private review.
7. Run context and docs checks.

**Focused verification:**
```bash
scripts/check-pi-config.sh
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt action validate
.venv/bin/python -m pytest tests/
```

**Expected result:** Documentation matches implemented ownership and privacy boundaries without exposing private examples.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt_lib/langfuse.py` | Tasks 1, 4 | Task 4 depends on Task 1; keep API transport separate from review policy. |
| `pi/agent/bin/agnt_lib/improvement.py` | Tasks 2-5 | Execute serially with focused commits/tests. Do not parallel-edit. |
| `pi/agent/bin/agnt` | Tasks 2, 8 | Add `improve` first; remove `lessons` only after soak. |
| `pi/agent/bin/README.md` | Tasks 8, 9 | Remove legacy references in Task 8; perform final command-reference pass in Task 9. |
| `tests/test_improvement.py` | Tasks 1-5 | Execute serially; keep fixtures synthetic and private-data-free. |
| `pi/agent/bin/agnt_lib/maintenance.py` | Task 6 | Single owner; historical label compatibility tested before legacy removal. |

## Rollout and stop conditions

Rollout order:

1. Read-only scan against at most five recent sessions.
2. Private human inspection of report shape.
3. Apply one `no-action` reviewed marker and verify idempotency.
4. Produce public Bead preview from a synthetic fixture and run privacy tests.
5. Produce one real preview; require human approval before creation.
6. Run maintenance due/create dry run.
7. Calibrate 30-50 sessions.
8. Enable recurring review.
9. Validate one promoted synthetic finding through a matched post-change cohort; verify pending and recurrent paths.
10. Retire lessons transport after soak.

Stop before continuing if:

- no implementation Bead exists;
- public preview contains any private identifier, excerpt, URL, or absolute path;
- Langfuse session scores cannot provide an idempotent reviewed marker;
- bounded API reads cannot be guaranteed;
- scan/report writes anywhere under tracked repository paths;
- model-assisted review would send private telemetry to an unapproved provider;
- current `privacyPreset=conversations` capture of full provider payload is not accepted or corrected;
- unrelated working-tree changes appear;
- remote lesson decommission or data deletion becomes necessary without explicit approval.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-27-langfuse-continuous-improvement-design-plan.md`.

Before implementation: create/inspect a public-safe Bead and confirm API compatibility. Recommended next skills: `executing-plans`, `test-driven-development`, and `verification-before-completion`. Use `documentation-standards` for final docs validation. Do not begin implementation from this planning request alone.
