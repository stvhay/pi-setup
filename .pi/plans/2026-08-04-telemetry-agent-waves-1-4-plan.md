# Telemetry and Agent Workflow Waves 1–4 Implementation Plan

**Issue:** pi-4tg9 — Harden telemetry and agent workflow from 24-hour retrospective
**Design:** Bead epic `pi-4tg9`, human decision `pi-g3xv`, and read-only maps `/tmp/wave-map-peer-{1..5}.md`
**Date:** 2026-08-04
**Branch:** `feature/pi-4tg9-waves-1-4` after this plan reaches `main`

**Goal:** Complete all 26 Wave 1–4 Beads through dependency-aware isolated worktrees, contract-first package integration, test-first changes, review, and evidence-backed closeout without copying private telemetry or creating upstream forks by default.

**Architecture:** One clean integration worktree owns ordered local integration. Each Bead runs in its own child worktree based on the latest dependency-complete integration commit. Five package contract investigations run before affected implementation: pi-langfuse, BetterWright, Ponytail, Pi core, and Archimedes. Supported Pi extension, package-filter, lifecycle, CLI-adapter, and resource seams win over forks; an irreducible upstream boundary stops only affected Beads and creates a concrete human decision backed by synthetic proof.

**Acceptance Criteria:**
- [ ] Wave 1–4 cover exactly `pi-4tg9.1`–`.14` and `.17`–`.28`; Wave 5 `.15` and Wave 6 `.16` remain out of scope.
- [ ] All 26 Beads have an isolated project branch/worktree, exact likely files, TDD RED command, focused GREEN command, and broader verification profile.
- [ ] pi-langfuse, BetterWright, Ponytail, Pi core, and Archimedes receive explicit contract investigations before affected source edits.
- [ ] Human decision `pi-g3xv` is enforced: understand contracts first, prefer supported local composition/adapter seams, create no fork by default, and isolate irreducible upstream decisions with concrete proof.
- [ ] Shared-file branches are serialized in the stated order; no two workers concurrently edit the same hotspot.
- [ ] Every behavior change observes RED before production edits, then focused GREEN and broader regression checks.
- [ ] All Python commands use `/Users/hays/Projects/pi-setup/.venv/bin/python`; no worktree-local `.venv` is assumed or created.
- [ ] Private prompts, outputs, trace/session/observation IDs, raw errors, telemetry excerpts, credentials, and absolute private artifact paths never enter Git, Beads, reviews, or commit messages.
- [ ] A Bead closes only after its accepted implementation or supported package release is integrated, verified, documented, and committed.
- [ ] No push, remote fork/branch/PR, local merge, worktree removal, or branch deletion occurs without the approval required by project policy.

---

## Scope and dependency graph

### Wave inventory

| Wave | Beads | Count |
|---|---|---:|
| 1 — foundations and independent workflow work | `.1`, `.2`, `.5`, `.6`, `.7`, `.10`, `.20`, `.21`, `.24`, `.25`, `.26`, `.27`, `.28` | 13 |
| 2 — identity consumers and runtime controls | `.3`, `.4`, `.8`, `.9`, `.11`, `.17`, `.18`, `.22` | 8 |
| 3 — derived semantics | `.12`, `.13`, `.19`, `.23` | 4 |
| 4 — consolidated diagnostics | `.14` | 1 |
| **Total** | `pi-4tg9.1`–`.14`, `.17`–`.28` | **26** |

### Beads dependency DAG

```text
.2 ──┬── .3 ───────────────────────────────┐
     ├── .4 ───────────────────────────────┤
     ├── .8 ───────────────────────────────┤
     ├── .9 ──┬── .12                     │
     │        └── .13 ─────────────────────┤
     ├── .11 (also needs .10) ── .12      │
     ├── .17                               │
     └── .18 ── .19                       │
.1 ────────────────────────────────────────┤
.5 ────────────────────────────────────────┤
.6 ────────────────────────────────────────┤
.3/.4/.8/.13 ──────────────────────────────┤
                                           └── .14
.21 ── .22 ── .23
.7, .12, .14 ── .15  (Wave 5; out of scope)
.20, .24, .25, .26, .27, .28  (independent Beads; file conflicts still serialize)
```

Beads dependencies are necessary but not sufficient for parallel execution. File conflicts below add operational serialization edges.

## Non-negotiable boundaries

1. **Tracked source:** Edit `pi/`, `tests/`, and tracked docs only. Never edit installed runtime files under `~/.pi` as a solution.
2. **Private evidence:** Use synthetic fixtures for committed tests. Live acceptance may inspect private telemetry, but record only `PASS`/`FAIL`, generalized counts, and missing capability in Beads.
3. **Package ownership:** Installed package source is evidence, not an editable checkout. Reproduce in a clean upstream source checkout.
4. **No default fork:** A package-owned defect does not authorize fork creation, remote branches, PRs, vendoring, or pins to unpublished commits.
5. **Supported seams first:** Prefer Pi events (`message_end`, `agent_settled`, `session_shutdown`, `input`, `resources_discover`, `tool_result`), `prepareArguments`, package filters, first-class skill metadata, and existing `runAgntJson` CLI composition when they preserve the complete contract.
6. **No imitation seam:** Do not duplicate a package subsystem merely to avoid upstream work. A local adapter is acceptable only when the public contract exposes all required state and lifecycle ownership.
7. **One Bead, one atomic project commit:** Shared upstream releases may carry several atomic upstream commits, but each project Bead keeps distinct tests, evidence, and closeout.

---

## Shared environment and verification profiles

Every project worktree starts with:

```bash
ROOT=/Users/hays/Projects/pi-setup
WT_ROOT="$ROOT/.worktrees"
PY=/Users/hays/Projects/pi-setup/.venv/bin/python

test -x "$PY"
git status --short --branch
bd show <bead-id>
```

Never use `.venv/bin/python` from a child worktree; worktrees do not contain `.venv`.

### Project Full P0 — Python/config regression

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m ruff check pi/agent/bin/agnt_lib tests
"$PY" -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
git diff --check
```

### Project Full P1 — context/workflow regression

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m ruff check pi/agent/bin/agnt_lib tests
"$PY" -m pytest tests/test_agnt.py tests/test_context_architecture.py tests/test_instructions.py
pi/agent/bin/agnt action validate
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
scripts/check-pi-config.sh
git diff --check
```

### Project Full P2 — Langfuse/improvement regression

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest tests/test_langfuse_skill.py tests/test_langfuse_evaluators.py tests/test_improvement.py tests/test_subagent_workaround.py
"$PY" -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
git diff --check
```

### Project Full P3 — question/approval regression

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest tests/test_agent_os_compat.py tests/test_approvals.py tests/test_ticket_gateway.py tests/test_orchestrator_extension.py
"$PY" -m ruff check pi/agent/bin/agnt_lib tests
scripts/check-pi-config.sh
git diff --check
```

### Package verification rule

Before recording any upstream command in a Bead, inspect that checkout's `package.json`, lockfile, contributing docs, and test layout. Use its existing package manager and scripts. Do not run `npx` commands that download undeclared tools, and do not install dependencies into `~/.pi/agent/npm` or the live Ponytail checkout.

---

## Isolated worktree topology

### Integration worktree

After this plan is merged to `main` and explicit implementation starts:

```bash
ROOT=/Users/hays/Projects/pi-setup
cd "$ROOT"
git status --short
git check-ignore -q .worktrees
git worktree add ".worktrees/feature/pi-4tg9-waves-1-4" \
  -b "feature/pi-4tg9-waves-1-4" main
```

Stop if `main`, target path, or integration branch is dirty/ambiguous. Do not fetch, push, or merge as part of setup.

### Child branch/worktree matrix

Each child branch is created from the latest integration commit containing all declared dependencies and earlier conflict-lane commits.

