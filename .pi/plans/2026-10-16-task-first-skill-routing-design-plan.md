# Task-first skill routing and responsibility cleanup — proposed design

**Bead:** pi-uz3t

**Date:** 2026-10-16

**Source baseline:** `b24e986b02df4db109b157fbfe81390def9c048b` (`main`)

**Status:** Design deliverable only. Proposed skill/test edits below require separate implementation approval. Saving this proposal does not approve them.

## Goal and boundary

Select skills by the user's requested outcome, then choose an appropriate method. Remove conflicting instructions and stale handoffs before deduplicating procedures. Preserve existing names, natural-language discovery, slash entry points, method outputs, approval/verification gates, and budget policy.

This is instruction coordination, not `agnt route` model selection. No executable router, new umbrella skill, mandatory family gateway, new dependency, package-skill edits, host assignment changes, or discovery hiding. Laya and assignment-driven hiding remain deferred. No deployment, push, real-model routing experiments, or claim of measured selection improvement.

Current authorized deliverable: this design and its source/verification evidence. Future implementation changes only tracked `pi/`, tests, and named scenario files. Live `~/.pi` stays untouched. Preserve unrelated untracked plans:

- `.pi/plans/2026-08-18-telemetry-preproduction-contract-design-plan.md`
- `.pi/plans/2026-10-01-laya-chat-shadow-routing-design-plan.md`

## Options and recommendation

1. **Contradiction fixes only:** smallest patch, but leaves repeated advisory orchestration and method-first routing intact.
2. **Outcome-first local boundaries plus targeted procedure sharing — recommended:** retain discovery; sharpen collision-prone descriptions and local handoffs; use existing owners. Three serial implementation slices below.
3. **Family gateways, hidden specialists, generic router:** larger behavioral change with unmeasured recall risk. Rejected for this scope.

Do not copy this full map into root instructions or every skill. Keep a maintainer map in a proposed `pi/agent/skills/README.md`, linked from `pi/README.md`; operational selection remains existing descriptions plus small local boundary/handoff sections. The README is not automatically loaded and is not an enforcement mechanism.

## Routing contract

1. Identify requested deliverable and object: code repair, incident explanation, work learning, design, critique, evidence synthesis, etc. Words such as “failure,” “risk,” “review,” and “root cause” alone do not select a method.
2. Honor explicit named-method requests, subject to normal safety and scope gates. Offer alternatives without silently substituting them. A requested fault tree or STRIDE analysis does not automatically become STPA.
3. Select the smallest relevant entry point. Ask one targeted question only when different interpretations materially change the deliverable. “Past or future?” is insufficient until the task is established as systemic analysis.
4. Load a specialist only when its distinct output is needed. Multiple stages are permitted, not an automatic pipeline; preserve already supplied scope/evidence and ask before expanding work.
5. Handoffs state why, exact body/reference to read, evidence to carry, expected next output, and applicable stop/approval condition. If already loaded and unchanged, reuse it. A name in “Related skills” is not proof of a runtime load.
6. Cross-skill runtime pointers use the repository's existing `~/.pi/agent/skills/<name>/SKILL.md` convention; within-skill references remain relative. Source edits occur under tracked `pi/agent/skills/`, never live paths. Direct specialist entry must work without first visiting a parent; avoid base↔child routing loops.

## Cross-family intent-to-outcome map

These are selection expectations, not measured model behavior. In this table each skill name denotes its existing `pi/agent/skills/<name>/SKILL.md` source.

