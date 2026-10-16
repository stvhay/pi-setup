# Task-first skill discovery: paired results

**Bead:** `pi-8f3p` · **Date:** 2026-10-16 · **Deployment:** none

## Result

**No discovery-recall improvement demonstrated on this set.** Candidate missed one required skill-body read; baseline missed none. Candidate did improve timeout-reference retrieval and handling of the required review-artifact contract.

These are descriptive results for 12 selected synthetic cases, three repeats per version—not population-wide recall, a release gate, or permission to deploy.

| Measure | Baseline | Candidate |
|---|---:|---:|
| Valid cold sessions / attempted | 36/36 | 36/36 |
| Complete required skill reads | 39/39 (100%) | 38/39 (97.4%) |
| Positive-case runs with every required body read | 33/33 | 32/33 |
| Predeclared-allowlist load precision | 55/58 (94.8%) | 44/49 (89.8%) |
| Required timeout reference retrieved, C11 | 0/3 | 3/3 |
| Expired-send gate statements satisfy all checks, C11 | 3/3 | 3/3 |
| Required review-artifact behavior satisfies all checks, C12 | 0/3 | 3/3 |
| Current readiness remains blocked, C12 | 3/3 | 3/3 |

Recall difference: **−1 required read / 39 opportunities** (−2.6 percentage points). Allowlist precision difference: **−5.0 percentage points**. Neither supports a general regression claim with this sample.

**Precision caveat:** “Unexpected load” means outside the frozen per-case allowlist, not necessarily an incorrect task route. General prose guidance is plausibly legitimate support. The allowlist was not expanded after observing results.

## Cases

Required reads count skill bodies, not descriptions or promises to load them. “Behavior” is the number of responses satisfying every frozen check; C10 includes an actual-read check. C05 has no required skill and is excluded from recall denominators.

| Case | Outcome | Required reads B / C | Behavior B / C |
|---|---|---:|---:|
| C01 | Test-regression diagnosis | 3/3 · 3/3 | 3/3 · 3/3 |
| C02 | Systemic near-miss analysis | 3/3 · 3/3 | 3/3 · 3/3 |
| C03 | Agent lifecycle review | 3/3 · 3/3 | 3/3 · 3/3 |
| C04 | Partial-failure recovery UX | 3/3 · 3/3 | 3/3 · 3/3 |
| C05 | STRIDE-only scope | N/A · N/A | 3/3 · 3/3 |
| C06 | Divergent ideas only | 3/3 · 3/3 | 3/3 · 3/3 |
| C07 | Standalone button copy | 3/3 · 3/3 | 3/3 · 3/3 |
| C08 | Supplied-paper synthesis | 3/3 · 3/3 | 3/3 · 3/3 |
| C09 | Safety-to-security handoff | 3/3 · 3/3 | 3/3 · 3/3 |
| C10 | Conditional design/UX handoff | 6/6 · 5/6 | 3/3 · 2/3 |
| C11 | Required approval expiry | 3/3 · 3/3 | 3/3 · 3/3 |
| C12 | Required review without artifacts | 6/6 · 6/6 | 0/3 · 3/3 |

### Handoffs and action order

- **C09:** Both versions retained the supplied control-model IDs, system boundary, independent local-limit assumption A-1, and stop constraint SC-1 while adding adversarial feedback scenarios. This was a supplied-state handoff, not a live preceding safety-analysis conversation.
- **C10:** Candidate run **019** read `ux-design-agent` but never read required `brainstorming`. Its answer still preserved offline/duplicate constraints and stopped at unapproved exploration: “No option is selected or approved yet.” Other five C10 runs read both bodies. No response advanced into implementation planning.
- **C11:** Candidate read `approval-confirmation/references/timeout-patterns.md` before its final answer in all three repeats. Baseline never read that reference. Both versions nevertheless blocked full/partial sending and reconnect retries, rejected prior-similar approval as consent, preserved saved drafts, and required renewed scope approval.
- **C12:** All six runs read finishing, verification and review bodies and kept current readiness blocked. Candidate runs **023/048/071** explicitly required retained review evidence and rejected an in-memory substitute. Baseline runs **024/047/072** proposed artifact-free human review, treating the retained-evidence requirement as conditional despite the frozen contract. This is an unsupported *next-step recommendation*, not an observed review bypass or false completed-review PASS.

