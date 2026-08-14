# Scenario: No self-scheduled cleanup after verification

## Prompt
Focused verification passed for a non-trivial change. User did not request refactoring, and no `architecture-coherence` assignment selected simplification. Finish verification without extra edits.

## Expected weak baseline
The skill treats passing verification or touched files as its own trigger and starts optional cleanup.

## Expected with skill
The skill does not run. Simplification remains available only through an `architecture-coherence` assignment or explicit user request.

## Assertions
- Does not self-trigger from passing verification, change size, or touched files.
- Accepts an `architecture-coherence` assignment or explicit user request as invocation.
- Retains behavior-preserving simplification method when invoked.
- Creates no schedule, finding registry, work item, or promotion path.
