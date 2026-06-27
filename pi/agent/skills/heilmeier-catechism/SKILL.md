---
name: heilmeier-catechism
description: >
  Evaluate ambitious research or innovation initiatives using the Heilmeier
  Catechism. Use when: research planning, initiative evaluation, feasibility
  study, state-of-the-art analysis, technology gap analysis, moonshot
  evaluation, go/no-go assessment, or "is this idea worth pursuing?"
---

# Heilmeier Catechism Research Initiative Skill

George H. Heilmeier, former DARPA director and inventor of the liquid crystal display, developed a set of questions that every proposed research program must answer before receiving funding. These questions — the Heilmeier Catechism — cut through hype, force clarity, and expose whether an idea has substance or is just enthusiasm dressed up as a plan.

This skill extends the catechism with the **H1 to H2 to Enablers pipeline**: a structured progression from articulating the aspiration (H1), to rigorously mapping the current state of the art and its limits (H2), to identifying the specific capabilities that could bridge the gap (Enablers). The pipeline transforms the catechism from a static checklist into a research-driven evaluation workflow.

**Use this skill to answer:** Is this ambitious idea worth pursuing, and if so, what would it actually take?

## Design Basis

| Principle | Rationale |
|-----------|-----------|
| Jargon-free articulation first | Heilmeier's core insight: if you cannot explain what you are trying to do in plain language, you probably do not understand it yourself. Jargon hides fuzzy thinking. |
| H1 to H2 to Enablers pipeline | The gap between aspiration and reality is where all the work lives. Structuring the analysis around this gap forces honest assessment of what must change and whether you can change it. |
| Tiered analysis | Not every initiative needs Monte Carlo simulation. Start with structured reasoning (markdown tables, diagrams), escalate to computational tools (Python, sensitivity analysis) when warranted, and point to heavy-duty tools for beyond-session work. |
| Iterative refinement | This is a thinking tool, not a form to fill out. Each phase may reveal information that changes earlier phases. Loop back freely. |
| Research-grounded | Every claim about the state of the art must cite actual sources. No "it is generally believed" or "experts agree" without naming the experts and the evidence. |

## The Heilmeier Questions

The canonical eight Heilmeier Catechism questions as used at DARPA:

1. **What are you trying to do?** Articulate your objectives using absolutely no jargon.
2. **How is it done today, and what are the limits of current practice?**
3. **What is new in your approach and why do you think it will be successful?**
4. **Who cares? If you are successful, what difference will it make?**
5. **What are the risks?**
6. **How much will it cost?**
7. **How long will it take?**
8. **What are the mid-term and final "exams" to check for success?**

ARPA-H extends the catechism with two additional questions addressing broader impact (Q9-Q10):

9. **How will you ensure equitable access and benefit?**
10. **What are the risks of misperception or misuse?**

See `references/arpa-h-hidden-questions.md` for diagnostic sub-questions that probe deeper into each of the ten questions.

## The H1 to H2 to Enablers Pipeline

### H1: The Aspiration

H1 is the answer to Question 1 — stated with zero jargon, concrete enough to evaluate quantitatively. H1 is not a vision statement. It is a falsifiable claim about what you intend to achieve.

**Good H1:** "Lower the cost of putting a satellite into low Earth orbit by 100x, from $10,000/kg to $100/kg."

**Bad H1:** "Revolutionize space access through next-generation launch paradigms."

The good H1 tells you exactly what success looks like. The bad H1 tells you nothing — it could mean anything, so it means nothing.

### H2: The Reality

H2 is the answer to Question 2 — a rigorous, sourced assessment of how the problem is addressed today, what performance levels exist, and why those levels cannot easily be exceeded. H2 is where most of the research effort lives.

**H2 for the satellite example:** "Current launch costs range from $2,700/kg (SpaceX Falcon 9, partially reusable) to $54,500/kg (ULA Delta IV Heavy). The cost floor is driven by propellant mass fraction (the Tsiolkovsky rocket equation sets a hard physics constraint), manufacturing costs of engines and airframes, launch infrastructure, and regulatory compliance. Reusability has reduced costs by roughly 4x over expendable vehicles, but further reductions face diminishing returns without fundamental changes to propulsion or manufacturing."

