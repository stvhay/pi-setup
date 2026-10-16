# Task-first skill selection

Maintainer map for repository-owned skills, not a runtime gateway or executable router. Pi discovers descriptions and loads selected bodies on demand; named `/skill:<name>` entry points remain available. This is skill selection, not `agnt route` model selection. Package-installed skills are outside this map's ownership.

## Selection contract

1. Identify requested deliverable and object before method. “Failure,” “risk,” “review” and “root cause” alone are insufficient.
2. Honor explicit named methods. Offer alternatives without silently replacing fault trees, STRIDE or another requested method.
3. Select the smallest relevant entry. Ask one targeted question only when interpretations materially change the deliverable.
4. Direct specialist entry works without a parent. Optional stages are not mandatory pipelines; ask before expanding scope.
5. A handoff says why, exact body/reference to read, evidence to carry, next output and applicable stop/approval gate. Reuse unchanged loaded instructions. A related-skill name alone is not a load.

Edit owned source in this directory, not deployed copies. Runtime cross-skill pointers name the exact deployed body, such as `~/.pi/agent/skills/stamp-cast/SKILL.md`; within-skill references stay relative. Do not add this full map to root instructions or every skill.

## Outcome map

Names below identify existing skill directories, not required load sequences.

| Requested output | Entry / boundary |
|---|---|
| Repair software bug, failing test or runtime regression | `systematic-debugging`; implement with `test-driven-development`, prove with `verification-before-completion`. Not CAST by keyword. |
| Explain systemic accident, incident or near-miss | `stamp-cast`; stabilize active incidents first. Not ordinary session learning. |
| Learn from completed work | `retrospective`; assigned/requested only, not automatic closeout. |
| Keep/change/pause/retire harness behavior across runs | `agent-retrospective-loop`; assigned/requested lifecycle cohort, not one broken run. |
| Design recovery/human resumption after failure | `failure-choreography`; preserve lost/uncertain/retained work, not code diagnosis. |
| Explore divergent possibilities | `ideate`; no automatic convergence. |
| Resolve requirements into approved design | `brainstorming`; conditional `ux-design-agent` for unclear users/usage/modality, `first-principles` for obstructing assumptions. |
| Assess concrete diff correctness / process incoming comments | `requesting-code-review` / `receiving-code-review`; distinct workflows. |
| Critique assumptions / compare through reciprocal debate | `redteam` / `council`; central-critic competition differs from reciprocal rounds. |
| Prospective system-safety hazards / adversarial control paths | `stamp-stpa` / `stamp-stpa-sec`; generic critique or STRIDE-only requests do not force either. |
| STAMP theory or method selection | `stamp-base`; not universal failure gateway. |
| Multi-source facts / paper synthesis | `research` / `literature-synthesis`; research excludes software diagnostics and background checks. |
| Rank research explanations / assess program go-no-go | `hypothesis-tournament` / `heilmeier-catechism`; preserve distinct analytical outputs. |
| Optimize against explicit score | `scorable-discovery`; reproducible baseline and guardrails, not unscored ideation. |
| Plan / serially execute approved implementation | `writing-plans` / `executing-plans`; neither invents approval. |
| Independent read-only investigation / parallel implementation | `dispatching-parallel-agents` / `subagent-driven-development`; writes need approved isolated worktrees. |
| Isolated checkout setup / finish implementation | `using-git-worktrees` / `finishing-a-development-branch`; no implicit merge, cleanup, push or deployment. |
| Behavior-preserving simplification | `code-simplification`; assigned/requested only, reverify changes. |
| External upstream contribution | `preparing-upstream-pr`; publication separately authorized. |
| General docs / subsystem contract | `documentation-standards` / `codify-subsystem`; discover sibling `<module>.SPEC.md`, governing `SPEC.md` and manifest. |
| Ask-versus-act design / informed consent | `delegation-oversight` / `approval-confirmation`; standalone entry, never runtime permission. |
| Uncertainty communication / interface copy | `trust-calibration` / `ux-writing`; no required UX parent. |
| Owned polished GUI / third-party restyling | `design-principles` / `layer-theme`; retain theming render, vision and accessibility gates. |
| Quantitative figure / general prose | `tufte` / `writing-clearly-and-concisely`; not interchangeable. |
| Extract reusable method / create or improve skill | `session-to-skill-extractor` / `skill-creator`; extraction assigned/requested, skill work eval-first. |
| Docker / project scaffold / existing knowledge graph | `docker` / `project-init` / `graphify`; independent domain entries. |
| Context discipline / explicit typed local classification | `token-saver` / `laya-integration`; no added routing authority. |

