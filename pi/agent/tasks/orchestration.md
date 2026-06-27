---
id: orchestration
summary: Strict workflow control, approval gates, planning, verification, and branch-readiness decisions.
preferred:
  - openai-codex/gpt-5.5
qualified:
  - openai-codex/gpt-5.4-mini
  - olla-cloud/gpt-4.1-mini
  - claude-sonnet-4-6
avoid:
  - ollama/*
  - olla-local/*
---

Use for high-stakes control flow where tool discipline matters more than cheap breadth. Keep OpenAI/Codex as the default controller; use Anthropic only when retail-priced extra usage is justified.
