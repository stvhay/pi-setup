# Shared and local-only Beads

**Issue:** pi-13kj
**Date:** 2026-10-28
**Branch:** main (existing checkout; no branch/deployment/migration requested)
**Approval:** User approved reviewed dual-mode design in current session.

## Contract

Git tracking is publication choice, not work-tracking authority. Tracked `.beads/issues.jsonl` retains shared export/parity/commit behavior. Without that tracked export, local-only requires an explicitly ignored `.beads/` directory and no tracked paths beneath it. Mixed or ambiguous state fails before outcome/native mutation. Never infer local-only from a missing export alone; never stage local Beads. Existing repositories are not migrated.

Local-only still requires canonical successful closure readback, session/checkout ownership, current authority, clean tracked code, and terminal ownership release. It does not require a JSONL export or Git-commit authority. Native Beads may maintain ignored bookkeeping. Recheck publication mode and target identity around effects. Handoff uses same mode decision. Ignored state is not cloned by Git; existing published history remains published.

## Steps and files

1. Baseline focused lifecycle tests, then add RED local-mode regressions in `tests/test_closeout_authority.py` and native/worktree coverage in `tests/test_beads_workspace.py`.
2. Implement shared mode resolver and minimal local branch in `pi/agent/bin/agnt_lib/work.py`; preserve existing export security boundary. Cover authority denial/revocation, ambiguous/mixed mode, mode drift, malformed closure and dirty tracked code.
3. Update `pi/agent/AGENTS.md`, shared workflow skill and project-init checklist, CLI README and lifecycle SPEC. Add written skill baseline scenario; update static contract tests as necessary.
4. Focused GREEN, peer review, explicit task-owned staging, project verification matrix, local implementation commit, direct closeout. No push or deployment.

## Verification

- Baseline: `.venv/bin/python -m pytest -q tests/test_agnt.py tests/test_closeout_authority.py tests/test_beads_workspace.py tests/test_context_architecture.py` — 349 passed; `.pi/reviews/local-only-beads/baseline.log`.
- Focused: same files plus local-only tests and lifecycle/isolation regressions as affected.
- Final: `npm ci --ignore-scripts`; `scripts/check-pi-config.sh`; `bash -n scripts/*.sh`; `.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests`; `.venv/bin/python scripts/check-python-tests.py`; `pi/agent/bin/agnt eval run routing-smoke`; `pi/agent/bin/agnt eval run role-context-smoke`; diff checks.
- Plugin patches/dependencies are not modified by this feature; no live deployment authorized.
