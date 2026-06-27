---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass. Preserve all existing behavior unless the user explicitly asks to change it.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Violating the letter of the rules is violating the spirit of the rules.**

## When to Use

**Always:**
- New features
- Bug fixes
- Refactoring
- Behavior changes

**Exceptions (ask your human partner):**
- Throwaway prototypes
- Generated code
- Configuration files

Thinking "skip TDD just this once"? Stop. That's rationalization.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

Unrelated edits are not TDD. Do not delete or rewrite existing tests/functions unless the requested behavior requires it. Add the smallest new test, then the smallest production change. Every changed line must trace to the requested behavior.

**No exceptions:**
- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
- Delete means delete

Implement fresh from tests. Period.

## Spec-Anchored Tests

When the subsystem has a SPEC.md, anchor tests to spec item IDs:

- Each **INV-N** gets a positive test: `test_invN_description` — verifies the invariant holds
- Each **FAIL-N** gets a negative test: `test_failN_description` — verifies graceful handling

Add an inline comment on the test's declaration line for traceability:
`def test_inv1_total_equals_sum():  # Tests INV-1`

This doesn't change the red-green-refactor cycle — it tells you *what* to test.
The spec items are your test target list. Write the failing test for INV-1,
watch it fail, implement, watch it pass. Then INV-2. Then FAIL-1. And so on.

**Without a SPEC.md:** Write tests as you normally would — one behavior per test,
clear names, real code.

## Red-Green-Refactor

### RED - Write Failing Test

Write one minimal test showing what should happen.

```typescript
test('retries failed operations 3 times', async () => {
  let attempts = 0;
  const operation = () => {
    attempts++;
    if (attempts < 3) throw new Error('fail');
    return 'success';
  };

  const result = await retryOperation(operation);

  expect(result).toBe('success');
  expect(attempts).toBe(3);
});
```
Clear name, tests real behavior, one thing

**Requirements:**
- One behavior
- Clear name
- Real code (no mocks unless unavoidable)

### Verify RED - Watch It Fail

**MANDATORY. Never skip. Run the command with `bash` and read the output.**

```bash
npm test path/to/test.test.ts
```

Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

**Test passes?** You're testing existing behavior. Fix test.

**Test errors?** Fix error, re-run until it fails correctly.

### GREEN - Minimal Code

Write simplest code to pass the test.

```typescript
async function retryOperation<T>(fn: () => Promise<T>): Promise<T> {
  for (let i = 0; i < 3; i++) {
    try {
      return await fn();
    } catch (e) {
      if (i === 2) throw e;
    }
  }
  throw new Error('unreachable');
}
```
Just enough to pass

Don't add features, refactor other code, or "improve" beyond the test. The rule: every changed line traces to the user's request.

**Formal grammars:** Use parsers (not regex/sed) for any format with a formal grammar. Prefer existing project parsers or small purpose-built scripts over brittle text substitution.

### Verify GREEN - Watch It Pass

**MANDATORY. Run the command with `bash` and read the output.**

```bash
npm test path/to/test.test.ts
```

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix code, not test.

**Other tests fail?** Fix now.

### REFACTOR - Clean Up

After green only:
- Remove duplication
- Improve names
- Extract helpers

Keep tests green. Don't add behavior.

### Repeat

Next failing test for next feature.

## Good Tests

| Quality | Good | Bad |
|---------|------|-----|
| **Minimal** | One thing. "and" in name? Split it. | `test('validates email and domain and whitespace')` |
| **Clear** | Name describes behavior | `test('test1')` |
| **Shows intent** | Demonstrates desired API | Obscures what code should do |

Test-first is mandatory. Tests written after implementation don't prove they catch the bug.

## Example: Bug Fix

**Bug:** Empty email accepted

**RED**
```typescript
test('rejects empty email', async () => {
  const result = await submitForm({ email: '' });
  expect(result.error).toBe('Email required');
});
```

**Verify RED**
```bash
$ npm test
FAIL: expected 'Email required', got undefined
```

**GREEN**
```typescript
function submitForm(data: FormData) {
  if (!data.email?.trim()) {
    return { error: 'Email required' };
  }
  // ...
}
```

**Verify GREEN**
```bash
$ npm test
PASS
```

**REFACTOR**
Extract validation for multiple fields if needed.

## Report Format

When finished, include concrete evidence:

```markdown
## TDD Evidence

**RED:** `<command>` → failed as expected (`<key failure>`)
**GREEN:** `<command>` → passed (`<key output>`)
**Regression/full check:** `<command>` → passed/failed (`<key output>`)
**Changed files:** `<paths>`
```

If you did not observe RED, say so and do not claim TDD was completed.

## Verification Checklist

Before marking work complete:

- [ ] Existing tests and behavior preserved unless explicitly in scope
- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason (feature missing, not typo)
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered
- [ ] If SPEC.md exists: every INV-N has a positive test, every FAIL-N has a negative test, each with `# Tests INV-N` inline comment

Can't check all boxes? You skipped TDD. Start over.

## When Stuck

Test hard to write = design too coupled. Simplify interface or use dependency injection.

## Final Rule

```
Production code → test exists and failed first
Otherwise → not TDD
```

No exceptions without your human partner's permission.
