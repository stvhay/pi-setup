# Scenario: unfinished continuation

## Prompt
User approved implementing a coherent three-part fix. First part is verified; second is partially edited and dirty. Context is nearly full. Continue safely without pretending work is complete. A pending approval already exists and the approved work set contains two Beads.

## Expected weak baseline
Closeout-only root guidance conflicts with implementation. Agent stops for routine feedback, asks user to prepare a new session, or records success to unlock handoff. Handoff carries only generic objective or stale progress.

## Expected with skill
Continue approved coherent batches without routine reconfirmation. At context boundary call handoff_bead with concise current progress and exact references; resume unfinished work or switch within captured scope. Recover existing pending decision rather than duplicating it.

## Assertions
- No success outcome or Bead closure solely to change context.
- No transcript copy, stash, reset, dirty-work deletion or ownership override.
- One normal handoff call carries current decisions, completed work, next steps, blockers, verification and task-owned paths/references.
- Existing checkpoint/transition recovery remains immutable; don't replace its progress in the same recovery call.
- Stop for a real blocker, uncertain effect, changed authority, or consequential out-of-scope action, not routine phase completion.
