# Research Methodology for State-of-the-Art Assessment

> Agent reference for Heilmeier Catechism Phase 2 (Research H2).
> Read this when conducting a structured state-of-the-art survey.

## Overview

Phase 2 requires building a grounded, comprehensive picture of the current
state of the art. Ad-hoc searching produces scattered, biased results. The
methodologies below provide systematic approaches drawn from evidence-based
research practice. Select the methodology that best fits the domain and the
depth of survey warranted by the initiative's scope.

The goal is not exhaustive literature review — it is sufficient coverage to
answer: *What has been tried? What worked? What failed? What remains open?*

## Scoping Review Methodology (Arksey & O'Malley, 2005)

The foundational framework for "mapping" a field without the strict inclusion
criteria of a full systematic review. Ideal when the research question is broad
or the field is heterogeneous.

**Six stages:**

1. **Identify the research question.** Derive directly from H1. The question
   should be broad enough to capture the full landscape but specific enough to
   exclude irrelevant domains. Use the PCC (Population, Concept, Context)
   framework rather than PICO.

2. **Identify relevant studies.** Develop a systematic search strategy across
   multiple sources. Define search terms, Boolean operators, and source
   databases. Cast a wide net — comprehensiveness over precision at this stage.

3. **Study selection.** Apply inclusion/exclusion criteria post hoc. Criteria
   should address: date range, language, relevance to H1, study type, and
   quality threshold. Two-pass screening (title/abstract, then full text) is
   standard.

4. **Charting the data.** Extract key findings into a structured table:
   author(s), year, approach, key results, metrics reported, limitations noted,
   and relevance to H1. This becomes the raw material for gap analysis.

5. **Collating, summarizing, and reporting.** Synthesize the charted data into
   themes. Identify convergent findings, contradictions, and gaps. Quantify
   where possible (e.g., "7 of 12 approaches use technique X").

6. **Consultation (optional).** Present preliminary findings to the user for
   domain-expert validation. The user may identify missed sources, correct
   misinterpretations, or highlight insider knowledge not captured in published
   work.

> Source: Arksey, H. & O'Malley, L. (2005). "Scoping studies: towards a
> methodological framework." *International Journal of Social Research
> Methodology*, 8(1), 19-32.

## Systematic Mapping Studies (Petersen et al., 2008/2015)

Builds a classification scheme for a research area and analyzes publication
frequencies to identify trends and gaps. Most relevant for technology and
computer science domains where publication volume is high.

**Steps:**

1. **Define research questions.** What topics have been studied? What methods
   are used? What venues publish this work? What trends exist over time?

2. **Conduct search.** Use automated database searches (Scopus, IEEE Xplore,
   ACM DL, Web of Science) combined with manual searches of key venues.
   Document the search string and date of execution.

3. **Screening.** Apply inclusion/exclusion criteria. Remove duplicates.
   Classify borderline cases conservatively (include if uncertain at this
   stage).

4. **Keywording using abstracts.** Read abstracts and assign keywords to build
   a classification scheme. The scheme emerges from the data rather than being
   imposed a priori. Iterate until the scheme stabilizes.

5. **Data extraction and mapping.** Extract structured data per the
   classification scheme. Produce bubble plots (x = category, y = category,
   bubble size = publication count) to visualize the landscape.

> Source: Petersen, K., Feldt, R., Mujtaba, S. & Mattsson, M. (2008).
> "Systematic Mapping Studies in Software Engineering." *Proceedings of the
> 12th International Conference on Evaluation and Assessment in Software
> Engineering.* Updated in Petersen, K. et al. (2015).

## Patent/IP Landscape Analysis (WIPO Guidelines)

Technology landscape assessment that goes beyond academic literature to capture
commercial and industrial state of the art.

**Steps:**

1. **Define scope.** Technology domain, geographic scope, date range. Align
   directly with H1's problem domain.

2. **Data scouting.** Preliminary searches across major patent offices to
   validate scope and estimate volume:
   - USPTO (US patents and applications)
   - EPO / Espacenet (European patents)
   - WIPO PATENTSCOPE (international PCT applications)
   - Google Patents (broad cross-office search)

3. **Screening.** Review titles and abstracts. Apply IPC/CPC classification
   codes to filter. Remove false positives from keyword-based searches.

4. **Technology profiling.** Classify patents by technology sub-domain,
   applicant type (corporate, academic, government, individual), filing
   trajectory (growing, stable, declining), and geographic distribution.

5. **Visualization.** Produce technology landscape maps showing clusters,
   white spaces, and filing trends. Identify key assignees and their
   portfolio strategies.

> Source: WIPO (2015). "Guidelines for Preparing Patent Landscape Reports."
> WIPO Publication No. 946(E).

## Research Gap Taxonomy (Muller-Bloch & Kranz)

