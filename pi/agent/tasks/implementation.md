---
id: implementation
summary: Code editing after approval, usually with tests and focused verification.
preferred:
  - openai-codex/gpt-5.6-sol
qualified:
  - openai-codex/gpt-5.6-terra
  - openai-codex/gpt-5.6-luna
  - olla-cloud/glm-5.2
  - olla-cloud/kimi-k2.7-code
  - olla-cloud/kimi-k3
  - olla-cloud/qwen3-coder-flash
  - claude-sonnet-4-6
  - claude-opus-4-7
---

Use only after the relevant workflow approval gate. Keep changes small and verifiable. Prefer OpenAI/Codex when capability is comparable; Anthropic is retail-priced extra usage and should be reserved for work where it is likely to outperform the discounted default. Use Kimi K2.7 Code for coding-focused, long-horizon agent work and Kimi K3 for repository-scale or visual engineering work. Use Qwen3 Coder Flash only as a low-cost coding challenger until project evals establish autonomy; keep all challengers behind strict TDD and verification gates.
