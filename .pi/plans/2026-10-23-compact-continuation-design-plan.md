# Compact continuation recovery

Bead: pi-24u8. Approved implementation; no live deployment. Branch: main.

## Outcome and boundary

Reduce repeated startup output without summarizing away safety state. Existing default CLI responses remain unchanged. Add opt-in presentation-only `--compact` to direct-start and transition-recover; host kickoff chooses it. No lifecycle, ownership, approval, claim, dependency-validation or persistence changes.

The historical target of 10–15 KB is illustrative, not a truncation limit. Freeform current task notes may contain restrictions: retain them verbatim, even when large. Strip embedded dependency bodies (description/design/notes/acceptance criteria/metadata) with explicit pre-effect retrieval instructions, and duplicate workspace `changed` hash inventories with count/fingerprint and full-recovery command. Preserve all checkpoint progress, current task metadata, statuses, cancellation/uncertainty and recovery actions. Read-only replay showed retaining embedded decision metadata still exceeded 100 KB; keep references instead and require full referenced decision inspection before effects, including rejected/pending/revoked/consumed states. Never use compact output as effect authority.

## Files and steps

1. Tests first: tests/test_agnt.py (compact/default direct-start parity, errors), tests/test_work_continuation.py (progress and recovery parity; large workspace; uncertainty), tests/test_continuation_extension.py (actual generated kickoff).
2. Implement presentation in pi/agent/bin/agnt_lib/work.py and work_lifecycle.py. Update pi/agent/extensions/lib/work-continuation.ts kickoff: compact start/recovery instead of full bd show; inspect next-step evidence on demand and canonical decisions before effects. Keep source/target identity explicit for cross-Bead switches.
3. Update CLI README and work_lifecycle.SPEC.md. Fresh closed/unassigned handoff is not checkpoint resume; leave its policy/behavior unchanged.
4. Run focused tests, independent review, final project checks, commit task-owned files and direct-closeout.

## Verification

- `.venv/bin/python -m pytest tests/test_work_continuation.py tests/test_continuation_extension.py tests/test_agnt.py -q`
- Lifecycle/isolation/handoff regression tests.
- Full project checks from AGENTS.md, including complete Python gate.
- Synthetic large dependency/workspace fixtures demonstrate lossless semantic fields and reduced output; no hardware replay or claimed latency percentage.

No dependency additions, upgrades, new tools, model calls for classification, automatic deletion, global output middleware, or runtime deployment. Existing unrelated untracked plans/improvement-loop.md remain untouched.
