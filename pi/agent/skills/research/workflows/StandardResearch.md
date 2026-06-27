# Standard Research Workflow

**Mode:** 2 peers/search angles in parallel | **Timeout:** 1 minute

## CRITICAL: URL Verification Required

**BEFORE delivering any research results with URLs:**
1. Verify EVERY URL using curl or another real fetch tool
2. Confirm the content matches what you're citing
3. NEVER include unverified URLs - research agents HALLUCINATE URLs
4. A single broken link is a CATASTROPHIC FAILURE

See `references/UrlVerificationProtocol.md` for full protocol.

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

**SINGLE message with 2 Pi peer calls:**

```bash
mkdir -p .pi/research/scratch
~/.pi/agent/bin/agnt invoke olla-cloud/gemini-flash \
  "Research for depth/analysis: [query]. Return concise findings with source URLs and uncertainty." \
  > .pi/research/scratch/depth.md &
~/.pi/agent/bin/agnt invoke olla-cloud/gpt-4.1-mini \
  "Research for breadth/cross-domain perspectives: [query]. Return concise findings with source URLs and uncertainty." \
  > .pi/research/scratch/breadth.md &
wait
```

**Each peer:**
- Gets ONE query
- Does ONE search
- Returns immediately

### Step 3: Quick Synthesis

Combine the two perspectives:
- Note where they agree (high confidence)
- Note unique contributions from each
- Flag any conflicts

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

### Step 5: Return Results

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
