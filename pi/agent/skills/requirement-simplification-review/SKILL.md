---
name: requirement-simplification-review
description: Use when simplifying codebases by auditing requirements creep; not for refactoring or bug fixes.
disable-model-invocation: true
---

# Requirement Simplification Review

Trace implementation complexity back to requirements before changing code. Remove accidental obligations, retain load-bearing ones consciously, and leave an implementation-ready decision record.

Invoke explicitly with `/skill:requirement-simplification-review`. It stays out of automatic selection because this is a deliberate, potentially long product-requirement review.

## Hard gates

- **Review first, implementation later.** Do not edit implementation code or start refactoring during this review. Accepted changes become separately owned follow-up work.
- **Inspect facts; ask decisions.** Read code, callers, tests, docs, history, and work items instead of asking the user for discoverable facts.
- **One decision at a time.** Ask exactly one decision question, include a recommendation, and wait for agreement before advancing.
- **No deletion quota.** `Keep`, `Narrow`, `Drop`, and `Defer` are all valid. Security, data-integrity, accessibility, approval, and verification requirements need explicit evidence and approval before weakening.
- **No false precision.** Quantitative estimates are directional ranges with a measured baseline, stated scope, overlap reconciliation, and confidence.
- **Current and future stay distinct.** Never mix code already removable with code that merely need not be built later.

## Nearby skills

Use this skill one level before architecture or refactoring work:

- architecture-deepening review asks where a better **Module**, **Interface**, or **Seam** should live;
- code simplification asks how to preserve behavior with less code;
- this review asks whether behavior and its driving requirement need to exist at all.

When the repository uses deep-module vocabulary, use **Module**, **Interface**, **Implementation**, **Depth**, **Seam**, **Adapter**, **Leverage**, and **Locality** exactly. Do not design a speculative Interface while its requirement is still disputed; one Adapter is still a hypothetical Seam.

## 1. Establish scope and evidence state

Record:

- subsystem or behavior under review;
- current commit and worktree state;
- relevant design/spec/glossary/ADR files;
- existing work item and downstream dependencies;
- review artifact path and status (`In progress`).

Use project-local plans or architecture docs for durable decisions. Keep current behavior separate from approved future direction so documentation never claims unimplemented behavior exists.

If a project knowledge graph exists, use it as a map, then verify source. Prefer exact filesystem retrieval over broad pasted context.

## 2. Measure a rough baseline

Measure enough to make later reduction estimates meaningful, not enough to create a metrics project.

For the scoped production and focused test surface, record:

- included files and line counts;
- major state machines, branches, adapters, concurrency/lifecycle paths, or policy variants;
- public and package-private Interface size where relevant;
- recent change hot spots;
- non-test production reachability.

State exclusions. Record measurement command, date, and commit when practical. Lines are a proxy for maintenance surface, not a quality target.

## 3. Build requirement archaeology

Start from highest-complexity clusters. For each cluster, trace:

1. Implementation branches, states, invariants, and failure paths.
2. Every caller, especially non-test production callers.
3. Tests that preserve the behavior.
4. Normative docs, ADRs, plans, glossary terms, and work-item acceptance criteria.
5. History or provenance explaining why the behavior exists.
6. User outcome or operational constraint the behavior protects.

Classify each candidate requirement:

- **explicit-current** — clearly approved and currently required;
- **implicit** — inferred from implementation, tests, or workflow;
- **historical** — once required, now possibly superseded;
- **speculative** — built for an unproven future need;
- **implementation-choice** — mechanism mistaken for requirement;
- **contradictory** — sources disagree and need resolution.

A test proves behavior exists, not that requirement remains valid. No current production caller is strong challenge evidence, not automatic permission to delete a foundational requirement.

Rank candidates by:

- maintenance surface caused;
- deletion or future-avoidance leverage;
- confidence in provenance;
- dependency order between decisions; and
- safety or migration risk.

## 4. Run one-decision loop

Before each question, present only what is needed for that decision:

1. **Requirement:** precise current or inferred obligation.
2. **Evidence:** callers, tests, docs, and exact paths.
3. **Complexity cost:** machinery and maintenance burden it causes.
4. **Options:** usually `Keep`, `Narrow`, `Drop`, or `Defer`, with concrete meanings.
5. **Recommendation:** smallest requirement that still protects demonstrated need.
6. **Consequence:** what remains, becomes unsupported, or moves to explicit failure.
7. **Rough delta:** latest decision's estimated current and future effect, before acceptance.
8. **Question:** one choice only.

