---
name: crafting-apps
description: Use when running approved local Craft CLI or native MCP tools for graphics, media, CAD, documents or spreadsheets, or handing off their files. Not cloud ArtCraft generation, GUI, models or installation authorization.
---

# Crafting Apps — native Pi runtime

This skill grants no installation, enablement or document-edit authority. PhotoCraft, VectorCraft, CADCraft and SoundCraft have accepted global integrations. Remaining apps require recorded installation/native smoke results; source files alone do not prove availability. Inspect current native tool discovery, not stale disabled/absent assumptions. Never replay historical acceptance checkers, root-denial tests or spent budgets. No `pi mcp list` or broad reload as a harmless config check: these start servers.

**pi-setup maintains deployable source.** Launcher: `../../bin/start-craft-mcp.sh`; pinned versions/files: `../../craft/packages.json`; maintained asset hashes and historical origin: `../../craft/source.json`. Runtime needs no artcraft checkout. Installation uses pi-setup's scoped `scripts/update-pi-config.sh --craft` path under bounded approval, not ad-hoc HOME edits. No generic installer, MCP adapter or custom lifecycle supervisor.

## Paths and limitations

Binaries live at `~/.artcraft/<app>-cli-<version>-macos-universal/<app>-cli`. Versions come from package manifest, never `latest`. Launcher accepts one named selector and creates real mode0700 directories under **session cwd**, not automatic Git-root discovery. Existing files/modes survive; symlinks/non-directories refuse. No shared-home fallback. Partial directory creation can remain after failure. Static checks and application roots are **not a sandbox**; all processes inherit user permissions/environment. Avoid concurrent edits to shared files.

| App | Workspace under session cwd | Startup/path boundary |
|---|---|---|
| PhotoCraft | `.artcraft/workspace` | read/write root flags; session cwd retained |
| VectorCraft | `.artcraft/vectorcraft-workspace-recovery` | root flags, headless, config/Fonts isolation; session cwd retained |
| CADCraft | `.artcraft/cadcraft-workspace` | cwd only, no root controls |
| SoundCraft | `.artcraft/soundcraft-workspace` | root flags; session cwd retained |
| FigCraft | `.artcraft/figcraft-workspace` | cwd only; no system fonts |
| DesignCraft | `.artcraft/designcraft-workspace` | cwd only |
| LightCraft | `.artcraft/lightcraft-workspace` | cwd/config isolation only; default in-memory library, not persistent catalog |
| FilmCraft | `.artcraft/filmcraft-workspace` | cwd/data-dir convention only |
| EffectCraft | `.artcraft/effectcraft-workspace` | absolute read/write roots and config directory |
| PdfCraft | `.artcraft/pdfcraft-workspace` | `--root`; relative tool paths resolve inside root |
| WordCraft | `.artcraft/wordcraft-workspace` | absolute read/write roots; relative paths resolve against cwd |
| DeckCraft | `.artcraft/deckcraft-workspace` | cwd only |
| GridCraft | `.artcraft/gridcraft-workspace` | cwd only |

Cwd/config isolation is not filesystem confinement. No network-denial, link-race or full permission-hook guarantee. Do not copy root flags between apps. No implicit OCR/model downloads, plugins, camera/microphone/playback, cloud/paid operations, GUI/attach or real-document access.

## Native operations

Use `<app>-pilot` servers through native Pi. Discover actual schemas with `describeNamespace`, `describeTool` or `searchTools`; never guess parameters or use CLI to bypass denied native calls. Basic source-derived smoke candidates: Fig/Design/Word/Deck/Grid `list_commands {}`; Light/Photo `command_list {}`; Film/Effect `doc_inspect {}`; Pdf `doc_list {}`. Availability must be observed. One successful read-only round-trip establishes installation integration, not editing fidelity, exhaustive security or complete app capability.

Check `{content,isError,structuredContent}`. Some results contain JSON in text blocks; others are plain text. Successful JSON **null** is valid: use optional access, not unconditional `.warnings`. Check per-step results, completed/failed counts and warnings even when outer call succeeds. Batch and undo are not disk transactions. Client cancellation does not prove server cancellation. Never replay ambiguous mutations; inspect state before recovery. `store`/`load` accept JSON data only, never functions/closures. Forward image blocks with `image(block)`, never print base64.

For approved one-shot CLI work use exact pinned executable, quoted argument arrays, bounded outputs/timeouts and fresh paths. Help/version probes are real app starts. Keep editable native files alongside exports; flattened PNG/PDF/audio is not native-state preservation. PhotoCraft's observed two-layer PNG warning is not blanket permission to ignore warnings. Read [VectorCraft details](vectorcraft.md) before its editing/preview workflows.

## Handoff and recovery

Installation-first acceptance requires ordinary native discovery/round-trip and standard Pi runner completion—not mandatory editing campaigns, listening/visual acceptance or custom process observers. Independent process absence is a separate claim requiring evidence.

When user requests editing or takes control: save native plus useful bounded preview/inventory, pause agent edits and show exact paths. Require explicit **handback** before resuming; reopen/check saved state within task authority. Do not assume shared GUI memory, merge conflicting edits or signal another session's process.

Report real calls separately from fake/static tests and skipped features. On errors retain useful diagnostics and completed results. Scoped asset/config backups permit guarded restoration under matching authority; they do not authorize deleting binaries, workspaces or evidence. Unknown ownership/drift, new credentials/network exposure or destructive recovery requires human decision. Historical failures and ledgers stay preserved.
