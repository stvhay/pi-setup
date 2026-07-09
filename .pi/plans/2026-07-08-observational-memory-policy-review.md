# Observational Memory Policy Review

Date: 2026-07-09
Bead: `pi-6yg.2`
Plan: `.pi/plans/2026-07-08-beads-first-autonomous-orchestration-plan.md`
Package: `pi-observational-memory@3.0.3`

## Source/package review

Reviewed the published npm tarball before adding it to tracked Pi config.

Package metadata:

- npm package: `pi-observational-memory@3.0.3`
- license: MIT
- repository: `https://github.com/elpapi42/pi-observational-memory`
- npm integrity: `sha512-YVbGRKQFRqBnj4K8TUYmRAaP+zpUptkdag3/GlzvmuVYEVi8aCHroPb8cKA8edYaUD2v291mJfojYl1TtTII7g==`
- npm shasum: `3662c36e28ff7d5a668dfe01efa72358b2c08f2e`
- package extension entry: `src/index.ts`
- runtime dependencies: none beyond Pi peer packages; package scripts are `typecheck` and `test` only.

Reviewed implementation surfaces:

- `src/index.ts` registers consolidation trigger, compaction trigger, compaction hook, `/om:status`, `/om:view`, and `recall`.
- `src/config.ts` reads `observational-memory` settings from global/project Pi settings and `PI_OBSERVATIONAL_MEMORY_PASSIVE`.
- `src/hooks/consolidation-trigger.ts` runs observer/reflector/dropper memory workers at token thresholds and appends custom session entries.
- `src/hooks/compaction-hook.ts` renders prepared observations/reflections during `session_before_compact`; it does not call a model in the compaction hook.
- `src/hooks/compaction-trigger.ts` can trigger Pi compaction after token thresholds when not passive.
- `src/tools/recall-observation.ts` exposes `recall(<12-char-id>)` for source-backed evidence from the current branch.
- `src/commands/view.ts` renders memory and attempts to copy it to the OS clipboard.
- `src/debug-log.ts` writes opt-in debug NDJSON under Pi's agent directory and rotates at 10 MiB.

Security/operational notes:

- No install/postinstall script was present in the reviewed package metadata.
- No raw network/client code was found beyond calls through Pi's model registry/agent loop using the selected or configured model.
- The package reads local Pi settings and session branch entries.
- The package writes only via Pi session custom entries and optional debug logs under the Pi agent directory.
- The package uses `child_process.spawn` only for `/om:view` clipboard commands (`pbcopy`, `clip`, `wl-copy`, `xclip`, `xsel`, `termux-clipboard-set`). Treat `/om:view` as a manual convenience command; the planned orchestrator should not depend on clipboard behavior.
- Memory workers send serialized session excerpts to the selected/configured model. Do not enable for sessions containing secrets that should not be sent to that model/provider.
- `recall` is evidence retrieval for a known memory id, not semantic search or canonical state.

Review conclusion: acceptable for tracked config when version-pinned and governed by the policies below.

## Install/config decision

Add the package to tracked reusable Pi config as a pinned package:

```json
"packages": [
  "npm:pi-archimedes",
  "npm:pi-observational-memory@3.0.3"
]
```

Add minimal explicit settings:

```json
"observational-memory": {
  "passive": false,
  "debugLog": false
}
```

Rationale:

- Pinning avoids silent package upgrades through normal package update flows.
- Leaving `model` unset lets memory work use the session/worker-selected model, so the planned routing/budget policy remains the selection authority.
- `debugLog: false` avoids generated runtime debug state by default.
- `passive: false` makes main orchestrator sessions active by default; runner-spawned workers can override with `PI_OBSERVATIONAL_MEMORY_PASSIVE=1` when policy says short runs should record sessions without active memory workers.

No deploy to live `~/.pi` was performed as part of this task.

## Memory/session policy

Canonical state remains:

1. Beads for work, dependencies, blockers, approvals, closeout, and self-improvement work.
2. `.pi/runs` for run contracts, results, evidence, selected model/thinking, session refs, transcript refs, and closeout checks.
3. Git for committed source/config history.

Observational memory is advisory session recall/context only. Observations, reflections, and recall output cannot by themselves satisfy approval, blocker, evidence, verification, closeout, or quality requirements. Important findings must be promoted into Beads or `.pi/runs` before they affect project state.

Policy values:

| Context | Session policy | Observational-memory policy |
| --- | --- | --- |
| Main orchestrator | recorded | active |
| Deep/long worker | recorded | auto/active when thresholds or runner policy justify it |
| Short/simple worker | recorded | passive by default via `PI_OBSERVATIONAL_MEMORY_PASSIVE=1` unless runner policy opts in |
| Review/verification fanout | recorded | auto; prefer active for long/deep reviews, passive for cheap short fanout |
| Human approval/decision | Beads-backed | memory may help recall context but cannot be the approval record |

Runner implications for later tasks:

- Runner-created worker sessions must be recorded by default and named like `run:<id> bead:<id> action:<action>`.
- `.pi/runs/<run-id>/result.yaml` should include `sessionRef`, `transcriptRef`, and, when available, `memorySummaryRef`.
- Runner should set `PI_OBSERVATIONAL_MEMORY_PASSIVE=1` for short/simple worker sessions and leave it unset or set false for deep/long worker sessions.
- Lessons harvest should inspect closed Beads, `.pi/runs`, recorded session refs, and optional memory summaries/recall ids.

## Verification commands

Task verification uses:

```bash
scripts/check-pi-config.sh
PI_CONFIG_DIR="$PWD/pi" scripts/check-pi-config.sh
```
