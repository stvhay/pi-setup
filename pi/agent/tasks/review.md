---
id: review
summary: Independent code, design, or plan review with model diversity.
preferred:
  - openrouter-localish/google/gemma-4-31b-it
  - openrouter-localish/qwen/qwen3.5-9b
  - ollama/gemma4:31b
  - olla-local/qwen3:8b
qualified:
  - openai-codex/gpt-5.6-sol
  - olla-cloud/kimi-k2.7-code
  - olla-cloud/kimi-k3
  - olla-cloud/gpt-4.1-mini
  - olla-cloud/gemini-flash
---

Use several cheap/local reviewers, then verify findings against files and tests before acting. Kimi K2.7 Code adds a coding-focused review perspective; Kimi K3 is reserved for repository-scale, visual, or cross-domain review.
