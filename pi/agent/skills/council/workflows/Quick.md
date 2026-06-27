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

Launch all council members in parallel using shell-dispatched Pi peers. Use `~/.pi/agent/bin/agnt invoke --fanout` for default model diversity, or background `~/.pi/agent/bin/agnt invoke` calls when you need specific model/persona assignments.

Example:

```bash
mkdir -p .pi/council/quick
~/.pi/agent/bin/agnt invoke olla-cloud/gpt-4.1-mini "[Architect prompt]" > .pi/council/quick/architect.md &
~/.pi/agent/bin/agnt invoke olla-cloud/gemini-flash "[Designer prompt]" > .pi/council/quick/designer.md &
~/.pi/agent/bin/agnt invoke olla-local/qwen3:8b "[Engineer prompt]" > .pi/council/quick/engineer.md &
~/.pi/agent/bin/agnt invoke ollama/gemma4:31b "[Researcher prompt]" > .pi/council/quick/researcher.md &
wait
```

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
