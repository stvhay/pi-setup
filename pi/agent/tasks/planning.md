---
id: planning
summary: Convert approved designs into concrete filesystem-first implementation plans.
preferred:
  - openai-codex/gpt-5.4-mini
  - openai-codex/gpt-5.5
qualified:
  - claude-sonnet-4-6
  - olla-cloud/glm-5.2:cloud
  - olla-cloud/gpt-4.1-mini
---

Use for plan writing, task sizing, dependency checks, and verification command selection. Prefer OpenAI/Codex for routine planning because Anthropic usage is retail-priced extra usage. Use GLM-5.2 as a long-context planning specialist for large codebases, complex refactors, or standards-heavy plans; use `high` normally and `xhigh` for the hardest long-horizon planning.
