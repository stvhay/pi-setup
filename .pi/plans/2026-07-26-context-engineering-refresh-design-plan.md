# Context Engineering Refresh Design and Implementation Plan

**Issue:** pi-a7w — Track context-health refinement follow-ups
**Design:** Approved in conversation from verified Anthropic/OpenAI guidance
**Date:** 2026-07-26
**Branch:** main (project policy permits direct current-session work; user explicitly requested execution)

**Goal:** Reduce always-loaded and discovery context while preserving workflow gates, and enforce portable skill metadata and progressive-disclosure conventions.

**Architecture:** Keep the dependency-free frontmatter parser intentionally small and require single-line skill descriptions. Extend `agnt context-health` with deterministic discovery-budget and broader guidance scans. Pilot progressive disclosure in `skill-creator`, `executing-plans`, `project-init`, and `stamp-stpa`; retain non-negotiable gates in top-level skill files and move only bulky reference material.

**Non-goals:** Rewriting all 42 skills, changing externally installed/package-owned skills, touching the unrelated untracked `push/` repository, matching Anthropic's 80% reduction, weakening approval/security/verification rules, changing worker skill propagation tracked by `pi-2m1.27.19`, or adding dependencies.

**Acceptance Criteria:**
- [x] Every skill description is a supported single-line scalar; discovery metadata using name + description + relative path fits an 8,000-character budget.
- [x] `agnt context-health` reports metadata-budget violations and scans loadable skill references plus routing tasks for stale/gate-weakening guidance.
- [x] `skill-creator` documents concise trigger metadata, progressive disclosure, expressive interfaces, rich references, and eval-first iteration.
- [x] Pilot top-level skills remain behaviorally complete while each falls below the existing 220-line warning threshold.
- [x] Migrated skills are removed from `LARGE_SKILL_ALLOWLIST`.
- [x] `pi/agent/AGENTS.md` retains always-applicable policy while delegating command reference details to `pi/agent/bin/README.md`.
- [x] Trigger/non-trigger and behavior-preservation scenarios exist for changed skills.
- [x] Project docs and deterministic checks match implemented behavior.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_context_architecture.py tests/test_catalog.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib pi/agent/bin/_agnt_common.py tests
pi/agent/bin/agnt context-health --strict
scripts/check-pi-config.sh
bash -n scripts/*.sh
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
```

---

### Task 1: Add skill scenarios [Independent]

**Context:** Skill edits need baseline assertions before behavior changes. Use existing `.pi/skill-evals/<skill>/scenarios/` convention; scenarios encode trigger precision and preserved gates without requiring a new runner.

**Files:**
- Create: `.pi/skill-evals/skill-creator/scenarios/progressive-disclosure.md`
- Create: `.pi/skill-evals/executing-plans/scenarios/continuous-safe-execution.md`
- Create: `.pi/skill-evals/project-init/scenarios/audit-without-overwrite.md`
- Create: `.pi/skill-evals/stamp-stpa/scenarios/prospective-routing-and-output.md`

**Focused verification:**
```bash
find .pi/skill-evals/{skill-creator,executing-plans,project-init,stamp-stpa}/scenarios -type f | sort
```

### Task 2: Enforce metadata architecture [Depends on: Task 1]

**Context:** The shared parser does not support YAML folded/literal block scalars. Preserve its small dependency-free contract; reject unsupported skill descriptions instead of implementing YAML. Measure the portable discovery list as name + normalized description + path relative to `pi/agent/`.

**Files:**
- Modify: `tests/test_context_architecture.py`
- Modify: `tests/test_agnt.py`
- Modify: `pi/agent/bin/agnt_lib/context_health.py`
- Modify: `pi/agent/skills/*/SKILL.md` frontmatter descriptions as needed

**Steps:**
1. Add failing tests for multiline/block-scalar descriptions and discovery payload reporting.
2. Run focused tests and confirm expected failures.
3. Add minimal scanner/report implementation.
4. Normalize and shorten descriptions until the inventory fits 8,000 characters.
5. Verify focused tests and `agnt context-health`.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_context_architecture.py
pi/agent/bin/agnt context-health --strict
```

