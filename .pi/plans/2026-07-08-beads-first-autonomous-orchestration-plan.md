# Beads-First Autonomous Orchestration Implementation Plan

**Issue:** None — create a Beads epic/task set before implementation begins.
**Design:** Approved in chat on 2026-07-08; incorporates `docs/AGNT-SYSTEM.md`, `docs/ORCHESTRATION-LOOP.md`, `docs/RUN-ARTIFACTS.md`, and `.pi/plans/2026-07-08-archimedes-subagent-integration.md`.
**Date:** 2026-07-08
**Branch:** main

**Goal:** Build a Beads-first orchestration layer where a no-bash main orchestrator manages durable tickets, while a continuous runner dispatches approved work through audited run artifacts and Archimedes-visible workers.

**Architecture:** Beads remains the durable work graph for tickets, dependencies, blockers, approvals, closeout, and maintenance cadence checkpoints. `agnt` remains the deterministic control plane for validation, routing, run artifacts, health checks, and worker dispatch. Pi/Archimedes provides live UX: plan/dependency views, subagent progress, `ask` dialogs, and ephemeral todos derived from Beads/run state. Worker/subagent runs are recorded by default and referenced from `.pi/runs`; `pi-observational-memory` may provide compact recall/context continuity for long sessions but is not canonical project state. A project-level singleton runner drains ready work continuously, with pause and future budget-limit seams.

**Acceptance Criteria:**
- [ ] Main orchestrator can operate through a ticket gateway/plan view with no raw bash, write, edit, raw Beads, or raw subagent access.
- [ ] Beads ticket metadata can be validated for action, approval, allowed effects, model policy, epic/worktree policy, write sets, and closeout requirements.
- [ ] Model and thinking-level selection is deterministic, scored, and outside orchestrator discretion, while preserving model diversity for reviews/verification.
- [ ] A continuous project singleton runner can auto-start ready approved work, pause accepting new work, report status, and leave durable run artifacts.
- [ ] Human questions, approvals, and rejections are represented in Beads and cannot remain only in chat/Archimedes UI.
- [ ] Archimedes todos are ephemeral projections seeded from Beads/run data; durable outcomes are promoted back into Beads and `.pi/runs`.
- [ ] One worktree per epic is supported; task conflicts are expressed as Beads dependencies, not nested worktrees.
- [ ] Closeout cross-checks catch dangling approvals, missing evidence, stale runs, worktree/git drift, unresolved follow-ups, and blocker inconsistencies.
- [ ] Autonomous self-improvement cadence derives maintenance triggers from Beads/git/run artifacts and creates/reports normal Beads work.
- [ ] Worker/subagent runs are recorded by default with session/transcript refs in `.pi/runs`; observational memory may compact/recall details but is not canonical project truth.
- [ ] Documentation, tests, evals, and project checks pass.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

---

## Approved Design Decisions

- Main orchestrator has no bash. It receives validated domain tools only.
- Beads is the durable source of truth for work, dependencies, blockers, approvals, closeout, and maintenance/self-improvement tasks.
- Archimedes task lists are ephemeral, derived from Beads/run state, and may auto-clear without losing project state.
- Archimedes/subagent visibility is useful, but raw `subagent` calls must not be the durable dispatch path for real work.
- `ask`/approval decisions must be documented through Beads, not only chat or TUI state.
- Approved implementation tickets should auto-run.
- Human-review gates appear as Beads blockers/decision tickets; the orchestrator helps resolve them.
- Continuous auto-start is desired, with a stop-new-work toggle and design room for budget/rate limits.
- Model selection and thinking level should be selected by routing/scoring and diversity policy, not ad hoc by the main orchestrator.
- Keep worktree policy simple: one worktree per epic. Conflicts inside an epic are handled through Beads dependencies.
- Autonomous self-improvement uses derived cadence signals, not hidden counters.
- Worker/subagent sessions are recorded by default for post-hoc review, lessons learned, debugging, and handoff.
- Observational memory is a recall/context-management layer for long or deep sessions; it must promote durable findings into Beads or run artifacts before they affect project state.

