# Approved Ponytail Audit Implementation Plan

**Issue:** pi-un4f — Apply approved repo-wide ponytail audit
**Design:** User-approved repo-wide ponytail audit in current Pi session
**Date:** 2026-08-10
**Branch:** main

**Goal:** Apply approved complexity cuts while preserving active Pi workflows and safety boundaries.

**Architecture:** Remove legacy and no-op surfaces at their boundaries, then use native platform/stdlib behavior and existing concrete clients directly. Keep active direct-Pi, safe orchestrator, deployment, routing, telemetry, and skill behavior. Consolidate test setup without weakening assertions.

**Acceptance Criteria:**
- [ ] Legacy repair-tools mode, redundant GitHub bootstrap, orphan scenario, empty MCP config, dead shell helper, and redundant default config are absent.
- [ ] Native/stdlib replacements and direct `RunnerClient` use preserve CLI behavior.
- [ ] STPA-Sec and research workflows retain canonical instructions without duplicated blocks.
- [ ] Repeated test setup is consolidated while focused and full tests pass.
- [ ] Documentation and config checks match deployed behavior.
- [ ] Task-owned changes form one local atomic commit.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Lock removals with structural tests

**Files:**
- Modify: `tests/test_context_architecture.py`
- Modify: `tests/test_orchestrator_extension.py`
- Modify: `tests/test_pi_packages.py`
- Modify: `tests/test_update_pi_config.py`

**Steps:**
1. Change structural assertions to require approved dead/default surfaces to be absent.
2. Run focused tests and confirm RED against current files.
3. Keep behavioral assertions for remaining safe orchestrator, package, and deployment paths.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_orchestrator_extension.py tests/test_pi_packages.py tests/test_update_pi_config.py
```

### Task 2: Remove dead and native-replaced surfaces

**Files:**
- Delete: `scripts/pi-bootstrap-repair-mode.sh`
- Delete: `pi/agent/skills/project-init/templates/gh.sh`
- Delete: `.envrc.d/gh.sh`
- Delete: `pi/agent/mcp.json`
- Delete: `.pi/skill-evals/project-skills-maintenance/scenarios/2026-06-26-retrospective-followups.md`
- Modify: `pi/agent/extensions/orchestrator-service.ts`
- Modify: `scripts/check-pi-config.sh`
- Modify: `scripts/update-pi-config.sh`
- Modify: `flake.nix`
- Modify: `pi/agent/skills/project-init/templates/flake.nix`
- Modify: `pi/agent/settings.json`
- Modify: relevant docs/tests

**Steps:**
1. Remove legacy repair-tools flag, state, tool set, command, launcher, and docs.
2. Rely on Nix `gh`; remove custom downloader and root source wrapper.
3. Remove empty MCP file/check/docs, dead `install_patch_base`, unused `jq`/in-shell `direnv`, and runtime-default settings.
4. Run focused structural and extension/config tests to GREEN.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_orchestrator_extension.py tests/test_pi_packages.py tests/test_update_pi_config.py
scripts/check-pi-config.sh
bash -n scripts/*.sh
```

### Task 3: Apply code and content shrinks

**Files:**
- Modify: `pi/agent/bin/agnt`
- Delete: `pi/agent/bin/pi-plans-dir`
- Modify: `pi/agent/bin/agnt_lib/{evals,prompt,runs,runner_client,work,gateway,metrics}.py`
- Modify: `pi/agent/skills/stamp-stpa-sec/SKILL.md`
- Modify: `pi/agent/skills/research/workflows/{StandardResearch,ExtensiveResearch}.md`
- Modify: relevant tests/docs

**Steps:**
1. Inline `agnt plans-dir` behavior and remove its one-caller executable.
2. Replace hand-rolled slug loops with `re.sub` while preserving fallback behavior.
3. Call `RunnerClient` methods directly; remove module-level delegates.
4. Use `argparse.BooleanOptionalAction` for paired annotation flags.
5. Remove STPA-Sec and research text duplicated by canonical references.
6. Run focused CLI, runner, metrics, context, and skill checks.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_runner.py tests/test_runner_client.py tests/test_runner_visibility.py tests/test_ticket_gateway.py tests/test_context_architecture.py tests/test_workflow_compliance.py
```

### Task 4: Consolidate repeated test setup

**Files:**
- Modify: `tests/test_improvement.py`
- Modify: `tests/test_subagent_workaround.py`
- Modify: `tests/test_update_pi_config.py`

**Steps:**
1. Add one defaulted scan helper and replace repeated `scan_sessions` argument blocks.
2. Add one shared Node extension harness builder for repeated subagent setup.
3. Add one package fixture writer for repeated package metadata loops.
4. Preserve every existing assertion and parameterized behavior.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py tests/test_subagent_workaround.py tests/test_update_pi_config.py
```

### Task 5: Verify, review, and close

1. Inspect full diff and deleted files; compare actual line/dependency reduction with audit estimate.
2. Run focused checks, then full documented verification.
3. Run independent read-only review if delegation is healthy; verify concrete findings locally.
4. Stage only task-owned changes, create one local atomic commit, record `agnt improve outcome pi-un4f success`, and close Bead `pi-un4f`.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-10-approved-ponytail-audit-plan.md`
Recommended next skill: `test-driven-development`; use `verification-before-completion` before commit.
