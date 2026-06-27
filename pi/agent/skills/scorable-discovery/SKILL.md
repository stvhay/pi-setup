---
name: scorable-discovery
description: Use when optimizing code, algorithms, prompts, heuristics, models, or configurations against an objective scoring metric.
---

# Scorable Discovery

Optimize candidate solutions only when progress can be objectively measured. This is inspired by computational discovery systems such as evolutionary coding agents, but remains honest about local tooling: no improvement claim without evaluator evidence.

## Core rule

No baseline, no leaderboard, no improvement claim. Establish the scorer and baseline before generating or editing candidate solutions.

## When to use

Use for:

- algorithm or heuristic optimization
- prompt/config/model selection against metrics
- empirical software experiments
- performance/quality tradeoff exploration
- candidate code variants scored by tests, benchmarks, or evals

Do not use for:

- ordinary feature implementation without an objective metric; use `test-driven-development` / `executing-plans`
- open-ended hypothesis generation; use `hypothesis-tournament`
- literature review; use `literature-synthesis`
- changes that cannot be sandboxed, reverted, or evaluated safely

## Required inputs

Before optimization, define or obtain:

- task description
- candidate representation: file, patch, prompt, config, model, parameter set
- evaluator command and environment
- primary metric and direction: maximize/minimize
- guardrail metrics: correctness, latency, cost, safety, regressions
- budget: time, number of candidates, model calls, compute
- acceptance threshold
- rollback strategy

If there is no evaluator, first design one. If an evaluator cannot be built, do not use this workflow.

## Workflow

### 1. Define the scorable task

Write a compact task card:

```markdown
## Scorable task
- Candidate:
- Evaluator command:
- Primary metric:
- Guardrails:
- Budget:
- Acceptance threshold:
```

### 2. Establish baseline

Run the evaluator on the current candidate and record raw output.

```bash
<evaluator command for baseline>
```

Capture:

- commit/worktree state if relevant
- baseline metric values
- evaluator version/data
- variance notes if the scorer is noisy

For noisy metrics, run multiple trials or explicitly label results as tentative.

### 3. Generate bounded candidate families

Explore diverse but controlled changes:

- simple baseline-preserving variants
- parameter sweeps
- recombinations of known good approaches
- larger architectural variants only if budget allows
- ablations to identify what matters

Use peers for independent candidate ideas when helpful, but require executable/evaluable outputs before accepting claims.

### 4. Evaluate in isolation

For each candidate:

- apply candidate in an isolated branch/worktree/temp file when practical
- run the same evaluator command
- record raw metrics
- capture failures and error logs
- revert or isolate before next candidate

Do not mix multiple changes unless the candidate definition says so.

### 5. Maintain a leaderboard and lineage

Track every meaningful run:

| ID | Parent | Change summary | Primary metric | Guardrails | Result | Notes |
|---|---|---|---|---|---|---|

Keep failed candidates. They prevent repeated mistakes and reveal constraints.

### 6. Select and verify winner

A winner must:

- beat the baseline by the acceptance threshold
- satisfy guardrails
- be reproducible with a fresh evaluator run
- be understandable enough to maintain or document
- include rollback or follow-up notes when risky

If no candidate wins, report the best evidence and stop. Do not force a positive result.

## Output format

```markdown
## Scorable Discovery: <task>

### Task card
- Candidate:
- Evaluator:
- Primary metric:
- Guardrails:
- Budget:

### Baseline
<command and raw score summary>

### Candidate leaderboard
| ID | Parent | Change | Score | Guardrails | Status |
|---|---|---|---|---|---|

### Winner / result
- Selected candidate:
- Evidence:
- Tradeoffs:
- Repro command:
- Confidence:

### Failed or rejected candidates
- <candidate>: <reason>

### Next experiments
- <if useful>
```

## Safety and honesty

- Prefer deterministic evaluators. Label nondeterminism.
- Never optimize against a metric while hiding correctness regressions.
- Avoid benchmark overfitting; keep holdout data when possible.
- Do not run untrusted generated code outside a sandbox.
- Do not claim AlphaEvolve/ERA-level search unless actual helper tooling ran that scale of search.

## Integration

- Use `test-driven-development` to create or improve evaluators before optimization.
- Use `using-git-worktrees` for risky candidate isolation.
- Use `verification-before-completion` before reporting a winning change as complete.
- Future helper tooling could wrap this workflow as an `agnt discover` command; until then, keep the run log explicit.
