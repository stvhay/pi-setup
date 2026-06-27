# Self-Improvement Configuration Evaluation

**Date:** 2026-06-26
**Scope:** Tracked Pi configuration under `pi/agent/`, top-level project docs, and helper/eval surfaces relevant to self-improvement.
**Reference:** `docs/SELF-IMPROVEMENT-PRINCIPLES.md`

## Verdict

The configuration is already moving in the right direction: routing policy,
roles, skills, metrics, instruction composition, and evals are separate and
mostly inspectable. The highest-value improvements are not more prose in the
base instructions, but stronger action/message artifacts, prompt/action
semantics, beads-backed work state, and automated context-health checks.

## Checked surfaces

- `pi/agent/AGENTS.md` — global operational instructions and context package convention.
- `pi/agent/SOUL.md` — communication preferences and safety boundary.
- `pi/agent/tasks/*.md` — routing task policies.
- `pi/agent/AGENTS.d/roles/*.md` — delegated-worker role contracts.
- `pi/agent/skills/*/SKILL.md` — workflow/capability packages.
- `pi/agent/prompt-patterns/README.md` and `agnt prompt` — prompt-pattern inventory/import surface.
- `pi/agent/bin/agnt*` and `pi/agent/bin/agnt_lib/` — deterministic orchestration helper surface.
- `pi/agent/evals/` and `scripts/eval-workflow-compliance.sh` — gates and behavioral checks.
- `docs/ARCHITECTURE.md` and `docs/SELF-IMPROVEMENT.md` — architecture and feedback-loop docs.
- Local `beads`/`bd` CLI availability and tracked `.beads/` workspace export/config.

## Strengths

### 1. Repository/runtime separation is clear

`README.md`, `AGENTS.md`, and `docs/ARCHITECTURE.md` consistently state that
tracked `pi/` is the deployable source of truth and live `~/.pi` is runtime
state. Runtime telemetry and secrets are excluded from tracked policy. This is
an excellent foundation for inspectable self-improvement.

### 2. Routing tasks are mostly orthogonal to workflows

`pi/agent/tasks/*.md` are concise routing policies with model lists and short
summaries. They do not try to duplicate full skills. This matches the refined
principle that routing tasks answer "which model/default?" rather than "what
procedure?"

### 3. Roles are already independent peer contracts

`pi/agent/AGENTS.d/roles/*.md` mostly behave as independent output contracts:
reviewer, verifier, planner, researcher, implementation worker, etc. They
reference relevant skills without fully embedding those skills. This is the
right direction.

### 4. Skills encode reusable methods and safety gates

The major workflow skills (`writing-plans`, `executing-plans`,
`verification-before-completion`, `documentation-standards`,
`requesting-code-review`, `systematic-debugging`) provide reusable procedures
with explicit filesystem-first behavior. They are discoverable by description
and mostly atomic enough to load on demand.

### 5. Deterministic helper surface exists

`agnt` centralizes route, invoke, metrics, evals, instructions, prompt
inventory, graphify, plans-dir, and risk helpers. This is the correct place to
move behavior that should not depend on prose compliance.

### 6. Feedback loop is already policy-oriented

`docs/SELF-IMPROVEMENT.md` cleanly separates runtime metrics from tracked
policy changes. Model routing feedback and prompt overlays are eval-gated,
which directly supports auditable self-improvement.

## Gaps and risks

### 1. Prompt/action semantics have a first concrete implementation

Prompt patterns retain provenance-safe note storage, and active action templates
now live under `pi/agent/actions/*.md`. `agnt action list|validate|render`
provides the first deterministic surface for binding action id, routing task,
skills, role, allowed effects, and output contract.

Implemented actions now include `review`, `verify`, `plan`, `implement`,
`research`, and `finish`. Additional actions should be added only when they can
stay small and orthogonal.

### 2. Invocation/result artifacts now have a v1 schema

`docs/RUN-ARTIFACTS.md` defines the v1 run bundle shape, and `agnt runs` plus
`agnt action render` can create and validate `.pi/runs/<run-id>/` bundles with
`invocation.yaml`, `result.yaml`, and `artifacts/`.

`agnt runs update` and `agnt work finish` can now enrich `result.yaml` with
status, summary, evidence, artifacts, follow-up beads, metrics refs, and
completion time. Future model invocation integrations should call these helpers
rather than inventing separate result formats.

### 3. Beads is integrated as the work graph

