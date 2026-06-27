# Model notes: gpt-4.1-mini (all venues)

Observed failure modes for this family (see eval history): claiming a plan was
saved without creating the file, and writing to `~/.pi/plans` instead of the
project plans directory.

Hard rules:

- Resolve the plans directory only with `~/.pi/agent/bin/agnt plans-dir`.
  Never write under `~/.pi/plans`.
- A file you did not verify does not exist. After creating any artifact, run
  `test -f <path> && echo SAVED` and treat the command output as the only
  evidence of save.
- In strict workflow skills, do not summarize a gate as satisfied without the
  shell evidence the skill requires.
