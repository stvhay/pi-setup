---
id: orchestration
summary: Strict workflow control, approval gates, planning, verification, and branch-readiness decisions.
preferred:
  - openai-codex/gpt-6-astra
qualified:
  - openai-codex/gpt-5.6-terra
  - openai-codex/gpt-5.6-luna
  - openrouter/anthropic/claude-opus-5
  - openai-codex/gpt-5.6-sol
thinkingLow: high
thinkingMedium: high
thinkingHigh: high
---

Use for high-stakes control flow where tool discipline matters more than cheap breadth. Keep Astra as controller. Use Opus 5 only for bounded phase checkpoints or independent architecture review, never as an unbounded continuation of the root conversation.
