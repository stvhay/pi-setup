---
name: council
description: Use when a decision needs structured debate or multiple agent perspectives.
---

# Council Skill

Multi-agent debate system where specialized agents discuss topics in rounds, respond to each other's points, and surface insights through intellectual friction.

**Boundary:** Council uses reciprocal debate with visible rounds and synthesis. Redteam offers steelman/counterargument or central-critic competition between proposals; it is not reciprocal debate. Keep their distinct output contracts.

## Workflow Routing

Route to the appropriate workflow based on the request.

| Trigger | Workflow |
|---------|----------|
| Full structured debate (3 rounds, visible transcript) | `workflows/Debate.md` |
| Quick consensus check (1 round, fast) | `workflows/Quick.md` |
| Critique or central-critic competition | Read `~/.pi/agent/skills/redteam/SKILL.md` |

Carry the question, positions, evidence and constraints into that handoff; request critique/proposal evaluation rather than another debate. Ask before expanding scope; do not run both workflows automatically.

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

**Pi execution model:** Route council work with `agnt route`, then call unnamed Archimedes `subagent` peers. Use one parallel `tasks` array per round and run rounds sequentially so later prompts can include earlier transcripts.

**Speed:** Parallel execution within rounds, sequential between rounds. A 3-round debate of 4 agents = 12 peer calls but only 3 sequential waits.

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
- **redteam** - Optional critique or central-critic competition, not an automatic post-debate phase
- **brainstorming** (dev-workflow-toolkit plugin) - Before major architectural decisions
- **research** - Gather context before convening the council

## Best Practices

1. Use QUICK for sanity checks, DEBATE for important decisions
2. Add domain-specific experts as needed (security for auth, etc.)
3. Review the transcript - insights are in the responses, not just positions
4. Trust multi-model convergence when it occurs, but note model/provider bias when all peers agree for the same reason
