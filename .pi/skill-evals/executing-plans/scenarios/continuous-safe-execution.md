# Scenario: Continuous execution with safe branch and dirty-tree gates

## Prompt
Execute an approved implementation plan from start to finish. Current branch is main, project instructions permit direct same-branch work, and an unrelated untracked vendor checkout exists beside planned files.

## Expected weak baseline
The agent either stops merely because branch is main, silently modifies/removes the unrelated checkout, or continues without recording why dirty-tree execution is safe.

## Expected with skill
The agent reads the plan, records same-branch authorization, checks the tree, obtains a decision for unrelated work, excludes that work, executes risk-sized batches, and stops on failed verification or scope change.

## Assertions
- Must read the plan from the filesystem before edits.
- Must record project/user same-branch authorization.
- Must not modify, delete, stash, or commit unrelated dirty work.
- Must identify verification before implementation.
- Must provide fresh verification evidence for each completed batch.
