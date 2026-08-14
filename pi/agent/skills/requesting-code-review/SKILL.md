---
name: requesting-code-review
description: Use when reviewing a diff or PR, finishing substantial implementation, or preparing to merge.
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

Use `agnt route --task review --access self-contained` for complete discovery packets. Use `--access repository` for filesystem verifiers rather than inventing mode or fanout policy. Review task policy uses:

- **Subscription-backed default:** `openai-codex/gpt-5.6-terra` at high thinking.
- **Medium-risk diversity:** `openrouter/moonshotai/kimi-k2.7-code`, scoped and one-shot.
- **High-risk independent reviewer:** `openrouter/anthropic/claude-opus-5`, scoped and one-shot; human adjudication remains required for consequential findings.
- **Manual unresolved-critical escalation only:** `openrouter/moonshotai/kimi-k3`.
- **Canary only:** `openrouter/minimax/minimax-m3` until accepted-output evidence supports promotion.

Kimi K3 is never an automatic review target. Every metered OpenRouter reviewer runs in a fresh worker; never switch a long-running root conversation to it. Self-contained discovery uses a bounded complete packet. Repository access requires agentic mode and route-generated justification, estimate, budget, and limits. Only tracked Codex and OpenRouter routes are configured.

`agnt route` measures month-to-date marginal review spend from OpenRouter, configured metered venues, and positive provider-reported retired venues; it excludes configured subscription targets. `AGNT_REVIEW_PAID_SPEND_USD` is an operator-supplied floor. Override from an authoritative provider dashboard when needed:

```bash
agnt route --task review --risk medium --budget balanced \
  --access self-contained --fanout-size 3 --monthly-paid-spend 7.40
```

Budget states:

- **Below $12:** normal Codex-first risk policy; scoped diversity passes are allowed.
- **$12–$17.99:** stop optional shadow sampling.
- **$18–$19.99:** reserve mode; use subscription-backed Terra only.
- **$20 or more:** hard-cap mode; keep subscription-backed Terra only and report paid-budget exhaustion.

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

Follow the shared evidence-complete packet contract. A reviewer should decide from primary evidence without transcript access or a second evidence-finding model call.

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
2. objective, current decision, and requirement, Bead, design, or plan excerpt;
3. exact source-of-truth paths, symbols, commands, and relevant diff hunks;
4. changed function/class context and important callers/dependents;
5. relevant external contract evidence, tests, verification target, and verification output;
6. constraints, stop conditions, and the compact `finding-discoverer` contract plus required output schema path.

If `graphify-out/graph.json` exists, query significant changed symbols before packet assembly. Give agentic reviewers exact graph/source retrieval commands; embed useful caller/dependent excerpts only for one-shot reviewers. The graph reflects the last commit, so do not treat absence of newly added symbols as a finding.

Agentic reviewers retrieve repository evidence from exact filesystem paths and commands. A one-shot reviewer cannot read artifact paths: embed bounded source excerpts in its packet instead of merely saying `diff: .pi/reviews/.../diff.patch`. Embed external evidence only when the worker cannot retrieve it.

Use two scopes:

- **Behavioral:** requirements, preservation, errors, edge cases, and tests.
- **Boundary:** actual caller, loader, and runtime contract plus dependencies, interfaces, schemas, persistence, concurrency, and security. Include their primary evidence whenever the conclusion depends on that boundary.

The tracked schema and example are:

```text
~/.pi/agent/skills/requesting-code-review/review-findings.schema.json
~/.pi/agent/skills/requesting-code-review/review-findings.example.json
```

## Run cold discovery passes

Subagent `mode: "one-shot"` disables tools and ambient project context. A 300-second child limit bounds stalled calls without cutting off otherwise-healthy slower reviews; one provider request is intrinsic, so do not add a redundant `maxProviderRequests` cap. Reuse the calibrated response contract in every discovery packet: report at most two concrete findings and return at most 6,000 characters. This keeps final JSON below the deliberate 16,384-token metered output ceiling without weakening review evidence.

Do not add a low ad hoc `maxOutputTokens` cap for structured review JSON. Provider output allowance can include reasoning before visible final output, so a 5,000-token ceiling does not safely guarantee a shorter JSON response. Keep subscription-backed discovery uncapped; retain the tracked metered wrapper ceiling. Use an explicit lower cap only for a bounded experiment or known spend/risk boundary, and record any resulting `output-limit` as a caller limit rather than a provider or network failure.

