# Evidence-complete delegated packet evaluation

## Protocol

Ran same `requesting_review_contract_change` model eval with deployed baseline skill and tracked candidate skill using `openai-codex/gpt-5.6-luna`. Both reviewed identical seeded `divide(a, 0)` contract change. Also ran tracked `dispatching_parallel_agents_readonly_contract` until generated peer prompts retained every packet field.

Commands:

```bash
./scripts/eval-workflow-compliance.sh --skill-mode deployed --case requesting_review_contract_change
./scripts/eval-workflow-compliance.sh --skill-mode candidate --case requesting_review_contract_change
./scripts/eval-workflow-compliance.sh --skill-mode candidate --case dispatching_parallel_agents_readonly_contract
```

Runtime evidence:

- deployed baseline: `/tmp/pi-workflow-evals/20260812-141026.UYecQm`
- candidate: `/tmp/pi-workflow-evals/20260812-141319.27tzXS`
- candidate packet check: `/tmp/pi-workflow-evals/20260812-140947.WGZv8C`

## Comparison

| Metric | deployed baseline | candidate |
|---|---:|---:|
| Finding yield | 1 confirmed | 1 confirmed |
| Verifier calls reported | 1 | 0 |
| Contract-change verdict | NEEDS_WORK | NEEDS_WORK |
| Workflow case | PASS | PASS |

Deployed summary reported Terra plus Kimi discovery and one independent verification. Candidate summary reached same confirmed finding through local primary-evidence inspection and reported no delegated verifier call. This small harness comparison proves no finding-yield loss for representative contract change; it does not replace broader paired calibration.

Candidate investigation output included objective, current decision, exact filesystem evidence and commands, external-evidence boundary, constraints, output schema, verification target, and stop conditions for both domains. No raw transcript or pasted repository source was used.
