# Pi Process Restart Implementation Plan

**Issue:** pi-3wo5 — Add extension-only Pi process restart
**Design:** Bead `pi-3wo5` design field
**Date:** 2026-08-10
**Branch:** main

**Goal:** Add tracked `/restart` and `restart_pi` extension surfaces that gracefully shut down Pi, replace its Node 24 process, and resume the same persisted session.

**Architecture:** Keep implementation in one auto-discovered extension. Command validates TUI, Node/macOS-or-Linux `process.execve`, persisted session identity, and current Node/Pi entrypoint before registering one `process.once("exit")` listener and calling `ctx.shutdown()`. On a clean exit, listener synchronously calls `process.execve(process.execPath, [process.execPath, ...process.execArgv, process.argv[1], "--session-dir", sessionDir, "--session", sessionId], process.env)`; synchronous shutdown-request errors remove the listener, and nonzero exits never restart. Tool only queues `/restart` as a follow-up. This preserves Node launch flags, cwd, and environment while letting Pi finish all normal shutdown handlers before process replacement.

**Acceptance Criteria:**
- [ ] Node runtime, CI, package engine, and project-init scaffold use current Node 24 LTS.
- [ ] `/restart` and `restart_pi` register from tracked extension.
- [ ] Tool queues terminal command; no process replacement occurs during tool execution.
- [ ] Supported command registers one exit listener before graceful shutdown and resumes exact session ID from default or custom session directory.
- [ ] Non-TUI, non-Node, non-macOS/Linux, missing-execve, ephemeral-session, or missing-entrypoint cases reject before listener/shutdown.
- [ ] Exit listener restarts only after exit code 0 and reports `execve` failure through synchronous stderr output with a failing exit status.
- [ ] Documentation distinguishes `/reload` resource refresh from `/restart` process replacement and states Node 24 macOS/Linux support.
- [ ] Focused and project acceptance checks pass under Node 24.

**Verification Command(s):**
```bash
nix develop --command node --version
nix develop --command npm ci --ignore-scripts
nix develop --command .venv/bin/python -m pytest tests/test_process_restart.py tests/test_beads_workspace.py
nix develop --command scripts/check-pi-config.sh
nix develop --command bash -n scripts/*.sh
nix develop --command .venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
nix develop --command .venv/bin/python -m pytest tests/
nix develop --command pi/agent/bin/agnt eval run routing-smoke
nix develop --command pi/agent/bin/agnt eval run role-context-smoke
```

---

### Task 1: Pin Node 24 LTS [Independent]

**Context:** Align local Nix, npm engine metadata, CI, and repository-owned project-init guidance with current Node 24 LTS.

**Files:**
- Modify: `flake.nix`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `.github/workflows/ci.yml`
- Modify: `pi/agent/skills/project-init/SKILL.md`
- Create: `.pi/skill-evals/project-init/scenarios/node-lts-toolchain.md`
- Test: `tests/test_beads_workspace.py`

**Steps:**
1. Update focused tests and skill baseline scenario first; observe old Node 22 assertions fail.
2. Change only runtime pins and root lockfile engine metadata.
3. Run focused Node pin tests and a Node 24 `process.execve` capability smoke.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_beads_workspace.py -k 'node_test_runtime_is_pinned or ci_installs_pinned_node_dependencies_before_tests' -q
nix shell nixpkgs#nodejs_24 --command node -p 'process.version + " " + typeof process.execve'
```

**Expected result:** Node pin tests pass; runtime reports Node 24 and `function`.

### Task 2: Test restart contract [Depends on: Task 1]

**Context:** Exercise extension through real Node TypeScript loading with fake Pi registration/context and monkeypatched process effects. Never execute real replacement.

**Files:**
- Create: `tests/test_process_restart.py`

**Steps:**
1. Add registration/tool test proving follow-up queue and no shutdown/exec during tool execution.
2. Add supported command test proving listener-before-shutdown order, exact exec path/argv/env, and both default/custom session directory values.
3. Add rejection tests for unsupported mode/platform/runtime, missing execve, ephemeral session, arguments, and missing entrypoint; assert no listener or shutdown.
4. Add failure-path subprocess assertion for synchronous stderr reporting.
5. Run focused test and confirm failure because extension is absent.

**Focused verification:**
```bash
nix develop --command .venv/bin/python -m pytest tests/test_process_restart.py -q
```

**Expected result:** RED before extension; all tests pass after Task 3.

### Task 3: Implement minimal restart extension [Depends on: Task 2]

**Context:** Follow Pi `reload-runtime.ts` tool-to-command pattern and `shutdown-command.ts` graceful shutdown pattern. Keep listener registration inside accepted command so `/reload` never accumulates it.

**Files:**
- Create: `pi/agent/extensions/process-restart.ts`

**Steps:**
1. Register `/restart` and `restart_pi` with empty parameters.
2. In command, reject arguments and unsupported/runtime/session/entrypoint states before side effects.
3. Build canonical Node/Pi resume argv from current executable, Node `execArgv`, entrypoint, session directory, and session ID.
4. Register one synchronous exit listener, then request `ctx.shutdown()`; remove listener if that synchronous request throws.
5. In listener, restart only after exit code 0; on `execve` throw, set failing exit status and synchronously write actionable error to stderr.
6. Run focused tests under Node 24.

**Focused verification:**
```bash
nix develop --command .venv/bin/python -m pytest tests/test_process_restart.py -q
```

**Expected result:** Registration, sequencing, resume arguments, rejection, and failure reporting pass without a real replacement.

### Task 4: Document runtime boundary [Depends on: Task 3]

**Context:** Operators need exact difference between resource reload and process replacement, plus platform/session limits.

**Files:**
- Modify: `pi/README.md`
- Modify: `docs/extension-web-compatibility.md`
- Test: `tests/test_process_restart.py`

**Steps:**
1. Add concise runtime commands section to `pi/README.md`.
2. Add tracked-extension matrix row noting TUI-only Node 24 macOS/Linux behavior and RPC unavailability.
3. Assert documentation names `/reload`, `/restart`, `restart_pi`, Node 24, macOS/Linux, Windows, and persisted-session requirement.
4. Run focused tests and config checks.

**Focused verification:**
```bash
nix develop --command .venv/bin/python -m pytest tests/test_process_restart.py tests/test_agent_os_compat.py -q
nix develop --command scripts/check-pi-config.sh
```

**Expected result:** Documentation contract and tracked extension matrix pass.

### Task 5: Full verification and closeout [Depends on: Task 4]

**Context:** Validate complete acceptance contract under project Node 24 environment before one task-owned commit and Bead closure.

**Files:**
- Modify: `.beads/issues.jsonl` through `bd`

**Steps:**
1. Update Bead Node boundary from 22 to 24.
2. Run all plan verification commands with fresh output.
3. Inspect status/diff for unrelated or generated changes.
4. Stage task-owned files and create one local atomic commit.
5. Close `pi-3wo5`; run `agnt improve outcome pi-3wo5 success`.

**Focused verification:**
```bash
git diff --check
git status --short
```

**Expected result:** All checks pass, one atomic local commit exists, Bead is closed, outcome is recorded.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-10-pi-process-restart-design-plan.md`
Recommended next skill: `test-driven-development`; `verification-before-completion` before completion claim.
