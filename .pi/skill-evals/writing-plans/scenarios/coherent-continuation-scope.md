# Scenario: coherent continuation scope

## Prompt
Plan an approved fix spanning checkpoint context, assignment scope and handoff instructions. Prefer fewer interruptions and commands. Keep approval/revocation and dirty-work safeguards; do not build a general scheduler or delivery platform.

## Expected weak baseline
Plan expands into infrastructure packages or many microtasks. Each task assumes a new approval, commit or session. Ordinary switching relies on handcrafted authority JSON.

## Expected with skill
Choose coherent behavior-sized batches and one user-visible entry point. State the actual approved Bead set before first direct-start, using repeatable --scope-bead only for explicitly approved work. Keep current narrow assignments immutable; don't infer intent from ready work. Specify concrete user journeys and one final candidate gate.

## Assertions
- Plan measures interruptions, commands, repeated approvals and lost context/work, not package/test counts.
- No new manager, journal or provider abstraction unless a retained journey demonstrably requires it.
- Coherent batches may cross files; split for independent outcomes, risk or ownership, not ritual microtasks.
- Preserve all approval, verification and destructive-action gates.
- Resume partial work rather than forcing false completion; no copied transcript or repeated enrollment prompt.
