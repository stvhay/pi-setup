# Extension web compatibility

This matrix covers the packages configured in `pi/agent/settings.json` and tracked extensions under `pi/agent/extensions/`. Baseline is Pi 0.83.0 RPC hosted by agent-os.

## Boundary

- Portable `select`, `confirm`, `input`, `editor`, `notify`, `setStatus`, text-array `setWidget`, `setTitle`, and editor-text calls work unchanged after RPC readiness.
- Pi 0.83.0 binds extensions before attaching its RPC stdin reader. Blocking `session_start` prompts therefore cannot consume browser responses. Runtime configuration must be provisioned first or the extension must defer the prompt.
- `archimedes.ts` composes the installed Archimedes public package entrypoint while replacing only its `ask` registration. The wrapper requires `selectionMode: "single" | "multi"` and migrates stored legacy `multi` arguments through `prepareArguments`. TUI and headless calls convert to legacy arguments and delegate to Archimedes' captured public tool contract, preserving its custom picker/accessibility and child ask socket; RPC alone uses portable dialogs because custom TUI components are unsupported there.
- `langfuse-config-env.ts` locks the managed preset to `conversations`, overriding any saved preset while preserving explicit false input/output flags. Its package-only proxy supplies bounded allowlisted clones for every pi-langfuse 1.5.7 content-bearing agent, turn, provider, message, tool, and compaction registration. Tool payloads/errors, provider headers/bodies, compaction summaries/details, and system/developer/tool conversation content stay out; handler mutations or replacements cannot alter real events, local handlers, or persistence. Unrelated package methods and events still pass through.
- `agent-os-compat.ts` activates only for `--mode rpc`. It supplies `/reload`, text todo/subagent widgets, and the browser-internal `/agent-os-package` adapter. The package adapter accepts only strict `install npm:<name> <approved-version>`, `remove npm:<name>`, or bounded selected `update npm:<name> <approved-version>` pairs after browser approval. It installs approved versions exactly while retaining unpinned project settings, rejects baseline/pinned/non-project updates, reports partial failures, reloads after any success, and skips reload when all selected updates fail. Settings flush and progress cleanup precede terminal `ctx.reload()`.
- Ponytail package skills are filtered from automatic discovery while its extension remains enabled. `ponytail-skill-input.ts` handles explicit `/skill:ponytail*` input from users and package aliases, resolves the installed package root from Pi command provenance, and reads the canonical skill body on each invocation. Ponytail still owns aliases, mode state, status, and active-mode prompt injection.
- Arbitrary TUI components, component widgets, custom headers/footers/editors, terminal input listeners, themes, and autocomplete have no exact browser parity. Browser-owned controls replace decorative chrome; unsupported management screens remain unavailable.

## Configured packages