| Requested outcome / object | First skill or method | Output and boundary / optional next step |
|---|---|---|
| Repair software bug, failing test, compiler error, runtime regression | `systematic-debugging` | Evidence/reproducer and root-cause hypothesis; implementation uses `test-driven-development`, then `verification-before-completion`. Not CAST because a test “failed.” |
| Explain systemic accident, incident, near-miss or failed organizational controls | `stamp-cast` | Event/control analysis and recommendations. Stabilize active incidents first; code debugging may be separate work. Not routine session learning. |
| Learn from completed project/session work | `retrospective` | Plan-versus-actual, friction and proposed improvements; assignment/direct request required. Not automatic closeout, CAST, or harness lifecycle audit. |
| Decide whether to keep/change/pause/retire agent or harness behavior across runs | `agent-retrospective-loop` | Bounded cohort, replay evidence and lifecycle decision; assignment/direct request. Not a single broken run. |
| Design recovery after agent failure | `failure-choreography` | Preserved/lost/uncertain work, recovery options and human resumption. Not root-cause debugging. |
| Explore possibilities without selecting a design | `ideate` | Divergent directions and open questions; explicit transition before `brainstorming`. |
| Resolve requirements/options into an approved design | `brainstorming` | Design and approval boundary; `ux-design-agent` only for unclear users, usage or modality; `first-principles` when assumptions are the obstacle. |
| Rebuild reasoning from fundamentals | `first-principles` | Evidence-classified assumptions and reconstructed options, not automatic implementation. |
| Assess concrete diff/PR correctness | `requesting-code-review` | Evidence-backed findings with verification; not generic adversarial debate. |
| Process incoming review feedback | `receiving-code-review` | Validate feedback and decide fixes; does not automatically request a new council or critic panel. |
| Stress-test an argument, plan or design's assumptions | `redteam` | Steelman/counterargument; optional central-critic competitive proposal workflow remains distinct. |
| Compare positions through reciprocal debate | `council` | Visible rounds and synthesis with disagreement; not interchangeable with a central critic. |
| Identify prospective system-safety hazards and constraints | `stamp-stpa` | Losses, hazards, control structure, UCAs, scenarios, requirements and verification. Not every generic design risk. |
| Model adversarial control/feedback paths and mission/safety losses | `stamp-stpa-sec` | Trust boundaries, adversarial scenarios and security requirements. Ordinary STRIDE may suffice when control-system analysis is not requested/needed. |
| Understand STAMP theory or choose among its methods | `stamp-base` | Shared foundations and bounded method selection; not a universal “failure” gateway. |
| Gather multi-source facts about a topic | `research` | Verified source inventory and answer. Not software diagnostics, due diligence or background checks. |
| Compare papers/evidence and synthesize findings | `literature-synthesis` | Extraction table, conflicts, limitations and cited synthesis; reuse research retrieval conventions. |
| Generate/rank competing research explanations | `hypothesis-tournament` | Hypotheses, discriminating predictions and falsification plan, not just a literature summary. |
| Assess research-program feasibility or go/no-go | `heilmeier-catechism` | Goal, baseline, enablers, cost/schedule and success exams; not routine code review. |
| Optimize against an explicit objective score | `scorable-discovery` | Reproducible baseline/candidate comparison with guardrails; not unscored ideation. |
| Plan approved implementation | `writing-plans` | Exact files, dependencies and verification plan. |
| Execute approved plan serially | `executing-plans` | Checkpoints and verified candidate; not implicit parallel-write permission. |
| Investigate independent domains concurrently, read-only | `dispatching-parallel-agents` | Evidence-complete peer packets and verified synthesis. |
| Coordinate independent implementation workers | `subagent-driven-development` | Task classification and worktree/write policy; advisory Mode A delegates procedure to dispatching. |
| Set up isolated checkout | `using-git-worktrees` | Approved branch/path/base and isolation checks; not merge or cleanup permission. |
| Finish implementation | `finishing-a-development-branch` | Closeout coordinator; load verification, docs and review at their phase triggers, not simplification/learning automatically. |
| Simplify behavior-preservingly | `code-simplification` | Assigned/requested simplification only; verify after changes. |
| Prepare contribution to external upstream | `preparing-upstream-pr` | Upstream-specific contribution checks; publication still separately authorized. |
| Author/validate general project docs | `documentation-standards` | Current docs or precise gaps; load `codify-subsystem` for a subsystem contract. |
| Codify module/directory invariants and failure modes | `codify-subsystem` | `SPEC.md` or `<module>.SPEC.md`, test traceability and manifest. |
| Clarify users, usage and interaction modality | `ux-design-agent` | Requirements/user model/modality; only relevant UX specialists, not all by default. |
| Decide when agent asks versus acts | `delegation-oversight` | Delegation boundaries and human control transfer; not runtime authority. |
| Design informed-consent approval | `approval-confirmation` | Preview, scope, consequences, reversibility and expiry; standalone entry valid. |
| Express uncertainty/evidence appropriately | `trust-calibration` | Calibrated communication; confidence never grants permission. |
| Edit buttons, errors, forms or notifications | `ux-writing` | Interface copy; no mandatory UX archaeology. |
| Implement polished GUI | `design-principles` | Visual design guidance; not a third-party userscript workflow. |
| Restyle third-party website | `layer-theme` | Userscript/UserStyle plus render/vision/contrast checks. |
| Design quantitative figure | `tufte` | Evidence-preserving chart/diagram, not decorative illustration. |
| Edit general prose | `writing-clearly-and-concisely` | Clear concise text; closeout coordinator already subsumes routine summary prose. |
| Extract reusable method from completed work | `session-to-skill-extractor` | Assigned/requested extraction proposal; then `skill-creator` for approved skill work. |
| Create/improve skill or trigger | `skill-creator` | Ownership, baseline scenarios, bounded change and verification. |
| Work on Docker / initialize project / query existing graph | `docker` / `project-init` / `graphify` | Domain-specific workflows; retain independent entries. |
| Manage context discipline / typed local classification | `token-saver` / `laya-integration` | Existing utilities, not new routing authority; Laya changes deferred. |

