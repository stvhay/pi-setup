---
name: crafting-apps
description: Use when running approved PhotoCraft CLI/MCP or VectorCraft native MCP, or handing off their synthetic previews. Not AI ArtCraft cloud generation, other apps' MCP, GUI or model installation.
---

# Crafting Apps — portable runtime

This skill grants no installation, enablement or execution authority. PhotoCraft is intentionally **disabled**; VectorCraft remains **absent** from managed MCP configuration. Keep those states unless separately approved. Old pilot budgets are not reusable. No checker replay, `pi mcp list`, broad reload or launcher invocation as an installation check: those can start real apps or unrelated servers.

Integration source is maintained in artcraft-setup and explicitly promoted into pi-setup, which alone deploys it. Runtime needs no source checkout. Launcher is `../../bin/start-craft-mcp.sh` relative to this skill directory (normally `~/.pi/agent/bin/start-craft-mcp.sh`). Promoted source commit/hashes are in `../../craft/source.json`. Presence of this skill or launcher does not prove deployment, installed binaries, active MCP or live acceptance. Do not change HOME files directly; request a separately approved pi-setup deployment if paths/config do not match.

## Prerequisites and workspace

Pinned macOS binaries are separately installed, never bundled or downloaded by this integration:

| Selector | Executable under `~/.artcraft/` | Root under Pi session cwd |
|---|---|---|
| `photocraft` | `photocraft-cli-0.9.0-macos-universal/photocraft-cli` | `.artcraft/workspace` |
| `vectorcraft` | `vectorcraft-cli-0.12.0-macos-universal/vectorcraft-cli` | `.artcraft/vectorcraft-workspace-recovery` |

At authorized startup the launcher checks the executable, creates missing real root components mode0700 and execs the app. Existing files/modes stay unchanged; symlinks/non-directories refuse. Roots follow **session cwd**, not skill location or Git discovery; use a trusted real project directory. No shared-home fallback. Partial directory creation can remain after failure. Static checks are not race-proof and **not a sandbox**. MCP inherits user permissions/environment and may start one child per Pi session, even outside trusted projects. Keep binaries and receipts outside document roots; do not concurrently edit the same documents.

VectorCraft adds `--headless`, `VECTORCRAFT_CONFIG_DIR=.artcraft/vectorcraft-workspace-recovery/config` and `VECTORCRAFT_NO_PREFS=1`, preparing `config/Fonts`. Read [VectorCraft restrictions](vectorcraft.md) before any approved native work; ordinary lifecycle acceptance remains blocked.

## Approved PhotoCraft operations

PhotoCraft 0.9.0 has bounded synthetic CLI/native MCP and two-project human acceptance evidence, not full-suite certification. Current disabled state still requires explicit enablement approval. Lifecycle permission does not authorize arbitrary document edits, overwrites, real user content, network/paid operations, scripts/plugins, GUI or model installation. No automatic download/reinstall, quarantine removal, ad-hoc signing or cloud fallback.

Use native `photocraft-pilot` for MCP work. Discover current schemas through `describeNamespace`, `describeTool` or `searchTools`; inspect command IDs/parameters with `command_list`. Never infer arguments or switch to CLI to bypass a denied native operation. For separately approved CLI tasks, use the pinned executable via bash with quoted paths/argument arrays, timeouts and fresh outputs; inspect `--help` and `commands` only within execution authority. Supported one-shot interfaces are `run`, `info`, `convert`.

Check `isError`, warnings and per-step `completed`, `failed` and results. PhotoCraft batches can report outer success despite failed steps; inspect document/history before recovery. Undo only known undoable edits, never assume file saves are undone. Unexpected warning, timeout, partial batch, path collision or conflicting state means stop and preserve evidence, not retry mutations.

PNG flattens editable layers. The observed two-layer conversion warning is `warning: 2 layer(s) flattened; layers, masks and blend modes are not kept`; do not generalize it into permission to ignore other warnings. Keep `.pcraft` originals.

## Human handoff

1. Save native plus a bounded PNG preview to fresh approved paths. Record native hash/inventory, dimensions and layers. PNG is a preview, not editable-state preservation.
2. Pause edits and let the owned native session stop within its authority. Show preview through Pi `read`; identify native path and ask for human acceptance or feedback. Never answer for the human.
3. Require explicit **handback** before resuming. Only within fresh/remaining authority, reopen the saved native file, inspect state and compare preview/hash. Do not assume shared GUI memory.
4. On drift or shutdown failure, preserve artifacts and stop for reconciliation. Never signal another session's process or silently merge changes.

Report mocked/static checks separately from real application evidence. Offline/network-denial, exhaustive permission hooks, GUI, models and whole-home effects remain unverified. No rollback or cleanup without exact ownership/path/hash review and separate authority; retain failed outputs and historical ledgers.
