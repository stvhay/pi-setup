---
name: requesting-code-review
description: Use when completing tasks, implementing major features, before merging, or reviewing a diff/PR. Runs cold, cost-bounded, model-diverse review and verifies concrete findings against executable evidence.
---

# Requesting Code Review

Run model-diverse review without turning every reviewer into a long autonomous tool loop. Discovery peers receive complete embedded packets in cold one-shot calls; fresh verifiers inspect serious findings against the actual repository and tests.

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Non-negotiable rules

- Treat findings as hypotheses, not instructions.
- Do not use reviewer confidence, `NOT_SURE`, or reviewer consensus as an escalation trigger.
- Require a concrete location, violated behavior/invariant, failure scenario, and evidence.
- Verify Critical and Important findings against code plus a focused test, reproducer, specification, or profile.
- Use profiling for performance claims.
- Keep cloud packets free of secrets, credentials, private customer data, and unrelated proprietary context.
- Kimi K3 is never an automatic review target.

## Models and measured cost policy

Use `agnt route --task review` rather than inventing a fanout. Review task policy currently uses:

- **Fast cheap default:** `openrouter-localish/google/gemma-4-31b-it`.
- **Zero-marginal fallback/control:** `ollama/gemma4:31b`.
- **Coding-focused independent reviewer:** `olla-cloud/kimi-k2.7-code`, scoped and one-shot.
- **Cheap challenger/boundary reviewer:** `openrouter-localish/deepseek/deepseek-v4-flash`.
- **Manual unresolved-critical escalation only:** `olla-cloud/kimi-k3`.

Local repository evidence for OpenRouter Gemma is 43 invocations, $0.232 provider-reported total cost, 52-second median latency. Treat this as a local operating observation, not a universal benchmark. Gemma remains a diverse default; DeepSeek is measured as a challenger because code-generation benchmarks do not establish code-review quality.

`agnt route` measures month-to-date marginal review spend from OpenRouter plus catalog venues marked `billingClass: metered`; it excludes local compute and subscription-backed GPT opportunity cost. `AGNT_REVIEW_PAID_SPEND_USD` is an operator-supplied floor. Override from an authoritative provider dashboard when needed:

```bash
agnt route --task review --risk medium --budget balanced \
  --fanout-size 3 --monthly-paid-spend 7.40
```

Budget states:

- **Below $12:** normal risk policy; challenger sampling is allowed.
- **$12–$17.99:** stop optional shadow sampling.
- **$18–$19.99:** reserve mode; remove Kimi and use local Gemma plus DeepSeek as risk requires.
- **$20 or more:** hard cap; route only to local Gemma and report paid-budget exhaustion.

Set a provider-side cap as a backstop when the provider supports one.

## Determine scope and risk

Inspect a PR, working tree, or requested range:

```bash
git status --short
git diff --stat
git diff
```

If no working-tree diff exists, use the requested range or `git show HEAD`.

Classify risk from observable change facts before asking a model. High-risk triggers include:

- authentication, authorization, credentials, cryptography, or remote execution;
- billing, money, destructive data changes, migrations, backups, or persistence;
- concurrency, distributed state, retries, idempotency, or state machines;
- public APIs, protocols, schemas, installers, deployment, or user-environment mutation;
- changed behavior without focused tests; or
- a behavior segment too coupled to keep below roughly 150 changed lines.

Large line count is first a segmentation trigger, not proof that a frontier model is needed.

## Build complete behavior packets

Create one review directory:

```bash
ReviewId=$(date +%Y%m%d-%H%M%S)
ReviewDir=.pi/reviews/$ReviewId
mkdir -p "$ReviewDir"
git status --short > "$ReviewDir/status.txt"
git diff --stat > "$ReviewDir/diffstat.txt"
git diff > "$ReviewDir/diff.patch"
```

Segment by behavior, not file. Each packet should contain only what its reviewer needs:

1. review ID, scope, reviewer target, and family;
2. requirement, Bead, design, or plan excerpt;
3. exact relevant diff hunks;
4. changed function/class context and important callers/dependents;
5. relevant tests and verification output; and
6. the compact `finding-discoverer` contract plus required JSON schema path.

If `graphify-out/graph.json` exists, query significant changed symbols before packet assembly and paste the useful caller/dependent evidence into the packet. The graph reflects the last commit, so do not treat absence of newly added symbols as a finding.

A one-shot reviewer cannot read artifact paths. **Embed file contents in the packet**; do not merely say `diff: .pi/reviews/.../diff.patch`.

Use two scopes:

- **Behavioral:** requirements, preservation, errors, edge cases, and tests.
- **Boundary:** callers, dependencies, interfaces, schemas, persistence, concurrency, and security.

