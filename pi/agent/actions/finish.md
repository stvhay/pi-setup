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

Validate project or branch readiness with fresh evidence, summarize remaining
risks, and prepare safe next actions. Do not push, merge, deploy, or perform
remote/destructive operations without explicit approval.
