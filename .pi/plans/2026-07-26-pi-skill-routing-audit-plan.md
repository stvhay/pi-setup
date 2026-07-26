# Pi Skill Routing Audit and Cleanup Plan

**Issue:** pi-8wfd — Audit Pi skill routing and clean skill assets
**Design:** User-approved cleanup in current session
**Date:** 2026-07-26
**Branch:** main

**Goal:** Replace Claude-derived findings with Pi-session evidence, repair skill routing/assets, and add minimum regression coverage.

**Architecture:** Treat Pi `read` tool calls for repository-owned `skills/<name>/SKILL.md` as observable skill-load signals. Keep detailed guidance lazy under `references/`, executable behavior under `evals/`, and deterministic drift checks in existing pytest coverage.

**Acceptance Criteria:**
- [ ] Aggregate Pi session evidence identifies zero-use and low-use repository skills without exposing session contents.
- [ ] Real skill references resolve; fenced example artifact paths are not misclassified.
- [ ] Testing anti-pattern guidance is routed only when mocks or test-only production APIs are relevant.
- [ ] Systematic-debugging keeps one runnable pressure eval and no stale fixtures/scripts.
- [ ] Root `AGENTS.md` noise is removed and documented `agnt` commands have smoke coverage.
- [ ] Obsolete Claude report is deleted.

**Verification Commands:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_agnt.py
pi/agent/bin/agnt eval run systematic-debugging-pressure --dry-run
pi/agent/bin/agnt eval run routing-smoke
scripts/check-pi-config.sh
bash -n scripts/*.sh
```

---

## Pi session baseline

Scan scope: 220 saved sessions across 23 working directories, 2026-06-05 through 2026-07-26, excluding the current audit session. Signal: assistant `read` calls ending in a tracked `skills/<name>/SKILL.md` path.

- 39 of 42 tracked skills have at least one observed load.
- `layer-theme`: zero loads and zero matching theming/userscript tasks; no routing defect shown.
- `scorable-discovery`: zero loads. Strong apparent matches either predate the skill or are incidental uses of scoring/optimization language; no post-install routing defect shown.
- `stamp-base`: zero direct loads, while `stamp-stpa`, `stamp-cast`, and `stamp-stpa-sec` loaded. This is consistent with `stamp-base` being an ambiguity/shared-foundation router, not mandatory middleware.
- Explicit `/skill:<name>` invocations were not observed; routing is model-driven.
- Read counts are upper bounds because audits may load skills for inspection. Zero counts are stronger evidence than high counts.

## Tasks

1. Add focused failing tests for resolvable skill references and documented `agnt` command parsing.
2. Fix two confirmed deployed-runtime cross-skill paths and any additional failures exposed by the reference test.
3. Move `testing-anti-patterns.md` under `references/` and add a narrow route from TDD guidance.
4. Delete systematic-debugging orphan scripts/examples and obsolete code-review packet template.
5. Replace four stale systematic-debugging reference fixtures with one representative invoke eval.
6. Remove root `AGENTS.md` template noise and delete `claude-doctor-report-2026-07-26.md`.
7. Run focused and project verification; record remaining telemetry-based improvement items in Bead closeout.
