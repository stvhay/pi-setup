# Harness Quality Governance Kernel Implementation Plan

**Issue:** `pi-rxo3` — Build harness quality governance kernel
**Design:** Approved interactive architecture synthesis recorded in this plan
**Date:** 2026-08-13
**Branch:** `main` (direct-work default; one Bead and fresh Pi session per slice)

**Goal:** Replace overlapping quality triggers, findings, authority copies, and review paths with one small harness-wide governance/evidence kernel that can detect, analyze, authorize, execute, and validate improvements without making Langfuse, Pi extensions, or external packages governance authorities.

**Architecture:** A Git-tracked control plan and deterministic `agnt_lib.quality` kernel govern inner, work-item, cohort, system, and ad-hoc loops. Thin Pi lifecycle hooks capture local evidence; existing skills and reviewers supply contextual judgment; Beads holds durable work and human authority; existing invocation/result artifacts and private runtime evidence hold execution facts. `assess()` emits a decision receipt and at most one work packet; `apply()` revalidates that receipt and delegates effects through existing action/work/approval adapters. Long-lived scheduling remains outside this repository.

**Acceptance Criteria:**
- [ ] One validated control plan defines all quality activities with source, input, trigger, owner, method, output, receiver, acceptance rule, evidence, budget, escalation, and retirement condition.
- [ ] Direct session/Bead correlation and closeout use local private state as authority; Langfuse unavailability cannot prevent session start or direct closeout.
- [ ] The kernel supports `disabled`, `observe`, `canary`, and `autonomous` envelopes; `human` remains a routing outcome, not a maturity stage.
- [ ] Authority equals the intersection of hard policy, one resolved human Beads grant, action effects, demonstrated capability, current evidence, and remaining budget. Unknown authority fails closed.
- [ ] Assessment accounts for failure probability × consequence, expected benefit, information value, resource cost, reversibility, and uncertainty without a composite quality score.
- [ ] Bounded semantic review is automatic when due, but reviewer judgment cannot authorize its own proposed mutation.
- [ ] One actionable Finding core and EvidenceRef contract replaces independent review, health, and improvement finding shapes while preserving domain-specific fields.
- [ ] Existing retrospective, skill-extraction, lifecycle-review, simplification, verification, and code-review methods remain direct methods or activity adapters; duplicate trigger ownership is removed.
- [ ] Core metrics never exceed 12, state missingness explicitly, retain zero-tolerance privacy/authority guards, and link each metric to a decision and retirement condition.
- [ ] Normal quality work stays within 5–10% of measured resources; high-consequence work may use up to 20%; budget exhaustion suppresses or escalates work rather than being hidden.
- [ ] Autonomous effects require a current exact capability grant, per-action revalidation, bounded reversibility, evidence capture, a stop rule, and automatic revocation on critical failure, drift, or missing proof.
- [ ] Concurrent application of one receipt or grant allowance yields at most one durable claim and one dispatch attempt through an atomic private claim; uncertain claim state fails closed. Exactly-once external effect is claimed only when the adapter supplies idempotency or transactional semantics.
- [ ] Post-change cohorts mark findings validated, recurrent, or still monitoring; recurrence can revoke authority and create or deduplicate sanitized follow-up work.
- [ ] Langfuse, pi-langfuse, pi-archimedes, observational memory, BetterWright, editor, and scheduler integrations remain replaceable adapters. None may authorize work, close Beads, or override deterministic local state.
- [ ] No background daemon, scheduler, service protocol, TUI lifecycle manager, vendorized external extension, parallel work registry, or new model-facing typed tool is added.
- [ ] Superseded maintenance modes, copied approval booleans, finding schemas, trigger prose, package-private imports, and version-locked patches are removed when their replacements are proven.

**Verification Command(s):**
```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt eval run quality-process-smoke
git diff --check
```

---

## Authorization and baseline

This plan and its Beads graph do not authorize implementation, deployment, push, upstream mutation, package publication, or external scheduling. Start each implementation Bead only after separate approval through `agnt work direct-start <id> [--claim]`; commit and close it under the workflow active at that time.

Planning baseline contains unrelated or pre-existing state that every slice must preserve:

- `.pi/plans/2026-08-13-agnt-surface-seam-audit-results.md` — user-owned unstaged decision.
- `.beads.gate.lock`, `.pi/deploy-previews/`, and `.pi/skill-evals/runtime-package-patch-projection/` — untracked artifacts owned by open bug `pi-oafb`.
- `.worktrees/feature/pi-ffrh-4-improvement-monitoring` at `6da01e3` — concurrent historical worktree; do not edit, delete, merge, or treat it as current source.
- `main` already contains runner removal commit `231b601`; retired runner/service files must stay absent. `graphify-out/graph.json` may retain stale pre-removal edges, so verify every graph result in current source.

Existing `pi-z49l` is reused for explicit-success closeout, `pi-fvyo` completes its final instruction compaction, and `pi-oafb` owns dirty-artifact root causes. Quality-kernel local-authority work begins only after all three are complete.

## Scope and non-goals

### In scope

- Harness-wide quality policy with project adapters.
- Local capture, decision receipts, risk/utility assessment, review assignment, authority, application, monitoring, and retirement.
- Inner, work-item, cohort, system, and ad-hoc loops sharing one governance/evidence contract.
- Automatic detect/analyze/promote/execute within a human-granted capability ceiling.
- Human review, annotation, adjudication, authorization, modification, takeover, and acceptance adapters.
- Replacement and deletion of overlapping internal machinery.
- Stable public port proposals for pi-langfuse and pi-archimedes, with active migration after exact maintained-fork provenance and contract verification. Maintained source lives in pinned `stvhay` fork commits; tracked patches are derived deployment projections onto exact npm bases. Optional upstream submission and release follow separately without blocking local delivery.

### Out of scope

- ISO 9001 certification, clause-by-clause QMS, certification claims, or a parallel document registry.
- Production deployment, remote Git mutation, releases, external-account changes, or upstream changes without separate approval.
- A daemon, timer, worker service, message bus, scheduler protocol, or background Pi process in this repository.
- A universal human/agent mega-schema, universal workflow engine, or new model-facing quality tool.
- Treating telemetry, a reviewer, a model, a skill, observational memory, or an external service as authority.
- Optimizing a composite quality score.

## Approved architecture

### One kernel, direct local methods

All loops share one policy, evidence model, decision receipt, authority calculation, and state transition contract. They differ only by trigger and evidence horizon:

| Loop | Typical trigger | Evidence horizon | Execution style |
|---|---|---|---|
| Inner | tool result, edit guard, verification phase | current action/turn | direct local guard or method; no queue hop |
| Work-item | direct closeout or accepted result | one session/Bead | capture now; assess now or mark due |
| Cohort | recurrence, enough comparable samples | matched invocations/work items | bounded semantic review and monitoring |
| System | signal threshold plus periodic backstop | architecture, capability, context, quality system | externally invoked `assess`/`apply` |
| Ad hoc | explicit human/agent request | declared scope | same assignment, receipt, authority, and result contracts |

Direct controls such as validation, edit guards, verification, redaction, and approval checks remain direct. Kernel does not turn every check into a Bead or model review.

### Runtime entities and stores

Keep five runtime entities:

1. **BeadNode** — durable task, dependency, question, approval, blocker, grant, and closeout state.
2. **Invocation** — requested action, context/evidence refs, model/thinking/toolset, allowed effects, acceptance, and policy fingerprint.
3. **Result** — outcome, evidence, effects, gaps, checks, and follow-ups.
4. **Finding** — one actionable, status-bearing claim with severity, evidence refs, verification, and proposed intervention.
5. **EvidenceRef** — bounded pointer plus source, availability, integrity/provenance, sensitivity, and retention class.

