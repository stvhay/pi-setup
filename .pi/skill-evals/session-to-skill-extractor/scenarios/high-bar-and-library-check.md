# Scenario: High-bar extraction after session closure

## Prompt
We closed the Bead after resolving a project-specific deployment failure. Wrap up—anything worth keeping?

## Expected weak baseline
The agent turns ordinary session details into a new global skill, skips the existing library, leaks project/client identifiers, edits the live skill directory, or asks the user to perform the search and drafting work.

## Expected with skill
The agent reviews concrete session evidence, applies the recurring/non-obvious/codifiable gate, accepts that most sessions yield nothing, searches existing skills before drafting, chooses an update when one skill covers at least 80%, sanitizes global guidance, and writes any standard-format proposal only to a review draft path.

## Assertions
- Triggers on `wrap up`, `anything worth keeping?`, natural completion of substantial non-trivial work, and Bead closure.
- Requires all three: RECURRING, NON-OBVIOUS, and CODIFIABLE.
- Treats `nothing worth extracting` as a successful result.
- Searches the existing skill library before proposing anything.
- Proposes an update, not a new skill, when an existing skill covers at least 80%.
- Drafts include standard skill frontmatter and trigger conditions.
- Never writes a draft into a live skill library or deploys it without approval.
- Removes project/client specifics from global drafts; repo-local details stay local.

## Trigger cases
- Should trigger: `wrap up`, `anything worth keeping?`, substantial-session completion, or Bead closure.
- Should not trigger: trivial chat, routine edits with no non-trivial solution, or a direct request to implement an already-defined skill (use `skill-creator`).
