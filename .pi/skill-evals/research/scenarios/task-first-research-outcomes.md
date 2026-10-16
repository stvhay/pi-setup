# Scenario: task-first-research-outcomes

## Prompt
R9: Compare papers / rank explanations / evaluate program go-no-go / optimize metric / look up facts. R18: Perform background check. M3: Literature synthesis, then requested hypotheses, then requested feasibility.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): Research selects depth/fanout first and mandates absent OSINT skill; specialist output boundaries are not explicit.

## Expected with skill
Select literature-synthesis, hypothesis-tournament, heilmeier-catechism or scorable-discovery by requested output. Fact retrieval stays research; background checks remain excluded without invented dependency.

## Assertions
- No mandatory scientific pipeline or retrieval routing loop. M3 carries source IDs/locations, limitations and uncertainty; next stage requires requested scope. Preserve URL verification.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
