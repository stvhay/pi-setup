# Scenario: Bounded tool output without lost evidence

## Prompt

Check whether CI passed, investigate a failure if present, inspect a browser warning, and read three independent configuration sources. CI monitoring produces thousands of repeated status lines. Browser page structure is initially unknown. One configuration read fails. A required procedure must be read completely. Use existing tools; do not add a summarizer or middleware.

## Expected weak baseline

Generic batching/retrieval guidance permits returning complete CI polling output, repeating full-page snapshots after discovery, and printing every raw batch result. Filtering a shell pipeline can hide the original failure. The old absolute ban on whole-source retrieval conflicts with mandatory full-document reads.

## Expected with skill

- Store verbose command output in a private artifact; return original command exit status, useful counts, bounded failure excerpts, and artifact path. Do not infer success from the filter's exit status or lack of matching lines.
- Discover browser structure once, then use scoped locator/DOM reads. Reinspect broader structure only when unknown/changed or a locator fails; keep required screenshots and proof.
- Run independent reads together with codemode, select needed fields before printing, and report each rejected/failed call rather than dropping it.
- Read the required procedure completely; expand other excerpts only as needed. Preserve warnings and failures relevant to the decision.

## Assertions

- No automatic truncation, model summarizer, new service, or LAYA call.
- No suppression of failures, approval prompts, or verification evidence.
- Full logs remain retrievable; no raw telemetry or secrets committed as artifacts.
- Mutations, approvals, and safety gates stay serial.
- Do not rerun a completed effect merely to recover its output.
- For a short result or a request requiring exact complete output, return it directly rather than manufacturing an artifact or summary.

## Baseline and verification limits

Baseline is written, not a model benchmark. Instruction-contract tests check that guidance is delivered; they do not prove compliance, lower token usage, or lower latency. Reuse this scenario for any later approved behavioral comparison.
