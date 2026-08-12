# Repository Inspection Canary — 2026-08-12

## Decision

Keep qualified subscription-backed Codex as default for repository inspection. Do not promote metered M3 for repository inspection or fan-out from this canary: it showed lower strict validity, lower seeded-defect recall, higher latency, and nonzero marginal cost.

## Protocol

- Evidence: four existing tracked calibration packets, accessed by path with repository tools rather than embedded in task prompts.
- Cases: seeded and clean behavioral packets plus seeded and clean boundary packets.
- Models: `openai-codex/gpt-5.6-luna` (subscription) and `openrouter/minimax/minimax-m3` (metered).
- Execution: paired agentic workers, high thinking, inline output.
- Caller experiment limits per child: 4 provider requests, 40,000 total tokens, 180 seconds. M3 also had a $0.10 cost cap; four M3 children bounded requested aggregate cost at $0.40. These are calibration-only caller limits, not subscription defaults.
- Scoring: existing `review-routing-calibration/evaluate.py` JSON validation and semantic rubrics. Strict validity requires successful execution, schema-valid output, and at most 6,000 response characters.

An initial dispatch was rejected by the pre-change keyword guard before upstream execution; it made no model call. The measured dispatch used ignored local aliases containing exact copies of the four tracked packets so current transport could exercise agentic metered access without changing evidence.

## Results

| Target | Strict valid outputs | Seeded recall, usable output | Clean false positives | Median worker latency | Max worker latency | Requests | Tokens | Marginal cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Luna subscription | 3/4 | 4/4 (100%) | 0 | 20.1 s | 28.6 s | 9 | 134,893 | $0.000000 |
| M3 metered | 0/4 | 3/4 (75%) | 0 | 63.3 s | 181.0 s | 9 | 130,543 | $0.038015 |

### Run outcomes

| Case | Luna | M3 |
|---|---|---|
| behavioral seeded | valid; found A1/A2 | found A1/A2, but caller token limit made execution invalid |
| behavioral clean | valid PASS | PASS content, but 23,478-character response exceeded contract |
| boundary seeded | found B1/B2, but caller token limit made execution invalid | found B1 only; 10,826-character response exceeded contract |
| boundary clean | valid PASS | caller time limit; no JSON result |

Luna's one invalid execution and M3's token-limit execution both preserved usable complete JSON, showing the experimental 40,000-token cap can terminate otherwise useful agentic inspection. Production subscription agentic work therefore remains uncapped by default. Metered agentic admission still needs explicit token/cost bounds because marginal spend is nonzero.

## Rollout gate

- Quality regression: M3 failed (75% versus 100% usable seeded recall; 0/4 versus 3/4 strict validity).
- Latency regression: M3 failed (3.1× median worker latency; 6.3× max worker latency).
- Cost: subscription passed at zero marginal USD; M3 used $0.038015.
- Routing decision: subscription-first repository inspection. Metered agentic work remains exceptional and requires explicit quality/capability justification, estimate, aggregate budget, and per-child limits. No automatic metered fan-out promotion.

This one-repetition canary supports a conservative non-promotion decision; it is not sufficient evidence for future M3 promotion.