## Non-goals for the first implementation

- No nested per-task worktrees inside an epic.
- No always-on remote service or system-level daemon install.
- No GitHub-as-second-source-of-truth integration.
- No auto-push, auto-merge, branch deletion, worktree removal, hook installation, or Beads history mutation.
- No durable project state stored only in Archimedes todos.
- No autonomous refactoring implementation without explicit approval metadata.
- No treating observational-memory observations/reflections as canonical work, approval, blocker, evidence, or quality state.

## Proposed data model

Store dispatch policy under Beads metadata, using a namespaced object. Example:

```json
{
  "pi": {
    "action": "implement",
    "routingTask": "implementation",
    "role": "implementation-worker",
    "approved": true,
    "allowedEffects": ["read_workspace", "write_artifacts", "edit_files", "update_beads"],
    "risk": "medium",
    "budget": "balanced",
    "modelPolicy": {
      "mode": "auto",
      "diversity": "normal",
      "avoidFamilies": []
    },
    "thinkingPolicy": "auto",
    "epicId": "pi-123",
    "worktreePolicy": "epic-worktree",
    "writeSet": ["pi/agent/bin/agnt_lib/work.py", "tests/test_agnt.py"],
    "closeout": {
      "requiresEvidence": true,
      "requiresResolvedApprovals": true,
      "requiresFollowUpsReconciled": true
    },
    "sessionPolicy": "recorded",
    "memoryPolicy": "auto",
    "sessionName": "run:<id> bead:<id> action:<action>",
    "memoryPromotion": {
      "requiresDurablePromotion": true,
      "durableTargets": ["beads", "run-artifacts"]
    }
  }
}
```

Validation principles:

- Missing `pi.action` or unknown actions block auto-dispatch.
- `implement` requires `approved: true`, acceptance criteria, allowed effects, write set, and an epic/worktree policy.
- Read-only actions may auto-run with less metadata but still create run artifacts.
- Orchestrator-provided model overrides are rejected unless they match allowed policy constraints.
- Unknown write sets or overlapping write sets in concurrent work become blockers/dependencies.
- Missing session policy defaults to `recorded` for runner-spawned workers.
- Observational-memory records are advisory recall/context only; important findings must be promoted to Beads or `.pi/runs` before closeout.

## Task Plan

### Task 0: Create Beads work graph for this implementation [Manual prerequisite]

**Context:** The design itself says Beads is canonical. Before implementation edits, create a Beads epic and child tasks that map to this plan. This task is listed first because the plan currently has no Beads issue.

**Files:**
- No tracked file edits required.
- Beads state: `.beads/issues.jsonl` may change after approved Beads creation.

**Steps:**
1. Ask for explicit approval to create Beads for this plan, or have the user create them.
2. Create an epic for “Beads-first autonomous orchestration”.
3. Create child tasks for the plan phases below.
4. Add dependencies matching the task dependencies below.
5. Attach this plan path in notes/design fields.

**Focused verification:**
```bash
bd show <epic-id> --json
bd dep tree <epic-id>
```

**Expected result:** Beads show an epic and child tasks with dependencies and this plan referenced.

### Task 0.5: Evaluate and configure observational memory policy [Depends on: Task 0]

**Context:** `pi-observational-memory` can help long-lived orchestrator and deep-dive worker sessions preserve source-backed observations/reflections across compaction. It is useful as a recall/context-management layer, not as canonical project state.

**Files:**
- Modify: `pi/agent/settings.json` only after source/package review and explicit approval to add the package.
- Modify: `pi/.gitignore` and `scripts/check-pi-config.sh` only if the package creates generated runtime state under tracked config paths.
- Test: existing config and context checks.
- Docs: `docs/AGNT-SYSTEM.md`, `docs/ORCHESTRATION-LOOP.md`, and `pi/agent/bin/README.md` later in Task 11.

