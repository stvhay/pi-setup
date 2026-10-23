# Local parallel Python gate

**Bead:** pi-5why
**Goal:** Reduce full local verification latency without omitting tests or adding dependencies.

## Design and scope

Reuse installed pytest collection and standard-library subprocesses. Collect the full tests directory; partition collected file paths deterministically across at most four processes. Keep shared pytest cache disabled, retain per-process logs/JUnit reports, propagate failed collection/children and reject executed-count mismatches. Keep CI serial as an independent order-sensitive check. No production/runtime deployment changes.

Files: `scripts/check-python-tests.py`, `tests/test_parallel_tests.py`, `AGENTS.md`, `CONTRIBUTING.md`, `README.md`.

## Verification

- Test-first nested discovery, child failures, collection errors and missing reports.
- Focused: `.venv/bin/python -m pytest tests/test_parallel_tests.py -q`.
- Compare complete serial and parallel suites on the final candidate; same test count and zero failures. Reuse baseline timing evidence for comparison, not as a release verdict.
- Run project config/shell/Ruff/npm and deterministic eval gates, plus independent review.
- Commit this improvement separately; future local gates use parallel command once, not serial plus parallel routinely.

The owner accepts estimated whole-task benefit. Timing improvement is not a claim of changed model cost or output quality.
