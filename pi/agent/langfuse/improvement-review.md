# Improvement Review Rubric

Use this rubric only with a private `agnt improve scan` packet. Human review or an explicitly approved local/self-hosted reviewer classifies evidence; deterministic signals do not establish causality. Do not send packet content to another provider without explicit authorization.

## Decision format

Return JSON with `schemaVersion`, matching `reportId` and `reviewPolicyVersion`, ISO `reviewedAt`, and reviewed `sessions`. Each session has:

- `sessionId`: exact private packet session ID.
- `decision`: `no-action`, `actions-created`, `needs-human`, or `excluded`.
- `findings`: zero or more findings. `actions-created` requires at least one.

Each finding requires:

- `findingId`: `finding-` plus 12 lowercase hexadecimal characters.
- `category`: `coordination-error`, `expected-error`, `infrastructure`, `model-mismatch`, `prompt-targeting`, `token-inefficiency`, `tool-use-error`, `verification-gap`, or `unknown`.
- `errorRelevance`: `relevant`, `contributing`, `expected`, `recovered`, `infrastructure`, or `unknown`.
- `impact`: `none`, `low`, `medium`, `high`, `outcome-blocking`, or `unknown`.
- `attribution`: `agent`, `prompt-system`, `model`, `tooling`, `infrastructure`, `user-input`, or `unknown`.
- `confidence`: number from 0 through 1. Confidence is not proof.
- `evidenceRefs`: JSON pointers into packet session data. Never copy telemetry excerpts.
- `proposedIntervention`: `prompt`, `code`, `tool`, `eval`, `workflow`, `routing`, `monitor`, `none`, or `unknown`.
- `public`: proposed public-safe title, tracked relative paths, aggregate, intervention, acceptance criteria, and evaluation requirement.

Use `unknown` whenever evidence cannot support a narrower classification. Use `needs-human` when privacy or attribution remains uncertain.

## Evidence rules

Classify raw tool errors as events, not mistakes. Escalate only after evidence supports this sequence:

1. Event: observed tool, model, evaluator, or workflow signal.
2. Incident: verified user-visible failure or avoidable wasted work.
3. Pattern: repeated, attributable incidents in a matched cohort.
4. Change: Human approval of exact sanitized public proposal and regression check.

Default promotion threshold: at least 3 confirmed instances across 2 independent work items, or at least 5 comparable invocations with a materially worse baseline rate. Token inefficiency requires at least 5 comparable invocations and p95 normalized fresh tokens or cost at least 1.5× cohort median. Retry overhead becomes notable near 25% added tokens or latency without improved verified outcome.

Match cohorts by task, risk, context shape, role, model, and prompt version where available. Separate fresh input, cache-read, and output tokens. Missing samples remain `monitor`; absence of evidence is not success.

## Public boundary

Private packets, excerpts, URLs, telemetry IDs, absolute paths, user content, and repository identity stay outside Git. Public proposals contain only generalized failure class, sanitized aggregate, tracked relative paths, proposed change, acceptance criteria, and evaluation requirement. Human approval is mandatory before Bead creation. Policy or prompt changes remain separate, test-gated implementation work.