**Steps:**
1. Review the published package/source for `pi-observational-memory` v3 before adding it to tracked config.
2. Decide install scope: global reusable Pi config vs project-local package. Prefer tracked `pi/agent/settings.json` only after package review.
3. Define memory policy values: main orchestrator `active`; deep/long workers `auto`; short workers `recorded session with memory passive unless thresholds justify active memory`; no debug logs by default.
4. Allow the `recall` tool for the main orchestrator and long-running/deep-dive workers, but require durable promotion of important findings into Beads or `.pi/runs`.
5. Define worker environment defaults so recorded worker sessions can use observational memory when useful, while background memory cost is bounded by routing/budget policy.
6. Document that observational-memory ledgers are session-local recall aids and cannot satisfy closeout, approval, evidence, or blocker requirements by themselves.

**Focused verification:**
```bash
scripts/check-pi-config.sh
PI_CONFIG_DIR="$PWD/pi" scripts/check-pi-config.sh
```

**Expected result:** The plan has a clear memory package policy before implementation; package installation/config changes are explicitly gated by review and approval.

### Task 1: Add orchestration metadata schema and validators [Independent after Task 0.5]

**Context:** Implement a deterministic schema/parser for the `metadata.pi` dispatch contract before building UI or runner behavior. Keep the parser dependency-free, like existing `agnt_lib` modules.

**Files:**
- Create: `pi/agent/bin/agnt_lib/orchestration.py`
- Modify: `pi/agent/bin/agnt` if a new command family is needed
- Test: `tests/test_orchestration.py` or `tests/test_agnt.py`
- Docs: `docs/RUN-ARTIFACTS.md` or `docs/AGNT-SYSTEM.md` later in Task 11

**Steps:**
1. Define normalized metadata data structures as plain dictionaries/functions.
2. Implement validation for action, routing task, role, allowed effects, approval, risk, budget, model policy, worktree policy, write set, and closeout policy.
3. Add clear validation statuses: `dispatchable`, `blocked`, `needs-human`, `invalid`.
4. Add unit tests for valid review, valid approved implement, missing approval, unknown action, missing write set, and invalid model override.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_orchestration.py -q
```

**Expected result:** Metadata validation is covered without requiring live Beads or model calls.

### Task 2: Add Beads plan view and dependency tree core [Depends on: Task 1]

**Context:** The ticket gateway needs a deterministic plan-view source that shows durable work, dependencies, blockers, approvals, active runs, and closeout status. Start with a CLI/core helper before building Pi extension UI.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py` or create `pi/agent/bin/agnt_lib/tickets.py`
- Modify: `pi/agent/bin/agnt`
- Test: `tests/test_agnt.py` or `tests/test_orchestration.py`
- Docs: `pi/agent/bin/README.md` later in Task 11

**Steps:**
1. Add a read-only command such as `agnt work tree [--json] [--epic ID]` or `agnt ticket view`.
2. Read Beads via `bd ... --json`; do not parse `.beads/issues.jsonl` directly unless Beads CLI lacks the needed query.
3. Include nodes with: id, title, type, status, priority, dependencies, dependents, metadata validation status, active run refs, approval/blocker refs.
4. Add a compact text view and JSON output.
5. Ensure epic and non-epic views both work.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py -q -k "work or orchestration or ticket"
pi/agent/bin/agnt work tree --json >/tmp/pi-work-tree.json
python3 -m json.tool /tmp/pi-work-tree.json >/dev/null
```

**Expected result:** A machine-readable plan/dependency tree exists without exposing raw Beads commands to the orchestrator.

### Task 3: Add model scoring and diversity selection [Depends on: Task 1]

**Context:** Workers should not receive arbitrary model choices from the orchestrator. Extend existing routing to produce scored choices and diversified sets for review/verification.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/routing.py`
- Modify: `pi/agent/bin/agnt_lib/runs.py`
- Modify: `pi/agent/bin/agnt_lib/work.py` or orchestration module
- Test: `tests/test_agnt.py`, `tests/test_route_feedback.py`, or new `tests/test_routing_policy.py`
- Docs: `pi/agent/bin/README.md` later in Task 11

