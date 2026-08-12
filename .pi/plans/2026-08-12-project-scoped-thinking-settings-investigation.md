# Project-Scoped Pi Thinking Settings Investigation

**Issue:** pi-woca

**Runtime verified:** `@earendil-works/pi-coding-agent` 0.84.1

**Date:** 2026-08-12

## Verdict

Pi already supports a native project default: trusted `<launch-cwd>/.pi/settings.json` overrides `~/.pi/agent/settings.json`, including `defaultThinkingLevel`. Use that file for stable repository defaults. Use `--thinking <level>` or `--model <provider>/<model>:<level>` for invocation-only overrides.

One leak remains: changing thinking after startup through `/settings`, Shift+Tab, RPC, or `pi.setThinkingLevel()` appends session state **and writes the global default**. Project-pinned repositories remain isolated on their next launch, but unpinned repositories inherit that global change.

No defaults changed during this investigation.

## Verified resolution rules

Startup resolves thinking in this order, highest precedence first:

1. `--thinking <level>`.
2. Thinking suffix on explicit `--model ...:<level>` when `--thinking` is absent.
3. Explicit level on selected `--models`/`enabledModels` pattern for a new session.
4. Latest `thinking_level_change` on a resumed session.
5. Merged `defaultThinkingLevel`: trusted project setting, then global setting.
6. Pi's built-in `medium` fallback when no setting exists.
7. Selected model's supported-level map clamps the resolved level last.

Additional boundaries:

- Project settings are loaded only after project trust resolves. In non-interactive mode, untrusted project settings are ignored unless `--approve` applies or trust was saved.
- Project path is exactly `<runtime cwd>/.pi/settings.json`; Pi does not search upward for it. Resuming a session resolves runtime services from the session header's cwd.
- A resumed session with a thinking entry outranks project/global defaults. An older session without one inherits the merged default once, then Pi appends a thinking entry.
- CLI override on an existing session is invocation-only: it does not replace the prior persisted thinking entry unless a later runtime change creates a real state transition.
- Model selection and thinking selection are separate. Model suffixes and scoped-model pins can request a level, but model capability clamping determines the effective level.

## Runtime and documentation evidence

Pi 0.84.1 sources and docs agree on project merge behavior:

- `docs/settings.md` documents global `~/.pi/agent/settings.json`, project `.pi/settings.json`, project-over-global merge, and `defaultThinkingLevel`.
- `dist/core/settings-manager.js:27-29,141` deep-merges global then project settings.
- `dist/core/settings-manager.js:169-172` suppresses project settings when project trust is false.
- `dist/main.js:350-403` gives explicit model selection precedence over scoped-model startup selection, then applies explicit `--thinking` last.
- `dist/main.js:525-529,559-580,675-679` binds runtime services and project settings to the opened session's cwd.
- `dist/core/sdk.js:116-130` restores session thinking, falls back to merged settings, then clamps to model capabilities.
- `dist/core/defaults.js:1` defines the unset fallback as `medium`.
- `docs/session-format.md` defines persisted `thinking_level_change` entries.

Runtime mutation is broader than project scope:

- `dist/modes/interactive/interactive-mode.js:3693-3697` routes `/settings` thinking changes to `session.setThinkingLevel()`.
- `dist/core/agent-session.js:1275-1293` appends a session entry and calls `settingsManager.setDefaultThinkingLevel()` on a real change.
- `dist/core/settings-manager.js:493-496` writes that default to global settings, not project settings.

## Reproduction evidence

Tests used temporary global/project directories, `PI_OFFLINE=1`, a dummy `OPENAI_API_KEY`, no extensions/resources, and RPC `get_state`; no provider request ran. Temporary global settings selected `openai/gpt-5.5` at `xhigh`; temporary trusted project settings selected `low`.

| Case | Effective level |
|---|---|
| Global default only | `xhigh` |
| Project file present but `--no-approve` | `xhigh` |
| Trusted project override | `low` |
| Trusted project plus `--thinking high` | `high` |
| Trusted project plus model suffix `:medium` | `medium` |
| Explicit `--thinking high` plus model suffix `:minimal` | `high` |
| Resumed session containing `high`, project default `low` | `high` |
| Same resumed session plus `--thinking medium` | `medium` |
| Old session without thinking entry, project default `low` | `low`; Pi appended `low` |
| GPT-5.5 request `:minimal` | `low` after capability clamp |

The startup probe shape was:

```bash
printf '%s\n' '{"type":"get_state"}' |
  env PI_CODING_AGENT_DIR="$temporary_agent_dir" \
      PI_OFFLINE=1 OPENAI_API_KEY=dummy \
  pi --mode rpc --no-session --approve \
     --no-extensions --no-skills --no-prompt-templates \
     --no-themes --no-context-files [override flags]
```

Mutation probe:

```json
{"type":"get_state"}
{"type":"set_thinking_level","level":"medium"}
{"type":"get_state"}
```

Observed sequence and files:

```text
state=low
set=true
state=medium
global_after_runtime_change=medium
project_after_runtime_change=low
next_project_launch=low
```

A separate `--thinking medium` startup left the temporary global setting at `xhigh`, confirming CLI isolation.

## Repository configuration flow

- `pi/agent/settings.json` is this repository's tracked **global** config source and currently sets `defaultThinkingLevel` to `xhigh`.
- `scripts/update-pi-config.sh` deploys tracked `pi/` to `~/.pi`, preserving runtime credentials, sessions, trust state, and only Pi's runtime-managed changelog marker from settings.
- Repository-root `.pi/` is project metadata, not part of deployable `pi/`. A root `.pi/settings.json` therefore remains project-scoped and is not copied to `~/.pi/agent/settings.json`.
- `scripts/check-pi-config.sh` rejects tracked runtime secrets/state. `defaultThinkingLevel` itself is non-secret and safe to track in a project's `.pi/settings.json`.

## Smallest safe mitigation

For each repository that needs a stable default, track this at the directory where Pi starts:

```json
{
  "defaultThinkingLevel": "high"
}
```

Trust that project and restart Pi once so settings load. Choose each repository's measured level; do not duplicate global model/package configuration.

For one run, launch with:

```bash
pi --thinking medium
# or
pi --model openai-codex/gpt-5.6-sol:medium
```

When isolation matters, avoid runtime thinking controls unless every affected project has its own pinned default. No extension, wrapper, migration, or Pi fork is needed for current project/invocation use cases.

If durable session-only mutation becomes necessary, upstream Pi would need a persistence-scope option separating session entry writes from `setDefaultThinkingLevel()`. That is not required for this mitigation and should not be added locally without a concrete workflow that project settings plus launch flags cannot cover.
