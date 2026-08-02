# Scenario: Codex-first review with metered specialists

## Prompt
Review a medium-risk implementation diff in a repository where subscription-backed Codex is available and metered OpenRouter/Olla models have produced repeated credit failures and excess spend.

## Expected weak baseline
Skill automatically dispatches metered Gemma and Kimi reviewers, treats Codex as only a verifier/fallback, or reuses a metered model inside the parent conversation.

## Expected with skill
Skill follows `agnt route`: starts with fresh subscription-backed Codex, adds a fresh metered diversity reviewer only when risk warrants it, never selects Kimi automatically, and reserves Kimi K3 for an unresolved critical escalation after a budget check.

## Assertions
- Routine review starts with subscription-backed Codex.
- Metered Olla/OpenRouter calls use cold/fresh workers with bounded packets.
- Kimi K2.7 and Kimi K3 are not automatic review targets.
- Medium risk may add one diverse Gemma pass; high risk may add DeepSeek.
- Reserve/hard-cap review keeps Codex and local Gemma only.
