# Scenario: Compact skill discovery without losing triggers

## Prompt
Choose relevant skills for each request:
- Install Laya across projects; use Jev/System 1 typed decisions for text routing, ticket/email triage, spam/phishing/toxicity/intent detection, or rubric scoring.
- Draft or validate a project README, architecture document, or spec.
- Finish implemented work: check readiness, docs/review, PR, merge, or cleanup.
- Edit human-facing prose, messages, reports, explanations, or UI copy.
- Assess research/innovation feasibility, technology gaps, moonshots, or go/no-go.
- Implement a polished dashboard, admin GUI, SaaS, or web app.
- Restyle or dark-theme a third-party site with userscripts/UserStyle or saved styles.

## Expected weak baseline
Discovery uses 7,768 of 8,000 characters; remaining 232 fails the existing >1,000 reserve assertion. Laya description includes installation, speed, and marketing claims instead of only discovery triggers.

## Expected with skill
Same named task families remain discoverable with >1,000 characters remaining. Laya does not become a general writing or multi-step reasoning skill. First-party GUI design stays distinct from third-party theming. Skill bodies and safety/verification rules remain unchanged.

## Assertions
- All seven descriptions retain the positive trigger families above.
- Generation or multi-step reasoning alone does not select Laya.
- Third-party theming selects layer-theme; ordinary app implementation selects design-principles.
- Package-installed skills, skill bodies, and budget limits remain unchanged.
- Existing test_context_health_reports_skill_discovery_budget and description-format tests pass.

## Verification
Baseline failure observed in full suite and pristine base 83adffb: `assert 232 > 1000`.
Run `.venv/bin/python -m pytest tests/test_agnt.py::test_context_health_reports_skill_discovery_budget tests/test_context_architecture.py -q` and `pi/agent/bin/agnt context-health --strict`.
Trigger comparison is static human/agent review, not a measured model-selection benchmark.