Do not hide default judgments behind questions. Recommend an answer and explain why. If the answer depends on a repository fact, inspect it first.

After agreement:

- restate decision as an enforceable requirement and non-goals;
- record disposition and provenance in review artifact;
- update latest delta and reconciled running totals;
- note source documents and work items made stale;
- identify required follow-up without implementing it; and
- then move to next dependency-ready decision.

If user revises an earlier decision, replace it and recompute downstream totals. Do not layer contradictory decisions.

## 5. Maintain quantitative scoreboard

Keep four separate ledgers:

1. **Current net removal** — estimated production-plus-test code already present that accepted decisions make removable, net of replacement code.
2. **Gross future avoidance** — unimplemented machinery no longer required.
3. **Required future additions** — new machinery accepted decisions still require.
4. **Net future avoidance** — gross avoidance minus required additions.

For independent ranges:

```text
net future range = [gross low - additions high, gross high - additions low]
```

When candidates overlap, do not sum them mechanically. Reconcile shared files, tests, and mechanisms, then state that running total is overlap-adjusted.

Track every decision, including zero-delta retained requirements:

| Decision | Disposition | Latest current delta | Latest future avoided/cost | Running current net removal | Running net future avoided | Basis/confidence |
|---|---|---:|---:|---:|---:|---|

Always report both latest delta from previous clarification and running totals. Use another stable unit—files, branches, states, Interfaces, dependencies—when line estimates would mislead.

## 6. Record durable contract

Review artifact should contain:

```markdown
# Requirement Simplification Review

**Status:** In progress | Complete
**Scope and measured baseline:** ...

## Requirement map
## Decision log
## Quantitative scoreboard
## Accepted implementation follow-ups
## Retained requirements
## Deferred ideas and evidence triggers
## Superseded or contradictory sources
## Open questions
```

For each decision record:

- exact requirement and disposition;
- evidence/provenance;
- current behavior versus approved direction;
- consequences and non-goals;
- latest and running quantitative estimate;
- implementation owner or explicit deferral trigger.

`Defer` means no implementation authorization. Name observable evidence that would justify reopening it.

## 7. Close out review

Before marking review complete:

1. Resolve or explicitly list every open question.
2. Audit normative docs, specs, ADRs, glossary, plans, and work items for contradictions and stale terminology.
3. Ensure every accepted current-code cut and required addition has one non-duplicative follow-up work item.
4. Refresh stale downstream work-item descriptions and acceptance criteria.
5. Check dependency direction, cycles, blockers, and ready-work result.
6. Keep trigger-based deferrals out of implementation queue unless user authorizes them.
7. Obtain independent read-only review of decision consistency, arithmetic, and follow-up coverage for substantial reviews.
8. In a Beads repository, update the review Bead with decision evidence, link each successor Bead without duplication, and verify dependency cycles and ready-work effects.
9. Run link, arithmetic, diff, context, and project verification appropriate to changed artifacts.
10. Mark artifact `Complete` only after findings are resolved and checks pass, then commit task-owned artifact, source, and work-item updates.
11. Close the review Bead only after that commit; record tracked closure bookkeeping per project policy.

Final report states:

- measured baseline;
- retained, narrowed, dropped, and deferred requirements;
- current net-removal range;
- gross future avoidance, required additions, and net future-avoidance ranges;
- owned follow-up work;
- verification evidence; and
- remaining uncertainty.

## Failure modes

- **Jumping to refactors:** return to requirement causing the complexity.
- **Batching questions:** ask highest-leverage dependency-ready decision only.
- **Treating implementation as requirement:** restate protected outcome, then compare mechanisms.
- **Counting tests as demand:** find production or explicit product provenance.
- **Optimizing for deletion:** keep load-bearing requirements even when delta is zero or negative.
- **Double-counting estimates:** reconcile overlap and show arithmetic.
- **Chat-only agreement:** update durable sources and work-item ownership before closeout.
- **Premature implementation:** stop review at approved contract and hand off successor work.