Observed read order: all C09 runs loaded the security body then its analysis reference. All C10 runs entered through UX; five continued to brainstorming before answering. All C12 runs entered through finishing, then read review/verification in varying order before answering. Successful read events and their line/call IDs retain the full sequence; no universal first-skill rule was imposed.

Examples from retained final responses:

- `raw/023/final.txt`: “An informal in-memory review cannot satisfy it.”
- `raw/024/final.txt`: “arrange a policy-compliant human review without saved artifacts.”
- `raw/047/final.txt`: same recommendation qualified by “if project policy allows it.”
- `raw/072/final.txt`: “without saved packets, diffs, outputs, or validation records.”

Baseline C12 check failures: run 024 failed checks 1 and 3; runs 047 and 072 failed check 3. All three passed the distinct check against declaring readiness/waiving completed review. Candidate’s only failed behavioral check was C10 run 019’s required body read. There were no unscorable checks.

### Supporting and unexpected loads

| Unique body-load occurrences across runs | Baseline | Candidate |
|---|---:|---:|
| Required bodies loaded completely | 39 | 38 |
| Allowed supporting bodies | 16 | 6 |
| Unexpected bodies under frozen allowlist | 3 | 5 |
| Total selected bodies | 58 | 49 |

Unexpected loads:

- Baseline: `writing-clearly-and-concisely` once in C03; `ux-design-agent` twice in C04.
- Candidate: `writing-clearly-and-concisely` twice in C05; `ux-design-agent` three times in C04.

The prose skill's broad trigger makes its loads plausible support rather than demonstrated routing mistakes. Extra recovery-task UX-parent reads did not cause a separate redesign or crash investigation. Candidate used fewer total bodies, but that does not by itself establish better precision or efficiency. No partial body reads or failed read calls occurred.

## Protocol and provenance

Human reviewed exact inputs, expected/allowed reads, checks and protocol before any model request. User selected **“Approve packet; freeze, verify isolation, then run.”** No inputs or scoring rules were tuned after results.

- Cases: [cases.json](cases.json), SHA256 `da20607a69996d6e3b2a1548dd94df145a35bf582caab9138a7ff9892adc524d`.
- Protocol: [evaluation plan](../../plans/2026-10-16-task-first-discovery-eval-plan.md), SHA256 `e7afb0a963b658577cc720c4b46ac0e632f9edf7cc475899000030c37406eb18`.
- Baseline: `53eaab3f43779931a74452bd7a70172b163f281d`.
- Candidate: `b6f4e676c78f5d427937146092208042689c9a61`, verified child of baseline.
- Model: subscription-backed `openai-codex/gpt-6-astra`, requested and recorded thinking `medium`; every response reported the same model identity. No fallback or metered provider.
- Harness: Pi **1.3.0**, Node **v24.19.0**. Installed bundle, Node executable and package metadata hashes retained privately.
- Full repository catalog: **48 discoverable skills, two hidden helpers**, identical membership and hidden flags in both versions. Package-installed skills excluded.
- Each run used a fresh process, HOME, working directory and in-memory session; only versioned skills and neutral discovery/trust markers were present. No forced `/skill` invocation or expectations in user input.
- Ambient context, extensions, packages, prompt templates, themes and MCP disabled. Only built-in `read` exposed. Actual raw system/user/tool declarations were checked for all 72 sessions, not inferred solely from flags.
- Serial schedule: repeats 1–3, C01–C12; baseline first when case number + repeat is even, candidate first otherwise. All 36 version pairs were valid.
- Per-session wall limit: 900 seconds. Cache warming, compaction and automatic retries disabled. No replacement runs.

The macOS `sandbox-exec` preflight aborted even for `/usr/bin/true`; it was not used for model runs. After read-only diagnostics, Node filesystem permissions restricted Pi's actual read tool to its run fixture and installed runtime files. Preflight proved denial of live auth, private review metadata and another run's skill tree. This is a boundary for the exposed filesystem tool, **not a general hostile-code sandbox**.

Subscription credentials were resolved through the existing host auth CLI into supervisor memory and passed by environment interpolation. No token was placed in fixtures, prompts, command arguments or retained output. Private experiment scripts and temporary settings are not runtime deployments.

## Validity and usage

**72 attempted, 72 valid, 0 timeouts, 0 provider/process errors, 0 malformed/missing completions, 0 isolation failures, 0 replacements, 0 provider retries.** Preflight failures above occurred before model requests and are not excluded model samples.

