# README Architecture Reorganization Implementation Plan

**Issue:** None — create or claim a Bead before editing tracked documentation
**Design:** Architecture-grounded README review approved in the 2026-07-21 Pi conversation
**Date:** 2026-07-21
**Branch:** main (currently has intentional uncommitted `README.md` updates that must be preserved)

**Goal:** Reorganize the root README so it accurately presents the deployable Pi configuration, the everyday `agnt` control plane, the direct-work default, and the optional orchestration/feedback systems in architectural order.

**Architecture:** The tracked `pi/` tree is the opinionated deployable artifact; `~/.pi` is its runtime copy plus preserved local state. Pi is the normal interactive execution surface, while `agnt` supplies on-demand routing, context composition, peer invocation, review, health, metrics, and eval controls. Beads and plans hold durable work state; runtime metrics and optional run bundles hold evidence; the project-local runner is an explicit opt-in path rather than the default workflow. The README should introduce those layers in that order and link implementation/operator detail to the existing subsystem documentation.

**Acceptance Criteria:**
- [ ] The opening describes Pi Setup as an opinionated deployable Pi environment plus the `agnt` control CLI; only artifact-backed dispatch and the runner are called optional.
- [ ] The default-work diagram shows direct Pi work and ordinary non-runner `agnt` controls, scopes the Bead rule to code edits in Beads-enabled projects, and separates manual run bundles from the optional runner service.
- [ ] The README explains what the deployed configuration contains and distinguishes root `AGENTS.md` from deployed `pi/agent/AGENTS.md`.
- [ ] A compact concept table keeps work items, tasks, actions, skills, roles, tools/evals, and artifacts distinct.
- [ ] Deployment instructions place the managed-copy warning beside `--apply` and describe `~/.pi` as deployed configuration plus preserved runtime state.
- [ ] Stable everyday controls (`agnt route`, `invoke`, `instructions`, `doctor`, and review/eval concepts) receive more prominence than the runner or Graphify.
- [ ] Graphify detail, the full maintainer verification matrix, and the detailed private-state list are removed from the root README and remain discoverable in their canonical docs.
- [ ] Optional run artifacts, runner service, lesson server, and Graphify are grouped and labeled as optional capabilities or integrations.
- [ ] The documentation map contains no duplicate runner entry and is grouped by user goal and architectural layer.
- [ ] `pi/README.md` names the deployed task, role, and model-overlay surfaces; `CONTRIBUTING.md` contains the canonical project verification commands moved out of the root README.
- [ ] The existing uncommitted Lesson Server documentation/layout additions and Ruff verification coverage are preserved in the reorganized documentation.
- [ ] All local Markdown links resolve, displayed commands match the tracked CLI, project checks pass, and `git diff --check` reports no errors.

**Verification Commands:**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt --help >/dev/null
pi/agent/bin/agnt route --help >/dev/null
pi/agent/bin/agnt invoke --help >/dev/null
pi/agent/bin/agnt instructions --help >/dev/null
pi/agent/bin/agnt doctor --help >/dev/null
git diff --check
python - <<'PY'
import re
from pathlib import Path

for source_name in ("README.md", "pi/README.md", "CONTRIBUTING.md"):
    source = Path(source_name)
    for raw_target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source.read_text()):
        if raw_target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = raw_target.split("#", 1)[0]
        if target and not (source.parent / target).exists():
            raise SystemExit(f"broken local link: {source}:{raw_target}")