The repository now has a `.beads/` workspace with tracked portable config/export
files and ignored local database/runtime state. Project instructions make Beads
the canonical agent-facing queue and treat GitHub as an adapter/export surface
if used.

GitHub synchronization is explicitly deferred in `docs/GITHUB-ADAPTER.md`.
If desired later, it should be implemented as an explicit adapter instead of
reintroducing dual-source tracking.

### 4. Context-health checks are stronger but still evolving

Existing evals test routing and role-context composition. Unit tests now cover
role/task/skill references, action-template references, action write-effect
compatibility with read-only roles, prompt inventory health, and run artifact
validation.

The check surface now also validates action effect vocabulary, role
`writeAccess`, and stale active skill references to removed plan helpers.
Duplicate skill scopes, oversized skills, and broader gate-weakening scans
remain useful future refinements.

### 5. Role validation is improving but not complete

`agnt instructions --roles` inventories roles, and role context smoke tests
cover key cases. This evaluation added unit coverage for role `task`
frontmatter, role skill references, task ids, and skill descriptions. Remaining
gaps include write-access/allowed-effect validation and richer output-contract
checks.

**Impact:** Role contracts are less likely to drift silently, but effect-policy
validation still needs design.

### 6. Tooling surfaced a prompt inventory bug

Running `agnt prompt inventory` exposed a missing `parse_frontmatter` reference
in `agnt_lib/prompt.py`. This was corrected to use the shared
`common.parse_frontmatter_file` helper, and a unit test was added.

**Impact:** The incident supports the principle that helper commands should be
part of the verification surface, not only documented as available.

## Recommendations

### Priority 1 — Preserve and validate the refined ontology

1. Keep `docs/SELF-IMPROVEMENT-PRINCIPLES.md` as an occasional design reference,
   not default runtime context.
2. Keep `docs/ARCHITECTURE.md` as the concise operational architecture.
3. Continue extending evals/checks. This pass added unit checks that roles
   reference existing routing tasks and skills, task ids match filenames, and
   skills have descriptions. Remaining checks should validate write-access vs.
   allowed effects, composed-context gate weakening, and `agnt prompt inventory`
   health at the CLI level.

### Priority 2 — Deepen invocation/result workflow integration

The v1 schema and helper commands exist. Next, model invocation and verification
workflows should update `result.yaml` with richer evidence, metrics refs,
follow-up beads, and final statuses.

### Priority 3 — Mature beads integrations

Beads is canonical for agent-facing work. Remaining integration work:

- fresh-clone/bootstrap validation in CI or a deterministic smoke test;
- optional GitHub adapter/export design;
- clearer worktree behavior guidance, since Beads resolves to the main repo's
  `.beads/` from linked worktrees;
- idempotency/retry conventions for reopened or superseded beads.

### Priority 4 — Expand prompt/action templates cautiously

The initial `review` and `verify` templates prove the model. Add more actions
only when they remain small bindings of task + skills + role + effects + output
contract.

### Priority 5 — Add a workflow-refactoring capability only if reused

Workflow refactoring is a recurring self-improvement need, but avoid adding a
new skill prematurely. First use this principles document plus ad hoc plans. If
similar audits recur, create a focused skill such as `context-architecture` or
`workflow-refactoring` with:

- inventory commands;
- boundary checks;
- role/task/skill/prompt/tool rubric;
- artifact and eval expectations;
- explicit no-runtime-context-bloat guidance.

## Suggested next work items

1. **Model invocation result integration**
   - Have `agnt invoke` or selected workflows write enriched `result.yaml`
     records when they run from an invocation artifact.

2. **Optional GitHub adapter implementation**
   - Only if collaboration requirements demand it; keep Beads canonical.

3. **Additional action templates**
   - Add only when a new action has a crisp effect policy and output contract.

4. **Context health check command/eval**
   - Move more architecture invariants into `scripts/check-pi-config.sh`,
     `agent-instructions --check`, or a dedicated `agnt` check.

5. **Workflow refactoring skill decision**
   - If this kind of audit recurs, create a focused `context-architecture` or
     `workflow-refactoring` skill.

## Non-recommendations

- Do not load the principles document in every Pi session.
- Do not merge roles into skills; keep roles as delegated-worker contracts.
- Do not put orchestration state in chat or skill prose.
- Do not create a second work tracker beside beads if beads becomes canonical;
  integrate external systems through adapters.
- Do not rewrite all existing skills before automated inventory and checks are
  in place.
