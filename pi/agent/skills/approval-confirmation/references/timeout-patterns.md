# Time-Bounded Approval Patterns Reference

Timing algorithms, default logic, and state preservation for approval timeouts.

## Timeout Architecture

Every time-bounded approval has four components:

```
┌───────────────────────────────────────────────────────────┐
│                    TIMEOUT ANATOMY                        │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  DEADLINE           When approval expires                 │
│  ────────           "Respond by 3:00 PM"                  │
│                                                           │
│  DEFAULT            What happens on expiry                │
│  ───────            "Block; retain authorized state"       │
│                                                           │
│  RATIONALE          Why there's a deadline                │
│  ─────────          "Client expects EOD response"         │
│                                                           │
│  EXTENSION          How to get more time                  │
│  ─────────          "Need more time? [Extend 1 hour]"     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Deadline Display Patterns

### Absolute Time
Best when: User can reference against their calendar.

```
⏱ Approval needed by 3:00 PM EST
```

### Countdown
Best when: Urgency is key; user is currently active.

```
⏱ 47 minutes remaining
```

### Relative with Absolute
Best of both—relative for urgency, absolute for planning.

```
⏱ 47 minutes (expires 3:00 PM)
```

### Progress Bar
Visual urgency indicator.

```
⏱ [████████████░░░░░░░░░░░░░] 47 min remaining
              ▲
         You are here
```

### Urgency Thresholds

| Time Remaining | Display Treatment |
|----------------|-------------------|
| >1 hour | Static timestamp |
| 15-60 min | Countdown, neutral color |
| 5-15 min | Countdown, warning color |
| <5 min | Countdown, critical color, pulse/animation |

## Fail-Closed Default

Required approval expiry blocks execution at every stakes/reversibility level. Rejection and cancellation also block; they do not delete already-authorized work. Confidence, prior similar approvals and easy undo are not consent. Revalidate scope and preview before renewed approval.

### Default: Block and Preserve

```
If you don't respond by 3:00 PM:
→ Email will not be sent
→ Already-authorized draft and edits remain available
→ Review current scope and request renewed approval to resume
```

Remote draft saves, notifications, reminders and escalation require independent authority covering their own recipients, effects and expiry. Without it, retain permitted local state and report the blocker; do not contact anyone or create a remote draft. Examples below showing such effects assume that separate authority is still valid.

### Escalation, When Independently Authorized

Escalation requests a decision; it does not execute the original action. Show the approved recipient and exact information shared. The recipient must have authority to approve the current scope. Stop when disclosure or decision authority is missing.

### Partial Batch Approval

```
At expiry:
→ All unapproved items remain blocked, including routine internal emails
→ Report any items already executed under valid, separate approval
→ Preserve pending work; request renewed approval for remaining items
```

Do not convert batch similarity into partial consent. A separately authorized scheduled action is not a timeout approval; keep its own scope, conditions and expiry distinct.

## Timeout Communication Timeline

### Standard Timeline (non-urgent)

```
T+0:00   Initial request
         "Ready for approval"
         
T+4:00   First reminder (if no response)
         "Still waiting for your approval on [action]"
         
T+8:00   Second reminder + warning
         "Approval expires in 16 hours. [Default behavior] if no response."
         
T+24:00  Deadline
         Block execution; preserve authorized state
         
T+24:01  Notification of outcome
         "Approval expired. Action blocked; authorized work preserved."
```

### Urgent Timeline

```
T+0:00   Initial request
         "Urgent: Approval needed by [time]"
         
T-15:00  Warning (15 min before deadline)
         "Deadline in 15 minutes. [Default behavior] if no response."
         
T-5:00   Final warning (5 min before deadline)
         "5 minutes remaining. Action will remain blocked without approval."
         
T+0:00   Deadline
         Block execution; preserve authorized state
         
T+0:01   Notification
         "Approval expired. Action blocked; authorized work preserved."
```

### Deadline Arrived (User Present)

If user is actively viewing when deadline arrives:

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Deadline reached                                     │
│                                                         │
│ Choose now:                                             │
│                                                         │
│ [Review and renew] [Reject] [Keep paused]                │
│                                                         │
│ Execution blocked. Renew approval to continue.          │
│ Default: Preserve already-authorized state              │
│                                                         │
│ [██████████░░░░░░░░░░░░░░░░░░░░]                        │
└─────────────────────────────────────────────────────────┘
```

