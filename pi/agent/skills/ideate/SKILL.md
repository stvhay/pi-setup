---
name: ideate
description: "Divergent exploration of fuzzy problem spaces. Use when problem is unclear, multiple large directions exist, or user wants to generate ideas without committing to a design."
---

# Ideate

Divergent exploration for fuzzy problem spaces. Generates a network of idea artifacts that can later feed into a design/brainstorming skill.

## When to Activate

**Full ideation session:**
- Problem space is fuzzy - need discovery to find its shape
- Multiple large-scope directions exist - need to sketch several before committing
- "I'm thinking about...", "What if we...", "I have some ideas about..."
- User explicitly wants to explore without designing yet

**Light mode (quick capture):**
- Single idea to capture quickly
- Brief exploration of one problem/opportunity
- For light mode: have a quick back-and-forth, capture to a single idea file, done

## Process (Full Session)

1. **Explore** - Understand the problem space:
   - What's the opportunity or pain point?
   - What's unclear or unknown?
   - What constraints exist (if any are known)?

2. **Generate** - Surface multiple directions:
   - Encourage divergent thinking - quantity over quality initially
   - Each distinct problem/opportunity becomes its own idea
   - Don't evaluate or pick winners yet

3. **Connect** - Identify relationships:
   - Which ideas inform or depend on others?
   - Which are alternatives to each other?
   - Capture links between related ideas

4. **Capture** - Write idea files with appropriate status

## Conversation Style

- Ask one question at a time
- Encourage exploration, not decisions
- "What else?" and "Tell me more" over "Which one?"
- Summarize what you're hearing before writing files
- For light mode: be concise, capture quickly

## Output Format

Files at: `docs/plans/{date}-{slug}-idea-{status}.md`

Status levels:
- `raw` - Just captured, minimal structure
- `refined` - Clear problem/opportunity statement, could benefit from more ideation
- `actionable` - Ready for a design/brainstorming skill

Example:
```
docs/plans/2026-01-18-caching-layer-idea-raw.md
docs/plans/2026-01-18-api-redesign-idea-refined.md
docs/plans/2026-01-18-dashboard-rethink-idea-actionable.md
```

## Idea File Content

Minimal - only what emerged:

```markdown
# Idea: [Short Name]

## Problem/Opportunity
[The core insight - might be all there is]

## Context
[Optional - constraints, related systems, user needs if they emerged]

## Open Questions
[Optional - things to explore further]

Related: other-idea-filename.md
```

Context and Open Questions are optional. Sometimes you're in unknown-unknowns territory.

## Session End

User-determined. When they indicate done, summarize:

> "This session produced 5 ideas: 2 raw, 2 refined, 1 actionable"

No minimum requirements.

## What Ideate Does NOT Do

- Make design decisions
- Pick which direction to pursue
- Automatically hand off to brainstorming
- Produce implementation details

## Handoff to Design

Manual. When user is ready to design one of the ideas:
1. They invoke a design/brainstorming skill
2. They reference the actionable idea file
3. The design skill reads it + linked ideas for context, then designs

Do NOT start designing unless user explicitly moves to a design skill.
