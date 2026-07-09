# Production Soak Retrospective: Beads-first orchestration

Date: 2026-07-09
Beads: `pi-2`, `pi-1`, implementation epic `pi-6yg`
Run artifact: `.pi/runs/production-soak-retro`

## Scope

This soak used the completed Beads-first orchestration workflow on real project work before declaring the system production-ready. The session completed the implementation epic `pi-6yg`, including Tasks 5-11 in this continuation, with Beads notes, atomic commits, focused/full verification, command smokes, and peer reviews.

## Evidence of real workflow use

- Beads graph: `pi-6yg.1` through `pi-6yg.13` are closed; `pi-6yg` is closed.
- Run artifact for this retrospective: `.pi/runs/production-soak-retro`.
- Recent commits include:
  - `353db96` / `178ca30` — Beads-backed approval flow and closure.
  - `4d330f7` / `0a5a8d0` — strict ticket gateway and closure.
  - `8b76467` / `30c7d0e` — singleton runner and closure.
  - `e7b7f74` / `de0eba2` — epic worktree policy and closure.
  - `b97b429` / `7cffa44` — health/closeout checks and closure.
  - `2a44bc3` / `2adf153` — maintenance cadence and closure.
  - `c4803e6` / `9323bb3` — docs/eval alignment and epic closure.
- Peer review artifacts exist for Tasks 5-11 under `.pi/reviews/task*/`.
- Final verification for Task 11 passed:
  - `.venv/bin/python -m pytest tests/ -q` → 137 passed.
  - `agnt context-health --strict` → passed.
  - `agnt action validate` → passed.
  - `agnt eval run routing-smoke` → passed.
  - `agnt eval run role-context-smoke` → passed.
  - `scripts/check-pi-config.sh` and `PI_CONFIG_DIR="$PWD/pi" scripts/check-pi-config.sh` → passed.
  - `agnt work health --json` and `agnt work maintenance due --json` emitted valid JSON and passed.

## Failure and recovery events

1. **Legacy run-artifact health failures.** During Task 9, `agnt work health --json` exposed local legacy smoke run artifacts with missing historical Beads refs. Recovery: current-format runs still fail on unsafe unresolved refs, while legacy completed v1 artifacts warn; two never-invoked legacy smoke bundles were superseded in local runtime state. This validated the health command's ability to surface stale artifacts without breaking backward compatibility.
2. **Reviewer stub output.** During Task 10, a gemma review returned a tool-call/stub instead of a substantive review. Recovery: the invocation was annotated `rejected`, the review was rerun with embedded diff context, and the rerun was annotated `accepted` after a substantive PASS.
3. **Repeated Beads role warning.** Many `bd` commands printed `beads.role not configured (GH#2950)`. Recovery: follow-up Bead `pi-4lb` was created to decide whether to configure a repo-local role or document intentional deferral.

## What worked well

- Beads provided durable task state, dependencies, evidence notes, and close reasons across a long multi-task sequence.
- Atomic commits after each implementation/closure pair made recovery points clear.
- TDD caught missing command surfaces before implementation for health and maintenance.
- `agnt work health` caught real stale runtime artifacts and now protects closeout from missing evidence, unresolved decisions, dirty worktrees, and raw-tool bypass markers.
- Peer reviews caught a process issue: artifact-path reviews can return stubs; metrics annotation captured accepted/rejected reviewer quality.
- Documentation and role-context eval updates kept default instructions compact while guarding the new durable-state guidance.

## Friction points

- `bd` repeatedly warned that `beads.role` is unset, which added noise to command output.
- Review peers sometimes require embedded diffs instead of artifact paths to produce substantive output.
- `.pi/runs` is intentionally runtime state, so local health reconciliation did not become part of git history; important findings had to be promoted into Beads notes and this retrospective.
- The runner exists as an explicit project-local loop, but it has not yet been soak-tested as an installed long-running service; this is intentionally deferred.

## Follow-ups

- Created `pi-4lb`: Decide Beads role configuration for pi-setup.
- No additional required follow-up Beads were identified for the completed `pi-6yg` implementation. Maintenance due may still propose review checkpoints from durable signals; those should be evaluated through `agnt work maintenance due --json`.

## Production-readiness assessment

The Beads-first orchestration implementation is ready for local production use as an explicit gated workflow and project-local runner. It is not yet an installed service. Continue to require explicit approval for push, deploy, destructive git operations, Beads history/remotes/hooks, worktree creation/removal, and implementation/refactor work that lacks approved metadata.
