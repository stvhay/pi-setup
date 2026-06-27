# Extensive Research Workflow

**Mode:** 9 peers/search angles (3 types x 3 threads each) | **Timeout:** 5 minutes

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

**Launch 9 Pi peer calls (3 types x 3 threads each):**

```bash
mkdir -p .pi/research/scratch
for i in 1 2 3; do
  ~/.pi/agent/bin/agnt invoke olla-cloud/gemini-flash \
    "Analytical research angle $i for [topic]: [angle $i]. Return findings with source URLs and uncertainty." \
    > ".pi/research/scratch/analytical-$i.md" &
done
for i in 4 5 6; do
  ~/.pi/agent/bin/agnt invoke olla-cloud/gpt-4.1-mini \
    "Cross-domain research angle $i for [topic]: [angle $i]. Return findings with source URLs and uncertainty." \
    > ".pi/research/scratch/breadth-$i.md" &
done
for i in 7 8 9; do
  ~/.pi/agent/bin/agnt invoke olla-local/qwen3:8b \
    "Contrarian fact-based research angle $i for [topic]: [angle $i]. Return findings with source URLs and uncertainty." \
    > ".pi/research/scratch/contrarian-$i.md" &
done
wait
```

**Each peer:**
- Gets ONE focused angle
- Does 1-2 searches max
- Returns as soon as it has findings

### Step 2: Collect Results (5 MINUTE TIMEOUT)

- Peers run in parallel
- Most return within 30-90 seconds
- **HARD TIMEOUT: 5 minutes** - proceed with whatever has returned
- Note non-responsive peers

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