print("local Markdown links: OK")
PY
```

---

## Scope and source hierarchy

Use these files as authoritative context during implementation:

- `docs/ARCHITECTURE.md` — repository/runtime boundary, control-plane layers, primitives, safety, quality gates, and feedback flow.
- `docs/AGNT-SYSTEM.md` — narrative system model, normal versus optional workflows, command families, feedback loop, and maturity.
- `docs/ORCHESTRATION-LOOP.md` — decision that direct Pi coding is the default and runner orchestration is explicit opt-in.
- `pi/README.md` — deployable configuration contents, deployment effects, credentials, endpoints, and excluded runtime state.
- `pi/agent/bin/README.md` — canonical command details, including Graphify and ordinary `agnt` controls.
- `CONTRIBUTING.md` and `AGENTS.md` — repository workflow and verification commands.
- `lesson-server/README.md` — optional lesson aggregation service boundary.

Do not expand scope into implementation or architecture changes. `docs/ARCHITECTURE.md`, `docs/AGNT-SYSTEM.md`, runner docs, CLI code, skills, and tests should remain unchanged unless final validation reveals a concrete contradiction introduced by the README rewrite.

### Intended audience order

1. A person deciding whether to deploy and use this Pi configuration.
2. A contributor or agent working on this repository.
3. A maintainer trying to understand or extend the architecture.
4. An operator intentionally selecting optional artifact/runner workflows.

## Proposed root README structure

Use this as the target information architecture; wording may be refined for clarity without changing the hierarchy.

1. `# Pi Setup` — concise identity, opinionated-defaults disclosure, source/runtime boundary, and direct-work default.
2. `## What you get` — compact table covering deployed Pi configuration, `agnt` controls, durable state, optional orchestration, and evidence-driven feedback.
3. `## How the system fits together` — corrected default/optional architecture diagram and a short explanation of the two instruction levels.
4. `## Deploy and use the configuration` — prerequisites, dry-run/apply, adjacent overwrite/preservation warning, provider-key link, and representative ordinary `agnt` commands.
5. `## Work on this repository` — concise Beads workflow and link to `CONTRIBUTING.md` for full checks and branch readiness.
6. `## Core concepts` — work/task/action/skill/role/tool/artifact responsibility table.
7. `## Optional orchestration and integrations` — manual run bundles, runner service, lesson server, and Graphify, each linked and explicitly non-default.
8. `## Repository layout` — retain the current layout, including `lesson-server/`.
9. `## Documentation map` — group deploy/use, architecture/design, optional orchestration/services, contribution, and historical audit material; list each destination once.
10. `## Security and runtime state` — concise no-secrets rule and link to `pi/README.md` instead of duplicating the full exclusion list.

### Editorial constraints

- Prefer one representative command over a command inventory; canonical syntax belongs in `pi/agent/bin/README.md`.
- Do not call all of `agnt` optional. Call manual run artifacts, runner startup, gateway-only orchestration, and related stricter gates opt-in.
- Do not imply that every direct/read-only Pi session requires a Bead. State the repository/global policy precisely: before code edits when a project has adopted Beads.
- Do not imply that `agnt work run` requires the daemon runner; show manual artifact-backed dispatch and service-backed scheduling as separate paths.
- Describe self-improvement as runtime evidence informing reviewed, eval-gated tracked policy changes—not autonomous mutation.
- Avoid feature-count inventories that will drift. Name capability categories and link to authoritative directories/docs.
- Keep current intentional content: Lesson Server remains in optional integrations, documentation map, and repository layout; Ruff remains in the canonical verification documentation.

### Candidate architecture diagram

The implementation may improve labels and spacing, but it should preserve this topology:

```text
tracked pi/ policy ──deploy──▶ ~/.pi runtime
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
              direct Pi work             agnt controls
              inspect/edit/test     route/invoke/context/review/doctor
                    │                           │
                    └────── durable state/evidence ──────┘
                         Beads / plans / metrics
                                      │
                             optional run bundles
                                      │
                             optional runner service

runtime evidence / lessons ──review + eval──▶ tracked policy changes
```

## Implementation tasks

### Task 1: Establish durable work and preserve the baseline [Independent]

**Context:** The working tree is on `main` with intentional uncommitted edits to `README.md`: Lesson Server links/layout and the Ruff command. A fresh implementation session must not overwrite or silently discard them. The repository workflow expects meaningful tracked work to have a Bead even though this planning artifact itself is documentation-only.

**Files:**
- Inspect: `README.md`
- Inspect: `.beads/` through `bd`
- Reference: `.pi/plans/2026-07-21-readme-architecture-reorganization-plan.md`

**Steps:**
1. Run `bd prime`, `bd search "README architecture"`, and `bd ready`.
2. If no suitable Bead exists, create one titled `Reorganize README around the Pi Setup architecture` with this plan path, the acceptance criteria above, and a note that the working tree already contains intentional README additions. Claim it before tracked edits.
3. Inspect the Bead with `bd show <id>`.
4. Capture `git status --short` and `git diff -- README.md`; verify that the baseline contains the Lesson Server documentation/layout additions and Ruff command.
5. Do not reset, stash, commit, or otherwise alter the existing working-tree changes as part of setup.

**Focused verification:**
```bash
bd show <id>
git status --short
git diff -- README.md
```

**Expected result:** A claimed Bead records the work and plan, and the implementer has explicit evidence of the pre-existing README changes that must survive the rewrite.