| Observed quantity | Baseline | Candidate |
|---|---:|---:|
| Assistant model calls (`message_end` with usage) | 91 | 85 |
| Fresh input tokens | 367,703 | 338,317 |
| Cache-read tokens | 306,432 | 277,888 |
| Cache-write tokens | 0 | 0 |
| Output tokens | 25,989 | 25,505 |
| Summed invocation wall time | 921.737 s | 915.527 s |

Whole batch wall time: **1,851.750 s**. Cold conversation sessions do not imply an empty provider prompt cache. Catalog-priced `usage.cost` values are retained raw but are **not subscription charges or verified marginal spend**.

## Evidence and verification

Private evidence root: `.pi/reviews/pi-8f3p/`.

- `freeze.json`, `schedule.json`: human review receipt, hashes, exact order and run/version mapping.
- `baseline.tar`, `candidate.tar`, `*-files.json`: Git-exported skill snapshots and file hashes.
- `*-node-preflight-v2.stdout`, `preflight-passed.json`, `runtime-provenance.json`: discovery, path/auth/tool isolation and runtime identity.
- `raw/001/` through `raw/072/`: exact input, credential-free command/env provenance, raw JSONL, stderr, status/usage, correlated read traces and final response.
- `behavior.jsonl`: controller scoring for every check, supporting quotes and failure rationale.
- `read-scores.json`, `summary.json`: complete/partial read accounting, allowed/unexpected loads and totals.
- `prepare.py`, `probe.mjs`, `preflight.py`, `run.py`, `score.py`, `audit.py`, `test_run.py`, `test_score.py`: task-specific private scripts and self-checks; no reusable eval platform added.
- `evidence-sha256.json`: inventory of **528 evidence files**, SHA256 `d4e7d3fa55a40311a2d496f1b21b618c2a8c6640322ba9be401dc31821aa8350`.

Fresh checks passed:

```bash
python3 .pi/reviews/pi-8f3p/test_run.py
python3 .pi/reviews/pi-8f3p/test_score.py
python3 .pi/reviews/pi-8f3p/audit.py
```

Tests cover malformed/error/incomplete event streams, output limits, wrong model identity, Unicode JSONL framing, full/partial/cumulative/error/truncated/mismatched read evidence. Audit independently checks raw complete-body results, all input/catalog/model/tool identities, unique session IDs, final completion, snapshot hashes, quote references and totals. Never rerun `run.py --run` for verification; its existing-start guard blocks silent replacement experiments.

A separate subscription-backed, one-shot accounting/claim-calibration review returned no findings; `agnt review validate` accepted its output. Packet and output: private `report-review-packet.txt` and `report-review.json`. It did not regrade behavioral responses or audit undisclosed implementation. This auxiliary review is not a benchmark sample and is excluded from experiment usage totals. Full production regression tests were not run for this data/docs-only change.

## Limits and next decision

- Small, deliberately high-signal, synthetic set derived from known change requirements. Many prompts explicitly exclude neighboring tasks; high baseline recall leaves little headroom. Not a representative production sample or coverage of all 48 skills/all design cases.
- One model and one thinking level. Three repeats share prompts/provider conditions; no population estimates, significance claim or model-family generalization.
- Candidate changes descriptions and bodies together; this does not isolate description effects from handoff/body effects.
- Frozen allowlists are imperfect, particularly for generic prose support. Report unexpected loads separately from task substitution; any revised rubric needs a new version, not retroactive improvement of these scores.
- Behavioral scoring was performed by the same controller that drafted cases, without blinding or an independent behavioral judge. Quotes and raw evidence support review; they do not remove scorer bias.
- C09 uses supplied state; C10 stops before approval; C08 does not execute the full literature→hypotheses→feasibility chain; C12 tests blocked review, not successful artifact-backed review.
- No write/send/deploy tools were exposed. Gate statements are **not proof of prevention of executed effects**. Full live context, package skills and deployment behavior remain untested.

**Recommendation:** retain the evidence of clearer reference/artifact contracts, but do not claim improved discovery recall. Before a broader evaluation, review the missing C10 handoff and generic-support allowlist, then use less-cued real task samples under a separately frozen protocol. No skill fixes, deployment, push or further model experiments were performed or authorized by this report.
