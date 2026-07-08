---
id: implementation
summary: Code editing after approval, usually with tests and focused verification.
preferred:
  - openai-codex/gpt-5.5
qualified:
  - openai-codex/gpt-5.4-mini
  - olla-cloud/glm-5.2:cloud
  - claude-sonnet-4-6
  - claude-opus-4-7
---

Use only after the relevant workflow approval gate. Keep changes small and verifiable. Prefer OpenAI/Codex when capability is comparable; Anthropic is retail-priced extra usage and should be reserved for work where it is likely to outperform the discounted default. Use GLM-5.2 only for approved large refactors or long-horizon agentic coding where its 1M-context reasoning is relevant, with strict TDD and verification gates.
