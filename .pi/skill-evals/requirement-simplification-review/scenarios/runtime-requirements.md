# Scenario: runtime requirement archaeology

## Prompt
An implemented project-runtime subsystem has grown difficult to maintain. Identify explicit or implicit requirements causing most complexity, challenge them one decision at a time, and stop after asking first decision question. Use repository evidence instead of asking me for facts you can inspect. For every resolved decision, maintain a rough quantitative comparison showing latest delta and running totals for current code removable and future code avoided. Do not implement refactors during review.

## Expected weak baseline
Generic architecture review jumps to modules, interfaces, or refactoring candidates before proving which requirement causes each complexity cluster. It may batch questions, omit a recommendation, mix current deletion with speculative future avoidance, report additive line estimates without overlap reconciliation, or leave accepted decisions only in conversation without documentation and follow-up ownership.

## Expected with skill
Agent measures relevant implementation/test surface, traces high-complexity clusters through callers, tests, docs, and history to candidate requirements, ranks candidates, and asks exactly one decision question with evidence, recommendation, consequence, and rough delta. It keeps current-code removal separate from future-code avoidance/cost, waits for agreement before next question, and reserves implementation for successor work.

## Assertions
- Inspects code, tests, callers, design docs, history, and existing work items before treating an assumption as a requirement.
- Distinguishes current behavior, documented requirement, inferred requirement, and proposed requirement.
- Ranks complexity-driving requirements rather than listing generic code smells.
- Asks one decision question only, includes recommended answer, and waits.
- Does not edit implementation code or begin refactoring.
- Defines separate range ledgers for current net removal, gross future avoidance, required future additions, and net future avoidance.
- Reports latest-decision delta plus reconciled running total without blindly summing overlapping ranges.
- Plans durable decision provenance, source-document alignment, and non-duplicative implementation work-item coverage at closeout.
- Treats retained requirements and required additions as valid outcomes rather than forcing deletion.
