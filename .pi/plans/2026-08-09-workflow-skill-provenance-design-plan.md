# Workflow Skill Provenance Design and Implementation Plan

**Issue:** pi-3lgo — Make workflow compliance evals load candidate skills explicitly
**Design:** This document
**Date:** 2026-08-09
**Branch:** `fix/workflow-skill-provenance`

**Goal:** Make every workflow compliance run explicitly choose tracked candidate skills or deployed live skills, with machine-readable provenance and unchanged scenario prompts.

**Architecture:** Add one required `--skill-mode candidate|deployed` option to the existing shell harness. Candidate mode invokes Pi with ambient skill/extension/context/prompt-template discovery disabled and one explicit recursive tracked skill root; `/skill:<name>` in each existing prompt still force-loads the requested body, while built-in tools remain enabled. Deployed mode preserves the existing ambient Pi invocation for post-deployment smoke checks. Each run writes a small payload-free provenance file and prints the same mode/root.

**Acceptance Criteria:**
- [ ] Eval execution without an explicit skill mode fails before repository or model work; `--list` remains read-only and mode-free.
- [ ] Candidate mode passes `--no-skills --skill <tracked-root> --no-extensions --no-context-files --no-prompt-templates` and does not disable tools.
- [ ] Candidate mode preserves the exact original case prompt, including `/skill:<name>` force loading.
- [ ] Deployed mode preserves ambient skill/context/extension behavior but is explicitly selected.
- [ ] Run provenance records schema, mode, resolved skill root, and ambient-discovery state without prompts, model output, credentials, or unrelated environment.
- [ ] A fake-Pi behavior difference fails in deployed mode and passes in candidate mode.
- [ ] Existing case names, provider/model controls, parallel behavior, filesystem assertions, and real tool-enabled scenarios remain unchanged.

**Verification Commands:**
```bash
ROOT=/Users/hays/Projects/pi-setup
"$ROOT/.venv/bin/python" -m pytest -q tests/test_workflow_compliance.py tests/test_context_architecture.py
bash -n scripts/eval-workflow-compliance.sh
scripts/eval-workflow-compliance.sh --list
"$ROOT/.venv/bin/python" -m ruff check tests/test_workflow_compliance.py tests/test_context_architecture.py
"$ROOT/.venv/bin/python" -m pytest -q tests/
scripts/check-pi-config.sh
pi/agent/bin/agnt context-health --strict
scripts/eval-workflow-compliance.sh --skill-mode candidate --case executing_plans_stops_on_main
```

---

## Root Cause and Contract

`run_pi()` currently calls bare `pi --print --no-session ... "$prompt"`. Pi therefore discovers skills from the live global agent directory; a tracked but undeployed skill edit is absent. The case can pass due to deployed behavior, and the harness emits no source evidence.

Pi's documented loading contract provides the native fix: `--skill <path>` is additive even with `--no-skills`, explicit skill locations discover nested `SKILL.md` directories recursively, and `/skill:<name>` force-loads a registered skill. Candidate mode uses that contract directly.

Interface:

```text
--skill-mode candidate  # tracked pre-deployment verification
--skill-mode deployed   # live post-deployment smoke
```

No implicit execution mode. `--list` exits before mode validation because it performs no model or skill load.

Candidate Pi arguments:

```text
--no-skills --skill <repo>/pi/agent/skills
--no-extensions --no-context-files --no-prompt-templates
```

Do not add `--no-tools`; existing tool-enabled cases must keep built-in tools. Do not use one-shot mode because it disables skills. Do not rewrite case prompts.

Per-run provenance file:

```text
schemaVersion=1
skillMode=candidate|deployed
skillRoot=<resolved relevant root>
ambientDiscovery=false|true
```

The root path is relevant provenance. No prompt, output, model payload, environment dump, or credential is included.

## Task 1: Deterministic fake-Pi regressions [Independent]

**Files:**
- Create: `tests/test_workflow_compliance.py`

**Steps:**
1. Add a fake `pi` executable that logs argv and returns bounded deterministic output for the existing `brainstorming_no_write` case.
2. Assert mode omission fails before fake Pi invocation.
3. Assert candidate argv contains exact isolation/skill-root flags, leaves tools enabled, and preserves the exact prompt.
4. Assert deployed argv omits candidate isolation flags and requires explicit mode.
5. Assert provenance contents for both modes.
6. Make fake behavior conditional on candidate flags; prove candidate passes while deployed fails the unchanged case assertion.
7. Run focused tests and confirm expected RED against unsupported `--skill-mode`/missing provenance.

**Focused Verification:**
```bash
/Users/hays/Projects/pi-setup/.venv/bin/python -m pytest -q tests/test_workflow_compliance.py
```

**Expected Result:** RED because current harness rejects `--skill-mode` and cannot emit provenance.

## Task 2: Minimal harness implementation [Depends on: Task 1]

**Files:**
- Modify: `scripts/eval-workflow-compliance.sh`
- Test: `tests/test_workflow_compliance.py`
- Test: `tests/test_context_architecture.py`

**Steps:**
1. Resolve repository and candidate/deployed skill roots without relying on caller cwd.
2. Parse one required `--skill-mode` value for execution; reject duplicates/unknown values.
3. Keep `--list` behavior unchanged.
4. Build Pi argv in `run_pi()` using Bash 3.2-compatible arrays.
5. Add candidate-only discovery isolation and explicit tracked root; preserve final prompt byte-for-byte and omit `--no-tools`.
6. Write/print provenance after run directory creation and before cases execute.
7. Add static architecture assertions for the native flags and explicit-mode contract.
8. Run focused GREEN tests plus shell syntax/list checks.

**Expected Result:** Both deterministic modes pass; candidate-only fake behavior proves wrong-skill runs no longer count.

## Task 3: Documentation and final evidence [Depends on: Task 2]

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md`
- Modify: `docs/ARCHITECTURE.md`

**Steps:**
1. Mark candidate mode as the pre-deployment command and deployed mode as the post-deployment smoke command.
2. Document provenance location/fields and candidate isolation/tool behavior.
3. Run focused deterministic checks.
4. Request approval for exactly one bounded subscription-backed real `executing_plans_stops_on_main` candidate-mode case.
5. Verify output provenance points to the tracked root, original filesystem assertions pass, and no ambient skill source is used.
6. Run final full project gates and independent review; repair only confirmed task-scoped findings test-first.
7. Commit one signed task-owned implementation commit.

**Expected Result:** Clean verified candidate branch; main integration/deployment/Bead closeout remain separately gated.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-09-workflow-skill-provenance-design-plan.md`

Recommended next skill: `test-driven-development`; use `verification-before-completion` before claiming completion.
