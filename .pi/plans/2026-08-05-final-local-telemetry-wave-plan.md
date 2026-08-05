# Final Local Telemetry Wave Implementation Plan

**Issue:** pi-4tg9.36 — Execute final local telemetry wave
**Design:** Beads `pi-4tg9`, `pi-4tg9.36`, decision `pi-bdyu`, and `.pi/plans/2026-08-04-telemetry-agent-waves-1-4-plan.md`
**Date:** 2026-08-05
**Branch:** `main` for plan; serial child worktrees from latest integrated `main`

**Goal:** Finish every supportable local pi-4tg9 item through Wave 4 without upstream or remote changes, and leave irreducible package-owned blockers explicit.

**Architecture:** Execute `.35 → .12 → .13 → .23` serially because telemetry tasks share extension, metrics, improvement, and test files. `.12` uses existing tracked Archimedes composition to add an optional local output-contract envelope while delegating unchanged execution to the captured public subagent tool. After local items close, re-prove `.3/.4` package boundaries; `.14` runs only if those dependencies become locally supportable, otherwise it remains blocked with exact generalized evidence.

**Acceptance Criteria:**
- [ ] `pi-4tg9.35` isolates every deterministic test from operator provider-circuit state while preserving explicit state-path and subprocess integration coverage.
- [ ] `pi-4tg9.12` evaluates bounded delegated output against explicit inline, artifact, status-only, PASS/no-findings, or unknown contracts without exposing raw artifact paths.
- [ ] `pi-4tg9.13` reports deterministic payload-free error class, source, actionable, outcome-blocking, unknown, and raw-health counts without guessing expected failures.
- [ ] `pi-4tg9.23` routes current-session clarification through transient `ask`, handoff/blocking questions through `ticket_question`, and consequential approvals through `ticket_approval`.
- [ ] `.3/.4` receive refreshed supported-seam verdicts; if still irreducible, both are deferred with partial outcomes and `.14` remains visibly blocked rather than bypassed.
- [ ] `.18/.19`, `.31`, and Waves 5–6 remain outside scope.
- [ ] Each implemented child receives focused TDD proof, review, one atomic child commit, serial local integration, and cleanup.
- [ ] One final stable-candidate gate passes. No push, upstream edit, fork, PR, release, pin, vendoring, installed-package edit, remote Langfuse apply, or remote deployment occurs.

**Verification Commands:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
npm ci --ignore-scripts
"$PY" -m ruff check pi/agent/bin/agnt_lib tests
"$PY" -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt eval run question-routing-smoke --models openai-codex/gpt-5.6-luna
pi/agent/bin/agnt action validate
pi/agent/bin/agnt context-health --strict
git diff --check
git status --short --branch
```

---

## Boundaries and baseline

- Current baseline: GitHub Actions deterministic-checks run `30996710831` passed on current `main` commit `15c6f9b`.
- Run one local pre-change baseline after this plan commit. During repair, run focused checks only. Run one full gate for the stable final candidate.
- Use `/Users/hays/Projects/pi-setup/.venv/bin/python` from every worktree; do not create worktree-local environments.
- Use synthetic telemetry only in tracked tests. Private prompts, outputs, IDs, hashes, raw provider errors, credentials, absolute artifact paths, and live packets stay out of Git and Beads. Existing bounded opaque `runtime:` refs remain allowed in tool results and telemetry; evaluator prompts receive status/count only, never refs or filesystem paths.
- `scripts/update-pi-config.sh` currently performs remote `agnt langfuse apply` when credentials exist. Remote deployment is prohibited, so do not run it against `~/.pi` in this wave. Verify deployment against a fresh temporary `PI_CONFIG_DEST` with every Langfuse credential variable explicitly unset, and assert sync was skipped.
- The stale `graphify-out/graph.json` is advisory only; verify every dependency against current source.

## Serial worktree protocol

For each implemented child:

```bash
ROOT=/Users/hays/Projects/pi-setup
BEAD=<bead>
BRANCH=<branch>
WT="$ROOT/.worktrees/$BRANCH"

git -C "$ROOT" status --short --branch
bd show "$BEAD"
~/.pi/agent/bin/agnt work direct-start "$BEAD" --claim
git -C "$ROOT" worktree add "$WT" -b "$BRANCH" main
```

Observe RED before production edits, make smallest GREEN change, run focused checks, inspect diff, review, commit only child-owned files, merge serially into `main`, rerun focused checks on `main`, record `agnt improve outcome`, close child, then remove its worktree and branch. Do not create later worktrees from stale bases.

## Task 1: Isolate deterministic provider-circuit tests — pi-4tg9.35

**Branch/worktree:** `fix/pi-4tg9-35-test-isolation` / `.worktrees/fix/pi-4tg9-35-test-isolation`

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_agnt.py`
- Verify existing integration: `tests/test_provider_circuits.py`, `tests/test_route_feedback.py`