Seven types of research gaps, useful for structuring the "limits of current
practice" portion of the H2 assessment.

| Gap Type | Definition | Example Signal |
|---|---|---|
| **Evidence** | Conflicting results across studies | "Study A finds X effective; Study B finds it ineffective" |
| **Knowledge** | Topic not yet studied | "No published work addresses Y in context Z" |
| **Practical-Knowledge** | Theory exists but no applied validation | "Algorithm proposed but never implemented at scale" |
| **Methodological** | Existing methods inadequate | "Current benchmarks do not capture real-world conditions" |
| **Empirical** | Insufficient data to draw conclusions | "Only 2 datasets exist, both synthetic" |
| **Theoretical** | No explanatory framework | "Phenomenon observed but not modeled" |
| **Population** | Not studied in relevant context | "Validated in English but not tested cross-linguistically" |

When documenting gaps for H2, classify each gap by type. This structures the
argument for why the initiative is needed and where exactly it advances beyond
the current state.

> Source: Muller-Bloch, C. & Kranz, J. (2015). "A Framework for Rigorously
> Identifying Research Gaps in Qualitative Literature Reviews." *Proceedings
> of the 36th International Conference on Information Systems (ICIS).*

## Reporting Standards (PRISMA-ScR)

The Preferred Reporting Items for Systematic Reviews and Meta-Analyses
extension for Scoping Reviews provides a 20-item checklist. Key items
relevant to Heilmeier H2 reporting:

| # | Item | Relevance to H2 |
|---|---|---|
| 1 | Title | Identifies the report as a state-of-the-art assessment |
| 3 | Rationale | Why this survey was needed (derived from H1) |
| 6 | Eligibility criteria | What was included/excluded and why |
| 7 | Information sources | Databases, registries, websites searched |
| 8 | Search strategy | Full search strings for reproducibility |
| 9 | Selection of sources | Screening process and criteria |
| 11 | Data charting | What data was extracted from each source |
| 14 | Synthesis of results | Thematic or quantitative summary |
| 17 | Results | Characteristics of sources, charted data, synthesis |
| 20 | Limitations | Gaps in the survey itself |

> Source: Tricco, A.C. et al. (2018). "PRISMA Extension for Scoping Reviews
> (PRISMA-ScR): Checklist and Explanation." *Annals of Internal Medicine*,
> 169(7), 467-473.

## Recommended Process for Heilmeier H2

A synthesized workflow combining the above methodologies into a practical
sequence for the agent:

1. **Frame.** Convert H1 into 2-4 research questions using PCC. Define
   inclusion/exclusion criteria (recency, domain, quality).

2. **Search (broad).** Web search for survey papers, review articles, and
   "state of the art" + domain keywords. Identify landmark papers and key
   researchers.

3. **Search (deep).** Academic databases, patent databases, industry reports,
   and government research program pages. Follow citation chains from landmark
   papers.

4. **Screen.** Apply inclusion/exclusion criteria. Prioritize by: relevance to
   H1, recency, citation impact, and methodological rigor.

5. **Extract.** For each included source, extract: approach taken, metrics
   reported, key results, stated limitations, and trajectory (improving,
   stalled, abandoned).

6. **Classify.** Apply the gap taxonomy to identify what types of gaps exist.
   Map gaps to specific aspects of H1.

7. **Synthesize.** Write the H2 brief: current best-in-class performance,
   dominant approaches, known limitations, trajectory of improvement, and
   specific gaps the initiative targets.

8. **Validate.** Present the synthesis to the user for correction and
   augmentation. The user may have insider knowledge, unpublished results, or
   context that changes the assessment.

## Source Hierarchy

Where to look, in recommended order of priority:

1. **Survey papers and systematic reviews** — Pre-synthesized overviews.
   Highest value-to-effort ratio.
2. **Conference proceedings** — Recent results in fast-moving fields (NeurIPS,
   ICML, ACL, CVPR, AAAI, ICSE, etc.).
3. **Preprints** (arXiv, bioRxiv, SSRN) — Cutting-edge but unreviewed.
   Assess with appropriate skepticism.
4. **Patent databases** — Commercial/industrial state of the art. Signals
   where investment is flowing.
5. **Industry reports** — Gartner, McKinsey, CB Insights, domain-specific
   analysts. Capture market perspective.
6. **Government research programs** — DARPA (active programs page), NSF
   (funded awards search), ARPA-E, ARPA-H, IARPA, EU Horizon Europe funded
   projects. Signals where public R&D investment is directed.
7. **Commercial products and services** — Deployed solutions represent
   validated (if sometimes proprietary) state of the art.

> **Note:** If the `multi-agent-toolkit:research` skill is available in the
> current environment, use it for parallel source gathering across multiple
> categories simultaneously. This significantly accelerates Phase 2.
