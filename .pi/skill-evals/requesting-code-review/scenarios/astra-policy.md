# Scenario: Astra review policy

Prompt: Choose low, medium, high risk review and reserve/hard-cap targets after owner adopts Astra with down-one-level medium-floor effort.

Weak baseline: skill selects Sol low/medium/xhigh, conflicting with approved Astra matrix.

Expected: Astra medium/medium/high; Terra challenger, Kimi/Opus independent checks and paid admission preserved; reserve/hard-cap Astra only.

Assertions: tests/test_model_config.py::test_review_skill_matches_approved_astra_first_diversity_matrix and tests/test_agnt.py review policy tests.
