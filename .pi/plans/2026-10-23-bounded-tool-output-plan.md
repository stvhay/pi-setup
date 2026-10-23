# Bounded Tool Output Implementation Plan

**Issue:** pi-ygae — Reduce tool-result context with existing output guidance
**Design:** Approved conversation: simplify existing tool use before adding infrastructure.
**Date:** 2026-10-23
**Branch:** main

## Goal and boundary

Reduce unnecessary model input from verbose command logs, repeated browser snapshots, and unfiltered tool batches. Change repository-owned guidance, not tool APIs or runtime output. No summarizer, truncation middleware, dependencies, LAYA, deployment, or push. Preserve approval gates, errors, full evidence access, and required verification/full-document reads.

## Implementation

1. Record written baseline scenarios in `.pi/skill-evals/token-saver/scenarios/bounded-tool-output.md`; add failing instruction-contract assertions to `tests/test_context_architecture.py`.
2. Replace generic retrieval/batching guidance in `pi/agent/skills/token-saver/SKILL.md` with actionable command/browser/batch output discipline. Replace redundant search guidance with one short always-loaded rule in `pi/agent/AGENTS.md`; document guidance-only behavior in `pi/README.md`. Update `pi/agent/evals/role-context-smoke/eval.json` for equivalent compact wording and verify the new output rule reaches delegated workers.
3. Run focused checks, inspect the diff for accidental weakening, then run required final checks and commit task-owned files. Close pi-ygae using direct-closeout. Leave unrelated plans untouched.

## Acceptance

- Verbose commands retain full logs in private artifacts and report actual command exit status, counts, bounded failure excerpts, and artifact path. A filter must not mask failure.
- Browser reads become scoped after discovery; further broad snapshots require unknown/changed structure or failed locator. Required proof remains intact.
- Independent codemode reads are filtered inside the script before output; per-call failures remain visible. Mutations and safety gates remain serial.
- Insufficient excerpts expand by relevant section; explicitly required full reads are preserved.
- Guidance remains advisory: no automatic truncation or claimed measured token/latency savings.

## Verification

Baseline: `.venv/bin/python -m pytest tests/test_context_architecture.py -q` — 105 passed before edits.
Written scenario baseline is sufficient for this small skill edit; deterministic checks verify instruction delivery, not model compliance. No real-model benchmark is part of this change.

Focused:
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py -q
pi/agent/bin/agnt context-health --strict
```

Final stable-candidate gate:
```bash
npm ci --ignore-scripts
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
git diff --cached --check
```

## Execution handoff

Execute in current session. Before completion, record focused/final results and limitations in Bead notes. No live `~/.pi` changes authorized; source-only guidance will not affect other sessions until separately deployed.
