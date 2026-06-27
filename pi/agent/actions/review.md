---
id: review
summary: Evidence-backed review of a target artifact, diff, plan, or document.
routingTask: review
skills:
  - documentation-standards
defaultRole: documentation-reviewer
allowedEffects:
  - read_workspace
  - write_artifacts
outputContract: findings-with-evidence
---

# Action: review

Review the requested target and produce concrete findings with file/path or
command evidence. Use the selected skill for method and the selected role for
report shape. Do not mutate repository files unless a separate implementation
action explicitly allows it.