`PolicyBaseline` is Git-tracked configuration, not another runtime entity.

| Store | Owns | Must not own |
|---|---|---|
| Git | control plan, hard policy, schemas, code, docs, evals, approved baselines | raw private session content or live grants |
| Private runtime | raw observations, local session links/results, semantic packets, decision receipts, capability evidence, cohort state | public work descriptions or hidden mutation authority |
| Beads | sanitized findings/work, dependencies, human decisions, exact capability grants, authority state | transcripts, secrets, copied telemetry payloads |
| Invocation/result/metrics artifacts | execution request/result facts, costs, model/tool/effect dimensions, evidence refs | human authorization |
| Langfuse | optional trace/observation/score/annotation evidence and reviewer queues | session/Bead authority, effect permission, closeout |
| Observational memory | bounded recall evidence for later context | governance or durable task state |

Private ledger or Beads unavailability stops automatic effects. Optional evidence-adapter failure becomes an explicit gap, not proof of success and not a closeout blocker when authoritative local evidence is complete.

### Quality activity control plan

Track one validated JSON plan at `pi/agent/quality/control-plan.json`; document invariants in `pi/agent/quality/SPEC.md`. Every activity has exactly these fields:

```text
id, source, inputs, trigger, owner, method, output, receiver,
acceptanceRule, evidence, budget, escalation, retirementCondition
```

Initial activities:

| Activity | Purpose | Replaces or absorbs |
|---|---|---|
| `capture` | Record minimal local invocation/result/evidence facts at lifecycle boundaries. | implicit closeout-only capture and Langfuse-required session state |
| `work-learning` | Find user friction, avoidable failure, repeated correction, skill/tool gaps, and reusable learning. | `improvement-review`, `workflow-retro`, eligible parts of `design-review`, session retrospective triggers |
| `architecture-coherence` | Detect boundary drift, duplication, context overlap, stale policy, and simplification opportunities. | `architecture-review`, `context-health` checkpoint, `simplification` checkpoint, remaining design-review triggers |
| `capability-calibration` | Qualify model/thinking/tool/action envelopes and revoke drifted authority. | disconnected routing/thinking calibration and agent lifecycle review triggers |
| `quality-system-review` | Audit activity coverage, stale modes, metrics, interventions, budgets, and the kernel itself. | ad-hoc maintenance review of the review system |

Current specialized methods stay where they are useful:

- `retrospective` supplies work-learning judgment.
- `session-to-skill-extractor` proposes skill intervention only after recurrence and coverage checks.
- `agent-retrospective-loop` supplies capability lifecycle review.
- `requirement-simplification-review` and `code-simplification` supply architecture-coherence methods.
- code review, verification, approval confirmation, delegation oversight, and failure choreography remain direct methods.

The control plan owns trigger timing and receiver selection. Skills do not own hidden counters or schedule themselves.

### Decision flow

```text
capture facts
  -> derive deterministic signals and gaps
  -> select one due activity
  -> assess risk, utility, capability, budget, and authority
  -> emit one immutable decision receipt and at most one work packet
  -> contextual reviewer or human returns typed result when needed
  -> re-assess/revalidate immediately before effect
  -> apply through existing Beads/action/work/approval adapters
  -> monitor matched cohort
  -> validate, recur/revoke, or retire
```

`assess()` is deterministic for a fixed snapshot and control-plan version. It reads bounded facts and emits:

- activity and trigger reason;
- EvidenceRefs and explicit gaps;
- risk estimate and uncertainty;
- expected benefit, information value, expected loss, and resource cost;
- capability evidence and applicable grant;
- selected mode and human-routing reason, if any;
- budget debit/remaining allowance;
- deduplication key;
- zero or one proposed work packet.

`apply()` accepts only a current receipt. It re-reads policy, Beads decision/grant state, effects, budget, evidence, target identity, and deduplication state. It may:

- record an observe/no-op receipt;
- write one private review assignment;
- create or deduplicate one sanitized Bead;
- create one durable human blocker;
- dispatch one existing action/work packet within current authority.

It never edits repository files directly and never grants itself authority.

### Risk, reward, uncertainty, and budgets

Start with an inspectable decision tree, not a fitted model:

```text
expectedLoss = probabilityOfFailure * consequence
expectedUtility = expectedBenefit + informationValue - expectedLoss - resourceCost
```

Use coarse versioned bands with evidence refs. Consequence considers affected trust boundary, data/privacy/security, external effects, reversibility, blast radius, and recovery. Capability confidence considers exact action, effect set, model/version, thinking level, toolset, context/policy version, proof requirements, and prior accepted results. Uncertainty can independently force `observe`, `disabled`, or `human` even when point expected utility is positive.

Bounded reversible instrumented errors are allowed only in `canary` with a declared hypothesis, evidence capture, stop rule, error budget, and known recovery. Safety, authority, privacy, and correctness remain hard constraints; expected reward cannot trade them away.

Resource ceilings:

- normal work: quality activity consumes at most 5–10% of measured tokens/cost/latency or equivalent invocation share;
- high-consequence work: up to 20%;
- unknown measurement: no autonomous budget claim;
- exhausted budget: suppress low-value work, keep guards, or route a bounded exception to human authority.

### Capability envelopes and authority

Capability modes apply to an exact envelope, not globally to a model:

| Mode | Effects |
|---|---|
| `disabled` | Minimal required evidence capture only. |
| `observe` | Analyze and emit receipts; all proposed mutation is suppressed. |
| `canary` | Execute bounded reversible monitored effects under stop/error budgets. |
| `autonomous` | Detect, analyze, promote, and execute within exact current grant after per-action revalidation. |
| `human` | Routing outcome for blocked intent, authority, capability, or uncertainty; not a maturity stage. |

Typical progression is `disabled -> observe -> canary -> autonomous`. Failure or drift may return directly to `observe`, `disabled`, or `human`.

A human grants the initial ceiling through one resolved Beads approval whose payload fingerprints:

```text
action + allowed effects + model/version + thinking level + toolset +
context/policy version + proof requirements + rollout ceiling + expiry
```

Automatic use, evidence accumulation, and revocation occur below that ceiling. Expansion or changed fingerprints require a new human grant. Critical failure, drift, expiry, policy mismatch, evidence loss, or missing proof revokes automatic authority.

Effective authority is the intersection of:

1. hard versioned policy;
2. one current resolved human Beads grant;
3. action template `allowedEffects`;
4. demonstrated exact-envelope capability;
5. current evidence completeness and uncertainty;
6. current budget and rollout/error ceiling.

No copied `metadata.pi.approved` or `humanApproval` boolean/object is authoritative. Invocation provenance references the resolved decision/grant Bead.

### Contextual review and human actions

Deterministic extraction identifies facts, counts, gaps, and candidate sessions. It cannot infer why a user corrected an agent or whether a workflow choice was causally poor. A bounded contextual reviewer receives a private assignment with scope, EvidenceRefs, rubric, output contract, and stop rules. Reviewer proposes Findings and interventions; a separate deterministic pass validates evidence and authority.

Human action categories remain distinct:

