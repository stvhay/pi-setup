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
thinkingLow: high
thinkingMedium: high
thinkingHigh: xhigh
---

Temporarily use Sol for first-pass review while matched canaries run. Keep Terra as a subscription-backed challenger. Medium risk adds Kimi K2.7 Code as a bounded different-family challenger; high risk uses Opus 5 plus human adjudication for consequential findings. Verify every finding against files, tests, specifications, or profiling before acting. Model confidence never triggers escalation.

Kimi K3 remains escalation-only for a concrete unresolved critical finding after fresh adversarial verification and a budget check. Every metered OpenRouter reviewer runs in a fresh bounded worker; never switch a long-running root conversation to it.

Review spend uses deterministic monthly gates. At reserve and hard-cap thresholds, keep subscription-backed Sol only. Annotate real review and verification outcomes so routing accumulates evidence; do not manufacture review work solely to generate metrics.
