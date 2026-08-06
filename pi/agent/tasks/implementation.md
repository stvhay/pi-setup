---
id: implementation
summary: Code editing after approval, usually with tests and focused verification.
preferred:
  - openai-codex/gpt-5.6-sol
qualified:
  - openai-codex/gpt-5.6-terra
  - openai-codex/gpt-5.6-luna
  - openrouter/moonshotai/kimi-k2.7-code
  - openrouter/minimax/minimax-m3
thinkingLow: medium
thinkingMedium: high
thinkingHigh: xhigh
---

Use only after the relevant workflow approval gate. Keep changes small and verifiable. Keep Sol as the normal implementation lead. Use Kimi K2.7 Code for a bounded different-family check and M3 as a canary until project evidence supports broader autonomy. Metered OpenRouter workers require fresh packets, strict TDD, and verification gates.
