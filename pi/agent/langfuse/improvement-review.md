# Improvement Review Rubric

Use this rubric only with the private ReviewAssignment emitted beside an `agnt improve scan` packet. Human review, a local/self-hosted reviewer, or an explicitly provider-authorized reviewer classifies evidence; deterministic signals do not establish causality. Route only to the assignment's demonstrated reviewer capability. Do not send packet content to another provider without explicit authorization.

## Decision format

Return one assignment-bound JSON result with:

- `schemaVersion`: `1`.
- `assignmentId`: exact private assignment ID.
- `reviewStatus`: `completed`, `unavailable`, `timed-out`, `privacy-uncertain`, or `schema-invalid`.
- `route`: `none` only for a completed valid result; otherwise `human`.
- `gaps`: empty only for completion; otherwise the assignment-defined explicit gap.
- `attempt`: `1`. Stop after one attempt; never silently retry paid review.
- matching `reportId` and `reviewPolicyVersion`, ISO `reviewedAt`, and reviewed `sessions`.

For non-completed status, return no sessions or findings. Reviewer output cannot set grant, mode, authority, or allowed effects. A `completed` result must cover every assigned session exactly once. Each session has:

- `sessionId`: exact private packet session ID.
- `decision`: `no-action`, `actions-created`, `needs-human`, or `excluded`.
- `findings`: zero or more findings. `actions-created` requires at least one.

Each finding uses the shared Finding core:

- `schemaVersion`: `1`.
- `id`: `finding-` plus 12 lowercase hexadecimal characters.
- `activity`: `work-learning`; `source`: `improvement-review`.
- `category`: `coordination-error`, `expected-error`, `infrastructure`, `model-mismatch`, `prompt-targeting`, `security-boundary`, `token-inefficiency`, `tool-use-error`, `verification-gap`, or `unknown`.
- `severity`: `none`, `low`, `medium`, `high`, `outcome-blocking`, or `unknown`.
- `claim`: bounded private claim supported by cited packet evidence.
- `status`: `unverified`, `confirmed`, `refuted`, or `unresolved`.
- `evidenceRefs`: one or more exact session `evidenceRef` objects copied from this packet. Never alter pointers or copy telemetry excerpts.
- `verification`: `null` only while `unverified`; otherwise `method` is `test`, `reproducer`, `inspection`, `profile`, or `specification`, and `evidenceRefs` cites a subset of the finding refs.
- `proposedIntervention`: exact proposed change text; it must match `public.proposedIntervention`.

Improvement-owned extensions remain explicit:

- `errorRelevance`: `relevant`, `contributing`, `expected`, `recovered`, `infrastructure`, or `unknown`.
- `attribution`: `agent`, `prompt-system`, `model`, `tooling`, `infrastructure`, `user-input`, or `unknown`.
- `confidence`: number from 0 through 1. Confidence is not proof.
- `evidenceStage`: `event`, `incident`, `pattern`, `change`, or `unknown`.
- `interventionType`: `prompt`, `code`, `tool`, `eval`, `workflow`, `routing`, `monitor`, `none`, or `unknown`.
- `public`: proposed public-safe title, tracked relative paths, aggregate, intervention, acceptance criteria, and evaluation requirement.
- `relatedFindingId` (optional): existing private monitored finding ID when this new finding is an explicit recurrence in a packet-listed matched post-change cohort.

Use `unknown` whenever evidence cannot support a narrower classification or stage. Use `needs-human` when privacy or attribution remains uncertain.

The packet's `features.errorTaxonomy` is deterministic triage, not causal
judgment. It separates raw and unclassified-raw error-observation health counts
from classified signals; expected/recovered are non-actionable, provider/
infrastructure/agent are actionable, and unknown stays explicit.
`outcomeBlocking` is an independent state, not a primary error class. Never
reinterpret hashes, raw counts, or a
positive final outcome to guess a narrower class.

## Evidence rules

Classify raw tool errors as events, not mistakes. Record the supported `evidenceStage`; do not collapse or infer missing stages:

1. `event`: observed tool, model, evaluator, or workflow signal.
2. `incident`: verified user-visible failure or avoidable wasted work.
3. `pattern`: repeated, attributable incidents in a matched cohort.
4. `change`: Human-approved exact sanitized proposal with a regression check.

A proposed intervention does not itself advance evidence to `change`.

Default promotion threshold: at least 3 confirmed instances across 2 independent work items, or at least 5 comparable invocations with a materially worse baseline rate. One confirmed high-impact or outcome-blocking `security-boundary` finding, including confirmed credential exposure, is immediately eligible for a public-safe proposal. Token inefficiency requires at least 5 comparable invocations and p95 normalized fresh tokens or cost at least 1.5× cohort median. Retry overhead becomes notable near 25% added tokens or latency without improved verified outcome.

Human calibration for policy v2 established three regression rules:

- A successful outcome or zero deterministic actionable signals does not prove `no-action`; inspect human-visible constraint, privacy, and lifecycle failures.
- Classify a workflow stall as `coordination-error` when a handoff or lifecycle contract fails, `infrastructure` only when that cause is verified, and `unknown` otherwise.
- Classify avoidable output-limit truncation as `token-inefficiency`; use `infrastructure` only for a verified provider/platform cap and `unknown` when attribution is unresolved.

Synthetic regression cases:

| Case | Evidence | Expected classification |
|---|---|---|
| `security-success` | Successful outcome, zero actionable signals, and separately confirmed credential exposure | `security-boundary`, high impact |
| `handoff-stall` | Handoff contract does not start the ready target and no infrastructure cause is verified | `coordination-error`, workflow intervention |
| `one-shot-truncation` | Avoidable configured output cap terminates otherwise usable one-shot work | `token-inefficiency`, routing or workflow intervention |

Match cohorts by task, risk, context shape, role, model, and prompt version where available. Separate fresh input, cache-read, and output tokens. Missing samples remain `monitor`; absence of evidence is not success.

Promoted findings keep private monitoring state. Monitoring starts only after the linked Bead is closed. Five distinct reviewed sessions from the exact stored cohort mark the finding `validated` when none reports recurrence. Fewer samples remain monitoring. A new finding may use `relatedFindingId` only for a packet-listed matched session; applying review then marks the original finding `recurrent`. Validation and recurrence update private state only. Any recurrent public follow-up still requires the normal exact-preview Human approval before Bead creation.

## Public boundary

Private packets, excerpts, URLs, telemetry IDs, absolute paths, user content, and repository identity stay outside Git. Public proposals contain only generalized failure class, sanitized aggregate, tracked relative paths, proposed change, acceptance criteria, and evaluation requirement. Human approval is mandatory before Bead creation. Policy or prompt changes remain separate, test-gated implementation work.
