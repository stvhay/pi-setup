# Scenario: Accepted sentence revision

## Prompt
Use `token-saver`. Current accepted result: `Build small, verify once.` New change: replace `small` with `narrow`. Return exactly one sentence. This job needs no tools.

## Expected weak baseline
The agent may expose unnecessary tools, reprocess prior conversation, use another model for an exact rewrite, add explanation, or omit usage fields that the harness does not expose.

## Expected with skill
The agent loads only `token-saver`, exposes no tools, revises only the accepted result plus the new change, returns `Build narrow, verify once.`, and leaves accounting to reported harness fields without estimates.

## Assertions
- Exact output is `Build narrow, verify once.`
- No tools are loaded.
- No secondary model chooses the model.
- Verification reports fresh input, reused input, output, model calls, and retries; missing harness fields are `unavailable`.
- Skill requires local code before models for deterministic work, bounded passage retrieval, one-current-result promotion, complete-job model economics, request-shaped output, and at most one bounded repair.

## Trigger cases
- Should trigger: explicit `token-saver`, large-source extraction, iterative revision from an accepted result, or token/context budget work.
- Should not trigger: ordinary small talk with no token/context discipline request.
