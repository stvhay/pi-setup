# Extension web compatibility

This matrix covers the packages configured in `pi/agent/settings.json` and tracked extensions under `pi/agent/extensions/`. Baseline is Pi 0.83.0 RPC hosted by agent-os.

## Boundary

- Portable `select`, `confirm`, `input`, `editor`, `notify`, `setStatus`, text-array `setWidget`, `setTitle`, and editor-text calls work unchanged after RPC readiness.
- Pi 0.83.0 binds extensions before attaching its RPC stdin reader. Blocking `session_start` prompts therefore cannot consume browser responses. Runtime configuration must be provisioned first or the extension must defer the prompt.
- `agent-os-compat.ts` activates only for `--mode rpc`. It supplies portable `ask` behavior, `/reload`, and the browser-internal `/agent-os-package` adapter. The package adapter accepts only strict `install npm:<name> <approved-version>`, `remove npm:<name>`, or bounded selected `update npm:<name> <approved-version>` pairs after browser approval. It installs approved versions exactly while retaining unpinned project settings, rejects baseline/pinned/non-project updates, reports partial failures, reloads after any success, and skips reload when all selected updates fail. Settings flush and progress cleanup precede terminal `ctx.reload()`. Pi TUI and headless subagent behavior remain unchanged.
- Arbitrary TUI components, component widgets, custom headers/footers/editors, terminal input listeners, themes, and autocomplete have no exact browser parity. Browser-owned controls replace decorative chrome; unsupported management screens remain unavailable.

## Configured packages

| Package source | Carrying version | Classification | Browser behavior and evidence |
| --- | --- | --- | --- |
| `npm:pi-archimedes` | 1.8.3 | Adapted / partial | Local RPC adapter replaces the custom-component `ask` tool with sequential portable dialogs, mirrors active `manage_todo_list` state into a text widget, and translates subagent progress updates into privacy-safe keyed widgets with one status line per task, agent/tool labels, and tool counts but no task prompt text. Todo and subagent widgets clear when their work ends. Portable notifications remain unchanged. Custom `/archimedes` settings and `/agents` manager, component header/footer/editor, and exact terminal-input behavior remain unavailable. Package evidence: `src/settings.ts`, `@pi-archimedes/ask/src/{picker,dialog}.ts`, `@pi-archimedes/todo/src/ui/todo-widget.ts`, `@pi-archimedes/{core,footer,subagent,notify,image-paste}/src/`. |
| `npm:@mariozechner/clipboard@0.3.9` | 0.3.9 | Unchanged / no UI | Clipboard helper exposes no Pi extension UI. Browser image/clipboard interaction remains host-owned. |
| `npm:pi-observational-memory@3.0.3` | 3.0.3 | Unchanged | Uses portable notifications for status, warnings, and `/om:*` command output. |
| `npm:pi-langfuse@1.5.7` | 1.5.7 | Preconfigured + unchanged | Commands use portable select/input/notifications. Agent-os provisions `pi-langfuse/config.json` before launch, preventing its blocking startup setup flow; other RPC deployments must do the same or defer setup until ready. |
| `git:github.com/langfuse/skills@13a79944c3c16cde049bb39576102cd768baa06b` | 13a79944 | Unchanged / no UI | Skill files add instructions, not Pi extension UI. |
| `git:github.com/mattpocock/skills@2ab958093e83e0ec752e6c1c5932da465bf23e0c` | 2ab95809 | Unchanged / no UI | Filtered skill files add instructions, not Pi extension UI. |
| `git:github.com/DietrichGebert/ponytail` | 16f2980 tested | Unchanged | Uses portable keyed status updates and a startup notification. |
| `npm:pi-caveman` | 1.0.7 | Unchanged / partial | Level commands, notifications, and keyed status work unchanged. The custom `/caveman config` TUI remains unavailable; direct `/caveman <level>` commands preserve the essential workflow. |
| `npm:betterwright` | 1.5.2 | Unchanged | Browser download approval uses portable confirm. BetterWright browser rendering remains its own host integration. |

## Tracked extensions

| Extension | Classification | Browser behavior |
| --- | --- | --- |
| `agent-os-compat.ts` | RPC adapter | Portable `ask` dialogs, text-only todo/subagent widgets, terminal in-process `/reload`, and strict project-local catalog package install/remove after agent-os approval; inactive outside `--mode rpc`. User-scope baseline packages remain source-controlled and read-only. |
| `beads-ask-bridge.ts` | Unchanged | Portable select/confirm after durable Beads decision creation. |
| `guidance-edit-guard.ts` | Unchanged | Portable warning notifications. |
| `langfuse-config-env.ts` | Unchanged | Non-blocking startup notification only; reads pre-provisioned config. |
| `olla-provider.ts` | Unchanged / no UI | Provider registration has no extension UI. |
| `orchestrator-service.ts` | Unchanged | Portable status, text widgets, and notifications; agent-os strips ANSI styling. |
| `subagent-error-workaround.ts` | Unchanged / no UI | Tool-result normalization has no extension UI. |
| `ticket-gateway.ts` | Unchanged | Portable confirm, notifications, and text widgets. |

## Verification

```bash
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/test_agent_os_compat.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
```

`tests/test_agent_os_compat.py` executes the RPC adapter with fake Pi contexts, verifies `/reload` idle/reload ordering and argument rejection, exercises install/remove against Pi's real package manager with a fake npm process, covers trust, duplicate, baseline, missing-package, flush-before-reload, and terminal reload behavior, verifies no startup UI call occurs, covers single/multi-question responses, text todo rendering, and privacy-preserving per-task subagent progress, checks inactivity outside RPC, requires one matrix row per configured package, and rejects TUI-only APIs in tracked extensions.
