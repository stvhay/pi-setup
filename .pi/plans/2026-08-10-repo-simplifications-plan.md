# Repository Simplifications Implementation Plan

**Issue:** #pi-b9u1 — Implement repo simplification audit
**Design:** Approved ponytail audit in current Pi session
**Date:** 2026-08-10
**Branch:** main

**Goal:** Delete redundant commands, compatibility paths, configuration, tests, roles, and prose while preserving active headless execution, approval safety, and runtime artifacts.

**Architecture:** Pi's `subagent` tool becomes the interactive and fanout peer surface. The public `agnt invoke` command goes away, but shared `invoke_one` remains because runner/eval processes execute outside a live Pi tool context. Dedicated approval bridge tools remain the only approval surface. Graphify owns its Git hooks.

**Acceptance Criteria:**
- [ ] `subagent` handles interactive, one-shot, parallel, and metered review dispatch; no public `agnt invoke` command remains.
- [ ] Internal runner/eval headless workers and metrics remain functional through `invoke_one`.
- [ ] Generic ticket gateway no longer duplicates approval creation or decision resolution.
- [ ] `agnt graphify hook ...` passes through to Graphify's native command.
- [ ] Unused prompt-note, SOUL CLI, role, classifier, and dead metadata surfaces are removed; legacy Ollama retirement remains because removing it breaks old deployed configs.
- [ ] Node subprocess setup is shared once across extension tests.
- [ ] Current docs describe remaining behavior without historical or duplicated prose.
- [ ] Focused tests and full repository checks pass.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
npm test
```

---

### Task 1: Replace public invoke surface

**Files:**
- Modify: `tests/test_agnt.py`, `tests/test_agent_os_compat.py`, `tests/test_context_architecture.py`
- Modify: `pi/agent/bin/agnt`, `pi/agent/bin/agnt_lib/invoke.py`, `pi/agent/bin/agnt_lib/routing.py`
- Modify: `pi/agent/extensions/archimedes.ts`
- Modify: `pi/agent/skills/requesting-code-review/SKILL.md`, `pi/agent/skills/dev-workflow-common/SKILL.md`, `pi/agent/AGENTS.md`
- Modify: relevant command, architecture, and workflow docs

**Steps:**
1. Change tests first: route output exposes a `subagentExample`, public command inventory omits `invoke`, and metered one-shot reviews reach Archimedes with an output cap.
2. Run focused tests and confirm expected failures.
3. Delete `cmd_invoke`, fanout/file parsing, front-controller registration, and metered-review rejection. Retain `invoke_one`, `safe_target_name`, and eval/run callers.
4. Replace tracked interactive/review instructions with routed unnamed `subagent` calls.
5. Run focused tests.

### Task 2: Remove duplicate gateway approvals

**Files:**
- Modify: `tests/test_ticket_gateway.py`, `tests/test_orchestrator_extension.py`
- Modify: `pi/agent/bin/agnt_lib/gateway.py`, `pi/agent/extensions/ticket-gateway.ts`
- Modify: `pi/agent/bin/README.md`, `docs/ARCHITECTURE.md`

**Steps:**
1. Change gateway tests first to reject removed operations and preserve dedicated approval tools.
2. Confirm failure, then delete request/resolve schema, delegates, UI prompt, and imports.
3. Run gateway and approval tests.

### Task 3: Use native Graphify hooks

**Files:**
- Modify: `tests/test_agnt.py`, `pi/agent/bin/agnt_lib/graphify.py`
- Modify: `pi/agent/skills/graphify/SKILL.md`, `pi/agent/bin/README.md`

**Steps:**
1. Change tests first to require direct `hook install|status|uninstall` passthrough.
2. Confirm failure, then delete custom hook block management.
3. Run focused Graphify tests.

### Task 4: Delete unused compatibility surfaces

**Files:**
- Delete: `pi/agent/prompt-patterns/`, `pi/agent/AGENTS.d/roles/{debugger,redteam-reviewer,ux-reviewer}.md`
- Modify: `pi/agent/bin/agnt_lib/prompt.py`, `pi/agent/bin/agnt`, `pi/agent/bin/web-search`
- Modify: `scripts/update-pi-config.sh`, `tests/test_update_pi_config.py`
- Modify: `pi/agent/tasks/review.md`, `pi/agent/catalog.json`, related config tests
- Modify: relevant docs and smoke tests

**Steps:**
1. Remove unused prompt-note importer, SOUL command, orphan roles, dead metadata, and inference-only web category logic.
2. Retain the legacy Ollama retirement guard after review confirms that removing it leaves an incompatible preserved local extension active.
3. Add one subprocess check proving default search omits `categories` and explicit category forwards it.
4. Run focused CLI, package, deployment, and web-helper tests.

### Task 5: Shrink test and documentation surfaces

**Files:**
- Modify: `tests/conftest.py` and six Node-driven extension test modules
- Modify: `tests/test_cli_nameerrors.py`, `tests/test_context_architecture.py`
- Delete: `docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md`
- Rewrite: `docs/AGNT-SYSTEM.md`
- Modify: `README.md`, `pi/README.md`, `docs/ARCHITECTURE.md`, `docs/SELF-IMPROVEMENT.md`, `docs/RUN-ARTIFACTS.md`, `docs/RUNNER-SERVICE.md`, `docs/ORCHESTRATION-LOOP.md`

**Steps:**
1. Centralize Node subprocess setup in one fixture/helper and delete local copies.
2. Delete assertions that only freeze retired names or exact implementation syntax.
3. Delete stale point-in-time evaluation and trim system narrative to thesis, primitives, normal flow, and links.
4. Remove stale links and run documentation/config checks.

### Task 6: Final verification and closeout

1. Run focused suites after each changed subsystem.
2. Run full verification commands once against final candidate.
3. Inspect `git diff --check`, status, and requirement coverage.
4. Run read-only peer review, fix confirmed issues, and rerun affected checks.
5. Stage task-owned changes, commit once, record `agnt improve outcome pi-b9u1 success`, and close `pi-b9u1`.

## File Conflicts

Tasks 1, 2, 3, and 5 all touch command/architecture docs. Apply code and focused tests first; perform one final documentation pass in Task 5.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-10-repo-simplifications-plan.md`.
Recommended skills: `test-driven-development`, then `verification-before-completion`.
