# OpenRouter API Routing Design and Implementation Plan

**Issue:** #pi-d1sw — Adopt API-first OpenRouter routing portfolio
**Design:** This file
**Date:** 2026-08-06
**Branch:** main

**Goal:** Keep OpenAI Codex Pro 20× as root capacity while routing bounded, fresh delegated diversity calls directly through Pi's built-in OpenRouter provider and disabling active local/Olla routes.

**Architecture:** Pi already ships an `openrouter` provider and resolves `OPENROUTER_API_KEY` or `/login openrouter`; no custom provider belongs in `models.json`. `settings.json` controls the active model surface, `catalog.json` supplies deterministic routing metadata, and `tasks/*.md` encode the approved primary and external-primary matrices. Existing Olla/local implementation can remain dormant for easy rollback, but active settings and task policy must not select it.

**Acceptance Criteria:**
- [ ] Tracked report preserves telemetry basis, decision, matrices, confidence, and reevaluation gates.
- [ ] Enabled non-Codex models use exact built-in `openrouter/<model-id>` targets.
- [ ] Active task policies contain no `olla-local`, `olla-cloud`, or `ollama` targets.
- [ ] Global instructions require fresh bounded workers for metered OpenRouter calls and mark local/Olla routes inactive.
- [ ] Model/routing tests and deterministic evals pass.
- [ ] No credential is committed; runtime auth uses `/login openrouter` or `OPENROUTER_API_KEY`.

**Verification Command(s):**
```bash
.venv/bin/python -m pytest tests/test_model_config.py tests/test_catalog.py tests/test_agnt.py
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
scripts/check-pi-config.sh
bash -n scripts/*.sh
```

---

### Task 1: Record approved portfolio

**Files:**
- Create: `docs/MODEL-PORTFOLIO-2026-08.md`

Record sanitized telemetry, approved API-first decision, primary/reverse matrices, plan economics, confidence, and reevaluation gates.

### Task 2: Replace active routes

**Files:**
- Modify: `pi/agent/settings.json`
- Modify: `pi/agent/catalog.json`
- Modify: `pi/agent/tasks/*.md`
- Modify: `pi/agent/AGENTS.md`
- Modify: `pi/agent/skills/requesting-code-review/SKILL.md`

Use exact built-in OpenRouter IDs for M3, Kimi K2.7 Code, Kimi K3, and Opus 5. Keep OpenAI Codex default. Do not add a custom OpenRouter provider.

### Task 3: Align tests and docs

**Files:**
- Modify: `tests/test_model_config.py`
- Modify: `tests/test_catalog.py`
- Modify: focused routing expectations in `tests/test_agnt.py` and eval fixtures as needed
- Modify: `pi/README.md`
- Modify: `docs/ARCHITECTURE.md`

Prove direct OpenRouter activation, local/Olla deactivation, matrix routing, and documented credential flow.

## Execution Handoff

Plan saved to: `.pi/plans/2026-08-06-openrouter-api-routing-design-plan.md`.
Recommended next skill: `test-driven-development`; `verification-before-completion` before commit.