| Bead | Branch | Worktree path | Base gate |
|---|---|---|---|
| `.1` | `fix/pi-4tg9-1-zero-cost` | `.worktrees/fix/pi-4tg9-1-zero-cost` | contract C1 |
| `.2` | `feature/pi-4tg9-2-invocation-schema` | `.worktrees/feature/pi-4tg9-2-invocation-schema` | Wave 1 base |
| `.3` | `fix/pi-4tg9-3-session-identity` | `.worktrees/fix/pi-4tg9-3-session-identity` | `.2`, C1 |
| `.4` | `fix/pi-4tg9-4-worker-finalization` | `.worktrees/fix/pi-4tg9-4-worker-finalization` | `.2`, C1 |
| `.5` | `fix/pi-4tg9-5-trace-pagination` | `.worktrees/fix/pi-4tg9-5-trace-pagination` | Wave 1 base |
| `.6` | `fix/pi-4tg9-6-tool-byte-metadata` | `.worktrees/fix/pi-4tg9-6-tool-byte-metadata` | C1, after `.1` source lane |
| `.7` | `fix/pi-4tg9-7-media-string-bounds` | `.worktrees/fix/pi-4tg9-7-media-string-bounds` | C1, after `.6` source lane |
| `.8` | `fix/pi-4tg9-8-model-dimensions` | `.worktrees/fix/pi-4tg9-8-model-dimensions` | `.2` |
| `.9` | `fix/pi-4tg9-9-execution-outcome` | `.worktrees/fix/pi-4tg9-9-execution-outcome` | `.2`, after `.8` conflict lane |
| `.10` | `feature/pi-4tg9-10-runtime-directory` | `.worktrees/feature/pi-4tg9-10-runtime-directory` | Wave 1 base |
| `.11` | `feature/pi-4tg9-11-parent-artifacts` | `.worktrees/feature/pi-4tg9-11-parent-artifacts` | `.2`, `.10`, after `.9` conflict lane |
| `.12` | `fix/pi-4tg9-12-artifact-evaluation` | `.worktrees/fix/pi-4tg9-12-artifact-evaluation` | `.9`, `.11`, after `.13` conflict lane |
| `.13` | `feature/pi-4tg9-13-error-taxonomy` | `.worktrees/feature/pi-4tg9-13-error-taxonomy` | `.2`, `.9` |
| `.14` | `feature/pi-4tg9-14-cohort-health` | `.worktrees/feature/pi-4tg9-14-cohort-health` | `.1`, `.3`, `.4`, `.5`, `.6`, `.8`, `.13` |
| `.17` | `feature/pi-4tg9-17-provider-circuits` | `.worktrees/feature/pi-4tg9-17-provider-circuits` | `.2`, after `.11` conflict lane |
| `.18` | `feature/pi-4tg9-18-subagent-budgets` | `.worktrees/feature/pi-4tg9-18-subagent-budgets` | `.2`, C5, after `.17` conflict lane |
| `.19` | `fix/pi-4tg9-19-error-breaker` | `.worktrees/fix/pi-4tg9-19-error-breaker` | `.18`, C5 |
| `.20` | `fix/pi-4tg9-20-browser-evidence-scope` | `.worktrees/fix/pi-4tg9-20-browser-evidence-scope` | C2 |
| `.21` | `feature/pi-4tg9-21-question-selection-mode` | `.worktrees/feature/pi-4tg9-21-question-selection-mode` | C5 ask contract |
| `.22` | `feature/pi-4tg9-22-question-custom-input` | `.worktrees/feature/pi-4tg9-22-question-custom-input` | `.21`, C5 ask contract |
| `.23` | `chore/pi-4tg9-23-question-routing` | `.worktrees/chore/pi-4tg9-23-question-routing` | `.21`, `.22` |
| `.24` | `fix/pi-4tg9-24-context-budget-warning` | `.worktrees/fix/pi-4tg9-24-context-budget-warning` | Wave 1 base |
| `.25` | `chore/pi-4tg9-25-ponytail-discovery` | `.worktrees/chore/pi-4tg9-25-ponytail-discovery` | C3; serialize against current context/test owner |
| `.26` | `feature/pi-4tg9-26-skill-body-cache` | `.worktrees/feature/pi-4tg9-26-skill-body-cache` | C4; serialize against current context/test owner |
| `.27` | `chore/pi-4tg9-27-closeout-routing` | `.worktrees/chore/pi-4tg9-27-closeout-routing` | after `.24` conflict lane |
| `.28` | `feature/pi-4tg9-28-direct-work-start` | `.worktrees/feature/pi-4tg9-28-direct-work-start` | after `.27` conflict lane |

Creation template:

```bash
INTEGRATION=/Users/hays/Projects/pi-setup/.worktrees/feature/pi-4tg9-waves-1-4
BRANCH=<branch-from-table>
PATH=/Users/hays/Projects/pi-setup/.worktrees/$BRANCH

git -C "$INTEGRATION" status --short
git -C "$INTEGRATION" worktree add "$PATH" -b "$BRANCH" \
  feature/pi-4tg9-waves-1-4
```

Do not create all 26 worktrees at once. Create only ready worktrees whose dependencies and contract gates are satisfied; this prevents stale-base branches and needless rebases.

---

## Contract investigations — mandatory before affected edits

Contract work is read-only until a supported seam is selected. Use detached or isolated clean source checkouts under `/tmp/pi-4tg9-contracts/`; never edit installed runtime package files. Persist only generalized proof in the affected Bead notes.

Every investigation must produce this **contract dossier**:

1. package/repository identity, installed version/commit, manifest scripts, and public entrypoints;
2. synthetic minimal reproducer and expected failing assertion;
3. exact owner symbol and event/call chain;
4. supported local composition seams tested, with pass/fail reason;
5. privacy/lifecycle/backward-compatibility constraints;
6. smallest likely upstream change and official focused/full tests;
7. consumable integration artifact needed: released version, public commit, or no package change;
8. stop decision if local acceptance cannot be met.

No dossier may contain private telemetry, user content, raw provider errors, credentials, or private identifiers.

### C1: pi-langfuse contract investigation (`.1`, `.3`, `.4`, `.6`, `.7`)

