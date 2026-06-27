# Project Documentation Standard

## Document Structure

Every project using dev-workflow-toolkit maintains these tracked documents:

| Document | Purpose | When Updated |
|----------|---------|-------------|
| `README.md` | Project overview, setup, usage | Public interface or getting-started changes |
| `docs/ARCHITECTURE.md` | Architectural decisions, system structure, trade-offs | Structural decisions made or revised |
| `docs/DESIGN.md` | Design rationale, patterns, conventions | Design patterns or conventions change |
| `docs/*.md` | Topic-specific docs as needed | As topics emerge |
| `*/SPEC.md` | Subsystem contracts per VSA | Subsystem invariants change |

## Three Tiers of Documentation

1. **Ephemeral** — plans directory (default `.pi/plans/`, resolved with `~/.pi/agent/bin/agnt plans-dir`) — gitignored working material for PRs
2. **Tracked project docs** — `README.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/*.md`
3. **Tracked subsystem specs** — `SPEC.md` files per VSA (machine-readable contracts)

Work flows upward: ephemeral plans produce decisions that graduate into
tracked docs and specs.

## Living Documents, Not Append-Only Logs

Decisions are woven into the relevant document section. When a decision is
superseded, the old rationale is updated in-place — git history preserves
the record. This keeps documentation curated and readable.

**Do not** accumulate numbered ADR files (`0001-*.md`, `0002-*.md`). Instead,
organize by topic within `ARCHITECTURE.md` and `DESIGN.md`.

## ADR Rigor Within Living Documents

Each decision section captures:

- **Context** — what problem or need motivated this decision
- **Considered options** — alternatives evaluated with trade-offs
- **Decision** — what was chosen and why
- **Consequences** — what becomes easier or harder

Use the Alexandrian prologue for quick scanning:

> In the context of [X], facing [Y], we decided [Z] to achieve [W],
> accepting [Q].

## What Goes Where

### ARCHITECTURE.md
- System structure and component relationships
- Technology choices (languages, frameworks, infrastructure)
- Integration patterns and data flow
- Subsystem boundary rationale
- Deployment and scaling decisions

### DESIGN.md
- Design patterns and conventions
- API design rationale
- Error handling philosophy
- Naming conventions
- Code organization principles

### SPEC.md (per VSA)
- Subsystem invariants (INV-N)
- Failure modes (FAIL-N)
- Public interface contracts
- Dependencies

When a SPEC.md grows beyond recommended length, decompose the subsystem
further down the VSA tree. Each child subsystem gets its own SPEC.md.
The parent SPEC.md becomes leaner by delegating detail to children.

## When Documentation Updates Are Required

**Must update tracked docs when:**
- New architectural decisions (→ ARCHITECTURE.md)
- New design patterns or conventions (→ DESIGN.md)
- Modified subsystem behavior (→ relevant SPEC.md)
- SPEC.md exceeds recommended length (→ decompose subsystem)
- Public interface changes (→ README.md)

**No update needed for:**
- Bug fixes that don't change architecture or design
- Pure refactors that don't alter behavior or contracts
- Dependency bumps with no design impact

## Workflow Integration

- **Brainstorming** drafts documentation updates as part of the design
- **Implementation** may surface additional decisions worth documenting
- **Finishing** validates that tracked docs reflect the completed work (hard gate)
