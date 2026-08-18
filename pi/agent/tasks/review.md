---
id: review
summary: Independent code, design, or plan review with model diversity.
preferred:
  - openai-codex/gpt-5.6-sol
qualified:
  - openai-codex/gpt-5.6-terra
  - openrouter/moonshotai/kimi-k2.7-code
  - openrouter/minimax/minimax-m3
  - openrouter/anthropic/claude-opus-5
reviewLow:
  - openai-codex/gpt-5.6-sol
reviewMedium:
  - openai-codex/gpt-5.6-sol
  - openrouter/moonshotai/kimi-k2.7-code
reviewHigh:
  - openai-codex/gpt-5.6-sol
  - openrouter/anthropic/claude-opus-5
reserveReview:
  - openai-codex/gpt-5.6-sol
hardCapReview:
  - openai-codex/gpt-5.6-sol
thinkingLow: low
thinkingMedium: medium
thinkingHigh: xhigh
---

Use Sol for first-pass review at low or medium thinking and at extra-high thinking for high risk. Keep Terra as a subscription-backed challenger. Medium-risk Kimi K2.7 Code and high-risk Opus 5 become eligible only with explicit token estimates, justification, and aggregate marginal budget; without all three, fanout stays subscription-only. Human adjudicates consequential findings. Verify every finding against files, tests, specifications, or profiling before acting. Model confidence never triggers escalation.

Kimi K3 remains escalation-only for a concrete unresolved critical finding after fresh adversarial verification and a budget check. Every metered OpenRouter reviewer runs in a fresh bounded worker with routed output/duration limits; never switch a long-running root conversation to it.

Review spend uses deterministic monthly gates. At reserve and hard-cap thresholds, keep subscription-backed Sol only. Annotate real review and verification outcomes so routing accumulates evidence; do not manufacture review work solely to generate metrics.
