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
