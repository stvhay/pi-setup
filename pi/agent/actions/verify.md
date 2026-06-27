---
id: verify
summary: Evidence-first verification of a completion, readiness, or safety claim.
routingTask: review
skills:
  - verification-before-completion
defaultRole: verifier
allowedEffects:
  - read_workspace
  - write_artifacts
outputContract: verification-review
---

# Action: verify

Verify the requested claim or work item using fresh command evidence. Treat
success claims as unproven until tests, checks, diffs, or artifacts support
them. Write verification evidence to run artifacts when invoked through the
work backbone.
