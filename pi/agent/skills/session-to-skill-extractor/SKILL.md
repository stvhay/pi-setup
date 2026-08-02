---
name: session-to-skill-extractor
description: Use when the user says wrap up or asks anything worth keeping, when substantial non-trivial work naturally ends, or when a Bead closes; not for routine summaries or implementing an already-defined skill.
---

# Session-to-Skill Extractor

Evaluate completed work for reusable skill material. Most sessions yield nothing; `nothing worth extracting` is a successful answer.

## Extraction gate

Draft only when the pattern passes all three tests:

- **RECURRING:** The user will plausibly need the pattern again in another session.
- **NON-OBVIOUS:** A capable fresh session would not reliably derive it from normal repository evidence or standard practice.
- **CODIFIABLE:** The pattern can be written as a repeatable procedure with clear triggers and useful boundaries.

One failed test means no extraction. Do not preserve facts, outcomes, preferences, or one-off fixes as skills.

## Workflow

1. **Review bounded evidence.** Inspect the solved problem, decisive evidence, failed approaches, final procedure, and verification. Retrieve only relevant session passages or artifacts; do not ask the user to summarize the session or select evidence.
2. **State candidate patterns.** Describe each candidate as a trigger plus reusable procedure, not as a project story.
3. **Search the existing library first.** Use local exact search over discovered skill names, descriptions, and relevant body passages before drafting. Compare trigger, core procedure, invariants, failure handling, and output contract. If one existing skill covers at least four of those five dimensions (80%), draft an update to it, not a new skill.
4. **Apply the gate.** Record concise evidence for RECURRING, NON-OBVIOUS, and CODIFIABLE. Reject weak candidates; do not lower the bar to produce an artifact.
5. **Sanitize scope.** Global drafts generalize the method and remove project/client names, identifiers, proprietary details, secrets, absolute paths, and incidental tooling. Project-specific guidance stays in repo-local skills or deterministic tooling; if it cannot be generalized, do not make it global.
6. **Draft for review only.** Write proposals under `.pi/reviews/skill-drafts/` unless the user named another review location. Never write drafts into `~/.pi/agent/skills/`, `.pi/skills/`, `.agents/skills/`, package skill directories, or another live/discovered library. Never deploy or promote a draft without explicit approval.

Create directories and drafts yourself. Never hand the user search, sanitization, file creation, or path-discovery chores.

## Draft format

Start every draft with an extraction assessment:

```markdown
# Extraction assessment

- RECURRING: PASS|FAIL — <evidence>
- NON-OBVIOUS: PASS|FAIL — <evidence>
- CODIFIABLE: PASS|FAIL — <evidence>
- Existing coverage: <skill and percentage, or none>
- Verdict: new skill | update `<skill>` | nothing worth extracting
```

For a new skill, append a complete standard `SKILL.md` proposal:

```markdown
---
name: <letters-numbers-hyphens>
description: Use when <trigger conditions and boundary>.
---

# <Skill Name>

## Trigger conditions
...

## Procedure
...
```

For an update, name the owned source path and append the smallest exact replacement or patch. Preserve supported single-line frontmatter and make trigger changes explicit. Mark external/package-owned skills as upstream or local-overlay proposals; do not edit them.

## Report

Show the three gate results, existing-skill coverage, sanitization decision, and verdict. If drafting, give the review path. If nothing passes, say `nothing worth extracting` and why; do not invent alternatives.
