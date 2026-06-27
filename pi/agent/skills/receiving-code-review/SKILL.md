---
name: receiving-code-review
description: Use when receiving human, GitHub, or model-generated code review feedback. Evaluate feedback technically before implementing; verify each fix with focused tests.
---

# Receiving Code Review

Treat review feedback as hypotheses to verify, not orders to obey. This applies especially to model-diverse peer reviews: gemma/qwen/deepseek/gpt outputs are useful leads, but they can hallucinate.

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Response pattern

1. **Read all feedback** before reacting.
2. **Group items** by severity and affected file/subsystem.
3. **Verify against code** using `rg`, `git diff`, tests, and exact paths.
4. **Classify each item:** valid / invalid / needs clarification / already fixed.
5. **Implement valid fixes one at a time.**
6. **Run focused verification after each fix**, then broader verification before completion.
7. **Respond with evidence**, not performative agreement.

Always produce a final response. Do not silently edit files and stop.

## No performative agreement

Avoid:

- "You're absolutely right"
- "Great point"
- "Thanks for catching that"
- blind implementation before checking

Use:

- "Verified: this is valid because ..."
- "Not applying: current code does X, so the finding does not apply."
- "Need clarification: item 3 conflicts with ..."
- or just implement and show evidence.

## Handling model-diverse review output

When feedback comes from `requesting-code-review` peer outputs:

1. Read all files in `.pi/reviews/<topic>/`.
2. Deduplicate findings.
3. Prioritize findings reported by multiple model families, but do not assume convergence means correctness.
4. For each serious finding, inspect the exact file/path and reproduce if possible.
5. Discard findings with no code evidence.
6. If reviewers disagree, state the trade-off and ask the user only when the choice is architectural/product-level.

Useful commands:

```bash
find .pi/reviews -maxdepth 3 -type f | sort
rg -n "Critical|Important|Verdict|NEEDS_WORK|NOT_SURE" .pi/reviews
rg -n "<symbol or file from feedback>" . --glob '!node_modules' --glob '!vendor'
git diff -- <path>
```

## YAGNI check

If feedback asks to "implement properly" or add a feature:

```bash
rg -n "<API/function/endpoint>" . --glob '!node_modules' --glob '!vendor'
```

If nothing uses it, ask whether to remove/defer instead of expanding scope.

## Implementation order

For multi-item feedback:

1. Clarify blocking ambiguities first.
2. Fix Critical issues.
3. Fix simple Important issues.
4. Fix complex Important issues.
5. Batch Minor cleanup only if safe and in scope.

Each fix should be small enough to review in `git diff`.

## Verification and response format

For each accepted item:

```markdown
- [x] <review item> — fixed in `file:line`; verified with `<command>`
- [ ] <review item> — not fixed because <reason/blocker>
```

Before claiming completion, use `verification-before-completion`.

Final response format:

```markdown
## Review Feedback Response

**Applied:**
- <item> — changed `file:line`; verified with `<command>`

**Rejected / deferred:**
- <item> — reason

**Verification:**
- `<command>` → PASS/FAIL (`<key output>`)
```

## GitHub replies

If feedback came from PR comments and the user wants replies posted, reply with concise evidence. Prefer thread replies for inline comments when comment IDs are available; otherwise use a top-level summary comment.

```bash
gh pr comment <N> --body-file .pi/reviews/<topic>/response.md
```

Do not auto-resolve/approve/request-changes unless the user explicitly asks.

## Bottom line

Technical correctness over social comfort. Verify, then fix or push back with evidence.
