# Model Portfolio Decision — August 2026

**Status:** Approved 2026-08-06

**Decision owner:** Repository owner

**Implementation Bead:** `pi-d1sw`

**Revisit:** After 30 days of direct OpenRouter telemetry, before any annual subscription or OpenAI Pro downgrade

## Decision

Keep ChatGPT/OpenAI Codex **Pro 20×** as root capacity and default controller. Use a small pay-as-you-go **OpenRouter API** portfolio for bounded, fresh delegated diversity calls. Do not add another subscription yet. Keep only configured Codex and OpenRouter venues; use Git history instead of dormant provider code for rollback.

Pi has a built-in `openrouter` provider. Authenticate with `/login openrouter` or `OPENROUTER_API_KEY`; do not define a duplicate custom provider and never commit credentials. `pi/agent/models.json` only applies a 16,384-token operational output cap to each approved OpenRouter model, preventing provider credit checks from reserving each model's much larger catalog maximum. Active model selection lives in `pi/agent/settings.json`, deterministic model facts in `pi/agent/catalog.json`, and task routing in `pi/agent/tasks/`.

## Temporary Sol-first floor

`pi-04q7.2` temporarily routes planning, research, and primary review to Sol at high thinking. Orchestration remains Sol at extra-high thinking, Luna remains the explicit cheap/mechanical peer, and Terra remains a subscription-backed review challenger. Operational reliability and user experience justify this reversible floor; they are not a lasting quality ranking. Matched canaries under `pi-04q7.4` decide whether to retain, narrow, or remove it.

Rollback is a policy-only revert: restore the prior routing in `pi/agent/tasks/planning.md`, `research.md`, and `review.md`; restore synchronized guidance in `pi/agent/skills/requesting-code-review/SKILL.md`, `pi/agent/bin/README.md`, and `docs/SELF-IMPROVEMENT.md`; then revert matching routing assertions and this amendment. No provider, credential, budget, or data migration change is involved. Live `~/.pi` deployment remains outside this task.

## Evidence basis

Local telemetry from 2026-07-21 through 2026-08-06 (15.86 days):

- 1,447 user prompts; peak 103 prompts in one rolling five-hour window.
- OpenAI/Codex workload: 178.4M fresh-input, 5.570B cache-read, and 16.8M output tokens.
- Provider-reported API-equivalent value: $2,247 for the window, approximately $4,251 per 30 days. This is replacement value, not cash spend.
- Delegated workload: 28.06M fresh-input, 520.57M cache-read, and 3.10M output tokens; approximately 1.04B tokens/month at the observed rate.
- Recent non-OpenAI metered work: 191 calls costing $0.376, approximately $0.71/month at the same call rate.
- Review evidence remains sparse: only 20 adjudicated findings across all models. Raw confirmed-finding counts are not accuracy rates.

Consequences:

1. Pro 20× is economically valuable and absorbs current peaks. Pro 5× has one quarter of its capacity; telemetry does not prove a downgrade safe.
2. Another subscription cannot beat current marginal API spend. It would buy capacity or convenience, not immediate cash savings.
3. MiniMax Plus is the first subscription candidate only if M3 proves useful at scale: its advertised ~1.7B M3 tokens/month nominally covers 1.6× the observed delegated run rate.
4. Copilot Pro+ is the premium-diversity candidate only when premium reviewer usage or access friction consistently justifies $39/month.

## Active API portfolio

| Role | Pi target | Default use |
|---|---|---|
| Bulk/canary peer | `openrouter/minimax/minimax-m3` | Cheap bounded critique, extraction, research, or decomposed workstream; shadow/canary until qualified |
| Coding/review challenger | `openrouter/moonshotai/kimi-k2.7-code` | Different-family coding or normal-review check |
| Frontier escalation | `openrouter/moonshotai/kimi-k3` | Concrete unresolved critical issue only, after budget and evidence gates |
| Independent high-risk reviewer | `openrouter/anthropic/claude-opus-5` | Architecture, high-risk review, or phase checkpoint |

GLM-5.2 remains unconfigured. Earlier relay-path calls produced almost no usable output; require direct-provider canary evidence before adding it again.

## Primary matrix

All metered OpenRouter calls use fresh workers with bounded complete packets. Different-family output is evidence to verify, never authority.