| Package source | Carrying version | Classification | Browser behavior and evidence |
| --- | --- | --- | --- |
| `npm:pi-archimedes` | 1.8.3 | Adapted / partial | Package entrypoint autoload is disabled and `archimedes.ts` calls its public entrypoint through the installed package resolver, suppresses only the upstream `ask` tool registration, and registers one strict portable replacement. Normal TUI retains Archimedes components, commands, lazy tools, child ask socket, and notifications. RPC uses portable ask dialogs plus text todo/subagent widgets; custom `/archimedes` settings and `/agents` manager, component header/footer/editor, and exact terminal-input behavior remain unavailable there. Package evidence: public manifests and entrypoints for `pi-archimedes` and `@pi-archimedes/{core,footer,diff,subagent,ask,image-paste,todo,notify}`. |
| `npm:@mariozechner/clipboard@0.3.9` | 0.3.9 | Unchanged / no UI | Clipboard helper exposes no Pi extension UI. Browser image/clipboard interaction remains host-owned. |
| `npm:pi-observational-memory@3.0.3` | 3.0.3 | Unchanged | Uses portable notifications for status, warnings, and `/om:*` command output. |
| `npm:pi-langfuse@1.5.7` | 1.5.7 | Preconfigured + public composition | Package entrypoint autoload is disabled. Before calling its public entrypoint, `langfuse-config-env.ts` sets the managed privacy ceiling used by runtime config and `/langfuse-status`, then proxies every content-bearing registration with event-specific sanitized clones. Correlation, accounting, safe conversation content, and generic failure state remain available; real events, local subscription alias/restore handlers, persistence, and exact downstream normalization remain unchanged. Commands use portable select/input/notifications. Agent-os provisions `pi-langfuse/config.json` before launch, preventing its blocking startup setup flow; other RPC deployments must do the same or defer setup until ready. |
| `git:github.com/langfuse/skills@13a79944c3c16cde049bb39576102cd768baa06b` | 13a79944 | Unchanged / no UI | Skill files add instructions, not Pi extension UI. |
| `git:github.com/mattpocock/skills@2ab958093e83e0ec752e6c1c5932da465bf23e0c` | 2ab95809 | Unchanged / no UI | Filtered skill files add instructions, not Pi extension UI. |
| `git:github.com/DietrichGebert/ponytail` | 16f2980 tested | Locally composed | Package extension remains unchanged and uses portable keyed status updates and a startup notification. Package skills are excluded from automatic discovery; explicit skill commands and extension aliases load canonical installed bodies through the tracked input adapter. |
| `npm:pi-caveman` | 1.0.7 | Unchanged / partial | Level commands, notifications, and keyed status work unchanged. The custom `/caveman config` TUI remains unavailable; direct `/caveman <level>` commands preserve the essential workflow. |
| `npm:betterwright` | 1.5.2 | Unchanged | Browser download approval uses portable confirm. BetterWright browser rendering remains its own host integration. |

## Tracked extensions

| Extension | Classification | Browser behavior |
| --- | --- | --- |
| `agent-os-compat.ts` | RPC adapter | Text-only todo/subagent widgets, terminal in-process `/reload`, and strict project-local catalog package install/remove after agent-os approval; inactive outside `--mode rpc`. User-scope baseline packages remain source-controlled and read-only. |
| `archimedes.ts` | Public composition adapter | Preserves Archimedes public composition except its upstream `ask` registration, then registers one strict-schema wrapper. TUI/headless execution delegates to the captured public tool after legacy conversion; RPC uses portable dialogs. |
| `beads-ask-bridge.ts` | Adapted | Durable questions require and persist explicit selection mode; multi mode collects all selected options while distinguishing cancellation from an explicitly empty selection. Approvals remain confirm-only. |
| `guidance-edit-guard.ts` | Unchanged | Portable warning notifications. |
| `langfuse-config-env.ts` | Public composition adapter | Reads pre-provisioned config, locks the managed `conversations` ceiling, gives only package-owned provider and message-output telemetry bounded sanitized clones, keeps startup notification non-blocking, and surrounds upstream telemetry with a transient subscription alias that is removed before persistence. |
| `olla-provider.ts` | Unchanged / no UI | Provider registration has no extension UI. |
| `orchestrator-service.ts` | Unchanged | Portable status, text widgets, and notifications; agent-os strips ANSI styling. |
| `ponytail-skill-input.ts` | Package composition adapter / no UI | Restores explicit `/skill:ponytail*` commands after package skill discovery is disabled. Reads package-owned bodies at invocation time and leaves active-mode injection to Ponytail. |
| `subagent-error-workaround.ts` | Unchanged / no UI | Tool-result normalization has no extension UI. |
| `ticket-gateway.ts` | Unchanged | Portable confirm, notifications, and text widgets. |

## Verification

```bash
scripts/check-pi-config.sh
.venv/bin/python -m pytest tests/test_agent_os_compat.py
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/
```

`tests/test_agent_os_compat.py` executes the RPC adapter and Archimedes composition with fake Pi contexts, verifies one strict `ask` registration plus legacy argument migration, upstream TUI/headless delegation, and RPC-only portable execution, checks `/reload` ordering and package argument rejection, exercises install/remove against Pi's real package manager with a fake npm process, covers text todo rendering and privacy-preserving per-task subagent progress, checks inactivity outside RPC, requires one matrix row per configured package, and rejects TUI-only APIs in tracked extensions. `tests/test_pi_packages.py` also proves package skill-only filtering and explicit Ponytail command expansion from canonical invocation-time bodies.
