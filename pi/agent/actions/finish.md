---
id: finish
summary: Verify branch or project readiness and prepare safe next actions.
routingTask: orchestration
skills:
  - finishing-a-development-branch
defaultRole: verifier
allowedEffects:
  - read_workspace
  - write_artifacts
outputContract: readiness-report
---

# Action: finish

Use `finishing-a-development-branch` as sole closeout coordinator.
Do not pre-load or stack companion closeout skills; let coordinator select each phase.
Validate readiness with fresh evidence and prepare safe next actions. Do not
push, merge, deploy, or perform remote/destructive operations without explicit
approval.
