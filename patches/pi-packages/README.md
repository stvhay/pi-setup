# Temporary Pi package patches

These version-locked runtime patches project reviewed fork changes onto exact installed npm releases until upstream releases contain them. Reviewed sources are pinned as submodules under `forks/pi-langfuse` and `forks/pi-archimedes`; patches contain only installed production/package files. Each fork's `vendor/pi-setup` branch combines reviewed work without rewriting or merging its draft PR branches.

Pi's git package installer cannot consume the Archimedes source monorepo directly: it runs npm while that repository requires pnpm and uses npm-unsupported `workspace:*` dependency specs. Keep `npm:pi-archimedes@1.8.3` as the installable base, then apply the exact production projection pinned by `forks/pi-archimedes`.

| Package | Base | Patch |
|---|---:|---|
| `pi-langfuse` | 1.5.9 | Prefer Pi's logical `SessionManager.getSessionId()` before the legacy session-file fallback and assign stable entity IDs to queued scores. |
| `pi-archimedes` | 1.8.3 | Add `/archimedes` operator controls for bounded subagent defaults. |
| `@pi-archimedes/subagent` | 1.8.3 | Preserve child session correlation; add bounded agentic and isolated one-shot execution; expose globally bounded parallel child outputs from fork branch [`vendor/pi-setup`](https://github.com/stvhay/pi-archimedes/tree/vendor/pi-setup). |

Normal deployment installs missing, mismatched, or stale-patch exact bases and applies patches automatically:

```bash
scripts/update-pi-config.sh --dry-run
scripts/update-pi-config.sh
scripts/apply-pi-package-patches.sh --check
```

Run `scripts/apply-pi-package-patches.sh` directly only when repairing an already installed exact base without redeploying config.

`--check` is read-only. Apply is idempotent and rejects version, source-context, or incomplete-patch mismatches. Apply is not filesystem-transactional: after an interrupted write or permission failure, reinstall the exact pinned packages before checking and applying again. Remove each patch and its package pin after a verified upstream release includes the corresponding change. Reinstall the exact npm base before moving between materially different patch revisions; partial states fail closed.

The Archimedes projection retains `--no-session`, does not persist child transcripts, and adds no invocation/trace transport. One-shot disables tools, discovered extensions, skills, context files, and persistence; explicit prompt-template macros remain available.