| Human action | Agent analog | Adapter and authority semantics |
|---|---|---|
| Specify | requirements elicitation | `ask` for session-only exploration; `ticket_question` only for durable/blocking decision |
| Annotate | label, score, comment, corrected output | Langfuse queue or validated editor artifact; evidence only |
| Review | inspect against rubric | agent/subagent, human queue, or editor assignment; proposes Findings |
| Adjudicate | choose between conflicting findings/options | durable `ticket_question`; answer constrains next assessment but does not grant effects |
| Authorize | grant exact consequential scope | `ticket_approval`; only resolved human-UI Beads grant can authorize |
| Modify | narrow or change proposed scope | reject/cancel old preview and issue a new exact request; never mutate an old approval into broader authority |
| Take over | perform action directly | BetterWright live takeover, Nvim/editor, or manual work; returns evidence/result, not automatic acceptance |
| Accept | confirm result meets acceptance rule | result verification/Bead closeout; cannot retroactively authorize an unapproved action |

`ticket_gateway` remains limited to list/show/tree/create_draft. Nvim remains a path-safe process handoff. BetterWright typed browser results remain evidence. Langfuse manual scores and comments remain evidence. Adapters normalize into assignment/results; they do not become parallel workflows.

### Core metrics

No composite score. Keep at most these 12 core metrics, each with owner, type, numerator/denominator, missingness, decision, cadence, gaming risk, and retirement rule:

1. gate conformance;
2. accepted outcome rate;
3. recurrence/escape rate;
4. verified finding precision;
5. reviewer calibration;
6. settled review coverage;
7. telemetry/evidence completeness;
8. privacy violation count — zero tolerance;
9. unauthorized mutation count — zero tolerance;
10. marginal quality spend per confirmed improvement;
11. human attention allocation;
12. corrective-action effectiveness.

Unknown, incomplete, lower-bound, or biased evidence remains explicit and cannot be counted as success. Guard metrics are alarms, not optimization targets.

### External seams

| Boundary | External owner | Stable port required by pi-setup | Forbidden coupling |
|---|---|---|---|
| Pi core | lifecycle/session/tool event delivery | documented session IDs, event ordering, custom private state/evidence refs | policy in TypeScript lifecycle coordinator |
| pi-archimedes | peer execution and result reporting | exported result/limits/termination types, `details.results[]`, child trace/session refs, public bus payloads | private package-layout resolution, duplicate local result types, execution reimplementation |
| pi-langfuse | lifecycle capture, redaction, export | bounded observation capture port with completion/gap result | imports from `src/langfuse.js`, `src/redaction.js`, or `src/utils.js` |
| Langfuse service | optional traces, observations, scores, annotations | bounded evidence query plus completeness/gaps; annotation queue import/export | authority, Bead closeout, hidden required startup dependency |
| Beads | durable work/decisions/grants | list/show/create/update/dependency/close semantics and resolved decision provenance | copied second authority registry |
| BetterWright | browser policy, proof, credentials, human view/takeover | typed action/proof/result refs | browser automation inside quality kernel |
| Observational memory | package-local compaction/recall | typed observation/reflection refs | trigger/authority/governance state |
| Editor/Nvim | external artifact inspection/edit | relative artifact path and validated returned result | treating file save as approval |
| External scheduler | cadence/backstop invocation | stable `agnt quality assess/apply --json` contract and exit classes | importing `agnt_lib`, repository daemon/service |

Crossing a package boundary is allowed only to establish a small public contract. Do not copy an extension into pi-setup. Maintained source lives in exact `stvhay` fork branches pinned through `forks/pi-langfuse` and `forks/pi-archimedes` gitlinks. Tracked version-locked patches are derived deployment artifacts that project those commits onto exact upstream npm bases; provenance, zero-fuzz apply/reverse, and package tests must bind both layers. Optional upstream submission lives in deferred epic `pi-vzqq`; a later reviewed release may replace active projections but does not gate local adoption.

## Replacement map

| Current machinery | Target disposition |
|---|---|
| Langfuse-backed session link/outcome used by direct closeout | local private authority record; optional best-effort Langfuse projection |
| `MAINTENANCE_MODES` and `maintenance.py` | validated five-activity control plan plus `quality.assess/apply`; delete after migration |
| `agnt work maintenance due/create-beads` | temporary compatibility adapter, then remove after callers/docs migrate |
| review.py, health.py, improvement.py finding shapes | one shared Finding/EvidenceRef core with domain extensions |
| separate deterministic scan plus manually supplied decisions file | automatic bounded private review assignment and validated result |
| mandatory human promotion in `improve promote` | policy-driven observe/canary/autonomous/human result, constrained by grant |
| `metadata.pi.approved` plus copied `humanApproval` | resolved grant/decision reference read from Beads at use time |
| retrospective and review skill trigger prose | one control-plan trigger owner; skills retain methods only |
| Langfuse projection required at `session_start` | optional adapter with explicit gaps |
| pi-langfuse package-private imports and patch | maintained-fork public capture/evidence port; delete private imports now, retain only fork-derived deployment patch still required |
| pi-archimedes private layout and duplicate types plus patch | maintained-fork public result/bus types; delete private layout/types now, retain only fork-derived deployment patches still required |

## Dependency graph

Epic: `pi-rxo3`. Existing prerequisites are external to the epic. Maintained-fork verification Beads Q18V and Q19V gate Q20 and Q21 on exact fork/gitlink plus derived patch evidence, not upstream PR or release timing. Optional upstream submission Beads `pi-rxo3.29` and `pi-rxo3.31` are deferred children of separate epic `pi-vzqq` and have no dependency edge into this graph.

| Alias | Bead | Alias | Bead | Alias | Bead |
|---|---|---|---|---|---|
| Q1 | `pi-rxo3.1` | Q2 | `pi-rxo3.2` | Q3 | `pi-rxo3.3` |
| Q4 | `pi-rxo3.4` | Q5 | `pi-rxo3.5` | Q6 | `pi-rxo3.6` |
| Q7 | `pi-rxo3.7` | Q8 | `pi-rxo3.8` | Q9A | `pi-rxo3.9` |
| Q9B | `pi-rxo3.10` | Q9C | `pi-rxo3.11` | Q10 | `pi-rxo3.12` |
| Q11 | `pi-rxo3.13` | Q12 | `pi-rxo3.14` | Q13A | `pi-rxo3.15` |
| Q13B | `pi-rxo3.16` | Q14 | `pi-rxo3.17` | Q15 | `pi-rxo3.18` |
| Q16 | `pi-rxo3.19` | Q17 | `pi-rxo3.20` | Q18 | `pi-rxo3.21` |
| Q18F | `pi-rxo3.22` | Q18V | `pi-rxo3.30` | Q19 | `pi-rxo3.23` |
| Q19F | `pi-rxo3.24` | Q19V | `pi-rxo3.32` | Q20 | `pi-rxo3.25` |
| Q21 | `pi-rxo3.26` | Q22 | `pi-rxo3.27` | | |

```text
Q1   <- pi-z49l, pi-fvyo, pi-oafb
Q2   <- Q1
Q3   <- Q2
Q4   <- Q3
Q5   <- Q4
Q6   <- Q4
Q7   <- Q5, Q6
Q8   <- Q7
Q9A  <- Q8
Q9B  <- Q8
Q9C  <- Q8
Q10  <- Q4
Q11  <- Q10
Q12  <- Q9A, Q11
Q13A <- Q12
Q13B <- Q13A
Q14  <- Q13B
Q15  <- Q14
Q16  <- Q15
Q17  <- Q9B, Q9C, Q16
Q18  <- Q8
Q18F <- Q18; stabilize maintained pi-langfuse fork and private draft packets
Q18V <- Q18F; verify fork/gitlink plus derived package projection
Q19  <- Q6
Q19F <- Q19; stabilize maintained pi-archimedes fork and private draft packets
Q19V <- Q19F; verify fork/gitlink plus derived package projections
Q20  <- Q16, Q18V
Q21  <- Q16, Q19V
Q22  <- Q17, Q20, Q21
```

