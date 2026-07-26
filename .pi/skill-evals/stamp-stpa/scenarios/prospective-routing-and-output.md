# Scenario: Prospective safety analysis routing and output

## Prompt
We are designing an autonomous medication dispenser. Analyze what could go wrong, show its control structure, identify unsafe control actions, and produce traceable safety requirements. No incident has occurred.

## Expected weak baseline
The agent performs component-failure brainstorming, assigns unsupported probabilities, routes to retrospective CAST, or produces hazards without control paths and traceable constraints.

## Expected with skill
The agent stays in prospective STPA, defines losses and system hazards, maps controllers/actions/feedback, derives unsafe control actions and causal scenarios, and links safety requirements back to hazards or UCAs.

## Assertions
- Must use prospective STPA, not CAST.
- Must define system boundary, losses, and hazards.
- Must model controllers, control actions, controlled processes, and feedback.
- Must cover unsafe action categories and causal scenarios.
- Must produce traceable safety requirements.
- Must use the documented output/diagram reference when machine-readable or diagram output is requested.
