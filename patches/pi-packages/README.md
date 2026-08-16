# Temporary Pi package patches

These version-locked runtime patches project reviewed fork changes onto exact installed npm releases until upstream releases contain them. Reviewed sources are pinned as submodules under `forks/pi-langfuse` and `forks/pi-archimedes`; patches contain only installed production/package files. Each fork's vendor branch combines reviewed work without rewriting or merging its draft PR branches.

Pi's git package installer cannot consume the Archimedes source monorepo directly: it runs npm while that repository requires pnpm and uses npm-unsupported `workspace:*` dependency specs. Keep `npm:pi-archimedes@2.1.0` as the installable base, then apply the exact production projection pinned by `forks/pi-archimedes`.

| Package | Base | Patch |
|---|---:|---|
| `pi-langfuse` | 1.5.14 | Split capability-gated legacy REST ingestion under a 3,000,000-byte request ceiling, preserve valid media only on the transient OTel extraction path, add privacy-controlled versioned tool-payload byte metadata, and expose bounded quality integration ports through the project-local `./quality` export. Logical session IDs, score entity IDs, v4 fallback detection, isolated shutdown, final system-prompt capture, and opt-in source metadata are native in the 1.5.14 base. |
| `pi-archimedes` | 2.1.0 | Add `/archimedes` operator controls for bounded subagent defaults. |
| `@pi-archimedes/ask` | 2.1.0 | Preserve exact optional typed-bus payloads by omitting absent custom input. |
| `@pi-archimedes/core` | 2.1.0 | Publish strict typed cost, todo, and ask bus payloads through the native `./bus` export without changing runtime dispatch or listener isolation. |
| `@pi-archimedes/footer` | 2.1.0 | Preserve Pi's keyed extension-status contract when the Archimedes custom footer replaces Pi's built-in footer. Newline-delimited entries render on separate sorted, sanitized, width-bounded rows without collapsing intentional spacing; Caveman and Ponytail render on the first row whenever space permits—even in split mode—or together on one fallback row. |
| `@pi-archimedes/subagent` | 2.1.0 | Add bounded agentic and isolated one-shot execution, provider output-cap evidence, repeated-error termination, bounded parallel/progress rendering, and dual legacy/Pi 0.84 stream parsing. Public `./agents` and `./types` exports expose configured-model resolution and complete ordered child-result evidence, including output-contract labels and child-session correlation. Native v2.1.0 local model/thinking overrides remain authoritative. |

Normal deployment pins these patch-base dependencies exactly in the runtime npm manifest, installs missing, mismatched, or stale-patch exact bases, and applies patches automatically:

```bash
scripts/update-pi-config.sh --dry-run
scripts/update-pi-config.sh
scripts/apply-pi-package-patches.sh --check
scripts/verify-pi-langfuse-package-patch.sh       # networked exact-tarball/contract proof
scripts/verify-pi-archimedes-package-patches.sh  # networked exact-tarball proof
```

Run `scripts/apply-pi-package-patches.sh` directly only when repairing an already installed exact base without redeploying config. The Langfuse proof verifies the maintained fork/gitlink and patch hashes, downloads the integrity-pinned npm base, proves zero-fuzz apply/reverse and byte-exact fork projection, then runs all 15 installed-package quality contract tests; run `npm ci --ignore-scripts` in `forks/pi-langfuse` first when its test dependencies are absent. The Archimedes proof verifies the exact published fork stack, gitlink, and five patch hashes; matches integrity-pinned npm tarballs to v2.1.0 source; proves zero-fuzz apply, idempotence, byte-exact production projection, and byte-identical reverse; compiles public declarations; and runs 100 installed-package result, execution, agent-resolution, and bus contract tests. Run `corepack pnpm install --frozen-lockfile` in `forks/pi-archimedes` first when its test dependencies are absent.

`--check` is read-only. Apply is idempotent and rejects version, source-context, or incomplete-patch mismatches. Apply is not filesystem-transactional: after an interrupted write or permission failure, reinstall the exact pinned packages before checking and applying again. Remove each patch and its package pin after a verified upstream release includes the corresponding change. Reinstall the exact npm base before moving between materially different patch revisions; partial states fail closed.

The Archimedes projection retains `--no-session`, does not persist child transcripts, and adds no invocation ID or telemetry lookup. `childTrace.sessionId` exposes the same native child session UUID already returned as `childSessionId`; no trace ID is invented. One-shot disables tools, discovered extensions, skills, context files, and persistence; explicit prompt-template macros remain available. The tracked wrapper reads `catalog.json` billing classes and injects a 16,384-token default only for metered one-shot children. Set `PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS` to a positive integer, `0`, or `off` to tighten or disable that local default; explicit tighter call limits win.
