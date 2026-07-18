---
name: requesting-code-review
description: Use when completing tasks, implementing major features, before merging, or reviewing a diff/PR. Runs model-diverse Pi peer reviews with emphasis on local models such as gemma4 and qwen, then synthesizes actionable findings.
---

# Requesting Code Review

Request a model-diverse review of local changes or a PR. Prefer concrete diffs and filesystem paths over pasted context.

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Core idea

Use multiple reviewers with different failure modes. Generate reviewer prompt context from the shared role package instead of duplicating reviewer instructions in this skill:

```bash
~/.pi/agent/bin/agnt instructions --role code-reviewer --context provider/model
```

Use `agnt route --task review --risk <level> --budget <cheap|balanced|quality>` to select candidates, or use these curated defaults:

- **Large reviewer:** `ollama/gemma4:31b` or faster `openrouter-localish/google/gemma-4-31b-it`.
- **Fast pragmatic reviewer:** `olla-local/qwen3:8b` or faster `openrouter-localish/qwen/qwen3.5-9b`.
- **Small/fast second perspective:** `olla-local/gemma4:e4b` when available.
- **Reasoning reviewer when useful:** `olla-local/deepseek-r1:14b` or `openrouter-localish/deepseek/deepseek-r1-distill-qwen-32b` for tricky logic/security/root-cause reviews.
- **Cheap cloud tie-breaker when useful:** `olla-cloud/gpt-4.1-mini` for external diversity or disagreement.
- **Coding-focused independent reviewer:** `olla-cloud/kimi-k2.7-code` for ordinary GPT-authored changes.
- **Frontier independent reviewer:** `olla-cloud/kimi-k3` at max effort for high-risk, repository-scale, visual, or cross-domain changes.

Prefer reviewer independence from the authoring model family over diversity for its own sake. Use GPT-5.6 Sol for Kimi-authored changes; use Kimi K2.7 Code for medium-risk GPT-authored changes; and pair GPT-5.6 Sol with Kimi K3 for high-risk changes. For low-risk work, one cheap/local reviewer is enough. Prefer local models when fast enough and use OpenRouter localish equivalents when materially faster or local models are unavailable. Do not run every reviewer every time. Opportunistically include Kimi in real reviews and annotate its outcomes, but do not create synthetic review work solely to generate metrics.

## Inputs

Determine review scope:

1. If user gives a PR number, inspect it with `gh pr view <N>` and `gh pr diff <N>` if available.
2. Else review local changes:
   ```bash
   git status --short
   git diff --stat
   git diff
   ```
3. If no working-tree diff exists, review the most recent commit or a requested range:
   ```bash
   git show --stat --oneline HEAD
   git show HEAD
   ```

For large diffs, write artifacts instead of pasting huge text:

```bash
mkdir -p .pi/reviews
ReviewDir=.pi/reviews/$(date +%Y%m%d-%H%M%S)
mkdir -p "$ReviewDir"
git diff --stat > "$ReviewDir/diffstat.txt"
git diff > "$ReviewDir/diff.patch"
git status --short > "$ReviewDir/status.txt"
```

If `graphify-out/graph.json` exists, also generate structural impact context: small local peers will not reliably query the graph themselves, so run the queries here and ship the result as an artifact. For each significant changed function/file (use short keyword labels):

```bash
if [ -f graphify-out/graph.json ]; then
  for sym in <key changed symbols/files from diffstat>; do
    ~/.pi/agent/bin/agnt graphify explain "$sym" >> "$ReviewDir/graph-impact.txt"
  done
fi
```

## Review prompt construction

Build peer prompts from three small pieces:

1. Role context:
   ```bash
   agnt instructions --role code-reviewer --context provider/model
   ```
2. Review scope: repo path, diff/PR/range, requirement or plan path.
3. Artifact paths: `diffstat.txt`, `diff.patch`, `status.txt`, `graph-impact.txt` (when generated), or PR diff files. When including `graph-impact.txt`, label it: "callers/dependents of changed code from the project knowledge graph; built at the last commit, so symbols added by this diff are absent."

A reusable template remains at `code-reviewer.md`, but the role package is the source of truth for reviewer stance and output contract.

## Small/local review

For low-risk diffs, one local/near-local reviewer is sufficient. Add a second reviewer when the change is medium-risk or an independent family would materially reduce correlated blind spots:

