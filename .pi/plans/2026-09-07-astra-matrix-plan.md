# Astra default and matrix

Bead: `pi-6j6t`. Branch: `main`. Date: 2026-09-07.

## Decision

Owner selects Astra as primary across existing Sol-led routes. Map Sol effort down one level with medium floor: low/medium/high -> medium; xhigh -> high. Interactive default Astra medium; routed orchestration high at all risks (formerly Sol xhigh). Keep Terra-low cheap-peer, existing independent checks and paid admission gates. Keep Sol as qualified fallback; fallback inherits task effort. Observational-memory Sol-low stays unchanged. No deployment or push.

## Implementation

1. Change existing config/routing assertions first; observe RED.
2. Add catalog metadata from installed Pi models-store (272000 context, text/image, native thinking map); update settings and six Sol-led task policies, keeping Sol fallback. No routing code/schema changes.
3. Align routing-smoke and active docs/review skill. Preserve historical evals and evidence.
4. Evaluate task/risk/budget matrix deterministically; no measured quality/latency promotion claim. Owner heuristic supplies policy, not benchmark result.
5. Focused tests, review, stage exact task paths, final checks, local commit and direct-closeout.

## Verification

Baseline: 193 tests passed across test_model_config.py, test_agnt.py, test_catalog.py, test_pi_packages.py; routing-smoke 8/8 passed.

Focused: `.venv/bin/python -m pytest tests/test_model_config.py tests/test_agnt.py tests/test_catalog.py tests/test_pi_packages.py -q`.
Final: `scripts/check-pi-config.sh`; `bash -n scripts/*.sh`; `.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests`; `.venv/bin/python -m pytest tests/ --durations=15`; `pi/agent/bin/agnt eval run routing-smoke`; `pi/agent/bin/agnt eval run role-context-smoke`; diff checks.

## Acceptance

Astra-medium default; mapped task levels and Sol fallback; cheap-peer and metered gates preserved; runtime metadata correct; deterministic matrix verified; no quality-superiority claim; task-owned commit. Unrelated `.pi/plans/2026-08-18-telemetry-preproduction-contract-design-plan.md` excluded.
