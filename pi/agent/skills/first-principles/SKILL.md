---
name: first-principles
description: Use when conventional solutions feel wrong, costs seem fixed, you hear "that's how it's done," or need breakthrough rather than incremental improvement
---

# First Principles Analysis

## Overview

Break problems down to fundamental truths, question every assumption, rebuild solutions unconstrained by convention.

**Core principle:** Most constraints are conventions masquerading as requirements. Find the real constraints.

## When to Use

- Existing solutions feel like cargo cult or "we've always done it this way"
- You hear "that's impossible" or "too expensive"
- Industry conventions don't make logical sense
- Need breakthrough rather than incremental improvement
- Something feels like inherited constraint vs actual constraint

**Don't use when:**
- Problem is well-defined with clear solution path
- Incremental improvement is appropriate
- Time pressure requires proven patterns

## The Six Phases

Work through each phase with natural dialogue. Ask one question at a time, follow interesting threads.

### Phase 1: Define the Problem

Most failed analyses come from solving the wrong problem.

- What's the core problem in your own words?
- What would success look like concretely?
- Why does this problem exist now?

**Stay here until the problem is crystal clear.**

### Phase 2: Surface Assumptions

List everything we're assuming - especially the "obvious" stuff nobody questions.

- What do we assume to be true?
- What's "just how it's done" in this space?
- What would someone with zero context find strange?

### Phase 3: Question Each Assumption

The core of first principles. For each assumption:

- Is this actually true? What's the evidence?
- Why do we believe this? Where did it come from?
- What if the opposite were true?
- Is this physics/logic, or just convention?

**Flag each as:** Fundamental (keep) or Convention (question further)

```
Assumption → Evidence exists? → Physics/logic constraint?
                 ↓ no              ↓ no
            Convention         Convention
                 ↓ yes             ↓ yes
            Verify it          Fundamental
```

### Phase 4: Identify Fundamentals

Take stock of what remains after questioning.

- What constraints are actually real?
- What requirements are truly non-negotiable?
- What's left when we strip away conventions?

**Don't proceed until there's agreement on the foundation.**

### Phase 5: Rebuild From Scratch

Forget how it's currently done. Using ONLY the fundamentals:

- If starting fresh today, what would we build?
- How do completely different domains solve similar problems?
- What becomes possible now that we've dropped [convention]?

Propose 2-3 radically different approaches with trade-offs.

### Phase 6: Validate

Stress-test the new approach before committing.

- Does this solve the core problem from Phase 1?
- What new assumptions have we introduced?
- What could go wrong?
- Is this actually implementable?

**Loop back if something doesn't hold up.**

## Quick Reference

| Phase | Key Question | Output |
|-------|--------------|--------|
| 1. Define | What are we actually solving? | Clear problem statement |
| 2. Surface | What do we assume? | List of assumptions |
| 3. Question | Is this real or convention? | Flagged assumptions |
| 4. Identify | What's truly non-negotiable? | Fundamentals only |
| 5. Rebuild | What's possible from scratch? | 2-3 new approaches |
| 6. Validate | Does this actually work? | Validated solution |

## Socratic Toolkit

| Need to... | Ask... |
|------------|--------|
| Clarify | "What do you mean by...?" / "Can you give an example?" |
| Challenge | "What if that weren't true?" / "Who says?" |
| Probe evidence | "How do we know?" / "Are there counterexamples?" |
| Shift perspective | "How would an outsider see this?" |
| Test consequences | "What happens if...?" / "What could go wrong?" |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skipping Phase 1 | Unclear problem = wrong solution. Define first. |
| Accepting "obvious" assumptions | The obvious ones are most dangerous. Question them hardest. |
| Stopping at Phase 3 | Questioning isn't enough. Must rebuild (Phase 5). |
| Keeping conventions "just in case" | If it's not fundamental, remove it completely. |
| Rebuilding with old mental models | Fresh perspective required. Forget "how it's done." |

## After the Analysis

**Document it:**
- Write to `docs/plans/YYYY-MM-DD-<topic>-first-principles.md`
- Capture: problem, assumptions challenged, fundamentals, new approach
- Note: `docs/plans/` may or may not be git-tracked depending on the project — don't assume either way

**If implementing:**
- Use a design/brainstorming skill to refine the chosen approach
- Watch for old assumptions creeping back during implementation

## Key Principles

- **Question everything** - Especially the "obvious"
- **One question at a time** - Depth over breadth
- **Follow threads** - If something's interesting, explore it
- **Seek fundamentals** - Physics, logic, true requirements
- **Ignore convention** - "How it's done" isn't a reason
- **Validate rigorously** - New ideas need scrutiny too