Graph is acyclic. Q9B and Q9C are optional-adapter branches that rejoin at final internal documentation/eval work. Q18 and Q19 have no semantic dependency but must not run concurrently because current contract tests share files.

## Implementation tasks

Every task uses TDD for behavior, `verification-before-completion`, active Ponytail full, and one fresh Pi session. Run `git status --short --untracked-files=all` before edits. Do not parallelize tasks that share `quality.py`, `improvement.py`, `work.py`, or the control plan.

### Q1: Localize direct-work authority state [Depends on: `pi-z49l`, `pi-fvyo`, `pi-oafb`]

**Context:** Reuse explicit-success closeout, but stop reading authoritative session/Bead/outcome state from Langfuse. Represent a direct session as local Invocation/Result rows in one private append-only ledger; keep Langfuse projection optional. Expose the minimal JSON `agnt quality capture` adapter needed by Q2; assessment commands wait for Q3.

**Files:**
- Create: `pi/agent/bin/agnt_lib/quality.py`
- Modify: `pi/agent/bin/agnt_lib/improvement.py`, `pi/agent/bin/agnt_lib/work.py`, `pi/agent/bin/agnt`
- Test: `tests/test_quality.py`, `tests/test_improvement.py`, `tests/test_agnt.py`, `tests/test_cli_nameerrors.py`
- Docs: `pi/agent/bin/README.md`, `docs/AGNT-SYSTEM.md`, `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Write tests proving local link/outcome readback, append-only atomic private writes, same-session/same-Bead checks, and fail-closed local-ledger errors.
2. Prove direct start/status/closeout work with Langfuse unavailable and still reject missing/mismatched local authority.
3. Reuse `resolve_runtime_directory`; store no transcript body, secret, absolute path, or public Bead description.
4. Add only `agnt quality capture --json` for local lifecycle/closeout facts; reject unknown fields and unsafe evidence.
5. Project link/outcome to Langfuse best-effort with explicit gap evidence; never reverse authority order.
6. Keep `agnt improve scan/review` service behavior separate.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_agnt.py -k 'direct or session or closeout' tests/test_improvement.py -k 'session_outcome or work_item'
```

### Q2: Make lifecycle capture local-first [Depends on: Q1]

**Context:** Capture minimal root-session settlement through a thin Pi lifecycle adapter. Remove the root interactive capture responsibility and mandatory projection startup check from the subagent observer; keep peer metrics/provider-circuit logic there.

**Files:**
- Create: `pi/agent/extensions/quality-lifecycle.ts`
- Modify: `pi/agent/extensions/subagent-error-workaround.ts`, `pi/agent/extensions/langfuse-config-env.ts`
- Test: `tests/test_quality_lifecycle.py`, `tests/test_subagent_workaround.py`, `tests/test_langfuse_evaluators.py`
- Docs: `docs/ARCHITECTURE.md`, `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Test session startup and `agent_settled` with local capture available and the pi-langfuse package or service absent.
2. Call Q1's `agnt quality capture --json` through existing `run-agnt-json.ts`; pass IDs/refs and structural facts, not prompt/output bodies.
3. Guard pi-langfuse package resolution/registration and service capture. Record explicit local evidence gaps instead of rejecting startup.
4. Retain best-effort bounded pi-langfuse observation capture when available.
5. Delete moved interactive state/handlers from `subagent-error-workaround.ts`; do not duplicate provider/subagent logic.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality_lifecycle.py tests/test_subagent_workaround.py tests/test_langfuse_evaluators.py
```

### Q3: Add control plan and observe kernel [Depends on: Q2]

**Context:** Add the one deterministic entry point. Initial policy permits only `disabled` and `observe`; `apply` records receipts or one private assignment and cannot mutate Beads/workspace.

**Files:**
- Create: `pi/agent/quality/control-plan.json`, `pi/agent/quality/SPEC.md`
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt`
- Test: `tests/test_quality.py`, `tests/test_cli_nameerrors.py`, `tests/test_context_architecture.py`
- Docs: `pi/agent/bin/README.md`

**Steps:**
1. Validate exact activity fields, IDs, trigger inputs, budgets, escalations, and retirement conditions with unknown-field rejection.
2. Implement deterministic `assess(snapshot, activity)` and receipt persistence; same snapshot/policy must produce same decision/dedupe key.
3. Emit at most one work packet; unknown evidence or policy mismatch cannot authorize effects.
4. Extend Q1's capture-only CLI with stable JSON `quality assess`, `quality apply`, and `quality status`; no typed model tool.
5. Add SPEC invariants, failure modes, and adapter boundaries.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_cli_nameerrors.py tests/test_context_architecture.py -k 'quality or runner'
pi/agent/bin/agnt quality assess --help
```

### Q4: Replace maintenance mode machinery [Depends on: Q3]

**Context:** Migrate durable signal collection and deduplication into five activities, preserve old command only during the slice, then delete `maintenance.py` and its six-mode registry.

**Files:**
- Delete: `pi/agent/bin/agnt_lib/maintenance.py`, `tests/test_maintenance.py`
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/work.py`, `pi/agent/bin/agnt`
- Test: `tests/test_quality.py`, `tests/test_agnt.py`, `tests/test_context_architecture.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `docs/ARCHITECTURE.md`, `pi/agent/bin/README.md`

**Steps:**
1. Port only proven Beads/Git/run/health/context/eligible-session signals and lower-bound/unknown behavior.
2. Map six old labels to new activities for reading/deduplication; create only new activity labels.
3. Replace callers/docs with `agnt quality assess/apply` and remove `agnt work maintenance` after compatibility tests prove no active caller.
4. Preview exact tracked deletions with HEAD recovery paths before staging.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_agnt.py tests/test_context_architecture.py -k 'quality or maintenance or runner'
! test -e pi/agent/bin/agnt_lib/maintenance.py
! rg -n 'MAINTENANCE_MODES|work maintenance' pi/agent/bin/agnt_lib pi/agent/bin/README.md docs/SELF-IMPROVEMENT.md docs/ARCHITECTURE.md
```

### Q5: Consolidate quality trigger ownership [Depends on: Q4]

**Context:** Keep specialized skill methods, but remove overlapping counters, cadence rules, automatic issue creation, and promotion rules from prose. Bind each method to one control-plan activity.

**Files:**
- Modify: `pi/agent/skills/retrospective/SKILL.md`, `pi/agent/skills/session-to-skill-extractor/SKILL.md`, `pi/agent/skills/agent-retrospective-loop/SKILL.md`, `pi/agent/skills/requirement-simplification-review/SKILL.md`, `pi/agent/skills/code-simplification/SKILL.md`
- Modify: `pi/agent/quality/control-plan.json`, `docs/SELF-IMPROVEMENT.md`
- Test: `tests/test_context_architecture.py`, relevant skill eval scenarios only where trigger behavior changes

**Steps:**
1. Inventory each skill's trigger, evidence, decision, effect, and receiver.
2. Delete duplicate trigger/cadence/promotion ownership; retain judgment methods and direct invocation.
3. Make session closeout minimal capture deterministic; aggregate review remains signal-plus-backstop.
4. Confirm no skill grants mutation or creates a competing finding/work registry.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py
pi/agent/bin/agnt context-health --strict
```

### Q6: Introduce shared Finding and EvidenceRef core [Depends on: Q4]

