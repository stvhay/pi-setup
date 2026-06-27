---
id: implement
summary: Execute an approved bounded implementation task with verification.
routingTask: implementation
skills:
  - executing-plans
defaultRole: implementation-worker
allowedEffects:
  - read_workspace
  - write_artifacts
  - edit_files
  - update_beads
outputContract: implementation-report
---

# Action: implement

Implement only approved, bounded work. Use the assigned plan or bead as scope,
write or update tests when behavior changes, and report changed files plus fresh
verification evidence.
