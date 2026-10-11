# Beads/Pi lifecycle repair plan

**Issue:** pi-q0ru
**Design:** Bead notes plus current source and isolated Beads 1.3.1 replay
**Date:** 2026-10-11
**Branch:** main

## Goal and boundaries
Predictable direct start/closeout/handoff, explicit export parity, truthful diagnostics. Edit tracked pi/ only for deployable config. No deployment, installed binary/schema change, sibling-project writes, hooks, remotes, push, audit deletion/untracking. Preserve pre-existing issues export and two unrelated plans.

## Evidence and decisions
- Baseline: focused lifecycle/handoff/workspace/doctor suite: 83 passed, 123 deselected.
- Graph maps direct_start -> link_current_session -> capture_session_link; verify current source because graph line numbers are stale.
- Start currently claims before session ownership check. Move claim into a callback under existing ledger lock after validation, before invocation append. Claim failure writes no link; conflicting/malformed session writes no claim. Reuse native idempotent `--claim` on retries to reject foreign claims. Disk/crash failure between stores cannot be transactional: report partial and retry same session, never auto-unclaim or offer ready-only handoff for claimed work.
- Installed 1.3.1 audit.enabled defaults false. Isolated replay: enabled explicit status update writes status row without reason; close writes closure/reason; claim and reopen command do not append. Handoff extension only invokes read-only handoff-check and creates fresh session. Historical writer attribution remains uncertain.
- Keep strict closure-only sidecar validator. Committed legacy history is opaque preserved baseline; dirty reopen/foreign/tampered/staged divergences block. Originating transition owner must reconcile uncommitted non-closure audit before closeout; no auto-adoption or deletion.
- Dolt canonical; auto-export throttled, not per-mutation promise. Explicit export and target parity required at portable handoff/closeout boundaries. JSONL is not full database-history backup.
- Align CI to installed/tested 1.3.1, require comments/provenance. Published Linux amd64 SHA256: 3219443a9734b89b93fb16ee8d65844759fa1b3cd3cf139c606b7353cfb0715c (official checksums.txt).
- Parse doctor JSON and mark embedded unsupported/unknown results degraded, not verified; supported read-only list/conventions checks have limited scope.

## Reach and execution
1. Regression-first lifecycle changes: pi/agent/bin/agnt_lib/work.py, improvement.py, quality.py; tests/test_agnt.py, tests/test_quality.py, tests/test_improvement.py. Cover open-target conflict, missing/malformed session, concurrent links, claim failure, storage failure/retry and foreign claim. Trace CLI + handoff extension callers; no extension changes unless required.
2. Audit regressions and integrated lifecycle: tests/test_agnt.py, tests/test_beads_workspace.py, tests/test_bead_handoff.py. Preserve legacy reopen baseline, reject dirty reopen and foreign/tampered/index changes. Real isolated 1.3.1 rapid transitions + explicit export parity, fresh-session start/closeout/handoff.
3. Diagnostics/setup: doctor.py, tests/test_doctor.py, .github/workflows/ci.yml, .beads/README.md, pi/agent/bin/README.md, pi/agent/skills/project-init/SKILL.md and references/audit-checklist.md; written skill scenario. No config policy toggles required.
4. Review, explicit task-owned staging, full gate, local atomic implementation commit. Record evidence in Bead, then direct-closeout creates portable-state commit; handoff only after success.

## Acceptance
- Session conflict/unavailable ownership fails before claim; concurrent session links cannot sneak between preflight and claim.
- Explicit claim retry uses native CAS, never steals foreign claim; partial storage failure offers usable same-session recovery, not ready-only handoff.
- Audit history preserved, authority boundary unchanged.
- Version/setup/export docs agree with tested runtime; embedded doctor cannot report full health green.

## Verification
```bash
.venv/bin/python -m pytest tests/test_agnt.py tests/test_quality.py tests/test_improvement.py tests/test_bead_handoff.py tests/test_beads_workspace.py tests/test_doctor.py -q
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt context-health --strict
```

Fresh focused RED/GREEN before each behavior change; independent read-only review before final gate. No real-model canary needed. Task regression and release verdict reported separately on failures.
