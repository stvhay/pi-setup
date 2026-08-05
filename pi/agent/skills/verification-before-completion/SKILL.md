---
name: verification-before-completion
description: Use before claiming work complete, fixed, or passing, and before commits or PRs, to require fresh verification evidence.
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

## Verification phases

### Baseline once

At work-item or worktree start, run the documented relevant matrix once and record command, exit status, failing test identity, and failure signature. Reuse that evidence during repair; do not repeat an unchanged broad baseline to rediscover the same failure.

### Focused repair

After a test, review, simplification, or documentation fix, run the smallest executable check that proves the repaired behavior and affected neighbors. A failed focused check permits one focused repair and rerun. Widen checks only when the change widens or evidence points outside the original surface.

### Final candidate gate

When tracked task changes are stable, run every required full release command once. A tracked final-candidate change invalidates the final gate and requires one new complete gate for that new candidate. Do not substitute focused checks for this gate.

### Unchanged baseline failures

Classify a failure as an unchanged baseline failure only when baseline and final evidence show the same command, test identity, and failure signature. Report task regression and release readiness separately. Example: `task regression: PASS`; `release verdict: NOT VERIFIED`. Never convert a red required gate into PASS.

## Gate function

Before claiming success:

1. **Identify phase and proof** — baseline, focused repair, or final candidate gate; find commands that prove that phase's claim.
   - Check `CONTRIBUTING.md`, `README.md`, `package.json`, `pyproject.toml`, `Makefile`, CI config.
   - Use `rg -n "test|lint|typecheck|quality|verify|ci" README.md CONTRIBUTING.md docs package.json pyproject.toml Makefile .github 2>/dev/null || true`.
2. **Run fresh** — execute the selected command with `bash`; use the complete required matrix for the final candidate gate.
3. **Read output** — check exit code, failures, warnings, skipped tests, and baseline signatures.
4. **Compare to claim** — separate task regressions from unchanged baseline failures; state actual status and gaps.
5. **Only then claim** — include phase, command, and result in the response.

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

For risky changes, route a review target, then call `subagent` with `agent` omitted:

```bash
~/.pi/agent/bin/agnt route --task review --risk medium --budget balanced
```

```json
{
  "task": "Review this diff for missed requirements or risks. Focus on concrete issues and exact file references.",
  "model": "<selected routed target>",
  "cwd": "<repository>"
}
```

Include relevant files/diff paths rather than pasting huge context. Synthesize peer output yourself; do not trust it blindly.

After synthesis, label each generated metric record so routing learns from the outcome (`verified-pass` when the peer's assessment matched the evidence, `verified-fail` when it did not):

```bash
~/.pi/agent/bin/agnt metrics annotate <metrics-file-basename-or-recordId> --outcome verified-pass
```

## Code simplification

After focused verification passes and before final completion, consider `code-simplification` for non-trivial code changes. Run focused repair checks after any simplification, then run the final candidate gate once changes stabilize.

## Report format

```markdown
## Verification

**Baseline once:**
- `<command>` → PASS/FAIL (<recorded failure signatures or clean>)

**Focused repair:**
- `<command>` → PASS/FAIL (<behavior proved>)

**Final candidate gate:**
- `<complete command matrix>` → PASS/FAIL (<key output>)

**Unchanged baseline failures:**
- `<none or exact command/test/signature comparison>`

**Commands run:**
- `<command>` → PASS/FAIL (<key output>)

**Diff checks:**
- `git diff --check` → PASS/FAIL
- `git status --short` → <summary>

**Requirement check:**
- [x] <requirement> — evidence
- [ ] <gap> — what remains

**Task regression verdict:** PASS / FAIL / NOT VERIFIED
**Release verdict:** PASS / NOT VERIFIED
```

If task regression verdict is not PASS, do not claim task completion. If release verdict is not PASS, do not claim release readiness.