**Steps:**
1. Reuse existing task routing and metrics feedback instead of adding a second model table.
2. Add a selector that returns `{target, thinkingLevel, reasons, rejected, diversityGroup}`.
3. For review/verification fanout, choose diverse model families when policy asks for diversity.
4. Disallow direct orchestrator model selection except policy constraints such as budget/risk/local-ok/avoid family.
5. Ensure run artifacts record selected model and thinking level.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_route_feedback.py -q
pi/agent/bin/agnt route --task review --risk medium --budget cheap --local-ok >/tmp/pi-route.json
python3 -m json.tool /tmp/pi-route.json >/dev/null
```

**Expected result:** Model selection is deterministic, auditable, and compatible with existing routing tests.

### Task 4: Extend run artifacts for orchestration state [Depends on: Tasks 1 and 3]

**Context:** `.pi/runs` should preserve selected model, thinking, ticket metadata snapshot, Beads decisions/approvals, seeded todos, worker session refs, transcript/memory-summary refs when available, and closeout checks without relying on chat.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/runs.py`
- Modify: `pi/agent/bin/agnt_lib/work.py`
- Test: `tests/test_agnt.py` or `tests/test_orchestration.py`
- Docs: `docs/RUN-ARTIFACTS.md` later in Task 11

**Steps:**
1. Add backward-compatible optional fields to `invocation.yaml`: `ticketMetadata`, `selectedModel`, `thinkingLevel`, `ephemeralTodoSeed`, `worktree`, `dispatchPolicy`, `sessionPolicy`, and `memoryPolicy`.
2. Add result fields or artifact references for `sessionRef`, `transcriptRef`, `memorySummaryRef`, `approvalRefs`, `decisionRefs`, `healthChecks`, and `closeoutChecks` if needed.
3. Keep schemaVersion 1 if fields are optional; otherwise document schemaVersion 2 and migration behavior.
4. Update prompt rendering to tell workers that Archimedes todos are transient and durable outcomes must become Beads/run evidence.
5. Update worker invocation to record sessions by default for runner-spawned work; keep `.pi/runs` summaries/evidence as the primary durable searchable layer.
6. Add validation tests for optional fields and backward compatibility.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py -q -k "run_bundle or invocation or result"
pi/agent/bin/agnt runs validate .pi/runs/nonexistent 2>/dev/null || true
```

**Expected result:** Existing run artifact commands still work, and new orchestration fields validate when present.

### Task 5: Implement Beads-backed ask, decision, and approval flow [Depends on: Tasks 1 and 4]

**Context:** Human input must not dangle in chat or Archimedes UI. Questions and approvals need durable Beads records that can block/resume work.

**Files:**
- Create: `pi/agent/extensions/beads-ask-bridge.ts` or integrate into a ticket gateway extension
- Modify: `pi/agent/settings.json` if adding a new extension file is not auto-discovered in deploy config
- Modify: `pi/agent/bin/agnt_lib/orchestration.py` or ticket module for decision helpers
- Test: static/unit tests where practical; TypeScript smoke via project checks
- Docs: `docs/ORCHESTRATION-LOOP.md`, `docs/RUN-ARTIFACTS.md` later in Task 11

**Steps:**
1. Decide the first implementation surface: a new explicit `ticket_question`/`ticket_approval` tool, an Archimedes ask bus bridge, or both.
2. For every question/approval, create or update a Beads decision/approval ticket with context, options, requested default, requesting run id, and blocking relationship.
3. Record the final answer/rejection/timeout in Beads notes/metadata and in the run result.
4. If the user cancels or times out, leave the blocker visible instead of silently failing.
5. Ensure approval previews include action, scope, consequences, reversibility, and closeout path.

**Focused verification:**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/test_orchestration.py -q
```