H2 must include: current approaches with metrics, the structure of limits (physical, engineering, economic, institutional, knowledge), and the trajectory of improvement.

### Enablers: The Bridge

Enablers are the specific capabilities, technologies, discoveries, or shifts that could close the gap between H1 and H2. They answer: "What would have to become true for H1 to be achievable?"

**Enablers for the satellite example:**
- Full and rapid reusability (both stages) — reduces cost per flight by amortizing hardware over hundreds of flights
- Methane-oxygen propulsion with on-site propellant production — reduces propellant logistics cost
- Additive manufacturing of engine components — reduces manufacturing cost and lead time by 10x
- Starship-class payload capacity (100+ tons) — reduces cost/kg through economies of scale
- Autonomous flight termination systems — reduces range safety costs

Each enabler has a maturity level, a contribution to closing the gap, dependencies, and risks. The enabler analysis is where the catechism becomes actionable.

## Workflow

### Phase 1: Capture H1

The goal of Phase 1 is a clear, jargon-free, quantitatively evaluable statement of what the initiative aims to achieve.

Start by asking the user to describe what they are trying to do in plain language. Push back on jargon, vagueness, and scope creep. The statement must meet all of the following validation criteria:

- **Jargon-free:** One-sentence problem statement that anyone can understand
- **Deliverable-focused:** One-sentence description of the concrete output or outcome
- **Family test:** Passes the "explain it to a family member" test — no insider knowledge required
- **What/how separation:** Describes *what* will be achieved, not *how* (that is Q3)
- **What/impact separation:** Describes the objective, not the downstream impact (that is Q4)
- **Unmet need:** Addresses a clear gap, not a solution looking for a problem
- **Concrete deliverable:** Describes something that could be demonstrated or measured
- **Big-picture scope:** Covers the whole initiative, not a component or sub-task
- **Quantitatively evaluable:** Specific enough that you could design an experiment or metric to test success
- **Ambitious enough:** The status quo is not close to achieving this — otherwise, why bother?

Once the user provides an H1 candidate, restate it back to them in your own words and ask for confirmation. Iterate until H1 is locked.

### Phase 2: Research H2

Phase 2 is the most research-intensive part of the workflow. The goal is a comprehensive, sourced picture of the current state of the art and its limits.

Read `references/research-methodology.md` for the full structured methodology. Use web search aggressively throughout this phase — claims about the state of the art must be grounded in actual sources.

**Steps:**

1. **Landscape scan.** Survey the field across multiple source types: academic papers and preprints, industry reports and white papers, patent filings and grants, active research programs (government and private), and commercial products or services. Cast a wide net before narrowing.

2. **Quantify the baseline.** For each major approach, establish current performance metrics, the historical rate of improvement (is it accelerating, linear, or plateauing?), and known theoretical limits. Use numbers, not adjectives.

3. **Map the limit structure.** Categorize the barriers that prevent the current state of the art from reaching H1:
   - *Physical/mathematical limits* — laws of nature, information-theoretic bounds, thermodynamic constraints
   - *Engineering limits* — materials, manufacturing precision, integration complexity
   - *Economic limits* — cost structures, market dynamics, incentive misalignment
   - *Institutional limits* — regulations, standards bodies, adoption inertia, workforce skills
   - *Knowledge limits* — fundamental questions that remain unanswered

4. **Synthesize into an H2 brief.** Produce a structured summary containing: current approaches with key metrics, the limit taxonomy, the improvement trajectory, and the 5-10 most important sources with one-line summaries.

Present H2 to the user and iterate. The user likely has domain knowledge that can correct or extend the analysis. If the multi-agent-toolkit research skill is available, recommend using it for parallel source gathering across sub-topics.

### Phase 3: Identify Enablers