### Task 3: Broaden context scans and ratchet large skills [Depends on: Task 2]

**Context:** Bead `pi-a7w` requires broader gate-weakening scans and explicit handling of oversized skills. Scan all loadable skill Markdown and routing tasks. Keep existing warning semantics; remove allowlist entries only for migrated skills.

**Files:**
- Modify: `tests/test_agnt.py`
- Modify: `pi/agent/bin/agnt_lib/context_health.py`

**Steps:**
1. Add failing tests showing skill references/tasks are scanned.
2. Implement smallest path inventory expansion.
3. Remove migrated allowlist entries after Task 4 passes line checks.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agnt.py
```

### Task 4: Refresh skill guidance and pilot disclosure [Depends on: Tasks 1-2]

**Context:** Update `skill-creator` with current portable guidance. Slim pilot skills without deleting safety or decision rules. Reuse existing references/templates; create one STPA output-format reference because schema and diagram syntax are bulky and independently retrievable.

**Files:**
- Modify: `pi/agent/skills/skill-creator/SKILL.md`
- Modify: `pi/agent/skills/executing-plans/SKILL.md`
- Modify: `pi/agent/skills/project-init/SKILL.md`
- Modify: `pi/agent/skills/stamp-stpa/SKILL.md`
- Create: `pi/agent/skills/stamp-stpa/references/output-formats.md`

**Focused verification:**
```bash
wc -l pi/agent/skills/{skill-creator,executing-plans,project-init,stamp-stpa}/SKILL.md
.pi/skill-evals/*/scenarios/*.md >/dev/null 2>&1 || true
.venv/bin/python -m pytest tests/test_context_architecture.py
```

### Task 5: Slim always-loaded guidance [Depends on: Task 2]

**Context:** Keep safety, project workflow, research verification, and context layering in `pi/agent/AGENTS.md`. Replace duplicated command inventory and explanatory taxonomy with links to deployed command documentation and concise distinctions.

**Files:**
- Modify: `pi/agent/AGENTS.md`
- Modify if needed: `pi/agent/bin/README.md`

**Focused verification:**
```bash
wc -lc pi/agent/AGENTS.md
scripts/check-pi-config.sh
```

### Task 6: Align docs and verify [Depends on: Tasks 3-5]

**Files:**
- Modify: `pi/agent/bin/README.md`
- Modify: `docs/SELF-IMPROVEMENT-CONFIG-EVALUATION.md`

**Steps:**
1. Document discovery-budget and broader-scan behavior.
2. Mark duplicate-scope and oversized-skill handling implemented; state remaining limits.
3. Run all acceptance verification commands.
4. Review diff for safety-gate regressions and unnecessary complexity.

**Focused verification:**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/
```

## File Conflicts

| File | Tasks | Resolution |
|---|---|---|
| `tests/test_agnt.py` | Tasks 2-3 | Execute sequentially. |
| `context_health.py` | Tasks 2-3 | Execute sequentially. |
| `pi/agent/bin/README.md` | Tasks 5-6 | Task 6 performs final alignment. |

## Execution Evidence

- Discovery payload: 6,804 / 8,000 characters.
- Always-loaded `pi/agent/AGENTS.md`: 136 lines / 10,153 bytes → 85 lines / 4,391 bytes.
- Pilot top-level skills: `skill-creator` 188 lines; `executing-plans` 144; `project-init` 144; `stamp-stpa` 145.
- Generated implementation-worker context: 7,723 bytes, down from pre-change 13,485 bytes.
- Tests: 300 passed; Ruff, shell checks, config check, context health, routing smoke, and role-context smoke passed.
- Review: Gemma behavioral review returned no findings. Kimi boundary review was unavailable due provider monthly limit; Codex fallback found one block-scalar modifier gap, confirmed and fixed with a parameterized regression test.
- External package skills and unrelated untracked `push/` repository remained untouched per decision `pi-vkwp`.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-26-context-engineering-refresh-design-plan.md`
Implementation and acceptance verification completed. Use `finishing-a-development-branch` before commit/PR work.