**Installed evidence only:**
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/package.json`
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/index.ts`
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/src/utils.ts`
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/src/state.ts`
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/src/langfuse.ts`
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/src/handlers/generation.ts`
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/src/handlers/tool.ts`
- `/Users/hays/.pi/agent/npm/node_modules/pi-langfuse/src/redaction.ts`
- upstream repository declared by package: `github.com/gooyoung/pi-langfuse`

**Questions to prove:**
- Does `extractCostDetails()` distinguish absent cost from explicit all-zero cost?
- Which Pi event ordering determines whether local `message_end` mutation reaches generation export?
- Can public `runWithSession()`/`shutdownRuntime()` exports plus Pi `agent_settled`/`session_shutdown` provide a complete local adapter, or are they internal and order-dependent?
- Does session resolution expose session manager ID and `PI_SESSION_ID` without mutable global fallback?
- At what point does `shapePayload()` truncate provider media, and can capture policy preserve a complete extraction marker while bounding ordinary strings?
- Are tool bytes measured before capture policy removal, after shaping, or from a fabricated `undefined` serialization?

**Synthetic proof commands in a clean upstream checkout:**

```bash
node -e 'const p=require("./package.json"); console.log(p.name,p.version,p.scripts)'
rg -n 'extractCostDetails|shapePayload|estimatePayloadBytes|agent_end|shutdownRuntime|runWithSession|currentSessionId' index.ts src test
npm install --ignore-scripts
npx --no-install tsx --test test/*.test.ts
npm run typecheck
```

If `npm install --ignore-scripts` conflicts with upstream development docs, use the documented install command instead and record why. Never supply live Langfuse credentials to contract tests.

**Preferred seams in order:** existing local `message_end` mutation; Pi lifecycle hook plus documented package export; package-supported payload/capture option; upstream package fix. Reject duplicate custom generation export or copied shaping code.

**Irreducible proof gate:** Before asking for upstream action, show that a synthetic event passes through the local seam yet the package owner function loses the required field/state. Then create one Beads-backed question covering the minimal package action; default remains wait for/support upstream, not create a fork.

### C2: BetterWright contract investigation (`.20`)

**Installed evidence only:**
- `/Users/hays/.pi/agent/npm/node_modules/betterwright/package.json`
- `/Users/hays/.pi/agent/npm/node_modules/betterwright/types/pi-extension.d.ts`
- `/Users/hays/.pi/agent/npm/node_modules/betterwright/dist/src/pi-extension.js`
- upstream repository declared by package: `github.com/BetterWright/betterwright`

**Likely upstream files in a clean checkout:**
- `src/pi-extension.ts`
- `tests/node/pi-extension.test.js`
- `tests/unit/pi-extension.test.ts` if present
- `types/pi-extension.d.ts`

**Questions to prove:**
- Is evidence state scoped only to the extension closure (`checklistInitialized`, `evidenceChecklist`)?
- Can a task ID/reset be supplied through an existing option or public API?
- Can Pi `tool_call`/`tool_result` middleware safely reset the original closure? If not, document why tool override cannot call the original execute contract.
- What terminal states distinguish completed, audited, and pending requirements?

**Commands:**

```bash
node -e 'const p=require("./package.json"); console.log(p.name,p.version,p.scripts)'
rg -n 'checklistInitialized|evidenceChecklist|initialize|prove|audit|reset|taskId' src tests types
npm install --ignore-scripts
npm run typecheck
npm run test:unit
npm test
```

Use the repository's documented install if scripts are required. A local wrapper is allowed only if BetterWright exposes a supported delegate/reset API and wrong-task protection remains enforceable. Otherwise `.20` waits for a released package fix or a separately approved upstream strategy.

### C3: Ponytail contract investigation (`.25`)

**Existing source checkout evidence:**
- `/Users/hays/.pi/agent/git/github.com/DietrichGebert/ponytail/pi-extension/index.js`
- `/Users/hays/.pi/agent/git/github.com/DietrichGebert/ponytail/hooks/ponytail-instructions.js`
- `/Users/hays/.pi/agent/git/github.com/DietrichGebert/ponytail/skills/ponytail*/SKILL.md`
- `/Users/hays/.pi/agent/git/github.com/DietrichGebert/ponytail/pi-extension/test/extension.test.js`
- installed Pi `docs/skills.md` and `docs/packages.md`

The live checkout currently has an unrelated untracked `package-lock.json`; do not edit, clean, stage, or use that checkout as an implementation branch. Use a detached worktree from its recorded commit or a fresh clean checkout.

**Questions to prove:**
- Does first-class `disable-model-invocation: true` hide a skill from discovery while retaining `/skill:name`?
- Which Ponytail skills are command-only, and which active-mode body is already injected by `before_agent_start`?
- Do package filters remove the skill command entirely? Verify aliases that call `/skill:ponytail-*` still resolve.
- Is there any package metadata override that can add frontmatter without copying skill bodies? If not, local overlay copies are rejected as maintained forks.

**Commands:**

```bash
node --test pi-extension/test/*.test.js
node --test tests/commands.test.js tests/package.test.js
npm test
rg -n 'disable-model-invocation|/skill:ponytail|before_agent_start|getPonytailInstructions' pi-extension hooks skills tests
```

Preferred result is an upstream metadata-only patch followed by a pinned public commit/release. Do not remove package skills or duplicate their bodies locally merely to shrink discovery.

### C4: Pi core contract investigation (`.26`)

**Installed evidence only:**
- `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/docs/skills.md`
- `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/docs/extensions.md`
- `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/docs/packages.md`
- `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/skills.js`
- `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/resource-loader.js`
- `/Users/hays/.local/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js`
- upstream repository declared by package: `github.com/earendil-works/pi`, package directory `packages/coding-agent`

**Likely upstream files:**
- `packages/coding-agent/src/core/skills.ts`
- `packages/coding-agent/src/core/resource-loader.ts`
- `packages/coding-agent/src/core/agent-session.ts`
- `packages/coding-agent/test/skills.test.ts`
- `packages/coding-agent/test/resource-loader.test.ts`
- `packages/coding-agent/test/agent-session.test.ts`

**Questions to prove:**
- Does repeated `_expandSkillCommand()` synchronously reread the same file?
- Can the supported pre-expansion `input` event plus `pi.getCommands()` `sourceInfo.path` implement exact session-local path+file-version caching without changing argument expansion or errors?
- Does `/reload` recreate extension state and invalidate cached bodies?
- What explicit reread syntax can remain user-controlled without shadowing normal `/skill:name` semantics?
- Would a local adapter reproduce too much private `_expandSkillCommand()` behavior? If yes, stop at Pi core.

**Commands in a clean Pi source checkout:**

```bash
node -e 'const p=require("./packages/coding-agent/package.json"); console.log(p.name,p.version,p.scripts)'
rg -n '_expandSkillCommand|loadSkillFromFile|updateSkillsFromPaths|resources_discover|reload' packages/coding-agent/src packages/coding-agent/test
npm install --ignore-scripts
npm test --workspace packages/coding-agent -- skills resource-loader agent-session
npm test --workspace packages/coding-agent
```

Use the actual workspace syntax declared by the checked-out root manifest if it differs; record it before edits. Prefer a small tracked extension only if it can delegate all canonical expansion behavior. Otherwise `.26` requires a Pi core release; this repository has no Pi-core version pin, so package release/installation remains an explicit external gate.

### C5: Archimedes ask and subagent contracts (`.18`, `.19`, `.21`, `.22`)

**Installed evidence only:**
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/ask/src/index.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/ask/src/selection.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/ask/src/picker.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/ask/src/dialog.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/subagent/src/types.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/subagent/src/stream.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/subagent/src/handlers.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/subagent/src/execute.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/subagent/src/spawn.ts`
- `/Users/hays/.pi/agent/npm/node_modules/@pi-archimedes/subagent/src/index.ts`

Package manifests expose source but no repository URL or package test script. That absence is part of the dossier: identify the authoritative source/release path before any upstream proposal.

**Questions to prove:**
- Ask: can `selectionMode` replace optional `multi` through `prepareArguments`, while preserving single/multi custom input in TUI, RPC adapter, and child ask socket protocol?
- Ask: which source owns keyboard/accessibility behavior and result cardinality?
- Subagent: are usage/tool/turn events visible only inside `stream.ts`?
- Subagent: does `executeParallel()` share one parent abort signal across children?
- Subagent: can any public parent hook stop one child while preserving siblings and partial output? A parent `ctx.abort()` is not acceptable proof.
- Breaker: where can canonical tool name+input+normalized failure be observed, and what event resets the consecutive count?

**Commands after locating a clean authoritative checkout:**

```bash
node -e 'for (const p of ["packages/ask/package.json","packages/subagent/package.json","package.json"]) { try { const x=require("./"+p); console.log(p,x.name,x.version,x.scripts) } catch {} }'
rg -n 'multi|customInput|ask_request|ask_response|tool_execution_start|tool_execution_end|AbortController|signal|usage|stopReason' packages src
npm install --ignore-scripts
npm test -- packages/ask packages/subagent
npm test
```

If those paths/scripts differ, the investigator must replace them with manifest-backed exact commands in Bead notes before editing. Prefer upstream extension options or exported stream controls. Replacing the whole `subagent` tool locally is a maintained fork and needs a separate decision.

### Upstream decision protocol

When a contract dossier proves no complete supported local seam:

1. Leave affected Bead open and mark implementation outcome `partial`, not success.
2. Attach only generalized synthetic proof to Bead notes.
3. Create one durable Beads-backed question/approval for the smallest package-specific action with options such as:
   - wait for or request an upstream release;
   - approve a bounded local source branch and temporary public commit pin;
   - approve vendoring only the required adapter boundary;
   - defer the affected Bead.
4. Preview exact files, package pin changes, tests, rollback, and downstream blockers.
5. Do not create a GitHub fork, push, PR, unpublished pin, or vendored copy until that decision explicitly authorizes it.

---

## Wave 1 tasks

### pi-4tg9.1 — restore zero-cost subscription generations

**Depends on:** C1 and resolved `pi-g3xv`. **Conflict lane:** pi-langfuse `.1 → .6 → .7 → .3 → .4`.

**Likely files:**
- Project: `tests/test_langfuse_skill.py`, `pi/agent/settings.json` only when consuming a released fix, `pi/README.md` only if behavior text changes.
- Upstream if irreducible: `src/utils.ts`, `src/handlers/generation.ts`, `test/utils.test.ts`, `test/generation.test.ts`.
- Reference, do not edit as solution: `pi/agent/extensions/langfuse-config-env.ts`.

**TDD RED:** Add an integration-shaped fake generation assertion showing preserved runtime model ID and explicit zero `costDetails` after package export.

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_langfuse_skill.py -k emitted_generation_preserves_explicit_zero_cost
```

Expected RED: generated observation omits explicit zero cost or receives nonzero/default cost while model ID remains unchanged.

**Steps:**
1. Prove local `message_end` mutation already sets zero cost and identify the later loss seam.
2. Implement the smallest contract-preserving fix selected by C1; never alias/change runtime model ID.
3. Cover metered provider passthrough.
4. If package-owned, verify a clean upstream checkout, then consume only a released/approved artifact in `pi/agent/settings.json`.
5. Run one bounded live/integration smoke privately; record only pass/fail.

**Focused GREEN:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_langfuse_skill.py tests/test_pi_packages.py -k 'zero_cost or langfuse'
```

**Upstream focused/full if used:**

```bash
npx --no-install tsx --test test/utils.test.ts test/generation.test.ts
npm test
npm run typecheck
```

**Broader:** Project Full P2, then P0 before integration. **Stop:** no package artifact/pin or no private live/integration proof means leave `.1` open.

### pi-4tg9.2 — canonical invocation ID and telemetry schema

**Depends on:** none. Integrate first because seven Wave 2/3 Beads consume it.

**Likely files:**
- `pi/agent/bin/agnt_lib/metrics.py`
- `pi/agent/bin/agnt_lib/invoke.py`
- `pi/agent/bin/agnt_lib/runs.py`
- `pi/agent/extensions/subagent-error-workaround.ts`
- `tests/test_agnt.py`
- `tests/test_runner.py`
- `tests/test_subagent_workaround.py`
- `docs/RUN-ARTIFACTS.md`
- `docs/AGNT-SYSTEM.md`
- `pi/agent/bin/README.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_agnt.py tests/test_runner.py tests/test_subagent_workaround.py \
  -k 'canonical_invocation_id or telemetry_schema_v2 or legacy_metrics_record'
```

Expected RED: start/result/metrics/artifacts cannot join on one payload-free ID; legacy v1 reader case must remain readable.

**Steps:**
1. Specify additive schema v2: collision-resistant invocation ID generated once, parent session/work item, normalized provider/model/target, execution status, failure class, usage, duration, and bounded artifact refs.
2. Keep `recordId` as backward-compatible selector; do not derive invocation identity from payload or child index.
3. Thread one ID through direct invoke, run bundles, Archimedes single/parallel projections, and metric compaction.
4. Generate sibling child IDs once per invocation; index is metadata only.
5. Update schema docs and v1 compatibility tests.

**Focused GREEN:** same command without expecting failure. **Broader:** P0 and P2.

### pi-4tg9.5 — paginate improvement trace discovery truthfully

**Depends on:** none. **Conflict:** serialize before `.9`, `.13`, `.12`, and `.14` edits to `improvement.py`/tests.

**Likely files:**
- `pi/agent/bin/agnt_lib/langfuse.py`
- `pi/agent/bin/agnt_lib/improvement.py`
- `tests/test_improvement.py`
- `pi/agent/bin/README.md`
- `docs/SELF-IMPROVEMENT.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_improvement.py \
  -k 'trace_discovery_reports_lower_bounds or trace_discovery_paginates or legacy_list_traces'
```

Expected RED: hidden `MAX_TRACE_READ=500` cap appears complete, pagination metadata is discarded, or unattributed traces disappear.

**Steps:**
1. Preserve `list_traces(...) -> list[dict]` for callers; add a metadata-bearing iterator/result seam beside it.
2. Paginate to API end or explicit operator limit; never infer completion from a full page.
3. Report total available when API supplies it, scanned, attributable, unattributed, complete, and continuation reason/state.
4. Keep per-session trace and observation caps visible and unchanged unless tests prove a required correction.
5. Add CLI option only if needed to expose an operator limit; do not add a second scanner.

**Focused GREEN:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_improvement.py -k 'trace_discovery or list_traces or pagination'
"$PY" -m ruff check pi/agent/bin/agnt_lib/langfuse.py pi/agent/bin/agnt_lib/improvement.py tests/test_improvement.py
```

**Broader:** P2 and P0.

### pi-4tg9.6 — truthful tool payload byte metadata

**Depends on:** C1. **Conflict lane:** after `.1`, before `.7`.

**Likely files:**
- Project: `tests/test_langfuse_skill.py`, `pi/agent/settings.json` only for released package consumption.
- Upstream if irreducible: `src/handlers/tool.ts`, `src/utils.ts`, `src/types.ts`, `test/tool.test.ts`.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_langfuse_skill.py -k tool_payload_bytes
```

Expected RED: disabled capture reports a fabricated constant rather than absent/unavailable size.

**Steps:**
1. Define names for unavailable, captured bounded serialized size, and any intentionally pre-redaction measurement.
2. Under `conversations`, emit no tool payload and null/omit unavailable byte fields.
3. Under `full-debug`, measure the same bounded serialization actually exported.
4. Ensure no private payload enters fixtures or assertion messages.

**Focused GREEN:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_langfuse_skill.py -k 'tool_payload_bytes or privacy'
```

**Upstream focused/full if used:**

```bash
npx --no-install tsx --test test/tool.test.ts
npm test
npm run typecheck
```

**Broader:** P2 and P0. **Stop:** no released/approved package artifact means no Bead close.

### pi-4tg9.7 — finite strings without corrupting media

**Depends on:** C1. **Conflict lane:** after `.6`.

**Likely files:**
- `pi/agent/extensions/langfuse-config-env.ts`
- `tests/test_langfuse_skill.py`
- `pi/agent/settings.json` only for released package consumption
- Upstream if irreducible: `src/utils.ts`, `src/redaction.ts`, `src/limits.ts`, `test/utils.test.ts`.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_langfuse_skill.py -k media_round_trip_and_bounded_strings
```

Expected RED: finite cap corrupts media extraction, while current global `off` workaround leaves ordinary strings unbounded.

**Steps:**
1. Use complete media extraction/marker before ordinary string truncation; remove retained raw base64.
2. Restore a documented finite default in tracked config by removing unconditional `PI_LANGFUSE_MAX_STRING_LENGTH=off`.
3. Preserve explicit operator overrides, including `off`.
4. Test malformed/large media and large ordinary strings with synthetic data only.
5. Run a private live media smoke without committing payload or IDs.

**Focused GREEN:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_langfuse_skill.py -k 'media or bounded_strings or max_string'
```

**Upstream focused/full if used:**

```bash
npx --no-install tsx --test test/utils.test.ts
npm test
npm run typecheck
```

**Broader:** P2 and P0.

### pi-4tg9.10 — safe private runtime directory

**Depends on:** none. Integrate before `.11`.

**Chosen local architecture to test first:** one Python policy authority exposed as bounded JSON through `agnt`, consumed by TypeScript through existing `runAgntJson`; do not implement divergent Python and TypeScript path policies.

**Likely files:**
- Create: `pi/agent/bin/agnt_lib/runtime_paths.py`
- Modify: `pi/agent/bin/agnt`
- Modify: `pi/agent/bin/agnt_lib/metrics.py`
- Modify: `pi/agent/bin/agnt_lib/runs.py`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Reuse: `pi/agent/extensions/lib/run-agnt-json.ts`
- Create: `tests/test_runtime_artifacts.py`
- Modify: `tests/test_subagent_workaround.py`
- Modify: `tests/test_agnt.py`
- Modify: `docs/RUN-ARTIFACTS.md`
- Modify: `pi/agent/bin/README.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_runtime_artifacts.py tests/test_subagent_workaround.py \
  -k 'runtime_directory or tracked_path or global_fallback or private_permissions'
```

Expected RED: current fallback chooses `cwd/.pi` without proving it is ignored/untracked.

**Steps:**
1. Resolve a valid Git root without assuming `.git` is a directory.
2. Accept project `.pi/<kind>` only when Git proves the candidate is ignored and no candidate path is tracked.
3. Otherwise use mode-0700 global storage keyed by SHA-256 of canonical repository/non-Git identity; expose no raw identity in path or output.
4. Cover no-Git, missing Git, worktree `.git` file, tracked `.pi`, unignored `.pi`, symlinks, permissions, and deterministic collision-safe keys.
5. Route metrics, annotations, runs, and subagent artifact callers through the one policy seam only to the extent required by Bead scope.

**Focused GREEN:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_runtime_artifacts.py tests/test_subagent_workaround.py tests/test_agnt.py
"$PY" -m ruff check pi/agent/bin/agnt_lib/runtime_paths.py pi/agent/bin/agnt_lib/metrics.py pi/agent/bin/agnt_lib/runs.py tests
```

**Broader:** P0.

### pi-4tg9.20 — scope browser evidence checklists per task

**Depends on:** C2. Likely upstream-owned.

**Likely files:**
- Project integration: `pi/agent/settings.json`, `tests/test_pi_packages.py`, `docs/extension-web-compatibility.md`.
- Upstream: `src/pi-extension.ts`, `types/pi-extension.d.ts`, `tests/node/pi-extension.test.js`, package unit test for evidence state.

**TDD RED:** Upstream test initializes/audits task A, initializes task B, rejects wrong-task prove/audit, and requires acknowledged reset for pending A. Project RED proves the fixed BetterWright version is pinned once available.

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_pi_packages.py -k betterwright_evidence_task_version_is_pinned
```

**Steps:**
1. Require `taskId` on initialize/prove/audit, or prove a backward-compatible generated task ID contract.
2. Allow replacement only after completed/audited state; pending state requires explicit acknowledged reset.
3. Reject stale/wrong task IDs.
4. Prefer a BetterWright-supported reset/API. Do not override `browser_evidence` without a delegate to its original execution contract.
5. Consume only released/approved version; update compatibility matrix carrying version.

**Upstream focused/full:**

```bash
npm run build:harness
node --test tests/node/pi-extension.test.js
npm run typecheck
npm run test:unit
npm test
```

C2 must correct the focused test path if the clean checkout uses another exact file. **Project focused GREEN:** the RED command plus `scripts/check-pi-config.sh`. **Broader:** P0. **Stop:** no supported local reset and no release means `.20` remains open.

### pi-4tg9.21 — explicit single/multi question mode

**Depends on:** C5 ask contract. Integrate before `.22`.

**Likely files:**
- `pi/agent/extensions/agent-os-compat.ts`
- `pi/agent/extensions/beads-ask-bridge.ts`
- `pi/agent/bin/agnt_lib/approvals.py`
- `tests/test_agent_os_compat.py`
- `tests/test_approvals.py`
- `tests/test_ticket_gateway.py` for semantic guards only
- `docs/extension-web-compatibility.md`
- Upstream Archimedes ask if required: `packages/ask/src/index.ts`, `selection.ts`, `dialog.ts`, ask tests.

**Contract:** `selectionMode: "single" | "multi"`; keep legacy `multi` only through `prepareArguments`/reader compatibility, not in the new public schema. Single returns exactly one predefined selection or one non-empty custom input. Multi returns zero or more predefined selections plus optional custom input.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_agent_os_compat.py tests/test_approvals.py \
  -k 'selection_mode or question_mode or single_cardinality or multi_cardinality'
```

Expected RED: omission silently defaults to single and durable metadata loses cardinality.

**Steps:**
1. Require `selectionMode` in transient RPC and durable question schemas.
2. Add `prepareArguments` migration from old `multi` where Pi tool contract supports it.
3. Persist selection mode in Beads metadata and preserve old records as legacy single-select.
4. Keep approvals confirm-only; typed text never authorizes approval.
5. Enforce kind-specific outcomes: question cannot resolve `approved`; approval cannot resolve `answered`.
6. Cover normal TUI through Archimedes ask release or an exact supported seam; RPC-only success is not full acceptance.

**Focused GREEN:** same command plus:

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_ticket_gateway.py -k 'approved or answered'
```

**Broader:** P3 and P0. **Stop:** if normal TUI remains optional-`multi`, leave `.21` open and isolate package decision.

### pi-4tg9.24 — warn before context budget exhaustion

**Depends on:** none. **Conflict lane:** `.24 → .27 → .28` for `tests/test_agnt.py` and command docs.

**Likely files:**
- `pi/agent/bin/agnt_lib/context_health.py`
- `tests/test_agnt.py`
- `tests/test_context_architecture.py`
- `pi/agent/bin/README.md`
- `docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_agnt.py tests/test_context_architecture.py \
  -k 'context_health and discovery and warning'
```

Expected RED: near-limit discovery reports remaining headroom but no warning/top contributors.

**Steps:**
1. Track per-skill discovery contribution while reusing current scan.
2. Add configurable warning-remaining threshold below hard limit.
3. Report used, limit, remaining, threshold, and largest contributors.
4. Preserve hard-limit failure and below-threshold no-warning behavior.

**Focused GREEN:** same command without expected failure, then:

```bash
pi/agent/bin/agnt context-health --strict
```

**Broader:** P1 and P0.

### pi-4tg9.25 — remove Ponytail discovery duplicates

**Depends on:** C3. Likely package-owned metadata.

**Likely files:**
- Project integration: `pi/agent/settings.json` only to pin approved public commit/release, `tests/test_pi_packages.py`, `tests/test_context_architecture.py`, `docs/extension-web-compatibility.md`.
- Upstream: `skills/ponytail/SKILL.md`, `skills/ponytail-{review,audit,debt,gain,help}/SKILL.md`, `pi-extension/index.js`, `pi-extension/test/extension.test.js`, package tests.

**TDD RED:** Add package tests proving command-only/active skills are absent from `formatSkillsForPrompt`, while `/skill:*` and Ponytail alias commands still resolve.

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_pi_packages.py tests/test_context_architecture.py \
  -k 'ponytail and discovery'
```

**Steps:**
1. Add first-class `disable-model-invocation: true` only to explicitly command-only skills and active mode body already injected by extension.
2. Preserve explicit skill commands and all aliases.
3. Measure discovery character reduction deterministically; do not use private session token data.
4. Do not filter all Ponytail skills in settings or maintain copied overlay skill bodies.
5. Pin an approved public commit/release rather than leaving behavior dependent on moving `main`.

**Upstream focused/full:**

```bash
node --test pi-extension/test/extension.test.js tests/commands.test.js tests/package.test.js
npm test
```

**Project focused GREEN:** RED command plus `pi/agent/bin/agnt context-health --strict`. **Broader:** P1 and P0.

### pi-4tg9.26 — reuse unchanged skill bodies per session

**Depends on:** C4.

**Likely files if supported local adapter is complete:**
- Create: `pi/agent/extensions/skill-command-cache.ts`
- Create or modify: `tests/test_instructions.py`
- Modify: `tests/test_context_architecture.py`
- Modify: `docs/AGNT-SYSTEM.md`
- Modify: `docs/extension-web-compatibility.md`

**Likely Pi core files if adapter cannot preserve the contract:** C4 paths in `packages/coding-agent/src/core/{agent-session,resource-loader,skills}.ts` and matching tests.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_instructions.py tests/test_context_architecture.py \
  -k 'skill_body_cache or unchanged_skill or explicit_reread'
```

Required cases: second unchanged expansion performs no read; mtime/content version change rereads; cache is session-local; `/reload` and explicit reread invalidate; unknown/read-error behavior remains canonical.

**Steps:**
1. Attempt supported `input` + `pi.getCommands()` composition only after C4 proves exact expansion delegation.
2. Cache by resolved path plus stable file version/stat within one extension/session runtime.
3. Preserve frontmatter stripping, relative reference preface, args, unknown-skill pass-through, and extension error behavior.
4. If reproducing private `_expandSkillCommand()` logic is required, reject adapter and stop for Pi core release.
5. Do not add a global cross-session cache.

**Focused GREEN:** same project command if local. **Pi upstream focused/full if used:**

```bash
npm test --workspace packages/coding-agent -- skills resource-loader agent-session
npm test --workspace packages/coding-agent
```

C4 must replace syntax with manifest-backed equivalent if needed. **Broader:** P1 and P0. **Stop:** repository cannot pin Pi core; close only after supported local adapter or verified installed upstream release.

### pi-4tg9.27 — closeout skill selection/subsumption

**Depends on:** none, but serialize after `.24`.

**Likely files:**
- `pi/agent/actions/finish.md`
- `pi/agent/skills/finishing-a-development-branch/SKILL.md`
- `pi/agent/bin/agnt_lib/actions.py` only if validation needs explicit phase metadata
- `tests/test_context_architecture.py`
- `tests/test_agnt.py`
- `pi/agent/evals/workflow-gate-smoke/eval.json`
- `pi/agent/evals/workflow-gate-smoke/prompt.md`
- `docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_context_architecture.py tests/test_agnt.py \
  -k 'finish or closeout or subsumption'
```

Expected RED: no machine-checked trigger/subsumption matrix proves one coordinator while retaining verification/docs/review gates.

**Steps:**
1. Keep `finishing-a-development-branch` as sole `finish` action coordinator.
2. Encode compact matrix: verification always; docs/review when triggered; simplification only post-verification when requested/useful; session extraction only at substantial wrap-up/Bead close.
3. State which generic prose/simplification guidance coordinator subsumes without weakening safety.
4. Add representative eval assertions; avoid adding another closeout skill.

**Focused GREEN:** same command, then:

```bash
pi/agent/bin/agnt action validate
pi/agent/bin/agnt eval run role-context-smoke
```

**Broader:** P1 and P0.

### pi-4tg9.28 — idempotent direct-work lifecycle start

**Depends on:** none, but serialize after `.27`.

**Likely files:**
- `pi/agent/bin/agnt_lib/work.py`
- `pi/agent/bin/agnt_lib/improvement.py`
- `tests/test_agnt.py`
- `tests/test_improvement.py`
- `pi/agent/bin/README.md`
- `docs/AGNT-SYSTEM.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_agnt.py tests/test_improvement.py \
  -k 'direct_start or direct_work or idempotent_link or no_run_bundle'
```

Expected RED: no lightweight command combines show/validate, optional claim, and current-session link without creating `.pi/runs`.

**Steps:**
1. Add one `agnt work direct-start` subcommand; do not create a parallel top-level tool.
2. Validate/show Bead, optionally claim idempotently, then link the current session.
3. Use `PI_SESSION_ID` fallback when `PI_SESSION_FILE` is absent, matching canonical session contract; never choose unrelated current/default session.
4. Return stable JSON with per-stage success/failure and exact repair command.
5. Prove already-claimed/already-linked success and empty temp runs directory.
6. Preserve direct Pi as default; do not call `create_run_bundle`.

**Focused GREEN:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_agnt.py tests/test_improvement.py -k 'direct_start or improve_link'
pi/agent/bin/agnt work -h
```

**Broader:** P1 and P0.

---

## Wave 2 tasks

### pi-4tg9.3 — canonical session identity on every trace

**Depends on:** `.2`, C1. **Conflict:** after `.7` in pi-langfuse lane; before `.4`.

**Likely files:**
- `pi/agent/extensions/subagent-error-workaround.ts`
- `tests/test_subagent_workaround.py`
- `tests/test_langfuse_skill.py`
- `pi/agent/settings.json` only for released package
- Upstream: `index.ts`, `src/state.ts`, `src/langfuse.ts`, session tests.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_subagent_workaround.py tests/test_langfuse_skill.py -k session_id_fallback
```

Required failures: session-file ID, `PI_SESSION_ID` fallback, explicit unavailable reason, and concurrent isolation.

**Steps:**
1. Resolve session manager ID first, then exact `PI_SESSION_ID`, else attributable unavailable reason.
2. Remove mutable unrelated/default session fallback from root and projections.
3. Thread parent session through `.2` envelope and one-to-one child records.
4. Run concurrent synthetic contexts and bounded private smoke.

**Focused GREEN:** same command. **Upstream focused/full:** `npx --no-install tsx --test test/session.test.ts && npm test && npm run typecheck`. **Broader:** P2 and P0.

### pi-4tg9.4 — deterministic short-lived worker finalization

**Depends on:** `.2`, C1. **Conflict:** after `.3` in pi-langfuse lane.

**Likely files:**
- Project: `tests/test_langfuse_skill.py`, `pi/agent/settings.json` only for package release.
- Possible local adapter after C1: `pi/agent/extensions/langfuse-config-env.ts`.
- Upstream if irreducible: `index.ts`, `src/langfuse.ts`, `test/lifecycle.test.ts`.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_langfuse_skill.py -k headless_agent_end_awaits_shutdown
```

Expected RED: process can exit before deferred flush; timeout/failure visibility is absent.

**Steps:**
1. C1 decides whether supported `shutdownRuntime()` plus Pi `agent_settled`/`session_shutdown` is a complete local seam.
2. Headless/delegated workers await one bounded deadline; interactive path remains non-blocking unless session shutdown requires cleanup.
3. Preserve one named root observation and report timeout/failure without hanging parent.
4. Repeated private worker smoke records only pass/fail.

**Focused GREEN:** same command. **Upstream focused/full:** `npx --no-install tsx --test test/lifecycle.test.ts && npm test && npm run typecheck`. **Broader:** P2 and P0.

### pi-4tg9.8 — normalized subagent model dimensions

**Depends on:** `.2`. **Conflict lane:** `.8 → .9 → .11 → .17 → .18`.

**Likely files:**
- `pi/agent/extensions/subagent-error-workaround.ts`
- `pi/agent/bin/agnt_lib/metrics.py`
- `tests/test_subagent_workaround.py`
- `tests/test_agnt.py`
- `pi/agent/langfuse/evaluators.json` only if evaluator subject mapping needs explicit fields.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_subagent_workaround.py tests/test_agnt.py -k normalized_model_dimensions
```

Expected RED: projection and local metric cannot join one-to-one by invocation ID/provider/model/target for parallel children.

**Steps:**
1. Reuse `.2` invocation ID; emit normalized provider, model, target, and parent session.
2. Preserve fields through metric compaction/readers.
3. Do not change runtime model ID or infer named-agent effective provider when Archimedes does not expose it; record unavailable explicitly.
4. Keep prompts/outputs out of metadata.

**Focused GREEN:** same command. **Broader:** P2 and P0.

### pi-4tg9.9 — objective execution vs apparent outcome

**Depends on:** `.2`; serialize after `.8`.

**Likely files:**
- `pi/agent/bin/agnt_lib/invoke.py`
- `pi/agent/bin/agnt_lib/runs.py`
- `pi/agent/bin/agnt_lib/metrics.py`
- `pi/agent/bin/agnt_lib/improvement.py`
- `pi/agent/extensions/subagent-error-workaround.ts`
- `tests/test_runner.py`
- `tests/test_agnt.py`
- `tests/test_improvement.py`
- `tests/test_subagent_workaround.py`
- `docs/SELF-IMPROVEMENT.md`
- `docs/AGNT-SYSTEM.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_runner.py tests/test_improvement.py tests/test_subagent_workaround.py \
  -k 'execution_outcome or apparent_outcome or human_override'
```

Required cases: success, provider/process failure, timeout/unavailable, useful partial output, explicit human override, evaluator-positive/process-failure.

**Steps:**
1. Add deterministic `executionOutcome` and normalized failure class at producer boundaries.
2. Preserve subjective apparent/output-quality score separately.
3. Explicit human closeout overrides apparent result; positive judge never overwrites deterministic execution failure.
4. Decide and document whether `unavailable` is execution state rather than public final `TASK_OUTCOMES`; do not silently expand closeout outcomes.
5. Preserve compatibility for old records as unknown.

**Focused GREEN:** same command. **Broader:** P2 and P0.

### pi-4tg9.11 — parent-owned delegated artifacts

**Depends on:** `.2`, `.10`; serialize after `.9`.

**Likely files:**
- Create: `pi/agent/extensions/lib/runtime-artifacts.ts`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`
- Modify: `tests/test_subagent_workaround.py`
- Modify: `docs/RUN-ARTIFACTS.md`
- Modify: `docs/AGNT-SYSTEM.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_subagent_workaround.py \
  -k 'parent_owned_artifact or partial_output_artifact or artifact_write_failure'
```

Expected RED: interactive Archimedes result has no parent-persisted output artifact/reference.

**Steps:**
1. Resolve private directory through `.10`; parent `tool_result` handler owns writes.
2. Persist each child exactly once at stable invocation-ID/child path with restrictive permissions and atomic publication.
3. Preserve full final/partial/error output privately; return only bounded relative/opaque refs in details/telemetry.
4. Handle concurrent calls without overwrite.
5. On write failure, preserve tool execution status/output and add bounded artifact failure metadata.

**Focused GREEN:** same command. **Broader:** P2 and P0.

### pi-4tg9.17 — provider-venue availability circuits

**Depends on:** `.2`; serialize after `.11`.

**Likely files:**
- `pi/agent/bin/agnt_lib/routing.py`
- `pi/agent/bin/agnt_lib/metrics.py`
- `pi/agent/bin/agnt_lib/invoke.py`
- `pi/agent/extensions/subagent-error-workaround.ts`
- `tests/test_route_feedback.py`
- `tests/test_agnt.py`
- `tests/test_subagent_workaround.py`
- `docs/SELF-IMPROVEMENT.md`
- `docs/ARCHITECTURE.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_route_feedback.py tests/test_agnt.py tests/test_subagent_workaround.py \
  -k 'provider_circuit or venue_availability or circuit_expiry'
```

Required cases: deterministic quota/auth/credit/availability opens venue circuit; same-family other venue remains; success/TTL closes; old/unknown record does not open.

**Steps:**
1. Consume payload-free failure class from `.2`/`.9`; never parse private error text in routing.
2. Derive expiring circuit from existing pending/consolidated metrics; no extra state database.
3. Key by provider venue, not model family.
4. Emit visible rejection reason and expiry.
5. Keep subscription/local venues eligible when another venue is open-circuit.

**Focused GREEN:** same command, then:

```bash
pi/agent/bin/agnt eval run routing-smoke
```

**Broader:** P0.

### pi-4tg9.18 — live per-child subagent budgets

**Depends on:** `.2`, C5; serialize after `.17`.

**Likely files:**
- Project adapter/integration: `pi/agent/extensions/subagent-error-workaround.ts`, `tests/test_subagent_workaround.py`, `pi/agent/settings.json`, `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`.
- Upstream Archimedes: `packages/subagent/src/types.ts`, `stream.ts`, `handlers.ts`, `execute.ts`, `spawn.ts`, `index.ts`, new `stream.test.ts`/`execute.test.ts`.

**TDD RED:** Project adapter first rejects/does not understand structured budget stop reason; upstream synthetic parallel test shows no per-child token/tool/turn/wall enforcement.

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_subagent_workaround.py -k 'budget_stop_reason or partial_budget_output'
```

**Steps:**
1. C5 must prove stream ownership and lack of safe parent cancellation before upstream action.
2. Add configurable/default token, tool-call, turn, and wall-time bounds at child stream seam.
3. Use per-child abort controller; kill only offender and let siblings/parent continue.
4. Preserve partial output and usage; return structured stop reason through `.2` envelope.
5. Do not use parent `ctx.abort()` as implementation.

**Upstream focused/full after authoritative checkout is known:**

```bash
npm test -- packages/subagent/src/stream.test.ts packages/subagent/src/execute.test.ts
npm test
```

**Project focused GREEN:** RED command plus `scripts/check-pi-config.sh`. **Broader:** P0. **Stop:** no safe per-child upstream/released seam means `.18` remains open and `.19` stays blocked.

### pi-4tg9.22 — typed custom question response

**Depends on:** `.21`, C5 ask contract.

**Likely files:**
- `pi/agent/extensions/agent-os-compat.ts`
- `pi/agent/extensions/beads-ask-bridge.ts`
- `pi/agent/bin/agnt_lib/approvals.py`
- `tests/test_agent_os_compat.py`
- `tests/test_approvals.py`
- `docs/extension-web-compatibility.md`
- Archimedes ask: `packages/ask/src/index.ts`, `selection.ts`, `picker.ts`, `dialog.ts`, ask tests.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_agent_os_compat.py tests/test_approvals.py \
  -k 'custom_response or custom_input or empty_custom'
```

Required cases: single custom alternative; multi predefined+custom; empty custom rejected/reprompted; selected/custom durable fields; approval custom text never approves.

**Steps:**
1. Always render `Other…` for questions only.
2. Persist `selectedOptions` and `customInput` separately; retain human-readable `answer` summary for compatibility.
3. Reject empty custom input clearly and remain in question UI.
4. Use portable `select`/`confirm`/`input` for RPC; preserve Archimedes keyboard/accessibility in normal TUI.
5. Do not revive deferred `pi-2m1.34` orchestration repair.

**Focused GREEN:** same command. **Archimedes full if used:** package ask focused test then authoritative `npm test`. **Broader:** P3 and P0.

---

## Wave 3 tasks

### pi-4tg9.13 — deterministic error taxonomy

**Depends on:** `.2`, `.9`. Serialize before `.12` and `.14` in improvement/test hotspots.

**Likely files:**
- `pi/agent/bin/agnt_lib/improvement.py`
- `pi/agent/extensions/subagent-error-workaround.ts` only if producer metadata is still missing after `.9`
- `tests/test_improvement.py`
- `tests/test_subagent_workaround.py` only for producer changes
- `docs/SELF-IMPROVEMENT.md`
- `pi/agent/langfuse/improvement-review.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_improvement.py tests/test_subagent_workaround.py \
  -k 'error_classification or actionable_counts or classification_precedence'
```

Required classes: expected, recovered, provider, infrastructure, agent, outcome-blocking, unknown. Expected/recovered do not increase actionable count; unknown is never guessed.

**Steps:**
1. Consume normalized `.2`/`.9` fields; do not classify provider failure from private text.
2. Document deterministic precedence and whether multi-dimensional events get one primary class plus source.
3. Add additive schema-versioned `errorSummary`; preserve existing private fields for compatibility.
4. Keep hashes/private signatures out of public aggregate output.

**Focused GREEN:** same command. **Broader:** P2 and P0.

### pi-4tg9.12 — artifact-aware delegated quality evaluation

**Depends on:** `.9`, `.11`; serialize after `.13`.

**Likely files:**
- `pi/agent/extensions/subagent-error-workaround.ts`
- `pi/agent/langfuse/evaluators.json`
- `pi/agent/langfuse/improvement-review.md`
- `tests/test_subagent_workaround.py`
- `tests/test_langfuse_evaluators.py`
- `tests/test_improvement.py`
- `docs/SELF-IMPROVEMENT.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_subagent_workaround.py tests/test_langfuse_evaluators.py tests/test_improvement.py \
  -k 'artifact_contract or status_only or missing_required_output'
```

Required fixtures: inline findings, artifact output, requested PASS/no-findings, requested status-only, missing required findings, artifact unavailable.

**Steps:**
1. Add explicit output contract kind to delegated invocation envelope.
2. Give evaluator bounded artifact content through private runtime retrieval, or explicit unavailable state; never public path/raw identifier.
3. Keep execution outcome from `.9` separate from quality score.
4. Do not penalize status-only/PASS when requested; do penalize missing required output.
5. Update tracked evaluator prompt/rules and drift tests only; remote apply/deployment remains separate.

**Focused GREEN:** same command. **Broader:** P2 and P0.

### pi-4tg9.19 — repeated identical unrecovered error breaker

**Depends on:** `.18`, C5.

**Likely files:**
- Project: `pi/agent/extensions/subagent-error-workaround.ts`, `tests/test_subagent_workaround.py`, `pi/agent/settings.json`, `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`.
- Upstream: `packages/subagent/src/stream.ts`, `handlers.ts`, `types.ts`, `execute.ts`, new stream/parallel tests.

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_subagent_workaround.py -k 'repeated_error_breaker or repeated_error_stop_reason'
```

Upstream required cases: same failing read reaches bounded threshold before general timeout; changed input and successful recovery reset; sibling continues; result stores digest/count only.

**Steps:**
1. Reuse `.18` per-child cancellation.
2. Fingerprint canonical tool name + canonical input + normalized failure class; never retain raw input/error in telemetry.
3. Count consecutive identical unrecovered failures only.
4. Reset on success or materially changed fingerprint.
5. Preserve partial output/usage and structured `repeated-error` stop reason.

**Upstream focused/full:**

```bash
npm test -- packages/subagent/src/stream.test.ts packages/subagent/src/execute.test.ts
npm test
```

**Project focused GREEN:** RED command. **Broader:** P0. **Stop:** `.18` must be integrated first.

### pi-4tg9.23 — transient vs durable question routing

**Depends on:** `.21`, `.22`.

**Likely files:**
- `pi/agent/AGENTS.md`
- `docs/AGNT-SYSTEM.md`
- `docs/extension-web-compatibility.md`
- Create: `pi/agent/evals/question-routing-smoke/eval.json`
- Create: `pi/agent/evals/question-routing-smoke/prompt.md`
- `tests/test_context_architecture.py`
- `tests/test_agent_os_compat.py`
- `tests/test_approvals.py`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_context_architecture.py tests/test_agent_os_compat.py tests/test_approvals.py \
  -k 'question_routing or transient_question or durable_question'
```

**Steps:**
1. Codify `ask` for current-session clarification/exploration.
2. Codify `ticket_question` only when answer must survive handoff or block a Bead.
3. Keep consequential approvals durable/informed through `ticket_approval`.
4. Preserve selection mode/custom response in both paths.
5. Add focused scenarios proving no forced durable ideation sequence and unchanged approval gates.

**Focused GREEN:** same command, then:

```bash
pi/agent/bin/agnt eval run question-routing-smoke
```

If eval invokes real models, use an approved configured provider and commit only sanitized eval definitions/results summary, not session output. **Broader:** P1, P3, and P0.

---

## Wave 4 task

### pi-4tg9.14 — cohort health summaries

**Depends on:** `.1`, `.3`, `.4`, `.5`, `.6`, `.8`, `.13`. Run last.

**Likely files:**
- `pi/agent/bin/agnt_lib/improvement.py`
- `pi/agent/bin/agnt_lib/langfuse.py` only if `.5` metadata seam needs extension
- `tests/test_improvement.py`
- `pi/agent/bin/README.md`
- `docs/SELF-IMPROVEMENT.md`
- `pi/agent/langfuse/improvement-review.md`

**TDD RED:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_improvement.py \
  -k 'cohort_health or provider_model_health or evaluator_coverage or cohort_limits'
```

Required output: trace total/scanned/attributable/unattributed/continuation; provider/model outcomes; evaluator present/missing/outcome-covered/timeout; `.13` classes; every active cap/limit. No raw IDs, URLs, payloads, hashes, or absolute paths.

**Steps:**
1. Deepen existing scan output with additive nested `cohort.schemaVersion`; do not add another tool.
2. Aggregate only normalized prerequisite fields; old/missing values become `unknown`/`null`.
3. Report all limits and truthful lower bounds from `.5`.
4. Preserve review compatibility for legacy v1 packets.
5. Extend safe CLI JSON test and privacy fixture.
6. Run bounded private scan only after all prerequisites; record generalized pass/fail, never packet contents.

**Focused GREEN:**

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m pytest -q tests/test_improvement.py
"$PY" -m ruff check pi/agent/bin/agnt_lib/improvement.py pi/agent/bin/agnt_lib/langfuse.py tests/test_improvement.py
```

**Broader:** P2 and P0. **Stop:** any prerequisite open, false completeness, or private identifier in safe output blocks `.14` close.

---

## File-conflict serialization

| Hotspot | Beads | Required order/resolution |
|---|---|---|
| pi-langfuse `src/utils.ts` / package release | `.1`, `.6`, `.7`, `.3`, `.4` | One source lane: `.1 → .6 → .7 → .3 → .4`; atomic commits, combined release allowed only after all relevant tests. |
| Archimedes ask `index.ts`/selection/UI | `.21`, `.22` | `.21 → .22`; preserve one compatibility migration. |
| Archimedes subagent `stream.ts`/`execute.ts`/types | `.18`, `.19` | `.18 → .19`; breaker reuses per-child stop mechanism. |
| `pi/agent/settings.json` | `.1`, `.3`, `.4`, `.6`, `.7`, `.18`, `.19`, `.20`, `.21`, `.22`, `.25` | Integration manager alone resolves pins. Prefer one reviewed package-version edit per available release; never concurrent package-pin edits. |
| `subagent-error-workaround.ts` | `.2`, `.3`, `.8`, `.9`, `.10`, `.11`, `.12`, `.13`, `.17`, `.18`, `.19` | `.2 → .10 → .3 → .8 → .9 → .11 → .17 → .18 → .13 → .12 → .19`; rebase each child from latest integrated owner before editing. |
| `tests/test_subagent_workaround.py` | same as above | Same order; do not resolve by discarding another Bead's cases. |
| `metrics.py` | `.2`, `.8`, `.9`, `.10`, `.17` | `.2 → .10 → .8 → .9 → .17`; retain additive schema compatibility. |
| `improvement.py` / `test_improvement.py` | `.5`, `.9`, `.13`, `.12`, `.14`, `.28` | `.5 → .28 → .9 → .13 → .12 → .14`; recreate/rebase each later child from current owner. |
| `agent-os-compat.ts`, `beads-ask-bridge.ts`, `approvals.py` | `.21`, `.22` | `.21 → .22`; one response contract. |
| `tests/test_agnt.py`, `pi/agent/bin/README.md` | `.2`, `.8`, `.9`, `.10`, `.17`, `.24`, `.27`, `.28` | `.2 → .10 → .24 → .27 → .28 → .8 → .9 → .17`; rebase each later telemetry branch before edits. |
| `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`, `docs/SELF-IMPROVEMENT.md` | many | Each Bead edits only its section; final integration owner resolves prose and runs documentation validation. |

When a branch unexpectedly needs a hotspot owned by another active branch, stop. Either add an explicit dependency and recreate from newer integration base, or move the change to the owning Bead. Do not parallel-edit and “fix conflicts later.”

---

## Integration order

This total order is topological and conflict-safe. Read-only contract investigations C1–C5 may run in parallel before source edits.

1. `.2` canonical invocation schema.
2. `.10` safe runtime directory.
3. `.5` trace pagination.
4. `.21` question selection mode.
5. pi-langfuse lane `.1 → .6 → .7`.
6. `.20` BetterWright evidence scope when its contract gate is satisfied; skip this slot without blocking unrelated local work if C2 is unresolved.
7. local workflow lane `.24 → .27 → .28`.
8. `.25` and `.26` after their respective contract gates, one at a time from the latest context/test owner. If either package gate is unresolved, continue unrelated waves and return to its slot before final epic close.
9. pi-langfuse Wave 2 lane `.3 → .4` after `.2`.
10. identity/runtime lane `.8 → .9 → .11 → .17 → .18` after required bases.
11. `.22` custom question response after `.21`.
12. `.13` error taxonomy after `.9`.
13. `.12` artifact evaluation after `.9`, `.11`, and conflict-owner `.13`.
14. `.19` repeated-error breaker after `.18`.
15. `.23` question routing after `.21`/`.22`.
16. `.14` cohort health after every declared prerequisite.

Parallel execution is allowed only inside disjoint groups before merge:

```text
Group A: .2 | .5 | .10 | .20-contract | .21 | .24 | .25-contract | .26-contract
Group B after .2/.10: pi-langfuse lane | identity lane | question lane | workflow lane
Group C: .13 | .19 | .23   (only when their files/bases are disjoint)
Group D: .14 alone
```

Any unresolved upstream gate pauses its affected lane, not unrelated local lanes. Wave 4 cannot complete while `.1`, `.3`, `.4`, or `.6` remains package-blocked.

---

## Per-Bead TDD, review, integration, and closeout procedure

### 1. Start/claim

In child worktree:

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
bd show <bead-id>
bd update <bead-id> --claim
agnt improve link <bead-id>
git status --short --branch
```

If `agnt improve link` lacks `PI_SESSION_FILE`, use the exact current `PI_SESSION_ID` fallback supported by `.28` once integrated; before `.28`, record the failure and retry only with an explicit session-file surrogate whose stem is the current `PI_SESSION_ID`. Never choose another session.

### 2. Baseline

Run the task's focused suite before edits. A pre-existing failure stops implementation and is recorded with command/status; do not relabel it TDD RED.

### 3. RED

1. Add one minimal behavior test using synthetic, payload-free fixtures.
2. Run the task's exact RED command.
3. Confirm test fails for missing behavior, not typo/import/setup.
4. Save only command and generalized expected failure in Bead notes.

### 4. GREEN/refactor

1. Make the smallest owner-seam change.
2. Re-run focused command until green.
3. Refactor only after green; rerun focused command.
4. Run assigned broader profile and `git diff --check`.

### 5. Documentation validation

Use `documentation-standards` validate mode. Required docs follow public interface/architecture changes. Do not dump implementation details or private evidence into docs.

### 6. Review

Before commit, inspect:

```bash
git status --short
git diff --stat
git diff --check
git diff -- . ':(exclude).beads/issues.jsonl'
```

Use `requesting-code-review` for non-trivial changes. Review exact Bead acceptance, privacy, backward compatibility, lifecycle ownership, and tests. Verify every serious finding against source before fixing. Re-run focused and broader checks after review fixes.

### 7. Atomic child commit

Stage only task-owned files:

```bash
git status --short
git add <exact-task-owned-files>
git diff --cached --check
git diff --cached --stat
git commit -m '<type>: <concise change> (<bead-id>)'
```

One Bead commit may include tests/docs required for that behavior. Do not stage Beads runtime state, package checkouts, private telemetry, `/tmp` proof, or unrelated files.

### 8. Local integration gate

Project policy requires explicit approval before local merges. Integration manager prepares exact preview: child branch/commit, changed files, focused/full evidence, conflict resolution, rollback (`git revert -m 1 <merge>` or revert commit), and no push/deploy. Request one bounded approval for the next dependency-complete merge batch.

After approval, from integration worktree:

```bash
git status --short
git merge --no-ff <child-branch>
git status --short
```

If conflict occurs, stop and resolve only with both Bead diffs/tests visible. Never discard either side, reset, or rewrite history. Run task focused checks, then P0; run P1/P2/P3 when the merge touches that domain.

### 9. Close Bead only after integration

A local child commit alone is not completion. Close after approved integration and fresh checks:

```bash
bd show <bead-id>
bd close <bead-id> --reason 'Integrated <commit>; focused and broader checks pass; acceptance evidence recorded.'
agnt improve outcome <bead-id> success
```

For package-blocked or partially local work:

```bash
agnt improve outcome <bead-id> partial
```

Leave Bead open with package decision/resumption path. Do not close on a proposed upstream diff, private local patch, or unconsumed release.

### 10. Wave checkpoints

At end of each wave, integration worktree runs P0 plus relevant domain profiles. Verify `bd show pi-4tg9` dependency state and inspect committed files against wave inventory. Do not run Wave 4 while a declared prerequisite remains open.

### 11. Final review and branch readiness

After `.14` integrates:

```bash
PY=/Users/hays/Projects/pi-setup/.venv/bin/python
"$PY" -m ruff check pi/agent/bin/agnt_lib tests
"$PY" -m pytest tests/
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt action validate
pi/agent/bin/agnt context-health --strict
git diff --check
git status --short
```

Run final `requesting-code-review`, `documentation-standards` validation, and `finishing-a-development-branch`. Prepare local project-readiness report listing 26 Beads, commits, package versions/decisions, checks, and remaining upstream blockers. No push/PR/merge to `main` without separate approval.

### 12. Cleanup only after approval

Worktree removal and branch deletion are destructive and separately approval-gated. First prove child commits are integrated and worktrees clean:

```bash
git worktree list
for path in /Users/hays/Projects/pi-setup/.worktrees/{fix,feature,chore}/pi-4tg9-*; do
  [ ! -d "$path" ] || git -C "$path" status --short --branch
done
```

After explicit cleanup approval only:

```bash
git worktree remove <clean-child-worktree>
git branch -d <integrated-child-branch>
git worktree prune
```

Do not force-remove, use `branch -D`, remove integration worktree, delete upstream checkouts, or clean the existing Ponytail checkout without explicit scope. Keep integration branch/worktree until `main` integration is approved and verified.

---

## Stop conditions

Stop affected lane and preserve work if any condition holds:

- Bead missing, dependency open, branch base stale, or worktree dirty/ambiguous.
- Contract owner/call chain is not understood.
- Proposed local adapter cannot preserve lifecycle, privacy, cardinality, cancellation, or backward compatibility.
- Upstream repository/release/test authority cannot be identified.
- A fix requires a fork, push, PR, vendoring, unpublished pin, merge, deployment, or cleanup without explicit approval.
- TDD test does not fail for expected missing behavior.
- Full check fails outside understood/task-owned scope.
- Live acceptance would require copying private telemetry into tracked/public artifacts.
- Package release is unavailable: leave Bead open and isolate decision; do not claim Wave 4 complete.

## Execution handoff

Plan saved to: `.pi/plans/2026-08-04-telemetry-agent-waves-1-4-plan.md`.

Recommended execution skills: `executing-plans`, `using-git-worktrees`, and `test-driven-development`; use `verification-before-completion`, `requesting-code-review`, `documentation-standards`, and `finishing-a-development-branch` at each integration checkpoint. Implementation requires explicit start/claim and contract gates; this planning artifact authorizes no source implementation, package fork, remote action, merge, deployment, or cleanup by itself.