```bash
mkdir -p .pi/reviews/current
PROMPT="$(cat <<'EOF'
<generated code-reviewer role context>

Review scope: local working-tree diff.
Diff artifacts: .pi/reviews/current/diff.patch if present.
EOF
)"
~/.pi/agent/bin/agnt invoke openrouter-localish/google/gemma-4-31b-it "$PROMPT" > .pi/reviews/current/gemma4-31b.md
```

For medium-risk GPT-authored changes, add `olla-cloud/kimi-k2.7-code`; for Kimi-authored changes, add `openai-codex/gpt-5.6-sol`. If OpenRouter is unavailable, use `ollama/gemma4:31b`, `olla-local/qwen3:8b`, or `olla-local/gemma4:e4b`.

## Larger/riskier review

For larger or riskier diffs, use fan-out. Ensure at least one reviewer family differs from the author; for high-risk work, include both GPT-5.6 Sol and Kimi K3 when available, then add cheap/local perspectives as useful:

```bash
printf '%s\n' "<generated code-reviewer role context plus exact diff artifact paths>" > .pi/reviews/<topic>/prompt.md
~/.pi/agent/bin/agnt invoke --fanout \
  -o .pi/reviews/<topic> \
  openai-codex/gpt-5.6-sol .pi/reviews/<topic>/prompt.md \
  olla-cloud/kimi-k3 .pi/reviews/<topic>/prompt.md \
  openrouter-localish/google/gemma-4-31b-it .pi/reviews/<topic>/prompt.md
```

For tricky algorithmic/security issues, add:

```bash
add `olla-local/deepseek-r1:14b .pi/reviews/<topic>/prompt.md` to the fanout pairs
```

## Stub / non-substantive output fallback

Before synthesis, scan peer outputs. A review is not usable if it only says it will inspect files later, cannot access artifacts, summarizes the prompt, or gives generic advice with no file/path/diff evidence.

If any peer returns a stub or other non-substantive output:

1. Do not count it as a completed review.
2. Annotate the invocation as rejected when a metrics record is available.
3. Rerun that peer with the diff embedded, a smaller pasted excerpt, or clearer artifact paths; or switch to another reviewer.
4. Record the failed invocation and rerun in the review summary.

For large diffs where artifact-path review fails, produce a smaller focused prompt:

```bash
sed -n '1,240p' .pi/reviews/<topic>/diff.patch > .pi/reviews/<topic>/diff-excerpt.patch
```

Then rerun with the excerpt or with a targeted `git diff -- <path>` for the risky files.

## Synthesis

After peer outputs complete:

1. Read all peer outputs from `.pi/reviews/...`.
2. Deduplicate findings.
3. Verify each serious finding against the actual code/diff before reporting.
4. Discard hallucinated findings with no file/path evidence.
5. Record reviewer outcomes so routing learns which models give usable reviews. For each peer whose findings you kept or discarded:

   ```bash
   ~/.pi/agent/bin/agnt metrics annotate <metrics-file-basename-or-recordId> --outcome accepted   # findings verified and used
   ~/.pi/agent/bin/agnt metrics annotate <metrics-file-basename-or-recordId> --outcome rejected   # findings hallucinated/unusable
   ```

   Metric files for the run are in `.pi/metrics/invocations/` (and the fanout `-o` directory). This is the routing self-improvement signal; do not skip it. When annotating several outputs from one review, first list recent records so each outcome is deliberate:

   ```bash
   ls -1t .pi/metrics/invocations/*.metrics.json | head -20
   ```
6. Produce a concise review:

```markdown
## Code Review Summary

**Reviewers:** gemma4:31b, qwen3:8b, ...
**Scope:** <diff/range/PR>
**Verdict:** PASS | NEEDS_WORK | NOT_SURE

### Critical
- <issue> — `file:line` — evidence/fix

### Important
- <issue> — `file:line` — evidence/fix

### Minor
- <issue> — `file:line` — evidence/fix

### Disagreements / discarded findings
- <finding> — discarded because <reason>
```

## GitHub PR posting

If a PR exists and the user wants the review posted, use `gh pr comment` with the synthesized review. Do not auto-approve or request changes unless the user explicitly asks.

```bash
gh pr comment <N> --body-file .pi/reviews/<topic>/summary.md
```

## Rules

- Model output is evidence to investigate, not truth.
- Verify serious findings yourself before reporting them as real.
- Prefer local model diversity first; use cloud as tie-breaker or for high-stakes review.
- Do not paste huge diffs into chat; write diff artifacts and point peers at paths.
- Do not block on GitHub. Local review is still useful without a PR.