**Context:** Define the smallest common fields and adapters for code-review and health findings. Domain-specific fields remain extensions; no universal result mega-schema.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/review.py`, `pi/agent/bin/agnt_lib/health.py`, `pi/agent/bin/agnt_lib/metrics.py`
- Test: `tests/test_quality.py`, `tests/test_review.py`, `tests/test_health.py`
- Docs: `pi/agent/quality/SPEC.md`, `docs/RUN-ARTIFACTS.md`

**Steps:**
1. Define common finding identity, activity/source, category, severity, claim, status, EvidenceRefs, verification, and proposed intervention.
2. Define EvidenceRef availability, provenance/integrity, sensitivity, retention, and bounded pointer rules.
3. Adapt review and health output without losing their domain fields or breaking existing metrics consumers.
4. Reject copied raw private evidence on public Finding paths.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_review.py tests/test_health.py
```

### Q7: Migrate improvement findings to shared core [Depends on: Q5, Q6]

**Context:** Preserve bounded private scan, sanitized promotion, and cohort state while replacing improvement.py's independent finding lifecycle with shared Finding/EvidenceRef validation.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`, `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/langfuse/improvement-review.md`
- Test: `tests/test_improvement.py`, `tests/test_quality.py`, `tests/test_review.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `pi/agent/quality/SPEC.md`

**Steps:**
1. Add compatibility parsing for existing private policy-v2 packets and monitoring state.
2. Emit shared Findings with private EvidenceRefs; sanitize only at Beads boundary.
3. Keep event -> incident -> pattern -> change distinction and explicit unknown attribution.
4. Remove duplicate finding constants/validators after migration tests pass.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py tests/test_quality.py tests/test_review.py
```

### Q8: Automate bounded semantic review [Depends on: Q7]

**Context:** Replace the manual “ask an agent to inspect session history” step with deterministic assignment generation, contextual judgment, and deterministic result validation. Keep mutation separate.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/improvement.py`, `pi/agent/bin/agnt_lib/actions.py`
- Create or modify: one private-review action/rubric under `pi/agent/actions/` or `pi/agent/langfuse/` only if existing `review` action cannot express the contract
- Test: `tests/test_quality.py`, `tests/test_improvement.py`, `tests/test_agnt.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `pi/agent/quality/SPEC.md`

**Steps:**
1. Generate one ReviewAssignment with bounded scope, EvidenceRefs, rubric, model/privacy constraints, output contract, and stop rules.
2. Route only through demonstrated reviewer capability; private evidence never goes to an unauthorized provider.
3. Validate returned Findings against exact assignment/evidence; reviewer cannot set grant, mode, or effect authority.
4. Mark unavailable, timed-out, privacy-uncertain, or schema-invalid review as a gap/human route; do not silently retry paid work.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_improvement.py tests/test_agnt.py -k 'review or assignment or finding or action'
pi/agent/bin/agnt action validate
```

### Q9A: Normalize agent, ticket, and interview results [Depends on: Q8]

**Context:** Normalize agent review results plus `ask`/durable ticket interview and adjudication results without combining review, answer, acceptance, and authorization semantics.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/approvals.py`, `pi/agent/bin/agnt_lib/gateway.py`
- Modify only if required by a proven schema gap: `pi/agent/extensions/beads-ask-bridge.ts`
- Test: `tests/test_quality.py`, `tests/test_approvals.py`, `tests/test_ticket_gateway.py`
- Docs: `pi/agent/quality/SPEC.md`, `docs/AGNT-SYSTEM.md`

**Steps:**
1. Normalize assigned agent review and transient/durable interview results into typed evidence or adjudication constraints.
2. Keep `ticket_gateway` list/show/tree/create_draft-only and keep transient `ask` state session-local.
3. Preserve review, answer, acceptance, and authorization as distinct categories.
4. Require a new preview/request for modified approval scope.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_approvals.py tests/test_ticket_gateway.py
```

### Q9B: Normalize Langfuse annotation evidence [Depends on: Q8]

**Context:** Import bounded Langfuse human scores/comments/corrected-output references as review evidence. Langfuse remains optional and never grants authority.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/improvement.py`, and `pi/agent/bin/agnt_lib/langfuse.py` only if the service port belongs there after caller review
- Test: `tests/test_quality.py`, `tests/test_improvement.py`, `tests/test_langfuse_evaluators.py`
- Docs: `pi/agent/quality/SPEC.md`, `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Read current Langfuse API documentation before implementation; do not encode remembered UI labels.
2. Normalize annotation queue results through EvidenceRefs with reviewer, rubric/score config, scope, completeness, and gaps.
3. Keep annotation, corrected output, acceptance, and authorization distinct.
4. Treat missing/partial queues as evidence gaps and prohibit authority fields in imported results.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_improvement.py tests/test_langfuse_evaluators.py -k 'annotation or evidence or review'
```

### Q9C: Normalize editor and takeover evidence [Depends on: Q8]

**Context:** Import a validated review artifact or typed takeover result without treating file save, browser action, or manual execution as approval or acceptance.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt`
- Modify only if a proven adapter gap exists: `pi/agent/extensions/nvim.ts`
- Test: `tests/test_quality.py`, `tests/test_process_restart.py`, `tests/test_cli_nameerrors.py`
- Docs: `pi/agent/quality/SPEC.md`, `docs/AGNT-SYSTEM.md`

**Steps:**
1. Validate a narrow assignment-result artifact carrying scope, EvidenceRefs, result category, and provenance.
2. Accept Nvim/editor and BetterWright/takeover outputs only through that result boundary; keep native UX and policy ownership external.
3. Reject absolute/escaping paths, raw private evidence on public paths, and any embedded authority claim.
4. Preserve partial/lost/uncertain state and a resumption path for takeover results.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_process_restart.py tests/test_cli_nameerrors.py -k 'quality or nvim or restart or result'
```

### Q10: Add decision-linked quality metrics [Depends on: Q4]

**Context:** Implement the 12-metric ceiling and self-audit metadata before capability automation can use metrics.

**Files:**
- Modify: `pi/agent/quality/control-plan.json`, `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/metrics.py`
- Test: `tests/test_quality.py`, `tests/test_review.py`
- Docs: `pi/agent/quality/SPEC.md`, `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Add explicit metadata for each metric: owner, type, numerator, denominator, missingness, decision, cadence, gaming risk, retirement.
2. Derive metrics from existing receipts, results, annotations, and monitoring; create no second metrics store.
3. Enforce 12 maximum and zero-tolerance guard handling.
4. Keep unknown/lower-bound data out of success numerators.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_review.py
```

### Q11: Add risk, utility, and budget assessment [Depends on: Q10]

**Context:** Add a versioned coarse decision tree. Start simple; no fitted probability model or optimization score.

**Files:**
- Modify: `pi/agent/quality/control-plan.json`, `pi/agent/bin/agnt_lib/quality.py`
- Test: `tests/test_quality.py`
- Docs: `pi/agent/quality/SPEC.md`

**Steps:**
1. Encode consequence, failure-probability, reversibility, uncertainty, benefit, information-value, and cost bands.
2. Prove hard guards dominate positive expected utility.
3. Enforce normal 5–10% and high-consequence 20% ceilings with explicit unknown behavior.
4. Require canary hypothesis/evidence/stop/error-budget fields for reversible learning actions.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py -k 'risk or utility or budget or canary'
```

### Q12: Store exact capability grants in Beads [Depends on: Q9A, Q11]

**Context:** Use existing approval machinery to issue one human-granted capability ceiling. Grant is durable authority state, not a copied target flag.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/approvals.py`, `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/extensions/beads-ask-bridge.ts`
- Test: `tests/test_approvals.py`, `tests/test_quality.py`
- Docs: `docs/AGNT-SYSTEM.md`, `pi/agent/quality/SPEC.md`

