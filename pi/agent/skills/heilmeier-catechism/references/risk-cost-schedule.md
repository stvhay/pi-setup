# Risk, Cost, and Schedule Assessment for Research Initiatives

> Agent reference for Heilmeier Catechism Phase 4 (Complete the Catechism, Q5-Q8).
> Read this when assessing risks, estimating costs, planning timelines, and
> defining go/no-go criteria.

## Research Program Risk Assessment

Risk assessment for research programs differs fundamentally from systems
engineering risk management. Research risks involve unknowns about whether
something *can* work, not just whether a known design will perform to spec.

### TRL-Risk Matrix Integration (Mankins, 2009)

Maps technology immaturity directly to programmatic risk. The core insight:
risk does not decrease linearly with TRL advancement. The highest-risk
transitions are TRL 3-to-4 (lab to breadboard) and TRL 5-to-6 (component to
system in relevant environment).

**Risk scoring by TRL gap:**

| Current TRL | Target TRL | Risk Level | Rationale |
|---|---|---|---|
| 1-2 | 4+ | Very High | Scientific feasibility unproven |
| 3 | 5-6 | High | Lab-to-relevant-environment transition |
| 4-5 | 7+ | Medium | Engineering challenges, generally understood |
| 6+ | 8-9 | Low-Medium | Qualification and operational proving |

> Source: Mankins, J.C. (2009). "Technology readiness and risk assessments:
> A new approach." *Acta Astronautica*, 65(9-10), 1208-1215.

### Risk Categories

Five categories of risk must be assessed independently. An initiative may be
technically sound but face fatal programmatic or transition risk.

1. **Technical/scientific risk.** Can the technology work at all? Are the
   underlying physics/principles sound? Key indicators: conflicting theoretical
   predictions, failed prior attempts, reliance on unproven phenomena.

2. **Programmatic/management risk.** Can the effort be executed? Includes:
   team capability, organizational support, resource availability, stakeholder
   alignment, and institutional barriers.

3. **Transition risk.** Can results move from research to application? The
   "valley of death" between demonstration and deployment. Indicators: no
   identified transition partner, misaligned incentives, missing
   manufacturing capability.

4. **Tangential risk.** External factors beyond the initiative's control:
   regulatory changes, market shifts, competing technologies reaching market
   first, supply chain disruptions, geopolitical factors.

5. **Reputational risk.** Potential for the initiative to damage the
   organization's credibility if it fails publicly, consumes excessive
   resources, or produces harmful outcomes.

### RAND Normalized Risk Scoring

Normalizes unlike risk categories into comparable scores, enabling portfolio-
level risk assessment across heterogeneous initiatives.

**Method:**
1. Score each risk category on a 1-5 scale (likelihood x consequence matrix)
2. Weight categories by relevance to the specific initiative type
3. Compute weighted composite score
4. Compare across initiatives or program elements using the same weighting

> Source: RAND Corporation RR-1537, "Risk Management for Research and
> Development Programs."

### DARPA's Approach to Risk

DARPA explicitly embraces high technical risk. The methodology:

- **Structure programs to test critical assumptions early.** Front-load the
  riskiest experiments in Phase 1 rather than building toward them.
- **Multiple technical approaches.** Fund 3-4 teams pursuing different paths;
  down-select at phase gates based on demonstrated results.
- **Fail fast, fail cheap.** Design experiments to be decisive. An early "no"
  saves years and millions.
- **Program managers as risk owners.** Single accountable individual with
  authority to restructure, redirect, or terminate.
- **Risk ≠ recklessness.** High technical risk is accepted; high programmatic
  risk (poor management, unclear goals) is not.

## Research Cost Estimation Methods

### Analogous Estimation

Uses costs from similar past programs, adjusted for differences in scope,
complexity, and technical challenge.

- **When to use:** Early-stage initiatives (pre-Phase A) where detailed
  requirements do not yet exist.
- **Data requirements:** Historical cost data from 3+ comparable programs.
- **Accuracy range:** -30% to +50% (rough order of magnitude).
- **Limitations:** Highly sensitive to the choice of analogue. "Similar"
  programs may differ in critical ways that are not obvious. Document the
  analogy rationale and adjustment factors explicitly.