**Steps:**
1. Add a RED contract test asserting `AGNT_PROVIDER_CIRCUIT_DIR` resolves to the current test's private `tmp_path / "provider-circuits"`; run with ambient variable removed.
2. Add one autouse fixture in `tests/conftest.py` that sets that path per test using `monkeypatch` and `tmp_path`.
3. Do not change production routing or provider-circuit code. Explicit `state_path=` tests and tests that set their own environment remain authoritative.
4. Seed an ambient circuit directory in a focused shell check and prove selected routing tests ignore it while provider-circuit integration tests still exercise persisted state.
5. Commit, integrate, close `.35`, then allow `.12/.13/.23` to become ready.

**Focused verification:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
env -u AGNT_PROVIDER_CIRCUIT_DIR "$PY" -m pytest -q tests/test_agnt.py -k per_test_provider_circuit
"$PY" -m pytest -q tests/test_provider_circuits.py tests/test_route_feedback.py
"$PY" -m pytest -q tests/test_agnt.py -k 'route or select_model or start_work_records_policy_selected_model'
```

**Expected:** private fixture contract passes; explicit persistence coverage passes; ambient operator circuits cannot alter routing-unit expectations.

## Task 2: Evaluate delegated artifacts against explicit contracts — pi-4tg9.12

**Depends on:** Task 1, closed `.9`, closed `.11`.

**Branch/worktree:** `fix/pi-4tg9-12-artifact-evaluation` / `.worktrees/fix/pi-4tg9-12-artifact-evaluation`

**Files:**
- Modify: `pi/agent/extensions/archimedes.ts`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Modify: `pi/agent/extensions/lib/runtime-artifacts.ts`
- Modify: `pi/agent/bin/agnt_lib/metrics.py`
- Modify: `pi/agent/langfuse/evaluators.json`
- Test: `tests/test_agent_os_compat.py`
- Test: `tests/test_pi_packages.py`
- Test: `tests/test_subagent_workaround.py`
- Test: `tests/test_agnt.py`
- Test: `tests/test_langfuse_evaluators.py`
- Docs: `docs/RUN-ARTIFACTS.md`, `docs/SELF-IMPROVEMENT.md`, `docs/extension-web-compatibility.md`, `pi/agent/bin/README.md`

**Chosen local seam:** Reuse `archimedes.ts`, which already captures package tool registrations through a public composition proxy. Extend its local `ToolDefinition` shape to retain the complete captured `subagent` definition, including label, description, prompt metadata, renderers, argument preparation, and execute. Register one contract-aware wrapper by spreading that complete definition, replacing only parameters/execute, and strip local-only contract fields before calling captured public execution. Do not copy executor, stream, model validation, rendering, or UI implementation.

**Contract:** Optional `outputContract` on single calls and each parallel task, enum:

```text
inline | artifact | status-only | pass-no-findings
```

Absent contract remains `unknown`; never infer it from prose.

**Steps:**
1. Add RED Node-backed tests proving single and parallel contracts reach `tool_call`/`tool_result` observers while captured public execution receives its unchanged supported arguments and result shape.
2. Thread normalized contract through parent-owned runtime artifact schema 1 as an additive field, schema-2 invocation metrics/compaction, and `subagent-result` metadata. Add round-trip coverage for compact metrics and `unknown` defaults for legacy records.
3. Build a bounded evaluator view from already-available parent result data: task, explicit contract/unknown, artifact persisted/unavailable state, bounded reference count, and at most 12,000 characters of persisted `finalOutput` with a visible truncation marker. Do not reread arbitrary paths or put opaque refs into evaluator prompt input; existing tool/telemetry refs remain unchanged.
4. For failed persistence, emit explicit artifact-unavailable state while preserving inline output and objective execution outcome.
5. Update `Subagent output quality` rubric so requested status-only and PASS/no-findings can be excellent, artifact contracts use available bounded artifact content, and missing required findings or unavailable required artifacts remain poor/weak. Keep execution outcome separate from quality.
6. Keep evaluator manifest schema 1, metric schema 2, and runtime artifact schema 1. Preserve legacy records as `unknown` contract.
7. Do not run `agnt langfuse apply`; tracked evaluator changes remain unapplied remote drift in this local-only wave.

**RED/GREEN verification:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_agent_os_compat.py tests/test_pi_packages.py \
  tests/test_subagent_workaround.py tests/test_agnt.py tests/test_langfuse_evaluators.py \
  -k 'output_contract or artifact_contract or status_only or pass_no_findings or missing_required_output'
"$PY" -m pytest -q tests/test_subagent_workaround.py tests/test_agent_os_compat.py \
  tests/test_pi_packages.py tests/test_agnt.py tests/test_langfuse_evaluators.py
"$PY" -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
git diff --check
```

