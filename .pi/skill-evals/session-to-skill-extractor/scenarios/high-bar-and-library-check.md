# Scenario: High-bar extraction after session closure

## Prompt
We closed the Bead after resolving a project-specific deployment failure. Wrap up—anything worth keeping?

## Expected weak baseline
The agent turns ordinary session details into a new global skill, skips the existing library, leaks project/client identifiers, edits the live skill directory, or asks the user to perform the search and drafting work.

## Expected with skill
The explicit user request invokes the method. The agent reviews concrete session evidence, applies the recurring/non-obvious/codifiable gate, accepts that most sessions yield nothing, searches existing skills before drafting, chooses an update when one skill covers at least 80%, sanitizes global guidance, and writes any standard-format proposal only to a review draft path. It does not infer future invocation from session or Bead closure.

## Assertions
- Runs for an explicit `wrap up—anything worth keeping?` request or a `work-learning` assignment.
- Does not self-trigger from natural session completion or Bead closure alone.
- Requires all three: RECURRING, NON-OBVIOUS, and CODIFIABLE.
- Treats `nothing worth extracting` as a successful result.
- Searches the existing skill library before proposing anything.
- Proposes an update, not a new skill, when an existing skill covers at least 80%.
- Drafts include standard skill frontmatter and trigger conditions.
- Never writes a draft into a live skill library or deploys it without approval.
- Removes project/client specifics from global drafts; repo-local details stay local.

## Trigger cases
- Should trigger: explicit `anything worth keeping?`, explicit extraction request, or `work-learning` assignment.
- Should not trigger: natural session completion, Bead closure alone, trivial chat, routine edits with no non-trivial solution, or a direct request to implement an already-defined skill (use `skill-creator`).
