# STAMP Output Formats

STAMP analysis produces control structures, hazards, UCAs, scenarios, and recommendations. This guide shows how to format outputs for different audiences.

## Audience-Specific Formats

### Executive Summary (Decision Makers)

Use when presenting to leadership who need to approve resources or policy changes.

**Template:**

```markdown
# [System/Incident] Safety Analysis Summary

## Bottom Line
[1-2 sentences: What's the risk? What should we do?]

## Key Findings
1. [Finding that affects strategic risk]
2. [Finding that requires resource allocation]
3. [Finding with regulatory/liability implications]

## Recommended Actions
| Action | Owner | Impact | Timeline |
|--------|-------|--------|----------|
| [Change] | [Role] | [Risk reduced] | [When] |

## Investment Required
[Resources, budget, organizational changes needed]

## Risk of Inaction
[What happens if we don't act]
```

**Tone:** Business impact, not methodology. Executives don't need control structure details—they need decisions.

---

### Engineering Specification (Implementation Teams)

Use when handing off to engineers who will implement safety controls.

**Template:**

```markdown
# Safety Requirements Specification

## Control Structure
[Depict diagram showing relevant controllers and processes]

## Safety Requirements

### SR-1: [Requirement Name]
- **Requirement:** [What must be true]
- **Rationale:** Addresses UCA-X (controller does/doesn't provide action when context)
- **Verification:** [How to test this is satisfied]
- **Implementation Notes:** [Technical guidance]

### SR-2: [Requirement Name]
...

## Unsafe Control Actions to Prevent

| ID | Controller | Action | Context | Hazard |
|----|------------|--------|---------|--------|
| UCA-1 | [Who] | [Does/doesn't do what] | [When] | [H-X] |

## Causal Scenarios

**UCA-1 could occur because:**
- [Feedback failure]: ...
- [Process model error]: ...
- [Control path failure]: ...

## Test Cases
| Test | Verifies | Expected Result |
|------|----------|-----------------|
| [Scenario] | SR-X | [Outcome] |
```

**Tone:** Precise, actionable, traceable. Engineers need requirements they can implement and verify.

---

### Incident Report (Compliance/Regulatory)

Use when documenting incidents for regulators, auditors, or legal review.

**Template:**

```markdown
# Incident Analysis Report

## Incident Summary
- **Date:** [When]
- **Location:** [Where]
- **Loss:** [What happened - injuries, damage, etc.]

## Analysis Methodology
This analysis uses CAST (Causal Analysis based on System Theory), a systems-theoretic methodology that identifies systemic factors rather than assigning blame to individuals.

## Control Structure at Time of Incident
[Depict diagram with @red highlighting failed paths]

## Contributing Factors

### Organizational Level
- [Factor]: [How it contributed]
- [Factor]: [How it contributed]

### Operational Level
- [Factor]: [How it contributed]

### Physical Level
- [Factor]: [How it contributed]

## Why Actions Seemed Correct at the Time
[For each controller involved, explain their mental model and available information]

## Systemic Factors
- **Communication:** [Gaps identified]
- **Safety Culture:** [Issues observed]
- **Change Management:** [Relevant changes before incident]

## Recommendations

| # | Recommendation | Addresses | Owner | Verification |
|---|----------------|-----------|-------|--------------|
| 1 | [Action] | [Factor] | [Role] | [How to confirm] |

## Corrective Action Tracking
[Space for implementation status, dates, evidence]
```

**Tone:** Thorough, evidence-based, non-blaming. Auditors want systematic methodology and traceable findings.

---

### Quick Brief (Verbal Discussion)

Use when preparing for alignment meetings or when someone asks "what did you find?"

**Template:**

```markdown
# Quick Brief: [Topic]

## In One Sentence
[The core finding or concern]

## Three Key Points
1. [Most important finding]
2. [Second finding]
3. [Third finding or recommended action]

## Surprising Insight
[Something counterintuitive or not obvious before analysis]

## Recommended Next Step
[One clear action]

## If They Push Back
- "What's the root cause?" → [Your response]
- "Who's responsible?" → [Your response]
```

**Tone:** Conversational, memorable, actionable. Verbal settings need clarity, not completeness.

---

## Format Selection Guide

| Situation | Format | Why |
|-----------|--------|-----|
| Board presentation | Executive Summary | Decisions, not details |
| Design review | Engineering Spec | Actionable requirements |
| Regulatory filing | Incident Report | Thorough, methodology-documented |
| Team standup | Quick Brief | Alignment, not analysis |
| Stakeholder with no STAMP background | Executive Summary + Quick Brief | Accessible, outcome-focused |
| Technical peer review | Engineering Spec + YAML schema | Full detail, machine-parseable |

## YAML Schema for Machine Processing

When outputs need to feed into other tools or be stored for later reference, use the YAML schemas defined in:
- stamp-stpa: `stpa_analysis` schema
- stamp-cast: `cast_analysis` schema
- stamp-stpa-sec: `stpa_sec_analysis` schema

These schemas capture full analytical detail in structured form.

## Combining Formats

Complex situations may need multiple formats:

1. **Incident requiring executive action:**
   - Incident Report (for the record)
   - Executive Summary (for decision meeting)
   - Engineering Spec (for implementation)

2. **Design review with mixed audience:**
   - Quick Brief (verbal opening)
   - Engineering Spec (technical detail)
   - Executive Summary (for leadership present)

3. **Compliance audit:**
   - Incident Report (primary artifact)
   - YAML schema (evidence of systematic analysis)
   - Corrective action tracking (closure evidence)
