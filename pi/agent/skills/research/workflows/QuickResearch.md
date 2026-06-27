# Quick Research Workflow

**Mode:** Single peer/search angle, 1 query | **Timeout:** 30 seconds

## When to Use

- User says "quick research" or "minor research"
- Simple, straightforward queries
- Time-sensitive requests
- Just need a fast answer

## Workflow

### Step 1: Launch Single Peer/Search Angle

**ONE Pi peer call with a single focused query:**

```bash
~/.pi/agent/bin/agnt invoke olla-cloud/gemini-flash \
  "Do focused research for: [query]. Use only sources you can name. Return key findings, source URLs, and uncertainty. Keep it brief and factual." \
  > .pi/research/scratch/quick.md
```

**Prompt requirements:**
- Single, well-crafted query
- Instruct to return immediately after first search
- No multi-query exploration

### Step 2: Return Results

Report findings using this format:

```markdown
## Quick Research: [topic]

**Key Findings:**
[Main points from the search]

**Sources:**
- [Verified URL 1]
- [Verified URL 2]

**Confidence:** [High/Medium/Low based on source quality]

**Need more depth?** Run "do research on [topic]" for standard mode.
```

## Speed Target

~10-15 seconds for results
