---
id: review
summary: Independent code, design, or plan review with model diversity.
preferred:
  - olla-cloud/gemma-4-31b-it
  - olla-cloud/deepseek-v4-flash
  - olla-local/gemma4:31b
qualified:
  - olla-cloud/kimi-k2.7-code
  - openai-codex/gpt-5.6-sol
  - olla-cloud/qwen3.5-9b
  - olla-cloud/qwen3-coder-flash
  - olla-cloud/deepseek-v4-pro
  - olla-local/qwen3:8b
  - olla-cloud/gpt-4.1-mini
  - olla-cloud/gemini-flash
reviewLow:
  - olla-cloud/gemma-4-31b-it
reviewMedium:
  - olla-cloud/gemma-4-31b-it
  - olla-cloud/kimi-k2.7-code
reviewHigh:
  - olla-cloud/gemma-4-31b-it
  - olla-cloud/kimi-k2.7-code
  - olla-cloud/deepseek-v4-flash
reserveReview:
  - olla-local/gemma4:31b
  - olla-cloud/deepseek-v4-flash
hardCapReview:
  - olla-local/gemma4:31b
escalationTarget: olla-cloud/kimi-k3
---

Prefer reviewer independence from the authoring model family, then verify findings against files, tests, specifications, or profiling before acting. Run discovery peers as cold one-shot reviews with complete embedded packets; model confidence never triggers escalation.

Olla-cloud Gemma 4 31B is the fast cheap default, with Knuth-local Gemma as the zero-marginal-cost fallback and control. Medium-risk GPT-authored work adds one scoped Kimi K2.7 Code pass. High-risk work adds DeepSeek V4 Flash as a cheap independent boundary reviewer. Kimi K3 is not an automatic review candidate: use it only for a concrete unresolved critical finding after fresh adversarial verification and a budget check.

Review spend uses deterministic monthly gates. Below the reserve threshold, use the risk-specific sets above. At the reserve threshold, remove Kimi and prefer local Gemma plus DeepSeek. At the hard cap, use only local Gemma and surface the exhausted paid budget. Annotate real review and verification outcomes so routing accumulates evidence; do not manufacture review work solely to generate metrics.
