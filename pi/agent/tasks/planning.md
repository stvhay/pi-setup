---
id: planning
summary: Convert approved designs into concrete filesystem-first implementation plans.
preferred:
  - openai-codex/gpt-5.4-mini
  - openai-codex/gpt-5.5
qualified:
  - claude-sonnet-4-6
  - olla-cloud/glm-5.2
  - olla-cloud/gpt-4.1-mini
---

Use for plan writing, task sizing, dependency checks, and verification command selection. Prefer OpenAI/Codex for routine planning because Anthropic usage is retail-priced extra usage. Use GLM-5.2 as a long-context planning specialist for large codebases, complex refactors, or standards-heavy plans, but do not rely on Pi thinking-level controls for it because the Olla/OpenRouter route rejects reasoning/thinking request parameters.
