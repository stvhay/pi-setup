# Updater status implementation plan

Issue: pi-9aal. Approved design: Bead description. No live deployment or dependency changes.

## Scope and approach

Keep deployment control flow and exit codes. Capture noisy external validation/install/patch command output in a private temporary log directory. Print concise phase labels, replay stderr and stdout warnings, replay failure output, and end with OK/WARNING/FAILED. Keep identity, dry-run itemization, receipts, and backup/rollback paths visible. Logs are diagnostic evidence, not rollback backups. Avoid wrapping state-mutating shell functions in conditional calls (Bash errexit semantics).

Affected files: scripts/update-pi-config.sh, tests/test_update_pi_config.py, pi/README.md. Inspect existing package/Craft/Langfuse updater consumers in tests; retain their deployment contracts. No dependency or exported API changes.

## Sequence

1. Add success/warning/failure regression tests using existing isolated destination fixtures; observe RED.
2. Implement command logging and final status; document log privacy, retention, warning semantics, preview behavior.
3. Run focused deployment tests, shell syntax, config checks, Ruff, full Python suite, deterministic routing/context evals. Review diff, commit task-owned files, direct-closeout.

Verification: `.venv/bin/python -m pytest tests/test_update_pi_config.py tests/test_package_patches.py tests/test_langfuse_evaluators.py tests/test_craft_batch.py`; repository checks from AGENTS.md. No live deployment or model canary.
