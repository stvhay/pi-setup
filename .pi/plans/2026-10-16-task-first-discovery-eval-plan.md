# Task-first skill discovery: paired evaluation plan

**Bead:** `pi-8f3p`
**Status:** Human-reviewed and frozen. User selected “Approve packet; freeze, verify isolation, then run.” Model runs remain gated on the preflight below.
**Date:** 2026-10-16
**Goal:** Compare observable skill discovery and bounded handoff/gate behavior on 12 selected cases, not estimate population-wide recall.

## Scope and provenance

- Baseline: `53eaab3f43779931a74452bd7a70172b163f281d`.
- Candidate: `b6f4e676c78f5d427937146092208042689c9a61`; baseline is its verified parent.
- Source: `.pi/plans/2026-10-16-task-first-skill-routing-design-plan.md`, R1–R18/M1–M4, and existing `.pi/skill-evals/*/scenarios/` fixtures. These are source-derived expectations, not previously observed model results.
- Cases: `.pi/skill-evals/task-first-discovery/cases.json`. `input` alone goes to the tested agent. `expectedOutput` and `metadata` stay outside its fixture and prompt.
- Cases are synthetic, controller-authored adaptations. Human review is required; they are not ground truth merely because they match candidate instructions.
- Dataset guidance consulted: https://langfuse.com/academy/datasets (fetched successfully); input, expected criteria and metadata remain separate. No live Langfuse dataset, platform install or judge model.
- Current checkout skills match the candidate. No skill/runtime/config/dependency changes, deployment, push, branch/worktree operations or unrelated plan edits.

## Review set

Read the exact `input`, required/allowed reads and behavioral checks in `cases.json` before approving.

| Case | Requested outcome | Required skill body reads | Main distinction |
|---|---|---|---|
| C01 | Diagnose equality-boundary test regression | systematic-debugging | Not CAST or work learning; no fake test execution |
| C02 | Explain pump near-miss across controls | stamp-cast | Not software debugging or routine retrospective |
| C03 | Decide agent lifecycle from 20-run cohort | agent-retrospective-loop | Not one-run debugging; missing evidence stays unknown |
| C04 | Recovery screen after partial report failure | failure-choreography | Preserved/lost/uncertain state, not crash investigation |
| C05 | STRIDE-only API analysis | None | Neighbor reads allowed; method substitution forbidden |
| C06 | Divergent stale-decision ideas | ideate | No winner, convergence or implementation plan |
| C07 | Rewrite two button labels | ux-writing | No mandatory UX parent or unrelated redesign |
| C08 | Compare supplied paper excerpts | literature-synthesis | Source IDs/limits; no research-method pipeline |
| C09 | Extend supplied safety model to malicious feedback | stamp-stpa-sec | Carry IDs, boundary, assumptions and constraints |
| C10 | Design with unknown users/modality | brainstorming + ux-design-agent | Conditional UX handoff returns to approval gate |
| C11 | Design expired email-approval state | approval-confirmation | Also read timeout reference; fail closed, preserve drafts |
| C12 | Finish substantial change with review artifacts forbidden | finishing-a-development-branch + requesting-code-review | Required review blocked; no unsupported readiness |

C09 is a supplied-state handoff, not an actual preceding STPA conversation. C10 tests only the pre-approval portion of M2. C08 tests the boundary against an unsolicited pipeline, not the full M3 chain. C12 tests blocked review, not successful artifact-backed review. These limits must appear in the report.

## Frozen scoring rules

Score both versions against the same reviewed contract. Baseline defects are failures, not grounds to change expected behavior after seeing output.

### Reads and discovery

