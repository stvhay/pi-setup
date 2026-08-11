# agnt Surface and Seam Audit Plan

**Issue:** None
**Design:** 2026-08-11 user discussion: keep deterministic logic separate from Pi adapters and simplify loaded instructions
**Date:** 2026-08-11
**Branch:** main

**Goal:** Produce an evidence-backed target surface for `agnt`, Pi extensions, and typed tools without moving capabilities merely to reduce CLI count.

**Architecture:** Treat each capability as a module with one interface and one or more justified adapters. `agnt_lib` is the default home for deterministic domain logic; the `agnt` CLI is a human/CI/headless adapter; Pi extensions own lifecycle, UI, session, and provider integration; typed tools are thin agent-facing adapters. A capability moves only when caller evidence shows a better seam, and one-adapter hypothetical abstractions are rejected.

**Acceptance Criteria:**
- [ ] Every registered `agnt` command and Pi tool has an exact caller/effect matrix covering instructions, docs, scripts, CI, extensions, tests, and headless workers.
- [ ] Each capability is classified `keep CLI-only`, `dual CLI+tool`, `tool/extension-only`, `internal-only`, `merge/deepen`, or `delete`, with interface and adapter rationale.
- [ ] Recommendations preserve headless/CI operation and avoid duplicating Python domain logic in TypeScript extensions.
- [ ] High-frequency model workflows are evaluated for typed schemas, validation, approval semantics, and instruction reduction.
- [ ] Loaded instruction burden is measured before and after a concrete compact target draft.
- [ ] No migration or public-interface deletion occurs without separate approval and a follow-up Bead.

**Verification Command(s):**
```bash
rg -n '"[a-z-]+": \(' pi/agent/bin/agnt
rg -n 'registerTool\(|name: "' pi/agent/extensions
rg -n '\bagnt\b|ticket_gateway|subagent|handoff_bead|restart_pi' pi/agent/AGENTS.md AGENTS.md
.venv/bin/python -m pytest tests/test_agnt.py tests/test_context_architecture.py tests/test_ticket_gateway.py
```

---

### Task 1: Inventory current interfaces and callers

**Context:** Build one table from source, not command documentation alone.

**Files:**
- Read: `pi/agent/bin/agnt`
- Read: `pi/agent/bin/agnt_lib/*.py`
- Read: `pi/agent/extensions/*.ts`
- Read: `pi/agent/extensions/lib/*.ts`
- Read: `pi/agent/AGENTS.md`
- Read: `scripts/`, `.github/`, `tests/`, and active docs
- Create: `.pi/plans/<date>-agnt-surface-seam-audit-results.md`

**Steps:**
1. Enumerate front-controller commands and extension-registered tools/commands.
2. For each surface, record implementation module, inputs, outputs, effects, approval needs, environment dependencies, and exact callers.
3. Distinguish public callers from tests and documentation-only mentions.
4. Mark capabilities with no non-test caller, duplicate interfaces, or pass-through modules.

**Expected result:** Complete greppable surface/caller/effect matrix.

### Task 2: Evaluate module depth and seam placement [Depends on: Task 1]

**Context:** Use deletion test and adapter count. Deep modules hide meaningful behavior; shallow adapters exist only when they connect a real caller environment.

**Steps:**
1. Apply deletion test to every `agnt_lib` module and extension adapter.
2. Identify interfaces tested past their seam through source-text assertions.
3. Confirm which capabilities require both CLI and Pi-tool adapters.
4. Reject TypeScript duplication of deterministic Python logic.
5. Identify clusters that should merge behind a smaller interface, especially direct work start/outcome/closeout.

**Expected result:** Evidence-backed classification for every surface.

### Task 3: Evaluate high-frequency model workflows [Depends on: Task 1]

**Context:** Typed tools are justified when they reduce model instruction branches, enforce schemas, or mediate UI/session state—not merely because a CLI exists.

**Candidate workflows:**
- routing then subagent dispatch;
- direct Bead start, outcome recording, closeout, and handoff;
- ticket list/show/tree/draft and durable human decisions;
- runtime-path/provider-circuit calls currently used by extensions.

**Steps:**
1. Count loaded instruction steps and failure modes for each workflow.
2. Compare current CLI sequence with a thin typed-tool adapter over existing domain modules.
3. Prefer one deep workflow interface over several one-command tools when ordering invariants are real.
4. Keep operator, CI, bulk, destructive, and maintenance operations CLI-only unless a concrete agent caller requires them.

**Expected result:** Small set of justified dual-surface candidates; no blanket migration.

### Task 4: Draft target instruction surface [Depends on: Tasks 2-3]

**Context:** Loaded instructions should teach selection rules, not duplicate command reference.

**Target rules:**
1. Direct code work uses normal Pi workspace tools after Bead setup.
2. Typed Pi tools handle interactive decisions and Pi lifecycle.
3. `agnt` handles deterministic policy, checks, artifacts, and headless operations.
4. Extensions adapt domain modules; they do not duplicate domain logic.

**Steps:**
1. Draft compact replacement guidance for `pi/agent/AGENTS.md` without applying it.
2. Measure line/character reduction and retained safety gates.
3. Keep exact syntax in `pi/agent/bin/README.md`, loaded only on demand.

**Expected result:** Reviewable instruction draft with measured reduction and no weakened gates.

### Task 5: Recommend follow-up work [Depends on: Tasks 1-4]

**Steps:**
1. Rank findings by deleted interface burden and instruction simplification.
2. Separate no-behavior refactors from public behavior changes.
3. Propose the smallest implementation slices with exact files/tests.
4. Create no Beads and make no code changes until user approves the audit result.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-11-agnt-surface-seam-audit-plan.md` (verify with `test -f`)
Recommended next skill: `codebase-design` for module/interface/seam analysis; `writing-plans` only after audit recommendations are approved.