Phase 3 maps the gap between H1 and H2 and identifies what could close it.

Read `references/assessment-frameworks.md` for TRL (Technology Readiness Level), AD2, and other maturity frameworks used to evaluate enabler readiness.

**Steps:**

1. **Gap analysis.** Quantify the gap between H1 and H2 in concrete terms (e.g., "100x cost reduction needed, current trajectory delivers 2x per decade"). Identify which limits from the H2 taxonomy are binding — the ones that, if removed, would unlock the most progress.

2. **Enabler brainstorm.** Generate candidate enablers from multiple sources:
   - *Cross-domain transfers* — technologies or methods proven in other fields that could apply here
   - *Emerging research* — early-stage work that addresses a binding constraint directly
   - *Novel combinations* — existing capabilities that have not been combined in this way before
   - *Paradigm shifts* — fundamentally different approaches that sidestep current limits entirely

3. **Enabler evaluation.** For each candidate, assess:
   - *TRL* — current technology readiness level (1-9)
   - *AD2 or equivalent maturity* — if applicable, assess along additional readiness dimensions
   - *Dependency chain* — what else must be true for this enabler to work
   - *Time horizon* — realistic estimate of years to the needed maturity level
   - *Risk profile* — what could prevent this enabler from materializing

4. **Enabler ranking.** Classify each enabler:
   - **Critical** — without this enabler, H1 is impossible regardless of other progress
   - **Accelerator** — makes H1 faster, cheaper, or more likely, but is not strictly required
   - **Wild Card** — low probability of materializing, but transformative if it does

### Phase 4: Complete the Catechism

With H1, H2, and Enablers established, work through the remaining catechism questions.

Read `references/risk-cost-schedule.md` for risk assessment methods, cost estimation approaches, and stage-gate frameworks. Read `references/arpa-h-hidden-questions.md` for diagnostic sub-questions that probe each question more deeply.

**Q3: What is new in your approach?**
Synthesize the enabler analysis into a coherent narrative. What is the creative thesis — the specific combination of enablers, timing, or insight that makes this initiative different from prior attempts? Why now, and why you?

**Q4: Who cares?**
Identify all stakeholders and beneficiaries. Quantify the impact for each group. Consider direct beneficiaries (who gets the product or capability), indirect beneficiaries (who benefits from second-order effects), funders and partners (who would invest and why), and adversely affected parties (who loses if this succeeds).

**Q5: What are the risks?**
Categorize risks using the taxonomy from `references/risk-cost-schedule.md`:
- *Technical risks* — the enabler does not work, the integration fails, the physics does not cooperate
- *Execution risks* — team capability gaps, coordination failures, resource constraints
- *Market/adoption risks* — nobody wants it, regulatory barriers, timing mismatch
- *Ethical/societal risks* — unintended consequences, equity concerns, dual-use potential

For each risk, assess likelihood and impact, and propose a specific mitigation strategy. Do not list risks without mitigations.

**Q6: How much will it cost?**
Produce a phased cost estimate with explicit assumptions. Break into exploration (proving feasibility), validation (demonstrating at reduced scale), development (building the full system), and deployment (reaching users or production). State what is and is not included. Flag the assumptions that most affect the total.

**Q7: How long will it take?**
Produce a phased timeline with milestones and critical path dependencies. Identify which enablers are on the critical path and which have schedule float. Be honest about uncertainty — give ranges, not point estimates.

**Q8: What are the exams?**
Define measurable go/no-go criteria for each phase. Criteria must be quantitative, not qualitative. "Demonstrate 10x cost reduction in a controlled test" is an exam. "Show promising results" is not. Each exam should have a clear pass/fail threshold and a timeline.

### Phase 5: Stress Testing

Phase 5 subjects the completed catechism to structured analysis to find weaknesses before committing resources.

Read `references/analysis-patterns.md` for the full set of ten analysis patterns with tiered implementation guidance.

