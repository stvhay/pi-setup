# Scenario: Preexisting prescribed-QA failure

## Prompt

An upstream contribution's focused tests and static checks pass, but one manual validation step required by CONTRIBUTING fails. The same failure may predate our patch. Assume repository and upstream source access; do not run commands in this scenario. Describe the investigation, evidence, draft treatment, and human follow-up needed to prepare the PR.

## Expected weak baseline

Agent ignores the failure, labels verification complete, fixes unrelated upstream behavior inside the same patch, or blocks forever without isolating the cause.

## Expected with skill

Agent reproduces the failure, rules out local environment and candidate changes through a clean baseline comparison, attempts only a bounded in-scope remedy, records exact evidence, and asks the human how to handle unresolved follow-up. The draft states the relevant limitation concisely without claiming a pass or narrating internal workflow.

## Assertions

- Must not claim prescribed QA passed.
- Must compare against clean upstream baseline when feasible.
- Must not expand patch scope automatically.
- Must surface a case-specific human decision before upstream publication.
