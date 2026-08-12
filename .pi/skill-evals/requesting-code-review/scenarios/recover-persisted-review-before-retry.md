# Scenario: Recover persisted review before retry

## Prompt
A cold code-review child returned truncated inline JSON. Its tool result also reports `artifactStatus: persisted` and `artifactRefs: [runtime:delegated-results/018f47a8-62c4-7e91-a969-7b4f6c78d308/child-0.json]`. Review still needs a validated findings document. For this scenario, `agnt runtime-path delegated-results` succeeds and that schema-1 artifact contains a complete, valid `finalOutput` with no serious findings. State exact next actions and reviewer retry count. Also state recovery when artifact resolution, reading, schema validation, or usable output fails.

## Expected weak baseline
Parent validates truncated inline content, treats it as malformed, and spends another reviewer call without inspecting persisted output.

## Expected with skill
Parent resolves existing delegated-results root, reads exact referenced child artifact, checks schema-1 identity and usable `finalOutput`, saves and validates that complete output, and finishes with zero reviewer retries. Only missing, unavailable, malformed, mismatched, or unusable persisted output permits one concise format-repair retry.

## Assertions
- Resolve root with `agnt runtime-path delegated-results` before any reviewer retry.
- Read exact suffix named by `runtime:delegated-results/...`; do not invent another URI or storage path.
- Accept only schema 1 artifact matching referenced invocation and child index with non-empty usable `finalOutput`.
- Save and run `agnt review validate` on recovered complete output.
- Complete valid persisted output means zero reviewer retries.
- Resolution, read, schema, identity, or usable-output failure permits at most one concise format-repair retry.
