# Scenario: default install

## Prompt
/skill:improve-codebase-architecture Review this repository for deepening opportunities and stop after presenting the architecture report.

## Expected weak baseline
Pi cannot resolve `/skill:improve-codebase-architecture` because default package settings do not install it.

## Expected with skill
Pi loads pinned upstream skill plus its `codebase-design`, `domain-modeling`, and `grilling` companions, scans repository, and writes report outside repository.

## Assertions
- `improve-codebase-architecture` is available as explicit skill command.
- Required companion skills are available.
- Unrelated skills from upstream repository are not activated.
- Upstream source is pinned to reviewed commit.
- Report is written under OS temp directory, not repository.
