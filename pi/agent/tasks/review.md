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

Prefer reviewer independence from the authoring model family over diversity for its own sake, then verify findings against files and tests before acting. For low-risk work, one cheap/local reviewer is enough. For medium-risk work, add a reviewer from a different family than the author: normally Kimi K2.7 Code for GPT-authored code, or GPT-5.6 Sol for Kimi-authored code. For high-risk, repository-scale, visual, or cross-domain work, use GPT-5.6 Sol and Kimi K3, optionally with a cheap/local reviewer. Opportunistically include Kimi in real reviews and annotate outcomes so routing accumulates evidence; do not create synthetic review work solely to generate metrics.
