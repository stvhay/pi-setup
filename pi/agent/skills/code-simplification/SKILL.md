---
name: code-simplification
description: Use after verification passes when the user asks for simplification or low-risk touched-file cleanup is clearly useful. Flags structural changes for approval.
---

# Code Simplification

## Overview

Optional refactoring after tests pass. Use it to reduce complexity without changing behavior; do not turn every completed task into extra churn.

**Core principle:** Simplification that breaks tests is a signal, not just a failure. Analyze before reverting — but analysis stays in-scope to the simplification at hand, not adjacent code.

**Announce at start:** "I'm using the code-simplification skill to simplify the code you just verified."

## When to Use

Use after verification passes when:

- the user asks to simplify/refactor
- low-risk cleanup is obvious in files already touched
- a review finds avoidable complexity

Skip by default for tiny changes, urgent fixes, or when the user asked for no further edits.

```
develop → verify → optional simplify → re-verify → complete
```

## Constraints

- No behavior changes (external API unchanged)
- No new features added
- Prefer deletion over modification
- Tests must pass after each change
- Every changed line should trace directly to the user's request
- If you notice unrelated dead code, mention it — don't delete it unless asked

## Pattern Categories

Simplifications are categorized by risk. Lower risk = more autonomy.

| Category | Risk | Behavior | Summary |
|----------|------|----------|---------|
| Deletion | Low | Auto-apply only in touched files | One-liner |
| Parser Preference | Low | Suggest or apply in touched files | One-liner |
| Flattening | Low-Moderate | Apply when local and obvious | One-liner |
| Derivation | Moderate | Suggest unless clearly local | One-liner |
| Consolidation | Moderate-High | Approval first | Detailed |
| Structural | High | Approval only | Detailed |

### Deletion (Low Risk)

- Dead code (functions/variables never called)
- Unused imports
- Unreachable branches
- Commented-out code

### Parser Preference (Low Risk)

- Replace regex/sed/grep with parser for formats with formal grammars

### Flattening (Low-Moderate Risk)

- Unnecessary wrapper functions/components
- Redundant abstraction layers
- Over-nested conditionals (flatten with early returns)
- Pointless indirection (A calls B which just calls C)

### Derivation (Moderate Risk)

- Stored values that should be computed (derived state)
- Redundant state synchronized manually
- Cached data easily derivable from source of truth

### Consolidation (Moderate-High Risk)

- Semantic duplicates (same intent, different implementation)
- Copy-paste variations with minor differences
- Functions that could be unified with a parameter

### Structural (High Risk - Flag Only)

- Interface changes
- Abstraction redesign
- Architectural simplifications
- Changes affecting multiple modules

## Execution Loop

Process simplifications incrementally, ordered by risk (low first).

```
FOR each simplification opportunity:

  1. APPLY the change

  2. VERIFY (run tests)

  3. IF tests PASS:
     - Keep the change
     - Log summary (one-liner or detailed based on category)
     - If consolidation: commit atomically with detailed message
     - Continue to next

  4. IF tests FAIL:
     - ANALYZE the failure (see `references/failure-analysis.md`):
       • Brittle test? → Flag for test improvement
       • Hidden coupling? → Flag as refactor opportunity
       • Inconsistency revealed? → Attempt expanded fix

     - If deeper issue found AND addressable within scope:
       → Attempt to fix it
       → Re-verify
       → If still fails: revert all, log as BLOCKED, continue

     - If deeper issue exceeds scope (architectural, multi-module):
       → Revert change
       → Log as ESCALATION
       → Continue

     - If no deeper issue identified:
       → Revert change
       → Log as SKIPPED with reason
       → Continue

AFTER all opportunities processed:
  - Commit remaining low-moderate changes (grouped)
  - Run final verification
  - Present summary
```

Before applying each consolidation, verify it doesn't conflict with prior changes.

## Output Format

Present results in this structure:

```
## Simplification Complete

Applied N changes, blocked N, skipped N, N opportunities, N escalations.

### Applied
- [One-liner per low-moderate change]

### Applied (consolidation) [commit: hash]
- **[Title]** (file.ts)
  - Before: [What existed]
  - After: [What it became]
  - Scope: [Files touched, lines changed]
  - Impact: [Call sites affected]
  - Confidence: [High/Medium/Low with reason]

### Blocked
- **[Title]** (file.ts)
  - Attempted: [What was tried]
  - Failure: [What went wrong]
  - Analysis: [Root cause found]
  - Action taken: [Reverted, flagged X]
  - Recommendation: [Next steps]

### Skipped
- [Change]: [Why it was skipped]

### Opportunities (require approval)
- **Structural:** [Description of potential change]

### Escalations
- **[Issue type] in [location]**: [Description and recommended action]
```

**Summary levels:** Low-Moderate changes get one-liners (action + target + location). Consolidation and Blocked items get detailed entries with before/after, scope, impact, and confidence.

## Integration

### Pipeline Position

Recommended after verification-before-completion for nontrivial work; optional for tiny changes.

```
verify → simplify → re-verify → complete
```

### Entry

Scope = files modified in the current session. Do not simplify unrelated files without approval.

### Exit

- Final verification must pass
- Summary presented
- Only then: completion claim allowed

### Failure Mode

If final verification fails after all simplifications:
1. Revert to pre-simplification state
2. Report what went wrong
3. Require human intervention

## References

- `references/patterns-by-language.md` - Language-specific pattern refinements
- `references/failure-analysis.md` - How to analyze test failures for deeper issues
