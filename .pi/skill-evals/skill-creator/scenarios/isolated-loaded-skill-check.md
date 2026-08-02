# Scenario: Isolated loaded-skill behavior check

## Prompt
I already wrote the baseline scenario. What exact no-tool verification procedure should I use to prove the candidate skill was loaded during that original scenario and report exact harness usage without unrelated context? Give guidance only; do not edit files.

## Expected weak baseline
The agent says to make the candidate available without an executable method, uses `agnt invoke --one-shot` even though it disables skills, leaves unrelated context loaded, changes the scenario prompt, or estimates model calls and retries.

## Expected with skill
The agent runs direct Pi JSON mode with discovery disabled, explicitly adds and force-loads the candidate skill, preserves the original scenario, loads no tools by default, validates output locally, and derives accounting only from documented events.

## Assertions
- Uses direct `pi --mode json --print`, not `agnt invoke --one-shot`.
- Combines `--no-skills --skill <skill-directory>` with `/skill:<skill-name>`.
- Disables extensions, context files, prompt templates, session persistence, and tools for a no-tool scenario.
- Uses the smallest explicit `--tools` allowlist only when the scenario needs tools.
- Keeps the original scenario prompt and validates assertions locally.
- Reads usage only from assistant `message_end` events with usage.
- Counts usage-bearing assistant `message_end` events as model calls and `auto_retry_start` events as provider retries.
- Reports unavailable only for requested fields absent from harness events.