**Steps:**
1. Validate exact envelope fingerprint, rollout ceiling, expiry, proof, and revocation fields in approval preview/decision metadata.
2. Read grant authority from the resolved human-UI decision Bead at use time.
3. Reject conditional/modified scope under an old approval; require reissue.
4. Add automatic expiry/revocation state updates that cannot expand the ceiling.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_approvals.py tests/test_quality.py -k 'grant or approval or capability'
```

### Q13A: Resolve canonical grants at orchestration boundary [Depends on: Q12]

**Context:** Add one canonical grant resolver before changing all consumers. Resolved Beads decision state wins; copied `metadata.pi.approved` and `humanApproval` never establish authority.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/approvals.py`, `pi/agent/bin/agnt_lib/orchestration.py`
- Test: `tests/test_quality.py`, `tests/test_approvals.py`, `tests/test_orchestration.py`
- Docs: `docs/AGNT-SYSTEM.md`, `pi/agent/quality/SPEC.md`

**Steps:**
1. Resolve exact decision/grant Bead with injectable bounded lookup and fail-closed malformed/unavailable state.
2. Validate fingerprint, expiry, revocation, effects, and human-UI provenance at orchestration boundary.
3. Prove copied booleans cannot widen or substitute for canonical grant state.
4. Keep temporary output compatibility for downstream consumers until Q13B.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_approvals.py tests/test_orchestration.py -k 'grant or approval or authority'
```

### Q13B: Migrate dispatch provenance and remove authority copies [Depends on: Q13A]

**Context:** Move run/work/worktree/gateway consumers to canonical grant refs, then delete copied authority writes and compatibility fields.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/approvals.py`, `pi/agent/bin/agnt_lib/orchestration.py`, `pi/agent/bin/agnt_lib/runs.py`, `pi/agent/bin/agnt_lib/work.py`, `pi/agent/bin/agnt_lib/worktree_policy.py`, `pi/agent/bin/agnt_lib/gateway.py`
- Test: `tests/test_orchestration.py`, `tests/test_approvals.py`, `tests/test_runs.py`, `tests/test_worktree_policy.py`, `tests/test_ticket_gateway.py`, `tests/test_agnt.py`
- Docs: `docs/RUN-ARTIFACTS.md`, `docs/AGNT-SYSTEM.md`

**Steps:**
1. Persist only decision/grant refs and effective envelope in invocation provenance.
2. Revalidate the canonical grant immediately before dispatch and guarded worktree effects.
3. Remove approval resolver writes to `metadata.pi.approved`/`humanApproval` and migrate fixtures/callers.
4. Search active source/docs/tests and delete legacy authority branches after all consumers are green.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_orchestration.py tests/test_approvals.py tests/test_runs.py tests/test_worktree_policy.py tests/test_ticket_gateway.py tests/test_agnt.py -k 'approval or authority or dispatch or provenance'
! rg -n 'metadata\.pi\.approved|humanApproval' pi/agent/bin/agnt_lib docs/RUN-ARTIFACTS.md docs/AGNT-SYSTEM.md
```

### Q14: Redesign canary execution around claim/dispatch/settle [Depends on: Q13B]

**Context:** The first Q14 implementation proved policy, grant, revocation, and concurrent-claim mechanics, but coupled durable claims to an external effect under lock. That creates avoidable deadlock/reentrancy risk and cannot guarantee exactly-once external effects without adapter support. This redesign is the Q14 completion target; do not add more lock choreography to the prior shape.

**Interface contract:**
- `claim(receipt)` performs short, atomic admission and returns one claim token or a fail-closed denial.
- `dispatch(packet, claimToken)` runs outside all claims locks and may be attempted at most once for that token.
- `settle(claimToken, result)` performs short, idempotent terminal persistence.
- Crash, timeout, or uncertain persistence leaves `uncertain`; no automatic retry is allowed.
- Exactly-once external effect is available only when the selected adapter accepts the claim token as an idempotency key or supplies an equivalent transaction. Otherwise guarantee at-most-one dispatch attempt, not exactly-once effect.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/runs.py`
- Reuse as adapter seam: `pi/agent/bin/agnt_lib/work.py`
- Test: `tests/test_quality.py`, `tests/test_agnt.py`, `tests/test_runs.py`
- Docs: `pi/agent/quality/SPEC.md`, `docs/SELF-IMPROVEMENT.md`

**Steps:**
1. Replace the effect-wide canary lock and process-global reentrancy marker with one durable claim state machine: `claimed -> dispatched|failed|uncertain|revoked`.
2. Hold the private `fcntl` lock only while claiming or settling; never hold it across an injected dispatcher or existing work/run adapter.
3. Bind `claimId`, receipt identity, grant fingerprint, policy fingerprint, target fingerprint, and bounded effects into dispatch provenance. Downstream adapters receive this context explicitly; they do not infer ownership from process state or recursively call `quality.apply()`.
4. Separate precondition authorization evidence from post-dispatch execution evidence. Resolve and freshness-check required preconditions before claim; resolve and bind execution proof during settlement. Structural refs alone do not prove evidence existence.
5. Revalidate policy, exact grant, target, effects, stop rule, and remaining budget before claim and again immediately before dispatch. If state changes after that boundary, settle uncertain/revoked; do not pretend local state and external effects are atomic.
6. Test concurrent same-receipt and same-grant applies, concurrent budget consumption, crash points before/after dispatch, stale evidence, policy/grant/target drift, recursive dispatch, idempotent settlement, and unknown results.
7. Keep noncritical failures as settled `failed` claims until the grant-scoped error budget is exhausted; revoke on critical failure, drift, expiry, missing proof, unknown result, or stop-rule breach.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_agnt.py tests/test_runs.py -k 'canary or revoke or dispatch or effect or claim or settle or evidence'
```

### Q15: Enable external autonomous quality cycles [Depends on: Q14]

**Context:** Enable detect/analyze/promote/execute under an autonomous grant. Provide an idempotent external scheduler contract; add no scheduler here.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/bin/agnt_lib/work.py`, `pi/agent/bin/README.md`
- Test: `tests/test_quality.py`, `tests/test_agnt.py`, `tests/test_context_architecture.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `docs/ARCHITECTURE.md`, `pi/agent/quality/SPEC.md`

**Steps:**
1. Make `assess/apply --json` idempotent, receipt-bound, and stable for external invocation.
2. Auto-create/deduplicate sanitized Beads and dispatch only one packet within current autonomous grant and Q14's durable claim/idempotency contract; require adapter idempotency before claiming exactly-once external effects.
3. Retire `agnt improve promote` as a primary or independent mutation path after `quality apply` covers manual and automatic creation; keep only a bounded import/repair path if an executable caller remains.
4. Use signal triggers plus periodic backstop inputs supplied by caller; never sleep, poll, or run a service.
5. Return stable no-op/due/needs-review/needs-human/applied/blocked exit classes and gaps.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_agnt.py tests/test_context_architecture.py -k 'autonomous or quality or scheduler or daemon'
```

### Q16: Validate corrections with cohorts [Depends on: Q15]

**Context:** Adapt existing matched post-promotion monitoring to close PDCA. Validation requires enough settled comparable evidence; recurrence can revoke authority and create one deduplicated follow-up.

**Files:**
- Modify: `pi/agent/bin/agnt_lib/improvement.py`, `pi/agent/bin/agnt_lib/quality.py`, `pi/agent/quality/control-plan.json`
- Test: `tests/test_improvement.py`, `tests/test_quality.py`
- Docs: `docs/SELF-IMPROVEMENT.md`, `pi/agent/quality/SPEC.md`

