---
profile_version: 1
repository: https://github.com/danielcherubini/pi-archimedes
last_checked_utc: 2026-10-21T20:37:15.706173+00:00
target_ref: v2.11.1
source_commit: a44f94267239db0ef5d36d18d93391bf9d51c182
status: current-for-target-ref
result_port_status: maintained-fork-local-verified
publication_status: published
publication_verified_utc: '2026-10-21T23:33:39.598053+00:00'
publication_approval: pi-1c7e
npm_meta_published_utc: '2026-10-16T15:19:01.021Z'
npm_meta_integrity: sha512-mtG8nkfEPDusDJgHuf72bT1CePc4TzPQchT9DCEIpbIiYQRqLE5lYMQPwYn3jq5L7OZUPQS4UzRmeYJoxYl+NQ==
npm_meta_registry: https://registry.npmjs.org/pi-archimedes/2.11.1
npm_subagent_published_utc: '2026-10-16T15:21:23.629Z'
npm_subagent_integrity: sha512-5GK78g89o2FCuelZjgRulww+5M0uq0F7RkD9/iGCyvhaTT2zTwmqthVdk8ya9Wc4fA6Jpl8k3ibqr+YbMlZdcg==
npm_subagent_registry: https://registry.npmjs.org/%40pi-archimedes%2Fsubagent/2.11.1
npm_core_published_utc: '2026-10-16T15:19:30.406Z'
npm_core_integrity: sha512-zeiBPDLj6cb9VaFye+1YNGVf/GYH61uTp+tHD2Pwl1+IUz7TXlC7EDGpzNT+GqlkPnDr7gQOmS40HyoYzw3T0A==
npm_core_registry: https://registry.npmjs.org/%40pi-archimedes%2Fcore/2.11.1
maintained_fork_base: a44f94267239db0ef5d36d18d93391bf9d51c182
maintained_fork_head: 59c57a18976f0d470bae8ae6d5704c6715f06ee6
maintained_fork_branch: vendor/pi-setup-2111
superproject_gitlink: 59c57a18976f0d470bae8ae6d5704c6715f06ee6
historical_vendor_head: 8590ec0e1063811f86d1417ded9c2aeb48fd73b6
derived_patch_meta: patches/pi-packages/pi-archimedes-meta-2.11.1.patch
derived_patch_meta_sha256: 44c46ab575f598effc2ca6f00d1b56e60106ab1b387e2c6ba9648c9f2ff9280c
derived_patch_ask: patches/pi-packages/pi-archimedes-ask-2.11.1.patch
derived_patch_ask_sha256: 1e7ab9454a3fabf403654e4c377ec0f0579d14802c155a1da93c49a2b1fe9eb3
derived_patch_core: patches/pi-packages/pi-archimedes-core-2.11.1.patch
derived_patch_core_sha256: cf5e116a07abbe388ceb783dcaa5269d19334c828486120b02118b83612357e6
derived_patch_footer: patches/pi-packages/pi-archimedes-footer-2.11.1.patch
derived_patch_footer_sha256: 4508468a3eb7823c51e849002a4a637e92ef5575b748e0171482c8daccab42eb
derived_patch_subagent: patches/pi-packages/pi-archimedes-subagent-2.11.1.patch
derived_patch_subagent_sha256: 9447255b8af98424151fbe1e6e4a3d7684ff9d0e7642bc25e313734b144278c2
package_proof: scripts/verify-pi-archimedes-package-patches.sh
recheck_every_use:
  - permissions
  - fork-state
  - templates
  - branch-protection-and-ci
  - issue-requirements
source_files:
  - path: README.md
    sha256: 325c048a1d5fd70f6bab5daebf560406add7fb4202d262636d447ade5924b878
  - path: AGENTS.md
    sha256: 9188a8a22e4b1947bfdfae73e03c68caadc882539d7cf27b2d396d29bd024314
  - path: LICENSE
    sha256: 4a69dc29421e26d9c8e50a823a1255c64441020942d4d5d0ecbc2fec8ca0b823
  - path: package.json
    sha256: 5d729c200ad8df64638a34e3132582690f012e9e50d574b0a697d5624c39bab4
  - path: pnpm-workspace.yaml
    sha256: e2d17f54dceda821c6b03fa190eb367171040998b02b98dc42ed5cc6db54522a
  - path: meta/src/index.ts
    sha256: adb18b4c65af1ee2fe1c59ef6b2f48b1f0e4fe0dd0692de6b3172a395a7e6465
  - path: meta/src/plugins.ts
    sha256: c9f878f9267e4791ff101c4267eed75396bb6f6d4b607e1c3e7cc2ccb766ffe7
  - path: packages/core/src/events.ts
    sha256: 80050136f0f3e5d70f9f8488324456feb2b432f6bb382951bd39545a8644c666
  - path: packages/subagent/package.json
    sha256: a698304c33bacb3f16183d6ef78ea30c71e799d6ab7d9394857d6d37a4e89f9b
  - path: packages/subagent/src/index.ts
    sha256: 7b47f54004c5a40ea9c7bbfbd8e19c5eea5e53704095137935b2b40e1941c8ef
  - path: packages/subagent/src/tool-schema.ts
    sha256: 134376fb7a3dfafb226e27d95e5fe42153993441f2c316f8b0cf8f5130262958
  - path: packages/subagent/src/stream.ts
    sha256: 4ea82e4a0d83a7939e14f3483246c16918d5a1eba3c549f4b6c35b6f19a83122
  - path: packages/subagent/src/execute.ts
    sha256: 088c1f1d526c96a0210ca5f1606cd6a03e6923e024bd7e2577130a7e837ab040
