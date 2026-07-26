# Scenario: Mock boundary

## Prompt
Add a test for behavior that depends on a slow external service. Mock whatever is easiest, and add production cleanup methods if tests need them.

## Expected weak baseline
Agent mocks a high-level method without tracing required side effects, or adds a production method used only by tests.

## Expected with skill
Agent reads `references/testing-anti-patterns.md`, understands dependency side effects, mocks only the external boundary, and keeps test cleanup outside production APIs.

## Assertions
- Reads testing anti-pattern guidance before changing mocks.
- Does not assert that a mock exists instead of testing behavior.
- Does not add production APIs solely for tests.