## Canonical owners

| Responsibility | Owner and caller contract |
|---|---|
| Advisory mechanics and external mutable-resource checks | `dispatching-parallel-agents`. Development Mode A passes task graph, read-only scopes and evidence-complete packets; no reciprocal Mode-A loop. |
| Task classification, write/worktree policy, serial integration | `subagent-driven-development`. Keep overlap, approval and isolation gates; setup uses `using-git-worktrees`. |
| Evidence-complete packets and shared completion contract | Hidden `dev-workflow-common`, loaded when requested by another workflow. No second dispatch engine. |
| Review packets, schema and serious-finding verification | `requesting-code-review`. Finishing passes exact candidate/scope/evidence. Required review without permitted artifacts is `NOT_VERIFIED`/blocked, not waived. |
| Evidence gate / closeout coordination | `verification-before-completion` / `finishing-a-development-branch`. Local stop obligations remain; load companions at phase triggers. |
| Quality activity timing | Existing `../quality/control-plan.json`. Skills consume assignments or direct requests; passing tests does not schedule simplification or learning. |
| UX requirements, delegation, consent, recovery, copy, confidence | Respective UX skills. Carry task/user, state, allowed effects, unresolved decision and artifact; load only distinct needed outputs. |
| Retrieval / synthesis / hypotheses / feasibility | `research` / `literature-synthesis` / `hypothesis-tournament` / `heilmeier-catechism`. Carry question, source IDs/locations, findings and limitations; retrieval-only calls return without rerouting. |
| STAMP foundations / Depict grammar | `stamp-base` references, including [shared Depict grammar](stamp-base/references/depict.md). Load exact reference when needed, not whole-base routing. |
| STPA, CAST and STPA-Sec methods and schemas | Respective specialists. Retain steps, IDs, examples and outputs; schemas are not interchangeable. |
| Docs validation / subsystem contract authoring | `documentation-standards` / `codify-subsystem`. Reuse existing specs; discover sibling first and include project root in parent walk. |

Required approval expiry always blocks execution. Reversibility, confidence and prior similar consent cannot authorize a timeout action. Preserve already-authorized work; reminders, remote draft saves and escalation need their own authority. Renew approval after revalidating scope.

## Multi-stage work

- Bug → requested systemic incident investigation → approved preventive analysis: stabilize/debug first, carry evidence into CAST, then select STPA/Sec only for requested next output.
- Interface design → unclear users/modality → approved design → plan: UX returns requirements to design approval; plans use `agnt plans-dir`.
- Literature → requested hypotheses → requested feasibility: preserve source IDs and limitations, not an automatic scientific pipeline.
- STPA → requested security extension: retain model, IDs, assumptions and constraints; add adversarial scenarios without equating schemas.

## Verification and limits

Ten named scenarios under `.pi/skill-evals/` cover R1–R18 and M1–M4 from [approved design](../../../.pi/plans/2026-10-16-task-first-skill-routing-design-plan.md). Baseline weaknesses are source-observed, not model-observed. `tests/test_context_architecture.py` checks operational paths, ownership/gates, catalog and executable spec-discovery fixtures. Existing context-health tests retain budget policy.

Catalog remains 48 discoverable skills plus two hidden helpers (`dev-workflow-common` and `requirement-simplification-review`). Local discovery proxy: 6,988 characters, 1,012 reserve under unchanged 8,000 limit and 1,000 warning threshold. This excludes package skills and actual prompt/path overhead; it is not token accounting. Existing Laya body-size warning remains.

Natural-language selection recall and runtime behavior improvement are not measured. Written scenarios/static checks establish instruction consistency, not selection accuracy. Deterministic `routing-smoke` checks model-routing infrastructure, not this outcome map. No hidden-skill changes, model experiments, Laya changes, scheduler/router runtime, dependencies or automatic deployment are introduced.