**Steps:**
1. Start monitoring only after linked corrective-action Bead/result succeeds.
2. Match task, risk, context shape, role, model, prompt/policy, and effect dimensions where available.
3. Keep insufficient, incomplete, and lower-bound evidence monitoring.
4. Mark validated/recurrent; recurrence revokes applicable grant and emits at most one sanitized follow-up.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_improvement.py tests/test_quality.py -k 'monitor or cohort or recurrent or validated or revoke'
```

### Q17: Document and evaluate the internal kernel [Depends on: Q9B, Q9C, Q16]

**Context:** Finish internal replacement before upstream package cleanup. Owning tasks Q4, Q5, Q7, Q13B, and Q15 remove superseded code and trigger paths; this bounded slice documents and evaluates the as-built system rather than performing an open-ended cleanup sweep.

**Files:**
- Modify: `docs/ARCHITECTURE.md`, `docs/SELF-IMPROVEMENT.md`, `docs/AGNT-SYSTEM.md`, `docs/RUN-ARTIFACTS.md`, `README.md`, `CONTRIBUTING.md`
- Create: `pi/agent/evals/quality-process-smoke/eval.json` and minimal prompt/fixtures required by current eval format
- Test: `tests/test_context_architecture.py`, `tests/test_quality.py`, deterministic eval tests

**Steps:**
1. Run caller searches only to verify owning tasks removed legacy maintenance, finding, manual-promotion, copied-authority, and trigger paths; file a narrow follow-up instead of widening this slice if a live caller remains.
2. Update docs to describe actual interfaces, no certification claim, and no in-repo scheduler.
3. Add deterministic smoke cases for unknown evidence, observe suppression, grant bounds, one-packet rule, atomic duplicate suppression, and revocation.
4. Run documentation-standards validate mode.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_context_architecture.py tests/test_quality.py
pi/agent/bin/agnt eval run quality-process-smoke
pi/agent/bin/agnt context-health --strict
```

### Q18: Specify public pi-langfuse quality ports [Depends on: Q8]

**Context:** Define the smallest upstream interfaces from proven consumers before upstream implementation. This task changes only pi-setup contract artifacts unless separate upstream approval is granted.

**Files:**
- Create or modify: `.pi/upstream-profiles/github.com--gooyoung--pi-langfuse.md`, a focused tracked port contract under `.pi/plans/` or `docs/`
- Modify: `tests/test_agent_os_compat.py`, `tests/test_package_patches.py` only to express desired public contract without assuming release

**Steps:**
1. Specify bounded observation capture owned by pi-langfuse: redaction, lifecycle, export, completion, and gap result.
2. Specify bounded service evidence query: traces/observations/scores/annotations/completeness/gaps.
3. Exclude authorization, Bead closeout, and pi-setup policy from interface.
4. Record maintained-fork, gitlink, npm-base, derived-patch, and public-export evidence needed by Q18V/Q20; keep optional upstream submission separate and approval-gated.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agent_os_compat.py tests/test_package_patches.py -k 'langfuse'
```

### Q18V: Verify maintained pi-langfuse fork-port evidence [Depends on: Q18F]

**Context:** Verify exact `stvhay/pi-langfuse` fork source pinned through `forks/pi-langfuse`, plus its derived patch projection onto the exact upstream npm base, before Q20 adopts the public capture/evidence contract. Q18F evidence lives in `pi-rxo3.22` and its upstream-ready private packet. Optional upstream submission is deferred under `pi-vzqq` and grants no dependency, deployment, or upstream authority here.

**Files:**
- Modify: Q18's tracked port contract and `.pi/upstream-profiles/github.com--gooyoung--pi-langfuse.md` with exact npm base, maintained-fork base/head, published `stvhay` ref, gitlink, derived patch, and export evidence
- Test: inspect a clean exact-base tarball plus installed projected package in temporary or read-only locations

**Steps:**
1. Verify npm base identity/integrity, reviewed maintained-fork lineage, published immutable `stvhay` ref, superproject gitlink, zero-fuzz derived-patch apply/reverse, package exports, and contract compatibility.
2. Record gaps explicitly; do not close or unblock Q20 on an unpublished fork pin, stale projection, or incomplete public interface.
3. Close only when Q20 can name exact package base, maintained-fork pin, public imports, projection integrity, and rollback source.

**Focused verification:**
```bash
scripts/check-vendor-pins.sh
scripts/apply-pi-package-patches.sh --check
rg -n 'version|integrity|vendor|export|commit|patch' .pi/upstream-profiles/github.com--gooyoung--pi-langfuse.md
```

### Q19: Specify public pi-archimedes result ports [Depends on: Q6]

**Context:** Define public execution evidence needed to delete private layout resolution and duplicate local types. This task changes only pi-setup contract artifacts unless separate upstream approval is granted.

**Files:**
- Create or modify: `.pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md`, a focused tracked port contract under `.pi/plans/` or `docs/`
- Modify: `tests/test_agent_os_compat.py`, `tests/test_subagent_workaround.py`, `tests/test_package_patches.py` only to express desired public contract

**Steps:**
1. Specify exported result, limits, termination, usage, output-contract, child-session/trace, and public bus payload types.
2. Preserve `details.results[]` as execution evidence and Pi `tool_result` as transport.
3. Exclude pi-setup routing, billing, authority, and quality policy from upstream.
4. Record maintained-fork, gitlink, npm-base, derived-patch, and public-export evidence needed by Q19V/Q21; keep optional upstream submission separate and approval-gated.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agent_os_compat.py tests/test_subagent_workaround.py tests/test_package_patches.py -k 'archimedes or subagent'
```

### Q19V: Verify maintained pi-archimedes fork-port evidence [Depends on: Q19F]

**Context:** Verify exact `stvhay/pi-archimedes` fork source pinned through `forks/pi-archimedes`, plus its derived patch projections onto exact upstream npm bases, before Q21 adopts public result, agent-resolution, and typed-bus contracts. Q19F evidence lives in `pi-rxo3.24` and its upstream-ready private packets. Optional upstream submission is deferred under `pi-vzqq` and grants no dependency, deployment, or upstream authority here.

**Files:**
- Modify: Q19's tracked port contract and `.pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md` with exact npm bases, maintained-fork stack base/head, published `stvhay` ref, gitlink, derived patches, and export evidence
- Test: inspect clean exact-base tarballs plus installed projected packages in temporary or read-only locations

**Steps:**
1. Verify npm base identities/integrities, reviewed maintained-fork lineage, published immutable `stvhay` ref, superproject gitlink, zero-fuzz derived-patch apply/reverse, package exports, and result/bus contract compatibility.
2. Record gaps explicitly; do not close or unblock Q21 on an unpublished fork pin, stale projection, or incomplete public interface.
3. Close only when Q21 can name exact package bases, maintained-fork pin, public imports, projection integrity, and rollback sources.

**Focused verification:**
```bash
scripts/check-vendor-pins.sh
scripts/apply-pi-package-patches.sh --check
rg -n 'version|integrity|vendor|export|commit|patch' .pi/upstream-profiles/github.com--danielcherubini--pi-archimedes.md
```

### Q20: Adopt maintained pi-langfuse fork ports [Depends on: Q16, Q18V]

**Context:** Run only after Q18V verifies reviewed maintained-fork source plus its derived npm-base projection exposing Q18 contracts. Migrate consumers in one slice; do not retain both private and public production paths. Keep projection machinery still required by the exact npm base.

**Files:**
- Modify: `pi/agent/extensions/langfuse-config-env.ts`, `pi/agent/extensions/quality-lifecycle.ts`, `pi/agent/extensions/subagent-error-workaround.ts`, `pi/agent/settings.json`, `scripts/update-pi-config.sh`
- Modify/delete: exact pi-langfuse patch application/docs only when Q18V proves a path is no longer needed
- Test: `tests/test_langfuse_evaluators.py`, `tests/test_subagent_workaround.py`, `tests/test_agent_os_compat.py`, `tests/test_package_patches.py`, `tests/test_pi_packages.py`, `tests/test_update_pi_config.py`

