# Scenario: October model alignment

## Prompt
Select independent high-risk review target under October model policy.

## Expected weak baseline
Tracked skill names disabled `openrouter/anthropic/claude-opus-5`; settings enable Opus 5.5.

## Expected with skill
Skill names `openrouter/anthropic/claude-opus-5.5`; budget, fresh-worker, and human-adjudication requirements unchanged.

## Assertions
- Use exact October target, consistent with review task and settings.
- No automatic metered calls without estimates, justification and aggregate budget.
- No trigger-description or authority changes.

Deterministic regression: `tests/test_model_config.py::test_review_skill_matches_approved_astra_first_diversity_matrix` failed before skill edit. No model canary authorized.
