---
id: review
summary: Independent code, design, or plan review with model diversity.
preferred:
  - openai-codex/gpt-5.6-sol
  - olla-cloud/gemma-4-31b-it
  - olla-local/gemma4:31b
qualified:
  - openai-codex/gpt-5.6-luna
  - olla-cloud/deepseek-v4-flash
  - olla-cloud/qwen3.5-9b
  - olla-cloud/qwen3-coder-flash
  - olla-cloud/deepseek-v4-pro
  - olla-local/qwen3:8b
  - olla-cloud/gpt-4.1-mini
  - olla-cloud/gemini-flash
reviewLow:
  - openai-codex/gpt-5.6-sol
reviewMedium:
  - openai-codex/gpt-5.6-sol
  - olla-cloud/gemma-4-31b-it
reviewHigh:
  - openai-codex/gpt-5.6-sol
  - olla-cloud/gemma-4-31b-it
  - olla-cloud/deepseek-v4-flash
reserveReview:
  - openai-codex/gpt-5.6-sol
  - olla-local/gemma4:31b
hardCapReview:
  - openai-codex/gpt-5.6-sol
  - olla-local/gemma4:31b
escalationTarget: olla-cloud/kimi-k3
---

Prefer subscription-backed Codex for the first pass, then add a different model family only when risk or reviewer independence warrants it. Verify findings against files, tests, specifications, or profiling before acting. Run discovery peers as cold one-shot reviews with complete embedded packets; model confidence never triggers escalation.

Medium risk adds cheap Gemma diversity. High risk adds DeepSeek V4 Flash as a scoped boundary reviewer. Kimi K2.7 is not a routine reviewer. Kimi K3 remains escalation-only for a concrete unresolved critical finding after fresh adversarial verification and a budget check.

Review spend uses deterministic monthly gates. At reserve and hard-cap thresholds, keep subscription-backed Codex and local Gemma only. Annotate real review and verification outcomes so routing accumulates evidence; do not manufacture review work solely to generate metrics.
