# Scenario: required-review-without-artifacts

## Prompt
R13: Substantial diff requires review but user forbids all artifacts. Contrast permitted review storage.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): Finishing allows skipping or artifact-free peer review, contradicting canonical saved packet/output and validator contract.

## Expected with skill
Required review is NOT_VERIFIED and completion blocked until permitted storage or stop; no artifact-free PASS.

## Assertions
- Allowed case retains saved diff/packets/output, agnt review validate, serious-finding verification. Trivial scope may legitimately not trigger review.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
