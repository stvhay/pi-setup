---
name: council
description: Multi-agent debate system for decision-making. Use when council, debate, perspectives, agents discuss, or need multiple viewpoints on a decision.
---

# Council Skill

Multi-agent debate system where specialized agents discuss topics in rounds, respond to each other's points, and surface insights through intellectual friction.

**Key Differentiator from RedTeam:** Council is collaborative-adversarial (debate to find best path), while RedTeam is purely adversarial (attack the idea). Council produces visible conversation transcripts; RedTeam produces steelman + counter-argument.

## Workflow Routing

Route to the appropriate workflow based on the request.

| Trigger | Workflow |
|---------|----------|
| Full structured debate (3 rounds, visible transcript) | `workflows/Debate.md` |
| Quick consensus check (1 round, fast) | `workflows/Quick.md` |
| Pure adversarial analysis | **Use redteam skill instead** |

## Quick Reference

| Workflow | Purpose | Rounds | Output |
|----------|---------|--------|--------|
| **DEBATE** | Full structured discussion | 3 | Complete transcript + synthesis |
| **QUICK** | Fast perspective check | 1 | Initial positions only |

## Context Files

| File | Content |
|------|---------|
| `references/CouncilMembers.md` | Agent roles, perspectives |
| `references/RoundStructure.md` | Three-round debate structure |
| `references/OutputFormat.md` | Transcript format templates |

## Core Philosophy

**Origin:** Best decisions emerge from diverse perspectives challenging each other. Not just collecting opinions - genuine intellectual friction where experts respond to each other's actual points.

**Pi execution model:** Use shell-dispatched peer Pi calls for each council member. Parallelize within a round with `~/.pi/agent/bin/agnt invoke --fanout` or backgrounded `~/.pi/agent/bin/agnt invoke` calls; run rounds sequentially so later rounds can see earlier transcripts.

**Speed:** Parallel execution within rounds, sequential between rounds. A 3-round debate of 4 agents = 12 peer calls but only 3 sequential waits. Local models may take longer than cloud models.

## Examples

```
"Council: Should we use WebSockets or SSE?"
-> Invokes DEBATE workflow -> 3-round transcript

"Quick council check: Is this API design reasonable?"
-> Invokes QUICK workflow -> Fast perspectives

"Council with security: Evaluate this auth approach"
-> DEBATE with Security agent added
```

## Integration

**Works well with:**
- **redteam** (redteam plugin) - Pure adversarial attack after collaborative discussion
- **brainstorming** (dev-workflow-toolkit plugin) - Before major architectural decisions
- **research** - Gather context before convening the council

## Best Practices

1. Use QUICK for sanity checks, DEBATE for important decisions
2. Add domain-specific experts as needed (security for auth, etc.)
3. Review the transcript - insights are in the responses, not just positions
4. Trust multi-model convergence when it occurs, but note model/provider bias when all peers agree for the same reason