**Stop condition:** If public tool capture cannot preserve upstream validation/execution/result behavior or Pi does not expose wrapper input to `tool_call`, record concrete synthetic proof and defer `.12`; do not replace Archimedes execution locally.

## Task 3: Add deterministic payload-free error taxonomy — pi-4tg9.13

**Depends on:** Tasks 1–2 and closed `.2/.9`.

**Branch/worktree:** `feature/pi-4tg9-13-error-taxonomy` / `.worktrees/feature/pi-4tg9-13-error-taxonomy`

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`
- Test: `tests/test_improvement.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `pi/agent/bin/README.md`, `pi/agent/langfuse/improvement-review.md`
- Modify producer/metric files only if a RED fixture proves normalized metadata is absent; do not classify from raw error text.

**Taxonomy:**
- Primary class: `expected | recovered | provider | infrastructure | agent | unknown`
- Source: `tool | provider | process | artifact | evaluator | unknown`
- Separate `outcomeBlocking: true | false | unknown`
- Preserve count-only `rawErrorObservationCount`; report `classifiedSignals`, `actionableSignals`, and `unknownSignals` separately.

**Precedence:** explicit safe producer class → recovered fingerprint → provider failure class → timeout/artifact/infrastructure metadata → explicit process/agent failure → unknown. Reuse existing payload-free `failureClass`, `providerFailureClass`, `executionOutcome`, `artifactFailureClass`, and `toolErrorSignals`; do not reclassify provider errors from retained text. Only explicit metadata may classify expected failures. Unknown is never guessed. Expected/recovered do not increase actionable count. Outcome-blocking is set only by explicit metadata or failed root execution, not every failed child/tool.

**Steps:**
1. Add RED synthetic fixtures for every class/source, recovered retry, provider subtype, timeout, artifact failure, agent failure, root outcome block, and unknown.
2. Add one pure classifier/aggregator in `improvement.py` over normalized observation metadata and existing `toolErrorSignals`.
3. Avoid double counting: raw observation errors remain health counts; projected classified signals are a separate denominator.
4. Add `errorTaxonomy` to private schema-2 session features. Do not change review policy version, public review schema, or historical schema-1 compatibility.
5. Assert taxonomy output contains no payload, raw status text, path, URL, session/trace/observation ID, input hash, or error signature.

**Focused verification:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_improvement.py \
  -k 'error_taxonomy or classification_precedence or actionable_signals or outcome_blocking'
"$PY" -m pytest -q tests/test_improvement.py tests/test_subagent_workaround.py tests/test_agnt.py
"$PY" -m ruff check pi/agent/bin/agnt_lib/improvement.py tests/test_improvement.py
git diff --check
```

**Expected:** deterministic synthetic classes pass; expected/recovered stay non-actionable; provider/outcome-blocking remain visible; unknown remains explicit.

## Task 4: Route transient and durable questions — pi-4tg9.23

**Depends on:** Task 1 and closed `.21/.22`.

**Branch/worktree:** `chore/pi-4tg9-23-question-routing` / `.worktrees/chore/pi-4tg9-23-question-routing`

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/extensions/beads-ask-bridge.ts`
- Create: `pi/agent/evals/question-routing-smoke/eval.json`
- Create: `pi/agent/evals/question-routing-smoke/prompt.md`
- Modify: `pi/agent/evals/role-context-smoke/eval.json`
- Test: `tests/test_context_architecture.py`
- Preserve: `tests/test_agent_os_compat.py`, `tests/test_approvals.py`
- Docs: `docs/AGNT-SYSTEM.md`, `docs/extension-web-compatibility.md`

**Steps:**
1. Add RED architecture assertions for exact boundary: transient `ask` for clarification whose answer is only needed in the current session; durable `ticket_question` only when answer must survive handoff or block an identified Bead; `ticket_approval` for consequential approval.
2. Narrow `ticket_question` prompt guidance from “any human preference” to the durable boundary.
3. Require explicit single/multi selection mode and custom typed response availability in both question paths; do not change existing question UI or approval confirmation logic.
4. Add one focused invoke eval with three independent scenarios and exact output lines for ephemeral clarification, durable handoff/blocker, and consequential approval. Include a no-forced-durable-ideation assertion. Treat this model smoke as behavioral evidence, not deterministic proof; architecture tests remain the correctness gate.
5. Extend deterministic role-context smoke so generated worker context contains the boundary. Preserve no-UI behavior: transient `ask` reports cancellation/unavailability, while `ticket_question` creates a durable unresolved blocker without prompting.

