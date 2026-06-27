# Technology Assessment Frameworks

> Agent reference for Heilmeier Catechism Phase 3 (Identify Enablers).
> Read this when assessing enabler maturity and classifying enablers.

## NASA Technology Readiness Levels (TRL)

The standard maturity scale for technology development, widely adopted beyond
NASA across DoD, ESA, and industry.

| TRL | Description | Evidence Required |
|---|---|---|
| 1 | Basic principles observed and reported | Published research identifying fundamentals |
| 2 | Technology concept and/or application formulated | Practical applications identified; papers/patents describing the concept |
| 3 | Analytical and experimental critical function and/or proof of concept | Laboratory measurements validating analytical predictions of key parameters |
| 4 | Component and/or breadboard validation in laboratory environment | Standalone component tested; low-fidelity integration with other elements |
| 5 | Component and/or breadboard validation in relevant environment | Near-production component tested in simulated or realistic environment |
| 6 | System/subsystem model or prototype demonstration in relevant environment | Representative prototype tested in relevant environment |
| 7 | System prototype demonstration in operational environment | Prototype near or at planned operational scale tested in operational environment |
| 8 | Actual system completed and qualified through test and demonstration | Final product in final configuration tested and qualified |
| 9 | Actual system proven through successful mission operations | Operational deployment with documented performance data |

**Key rules for TRL assessment:**

- **Weakest-link rollup.** A system's TRL is the lowest TRL of its critical
  components. A TRL-7 system with one TRL-3 subsystem is effectively TRL-3.

- **Evidence-based assessment.** Each TRL claim must be backed by documented
  evidence. Self-assessed TRLs without documentation are unreliable.

- **Five assessment categories:**
  1. Prior development maturity
  2. Model and/or simulation fidelity
  3. Test environment fidelity
  4. Performance verification completeness
  5. Documentation adequacy

- **Common pitfalls:** Conflating TRL with quality, skipping intermediate
  TRLs, assessing in isolation without system context, and optimistic bias
  (the most common failure mode).

> Source: NASA SP-20205003605, "NASA Technology Readiness Assessment Best
> Practices Guide" (2020).

## Advancement Degree of Difficulty (AD2)

NASA's complement to TRL. While TRL measures *where you are*, AD2 measures
*how hard it is to get to the next level*. This is critical for Heilmeier
because two enablers at the same TRL may have vastly different advancement
difficulty.

| Level | Description | Characteristics |
|---|---|---|
| AD2-I | Exists, no or little development needed | Off-the-shelf solution available; minor adaptation only |
| AD2-II | Exists, moderate development needed | Known engineering challenges; established methods apply |
| AD2-III | Requires significant development | Substantial engineering effort; some research questions remain |
| AD2-IV | Requires major development, scientific questions | Fundamental scientific questions unanswered; high uncertainty |
| AD2-V | Requires major fundamental development | Breakthrough required; no known path to solution |

**Using AD2 with TRL:**

A technology at TRL-3 with AD2-II is far less risky than one at TRL-3 with
AD2-IV. The former has known engineering steps ahead; the latter faces
unresolved scientific questions. When assessing enablers, always pair TRL
with AD2 to get a complete maturity picture.

**AD2 assessment questions:**
- Are the underlying scientific principles fully understood?
- Do engineering methods exist to advance this technology?
- Have similar technologies been successfully advanced from this TRL?
- What resources (time, funding, expertise) are required for advancement?
- Are there known showstoppers or open research questions?

## Manufacturing Readiness Level (MRL)

DoD's parallel scale for production readiness. Relevant when the initiative
involves physical systems, hardware, or any artifact that must be manufactured
at scale.

| MRL Range | Phase | Description |
|---|---|---|
| 1-3 | **Research** | Basic manufacturing concepts identified (1), feasibility established (2), proof of concept demonstrated (3) |
| 4-6 | **Prototype** | Capability to produce in laboratory (4), capability to produce prototype components in production-relevant environment (5), capability to produce prototype system in production-relevant environment (6) |
| 7-9 | **Production** | Capability to produce system in representative production environment (7), pilot line demonstrated; ready for low-rate production (8), full-rate production demonstrated; manufacturing processes proven (9) |
| 10 | **Lean** | Full-rate production with continuous process improvement and lean practices |

**Key consideration:** An enabler may have high TRL (technology works) but
low MRL (cannot be produced affordably at scale). This mismatch is a common
source of "valley of death" failures in technology transition.

> Source: DoD Manufacturing Readiness Level Deskbook, Version 2025.