Policy by risk:

- **Low:** subscription-backed Terra behavioral pass.
- **Medium:** Terra behavioral pass plus one fresh Kimi K2.7 Code diversity pass.
- **High:** Terra at extra-high thinking plus one fresh Opus 5 boundary/adversarial pass; human adjudicates consequential findings.
- **Reserve/hard cap:** use the subscription-backed Terra target returned by `agnt route`.

Send one `subagent` call. Use `task` for one pass or `tasks` for parallel passes. Each task embeds one complete packet and sets:

```json
{
  "model": "<routed-provider/model>",
  "mode": "one-shot",
  "thinking": "<routed-thinking-level>",
  "sourceAccess": "self-contained",
  "limits": {"maxDurationMs": 300000},
  "outputContract": "inline"
}
```

Save each returned child output under `$ReviewDir` before validation. Metered self-contained discovery must use one-shot mode; the Archimedes wrapper applies the configured provider output cap.

### Recover persisted output before retrying

When inline output is truncated or malformed and the tool result reports a persisted `runtime:delegated-results/<invocation-id>/child-<index>.json` reference, inspect that artifact before another provider call:

1. Run `agnt runtime-path delegated-results` to resolve the existing private root.
2. Use the read tool on the exact referenced invocation and child suffix under that root; do not invent another URI or storage path.
3. Require a JSON object with `schemaVersion: 1`, an invocation ID and child index match the reference, and a non-empty `finalOutput`.
4. Save recovered `finalOutput` under `$ReviewDir`, then validate it normally.

Complete valid persisted output finishes that pass with zero reviewer retries. Only resolution, read, schema, identity, or usable-output failure permits the one concise format-repair retry below; missing or unavailable artifact metadata is such a failure.

Validate every output before counting it; validation and summary share one payload:

```bash
agnt review validate "$ReviewDir/kimi-findings.json"
```

Invalid JSON, stubs, generic advice, missing failure scenarios, or unsupported findings do not count as completed review. One concise format-repair retry is acceptable; do not fall back to an open-ended autonomous cloud agent merely to repair formatting.

## Fresh adversarial verification

Deduplicate discovery findings, then pass every Critical and Important candidate to a fresh GPT-family verifier using the `finding-verifier` role. The verifier may inspect the actual repository and run read-only/focused commands; it must try to refute the allegation.

Verification statuses:

- `confirmed` — code/spec plus executable or strong inspection evidence establishes the failure;
- `refuted` — caller, invariant, test, reproducer, or specification disproves it;
- `unresolved` — a concrete serious claim survives inspection but conflicting requirements or unavailable evidence prevent a decision;
- `unverified` — discovery only; never a promotion gate.

Route fresh filesystem verifiers with `agnt route --task review --access repository`. Repository access requires agentic mode. Prefer the qualified subscription-backed target and keep the 300-second liveness bound, but omit request, token, and cost caps: deep repository inspection may require many healthy turns. Add a request cap only for an explicit bounded experiment or identified runaway risk, and record it as a caller limit. A metered repository verifier is exceptional: use only route-emitted `quality-benefit` or `missing-capability` evidence and copy its estimate plus bounded limits exactly; parallel calls also copy the top-level aggregate budget.

```json
{
  "model": "<routed-subscription-provider/model>",
  "mode": "agentic",
  "sourceAccess": "repository",
  "limits": {"maxDurationMs": 300000},
  "outputContract": "inline"
}
```

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
  --findings-file "$ReviewDir/kimi-findings.json" \
  --outcome accepted
```

The annotation records review ID, scope, compact per-finding outcomes, and confirmed/refuted/unresolved counts. `agnt metrics status` reports verified findings and confirmed-findings-per-dollar by model when provider cost is available.

Use invocation outcomes consistently:

- `accepted` — substantive discovery output was retained for verification;
- `rejected` — hallucinated, vague, malformed, or unusable output;
- `verified-pass` — verifier refuted a candidate or established no defect;
- `verified-fail` — verifier confirmed a defect;
- `escalated` — a concrete unresolved serious item crossed an external gate.

Do not promote a model from SWE-Bench claims or raw agreement. Compare finding yield and verifier-call count with the prior workflow, alongside real confirmed unique findings, false positives, verification time, latency, and actual marginal cost. Use synthetic seeded defects only as an executable non-regression eval, not as the sole promotion basis.

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
