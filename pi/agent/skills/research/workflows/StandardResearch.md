# Standard Research Workflow

**Mode:** 2 peers/search angles in parallel | **Target:** about 1 minute

## When to Use

- Default mode for most research requests
- User says "do research" or "research this"
- Need multiple perspectives quickly

## Workflow

### Step 1: Craft One Query Per Peer

Create ONE focused query optimized for each researcher's strengths:
- **Peer 1**: Academic depth, detailed analysis, scholarly sources
- **Peer 2**: Multi-perspective synthesis, cross-domain connections

### Step 2: Launch 2 Peers in Parallel

Route once and choose two distinct qualified targets from `candidateOrder` when available:

```bash
~/.pi/agent/bin/agnt route --task research --risk medium --budget balanced
```

Make one `subagent` call with `agent` omitted:

```json
{
  "tasks": [
    { "task": "Research for depth/analysis: [query]. Return concise findings with source URLs and uncertainty.", "model": "<routed target A>" },
    { "task": "Research for breadth/cross-domain perspectives: [query]. Return concise findings with source URLs and uncertainty.", "model": "<routed target B>" }
  ]
}
```

Persist returned results to `.pi/research/scratch/depth.md` and `breadth.md` only when later synthesis needs files.

**Each peer:**
- Gets ONE query
- Does ONE search
- Returns immediately

### Step 3: Quick Synthesis

Combine the two perspectives:
- Note where they agree (high confidence)
- Note unique contributions from each
- Flag any conflicts

### Step 4: Return Results

```markdown
## Research: [topic]

**Key Findings:**
[Synthesized answer from both perspectives]

**From Depth Analysis:**
- [Key point 1]
- [Key point 2]

**From Breadth Analysis:**
- [Key point 1]
- [Key point 2]

**Sources:**
- [Verified URL 1]
- [Verified URL 2]

**Confidence:** [High/Medium/Low]

**Need more depth?** Run "extensive research on [topic]" for comprehensive mode.
```

## Speed Target

~15-30 seconds for results