### Task 2: Rewrite the root README around the architectural hierarchy [Depends on: Task 1]

**Context:** `README.md` currently identifies most subsystems but conflates the broad `agnt` control CLI with optional runner orchestration. It also presents a diagram that overgeneralizes the Bead gate and implies that artifact-backed work requires the runner. This task performs the primary information-architecture rewrite without changing system behavior.

**Files:**
- Modify: `README.md`
- Reference: `docs/ARCHITECTURE.md`
- Reference: `docs/AGNT-SYSTEM.md`
- Reference: `docs/ORCHESTRATION-LOOP.md`
- Reference: `pi/agent/bin/README.md`
- Reference: `lesson-server/README.md`

**Steps:**
1. Replace the opening with the approved positioning: opinionated deployable Pi configuration plus the `agnt` routing/workflow-control CLI; direct Pi work is normal and the artifact/runner path is opt-in.
2. Replace the current “Why this exists” inventory with a concise “What you get” layer table that gives the deployable configuration and everyday controls primary prominence.
3. Replace the current system diagram with the default/optional topology above. Scope the Bead requirement to code edits in Beads-enabled projects and branch manual run bundles separately from the runner service.
4. Add a short explanation of root `AGENTS.md` versus deployed `pi/agent/AGENTS.md` so contributors edit the correct policy layer.
5. Rework deployment guidance so `--dry-run` precedes `--apply`, the replacement/preservation warning is adjacent, provider credentials link to `pi/README.md`, and representative commands show `doctor`, routing, context/instructions, and peer discovery without becoming a full CLI reference.
6. Keep the repository workflow concise: `bd prime`, `bd ready`, and `bd show <id>`, followed by a link to `CONTRIBUTING.md` for full verification/review/branch guidance.
7. Add the compact core-concepts table. Keep each definition to one responsibility and link to the architecture documents for detail.
8. Create a clearly labeled optional section for run artifacts, the runner service, Lesson Server, and Graphify. Remove the dedicated Graphify procedure; link to `pi/agent/bin/README.md` or the tracked Graphify skill instead.
9. Rebuild the documentation map by user goal. Put `pi/README.md`, `docs/AGNT-SYSTEM.md`, `docs/ARCHITECTURE.md`, and the command reference before optional runner docs; remove the duplicate runner entry.
10. Retain the repository layout and Lesson Server entry. Replace the detailed private/generated-state path list with the concise security rule and canonical `pi/README.md` link.
11. Remove the full verification matrix from the root; keep only the smallest quick validation command if useful and point contributors to `CONTRIBUTING.md`.
12. Read the complete rewritten README once for narrative flow: what it is → what is installed → how normal work happens → how to deploy/contribute → concepts → optional capabilities → deeper docs.

**Focused verification:**
```bash
rg -n '^## ' README.md
rg -n 'opinionated|direct Pi|agnt route|agnt invoke|agnt instructions|agnt doctor|optional.*runner|Lesson Server' README.md
if rg -n '^### Run Graphify|workflow-compliance\.sh --case|Project-Local Runner Service.*Project-Local Runner Service' README.md; then
  echo 'unexpected duplicated or runbook-level content remains' >&2
  exit 1
fi
git diff --check -- README.md
```

**Expected result:** The root README teaches the correct core/control/state/optional hierarchy, preserves the prior Lesson Server work, and no longer reads as a runner or maintainer runbook.

### Task 3: Align canonical deployment and contributor documentation [Depends on: Task 2]

**Context:** Removing detail from the root README is safe only when canonical lower-level documentation remains complete. `pi/README.md` already owns deployment, credentials, endpoints, and excluded runtime state, but its contents list omits routing tasks and role/model overlays. `CONTRIBUTING.md` owns test commands but currently omits the Ruff command present in the working-tree README change.

**Files:**
- Modify: `pi/README.md`
- Modify: `CONTRIBUTING.md`
- Verify only: `pi/agent/bin/README.md`
- Verify only: `docs/ARCHITECTURE.md`
- Verify only: `docs/AGNT-SYSTEM.md`

