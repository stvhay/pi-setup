# Scenario: Evidence-complete agentic investigation

## Prompt
Delegate read-only investigation of failing loader behavior to agentic peer with repository access. Peer must decide without transcript access.

## Expected weak baseline
Prompt names symptom and one file but omits current decision, callers, verification command, and stop conditions. Peer spends another model turn locating primary evidence or repeats stale transcript hypotheses.

## Expected with skill
Packet states objective and current decision, then points to exact filesystem paths, symbols, and commands. It names constraints, output schema, verification target, stop conditions, and only external contract evidence peer cannot retrieve. No raw transcript or pasted repository source is included.

If worker lacks source access, packet substitutes bounded source excerpts needed for decision.

## Assertions
- Agentic worker receives retrieval manifest and uses filesystem evidence.
- Packet contains every shared evidence-complete field.
- No raw transcript is copied by default.
- Source excerpts remain bounded and appear only for inaccessible evidence.
- Peer can decide without transcript access or another evidence-finding call.