Two existing hidden helpers remain unchanged: `dev-workflow-common` (shared conventions when requested) and `requirement-simplification-review` (assigned/explicit specialist). Package-installed skills remain outside ownership; this map is not a claim to cover the complete runtime catalog.

## Canonical ownership and handoff contracts

| Responsibility | Owner | Caller behavior and carried context |
|---|---|---|
| Advisory parallel mechanics and external mutable-resource check | `dispatching-parallel-agents` | Development Mode A explicitly reads owner and passes task graph, independent scopes, evidence, output contract and stops. Owner must not redirect read-only proposals back to Mode A. |
| Task classification, parallel write/worktree approval and serial integration | `subagent-driven-development` | Preserve Mode B, file overlap and external-state gates; worktree setup remains `using-git-worktrees`. Short local safety summaries stay. |
| Evidence-complete packet format and shared development contract | `dev-workflow-common` | Existing consumers retain packet obligations; no second generic dispatch engine. |
| Review packets, schema validation, findings and verifier policy | `requesting-code-review` | Finishing selects review, passes exact candidate/scope/evidence, and honors unsupported/no-artifact stop state. |
| Evidence gate | `verification-before-completion` | Other workflows retain local stop obligations and load mechanics; never subsume mandatory verification. |
| Quality activity scheduling | Existing `pi/agent/quality/control-plan.json` | Skills consume assignment/direct request; no self-scheduling after tests. Do not edit scheduler in this proposal. |
| UX requirements / consent / recovery / copy / evidence communication | Respective existing UX skills | Preserve standalone selection. Handoff carries user/task, state, allowed effects, unresolved decision and artifact; uncertainty does not mandate unrelated redesign. |
| Source retrieval/verification / literature extraction / hypotheses / feasibility | `research` / `literature-synthesis` / `hypothesis-tournament` / `heilmeier-catechism` | Share retrieval pointers, not analytical methods. Pass question, source IDs/locations, findings, limitations and requested next output. No mandatory scientific pipeline. |
| Reciprocal debate / central-critic competition | `council` / `redteam` | Clarify contrasting mechanics and outputs; no workflow merger or fanout-policy rewrite. |
| STAMP theory / generic Depict grammar | `stamp-base` references | Specialist reads exact shared reference when needed; no compulsory whole-base preload for every direct invocation. Keep concise safe-control reminders local. |
| STPA / CAST / STPA-Sec procedures and schemas | Respective specialist | Retain method steps, IDs, schemas, examples and validation. Share only generic diagram grammar; carry boundary, losses/hazards, controllers, feedback, assumptions and IDs across stages. Schemas are not interchangeable. |
| General docs validation / subsystem contract authoring | `documentation-standards` / `codify-subsystem` | Docs hands off by exact path when contract authoring is requested; planners/executors/verifiers discover both spec forms plus `docs/specs/MANIFEST.md` when present. |

## Verified contradictions and exact repair decisions

Line numbers refer to baseline; section anchors govern if lines drift.