**Steps:**
1. In `pi/README.md`, keep the existing deployment and runtime-state wording, then add concise content-list entries for `agent/tasks/`, `agent/AGENTS.d/roles/`, and `agent/AGENTS.d/models/`. Describe tasks as routing policy, roles as delegated-worker stance/output contracts, and model overlays as family/venue-specific context.
2. If needed for completeness, clarify that `agent/settings.json` selects packages and defaults, while `catalog.json` and task files carry model facts and routing policy. Do not duplicate catalog schemas or model inventories.
3. In `CONTRIBUTING.md`, add the documented Ruff command alongside pytest and retain layout/shell checks, deterministic evals, and model-backed workflow compliance. Keep this as the canonical full verification list linked from the README.
4. Confirm that Graphify usage remains documented in `pi/agent/bin/README.md`; do not duplicate it elsewhere.
5. Compare the three edited docs with `docs/ARCHITECTURE.md` and `docs/AGNT-SYSTEM.md`. Do not edit the architecture docs unless there is an actual contradiction rather than a difference in detail.

**Focused verification:**
```bash
rg -n 'agent/tasks|AGENTS\.d/roles|AGENTS\.d/models' pi/README.md
rg -n 'ruff check|pytest|routing-smoke|role-context-smoke|workflow-compliance' CONTRIBUTING.md
rg -n '^## Knowledge graphs|agnt graphify' pi/agent/bin/README.md
git diff --check -- pi/README.md CONTRIBUTING.md
```

**Expected result:** Detail removed from the root remains available in its canonical documentation, the deployed configuration surface is complete, and the Ruff addition survives in `CONTRIBUTING.md`.

### Task 4: Validate the final documentation as a coherent entry point [Depends on: Tasks 2-3]

**Context:** This is a documentation-only reorganization, so validation should prove architectural consistency, link integrity, command validity, source/runtime safety wording, and preservation of the initial working-tree intent. It should not trigger unrelated architecture or implementation changes.

**Files:**
- Validate: `README.md`
- Validate: `pi/README.md`
- Validate: `CONTRIBUTING.md`
- Compare: `docs/ARCHITECTURE.md`
- Compare: `docs/AGNT-SYSTEM.md`
- Compare: `docs/ORCHESTRATION-LOOP.md`
- Compare: `pi/agent/bin/README.md`

**Steps:**
1. Run every command in the plan header. Fix only documentation defects or concrete regressions caused by this work.
2. Run the local-link checker against all edited docs and inspect every root documentation-map destination.
3. Use the `documentation-standards` skill in validate mode. Require a `PASS` result for the working-tree diff or document any intentionally deferred discrepancy in the Bead.
4. Read the README from each intended audience perspective: deployer, repository contributor, architecture maintainer, optional runner operator. Confirm that each can find the next authoritative document without reading unrelated runbooks first.
5. Inspect `git diff -- README.md pi/README.md CONTRIBUTING.md` and confirm the initial Lesson Server additions remain, Ruff is present in the canonical contributor checks, no secrets/examples beyond placeholders were introduced, and runner detail is consistently opt-in.
6. Update the Bead with exact verification evidence. Do not commit, push, merge, or close the Bead without following the repository’s normal completion and approval workflow.

**Focused verification:**
```bash
scripts/check-pi-config.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
git diff --check
git diff -- README.md pi/README.md CONTRIBUTING.md
```

**Expected result:** All deterministic checks pass, documentation validation reports `PASS`, links and displayed commands resolve, and the final diff expresses the approved architectural hierarchy without unrelated changes.

## File conflicts and execution order

| File | Tasks | Resolution |
|---|---|---|
| `README.md` | Tasks 1, 2, 4 | Task 1 records the existing diff; Task 2 rewrites it; Task 4 only applies verified corrections. |
| `pi/README.md` | Tasks 3, 4 | Task 4 validates after Task 3. |
| `CONTRIBUTING.md` | Tasks 3, 4 | Task 4 validates after Task 3. |

The primary work is intentionally serial because the root rewrite determines what detail must remain in supporting docs. Parallel edits would create unnecessary duplication and overwrite risk.

## Out of scope

- Changing `agnt`, Pi extensions, skills, routing policy, providers, models, runner behavior, or deployment scripts.
- Rebuilding Graphify or installing/uninstalling repository hooks.
- Redesigning the runner, run artifact schema, lesson server, or feedback loop.
- Adding generated inventories or hard-coded counts of tasks, skills, roles, models, actions, or evals.
- Committing, pushing, merging, or cleaning the existing working tree without separate authority.

## Execution Handoff

Plan saved to: `.pi/plans/2026-07-21-readme-architecture-reorganization-plan.md` (verify with `test -f`).
Recommended next skills: `writing-clearly-and-concisely` while rewriting, `documentation-standards` in validate mode, and `verification-before-completion` before claiming completion.
