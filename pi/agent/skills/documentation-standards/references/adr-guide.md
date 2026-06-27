# Architecture Decision Records — Reference Guide

_Distilled from [joelparkerhenderson/architecture-decision-record](https://github.com/joelparkerhenderson/architecture-decision-record) (CC-BY-NC-SA-4.0 for original author content) and general ADR literature. ADR templates (Nygard, MADR, Alexandrian) originate from their respective authors. This summary is original text describing established concepts._

## What Is an ADR?

An Architecture Decision Record captures an important architectural choice
with its context and consequences. An Architecture Decision Log collects
all ADRs for a project.

## Templates

### Nygard (Simple)

The most widely used format. Four sections:

- **Status:** proposed | accepted | rejected | deprecated | superseded
- **Context:** The issue or problem motivating this decision
- **Decision:** The change being proposed or adopted
- **Consequences:** What becomes easier or harder as a result

### MADR (Markdown Any Decision Records)

Structured format emphasizing options analysis:

- **Context and Problem Statement:** 2-3 sentences describing the problem
- **Decision Drivers:** Factors influencing the choice
- **Considered Options:** List of alternatives
- **Decision Outcome:** Chosen option with justification
- **Consequences:** Good and bad outcomes
- **Pros and Cons of Options:** Detailed comparison per option

#### MADR Short Form

```
## Context and Problem Statement
[problem]

## Considered Options
* Option A
* Option B

## Decision Outcome
Chosen option: "Option A", because [justification].
```

### Alexandrian Pattern

Narrative-driven, emphasizing forces and pressures:

- **Prologue:** "In the context of [use case], facing [concern], we decided
  for [option] to achieve [quality], accepting [downside]."
- **Discussion:** Forces at play — technical, organizational, social
- **Solution:** How the chosen option addresses the problem
- **Consequences:** Long-term outcomes and effects

## When to Write an ADR

**Document when:**
- Future developers need to understand the "why"
- Choice significantly impacts architecture or design
- Multiple valid options existed with real trade-offs
- Long-term maintainability requires documented context

**Skip when:**
- Limited-scope, low-risk decisions
- Temporary workarounds or experiments
- Decisions already covered by existing standards
- Single-developer, self-contained choices

## Best Practices

- **One decision per section** — don't bundle multiple decisions
- **Context first** — explain organizational context and reasoning
- **Lead with "why"** — not "we must document"
- **Review monthly** — compare assumptions against outcomes
- **Immutability in logs** — if using numbered ADR files, don't alter
  existing records; append amendments with dates
- **Living documents** — if using integrated docs (like ARCHITECTURE.md),
  update in-place as decisions evolve; git history preserves the record

## Complementary Approaches

- **Fitness functions** — automated checks verifying decisions hold
- **Architecture unit tests** — tools like ArchUnit enforce rules in code
- **SPEC.md invariants** — machine-readable contracts per VSA

## File Naming (If Using Individual Files)

Present-tense imperative verb, lowercase, dashes, markdown:
`choose-database.md`, `format-timestamps.md`, `manage-passwords.md`

## Example Decision Topics

Technology: programming languages, databases, cloud platforms, frameworks.
Architecture: monorepo vs multirepo, API format, authentication strategy.
Process: CI/CD pipeline, work-from-home policy, agile methodology.