---

# danielcherubini/pi-archimedes upstream profile

## Current target and authority

Target is immutable `v2.11.1@a44f942`, not an assumed moving `main` head. Thirteen integrity-verified npm 2.11.1 archives match that tag's package files; only npm's `workspace:*` manifest normalization is permitted. Source and publication timestamps are registry evidence, not a claim of SLSA provenance.

Local maintained source is `vendor/pi-setup-2111@59c57a1`, exactly one commit above the target. Publication is **verified** at the exact maintained head. Initial attempts under `pi-x4j7` and `pi-2zxp` were rejected for missing OAuth workflow scope. After human-reported credential repair, the single create-only attempt under `pi-1c7e` succeeded and fresh `ls-remote` verified `vendor/pi-setup-2111`. Evidence: `.pi/reviews/pi-7zn8/archimedes-publication-auth-complete-result.json`. All attempt grants are consumed; no further push is authorized. No PR, release, merge or live configuration change occurred. Remote permissions, branch protections, templates and current PR state must be rechecked before any remote action; historical ADMIN access is not authority.

Use pnpm 12.5.1 from the fork directory, `--ignore-scripts` for dependency setup, and pinned Pi 1.3.0 development packages. Preserve the `@types/node` 22.19.19 hold. TypeScript ESM, host `pi.events`, native tool-result usage and upstream plugin gates remain native. Diagnostics use `core/log`, not console writes in rendering/event paths.

## Retained and retired contracts

Retained: public `./agents`, `./types`, `./config`; child execution profiles/ceilings/guards; first-stop and partial-output evidence; native output schemas; direct script-callable dispatch; sliding idle leases and ask waits; current-turn/cumulative progress; keyed footer rows; decimal operator-cost settings; optional custom-input shape.

Retired: singleton `./bus` transport and custom cost accumulator. `./events` is native; footer cost follows persisted tool-result usage while progress retains live cost. Core's projection now changes only development SDK pins, not transport or accounting. Native bridge paths cannot bypass managed enforcement. One-shot disables MCP while retaining intentional prompt-template macros.

pi-setup owns routing, billing, quality, artifacts and managed JSON normalization. It disables new sudo/web plugins by default. Native first-run onboarding remains an explicit human UI flow; onboarding state is not tracked. Output contracts and JSON execution status never grant authority or assert review quality.

## Verification and recovery

- Untouched 2.11.1 baseline: recursive TypeScript and 2,511 tests passed.
- Final immutable local candidate: recursive TypeScript and 2,706 tests/168 files passed; independent GPT review found no important defect.
- `scripts/verify-pi-archimedes-package-patches.sh --local-candidate`: thirteen exact npm archives, five projection hashes, all-file base comparisons, byte-exact production projection, strict apply/idempotence/reverse, public type declarations, 859 installed-package tests and two managed-report tests (including real SDK composition) passed.
- Default proof mode retains the remote-ref check. Local-candidate mode explicitly does not establish publication. `scripts/check-vendor-pins.sh` still gates committing root gitlinks and CI.
- No live service or deployment verification is claimed. Remote publication is established; root delivery still requires the full candidate gate and local closeout.

Reinstall exact npm 2.11.1 bases to remove current projections; restore matching root gitlinks and patch files together to recover them. Old custom source remains at `work/pi-840u-idle-limit@8590ec0e1063811f86d1417ded9c2aeb48fd73b6`; old root projection files are recoverable from `76bf0dde8ed341de7ef69053eed227b66552dfd3`. No history was rewritten.

## Historical result-port evidence

Q19V verifies the exact `stvhay/pi-archimedes` stack at `8590ec0`, published `vendor/pi-setup-210`, against npm 2.1.0. Its 111-test record and old typed bus contract remain in `.pi/plans/2026-08-15-pi-archimedes-result-port-contract.md`; they are historical evidence, not current 2.11.1 publication proof. Existing fork-draft branches/PRs are preserved and their current remote state is unverified. External-upstream work remains deferred under `pi-vzqq`.