### Parametric Estimation

Uses Cost Estimating Relationships (CERs) that relate cost to measurable
technical or programmatic parameters (e.g., weight, lines of code, power,
number of test articles).

- **When to use:** When CERs exist for the technology domain and key
  parameters can be estimated.
- **Data requirements:** Calibrated CERs and parameter estimates with
  uncertainty ranges.
- **Tools:** SEER (Galorath), PRICE (True Planning), NAFCOM (NASA),
  COCOMO (software).
- **Accuracy range:** -20% to +30% with well-calibrated CERs.
- **Limitations:** CERs derived from historical data may not apply to
  genuinely novel technologies. Extrapolation beyond the calibration range
  is unreliable.

> Source: NASA Cost Estimating Handbook (CEH), Version 4.0.

### Process-Based (Activity-Based) Estimation

Bridges parametric and bottom-up approaches. Decomposes the initiative into
activities, estimates effort per activity, and applies labor and material
rates.

- **When to use:** When the work breakdown structure is defined but detailed
  bottom-up data is unavailable.
- **Data requirements:** Activity list, effort estimates (person-months),
  labor rates, material/equipment costs.
- **Accuracy range:** -15% to +25% with experienced estimators.
- **Limitations:** Dependent on completeness of the activity decomposition.
  Missing activities are the primary source of underestimation.

## Joint Cost and Schedule Confidence Level (JCL)

NASA's integrated method for determining the probability of completing a
project within a given cost and schedule. Required for all NASA programs
with lifecycle cost > $250M.

**Method:**

1. **Build the cost model.** Decompose costs into elements at WBS Level 3+.
   For each element, specify a probability distribution (typically triangular
   or beta-PERT) with minimum, most likely, and maximum values.

2. **Build the schedule network.** Define tasks, durations (with uncertainty
   distributions), dependencies, and resource assignments. Identify the
   critical path.

3. **Compile the risk register.** Each discrete risk event has: probability
   of occurrence, cost impact distribution, schedule impact distribution, and
   correlation with other risks.

4. **Run Monte Carlo simulation.** Simultaneously sample from all three
   models (cost, schedule, risk) for N iterations (typically 10,000+).
   Capture the joint probability distribution.

5. **Read the output.** The JCL chart shows probability contours across
   cost and schedule axes. NASA policy requires projects to budget at the
   70th percentile JCL.

**Structured reasoning tier (when computational tools are unavailable):**

List cost elements with min/likely/max estimates in a table:

| Element | Min | Likely | Max | Distribution |
|---|---|---|---|---|
| Example: Lab Equipment | $200K | $350K | $600K | Triangular |

List schedule tasks with dependencies and duration ranges:

| Task | Predecessor | Min (mo) | Likely (mo) | Max (mo) |
|---|---|---|---|---|
| Example: Prototype Build | Design Review | 4 | 6 | 10 |

List discrete risk events:

| Risk | P(occur) | Cost Impact | Schedule Impact |
|---|---|---|---|
| Example: Key personnel departure | 15% | +$200K | +3 months |

Compute expected values and use the three-point estimate formula:
E = (min + 4*likely + max) / 6 for each element. Sum for total. This
provides a rough central estimate without simulation.

> Cross-reference: For full Monte Carlo simulation, see
> analysis-patterns.md Pattern 3.

## Stage-Gate Decision Frameworks

### Cooper Stage-Gate

The standard industry framework for innovation project management.

**Stages:**
1. **Discovery** — Ideation, opportunity identification
2. **Scoping** — Quick assessment of technical merit and market prospects
3. **Feasibility** — Detailed investigation; business case construction
4. **Development** — Design and development of the product/technology
5. **Validation** — Testing, trial production, market testing
6. **Launch** — Full commercialization or deployment

**Five gate outcomes:**
- **Go** — Approved; proceed to next stage with specified resources
- **Kill** — Terminated; initiative does not meet criteria
- **Hold** — Paused; criteria met but resources unavailable or timing wrong
- **Recycle** — Sent back to previous stage for rework
- **Conditional Go** — Approved contingent on specific actions within a
  defined timeframe

### DoD Milestone Decision Points

