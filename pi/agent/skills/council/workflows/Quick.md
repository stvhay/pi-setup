# Quick Workflow

Fast single-round perspective check. Use for sanity checks and quick feedback.

## Prerequisites

- Topic or question to evaluate
- Optional: Custom council members

## Execution

### Step 1: Announce Quick Council

```markdown
## Quick Council: [Topic]

**Council Members:** [List agents]
**Mode:** Single round (fast perspectives)
```

### Step 2: Parallel Perspective Gathering

Route council work and choose distinct qualified targets from `candidateOrder` when diversity matters:

```bash
~/.pi/agent/bin/agnt route --task planning --risk medium --budget balanced
```

Launch one unnamed `subagent` call:

```json
{
  "tasks": [
    { "task": "[Architect prompt]", "model": "<routed target A>" },
    { "task": "[Designer prompt]", "model": "<routed target B>" },
    { "task": "[Engineer prompt]", "model": "<routed target C>" },
    { "task": "[Researcher prompt]", "model": "<routed target D>" }
  ]
}
```

Persist returned perspectives under `.pi/council/quick/` only when later rounds or handoff need transcripts.

**Each peer prompt:**
```
You are [Agent Name], [brief role description].

QUICK COUNCIL CHECK

Topic: [The topic]

Give your immediate take from your specialized perspective:
- Key concern, insight, or recommendation
- 30-50 words max
- Be direct and specific

This is a quick sanity check, not a full debate.
```

### Step 3: Output Perspectives

```markdown
### Perspectives

**Architect (Serena):**
[Brief take]

**Designer (Aditi):**
[Brief take]

**Engineer (Marcus):**
[Brief take]

**Researcher (Ava):**
[Brief take]

### Quick Summary

**Consensus:** [Do they generally agree? On what?]
**Concerns:** [Any red flags raised?]
**Recommendation:** [Proceed / Reconsider / Need full debate]
```

## When to Escalate

If the quick check reveals significant disagreement or complex trade-offs, recommend:

```
This topic has enough complexity for a full council debate.
Run: "Council: [topic]" for 3-round structured discussion.
```

## Timing

- Total: 10-20 seconds

## Done

Quick perspectives gathered. Use for fast validation; escalate to DEBATE for complex decisions.