**Expected result:** Human decisions appear in Beads and can be audited even if the UI/session disappears.

### Task 6: Add ticket gateway tool and plan-view command [Depends on: Tasks 1, 2, and 5]

**Context:** This is the main orchestrator’s validated control surface. It should expose structured operations without raw bash, raw Beads, raw subagent, edit, or write access.

**Files:**
- Create: `pi/agent/extensions/ticket-gateway.ts`
- Possibly create: `pi/agent/extensions/ticket-gateway/` if split into modules
- Modify: `pi/agent/settings.json` only if explicit extension registration is needed
- Test: `scripts/check-pi-config.sh`, context-health, and any TypeScript/static checks available
- Docs: `pi/agent/AGENTS.md`, `pi/agent/bin/README.md`, `docs/AGNT-SYSTEM.md` later in Task 11

**Steps:**
1. Register a `ticket_gateway` tool with strict enum operations: `list`, `show`, `tree`, `create_draft`, `request_approval`, `resolve_blocker`, `runner_status`.
2. Keep inputs structured and validated; reject free-form shell-like payloads.
3. Add a `/work` or `/plan-view` command for TUI tree/status display.
4. Ensure generated output is compact by default and expand-on-demand in UI.
5. Configure the orchestrator profile/instructions to use only this tool plus read-only file tools and approved recall/context tools such as `recall`.
6. Make the gateway surface session refs and memory-summary refs as supporting context, never as closeout evidence unless promoted into `.pi/runs` evidence.

**Focused verification:**
```bash
scripts/check-pi-config.sh
PI_CONFIG_DIR="$PWD/pi" scripts/check-pi-config.sh
```

**Expected result:** The gateway appears as a Pi extension/tool after deploy and passes config checks.

### Task 7: Implement continuous singleton runner [Depends on: Tasks 1-4]

**Context:** The project runner should continuously drain ready work, auto-run approved implementation tickets, and create durable blockers when it cannot proceed.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py` or create `pi/agent/bin/agnt_lib/runner.py`
- Modify: `pi/agent/bin/agnt`
- Test: `tests/test_orchestration.py`, `tests/test_agnt.py`
- Docs: `docs/ORCHESTRATION-LOOP.md`, `pi/agent/bin/README.md` later in Task 11

**Steps:**
1. Add commands such as `agnt work loop`, `agnt work runner status`, `agnt work runner pause`, `agnt work runner resume`, and `agnt work runner tick --dry-run`.
2. Enforce one active runner per git root with a lock file under `.pi/runner/` or `.pi/work-runner/`.
3. Implement continuous polling with a safe interval and clean shutdown.
4. Add pause semantics: finish active run if safe, but stop accepting new work.
5. Add budget/rate-limit placeholders in state/config without enforcing complex budgets in v1.
6. Record worker sessions by default, assign stable session names like `run:<id> bead:<id> action:<action>`, and write session/transcript refs into the run result.
7. Set observational-memory policy per run: main orchestrator active; deep/long workers auto/active; short workers recorded with passive memory unless thresholds/policy opt in.
8. Auto-start dispatchable ready tickets; mark invalid/needs-human work with Beads blockers/decision tickets.
9. Never close work without evidence and closeout checks.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_orchestration.py tests/test_agnt.py -q
pi/agent/bin/agnt work runner status --json
pi/agent/bin/agnt work runner tick --dry-run --json
```

**Expected result:** A dry-run tick explains what would start/block, and status reports singleton state without mutating unexpectedly.

### Task 8: Implement one-worktree-per-epic policy [Depends on: Task 7]