| Evidence | Proposed repair |
|---|---|
| `pi/agent/skills/code-simplification/SKILL.md:18` restricts invocation; `:175` recommends it after verification for nontrivial work | Replace Integration/Pipeline Position with “Only after assignment or explicit request and passing focused checks”; use `verify → requested simplify → re-verify → complete`. Do not hide skill or alter control plan. |
| `pi/agent/skills/approval-confirmation/SKILL.md:102-109` says low/reversible timeout → Proceed; `references/timeout-patterns.md` repeats auto-send, partial-send, prior-similar-approval, default create-event and retry examples | Required approval expiry always blocks execution. Replace unsafe defaults/examples, not merely add a disclaimer. Cancellation preserves already-authorized work; escalation and saving remote drafts are effects requiring their own authority. Prior similar approvals, confidence and reversibility are not current consent. No automatic retry after expired authorization. A separately authorized scheduled action is not a timeout approval and must be described separately if retained. |
| `pi/agent/skills/finishing-a-development-branch/SKILL.md:119-121` allows artifact-free review or skipping; requesting review requires saved packets/output and validator | Remove exemption. Keep canonical artifact-backed review. If required artifacts cannot be created, report review `NOT_VERIFIED`, explain missing evidence path and ask for permission to use permitted storage or stop. No new in-memory validator/API. Trivial diffs can still legitimately not trigger review. |
| `pi/agent/skills/ux-design-agent/SKILL.md:153` claims caller absent in brainstorming; `:116` uses `docs/plans` | Add conditional exact-path UX handoff in brainstorming when users/usage/modality need work; UX uses `agnt plans-dir`. Its planning/write transition requires approved design; remove graph/text shortcuts that imply obvious user model alone authorizes planning or implementation. |
| `pi/agent/skills/trust-calibration/SKILL.md:22` asserts invokers without guaranteed reciprocal loads | Replace factual “Invoked by” claim with standalone applicability and optional collaboration, rather than forcing all callers to load trust. Approval may explicitly hand off uncertainty framing when needed. |
| `pi/agent/skills/layer-theme/SKILL.md:89` points to absent `frontend-design` | Replace with exact `design-principles` skill path for owned polished-GUI work. Preserve theming/render/accessibility checks. |
| `pi/agent/skills/research/SKILL.md:22` mandates absent OSINT skill | Preserve exclusion. State this skill does not cover due diligence/background checks; use a separately available appropriate workflow or clarify scope. Do not invent/install OSINT. |
| `pi/agent/skills/council/SKILL.md:10` says redteam purely adversarial, but redteam has `references/AdversarialValidation.md` | Describe reciprocal debate versus central-critic competition; retain both existing workflows and output contracts. |
| STAMP base/CAST tables route generic “something failed”/“root cause”; STPA broadly routes design review; handoffs mostly names | First distinguish code repair, work learning, recovery UX, critique and systemic control analysis. Then choose STAMP method by analytical goal, timing and adversarial scope. Replace operational handoffs with exact read paths; generic STRIDE is not forced into STPA-Sec. |
| Development Mode A duplicates dispatching procedure; dispatching Escalation section points read-only proposals back to Mode A | Replace duplicated Mode A steps with exact-path delegation, retain classification/status and write policy; keep read-only proposals in dispatching to avoid cycle. |
| Docs lacks codify handoff; exact-name searches in docs, planning, execution and verification miss supported file-scoped specs | Add docs→codify exact path. Update searches to `\( -name SPEC.md -o -name '*.SPEC.md' \)`; consult manifest when present. Codify checks sibling file spec before walking parents; parent walk includes project root. Do not add new spec-discovery tool. |
| CAST/Sec Depict grammar duplicates STPA reference | Put shared grammar in new `stamp-base/references/depict.md`; replace three copies with exact references. Keep CAST incident examples/annotations and Sec trust-boundary limitations local. Do not migrate YAML schemas or analytical procedures. |

The timeout reference and research OSINT pointer were additionally verified in this session. No claim that every historical skill reference has been exhaustively audited.

## Bounded proposed file edits

All entries below are future implementation, not changes made by this design Bead. Implement serially; common tests/README/scenarios prevent independent write dispatch.

### Slice A — remove contradictions and broken contracts first

Modify these existing skill bodies under `pi/agent/skills/`:

- `code-simplification/SKILL.md`: assigned/requested Integration trigger only.
- `approval-confirmation/SKILL.md` and `approval-confirmation/references/timeout-patterns.md`: fail-closed required approvals and consistent examples; standalone applicability; optional exact-path recovery/copy/trust handoffs.
- `finishing-a-development-branch/SKILL.md` and `requesting-code-review/SKILL.md`: identical artifact requirement and blocked-review outcome, no silent waiver.
- `brainstorming/SKILL.md` and `ux-design-agent/SKILL.md`: real conditional handoff, project plan location and approved-design transition.
- `trust-calibration/SKILL.md`: remove asserted invocation dependency; retain standalone entry.
- `layer-theme/SKILL.md`: replace absent frontend-design pointer only.
- `documentation-standards/SKILL.md`, `codify-subsystem/SKILL.md`, `writing-plans/SKILL.md`, `executing-plans/SKILL.md`, `verification-before-completion/SKILL.md`: authoring handoff and complete spec discovery.
- `council/SKILL.md`: correct redteam distinction and exact handoff path.
- `research/SKILL.md`: remove absent OSINT dependency; add bounded output-based pointers to literature, hypothesis and feasibility skills before depth/fanout selection. Retrieval-only use must not bounce back into specialist selection.

### Slice B — outcome-first discovery and local handoffs

- Modify `systematic-debugging/SKILL.md`, `stamp-base/SKILL.md`, `stamp-stpa/SKILL.md`, `stamp-cast/SKILL.md`, `stamp-stpa-sec/SKILL.md`: add concise local outcome boundaries and explicit selected-skill loads, replacing conflicting generic routing rows/graphs rather than appending another competing router. Preserve explicit methods and urgent stabilization.
- Modify `redteam/SKILL.md`: distinguish critique, reciprocal debate and formal security analysis; exact paths to council and conditional STPA-Sec handoff. Keep `references/AdversarialValidation.md` mechanics unchanged.
- Modify `agent-retrospective-loop/SKILL.md` description only to include requested lifecycle review already allowed by body.
- Replace only these six discovery descriptions (all other descriptions unchanged):

| Skill | Proposed description |
|---|---|
| systematic-debugging | Use for software bugs, failing tests, or unexpected runtime behavior; diagnose before fixes. |
| stamp-stpa | Use for prospective safety hazards, STPA, fault-tree or Swiss-cheese analysis; not generic critique. |
| stamp-cast | Use for systemic incidents, accidents or near-misses (CAST); not code debugging or work retrospectives. |
| stamp-stpa-sec | Use for control-structure threat modeling (STPA-Sec), attack surfaces or safety/security risks. |
| agent-retrospective-loop | Use for assigned/requested agent/harness lifecycle review; not one-run bugs or work retrospectives. |
| research | Use for multi-source topic research; not software debugging, due diligence or background checks. |

Keep 48 discoverable skills and both existing hidden flags unchanged. Run scanner before accepting text: reserve must remain strictly above 1000 under unchanged 8000 limit and warning policy. If it does not, revise only these six descriptions without losing boundaries; broader compression requires new scope.

### Slice C — deduplicate proven shared procedures

- Modify `subagent-driven-development/SKILL.md` and `dispatching-parallel-agents/SKILL.md`: advisory ownership/delegation and no return loop. Keep Mode B approval/isolation/integration checks and shared external-resource safety summaries intact.
- Create `pi/agent/skills/stamp-base/references/depict.md`; modify `stamp-stpa/references/output-formats.md`, `stamp-cast/SKILL.md`, `stamp-stpa-sec/SKILL.md`, and `stamp-base/SKILL.md` for canonical grammar pointers. Preserve method-specific examples, YAML fields and output semantics. No new Depict parser or renderer.
- Create `pi/agent/skills/README.md` with condensed routing/ownership map and limits; link it from `pi/README.md`. This is maintainer documentation, not a new runtime gateway.

### Shared tests and fixtures

Modify `tests/test_context_architecture.py` only for new static invariants and small temporary-directory spec-discovery fixtures. Preserve existing packet fields, final-gate tests, role/action references and quality timing assertions. Existing `tests/test_agnt.py` budget tests stay unchanged.

Add written baseline scenarios before skill edits at these exact paths; use the scenario schema from `skill-creator` and label baseline weakness as source-observed, not model-observed:

- `.pi/skill-evals/systematic-debugging/scenarios/task-first-failure-routing.md`
- `.pi/skill-evals/stamp-base/scenarios/task-first-analysis-routing.md`
- `.pi/skill-evals/brainstorming/scenarios/task-first-design-and-ux.md`
- `.pi/skill-evals/research/scenarios/task-first-research-outcomes.md`
- `.pi/skill-evals/code-simplification/scenarios/assigned-only-integration.md`
- `.pi/skill-evals/approval-confirmation/scenarios/timeout-does-not-authorize.md`
- `.pi/skill-evals/requesting-code-review/scenarios/required-review-without-artifacts.md`
- `.pi/skill-evals/documentation-standards/scenarios/file-scoped-spec-handoff.md`
- `.pi/skill-evals/dispatching-parallel-agents/scenarios/advisory-owner-and-write-boundary.md`
- `.pi/skill-evals/stamp-stpa/scenarios/shared-depict-direct-entry.md`

No JSON schemas, exports, package settings, AGENTS files, model-routing tables, scheduler, approval runtime, scanner, or dependency files need edits. Existing action/role/control-plan names remain compatible. If evidence requires those changes, stop and revise scope rather than expanding silently.

## Verification cases

Each row has a positive route and a near-neighbor exclusion or preserved gate. Scenario files above may contain several labeled cases; no new evaluation framework.

| ID | Prompt / setup | Required result; forbidden shortcut |
|---|---|---|
| R1 | “This test failed after yesterday's change; find root cause.” | Debugging, not CAST/retrospective solely from failure/root-cause keywords. |
| R2 | “Analyze near-miss involving operator handoff, alarms and management controls.” | CAST control analysis, not code debugging or routine work retrospective. |
| R3 | “Retrospect on this completed feature.” / “Review this harness across 20 runs.” | Retrospective / lifecycle review respectively; ordinary Bead close selects neither. |
| R4 | “Design recovery UI after partial agent failure.” | Failure choreography; not CAST or automatic investigation of implementation bug. |
| R5 | “Assess this diff.” / “Poke holes in this proposal.” / “Debate these options reciprocally.” | Requesting review / redteam / council. Incoming reviewer comments select receiving review. |
| R6 | “Find hazards in this infusion-pump control design.” / “Threat-model its remote command channel.” | STPA / STPA-Sec; generic product feasibility is not forced into either. |
| R7 | “Do CAST/STPA/STPA-Sec explicitly.” / “Do ordinary STRIDE only.” | Named method remains reachable; STRIDE-only request is respected, not silently replaced. |
| R8 | “Give divergent ideas; don't choose.” / “Turn these requirements into a design.” | Ideate / brainstorming; no implementation or file writes from unapproved design. |
| R9 | “Compare papers.” / “Rank explanations.” / “Evaluate research-program go/no-go.” / “Optimize against this metric.” | Literature / hypothesis / Heilmeier / scorable discovery. Fact lookup stays research; no mandatory multi-stage chain. |
| R10 | “Rewrite button text.” / “Redesign approval preview.” / “Explain uncertainty.” | UX writing / approval / trust independently; no forced UX parent or unrelated redesign. |
| R11 | Verification passes, no simplification assignment/request | No simplification. Explicit simplification request loads existing skill and re-verifies. |
| R12 | Required approval expires; low stakes, reversible, similar action approved yesterday | No action, auto-send, partial-send or retry. Preserve authorized state; renewed approval required. Test body and timeout reference examples. |
| R13 | Substantial diff requires review; user forbids artifacts | Report review NOT_VERIFIED/blocked; no silent skip or unsupported artifact-free PASS. Allowed artifact-backed case retains schema validation and serious-finding verification. |
| R14 | `src/store.py`, sibling `src/store.SPEC.md`, root `SPEC.md`, manifest | Discover sibling and governing root; no duplicate contract creation. Directory-only and no-spec fixtures also work. |
| R15 | “Investigate two independent failures read-only.” entered directly or through development Mode A | Same dispatch owner/packet contract; no files/commits by peers, no reciprocal Mode-A loop. Shared database/port requires isolation or serial work. |
| R16 | “Implement independent tasks in parallel” without worktree approval, or overlapping files | No write dispatch. Approved disjoint worktrees retain write-set and serial integration gates. |
| R17 | Direct CAST/STPA/Sec request includes Depict diagram | Exact shared grammar read, local method examples retained, no whole-base routing loop; no diagram request need not load grammar. Schemas remain unchanged. |
| R18 | Owned GUI design versus third-party UserStyle | design-principles versus layer-theme; no missing frontend-design call. Research excludes background checks without pretending OSINT exists. |
| M1 | Debug bug → requested systemic incident investigation → prevent recurrence | Debug/stabilize first; then CAST; then approved STPA/Sec analysis as appropriate. Preserve evidence and scope, no forced entire chain. |
| M2 | Brainstorm interface → unclear user/modality → approve design → implementation plan | Conditional UX handoff returns requirements; plan uses project plans-dir; approval still required before implementation. |
| M3 | Literature synthesis → user requests hypotheses → then program feasibility | Preserve source IDs, limitations and uncertainty; select hypothesis then Heilmeier only on requested next outcomes. |
| M4 | STPA reveals malicious feedback → user requests security extension | Pass control model/IDs/assumptions into STPA-Sec; add adversarial analysis, do not equate schemas or discard existing constraints. |

