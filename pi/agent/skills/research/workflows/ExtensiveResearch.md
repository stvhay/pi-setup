# Extensive Research Workflow

**Mode:** 9 peers/search angles (3 types x 3 threads each) | **Review point:** 5 minutes

## CRITICAL: URL Verification Required

**BEFORE delivering any research results with URLs:**
1. Verify EVERY URL using curl or another real fetch tool
2. Confirm the content matches what you're citing
3. NEVER include unverified URLs - research agents HALLUCINATE URLs
4. A single broken link is a CATASTROPHIC FAILURE

See `references/UrlVerificationProtocol.md` for full protocol.

## When to Use

- User says "extensive research" or "do extensive research"
- Deep-dive analysis needed
- Comprehensive multi-domain coverage required
- High-stakes decisions requiring thorough research

## Workflow

### Step 0: Generate Creative Research Angles

Think deeply about the research topic:
- Explore multiple unusual perspectives and domains
- Question assumptions about what's relevant
- Make unexpected connections across fields
- Consider edge cases, controversies, emerging trends

Generate 3 unique angles per peer type (9 total queries).

### Step 1: Launch All Research Peers in Parallel

Route the task and select up to three distinct qualified targets from `candidateOrder`:

```bash
~/.pi/agent/bin/agnt route --task research --risk medium --budget balanced
```

Launch one `subagent` call with nine task entries and no `agent` fields:

```json
{
  "tasks": [
    { "task": "Analytical research angle 1 for [topic]: [angle 1]. Return findings with source URLs and uncertainty.", "model": "<routed analytical target>" },
    { "task": "Analytical research angle 2 for [topic]: [angle 2]. Return findings with source URLs and uncertainty.", "model": "<routed analytical target>" },
    { "task": "Analytical research angle 3 for [topic]: [angle 3]. Return findings with source URLs and uncertainty.", "model": "<routed analytical target>" },
    { "task": "Cross-domain research angle 4 for [topic]: [angle 4]. Return findings with source URLs and uncertainty.", "model": "<routed breadth target>" },
    { "task": "Cross-domain research angle 5 for [topic]: [angle 5]. Return findings with source URLs and uncertainty.", "model": "<routed breadth target>" },
    { "task": "Cross-domain research angle 6 for [topic]: [angle 6]. Return findings with source URLs and uncertainty.", "model": "<routed breadth target>" },
    { "task": "Contrarian fact-based research angle 7 for [topic]: [angle 7]. Return findings with source URLs and uncertainty.", "model": "<routed contrarian target>" },
    { "task": "Contrarian fact-based research angle 8 for [topic]: [angle 8]. Return findings with source URLs and uncertainty.", "model": "<routed contrarian target>" },
    { "task": "Contrarian fact-based research angle 9 for [topic]: [angle 9]. Return findings with source URLs and uncertainty.", "model": "<routed contrarian target>" }
  ]
}
```

Persist returned results under `.pi/research/scratch/` only when synthesis needs durable files.

**Each peer:**
- Gets ONE focused angle
- Does 1-2 searches max
- Returns as soon as it has findings

### Step 2: Collect Results (5-MINUTE REVIEW POINT)

- Peers run in parallel with live TUI status.
- Most should return within 30-90 seconds.
- Archimedes has no total wall-clock deadline; if work remains after five minutes, cancel only when enough coverage exists or the user requests a time limit.
- Note cancelled or non-responsive peers.

### Step 3: Comprehensive Synthesis

**Synthesis requirements:**
- Identify themes across all 9 research angles
- Cross-validate findings from multiple sources
- Highlight unique insights from each approach
- Note where sources agree (high confidence)
- Flag conflicts or gaps

**Report structure:**
```markdown
## Executive Summary
[2-3 sentence overview]

## Key Findings
### [Theme 1]
- Finding (confirmed by: multiple agents)
- Finding (source: specific peer)

### [Theme 2]
...

## Unique Insights by Approach
- **Analytical**: [depth findings]
- **Multi-perspective**: [cross-domain connections]
- **Contrarian**: [alternative viewpoints]

## Conflicts & Uncertainties
[Note disagreements]
```

### Step 4: VERIFY ALL URLs (MANDATORY)

**Before delivering results, verify EVERY URL:**

```bash
# For each URL returned by agents:
curl -s -o /dev/null -w "%{http_code}" -L "URL"
# Must return 200

# Then verify content:
curl -L "URL" | head -c 4000  # confirm content matches the citation
# Must return actual content, not error
```

**If URL fails verification:**
- Remove it from results
- Find an alternative source using an available search method
- Verify the replacement URL
- NEVER include unverified URLs

**Extensive mode generates MANY URLs - allocate time for verification.**

### Step 5: Return Results

```markdown
## Extensive Research: [topic]

### Executive Summary
[2-3 sentence overview]

### Key Findings
[Comprehensive findings by theme]

### Unique Insights
- **From depth analysis**: [key insight]
- **From breadth analysis**: [key insight]
- **From contrarian analysis**: [key insight]

### Sources (Verified)
- [URL 1]
- [URL 2]
- ...

### Confidence Assessment
[Overall confidence level with rationale]

### Research Metrics
- Total peers: 9
- Approaches: analytical, multi-perspective, contrarian
- Coverage: [assessment]
```

## Speed Target

~60-90 seconds for results (parallel execution)
