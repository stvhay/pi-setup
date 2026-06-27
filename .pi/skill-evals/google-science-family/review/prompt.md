Review these three new Pi skill definitions against their baseline scenario assertions. Return PASS/FAIL per skill with concise evidence and any blocking fixes.

=== hypothesis-tournament skill ===
---
name: hypothesis-tournament
description: Use when generating, ranking, critiquing, or refining research hypotheses, mechanisms, explanations, or testable investigation plans.
---

# Hypothesis Tournament

Generate and refine hypotheses through breadth, critique, tournament ranking, and falsifiable research planning. Use this when the user needs plausible discoveries or explanations, not merely a list of ideas.

## Core rule

Do not present generated hypotheses as facts. Keep a visible distinction between evidence, inference, speculation, and proposed tests.

## When to use

Use for:

- research hypotheses and mechanisms
- knowledge-gap exploration
- proposed experiments or investigations
- competing causal explanations
- novel directions that need critique and ranking

Do not use for:

- simple brainstorming with no need for evidence or testing; use `ideate` or `brainstorming`
- pure adversarial critique of an existing proposal; use `redteam`
- literature review without hypothesis generation; use `literature-synthesis` or `research`
- objectively scorable code/model optimization; use `scorable-discovery`

## Workflow

### 1. Frame the research objective

Clarify or infer:

- domain and target phenomenon
- desired type of hypothesis: mechanism, intervention, model, explanation, experiment, or research direction
- constraints: time, ethics, available data/tools, acceptable risk
- success criteria: novelty, plausibility, impact, testability, feasibility
- known evidence and references supplied by the user

If the prompt lacks grounding, ask for sources or run `research` / `literature-synthesis` first.

### 2. Build a grounded context pack

Create a short context summary before generating winners:

- established facts
- uncertain or conflicting findings
- unexplained observations
- assumptions
- known negative results or failed approaches
- source links when available

For external claims, verify URLs before citing them. Prefer source-backed claims over model memory.

### 3. Generate a broad candidate pool

Produce diverse candidates before ranking. Aim for at least 8-12 for normal work, fewer only for tiny requests.

For each candidate, capture:

- one-sentence hypothesis
- proposed mechanism or rationale
- evidence it would explain
- what would make it novel or useful
- first obvious weakness

Use Pi peers when breadth matters:

```bash
mkdir -p .pi/research/scratch
~/.pi/agent/bin/agnt invoke --fanout -o .pi/research/scratch/hypotheses \
  "Generate diverse, testable hypotheses for: <objective>. Include rationale, evidence fit, novelty, and weaknesses."
```

### 4. Critique and evolve

Stress-test the pool before selecting winners:

- remove duplicates and vague restatements
- identify critical flaws, confounders, and missing evidence
- improve hypotheses that are promising but underspecified
- split compound hypotheses into testable parts
- add discriminating predictions

Use `redteam` or peer critique for high-stakes work.

### 5. Run tournament ranking

Rank candidates with explicit criteria. Recommended default weights:

| Criterion | Meaning |
|---|---|
| Evidence fit | Explains known facts and conflicts |
| Novelty | Not merely obvious or already settled |
| Testability | Can be falsified with available or plausible methods |
| Impact | Would matter if true |
| Feasibility | Can be investigated within constraints |
| Robustness | Survives obvious objections |

State if weights differ for the user's goal.

### 6. Produce testable research plans

For each top hypothesis, provide:

- hypothesis statement
- mechanism/rationale
- supporting evidence
- conflicting evidence or critical flaw
- discriminating prediction
- falsification test
- proposed experiment/investigation
- expected observations if true vs false
- confidence and uncertainty
- next action

## Output format

```markdown
## Hypothesis Tournament: <objective>

### Grounded context
- Established:
- Uncertain:
- Knowledge gaps:

### Candidate pool
| ID | Hypothesis | Rationale | Main weakness |
|---|---|---|---|

### Tournament criteria
<criteria and weights>

### Ranked hypotheses
| Rank | ID | Score/assessment | Why it advanced | Critical flaw |
|---|---|---|---|---|

### Testable plans
#### 1. <hypothesis>
- Evidence fit:
- Critical flaw:
- Discriminating prediction:
- Falsification test:
- Next experiment/investigation:
- Confidence:

### Not recommended
- <hypothesis>: <reason>
```

## Integration

- Use `literature-synthesis` first when the evidence base is scattered across papers.
- Use `council` when ranking depends on competing expert perspectives.
- Use `redteam` when top hypotheses need adversarial flaw detection.
- Use `heilmeier-catechism` for ambitious research program go/no-go decisions.

=== hypothesis scenario ===
# Scenario: Biomedical mechanism hypotheses

## Prompt
Generate research hypotheses for why Drug X appears to reduce inflammatory marker Y in Treatment Z non-responders. We have five mixed papers and no obvious mechanism. Produce useful next steps.

## Expected weak baseline
The agent lists a few plausible mechanisms, overstates certainty, does not separate novelty from plausibility, and gives generic experiments without falsification criteria.

## Expected with skill
The agent clarifies the objective, grounds hypotheses in cited/source context if available, generates diverse candidates, critiques and ranks them tournament-style, surfaces critical flaws, and proposes falsifiable experiments.

## Assertions
- Must produce multiple candidate hypotheses before choosing winners.
- Must include explicit ranking criteria.
- Must identify critical flaws or disconfirming evidence for top hypotheses.
- Must include testable/falsifiable research plans.
- Must not present hypotheses as established facts.

=== literature-synthesis skill ===
---
name: literature-synthesis
description: Use when reviewing literature, comparing papers, extracting findings into evidence tables, or producing citation-grounded research reports and artifacts.
---

# Literature Synthesis

