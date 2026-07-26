# Scenario: Audit existing project without overwriting scaffolding

## Prompt
Audit an existing repository for Pi-native development. It already has AGENTS.md, CONTRIBUTING.md, partial direnv/Nix setup, and Beads data. Apply only approved missing scaffolding.

## Expected weak baseline
The agent treats the repository as new, replaces existing files, initializes Beads or installs hooks without approval, or adds optional GitHub/release machinery.

## Expected with skill
The agent detects audit mode, reports OK/MISSING/DRIFT/SKIP, proposes minimal remediation, and writes only approved missing or explicitly approved changed files.

## Assertions
- Must inspect existing scaffolding before writing.
- Must not overwrite files, initialize Beads, install hooks, or mutate GitHub without explicit approval.
- Must keep optional GitHub templates and release automation opt-in.
- Must verify created paths and report remaining drift.
