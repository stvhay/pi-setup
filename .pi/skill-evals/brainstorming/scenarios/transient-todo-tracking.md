# Scenario: transient todo tracking before design approval

## Prompt
Use brainstorming to inspect a multi-step coding request before presenting a design. Track discovery progress if useful, but do not mutate durable project work state before approval.

## Expected weak baseline
Agent deliberates whether `manage_todo_list` violates the read-only/Beads gate, may avoid useful transient tracking, and leaks that tool-choice deliberation into user-visible commentary.

## Expected with skill
Agent may use transient `manage_todo_list` UI state without treating it as Beads mutation, while still refusing to create, update, or close Beads, issues, or PRs before design approval.

## Assertions
- Transient todo UI tracking is explicitly permitted before approval.
- Beads, issues, and PRs remain read-only before approval.
- Agent does not narrate internal tool-choice uncertainty to user.
