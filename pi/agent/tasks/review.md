---
id: review
summary: Independent code, design, or plan review with model diversity.
preferred:
  - openai-codex/gpt-6-astra
qualified:
  - openai-codex/gpt-5.6-terra
  - openrouter/moonshotai/kimi-k2.7-code
  - openrouter/minimax/minimax-m3
  - openrouter/anthropic/claude-opus-5
  - openai-codex/gpt-5.6-sol
reviewLow:
  - openai-codex/gpt-6-astra
reviewMedium:
  - openai-codex/gpt-6-astra
  - openrouter/moonshotai/kimi-k2.7-code
reviewHigh:
  - openai-codex/gpt-6-astra
  - openrouter/anthropic/claude-opus-5
reserveReview:
  - openai-codex/gpt-6-astra
hardCapReview:
  - openai-codex/gpt-6-astra
thinkingLow: medium
thinkingMedium: medium
thinkingHigh: high
---

Use Astra for first-pass review at medium thinking and at high thinking for high risk. Keep Terra as a subscription-backed challenger. Medium-risk Kimi K2.7 Code and high-risk Opus 5 become eligible only with explicit token estimates, justification, and aggregate marginal budget; without all three, fanout stays subscription-only. Human adjudicates consequential findings. Verify every finding against files, tests, specifications, or profiling before acting. Model confidence never triggers escalation.

Kimi K3 remains escalation-only for a concrete unresolved critical finding after fresh adversarial verification and a budget check. Every metered OpenRouter reviewer runs in a fresh bounded worker with routed output/duration limits; never switch a long-running root conversation to it.

Review spend uses deterministic monthly gates. At reserve and hard-cap thresholds, keep subscription-backed Astra only. Annotate real review and verification outcomes so routing accumulates evidence; do not manufacture review work solely to generate metrics.
