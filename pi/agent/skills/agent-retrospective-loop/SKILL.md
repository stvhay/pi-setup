---
name: agent-retrospective-loop
description: Use when capability-calibration assigns agent or harness lifecycle review, or when explicitly invoked; not for one-run bugs or branch retrospectives.
---

# Agent Retrospective Loop

Recommend whether to **Keep, Change, Pause, or Retire** an existing agent. Analyze and recommend only; do not mutate, disable, or retire the harness without explicit approval.

## Invocation and ownership

Invoke only from a `capability-calibration` activity assignment or explicit direct invocation. Control plan owns trigger timing and receiver selection. This skill does not choose review cadence, grant authority, schedule itself, or maintain a finding/work registry.

## Evidence rules

- Work through Steps 1–6 in order. Establish the replay baseline before proposing changes.
- Use the assignment's bounded run cohort and recurrence rules without silently mixing jobs or versions. For direct invocation, declare a bounded cohort and report patterns without inventing a recurrence threshold.
- Use local deterministic extraction for run fields and counts. Cite run IDs, artifacts, or exact evidence locations.
- Mark unavailable human feedback, usage, source, tool, or verification data as `unknown`; never infer it from silence.
- Treat missing evidence as a finding, not proof that a surface is healthy.
- Keep client, project, and secret data inside authorized local artifacts; report only the minimum evidence needed.

## Step 1: Name the current job

Write exactly one sentence in this form:

```text
This agent's job is to [produce this work] from [these sources] for [these users], with [this human review] before [this consequence].
```

If current scope is vague, overloaded, or contradicted by runs, say so and provide a tighter sentence. Separate observed current behavior from intended job.

## Step 2: Inspect the assigned evidence cohort

Create one row per run:

| Run | Used / changed / dropped | Human change | Sources | Tools called | Could not verify | Review burden |
|---|---|---|---|---|---|---|

Use `unknown` for absent evidence. After the table, list materially similar corrections that meet the assignment's recurrence rule, with run IDs and count. If direct invocation supplied no rule, report observed repetitions without promoting them to a recurrence finding. Do not merge unrelated symptoms into one pattern.

## Step 3: Inspect the seven surfaces

For each surface, return `ok`, `drifting`, or `broken`, plus run evidence and a concrete fix:

| Surface | Question |
|---|---|
| Job | Has work grown past the job sentence? |
| Diet | Are sources, examples, or retrieved context stale or wrong? |
| Memory | Is an outdated saved fact being replayed? |
| Tools | Are tools too broad, overlapping, or risky? |
| Reach | Can the agent act beyond what its owner can review? |
| Proof | Does output show evidence a human can check? |
| Value | Is output actually used? |

Do not rate a surface `ok` solely because evidence is absent. Use `drifting` for a material observability gap, or `broken` when that gap makes operation unsafe or unreviewable.

## Step 4: Build or revise the replay pack

Use the assignment's bounded replay cases from successful runs, repeated corrections, edge cases, and safety/reach failures. For direct invocation, choose the smallest representative bounded pack and state its scope. For each case, record expected behavior and score the current unchanged agent on:

- source choice
- tool choice
- job fit
- proof
- review burden
- stop/escalate behavior

Use one rubric for every dimension:

- `2` — correct, bounded, and readily reviewable
- `1` — usable only after material human correction or review effort
- `0` — wrong, unsafe, dropped, or unverified

Show per-case scores, total out of 12, dimension totals, and critical zeroes. Run in a sandbox/dry-run when tools have consequences. If fresh replay is unavailable, score archived runs, label baseline `historical`, and state the limitation.

Give the current-agent baseline before any proposed harness change. Do not tune cases after seeing proposed changes.

## Step 5: Delete before adding

For each problem, first name the smallest removal or narrowing that addresses its cause:

- stale source
- bad example
- broad or overlapping tool
- excess reach
- wrong memory
- vague job
- obsolete model workaround

Prefer structural removal, permissions, and source correction over prompt prose. Propose a new instruction only when a named replay case would still fail after those removals; identify that case and why instruction is necessary. Do not implement changes during the retrospective.

## Step 6: Decide

Return exactly one decision:

- **Keep** — current job remains valuable and baseline shows no material drift or broken surface.
- **Change** — job remains valuable and bounded changes can fix observed failures while human review remains effective.
- **Pause** — broken reach, tools, proof, or missing evidence makes continued operation unsafe or unreviewable pending fixes.
- **Retire** — job no longer provides used value, is obsolete, or is better replaced than repaired.

Include:

1. decision and evidence
2. exact harness changes, ordered delete/narrow before add
3. exact replay cases to rerun and required score improvements
4. evidence, gaps, and observed signals returned to `capability-calibration`; do not schedule the next review
5. evidence limitations and confidence

## Output contract

Use these headings in order:

```markdown
## 1. Current Job
## 2. Assigned Evidence Cohort
## 3. Seven Surfaces
## 4. Replay Pack and Baseline
## 5. Delete Before Adding
## 6. Decision: Keep|Change|Pause|Retire
```