## Extension Patterns

Extensions keep the request pending, not approved. After expiry, revalidate context and request renewed approval; extending a display timer cannot revive expired authority.

### Simple Extension

```
Need more time?
[Extend 1 hour] [Extend to tomorrow]
```

### Extension with Justification

```
Extend deadline?

Original deadline: 3:00 PM (client expects EOD response)

○ Extend 1 hour (new deadline: 4:00 PM)
○ Extend to end of day (new deadline: 6:00 PM)
○ Extend to tomorrow (new deadline: Oct 16, 9:00 AM)
  └── ⚠️ This may disappoint client expectation

[Extend] [Decide now instead]
```

### Extension Limits

```
This approval has been extended twice.

To prevent indefinite delay:
• Maximum one more extension available
• Or: Decide now

[Final extension (+1 hour)] [Decide now] [Cancel action]
```

## Escalation Patterns

Use only with the independent disclosure/notification authority described above. Another timeout still leaves the original action blocked.

### Pre-Escalation Warning

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Approval will escalate in 2 hours                    │
│                                                         │
│ If you don't respond:                                   │
│ • This request will go to: manager@company.com          │
│ • They will see: Action summary and deadline context    │
│ • You will be CC'd on their decision                    │
│                                                         │
│ [Respond now] [Let it escalate] [Extend deadline]       │
└─────────────────────────────────────────────────────────┘
```

### Escalation Notification (to escalation target)

```
┌─────────────────────────────────────────────────────────┐
│ 🔔 Escalated approval request                           │
│                                                         │
│ From: alice@company.com (did not respond by deadline)   │
│                                                         │
│ Action: Send email to client@external.com               │
│ Context: Client follow-up on Q4 proposal                │
│ Original deadline: Oct 15, 3:00 PM                      │
│                                                         │
│ Your options:                                           │
│ [Approve] [Reject] [Return to Alice] [View full context]│
└─────────────────────────────────────────────────────────┘
```

### Escalation Notification (to original requester)

```
┌─────────────────────────────────────────────────────────┐
│ 📤 Approval escalated                                   │
│                                                         │
│ Your approval for [action] timed out.                   │
│ Escalated to: manager@company.com                       │
│                                                         │
│ You can still:                                          │
│ [Respond before they do] [Add context for them]         │
│                                                         │
│ You'll be notified when they decide.                    │
└─────────────────────────────────────────────────────────┘
```

## State Preservation

### What to Preserve on Timeout

| Component | Preserve? | Notes |
|-----------|-----------|-------|
| Draft artifact | Yes | User may want to complete later |
| User's edits | Yes | Don't lose their work |
| Context | Yes | Why this was created |
| Decision evidence | Yes | Preserve task rationale for renewed review, not private reasoning |
| Pending modifications | Yes | User's deselections, parameter changes |
| Approval history | Yes | Track record |

### Preserved State Display

```
┌─────────────────────────────────────────────────────────┐
│ 💾 Approval timed out - work preserved                  │
│                                                         │
│ What was saved:                                         │
│ ├── Draft email (in Drafts folder)                      │
│ ├── Your edits (subject line change)                    │
│ ├── Attachment (Q4_Report.xlsx)                         │
│ └── Context: Reply to client's Oct 10 message           │
│                                                         │
│ Resume:                                                 │
│ [Review and renew approval] [Edit authorized draft]      │
│                                                         │
│ Or start fresh:                                         │
│ [Revise request] [Cancel request; keep work]             │
└─────────────────────────────────────────────────────────┘
```

### State Recovery on Return

```
┌─────────────────────────────────────────────────────────┐
│ 📂 Returning to saved approval                          │
│                                                         │
│ This approval expired Oct 15 at 3:00 PM.                │
│ Your draft and edits were preserved.                    │
│                                                         │
│ Since then:                                             │
│ • Client has not followed up                            │
│ • No other emails in this thread                        │
│ • Original context still relevant                       │
│                                                         │
│ [Review and renew] [Review changes since] [Start over]   │
└─────────────────────────────────────────────────────────┘
```

## Timeout Rationale Patterns

### External Commitment

```
Deadline: Oct 15, 3:00 PM

