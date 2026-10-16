# Scenario: file-scoped-spec-handoff

## Prompt
R14: src/store.py has sibling src/store.SPEC.md, root SPEC.md and docs/specs/MANIFEST.md. Contrast directory-only, nested target and no-spec repository.

## Expected weak baseline
Source-observed at pre-implementation baseline (not model-observed): Exact SPEC.md searches miss file-scoped specs; codify parent loop excludes root and does not check sibling first.

## Expected with skill
Discover sibling, governing parent/root and manifest. Docs hands contract authoring to codify-subsystem rather than creating duplicate contract.

## Assertions
- Execute documented find and ancestor commands in temporary fixtures, including spaces and extensionless target. Directory/no-spec searches terminate. Existing spec does not authorize replacement or duplication.
- Written scenarios and static checks do not measure model selection recall; real-model comparison NOT_VERIFIED.
