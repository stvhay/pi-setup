# Scenario: Preserve bounded scope without new governance files

## Prompt
Initialize approved standard Pi scaffolding for an existing project that already uses Beads. Do not add charter, requirements, risk, glossary, ADR, or architecture files. The requested public API boundary has two interpretations with materially different compatibility consequences.

## Expected weak baseline
The agent makes a silent boundary choice, treats GitHub issues as canonical, or adds a new governance-document suite.

## Expected with skill
The agent keeps Beads canonical, puts the compact boundary rule in existing workflow guidance, and asks one targeted question with options and a recommendation before choosing between materially different API interpretations.

## Assertions
- Generated workflow guidance must require outcome, affected boundary, smallest implementation, and verification before public, persistent, security, dependency, or cross-cutting changes.
- Must ask one targeted question with options and a recommendation only when interpretations differ materially.
- `.project-init` must record `work_tracking` as `beads`.
- Must not add mandatory charter, requirements, risk, glossary, ADR, C4, or architecture artifacts.
