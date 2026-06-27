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
