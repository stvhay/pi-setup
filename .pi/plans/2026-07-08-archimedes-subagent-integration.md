# Archimedes subagent integration

Date: 2026-07-08

## Goal

Integrate maintained Pi-native subagent tooling to make it easy to launch, manage, and monitor subagents. This is intended to become a core capability for future orchestration workflows.

## Decision

Use the maintained `pi-archimedes` meta package rather than copying Pi's official `examples/extensions/subagent/` example into the tracked config.

Rationale:

- `@pi-archimedes/subagent` provides subagent dispatch, live TUI streaming, parallel execution, per-agent model overrides, and cost/token tracking.
- `@pi-archimedes/footer` surfaces spend/context status in the footer and consumes subagent cost events through `@pi-archimedes/core`.
- The meta package provides the `/agents` CRUD UI. The standalone `@pi-archimedes/subagent` package does not expose this management UI.
- The meta package also provides `ask` and `todo`, which are relevant for future orchestration: subagents can ask routed questions, and work visibility can be shared across parent/subagent activity.
- A maintained package gives upstream updates via Pi's package manager instead of vendoring an example extension.

## Tracked config changes

- `pi/agent/settings.json`: add `npm:pi-archimedes` to global packages.
- `scripts/bootstrap-pi-config.sh`: preserve `~/.pi/agent/npm/` and `~/.pi/agent/git/` runtime package installs across deploys.
- `pi/.gitignore` and `scripts/check-pi-config.sh`: treat `agent/npm/` and `agent/git/` as generated runtime package state, not source-of-truth config.

## Verified runtime surface

After deploying tracked config and running `pi update --extensions`, Pi's real resource loader reports:

- extension errors: none
- loaded package extension: `~/.pi/agent/npm/node_modules/pi-archimedes/src/index.ts`
- tools: `subagent`, `manage_todo_list`, `ask`
- commands: `todos`, `agents`, `archimedes`

`bootstrap-pi-config.sh --apply` was run again after package installation and preserved `~/.pi/agent/npm/node_modules/pi-archimedes` as expected.

## Verification commands

```bash
scripts/check-pi-config.sh
PI_CONFIG_DIR="$HOME/.pi" scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/ -q
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

All passed on 2026-07-08.

## Follow-up ideas

- Define project/user agent profiles under `.pi/agents/` or `~/.pi/agent/agents/` once we have orchestration roles to codify.
- Evaluate whether future `agnt` orchestration should call Pi's `subagent` tool directly or wrap it through a deterministic helper that records run artifacts.
- Decide whether `manage_todo_list` should become part of the standard orchestration contract for parent/subagent progress visibility.