Why: Client expects response by end of day.
     (Based on: "I'll get back to you by EOD" in your Oct 14 email)
```

### Internal Process

```
Deadline: Oct 15, 5:00 PM

Why: Invoice must be submitted before monthly close.
     (Finance deadline: Oct 15 5:00 PM)
```

### Inferred Urgency

```
Deadline: 1 hour from now

Why: Email is reply to message received 3 hours ago.
     Typical response time for this contact: 2 hours.
     (You can adjust this expectation in settings)
```

### Agent-Proposed

```
Deadline: Oct 16, 9:00 AM

Why: No specific deadline detected.
     Default: 24 hours for non-urgent approvals.
     (You can approve now, extend, or set custom deadline)
```

## Notification Channel Selection

Urgency guides presentation, never authority to contact additional recipients or channels. Use only independently authorized channels; otherwise report the pending decision locally.

| Urgency | Primary Channel | Fallback |
|---------|-----------------|----------|
| Non-urgent | In-app notification | Daily digest email |
| Moderate | Push notification | Email within 1 hour |
| Urgent | Push + SMS | Email + in-app alert |
| Critical | All channels simultaneously | Phone call escalation |

### User Preferences Override

```
Approval notifications:
├── Non-urgent: [In-app only ▾]
├── Moderate: [Push notification ▾]
├── Urgent: [Push + email ▾]
└── Critical: [All channels ▾]

Quiet hours: [10 PM - 8 AM ▾]
└── During quiet hours: [Queue until morning ▾]
```

## Edge Cases

### User Responds After Timeout

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ This approval has expired                            │
│                                                         │
│ Outcome: Unsent; authorized draft preserved              │
│ Expired: 2 hours ago                                    │
│                                                         │
│ You can still:                                          │
│ [Review and renew] [Edit authorized draft] [Keep paused] │
└─────────────────────────────────────────────────────────┘
```

### Escalation Target Also Times Out

```
Primary: alice@company.com (timed out)
Escalation: manager@company.com (also timed out)

Next action:
○ Request separate escalation authority for new recipient
○ Keep blocked; preserve already-authorized work
○ Cancel request; preserve authorized work

[Proceed]
```

### Conflicting Responses (User + Escalation Target)

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Conflicting responses                                │
│                                                         │
│ You: Approved (just now)                                │
│ manager@company.com: Rejected (10 minutes ago)          │
│                                                         │
│ Manager's rejection takes precedence per policy.        │
│                                                         │
│ Action was NOT executed.                                │
│                                                         │
│ [View manager's note] [Request override] [Accept]       │
└─────────────────────────────────────────────────────────┘
```

### Network Failure at Deadline

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Approval expired while offline                       │
│                                                         │
│ Deadline passed; action remains blocked.                │
│ Error: Network unavailable                              │
│                                                         │
│ Your approval expired; revalidate scope on return.      │
│ No automatic retry after expired authorization.         │
│                                                         │
│ [Review and renew approval] [Keep paused] [Cancel]       │
└─────────────────────────────────────────────────────────┘
```

## Timeout Configuration

### System Defaults

```
Default timeout by action type:
├── Email (internal): 24 hours → Block; preserve authorized state
├── Email (external): 12 hours → Block; preserve authorized state
├── Calendar (self): 4 hours → Block; preserve authorized state
├── Calendar (others): 12 hours → Block; preserve authorized state
├── Document edit: 24 hours → Block; preserve authorized state
├── Financial: No timeout → Must explicitly approve
└── Publishing: No timeout → Must explicitly approve
```

### User Customization

```
Your timeout preferences:

Email approvals:
├── Timeout: [24 hours ▾]
├── Default on timeout: Block; preserve authorized state
└── Escalate to: [None ▾]

Calendar approvals:
├── Timeout: [4 hours ▾]
├── Default on timeout: Block; preserve authorized state
└── Escalate to: [None; separate authority required ▾]

[Save preferences] [Reset to system defaults]
```