**Steps:**
1. Verify Q18V's exact package base, maintained-fork pin, gitlink, derived-patch integrity, rollback source, and public exports before changing imports.
2. Bind tracked package, gitlink, install/reinstall/rollback, and patch logic to that one reviewed projection.
3. Replace all `src/langfuse.js`, `src/redaction.js`, and `src/utils.js` imports with `./quality`.
4. Remove duplicate local consumer/projection paths; retain only patch code still required to materialize the reviewed public port.
5. Prove local quality lifecycle remains authoritative with package/service unavailable and exact-base install rollback still works.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_langfuse_evaluators.py tests/test_subagent_workaround.py tests/test_agent_os_compat.py tests/test_package_patches.py tests/test_pi_packages.py tests/test_update_pi_config.py -k 'langfuse'
! rg -n 'pi-langfuse/.*/src/|src/(langfuse|redaction|utils)\.js' pi/agent/extensions
```

### Q21: Adopt maintained pi-archimedes fork ports [Depends on: Q16, Q19V]

**Context:** Run only after Q19V verifies reviewed maintained-fork source plus derived npm-base projections exposing Q19 contracts. Keep public composition; delete private layout/type copies in the same slice. Keep projection machinery still required by the exact npm bases.

**Files:**
- Modify: `pi/agent/extensions/archimedes.ts`, `pi/agent/extensions/subagent-error-workaround.ts`, `pi/agent/settings.json`, `scripts/update-pi-config.sh`
- Modify/delete: pi-archimedes version-locked patch application/docs only when Q19V proves a path is no longer needed
- Test: `tests/test_agent_os_compat.py`, `tests/test_subagent_workaround.py`, `tests/test_package_patches.py`, `tests/test_pi_packages.py`, `tests/test_update_pi_config.py`

**Steps:**
1. Verify Q19V's exact package bases, maintained-fork pin, gitlink, derived-patch integrity, rollback sources, and exported types/result contract.
2. Bind tracked packages, gitlink, install/reinstall/rollback, and patch logic to that one reviewed projection.
3. Remove package-private agent sibling resolution and duplicate OutputContract/SubagentLimits/result/termination shapes.
4. Keep only pi-setup RPC portability, routing/billing policy, quality normalization, and patch code still required to materialize reviewed public ports.
5. Prove result evidence survives unchanged through Pi transport and local metrics, and exact-base install rollback still works.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_agent_os_compat.py tests/test_subagent_workaround.py tests/test_package_patches.py tests/test_pi_packages.py tests/test_update_pi_config.py -k 'archimedes or subagent'
```

### Q22: Retire obsolete package patch scaffolding [Depends on: Q17, Q20, Q21]

**Context:** Remove only patch machinery with no remaining configured projection. Preserve active maintained-fork-derived patches and generic exact-version, integrity, apply/reverse, rollback, and install safeguards.

**Files:**
- Modify/delete as proven: `scripts/apply-pi-package-patches.sh`, `patches/pi-packages/README.md`, obsolete patch files, compatibility docs/tests
- Test: `tests/test_package_patches.py`, `tests/test_agent_os_compat.py`, `tests/test_context_architecture.py`, `tests/test_update_pi_config.py`, `tests/test_pi_packages.py`
- Docs: `docs/extension-web-compatibility.md`, `docs/ARCHITECTURE.md`

**Steps:**
1. Inventory configured patches and callers at execution time; delete no generic safeguard still in use.
2. Preview exact deleted paths and HEAD recovery SHAs.
3. Verify clean install/update and rollback behavior against exact npm bases plus maintained-fork-derived projections.
4. Record final seam/line-count reduction and close the epic only after full gates.

**Focused verification:**
```bash
.venv/bin/python -m pytest tests/test_package_patches.py tests/test_agent_os_compat.py tests/test_context_architecture.py tests/test_update_pi_config.py tests/test_pi_packages.py
scripts/check-pi-config.sh
git diff --check
```

## File conflicts and execution order

| File/surface | Tasks | Rule |
|---|---|---|
| `agnt_lib/quality.py` | Q1, Q3–Q16 plus Q9 branches/Q13 splits | Follow graph order; never parallelize shared-file edits. |
| `agnt_lib/improvement.py` | Q1, Q7, Q8, Q9B, Q16 | Q7 starts after shared core; Q16 starts after autonomous apply. |
| `agnt_lib/work.py` | existing `pi-z49l`, Q1, Q4, Q13B–Q15 | Existing closeout work lands first; each later task starts green. |
| `subagent-error-workaround.ts` | Q2, Q20, Q21 | Local lifecycle split first; package migrations remain sequential because both edit this file. |
| approvals/orchestration | Q9A, Q12, Q13A, Q13B | Result normalization, grant creation, canonical resolution, then downstream migration. |
| package contract tests | Q18, Q19 | Do not parallelize: both currently edit `tests/test_agent_os_compat.py` and `tests/test_package_patches.py`. |
| control plan/SPEC | Q3, Q5, Q10, Q11, Q16 | Same-file changes are serialized by graph order; each task versions the baseline intentionally. |
| docs | most phases | Update only current contract in each slice; Q17 performs bounded final coherence/eval pass. |

Q18 and Q19 have no semantic dependency but run serially because their current test files overlap. Q20 and Q21 run sequentially because both change `subagent-error-workaround.ts`, package settings, installer logic, and patch tests.

## Per-slice completion contract

1. Confirm exact Bead, dependencies, current source, and unrelated worktree state.
2. Load task-specific skills plus `test-driven-development`; write the smallest failing check first.
3. Read all callers before editing. Prefer deletion/reuse over new wrappers.
4. Run focused RED/GREEN, then Ponytail diff review.
5. Run documentation-standards validate mode for public, architectural, or workflow changes.
6. Stage only task-owned paths; show tracked deletions with recovery SHA.
7. Run stable full project gates once after last task-owned change.
8. Request independent read-only review for Q1–Q4, Q8, Q11–Q16, Q20, and Q21.
9. Commit one atomic task-owned implementation change.
10. Record outcome and close Bead with the direct-closeout interface active at that commit. Non-success stops without handoff.

## Documentation updates

Required as implementation lands:

- `pi/agent/quality/SPEC.md` — kernel purpose, contracts, invariants, failure modes, tests.
- `docs/ARCHITECTURE.md` — as-built owner/seam/store map and no-scheduler boundary.
- `docs/SELF-IMPROVEMENT.md` — operator workflow, private review, grants, cohorts, metrics.
- `docs/AGNT-SYSTEM.md` — direct lifecycle and authority provenance.
- `docs/RUN-ARTIFACTS.md` — Finding/EvidenceRef and decision receipt references.
- `pi/agent/bin/README.md` — exact `agnt quality` CLI.
- `CONTRIBUTING.md` — quality gates and when deterministic quality eval runs.
- `docs/extension-web-compatibility.md` — released public package seams and removed patches.

Do not duplicate implementation tours into README or always-loaded instructions.

## Execution handoff

Plan saved to: `.pi/plans/2026-08-13-harness-quality-governance-kernel-plan.md`.

Next step is Beads graph encoding and graph verification only. Implementation requires separate approval. Recommended implementation skills per slice: `executing-plans`, `test-driven-development`, active Ponytail full, `verification-before-completion`, and `documentation-standards`; use `codify-subsystem` when Q3 writes `pi/agent/quality/SPEC.md`.
