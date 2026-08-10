# Scenario: Scaffold current Node LTS toolchain

## Prompt
Initialize Pi-native environment scaffolding for an existing Node project whose `package.json` does not pin a runtime.

## Expected weak baseline
Agent copies stale Node 22 tooling into Nix configuration instead of current project Node 24 LTS.

## Expected with skill
Agent selects `nodejs_24` for detected Node project while preserving existing project files and approval gates.

## Assertions
- Must select `nodejs_24` for detected `package.json`.
- Must not select `nodejs_22`.
- Must preserve existing scaffolding unless changes are approved.
