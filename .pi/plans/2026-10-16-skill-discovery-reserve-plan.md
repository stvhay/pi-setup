# Skill discovery reserve correction

**Bead:** pi-3tq5
**Approval:** pi-yug9
**Branch:** main (direct current-session work)
**Diagnosis:** .pi/reviews/pi-3tq5/diagnosis.md

## Goal and boundary

Recover at least 333 discovery characters without changing the 8000-character ceiling, 1000-character warning, warning visibility, or existing tests. Change description lines only in at most the eight approved repository skills: tufte, laya-integration, subagent-driven-development, receiving-code-review, delegation-oversight, stamp-stpa-sec, stamp-cast, failure-choreography. Preserve positive routing concepts, exclusions, automatic discovery and all bodies. Stop if this scope cannot preserve meaning.

## Steps

1. Record a written positive/near-neighbor scenario under `.pi/skill-evals/tufte/scenarios/discovery-budget.md`. Baseline already observed: focused context-health tests 18 pass, one failure `668 > 1000`.
2. Compress descriptions, inspect exact diff, and assert all other lines unchanged against source HEAD 49dd1ea. Measure with production scanner, not estimates.
3. Run focused context-health and context-architecture tests; inspect warning boundaries and trigger scenario. No model canary or equivalence claim.
4. Review, stage exact task-owned descriptions/scenario/plan; run full required local gates on stable candidate. Preserve two unrelated untracked plans.
5. Record evidence, commit once locally, run direct closeout and handoff. No deployment, push, package change or unrelated cleanup.

## Verification

```bash
pi/agent/bin/agnt context-health --strict
.venv/bin/python -m pytest tests/test_agnt.py -k context_health -q
.venv/bin/python -m pytest tests/test_context_architecture.py -q
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

Use isolated temporary HOME for pytest to avoid known ambient external-skill leakage. Reuse installed locked dependencies; package installation is outside approval. README threshold semantics remain accurate; no public API or persistent-format change.
