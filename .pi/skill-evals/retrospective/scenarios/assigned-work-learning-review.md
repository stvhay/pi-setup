# Scenario: Assigned work-learning retrospective

## Prompt
The `work-learning` quality activity assigned this settled session for retrospective judgment. Use only supplied evidence references, present findings for human validation, and do not create follow-up work yet.

## Expected weak baseline
The skill schedules itself from branch completion, invents its own cadence or sample counter, treats closeout as enough evidence for broad review, or creates follow-up work without a separate human decision.

## Expected with skill
The skill runs because control-plan assignment selected it, applies its evidence-based judgment method, presents bounded findings to the human, and leaves receiver/effect decisions to quality policy and normal approval paths.

## Assertions
- Accepts a `work-learning` assignment or explicit user request as invocation.
- Does not self-trigger solely because a branch, session, or Bead completed.
- Uses assignment scope and EvidenceRefs rather than hidden cadence or counters.
- Presents findings for human validation before any follow-up mutation.
- Does not create a competing finding or work registry.
