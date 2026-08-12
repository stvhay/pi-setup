# Scenario: Evidence-complete boundary review

## Prompt
Review deployment boundary where conclusion depends on wrapper caller, configuration loader, and installed runtime behavior. Compare packet workflow with prior transcript-shaped review.

## Expected weak baseline
Packet embeds changed function only. Reviewer cannot test boundary claim without second evidence-finding model call; verifier must rediscover caller and runtime contract.

## Expected with skill
Boundary packet includes actual caller, loader, and runtime contract primary evidence, plus objective, current decision, exact sources/commands, inaccessible external contract evidence, constraints, output schema, verification target, and stop conditions. One-shot source excerpts stay bounded. No raw transcript is copied.

## Assertions
- Reviewer can decide without transcript access or second evidence-finding model call.
- Boundary conclusion cites actual caller, loader, and runtime contract.
- Packet stays within configured source, finding, response, and duration bounds.
- Comparison records finding yield and verifier-call count for prior and candidate workflow.
- Candidate does not reduce confirmed unique findings or increase verifier calls.
