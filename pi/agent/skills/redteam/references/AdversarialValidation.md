# Adversarial Validation Pattern (Battle of Bots)

**Purpose:** Use competing peer personas + critic to produce superior synthesis through adversarial refinement.

**When to Use:**
- Feature specifications that need stress-testing
- Architectural decisions before implementation
- Code reviews where multiple approaches exist
- Content that needs to withstand scrutiny
- Any output where quality matters more than speed

## The Three-Round Protocol

### Round 1: Competing Proposals

Launch 2-3 specialized peer personas to produce competing solutions from different perspectives. Use separate Pi peer calls for high independence, or the collapsed single-prompt template below for speed.

```
ADVERSARIAL VALIDATION - ROUND 1 (COMPETING PROPOSALS):

You are [PERSONA]. Generate your best solution to this problem.

Your perspective emphasizes:
- [Key concern 1]
- [Key concern 2]
- [Key concern 3]

Produce a complete solution that optimizes for YOUR priorities.
Be specific and detailed - this will be compared against other proposals.

[Problem/Task description]
```

**Suggested Persona Combinations:**

**For Architecture Decisions:**
- Engineer (implementation ease, maintainability)
- Architect (scalability, patterns, long-term)
- Security (attack surface, vulnerabilities)

**For Feature Specs:**
- Product (user value, simplicity)
- Engineer (feasibility, complexity)
- QA (testability, edge cases)

**For Content/Writing:**
- Subject Matter Expert (accuracy, depth)
- Audience Representative (clarity, engagement)
- Editor (structure, flow)

### Round 2: Brutal Critique

A critic peer/persona reads ALL proposals and "brutally critiques" each:

```
ADVERSARIAL VALIDATION - ROUND 2 (BRUTAL CRITIQUE):

You are the Harsh Critic. You have received [N] proposals for [problem].

For EACH proposal:

1. **What they got RIGHT:**
   - Acknowledge genuine strengths (be specific)

2. **What they got WRONG:**
   - Identify flaws, gaps, weaknesses
   - Point out what they conveniently ignored
   - Highlight where their perspective blinds them

3. **The Uncomfortable Truth:**
   - What none of them want to hear?
   - What's the real problem they're all dancing around?

4. **If forced to pick one:**
   - Which has the strongest foundation?
   - Why?

Be harsh but fair. The goal is truth, not destruction.

[Proposals from Round 1]
```

### Round 3: Collaborative Synthesis

The original peer personas read the critique and collaborate on a final solution:

```
ADVERSARIAL VALIDATION - ROUND 3 (COLLABORATIVE SYNTHESIS):

You are [PERSONA]. You've seen the Critic's brutal assessment.

Working with the other peer perspectives, produce a SINGLE UNIFIED solution that:
- Addresses the valid criticisms
- Incorporates the best elements from each proposal
- Resolves the tensions between perspectives
- Acknowledges remaining trade-offs honestly

This is not compromise - it's synthesis. The final output should be BETTER
than any individual proposal, not just a blend.

[Original proposals + Critic's assessment]
```

## Choosing Multi-Round vs Single-Prompt

| Use Multi-Round (3 separate rounds) | Use Single-Prompt (collapsed template) |
|--------------------------------------|----------------------------------------|
| High-stakes decisions (architecture, strategy) | Quick exploration of trade-offs |
| You need genuinely independent proposals | Time-constrained — need a fast answer |
| The problem space is large or ambiguous | The problem is well-scoped with 2-3 obvious approaches |
| You want to iterate on critique before synthesis | You trust the LLM to self-critique honestly |

Multi-round produces higher quality because each round gets full context window attention. Single-prompt is faster but proposals tend to be less independent (the model knows it will critique them).

## Complete Adversarial Validation Template

For a single-prompt execution:

```
ADVERSARIAL VALIDATION - FULL PROTOCOL:

ROUND 1 - COMPETING PROPOSALS:
Generate 3 distinct solutions to this problem from different perspectives:

Proposal A (Pragmatist): Prioritizes ease of implementation and quick wins
Proposal B (Idealist): Prioritizes best practices and long-term quality
Proposal C (Skeptic): Prioritizes risk reduction and failure prevention

Each proposal should be complete and defensible.

ROUND 2 - BRUTAL CRITIQUE:
As a harsh but fair critic, evaluate all three proposals:
- What each got right
- What each got wrong
- The uncomfortable truth none addressed
- Which has the strongest foundation

ROUND 3 - COLLABORATIVE SYNTHESIS:
Synthesize the best elements into a single superior solution that:
- Addresses the valid criticisms
- Incorporates strengths from each proposal
- Resolves tensions between perspectives
- Honestly acknowledges remaining trade-offs

OUTPUT:
- Brief summary of the three proposals
- Key critique points
- Final synthesized recommendation with clear rationale

[Problem/Task to validate]
```

## Integration with Parallel Analysis

**Relationship:**
- The parallel analysis protocol is for DEPTH - attacking one argument from many perspectives
- Adversarial Validation is for SYNTHESIS - producing better output through competition and refinement

**When to Use Which:**
- **32-Agent Protocol:** "Red team this argument/idea" - stress-test existing content
- **Adversarial Validation:** "Help me design/decide/create X" - produce new content through adversarial refinement

**Combining Both:**
1. Use Adversarial Validation to produce initial solution
2. Use 32-Agent Protocol to stress-test the synthesized result
3. Iterate if critical flaws found

## Quality Signals

**Good Adversarial Validation:**
- Each proposal genuinely represents its perspective (not strawmen)
- Critic finds real flaws, not just nitpicks
- Synthesis is demonstrably better than any individual proposal
- Trade-offs are honestly acknowledged
- Final output withstands scrutiny

**Bad Signs:**
- Proposals are too similar (not enough diversity)
- Critic is too gentle or too destructive
- "Synthesis" is just one proposal with minor tweaks
- Trade-offs are handwaved away
- Adversarial process feels performative

## Example: API Design Decision

**Problem:** "Design authentication flow for our new API"

**Round 1 Proposals:**

**Proposal A (Pragmatist):** JWT with 24-hour expiry, refresh tokens, standard claims. Quick to implement, well-understood pattern.

**Proposal B (Idealist):** OAuth 2.0 with PKCE, short-lived access tokens (15 min), secure token storage, audit logging. Industry best practice.

**Proposal C (Skeptic):** API keys with rate limiting, IP allowlisting, manual rotation. Minimal attack surface, easy to revoke.

**Round 2 Critique:**

- A is fast but JWT secrets are hard to rotate, 24h is too long
- B is gold standard but massive implementation overhead for current team size
- C is secure but doesn't scale to public API use case

Uncomfortable truth: None addressed the question of "what happens when we NEED to revoke all tokens immediately?"

**Round 3 Synthesis:**

Start with A's JWT approach (pragmatic), add B's short-lived tokens (15 min) and audit logging (security), implement C's emergency revocation list (skeptic's concern). Defer full OAuth until public API launch.

## Key Principles

1. **Genuine competition** - Proposals must represent real alternatives, not strawmen
2. **Brutal but fair critique** - Find real flaws, acknowledge real strengths
3. **Synthesis > Compromise** - The goal is BETTER, not BLENDED
4. **Honest trade-offs** - Don't pretend tensions are fully resolved
5. **Permission to fail applies** - If no synthesis is clearly superior, say so

## When NOT to Use

- Simple decisions with obvious answers (overkill)
- Time-critical situations (too slow)
- Creative tasks where multiple valid outputs are fine
- Problems where expert consensus already exists

**Principle:** Adversarial Validation is for decisions where quality matters more than speed.
