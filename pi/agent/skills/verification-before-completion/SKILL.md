---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires fresh verification evidence before any success claim.
---

# Verification Before Completion

Evidence before claims. Do not say work is complete until fresh verification proves it.

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Iron law

No completion claims without fresh verification evidence from this session.

You must actually run the relevant shell commands with `bash` before reporting PASS/FAIL. If tools are unavailable, blocked, or you did not run commands, the verdict is `NOT VERIFIED`, not PASS or FAIL. Never infer command results from memory or expectations.

Avoid: "should pass", "looks good", "probably fixed", "done" before verification.

## Gate function

Before claiming success:

1. **Identify proof** — find the command(s) that prove the claim.
   - Check `CONTRIBUTING.md`, `README.md`, `package.json`, `pyproject.toml`, `Makefile`, CI config.
   - Use `rg -n "test|lint|typecheck|quality|verify|ci" README.md CONTRIBUTING.md docs package.json pyproject.toml Makefile .github 2>/dev/null || true`.
2. **Run fresh** — execute the full relevant command with `bash`, not a stale or partial run.
3. **Read output** — check exit code, failures, warnings, skipped tests.
4. **Compare to claim** — if evidence does not prove the claim, state actual status and gaps.
5. **Only then claim** — include the command and result in the response.

## Common proof commands

Use project-specific commands when available. Otherwise infer carefully:

```bash
npm test
npm run lint
npm run typecheck
pytest
uv run pytest
cargo test
go test ./...
make test
```

## Diff and requirement check

Fresh verification also includes checking what changed:

```bash
git status --short
git diff --stat
git diff --check
```

Then map changes to requirements/plan:

- Re-read the user request or plan.
- Create a short checklist.
- Verify each item against code/tests/docs.
- Report any gaps honestly.

## SPEC.md invariant check

If modified files live under a subsystem with `SPEC.md`:

1. Find nearest specs:
   ```bash
   find . -name SPEC.md -print
   ```
2. For relevant specs, check changed code against invariants/failure modes.
3. If tests use inline markers like `# Tests INV-N`, verify coverage with `rg "Tests (INV|FAIL)-"`.
4. Flag stale or missing spec coverage; do not invent certainty.

## Optional peer review

For risky changes, use a peer before final claim:

```bash
~/.pi/agent/bin/agnt invoke --fanout -o .pi/peer-runs/verify-<topic> \
  "Review this diff for missed requirements or risks. Focus on concrete issues."
```

Include relevant files/diff paths rather than pasting huge context. Synthesize peer output yourself; do not trust it blindly.

After synthesis, label each peer invocation so routing learns from the outcome (`verified-pass` when the peer's assessment matched the evidence, `verified-fail` when it did not):

```bash
~/.pi/agent/bin/agnt metrics annotate <metrics-file-basename-or-recordId> --outcome verified-pass
```

## Code simplification

After verification passes and before final completion, consider `code-simplification` for non-trivial code changes. Re-run verification after any simplification.

## Report format

```markdown
## Verification

**Commands run:**
- `<command>` → PASS/FAIL (<key output>)

**Diff checks:**
- `git diff --check` → PASS/FAIL
- `git status --short` → <summary>

**Requirement check:**
- [x] <requirement> — evidence
- [ ] <gap> — what remains

**Verdict:** PASS / FAIL / PARTIAL
```

If verdict is not PASS, do not claim completion.
