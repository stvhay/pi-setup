# Repo-Wide Ponytail Simplifications Implementation Plan

**Issue:** pi-i1ej — Apply repo-wide ponytail simplifications
**Design:** Bead `pi-i1ej` and approved repo-wide ponytail audit
**Date:** 2026-08-06
**Branch:** main

**Goal:** Remove approved rollback-only, duplicated, dead, and dependency-backed surfaces while preserving active Codex/OpenRouter behavior and project verification.

**Architecture:** Built-in Codex and OpenRouter targets remain the only model venues; Git history replaces the dormant Olla/local rollback implementation. Canonical project-init templates and skill references own shared content. Existing Python helpers and `nixpkgs.lib.genAttrs` replace local wrappers and `flake-utils`.

**Acceptance Criteria:**
- [ ] `olla-provider.ts`, Olla/local catalog venues, and Olla-only tests/eval contexts are absent; active Codex/OpenRouter routing still passes.
- [ ] Root GitHub CLI setup sources the canonical project-init template.
- [ ] Orphan and duplicated skill content is removed without weakening URL verification or STPA-Sec routing.
- [ ] `flake-utils`, no-op Nix configuration, dead helpers/imports/constants, and empty defaults are absent.
- [ ] Documentation describes active direct-provider policy without claiming retained Olla rollback code.
- [ ] Full documented verification passes and task-owned changes form one atomic local commit.

**Baseline Evidence:**
- `npm ci --ignore-scripts` → PASS with pre-existing npm audit warning: 3 vulnerabilities (1 moderate, 2 high).
- `scripts/check-pi-config.sh && bash -n scripts/*.sh` → PASS.
- `.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests` → PASS.
- `.venv/bin/python -m pytest tests/` → PASS, 556 tests.
- `pi/agent/bin/agnt eval run routing-smoke` → PASS.
- `pi/agent/bin/agnt eval run role-context-smoke` → PASS.

**Verification Commands:**
```bash
npm ci --ignore-scripts
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
nix flake metadata --no-write-lock-file >/dev/null
git diff --check
```

---

### Task 1: Remove dormant Olla/local surfaces

**Files:**
- Delete: `pi/agent/extensions/olla-provider.ts`
- Modify: `pi/agent/catalog.json`, `pi/agent/bin/agnt_lib/{doctor,metrics,routing}.py`, `pi/agent/bin/README.md`
- Modify: `pi/agent/evals/role-context-smoke/eval.json`, `pi/agent/tests/agent-context-smoke.sh`
- Modify: `docs/{ARCHITECTURE,MODEL-PORTFOLIO-2026-08,extension-web-compatibility}.md`, `pi/agent/AGENTS.md`, affected skills
- Test: `tests/test_agnt.py`, `tests/test_catalog.py`, `tests/test_model_config.py`, `tests/test_instructions.py`, and affected provider/runner/telemetry tests

**Steps:**
1. Change model-policy tests first to require no Olla/local provider file, catalog venue, route, or eval context; run focused tests and observe expected RED.
2. Delete provider and inactive catalog families/venues; remove Olla-specific branches while retaining provider-agnostic cost, circuit, and context behavior.
3. Replace Olla-specific test fixtures with active OpenRouter/Codex targets unless the test itself becomes obsolete.
4. Align docs and evals with active built-in providers and Git-history rollback.
5. Run focused model, routing, instruction, metric, and subagent tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_model_config.py tests/test_catalog.py tests/test_agnt.py tests/test_instructions.py tests/test_provider_circuits.py tests/test_subagent_workaround.py
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

### Task 2: Consolidate duplicated content

**Files:**
- Modify: `.envrc.d/gh.sh`
- Delete: `pi/agent/skills/requesting-code-review/references/structured-format-parsing.md`
- Modify: `pi/agent/skills/stamp-stpa-sec/SKILL.md`
- Modify: `pi/agent/skills/research/workflows/{StandardResearch,ExtensiveResearch}.md`
- Modify: `pi/agent/skills/project-init/templates/flake.nix`

**Steps:**
1. Add/update structural assertions where existing test suites already govern templates or skill content; observe RED before production/template edits.
2. Source canonical `templates/gh.sh` from the root direnv initializer.
3. Remove orphan reference; replace duplicated STPA-Sec process and research URL command blocks with explicit canonical-reference instructions.
4. Remove no-op Nix shell hook.
5. Run context, skill, config, and shell checks.

**Focused verification:**
```bash
bash -n .envrc.d/gh.sh pi/agent/skills/project-init/templates/gh.sh
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_langfuse_skill.py tests/test_update_pi_config.py
pi/agent/bin/agnt context-health --strict
```

### Task 3: Apply native/helper code cuts

**Files:**
- Modify: `flake.nix`, `flake.lock`, `pyproject.toml`
- Delete: `pi/agent/bin/openrouter-api-key`
- Modify: `pi/agent/bin/agnt`, `pi/agent/bin/agent-instructions`, `pi/agent/bin/web-search`
- Modify: `pi/agent/bin/agnt_lib/{doctor,health,runner,runner_protocol,runner_scheduler,tasks}.py`
- Test: focused Python/Nix/config tests

**Steps:**
1. Add/update structural tests first for absent helper/dependency/dead symbols and canonical imports; run focused tests and observe RED.
2. Replace `flake-utils.eachDefaultSystem` with `nixpkgs.lib.genAttrs`; regenerate `flake.lock` without obsolete nodes.
3. Reuse existing Python helpers, inline one-call wrappers, and remove dead imports/constants/empty defaults.
4. Delete the unreferenced OpenRouter key printer.
5. Run focused CLI, doctor, runner, health, and config tests.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_doctor.py tests/test_health.py tests/test_runner.py tests/test_runner_protocol.py tests/test_runner_scheduler.py tests/test_model_config.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
nix flake metadata --no-write-lock-file >/dev/null
```

### Task 4: Verify, review, and close

1. Inspect `git diff --stat`, `git diff`, deleted files, and remaining Olla/duplication references.
2. Validate affected docs and run a routed independent code review; verify any concrete finding before changes.
3. Run focused checks after review fixes, then one complete final verification matrix.
4. Stage only task-owned files, create one local atomic commit, record `agnt improve outcome pi-i1ej success`, and close Bead `pi-i1ej`.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-06-repo-wide-ponytail-simplifications-plan.md`
Recommended skills: `test-driven-development`, `verification-before-completion`, `requesting-code-review`, and `finishing-a-development-branch`.
