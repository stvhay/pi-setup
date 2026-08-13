# Temporary Pi package patches

These version-locked runtime patches project reviewed fork changes onto exact installed npm releases until upstream releases contain them. Reviewed sources are pinned as submodules under `forks/pi-langfuse` and `forks/pi-archimedes`; patches contain only installed production/package files. Each fork's vendor branch combines reviewed work without rewriting or merging its draft PR branches.

Pi's git package installer cannot consume the Archimedes source monorepo directly: it runs npm while that repository requires pnpm and uses npm-unsupported `workspace:*` dependency specs. Keep `npm:pi-archimedes@2.0.1` as the installable base, then apply the exact production projection pinned by `forks/pi-archimedes`.

| Package | Base | Patch |
|---|---:|---|
| `pi-langfuse` | 1.5.12 | Split capability-gated legacy REST ingestion under a 3,000,000-byte request ceiling with dedupe-safe envelope retries, and keep finite ordinary-string bounds while preserving valid media only on the transient OTel extraction path. Logical session IDs, score entity IDs, v4 fallback detection, isolated shutdown steps, and final system-prompt capture are native in the 1.5.12 base. |
| `pi-archimedes` | 2.0.1 | Add `/archimedes` operator controls for bounded subagent defaults. |
| `@pi-archimedes/footer` | 2.0.1 | Preserve Pi's keyed extension-status contract when the Archimedes custom footer replaces Pi's built-in footer. Newline-delimited entries render on separate sorted, sanitized, width-bounded rows without collapsing intentional spacing; Caveman and Ponytail render on the first row whenever space permits—even in split mode—or together on one fallback row. |
| `@pi-archimedes/subagent` | 2.0.1 | Add bounded agentic execution, isolated one-shot execution with best-effort provider-native output caps, exact requested/effective applied evidence, truthful unsupported Codex handling, failed native `length` termination, provider-error propagation, privacy-bounded repeated-error termination, bounded parallel outputs, adaptive turn-token progress, and dual legacy/Pi 0.84 stream parsing. Native v2.0.1 child session/model behavior is preserved; effective provider/profile/limits and output-cap enforcement remain available as result evidence from the pinned vendor submodule. |

Normal deployment pins these patch-base dependencies exactly in the runtime npm manifest, installs missing, mismatched, or stale-patch exact bases, and applies patches automatically:

```bash
scripts/update-pi-config.sh --dry-run
scripts/update-pi-config.sh
scripts/apply-pi-package-patches.sh --check
```

Run `scripts/apply-pi-package-patches.sh` directly only when repairing an already installed exact base without redeploying config.

`--check` is read-only. Apply is idempotent and rejects version, source-context, or incomplete-patch mismatches. Apply is not filesystem-transactional: after an interrupted write or permission failure, reinstall the exact pinned packages before checking and applying again. Remove each patch and its package pin after a verified upstream release includes the corresponding change. Reinstall the exact npm base before moving between materially different patch revisions; partial states fail closed.

The Archimedes projection retains `--no-session`, does not persist child transcripts, and adds no invocation/trace transport. One-shot disables tools, discovered extensions, skills, context files, and persistence; explicit prompt-template macros remain available. The tracked wrapper reads `catalog.json` billing classes and injects a 16,384-token default only for metered one-shot children. Set `PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS` to a positive integer, `0`, or `off` to tighten or disable that local default; explicit tighter call limits win.
