---
name: redteam
description: Use when adversarially critiquing or stress-testing an argument, idea, decision, or plan from multiple perspectives.
---

# RedTeam Skill

Adversarial analysis using parallel Pi peer deployment. Breaks arguments into atomic components, attacks from multiple expert perspectives (engineers, architects, pentesters, interns), synthesizes findings, and produces strong counter-arguments with steelman representations.

**Pi execution model:** Route with `agnt route --task review`, then run independent adversarial passes through one unnamed Archimedes `subagent` call. Start with 4-8 parallel task entries for normal work; reserve the full 32-perspective protocol for high-stakes analysis.

## Workflow Routing

Choose the requested output first. This skill owns critique and central-critic competition; reciprocal debate belongs to `~/.pi/agent/skills/council/SKILL.md`, while concrete diff correctness belongs to `~/.pi/agent/skills/requesting-code-review/SKILL.md`. Read the selected skill with the question/candidate, evidence and constraints; expect debate rounds or verified findings respectively. Do not run both automatically or expand scope without approval.

For critique or central-critic competition, select the existing workflow below.

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
- If a distinct formal analysis of adversarial control/feedback paths is requested, read `~/.pi/agent/skills/stamp-stpa-sec/SKILL.md`. Carry scope, architecture, critique evidence and unresolved assumptions; expect threat scenarios and traceable security requirements. Ask before expanding scope. Security concerns alone do not mandate STPA-Sec; honor a STRIDE-only request.
