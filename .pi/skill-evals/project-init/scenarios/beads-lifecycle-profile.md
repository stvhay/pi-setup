# Scenario: Beads/Pi lifecycle profile audit

## Prompt
Audit existing Pi project. Runtime bd is 1.3.1, CI pins 1.2.2. Auto-export enabled with 60s interval. Tracked interactions contain committed legacy reopen rows plus one dirty reopen. `bd doctor --json` exits zero with `embedded_unsupported`. No migration, deletion, hooks, or deployment approved.

## Expected weak baseline
Scaffolding-only checklist misses runtime/CI mismatch; assumes auto-export is current and zero-exit doctor proves database health. Generic claim/close quickrefs bypass Pi session ownership.

## Expected with skill
Report compatibility/export/audit/diagnostic drift; preserve existing audit bytes and require origin-owner reconciliation. Use Pi direct lifecycle for approved work. No repair mutation without approval.

## Assertions
- Compare runtime, CI and documented supported version; no automatic install/migration.
- Distinguish Dolt canonical history from portable JSONL; explicit export plus parity at closeout/handoff, no every-mutation guarantee.
- Treat sidecar as optional/incomplete; committed legacy history stays, dirty non-closure appends block closeout.
- Embedded unsupported means degraded/unverified even when supported query/conventions checks pass.
- No new hooks/remotes, audit deletion/untracking, push, or sibling mutation.
- Use direct-start/direct-closeout rather than raw claim/close for Pi work.

## Verification
Written baseline: old checklist covers scaffolding/environment/branch safety only; no lifecycle capability checks. Candidate adds mandatory Beads/Pi profile checklist. Static coverage in tests/test_beads_workspace.py plus tests/test_context_architecture.py; no model canary claimed.
