# Scenario: Internal branch closeout

## Prompt

Implementation in our own repository is complete. Check whether this branch is ready for our normal internal pull request and show merge options.

## Expected weak baseline

New upstream-contribution skill over-triggers and imposes fork profiles, AI upstream policy research, or fork-local staging workflow on ordinary internal branch closeout.

## Expected with skill

`preparing-upstream-pr` does not trigger. Use `finishing-a-development-branch` and normal project approval/verification rules.

## Assertions

- Must not select upstream-profile workflow.
- Must not require fork-local staging draft.
- Must route to branch-finishing workflow.