**Context:** Implementation work should run in an epic worktree. Tasks inside one epic are serialized or dependency-ordered; conflicts are handled by Beads dependencies.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py` or `runner.py`
- Modify: `pi/agent/bin/agnt_lib/orchestration.py`
- Test: `tests/test_orchestration.py`
- Docs: `docs/ORCHESTRATION-LOOP.md` later in Task 11

**Steps:**
1. Add helper logic to map an epic id to `.worktrees/epic/<epic-id>-<slug>` and branch `epic/<epic-id>-<slug>`.
2. In v1, require explicit approval before creating a worktree if it does not already exist.
3. Serialize implementation tasks within one epic worktree unless dependencies guarantee only one ready task.
4. Allow parallel work across different epics only when worktree and external-resource checks pass.
5. Reject or block implementation tickets with missing epic/worktree policy.

**Focused verification:**
```bash
git worktree list
.venv/bin/python -m pytest tests/test_orchestration.py -q -k "worktree or epic"
```

**Expected result:** The runner can identify required epic worktrees and refuses unsafe implementation dispatch.

### Task 9: Add closeout and rail-guard health checks [Depends on: Tasks 4, 7, and 8]

**Context:** Closeout must catch drift and dangling state: missing evidence, unresolved approvals, unreconciled follow-ups, dirty worktrees, stale runner locks, active runs with closed beads, and blocked beads without visible blockers.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/work.py` or create `pi/agent/bin/agnt_lib/health.py`
- Modify: `scripts/check-pi-config.sh` if a safe strict check should become part of layout validation
- Test: `tests/test_orchestration.py`, `tests/test_agnt.py`
- Docs: `docs/RUN-ARTIFACTS.md`, `docs/ORCHESTRATION-LOOP.md` later in Task 11

**Steps:**
1. Add `agnt work health --json` or extend `agnt work audit` with runner/worktree/run-artifact checks.
2. Check git status for main checkout and known epic worktrees.
3. Check run artifacts against Beads status.
4. Check approval/decision beads referenced by runs are resolved before closure.
5. Check follow-up refs resolve to Beads before closure.
6. Add clear severities: failure, warning, info.
7. Wire only cheap/read-only health checks into `scripts/check-pi-config.sh`.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_orchestration.py -q
pi/agent/bin/agnt work audit --json
pi/agent/bin/agnt work health --json
scripts/check-pi-config.sh
```

**Expected result:** Rail-guard checks are deterministic, read-only unless explicit closeout mutation is requested, and suitable for CI/local checks.

### Task 10: Add autonomous self-improvement cadence triggers [Depends on: Tasks 2, 7, and 9]

**Context:** Maintenance work should be triggered after enough project activity, without hidden counters. Triggers derive from Beads, git, and run artifacts since the last closed maintenance bead.

**Files:**
- Create: `pi/agent/bin/agnt_lib/maintenance.py` or add to orchestration module
- Modify: `pi/agent/bin/agnt`
- Test: `tests/test_orchestration.py` or `tests/test_maintenance.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `docs/SELF-IMPROVEMENT-PRINCIPLES.md`, `docs/ORCHESTRATION-LOOP.md` later in Task 11

