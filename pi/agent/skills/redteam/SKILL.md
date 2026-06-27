---
name: redteam
description: Adversarial analysis with multiple perspectives. Use when red team, attack idea, counterarguments, critique, stress test, devil's advocate, or poke holes in an argument.
---

# RedTeam Skill

Adversarial analysis using parallel Pi peer deployment. Breaks arguments into atomic components, attacks from multiple expert perspectives (engineers, architects, pentesters, interns), synthesizes findings, and produces strong counter-arguments with steelman representations.

**Pi execution model:** Use `~/.pi/agent/bin/agnt invoke` or `~/.pi/agent/bin/agnt invoke --fanout` for independent adversarial passes. Start with 4-8 peers for normal work; reserve the full 32-perspective protocol for high-stakes analysis.

## Workflow Routing

Route to the appropriate workflow based on the request.

| Trigger | Workflow |
|---------|----------|
| Red team analysis (stress-test existing content) | `references/ParallelAnalysis.md` |
| Adversarial validation (produce new content via competition) | `references/AdversarialValidation.md` |

## Quick Reference

| Workflow | Purpose | Output |
|----------|---------|--------|
| **ParallelAnalysis** | Stress-test existing content | Steelman + Counter-argument (8-points each) |
| **AdversarialValidation** | Produce new content via competition | Synthesized solution from competing proposals |

**The Five-Phase Protocol (ParallelAnalysis):**
1. **Decomposition** - Break into 24 atomic claims
2. **Parallel Analysis** - 4-32 peer passes examine strengths AND weaknesses
3. **Synthesis** - Identify convergent insights
4. **Steelman** - Strongest version of the argument
5. **Counter-Argument** - Strongest rebuttal

## Context Files

- `references/Philosophy.md` - Core philosophy, success criteria, agent types
- `references/Integration.md` - Skill integration, output format

## Examples

**Attack an architecture proposal:**
```
User: "red team this microservices migration plan"
--> references/ParallelAnalysis.md
--> Returns steelman + devastating counter-argument (8 points each)
```

**Devil's advocate on a business decision:**
```
User: "poke holes in my plan to raise prices 20%"
--> references/ParallelAnalysis.md
--> Surfaces the ONE core issue that could collapse the plan
```

**Adversarial validation for content:**
```
User: "battle of bots - which approach is better for this feature?"
--> references/AdversarialValidation.md
--> Synthesizes best solution from competing ideas
```

## Integration

**Use BEFORE RedTeam:**
- `research` - Gather context, find precedents

**Use AFTER RedTeam:**
- Consider alternatives or adjustments based on findings

**Use FOR system-level security:**
- `stamp-stpa-sec` - Control-theoretic security threat modeling for systems with control structures. When redteam reveals security concerns about a system architecture, hand off to STPA-Sec for formal threat modeling with STRIDE integration.