1. Evidence is a successful `read` tool call/result pair for the version-correct skill body. Match tool-call IDs and normalized paths; retain event indexes and file hashes. A prose claim, tool request without success, skill name in another file or description-only selection does not count.
2. Record complete and partial reads separately. Required body/reference credit requires complete returned content (one call or cumulative ranges); detect truncation and missing ranges. Successful partial reads count as attempted selection for precision diagnostics, not full recall credit.
3. Required reads are the case's `requiredSkillReads`. Skill-read recall is fulfilled required reads / required reads across valid runs. Also report each case's all-required-reads pass count out of valid repeats. C05 has no recall denominator; do not award it an automatic recall pass.
4. `allowedSupportingSkillReads` earn no recall credit and incur no penalty. `dev-workflow-common` is additionally allowed when the loaded skill references it. Other hidden bodies are not implicitly allowed. References belonging to required/allowed skills are neutral except C11's separately required timeout reference.
5. Load precision is unique required-or-allowed skill bodies successfully read / all unique skill bodies successfully read, per run and pooled. Count partial successful reads in this load metric and identify them. Report required, supporting and unexpected loads separately so optional loads cannot hide misses. No body reads gives undefined precision, not 100%.
6. Skills not listed as required/allowed are unexpected loads, even if another skill links them. Record plausible alternatives verbatim for human adjudication; do not silently broaden the allowlist after runs. Any rubric revision requires a new version and labels the original results exploratory.
7. `forbiddenRoutes` flags unacceptable task substitution/unsolicited work, not mere boundary consultation. Unexpected consultation reads still affect load precision. C05 explicitly permits STPA-Sec/base consultation while forbidding replacing STRIDE with their methods.
8. Track first complete skill body read and order of later reads. Do not enforce one universal first skill: direct specialists and legitimate boundary consultations remain valid. For C10 either design/UX entry order is valid. Repeated reads or parent-child loops are diagnostics, not extra recall credit.

### Behavior, handoffs and gates

- Score every `checks` item PASS/FAIL/UNSCORABLE with exact final-output quote or event reference. A normal completed response that omits a required behavior is FAIL, not invalid. UNSCORABLE requires an explicit evidence deficiency and cannot count as PASS.
- C09 handoff: IDs, boundary, A-1, SC-1, added security output. C10 handoff: both bodies read before final requirements/options, offline/duplicate constraints retained, approval stop. C12 handoff: both bodies read, missing artifact evidence stated, completion blocked.
- C11 reference load and fail-closed behavior are separate results. A safe answer without the required reference may pass behavior but fail reference retrieval. A dangerous timeout recommendation fails behavior even if the body was read.
- Report safety/gate statements separately from actual-read evidence. Read-only tools cannot prove prevention of real writes, sends, deployments, retries or other effects. Never infer executed-effects safety from lack of an available mutation tool.
- No aggregate pass score that conceals a gate failure. Report per-case/read/behavior results and paired differences; retain negative results.

### Validity, retries and pairing

- Planned sample: 12 cases × 3 repeats × 2 versions = 72 fresh processes/sessions; no resumed chats, forced `/skill` commands, corrective follow-up prompts or model-based judging.
- Proposed fixed model: `openai-codex/gpt-6-astra` (current subscription controller); thinking `medium` for both versions. No fallback model, provider switch or paid API calls. Verify availability without a model request.
- Fixed order: repeats 1–3, cases C01–C12; for each pair run baseline first when case number + repeat is even, candidate first otherwise. Run serially. This balances order without hidden randomization.
- Bound each process to 900 seconds wall time for this explicit experiment. No custom token/request cap. Stop the batch for credential/isolation drift or repeated infrastructure/provider failures; run read-only `agnt doctor --json` rather than retry blindly.
- Preserve every attempt. Classify timeout, provider/auth failure, malformed/missing event stream, missing final response and isolation failure separately. No automatic replacement sessions or reruns beyond the approved 72; request a bounded amendment if needed.
- A completed response with wrong/no skill loads, failed reads caused by its chosen path, refusal or poor answer is a behavioral result, not an infrastructure invalid. Known fixture/path setup errors are invalid; stop and fix preflight before resuming.
- Compare paired deltas only where both version runs are valid. Show valid denominators, unmatched runs and attempted/valid counts for each version. Three repeats are not independent population samples; report counts and descriptive deltas, not broad statistical claims.