- **Milestone A (TMRR entry):** Approve entry into Technology Maturation and
  Risk Reduction. Critical technologies identified, TMP approved, preliminary
  design concepts evaluated.
- **Milestone B (Engineering entry):** Approve entry into Engineering and
  Manufacturing Development. Critical technologies at TRL 6+, preliminary
  design review complete, cost estimate validated.
- **Milestone C (Production entry):** Approve entry into Production and
  Deployment. Critical design review complete, manufacturing processes proven,
  operational test plan approved.

### NASA Key Decision Points (KDPs)

- **KDP-A:** Approve formulation (concept study)
- **KDP-B:** Approve preliminary design and technology completion
- **KDP-C:** Approve final design and fabrication
- **KDP-D:** Approve system integration, test, and launch
- **KDP-E:** Approve operations and sustainment

Each KDP requires: updated cost estimate, schedule assessment, risk posture
review, and technology readiness evidence.

### DARPA Phase Gates

- **Phase 1 (Feasibility):** Typically 12-18 months. Prove the core technical
  concept is viable. Deliverable: demonstrated proof of concept with
  quantitative performance data. Go/no-go: does the data support advancement?

- **Phase 2 (Prototype):** Typically 18-24 months. Build and test a prototype
  in relevant conditions. Deliverable: prototype demonstration with metrics
  against program targets. Go/no-go: does performance meet thresholds?

- **Phase 3 (Transition):** Variable duration. Transition technology to a
  user, partner, or commercial entity. Deliverable: transition agreement and
  demonstrated operational utility. Go/no-go: is there a committed
  transition path?

## Defining Kill Criteria

Kill criteria (supports INV-9 invariant) are pre-defined conditions under
which the initiative should be terminated. They must be defined *before*
the initiative begins to avoid sunk-cost bias during execution.

### Technical Kill

The initiative should be killed if a key technical assumption is proven false.

- **Structure:** "If [specific experiment/test] fails to demonstrate
  [specific metric] ≥ [threshold] by [date], the initiative is terminated."
- **Example:** "If the prototype catalyst does not achieve ≥80% conversion
  efficiency at 200°C in bench-scale testing by Q3, the approach is
  fundamentally limited and should be terminated."
- **Requirement:** The test must be *decisive* — it must be possible to
  distinguish "the approach cannot work" from "this particular implementation
  needs refinement."

### Economic Kill

Costs exceed the threshold at which the initiative's value proposition
becomes untenable.

- **Structure:** "If total projected cost exceeds [threshold], or if
  cost-per-unit exceeds [target] by more than [margin], terminate."
- **Example:** "If manufacturing cost per unit exceeds $500 (vs. target
  $200), the product cannot compete with incumbent solutions."
- **Requirement:** Cost thresholds must be derived from the value
  proposition, not arbitrary budgets.

### Timeline Kill

The critical path slips beyond the window of opportunity.

- **Structure:** "If [milestone] is not achieved by [date], the market/
  technology window will have closed, and the initiative is terminated."
- **Example:** "If prototype demonstration slips beyond 2027, competing
  approaches will have reached market, eliminating the first-mover
  advantage."
- **Requirement:** The window must be real and externally validated, not
  an internal planning convenience.

### Strategic Kill

The landscape changes in ways that make the initiative irrelevant.

- **Structure:** "If [external event] occurs, the initiative's rationale
  is invalidated."
- **Example:** "If a competing open-source solution achieves performance
  parity, the proprietary development effort cannot justify its cost."
- **Requirement:** Monitor the landscape continuously. Strategic kill
  triggers are not tested at gates — they are ongoing watch conditions.

## Cross-References

The following analysis patterns from analysis-patterns.md provide
computational methods for the assessments described above:

| Assessment Need | Analysis Pattern | Pattern # |
|---|---|---|
| Cost/schedule uncertainty quantification | Monte Carlo Feasibility Sweep | 3 |
| Identifying critical assumptions | Sensitivity / Tornado Analysis | 2 |
| Comparing approaches | Cost-Performance Pareto Frontier | 6 |
| Timeline analysis | Timeline Critical Path Analysis | 7 |
| Phase gate decisions | Go/No-Go Decision Matrix | 9 |