## System Readiness Level (SRL)

Assesses integration maturity — how ready a system-of-systems is for
operation. Based on Integration Readiness Levels (IRL) between component
pairs.

**Integration Readiness Levels (IRL):**

| IRL | Description |
|---|---|
| 1 | Interface identified and characterized |
| 2 | Ability to influence each other's design established |
| 3 | Compatibility verified through integration testing |
| 4 | Integration in laboratory environment |
| 5 | Integration in relevant environment |
| 6 | Integration in operational environment |
| 7 | Integration verified and validated in operational environment |

**SRL Calculation:**

SRL is computed from the TRLs of individual components and the IRLs of their
pairwise connections. The formula normalizes across the system:

> SRL = f(TRL_i, IRL_ij) for all component pairs (i, j)

The key insight: individual components may each be mature (high TRL), but
their integration may be immature (low IRL), yielding a low SRL. This is the
"integration gap" and is one of the most underestimated risks in complex
initiatives.

## DoD Technology Readiness Assessment (TRA) Process

Updated February 2025. Statutory requirement under 10 USC 4252 for major
defense acquisition programs.

**Key elements:**

- **Independent TRA (ITRA).** Required at Milestone B for all ACAT I programs.
  Conducted by an independent team, not the developing organization.

- **Technology Maturation Plan (TMP).** Required when critical technologies
  are below TRL 6. Must include: target TRL, maturation activities, schedule,
  resources, risk mitigation, and exit criteria.

- **Milestone gates:**
  - Milestone A (TMRR entry): Critical technologies identified, TMP approved
  - Milestone B (Engineering entry): Critical technologies at TRL 6+
  - Milestone C (Production entry): Technologies at TRL 7+ in system context

- **Critical Technology Elements (CTEs).** Technologies that are new or novel,
  being applied in a new way, or in an area of significant technical risk.
  Each CTE requires individual TRL assessment with supporting evidence.

> Source: DoD Technology Readiness Assessment Guidebook, February 2025.

## EU Horizon Europe Criteria

The European Union's research funding framework uses three evaluation pillars:

**1. Excellence**
- Clarity and pertinence of objectives
- Soundness of methodology
- Novelty and ambition relative to state of the art
- Interdisciplinary considerations

**2. Impact**
- Credibility of pathways to impact
- Scale and significance of outcomes
- Communication, dissemination, and exploitation plans
- Key Impact Pathways (KIPs):
  - Scientific: publications, data, methods
  - Societal: policy, standards, public engagement
  - Economic: innovation, market creation, competitiveness
  - Technological: patents, prototypes, demonstrators

**3. Implementation**
- Quality and effectiveness of the work plan
- Capacity of participants and consortium
- Appropriate allocation of resources

**Relevance to Heilmeier:** The KIP framework provides a structured way to
articulate impact beyond technical metrics. When assessing enablers that
require external funding, alignment with major funding frameworks increases
the probability of resourcing.

## Applying Frameworks to Enabler Classification

Map each identified enabler to a classification using the frameworks above:

| Classification | TRL Range | AD2 Range | Characteristics |
|---|---|---|---|
| **Critical** | Any | Any | Without this enabler, H1 is impossible. Must be developed or acquired. Risk mitigation is mandatory. |
| **Accelerator** | TRL 4+ | AD2-I to AD2-III | Makes the initiative faster, cheaper, or higher-performing. Not strictly required but strongly desirable. |
| **Wild Card** | TRL 1-3 | AD2-IV to AD2-V | Low probability of timely maturation but potentially transformative if achieved. Plan without it, benefit if it arrives. |

**For each enabler, assess:**

1. **Current TRL** — With specific evidence supporting the assessment. Cite
   demonstrations, publications, or products that justify the claimed level.

2. **Target TRL** — The maturity level required for the initiative to proceed.
   This may differ from TRL 9; many initiatives only need TRL 5-6 for a
   specific component.

3. **AD2 for the gap** — How difficult is it to advance from current TRL to
   target TRL? This determines risk and timeline.

4. **Dependency chain** — Which other enablers must mature first? Identify
   serial dependencies that constrain the critical path.

5. **Time horizon** — Estimated calendar time to reach target TRL based on
   AD2, historical analogues, and available resources.

6. **MRL consideration** — If the enabler involves physical production, assess
   manufacturing readiness independently of technology readiness.

7. **Integration assessment** — IRL with other enablers. High individual TRLs
   with low inter-component IRLs is a red flag.