| Work type | Primary | Independent check |
|---|---|---|
| Precise, repetitive work | Luna — medium | M3 — bounded 10% shadow sample |
| Planning and research (temporary) | Sol — high | Luna control in matched canaries |
| Normal code review (temporary) | Sol — high | Terra challenger; Kimi K2.7 Code diversity pass |
| Complex/high-risk review (temporary) | Sol — extra high | Opus 5; Terra challenger; human adjudication |
| Moderate coding | Sol — high | Kimi K2.7 Code |
| Orchestration/main agent | Sol — extra high | Opus 5 at phase checkpoints only |
| Ambiguous change/architecture | Sol — extra high | Opus 5 |
| Difficult debugging | Sol — extra high | Kimi K3 high after two failed hypotheses |
| Exceptional single problem | Sol — maximum available | Opus 5; Kimi K3 max only if unresolved |
| Large decomposable project | Ultra-capability OpenAI coordinator | M3/Luna workstreams; Opus 5 final gate |

Use provider-native/default effort when Pi exposes no model-specific control. Never claim an unsupported effort level.

## Cost-balancing reverse matrix

This is an external-primary canary, not the default. Highest-risk control remains OpenAI-led until M3 earns promotion.

| Work type | External primary | OpenAI check |
|---|---|---|
| Precise, repetitive work | M3 | Luna medium, sampled |
| Normal code review | M3 | Terra high |
| Complex/high-risk review | M3 first pass | Terra extra high + human |
| Moderate coding | M3 | Terra high |
| Orchestration/main agent | M3 bounded phase | Sol extra high at every phase boundary |
| Architecture | M3 draft | Sol extra high final decision |
| Difficult debugging | M3 hypotheses/tests | Sol extra high after narrowing |
| Exceptional single problem | Keep Sol maximum as primary | Opus 5 or Kimi K3 independent check |
| Large decomposable project | Keep OpenAI coordinator; M3 workstreams | Terra extra high + Opus 5 integration gate |

## Spend and promotion gates

- Default API budget: **$10–20/month**.
- Review soft threshold: $12 month-to-date; stop optional shadow sampling.
- Review reserve threshold: $18; use subscription-backed Sol only during the temporary floor.
- Review hard cap: $20; use subscription-backed Sol only during the temporary floor and report exhaustion.
- Do not buy an annual plan during the evaluation window.
- Promote a route only from usable-output rate, accepted-result rate, missed-defect evidence, retries, latency, and real marginal cost—not benchmark claims or model agreement.
- Consider Pro 5× only after four consecutive weeks with at least 75% stable offload and OpenAI usage consistently below 25% of current capacity.

## 30-day evaluation

1. Keep Pro 20× and run direct OpenRouter peers only on bounded packets.
2. Record usable output, acceptance, verification outcome, provider retries, latency, and cost through existing invocation telemetry.
3. Keep M3 canary-only until it has enough accepted, verified work to compare against Luna/Terra controls.
4. Buy MiniMax Plus only if M3 handles delegated work non-inferiorly and expected direct M3 API spend exceeds its subscription cost.
5. Buy Copilot Pro+ only if premium-model usage or access friction consistently exceeds $39/month in value.
6. Reassess GLM only after a direct-provider transport canary succeeds.

## Confidence

- **High:** keep Pro 20×; API diversity is currently cheaper than another subscription.
- **Medium:** MiniMax Plus nominal capacity fit; vendor quota semantics may not equal telemetry tokens.
- **Low:** external quality ranking; adjudicated denominators are insufficient.

## Verified plan sources

Prices and limits were checked on official pages on 2026-08-06:

- [OpenAI Codex pricing](https://chatgpt.com/codex/pricing/)
- [OpenRouter provider support in Pi](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/docs/providers.md)
- [Z.AI GLM Coding Plan](https://z.ai/subscribe)
- [GitHub Copilot plans](https://github.com/features/copilot/plans)
- [MiniMax Token Plans](https://platform.minimax.io/subscribe/token-plan)
- [Kimi K3 pricing](https://www.kimi.com/resources/kimi-k3-pricing)

## Rollback

Restore prior provider code, enabled targets, and task policy from Git history only after explicit human approval, then redeploy with `scripts/update-pi-config.sh`. No data migration is involved.