**Focused verification:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_context_architecture.py tests/test_agent_os_compat.py tests/test_approvals.py \
  -k 'question or ask or approval'
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt eval run question-routing-smoke --models openai-codex/gpt-5.6-luna
scripts/check-pi-config.sh
git diff --check
```

**Expected:** scenarios choose `ask`, `ticket_question`, and `ticket_approval` correctly; selection/custom behavior and approval safety remain unchanged.

## Task 5: Re-evaluate held package seams — pi-4tg9.3 and pi-4tg9.4

**Depends on:** Tasks 1–4 integrated. **Read-only; no worktree needed unless a supported seam is found.**

**Primary evidence:**
- `pi/agent/extensions/langfuse-config-env.ts`
- `pi/agent/extensions/subagent-error-workaround.ts`
- installed `pi-langfuse@1.5.7` `package.json`, `index.ts`, `src/state.ts`, and `src/langfuse.ts` (read-only)
- `tests/test_langfuse_skill.py`, `tests/test_subagent_workaround.py`

**Required proof:**
1. `.3`: package root must expose a supported per-event/session resolver that accepts canonical session-manager identity, exact `PI_SESSION_ID` fallback, explicit unavailable state, and concurrent isolation without mutable current/default fallback.
2. `.4`: package root must expose a supported bounded worker-local finalization/shutdown promise that can be awaited for short-lived workers without forcing interactive shutdown latency.
3. Private deep imports, monkeypatching, copied tracing, installed edits, or a local replacement tracer do not count.

**Current preliminary verdict to verify:** NO for both. `pi-langfuse@1.5.7` resolves session from `getSessionFile()` then mutable `state.currentSessionId`; package root exports only default registration. `agent_end` defers unawaited `shutdownRuntime(sessionId)` via `setTimeout`, while bounded runtime shutdown is private.

**Closeout if verdict remains NO:**
- Append generalized file/symbol evidence to `.3/.4`.
- Record `agnt improve outcome <id> partial`.
- Mark `.3/.4` deferred as package-owned under the existing no-upstream decision.
- Append `.14` note that it remains blocked by deferred `.3/.4`; do not edit `.14` code or bypass dependency edges.

If a complete supported seam unexpectedly exists, stop and amend this plan before implementation because `.14` scope and final gate change materially.

## Task 6: Final review, temporary deployment proof, and coordination closeout

**Files:** all integrated child changes and aligned docs.

**Steps:**
1. Run one simplification pass after focused verification. Delete duplication; add no abstraction unless required by tests. Any tracked change invalidates prior final-gate evidence.
2. Request bounded code review for `.12/.13` telemetry/privacy behavior and `.23` approval boundary; verify findings against source before repairs.
3. Run focused checks after any repair, then one complete stable-candidate gate.
4. Verify deployment against an empty temporary destination only:

```bash
DEST=$(mktemp -d)
env -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY -u LANGFUSE_BASE_URL -u LANGFUSE_HOST \
  PI_CONFIG_DEST="$DEST" scripts/update-pi-config.sh | tee "$DEST/deploy.log"
grep -F 'Skipping Langfuse evaluator sync: credentials are not configured.' "$DEST/deploy.log"
PI_CONFIG_DIR="$DEST" scripts/check-pi-config.sh
rm -rf "$DEST"
```

The asserted output proves remote evaluator sync was skipped. Do not run live `~/.pi` deployment in this wave.
5. Inspect `git status`, dependency cycles, and Beads lint. Record `.36` success only if implemented children are committed/closed, deferred package boundaries are explicit, and final gate passes.
6. Close `.36`; leave epic `pi-4tg9` open while deferred/out-of-scope children remain.

## File conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/extensions/subagent-error-workaround.ts` | 2, possibly 3 | Task 3 starts from integrated Task 2; modify only on proven missing metadata. |
| `tests/test_subagent_workaround.py` | 2, possibly 3 | Same serial order; retain contract cases. |
| `pi/agent/bin/agnt_lib/metrics.py` | 2, possibly 3 | Contract field first; taxonomy reuses current normalized metadata. |
| `pi/agent/bin/agnt_lib/improvement.py` | 3; `.14` later | Task 3 owns current edit. `.14` does not start while `.3/.4` are deferred. |
| `docs/SELF-IMPROVEMENT.md` | 2, 3 | Task 3 rebases on Task 2 and edits only taxonomy section. |
| `pi/agent/AGENTS.md` | 4 | One policy edit; keep skill-discovery descriptions unchanged. |

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-05-final-local-telemetry-wave-plan.md`

Recommended next skills: `executing-plans`, `using-git-worktrees`, and `test-driven-development`; use `verification-before-completion` before each commit/closeout claim.