Static checks must verify operational references resolve, retired contradictory wording/examples are removed, new boundaries exist, the six descriptions preserve discovery budget, hidden flags are unchanged, and critical method/schema/gate content remains. Use focused assertions, not exact entire-body snapshots or a second executable router. For spec-discovery commands, execute the documented command against temporary fixtures; avoid merely asserting that '*.SPEC.md' appears somewhere.

Written scenarios and source assertions prove instruction consistency and fixture behavior, not natural-language selection recall. Real-model selection/output comparison remains NOT_VERIFIED and requires separate approval. Deterministic `routing-smoke` tests model-routing infrastructure, not this skill-selection map.

## Proposed implementation verification commands

Run focused checks after each slice; run the full required gate only after the final candidate stabilizes. No dependency install is required by this proposal; if the existing environment is unavailable, report blocker.

```bash
pi/agent/bin/agnt context-health --strict
.venv/bin/python -m pytest tests/test_context_architecture.py
.venv/bin/python -m pytest tests/test_agnt.py -k context_health
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
git diff --cached --check
```

Known environment caveat from predecessor evidence: ambient HOME can expose installed package skills to skill-count tests. If reproduced, inspect and use an isolated temporary HOME for deterministic tests, recording exact command and reason; do not change live config or weaken assertions. Do not mistake existing Laya body-size warning for a discovery-budget failure.

## Evidence and approval handoff

Read all three referenced audit `finalOutput` values after resolving `agnt runtime-path delegated-results`:

- `8bf998d0-cd23-496f-8868-138dad578148/child-0.json` — development/hidden helpers.
- `8f581ca1-fb13-474d-a5fe-f9edbfd60010/child-1.json` — research/exploration/learning.
- `f2ab77f2-2382-4ca7-a58c-54afd7f0be85/child-2.json` — UX/STAMP.

Verified principal findings against source, relevant caller searches, existing runtime-reference checker and budget tests. Graph probes `agnt graphify query 'skills'` and `agnt graphify explain 'context_health'` mapped scanner code but did not provide useful skill-body coverage; source remained authoritative. Installed Pi `docs/skills.md`, `docs/settings.md`, and `docs/packages.md` confirm description-based discovery and explicit invocation; no runtime recall claim follows from that documentation.

Fresh baseline `pi/agent/bin/agnt context-health --strict`: PASS, 6991 local metadata characters, 1009 remaining, limit 8000, warning threshold 1000; one existing Laya 227-line size warning. Metadata proxy excludes package skills and actual prompt framing/path overhead; it is not a token measurement.

Design-only validation: saved artifact existence and 22 routing cases checked; referenced skill bodies resolve; six proposed descriptions project to 6988 metadata characters / 1012 reserve by text arithmetic, not an applied scanner run. Both unrelated plan paths remain present. No skill source edits or behavioral experiments performed.

**Implementation approval requested later:** approve Slices A–C, named tests/scenarios/docs, verification, and one local task-owned commit under a new implementation Bead. No source implementation, deployment, push, dependencies, hiding, Laya or model experiments are authorized by this design deliverable. Prefer a separately approved task branch/worktree for implementation on current `main`; exact setup/integration authority must be bound then, not invented here.

**Acceptance coverage:** outcome map above covers requested collision families; ownership table defines shared responsibilities and explicit loads; repair table identifies verified contradictions; slices bound paths; R/M cases cover positive, negative and multi-stage behavior; approval and exclusions remain explicit.
