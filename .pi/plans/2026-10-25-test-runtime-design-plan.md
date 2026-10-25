# Test runtime design and audit — pi-7vwu

## Goal and scope
Reduce full-suite wall time without weakening unique contracts. User approved worker balancing and removal only of proven redundant coverage. No dependency changes, deployment, push, CI parallelism change, or live configuration changes.

## Design
Keep four isolated pytest processes and whole-file grouping. Replace alphabetical round-robin with longest-processing-time-first greedy assignment using tracked baseline file durations (`scripts/python-test-durations.json`). Timing hints affect scheduling only: new/nested files still run, unknown files get weight 1, stale hints never select tests. Keep full pytest discovery, error propagation, logs, JUnit and executed-count check. No timing cache or extra dependency. CI remains serial for order-sensitive coverage.

Affected files: `scripts/check-python-tests.py`, new timing JSON, `tests/test_parallel_tests.py`, `tests/test_agnt.py`, `README.md`, `CONTRIBUTING.md`. Verify all callers via repository search; no exports or production API changes.

## Steps / verification
1. Add deterministic scheduler tests: skewed durations, stable ties, unknown/nested files, exactly-once assignment, fewer files than workers. Observe failure before implementation.
2. Add minimal scheduler and measured duration hints. Focused gate: `.venv/bin/python -m pytest tests/test_parallel_tests.py`.
3. Merge the two default context-health scans in `tests/test_agnt.py`, retaining every distinct assertion. No whole-contract deletion justified by audit.
4. Benchmark same full runner and compare retained test coverage, not raw count alone. Read-only peer review; stable candidate then project full verification matrix from AGENTS.md. Commit task-owned changes and direct-closeout.

## Baseline
Commit 081fc15, local Python 3.13 / Node 24.21.0. `PYTEST_ADDOPTS='--durations=30' /usr/bin/time -p .venv/bin/python scripts/check-python-tests.py`: 1722 executed, 1721 passed, one failed; wall 174.95s. Shards 74.39 / 174.39 / 26.70 / 129.27s. JUnit file time sum 403.778s; greedy scheduling model ~100.95s, not a verified performance result.
Logs: `/tmp/pi-test-timing-baseline.log`; JUnit directory `/var/folders/rh/k2_zcjrj1vg6z_j_sr25qs580000gn/T/pi-python-tests-cyl_hygz`.
Failure `tests/test_bead_handoff.py::test_handoff_command_rejects_failed_closeout_preflight` passed isolated rerun (0.55s). Its asynchronous metrics polling is timing-sensitive; no root-cause claim or test removal authorized by failure.

## Redundancy audit
Two read-only peer investigations plus controller verification. Focused assertion/setup audit, not exhaustive mutation coverage of every parametrized case. Full AST inventory after changes: 1,215 test functions, no exact duplicate bodies. This does not prove semantic nonredundancy.

- Merge `test_context_health_report_passes_without_failures` and `test_context_health_reports_skill_discovery_budget`: both execute unmodified `agnt.context_health_report()`. Preserve status, file metadata and gate assertions in single report test.
- No runtime-saving whole-test deletion proven across deployment, runtime delivery, package patching, Beads workspace, workflow compliance, continuation, handoff and isolation families. Similar assertions exercise distinct adapter/domain, source/destination, signal/timeout, audit on/off, or state transitions.
- Repeated package token assertions, historical context size ratio and extension-exists assertions have negligible cost. Leave unchanged: deleting diagnostic assertions offers no useful speedup.
- Keep real Beads/bootstrap and process-termination tests. Avoid sharing mutable repositories or shortening real timeouts for speed.
- Static source/doc token assertions offer weaker behavioral confidence but are not automatically redundant. Further pruning needs explicit contract replacement, not test-name similarity.

## Candidate evidence
- TDD: four new scheduler cases failed because `partition_files` was absent; after implementation, nine focused scheduler/context-health cases passed.
- Balanced run: 1,725 passed, 107.94s wall; shards 105.17 / 99.18 / 98.12 / 106.87s. Local reduction 38.3%, not a CI guarantee. Log `/tmp/pi-test-timing-balanced.log`; JUnit directory `/var/folders/rh/k2_zcjrj1vg6z_j_sr25qs580000gn/T/pi-python-tests-tp0ih9qq`.
- JUnit identity comparison: only two original context-health IDs removed; one combined ID and four scheduler cases added. Every original assertion retained.
- Independent one-shot review: no findings, validated using `agnt review validate .pi/reviews/pi-7vwu/findings.json`. Packet and response retained in that private review directory.
- Fresh `npm ci --ignore-scripts` passed; existing root development dependency advisories remain (one moderate, one high). No dependency graph change or security-remediation claim.

Risks: historical weights drift or differ across hosts; benchmark is local. Existing handoff timing flake may recur under changed scheduling. No claim all tests are equally valuable or exhaustively audited.
