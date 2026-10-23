# Maintained Pi package projections

Reviewed sources live in `forks/pi-langfuse` and `forks/pi-archimedes`. Change the fork first, then regenerate its deployment artifact and update the gitlink. Preserve vendor history and the publication gate in `scripts/check-vendor-pins.sh`; local verification never authorizes publication or deployment.

## Langfuse: isolated runtime

`langfuse-runtime/` contains compiled ESM and public quality declarations, the maintained Langfuse 6/OTel 3 SDK archive, a production-only npm lock, and `release.json`. The release ID binds source inputs, generated files and installed dependency bytes. Host Pi remains an external peer. The production graph does not use the development-only Pi compatibility ports.

Use npm **12.2.1** with the repository's Node 24 environment; `PI_LANGFUSE_NPM_CLI` names its existing `npm-cli.js`. Nothing installs or upgrades global npm automatically.

```bash
# Development preparation (no install hooks):
(cd forks/pi-langfuse && node "$PI_LANGFUSE_NPM_CLI" ci --ignore-scripts)
# Build into a new, absent directory; review before replacing the tracked projection:
node forks/pi-langfuse/vendor/runtime-release/build.mjs \
  --output /path/to/new-langfuse-bundle --npm-cli "$PI_LANGFUSE_NPM_CLI"
# Requires the clean pinned fork and installed development dependencies:
scripts/verify-pi-langfuse-package-patch.sh
```

The verifier retains integrity-pinned npm 1.7.0 provenance and GNU/Apple patch round-trip checks against historical fork `0ba150f5bd38c1e282feec5a488a918e6076063b`. That patch is **historical only**, not an installer. Current delivery proof runs strict types and the full hermetic fork suite, checks the packed SDK ESM/CJS/types and installed public quality types, rebuilds the projection, verifies fresh/reused actual production installs, audits them, and exercises the managed wrapper/quality ports through real Pi package/resource loading without symlinked runtime dependencies.

Normal deployment prepares `<destination>/runtime/pi-langfuse/releases/<id>` before copying config and activates the settings entry last with `extensions: []`. The wrapper alone registers the extension and uses the same verified release for quality. It never falls back to shared npm. The installer does not activate settings, prune releases, repair changed releases, or touch legacy shared packages; failed stages remain for inspection.

Existing shared Langfuse data needs a separately reviewed, one-time transition for the actual dependency layout. Preserve unrelated packages and recovery bytes; resolve unfamiliar states individually. There is no shipping migration coordinator, supported-version registry or automatic retirement. Auditing the isolated release does not clear advisories in retained shared dependencies. See [deployment and recovery](../../pi/README.md#deployment-evidence-and-recovery).

## Archimedes: exact npm patches

Pi's npm-based git installer cannot consume Archimedes' pnpm monorepo and `workspace:*` specifications directly. Keep `npm:pi-archimedes@2.11.1` as the base and apply these five production projections:

| Package | Maintained contract |
|---|---|
| `pi-archimedes` | Operator controls for bounded subagent defaults. |
| `@pi-archimedes/ask` | Exact optional host-event payloads. |
| `@pi-archimedes/core` | Development SDK alignment; native `./events` replaces the singleton bus. |
| `@pi-archimedes/footer` | Sorted, sanitized, width-bounded extension status rows; Caveman/Ponytail placement. |
| `@pi-archimedes/subagent` | Bounded agentic/one-shot execution, idle/absolute limits, provider cap evidence, repeated-error termination, bounded progress/results and public agents/types ports. |

```bash
scripts/update-pi-config.sh --dry-run
scripts/apply-pi-package-patches.sh --check
scripts/verify-pi-archimedes-package-patches.sh
```

The updater pins only these patch bases in the shared npm manifest, reconciles missing/mismatched/stale bases, then applies patches before copying config. The patch helper preflights every package before mutation, accepts exact already-applied state, and rejects offsets, fuzz, version/source drift and partial patches. It is not filesystem-transactional; interrupted writes need exact-base recovery before reapplication. It does not inspect or patch Langfuse.

The Archimedes verifier checks ancestry/gitlink, five patch hashes, thirteen integrity-pinned npm archives, exact production projection/reversal, declarations and installed contracts. Prepare its development dependencies with `corepack pnpm install --frozen-lockfile --ignore-scripts` in the fork. Its `--local-candidate` mode does not establish publication or satisfy the vendor-pin gate.

Both historical Langfuse and active Archimedes patch proofs exercise PATH `patch` and distinct `/usr/bin/patch`, forbid offsets/fuzz, and compare reversed bytes. Context-bearing diffs avoid Apple patch's ambiguous zero-context reversals. Patch-format whitespace exemptions do not exempt added source lines from tests.

Archimedes retains native child session correlation, `--no-session`, host events and usage accounting; no duplicate cost accumulator or invented invocation ID remains. One-shot disables tools, MCP, ambient resources and persistence while keeping explicit prompt-template macros. Only metered one-shot children receive the wrapper's default provider cap; subscription children do not. New sudo/web plugins stay disabled.

## Provenance and rollout

The prior Langfuse ref `vendor/pi-setup-170` at `0ba150f5` was published under `pi-x4j7`; the new `pi-ox9n` isolated-runtime candidate is separate work, not authority to reuse that grant. Archimedes `vendor/pi-setup-2111` at `59c57a18976f0d470bae8ae6d5704c6715f06ee6` was published under `pi-1c7e`; prior rejected attempts and the consumed successful grant remain recorded. No new publication, merge or live rollout follows from these proofs.

Root `85e075806634fa501d092b6b869491ff486dba57` retains the previous 1.7.0 deployment configuration; root `76bf0dde8ed341de7ef69053eed227b66552dfd3` retains the earlier 1.5.14/Archimedes 2.1.0 projections. A config-only rollback cannot restore their package trees. Verify and approve matching package recovery before selecting old settings.