Turn a literature search into traceable evidence, structured comparison tables, and high-fidelity artifacts such as reports, briefs, slide outlines, mind maps, or infographic copy.

## Core rule

Every cited claim must be traceable to a verified source. Do not include unverified URLs or claims that cannot be linked back to source evidence.

## When to use

Use for:

- literature reviews and evidence scans
- comparing papers, methods, datasets, or findings
- extracting variables, metrics, populations, assumptions, and limitations
- source-grounded reports or briefings
- artifact generation from a research corpus

Do not use for:

- quick factual lookup; use `research`
- hypothesis generation and tournament ranking; use `hypothesis-tournament`
- optimizing code or algorithms against metrics; use `scorable-discovery`

## Workflow

### 1. Define the review question

Capture:

- research question and scope
- intended artifact: table, report, slide outline, mind map, infographic copy, annotated bibliography
- inclusion/exclusion criteria
- desired fields to extract
- recency/domain constraints
- acceptable source types

If the user only asks for a broad topic, propose a narrower review question before doing extensive work.

### 2. Search and collect sources

Use the existing `research` skill's search/fetch conventions. For scholarly topics, search multiple angles:

- core query
- synonyms and adjacent terms
- review/meta-analysis query
- benchmark/dataset/method query if relevant
- dissenting or null-result query

Keep a source inventory:

| ID | Source | URL/DOI | Type | Why included | Status |
|---|---|---|---|---|---|

### 3. Verify URLs and source relevance

Follow `pi/agent/skills/research/references/UrlVerificationProtocol.md`.

Before citing a URL:

```bash
curl -s -o /dev/null -w "%{http_code}" -L "URL"
curl -L "URL" | head -c 4000
```

Only include a source if the fetched content exists and supports the cited point. If a source cannot be verified, omit it or mark it as `NOT_VERIFIED` and do not rely on it.

### 4. Extract structured evidence

Create an evidence table with fields appropriate to the question. Default fields:

| Field | Meaning |
|---|---|
| Source ID | Links row to source inventory |
| Research question | What the paper/source investigates |
| Method/design | Study type, model, dataset, or method |
| Population/data | Sample, domain, corpus, benchmark |
| Key findings | Results relevant to the review question |
| Metrics/effect sizes | Quantitative results when available |
| Limitations | Internal/external validity concerns |
| Evidence quote/location | Short quote, section, table, or page when available |
| Relevance | Why this source matters |

Keep extraction conservative. Mark missing fields as `not reported` rather than guessing.

### 5. Synthesize, do not merely summarize

Separate:

- findings directly supported by evidence
- patterns across sources
- conflicts and possible explanations
- limitations of the evidence base
- knowledge gaps
- implications or recommendations

Use confidence labels tied to evidence quality and agreement, not rhetorical certainty.

### 6. Generate requested artifact

Transform the synthesis into the user's requested format. Common artifacts:

- **Report:** executive summary, method, evidence table, synthesis, gaps, references
- **Slide outline:** title, key message, supporting evidence, speaker notes
- **Infographic copy:** headline, 3-5 evidence-backed points, caveats, source list
- **Mind map:** central question, branches for themes, methods, findings, gaps
- **Annotated bibliography:** source, contribution, limitations, relevance

Do not let artifact polish hide uncertainty or weak evidence.

## Output format

```markdown
## Literature Synthesis: <question>

### Scope and inclusion criteria
- Included:
- Excluded:

### Source inventory
| ID | Source | URL/DOI | Type | Why included |
|---|---|---|---|---|

### Evidence table
| Source | Method/data | Key finding | Metric/evidence | Limitations |
|---|---|---|---|---|

### Synthesis
- Strongest supported findings:
- Mixed or conflicting findings:
- Knowledge gaps:
- Practical implications:

### Artifact: <type>
<report/slide outline/infographic/mind map/etc.>

### Confidence
<High/Medium/Low with rationale>
```

## Integration

- Use `research` for the search backend and URL verification discipline.
- Use `hypothesis-tournament` after synthesis to generate testable research directions.
- Use `writing-clearly-and-concisely` when polishing reports or artifact copy.

=== literature scenario ===
# Scenario: Evidence table literature review

## Prompt
Review the literature on whether remote work improves software team productivity. I need a concise report and a table comparing the most relevant studies.

## Expected weak baseline
The agent gives a generic essay, cites unverified or vague sources, mixes claims and interpretation, and omits a structured comparison table.

## Expected with skill
The agent defines inclusion criteria, verifies sources, extracts comparable fields into an evidence table, links claims to source evidence, separates findings from interpretation, and produces a concise artifact.

## Assertions
- Must include source selection/inclusion criteria.
- Must include a comparison/evidence table.
- Must verify URLs before citing them.
- Must distinguish evidence, synthesis, and uncertainty.
- Must not include unsupported claims or unverifiable citations.

=== scorable-discovery skill ===
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

=== scorable scenario ===
# Scenario: Algorithm optimization with scorer

## Prompt
Optimize this text chunking algorithm for retrieval quality and latency. We can run `python eval_chunker.py --candidate PATH` to return MRR, recall@10, p95 latency, and cost. Find a better implementation.

## Expected weak baseline
The agent edits heuristically based on intuition, runs few or no candidates, lacks a baseline score, and cannot explain why the chosen change is better.

## Expected with skill
The agent defines the scorable task, records baseline metrics, proposes bounded candidate families, runs candidates through the evaluator, maintains a leaderboard, inspects tradeoffs, and only recommends reproducible winners.

## Assertions
- Must establish baseline score before optimization claims.
- Must define objective metric/tradeoff policy.
- Must run or specify repeatable evaluator commands.
- Must track candidates and results in a leaderboard/run log.
- Must not claim improvement without fresh scoring evidence.