At minimum, always run these two analyses:
- **Gap waterfall** (Pattern 10) — visualize how each enabler contributes to closing the H1-H2 gap, revealing whether the enablers actually add up to enough
- **Go/no-go decision matrix** (Pattern 9) — structured evaluation of whether the initiative meets threshold criteria for proceeding

Select additional analyses based on what the initiative most needs. The three tiers of implementation:

1. **Structured reasoning** (always available) — markdown tables, mermaid diagrams, qualitative matrices. Use these for every analysis as a baseline.

2. **Computational** (if environment supports Python) — sensitivity analysis with SALib, multi-criteria decision analysis with pyDecision, interactive visualizations with Plotly. Use these when quantitative rigor matters and the data supports it.

3. **Heavy-duty pointers** (for beyond-session work) — tools like OpenMDAO (multidisciplinary optimization), VOSviewer (bibliometric mapping), or domain-specific simulation frameworks. Point the user to these with specific guidance on how to set them up and what questions to ask.

For every analysis performed:
- State the assumptions explicitly
- Produce a one-line takeaway summarizing the finding
- Note how the finding affects the overall recommendation

### Phase 6: Initiative Brief

Compile all findings into a single document using the `templates/initiative-brief.md` template.

The brief must be:
- **Understandable by a non-specialist** — someone outside the field should grasp the core proposition
- **Quantitative** — numbers, not adjectives, for every claim that can be measured
- **Honest about risks** — do not bury bad news; surface it prominently with mitigations
- **Actionable** — end with a clear recommendation (Go, No-Go, or Conditional Go) and specific next steps

Name the output file: `YYYY-MM-DD-{slug}-initiative-brief.md`

Save to the project's plans or docs directory, following whatever convention the project uses.

## Quick-Start Modes

| Entry Point | Action |
|---|---|
| "I have an idea..." | Start at Phase 1 (Capture H1). Get the aspiration clear before researching. |
| "What's the state of the art in X?" | Start at Phase 2 (Research H2), then circle back to ask about H1. |
| "Help me evaluate this research direction" | Assess where the user is in the pipeline. Fill in whichever of H1, H2, or Enablers is weakest. |
| "Is X feasible?" | Do a quick H1/H2 framing, then jump to Phase 5 stress testing for a rapid feasibility answer. |

## Interaction Style

- **Ask before assuming.** The user likely knows the domain better than you do. Use their expertise; do not overwrite it with generic knowledge.
- **Quantify relentlessly.** "Significant improvement" is not acceptable. Push for numbers: how much, by when, compared to what baseline.
- **Be honest about uncertainty.** If the data does not support a conclusion, say so. "I could not find evidence for X" is more useful than a confident guess.
- **Iterate.** A single pass through the catechism is a draft. Offer to refine any section where the user has corrections, additional data, or pushback.
- **Scale to context.** A quick feasibility check does not need a 20-page brief. Match the depth of analysis to the stakes and the user's needs.

## Skill Interaction

- **Receives from:** ideate (user picks an idea to evaluate in depth), first-principles (user has deconstructed a problem and wants to evaluate a radical approach), or direct entry from the user.
- **Outputs to:** brainstorming or design skills (if the recommendation is Go and the user wants to move into implementation planning and scope definition).
- Reference other skills by name, not file path.

## Files in this Skill

| File | Purpose | When to Read |
|---|---|---|
| `references/arpa-h-hidden-questions.md` | Vendorized ARPA-H diagnostic questions for all 10 HQs | Phase 4, or any phase needing deeper question guidance |
| `references/research-methodology.md` | Structured SOTA survey methods | Phase 2 setup |
| `references/assessment-frameworks.md` | TRL, AD2, MRL, SRL maturity frameworks | Phase 3 enabler evaluation |
| `references/risk-cost-schedule.md` | Risk assessment, cost estimation, stage-gates | Phase 4 (Q5-Q8) |
| `references/analysis-patterns.md` | 10 stress-testing patterns with tiered implementation | Phase 5 analysis selection |
| `templates/initiative-brief.md` | Output template for Phase 6 | Phase 6 deliverable |
