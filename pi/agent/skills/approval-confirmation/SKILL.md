---
name: approval-confirmation
description: Use when designing informed-consent approval interfaces for agentic systems.
---

# Approval & Confirmation

## Overview

Design approval interfaces that enable informed consent under time pressure.

**Core principle:** Users who approve know what they're approving. Users who reject know what they're preventing.

**Announce at start:** "I'm using the approval-confirmation skill to design the approval interface."

## When to Use

Use directly for consent/approval UI work, or after delegation-oversight identifies a checkpoint. No parent skill is required.

## The Core Problem

**Rubber-stamping:** User approves without understanding. Approval is theater.

**Approval fatigue:** Every request looks the same. Users can't triage.

Both fail because the request didn't communicate what users need to decide.

## Six Capability Domains

### 1. Pre-Action Preview

**Principle:** Show the action, don't describe it.

```
✗ "I'd like to send an email to the client."
✓ [Rendered email preview] with [Send] [Edit] [Cancel]
```

**Components:**
- Action statement (one sentence)
- Rendered artifact (WYSIWYG)
- Scope indicator (what changes, what doesn't)
- Trigger context (why this is happening)

**Rule:** Preview evaluation < 30 seconds. Longer = too much or too complex.

### 2. Stakes Communication

Not all approvals are equal. Calibrate treatment to consequence.

| Stakes | Treatment | Example |
|--------|-----------|---------|
| Routine | Inline, minimal friction | "Send?" |
| Notable | Standard confirmation | "Send email to 47 recipients" |
| Significant | Elevated, consequence statement | "...includes external addresses" |
| Critical | Maximum friction, explicit acknowledgment | "...cannot be recalled" |

**Anti-inflation:** If everything is "important," nothing is.

### 3. Consequence Visualization

| Type | Question | Approach |
|------|----------|----------|
| Immediate | What happens now? | Before/after |
| Downstream | What does this trigger? | Dependency chain |
| Reversibility | Can I undo? | Explicit statement |
| Rejection | What if I say no? | Alternative path |

### 4. Modification Options

**Binary trap:** Yes/No loses information. Real decisions have nuance.

| Dimension | Pattern |
|-----------|---------|
| Content | Inline edit of artifact |
| Scope | Subset selection |
| Parameters | Value adjustment |
| Conditions | "Approve if..." |
| Timing | Defer/schedule |

### 5. Batch Approval

**When to batch:** Same action type, same trigger, same stakes.

**Don't batch:** Varying stakes, unrelated actions.

**Pattern:**
```
Level 1: Summary ("5 emails ready")
Level 2: Grouped detail (Internal: 3, External: 2)
Level 3: Individual detail (on expand)
```

### 6. Time-Bounded Approval

**Every timeout needs:**
- Deadline (when it expires)
- Default behavior (block execution; preserve authorized state)
- Rationale (why deadline exists)
- Extension path (how to get more time)

**Required approval expiry always blocks execution**, regardless of stakes or reversibility. Rejection and cancellation also fail closed. Preserve already-authorized work; require renewed approval after revalidating scope. Confidence, prior similar approvals and easy undo are not current consent.

Escalation, reminders and remote draft saves are effects needing independent authority, not automatic timeout fallbacks. A separately authorized scheduled action is not approval by timeout; it must retain its own valid scope and expiry. Read `references/timeout-patterns.md` when designing expiry/recovery states.

## Output

Add to requirements document:

```markdown
## Approval Design

### Preview Components
- [What users see before approving]

### Stakes Calibration
- Routine: [examples]
- Critical: [examples]

### Modification Options
- [What users can adjust]

### Timeout Behavior
- Default: block execution; preserve already-authorized state
- Recovery: revalidate preview/scope and obtain renewed approval
- Deadline: [when/why]
```

## Integration

For a distinct requested output, read only the selected specialist (reuse if already loaded):
- Recovery after timeout, rejection or partial approval: `~/.pi/agent/skills/failure-choreography/SKILL.md`. Carry preserved/lost/uncertain state and allowed effects; return recovery options.
- Copy refinement: `~/.pi/agent/skills/ux-writing/SKILL.md`. Carry preview and audience; return interface text.
- Uncertainty framing: `~/.pi/agent/skills/trust-calibration/SKILL.md`. Carry claims, evidence and limits; return calibrated wording.

These are optional collaborations, not a pipeline or execution authority. Ask before expanding scope; none may bypass required approval.

## Anti-Patterns

**Wall of text:** Information dump no one reads.

**Uniform severity:** Every approval looks identical.

**Binary forcing:** No modification options.

**Hidden timeout defaults:** System acts without user knowing what happens.

## References

- `references/preview-patterns.md` - Preview components
- `references/stakes-patterns.md` - Stakes calibration
- `references/consequence-patterns.md` - Visualization patterns
- `references/modification-patterns.md` - Edit options
- `references/batch-patterns.md` - Grouping patterns
- `references/timeout-patterns.md` - Timeout handling