The tracked schema and example are:

```text
~/.pi/agent/skills/requesting-code-review/review-findings.schema.json
~/.pi/agent/skills/requesting-code-review/review-findings.example.json
```

## Run cold discovery passes

`--one-shot` disables tools, skills, context-file discovery, prompt templates, and session persistence. It also defaults to a 180-second subprocess timeout. This makes the packet the complete context, bounds stalled calls, and prevents tool-loop request multiplication.

Policy by risk:

- **Low:** OpenRouter Gemma behavioral pass.
- **Medium:** OpenRouter Gemma behavioral pass plus Kimi K2.7 boundary pass.
- **High:** Gemma behavioral, Kimi K2.7 boundary, and DeepSeek V4 Flash independent boundary/adversarial pass.
- **Reserve/hard cap:** use the targets returned by `agnt route`.

Example:

```bash
agnt invoke --one-shot --task review --risk-category medium \
  openrouter-localish/google/gemma-4-31b-it \
  "$ReviewDir/behavioral-packet.md" > "$ReviewDir/gemma-findings.json"

agnt invoke --one-shot --task review --risk-category medium \
  olla-cloud/kimi-k2.7-code \
  "$ReviewDir/boundary-packet.md" > "$ReviewDir/kimi-findings.json"
```

For parallel high-risk passes, use `agnt invoke --one-shot --fanout` with one complete packet per provider/model pair.

Validate every output before counting it:

```bash
agnt review validate "$ReviewDir/gemma-findings.json"
agnt review summary "$ReviewDir/gemma-findings.json"
```

Invalid JSON, stubs, generic advice, missing failure scenarios, or unsupported findings do not count as completed review. One concise format-repair retry is acceptable; do not fall back to an open-ended autonomous cloud agent merely to repair formatting.

## Fresh adversarial verification

Deduplicate discovery findings, then pass every Critical and Important candidate to a fresh GPT-family verifier using the `finding-verifier` role. The verifier may inspect the actual repository and run read-only/focused commands; it must try to refute the allegation.

Verification statuses:

- `confirmed` — code/spec plus executable or strong inspection evidence establishes the failure;
- `refuted` — caller, invariant, test, reproducer, or specification disproves it;
- `unresolved` — a concrete serious claim survives inspection but conflicting requirements or unavailable evidence prevent a decision;
- `unverified` — discovery only; never a promotion gate.

Validate the enriched artifact again. Do not implement a fix solely because several reviewers agree.

## Deterministic K3 escalation gate

A focused one-shot K3 call is permitted only when all conditions hold:

1. the finding maps to a predefined Critical impact category;
2. it includes a location, invariant/claim, and concrete failure scenario;
3. fresh adversarial verification attempted a test, reproducer, profile, inspection, or specification check;
4. the result remains `unresolved` for a stated external reason; and
5. the paid-review ledger is below the applicable budget threshold.

Send only the focused finding, relevant code/spec excerpts, and verification evidence. If budget is exhausted, record the unresolved risk and ask for a human decision rather than silently spending or silently passing.

## Record verified yield

Attach the structured findings to the discovery invocation metric:

```bash
agnt metrics annotate <recordId> \
  --findings-file "$ReviewDir/gemma-findings.json" \
  --outcome accepted
```

The annotation records review ID, scope, compact per-finding outcomes, and confirmed/refuted/unresolved counts. `agnt metrics status` reports verified findings and confirmed-findings-per-dollar by model when provider cost is available.

Use invocation outcomes consistently:

- `accepted` — substantive discovery output was retained for verification;
- `rejected` — hallucinated, vague, malformed, or unusable output;
- `verified-pass` — verifier refuted a candidate or established no defect;
- `verified-fail` — verifier confirmed a defect;
- `escalated` — a concrete unresolved serious item crossed an external gate.

Do not promote a model from SWE-Bench claims or raw agreement. Compare real confirmed unique findings, false positives, verification time, latency, and actual marginal cost. Use synthetic seeded defects only as an executable non-regression eval, not as the sole promotion basis.

## Report

Produce a concise summary:

```markdown
## Code Review Summary

**Review ID:** ...
**Reviewers/scopes:** ...
**Paid spend state:** normal | soft | reserve | hard-cap
**Verdict:** PASS | NEEDS_WORK | UNRESOLVED

### Confirmed
- `finding-id` — `file:line` — evidence and required action

### Refuted
- `finding-id` — decisive counterevidence

### Unresolved
- `finding-id` — missing/conflicting external evidence and escalation decision

### Cost and latency
- model — provider requests — elapsed — provider-reported/estimated cost
```

Post to GitHub only when the user asks. Do not auto-approve or request changes, and do not block local review on GitHub availability.