**Steps:**
1. Define maintenance labels: `maintenance:design-review`, `maintenance:architecture-review`, `maintenance:simplification`, `maintenance:workflow-retro`, `maintenance:context-health`.
2. Compute derived signals: closed implementation beads since last maintenance bead, commits since last maintenance bead, failed/blocked runs, repeated human blockers, context-health warnings, stale worktrees/runs, and recorded session volume since last lessons harvest.
3. Add `agnt maintenance due --json` and `agnt maintenance create-beads --dry-run` or equivalent under `agnt work maintenance`.
4. Add a lessons-harvest maintenance mode that reviews closed Beads, `.pi/runs`, worker session refs, and optional observational-memory summaries/recall ids for reusable lessons or follow-up Beads.
5. Let the runner auto-create maintenance review/planning beads when due, subject to pause/budget policy.
6. Auto-run read-only maintenance reviews; require approval metadata before implementation refactors.
7. Record maintenance closeout as normal Beads with evidence and updated checkpoint labels.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_maintenance.py tests/test_orchestration.py -q
pi/agent/bin/agnt work maintenance due --json
pi/agent/bin/agnt work maintenance create-beads --dry-run --json
```

**Expected result:** Maintenance triggers are auditable and reproducible from existing project state.

### Task 11: Documentation, instructions, and eval updates [Depends on: Tasks 1-10]

**Context:** User-visible workflow changes must be documented and instruction context must remain compact. Avoid dumping all daemon policy into `AGENTS.md`; keep detailed semantics in docs and tools.

**Files:**
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/ORCHESTRATION-LOOP.md`
- Modify: `docs/RUN-ARTIFACTS.md`
- Modify: `docs/SELF-IMPROVEMENT.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `pi/agent/bin/README.md`
- Modify: `pi/agent/AGENTS.md` only for compact operator guidance
- Modify/add: `pi/agent/evals/*` if new deterministic behavior needs eval coverage
- Test: docs/static checks and evals

**Steps:**
1. Document Beads as the durable work graph and Archimedes todos as ephemeral projections.
2. Document observational memory as a session-local recall/context layer and worker session recording as inspectable execution history.
3. Document ticket metadata fields and dispatch statuses.
4. Document runner lifecycle, pause/resume, singleton lock, session policy, memory policy, and budget seams.
5. Document Beads-backed ask/approval flow and closeout requirements.
6. Document one-worktree-per-epic policy.
7. Document maintenance cadence/self-improvement triggers, including lessons harvest from run artifacts and recorded sessions.
8. Update command reference for new `agnt` commands.
9. Add or update deterministic evals for instruction composition and workflow gates if needed.
10. Run context-health and project checks.

**Focused verification:**
```bash
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt action validate
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
scripts/check-pi-config.sh
```

**Expected result:** Docs and instructions describe the new system without bloating default context or weakening safety gates.

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `pi/agent/bin/agnt` | Tasks 1, 2, 7, 10 | Serialize command-map edits; add command families in small increments. |
| `pi/agent/bin/agnt_lib/work.py` | Tasks 2, 4, 7, 8, 9 | Prefer extracting new modules (`orchestration.py`, `runner.py`, `maintenance.py`, `health.py`) to keep `work.py` small. |
| `tests/test_agnt.py` | Tasks 1-10 | Prefer new focused test files to avoid one giant test module. |
| `docs/ORCHESTRATION-LOOP.md` | Tasks 5, 7, 8, 9, 10, 11 | Do one final docs pass in Task 11. |
| `pi/agent/bin/README.md` | Tasks 2, 3, 7, 10, 11 | Do one final command-reference pass in Task 11. |
| `pi/agent/AGENTS.md` | Tasks 6 and 11 | Keep changes compact and late; avoid adding detailed policy prose before tools exist. |
| `pi/agent/settings.json` | Task 0.5 | Add `pi-observational-memory` only after source/package review and explicit approval. |

## Parallelization Notes

- Task 0.5 should happen before implementation work so memory/session policy is settled.
- Tasks 1 and 2 are foundational and should be serial.
- Task 3 can proceed after Task 1 if it avoids runner/worktree files.
- Task 5 can be prototyped after Task 1 but should integrate after Task 4.
- Tasks 7-10 should be serial until the runner and health model stabilize.
- Documentation should be final, not concurrent with rapidly changing command names.

## Safety and Stop Conditions

Stop before implementation if:

- No Beads issue/epic exists for the implementation work.
- Current branch is `main` and same-branch implementation has not been explicitly approved.
- Working tree has unrelated uncommitted changes.
- Metadata fields, session policy, memory policy, or command names become ambiguous.
- Implementing the runner would require installing hooks, services, launch agents, or background startup behavior without explicit approval.
- A task requires pushing, merging, deleting branches/worktrees, resetting, cleaning, or changing Beads/Dolt history.
- Verification commands fail and the failure is not clearly pre-existing.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-08-beads-first-autonomous-orchestration-plan.md` (verify with `test -f`).
Recommended next skill: `executing-plans` after creating/assigning Beads and receiving explicit implementation approval; use `test-driven-development` for behavior changes and `verification-before-completion` before claiming completion.
