# Matched Model and Output-Contract Canary — August 2026

## Decision

Keep current temporary Sol-first floor unchanged pending lasting policy work. This canary found no basis for replacing Sol with Luna for planning/research or Terra for first-pass review. It also showed that output contracts can reduce parent context without a new output framework:

- `artifact` removed full child results from parent-visible tool output while preserving complete private artifacts, but did not reduce provider generation.
- `status-only` reduced both provider output and parent-visible result volume on deterministic checks.
- `pass-no-findings` removed parent-visible result volume, but one of two calls violated the requested one-line shape and generated more output than its inline match.

These results are small, synthetic canary evidence, not a permanent model ranking or route decision.

## Protocol

The canary ran 60 subscription-backed one-shot child calls:

- ten planning/research packet pairs: five planning and five source-synthesis cases, Luna at medium thinking versus Sol at high;
- ten review packet pairs: five seeded defects and five clean controls, Terra versus Sol at high thinking; and
- ten output-contract pairs on Sol at high thinking: five `inline` versus `artifact`, three `inline` versus `status-only`, and two `inline` versus `pass-no-findings`.

Each model pair held packet, execution mode, 180-second deadline, verifier, and acceptance rule constant. Output pairs held model, thinking, execution mode, deadline, and evidence constant; status-oriented prompts changed only the required result shape. Deterministic parent scoring kept execution success, usable result, strict contract validity, and accepted answer separate.

All 60 calls completed in one provider turn and persisted a private result artifact. No additional provider turn was observed; provider-internal transport retries were not exposed. Raw prompts, outputs, paths, session IDs, and invocation IDs remain private.

## Model results

### Planning and research

| Target | Executed | Usable | Accepted | Median / p95 latency | Output tokens | Parent-visible result chars |
|---|---:|---:|---:|---:|---:|---:|
| Luna, medium | 10/10 | 10/10 | 8/10 | 7.43 s / 9.98 s | 1,550 | 1,811 |
| Sol, high | 10/10 | 10/10 | 10/10 | 7.51 s / 9.00 s | 937 | 1,519 |

Luna produced two accepted-rule misses classified as unsupported facts. Sol met every fixed acceptance rule and used 40% fewer output tokens. Median latency was effectively tied in this single-run sample.

### Review

| Target | Executed | Usable | Accepted | Median / p95 latency | Output tokens | Parent-visible result chars |
|---|---:|---:|---:|---:|---:|---:|
| Terra, high | 10/10 | 10/10 | 9/10 | 7.47 s / 15.28 s | 1,955 | 2,246 |
| Sol, high | 10/10 | 10/10 | 10/10 | 8.62 s / 10.81 s | 1,205 | 1,995 |

Terra produced one accepted-rule miss classified as an extra adjacent-anchor finding. Sol met every fixed acceptance rule. Terra's median was faster, while Sol's p95 and output volume were lower; ten single runs cannot establish a stable latency difference.

## Output-contract results

Parent-visible result characters count child result payload only; fixed progress lines and private artifact references are excluded. Generated result characters count complete persisted final responses.

| Matched pair | Contract | Accepted | Strict shape | Output tokens | Generated result chars | Parent-visible result chars |
|---|---|---:|---:|---:|---:|---:|
| Full result, 5 calls | `inline` | 5/5 | 5/5 | 625 | 1,703 | 1,703 |
| Full result, 5 calls | `artifact` | 5/5 | 5/5 | 625 | 1,703 | 0 |
| Deterministic status, 3 calls | `inline` | 3/3 | 3/3 | 95 | 290 | 290 |
| Deterministic status, 3 calls | `status-only` | 3/3 | 3/3 | 15 | 9 | 0 |
| Review result, 2 calls | `inline` | 2/2 | 2/2 | 44 | 113 | 113 |
| Review result, 2 calls | `pass-no-findings` | 2/2 | 1/2 | 73 | 167 | 0 |

`artifact` cut measured parent-visible result payload by 100% with identical generated volume in its matched cohort. It is a parent-context control, not a generation-cost control. `status-only` cut output tokens by 84% and generated result characters by 97% while preserving all three decisions. Both `pass-no-findings` results remained usable, accepted, and persisted, but one missed the exact one-line shape and the pair showed no generation-volume benefit.

## Capture limitation

Parent result records preserved the requested provider/model, effective one-shot mode, thinking level, deadline, provider turn count, outcome, output, and artifact status. The invocation metrics emitted by the currently loaded runtime preserved `outputContract`, usage, duration, and execution outcome, but classified all 60 calls as task `peer`, mode `subagent`, thinking `default`, and no work item. Metric-only analysis therefore cannot prove the matched task/mode/thinking dimensions for this cohort; this report uses the private parent result records instead.

Resolve that live-runtime capture gap before automated routing consumes these canary dimensions. It does not invalidate measured execution or accepted outputs, but it lowers confidence in telemetry-only comparisons.

## Confidence

- **High:** all 60 calls executed, used one observed provider turn, and persisted complete private artifacts; `artifact` and status-oriented contracts removed child result payloads from parent-visible tool output in this runtime.
- **Medium:** `status-only` reduces generated volume for small deterministic completion checks.
- **Low:** relative model quality or latency beyond these constrained packets. Ten packets per comparison, one run per cell, and synthetic rubrics cannot support a lasting route change.