## Preflight after human case review, before any model call

1. Read installed Pi main/CLI documentation plus `skills.md`, `settings.md`, `packages.md`, and relevant environment/auth/JSON documentation completely; follow relevant links. Re-read `scripts/eval-workflow-compliance.sh` for existing JSON/timeout patterns. Do not reuse its forced-skill scores as discovery recall.
2. Confirm documented flags and chosen model/thinking without making a model request. Capture Pi version, executable/package provenance, model identity, settings and exact eventual argv; redact credentials.
3. Export only versioned `pi/agent/skills/` into isolated version-neutral fixture paths. No whole repository, case labels, rubric, design plan, raw results or review report in the model fixture. Preserve 48 discoverable skills and two hidden helpers in both versions; verify identical names/hidden flags and source hashes, with intentional content/description differences recorded.
4. Disable ambient context files, packages/extensions, prompt templates and MCP through supported flags/settings; use only `read`, `--mode json --print --no-session`, explicit skill root plus `--no-skills`. Verify no ambient/package skill appears. Check actual discovery construction without provider calls, including full paths/descriptions rather than relying on the metadata budget proxy alone.
5. Resolve all `~/.pi/agent/skills/` and relative handoffs into the correct snapshot through isolated HOME/path setup. Validate manifest and referenced paths. Hold directory layout/path lengths constant across versions where feasible; record unavoidable path differences.
6. Choose an existing subscription auth mechanism after reading docs. Never copy credentials into model fixtures, prompts or raw logs. Read-only tools are not a filesystem sandbox. If safe auth/isolation cannot be established, stop and report the limitation; do not weaken scope or invent a new credential mechanism.
7. Save exact reviewed case/rubric hashes, review answer, fixture manifests, path checks, runner commands/settings and an empty 72-row schedule before launch. Use ignored `.pi/reviews/pi-8f3p/` for private raw evidence and task-specific driver, if a small driver is needed; no reusable eval platform. Any nontrivial driver/scoring logic needs a small offline self-check before use.
8. During runs verify event evidence uses only the intended catalog. Isolation failure invalidates the affected run and stops the batch. Do not continue after seeing expectations or wrong-version files enter a prompt.

## Artifacts and verification

Task-owned durable artifacts:

- `.pi/skill-evals/task-first-discovery/cases.json`: reviewed inputs and criteria; freeze bytes/hash after approval.
- This plan: protocol and scoring; freeze hash after approval.
- `.pi/skill-evals/task-first-discovery/report.md`: eventual results, provenance, validity counts, case-level evidence references, limitations and private raw artifact inventory/hashes.

Private `.pi/reviews/pi-8f3p/` holds prompts, manifests, command provenance, raw JSONL/stderr, extracted read traces and scored evidence. Keep credentials out. Do not commit raw model output or session/auth state. No new dependencies or runtime exports/callers/config changes are needed.

Draft verification: JSON parses; exactly 12 unique case IDs and inputs; every required/allowed skill and required reference exists in both pinned versions; all source-case IDs appear in the design; no `/skill:` input or expected-route labels enter model inputs; `git diff --check`; preserve unrelated plans.

Before results/commit: validate all 72 schedule rows against manifests/raw events; reconcile actual-read counts manually against representative raw streams including failures; apply identical rubric to both versions, preferably with version labels hidden during behavioral scoring. Record scorer identity and unblinding limits. Verify report totals and artifact hashes; review task-owned diff. No production-code test suite is claimed necessary for data/report-only changes. Follow normal verification/commit/direct-closeout only after the Bead acceptance criteria are met.

## Review request

Approve or revise the exact 12 inputs, required/allowed reads, behavioral checks, exclusions and protocol before runs. These drafts deliberately favor high-signal collision/gate cases over broad catalog coverage. Approval does not authorize deployment, skill fixes, paid models, extra runs or changes to unrelated plans.
