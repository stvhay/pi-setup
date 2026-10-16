---
name: ux-design-agent
description: Use when designing user experiences, especially interfaces or agentic workflows with unclear users or usage.
---

# UX Design Agent

## Overview

Extract requirements, model users, select modality. Hand off to implementation skills.

**Core principle:** Solve the right problem for the right user through the right interface.

**Announce at start:** "I'm using the ux-design-agent skill to design this experience."

## When to Use

Use for unclear users, usage or interaction modality. If these are already established, return them to design approval rather than repeating discovery. An obvious user model does not authorize planning or implementation.

Copy, consent, recovery and evidence communication can enter their specialist skills directly; this skill is not a mandatory gateway.

## Skill Coordination

Load only the specialist needed for the requested output (reuse unchanged loaded instructions):

| Need | Read | Output |
|---|---|---|
| Polished GUI | `~/.pi/agent/skills/design-principles/SKILL.md` | Visual design |
| Ask-versus-act boundaries | `~/.pi/agent/skills/delegation-oversight/SKILL.md` | Delegation/handoff design |
| Informed consent | `~/.pi/agent/skills/approval-confirmation/SKILL.md` | Approval preview and scope |
| Recovery after failure | `~/.pi/agent/skills/failure-choreography/SKILL.md` | Preserved/lost/uncertain state and recovery |
| Confidence framing | `~/.pi/agent/skills/trust-calibration/SKILL.md` | Calibrated claims/evidence |
| Interface copy | `~/.pi/agent/skills/ux-writing/SKILL.md` | Buttons, errors and notifications |

Carry user/task, constraints, current state, allowed effects, unresolved decisions and existing artifact. Return the selected output to the design; ask before expanding scope. These are optional collaborations, not an automatic pipeline.

## The Process

### Phase 1: Requirements Archaeology
- What problem are we actually solving?
- What does success feel like?
- What are the hard constraints?

### Phase 2: User Modeling
- Task frequency (daily vs. quarterly)
- Expertise gradient (domain, interface, this tool)
- Context of use (time pressure, environment)

### Phase 3: Modality Selection

| Modality | Use When |
|----------|----------|
| GUI | Visual scanning, comparison, novice users |
| CLI | Precision, scripting, expert users |
| Voice | Hands-free, accessibility |
| Agentic | User wants outcome not process |

### Phase 4: Hand Off

Select relevant specialists above for GUI or agentic needs; CLI/voice may need only requirements. Preserve supplied evidence rather than restarting discovery.

Return requirements/options to `~/.pi/agent/skills/brainstorming/SKILL.md` when converging on a design. Present the design and obtain approval before file writes or implementation planning. Once approved, read `~/.pi/agent/skills/writing-plans/SKILL.md` with that design, constraints and acceptance criteria to produce the implementation plan. Stop if approval or scope is unresolved.

## Output

Before design approval, present requirements in the response only. After approval, resolve the project plan directory:

```bash
PLANS_DIR=$(~/.pi/agent/bin/agnt plans-dir)
```

Save useful requirements to `$PLANS_DIR/YYYY-MM-DD-<feature>-requirements.md`; reuse an approved combined design-plan instead of duplicating it.

Format:
```markdown
# [Feature] Requirements

## Problem Statement
[One paragraph]

## User Model
- Primary user: [behavioral description]
- Context: [when/where/how they use this]
- Expertise: [domain, interface, tool]

## Success Criteria
- [Measurable outcomes]

## Modality
[Selected modality with rationale]

## Constraints
- [Technical, regulatory, organizational]

## Delegation Design (if agentic)
[From delegation-oversight]

## Approval Design (if agentic)
[From approval-confirmation]

## Failure Handling (if agentic)
[From failure-choreography]
```

## Integration

Brainstorming may conditionally load this skill for unclear users/usage/modality. Direct entry is also valid. Return the requirements to the caller's design approval gate; only an approved design proceeds to implementation planning.
