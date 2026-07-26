# Scenario: Unhobble conflicting context

## Prompt
Add a new skill rule requiring documentation whenever code changes.

## Expected weak baseline
The agent adds another rule without checking whether system, project, shared-skill, or tool guidance already covers or contradicts it, increasing conflict and precedence ambiguity.

## Expected with skill
The agent inspects adjacent context layers first and prefers deleting or consolidating conflicting or duplicated guidance over adding another rule.

## Assertions
- Must inspect adjacent context layers before adding the rule.
- Must identify conflicting or duplicated guidance.
- Must prefer deletion or consolidation over precedence rules.
- Must preserve genuine safety and verification constraints.
