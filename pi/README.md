# Pi Config

Deployable Pi configuration for this setup repository. The repository root [README](../README.md) is the documentation entry point; this file focuses on the contents and deployment behavior of `pi/`.

The tracked `pi/` tree is the source of truth. The default Pi runtime directory, `~/.pi`, is a deployed copy that may also contain ignored runtime state.

## Deploy or update the runtime copy

From the repository root:

```bash
scripts/update-pi-config.sh --dry-run    # validate source; itemize managed changes
scripts/update-pi-config.sh              # back up, update ~/.pi, verify local config
scripts/apply-pi-package-patches.sh      # Archimedes only, after pinned installation
scripts/verify-pi-langfuse-package-patch.sh  # historical provenance + real isolated delivery
```

The update helper preserves runtime secrets/state and installs helper commands into `~/.pi/agent/bin`, including:

```bash
agnt --help
```

Langfuse uses the compiled, lock-controlled projection in `patches/pi-packages/langfuse-runtime/`, not the shared npm package tree. The updater verifies and installs it at `<destination>/runtime/pi-langfuse/releases/<content-hash>`, verifies reused releases byte-for-byte, then activates the tracked settings entry with `extensions: []`. The managed wrapper alone registers the extension and resolves its public quality port from that same release, with no shared-package fallback. `pi-langfuse/quality` is active. The maintained build requires Langfuse Cloud or self-hosted **4.59.0+** and uses Langfuse 6/OpenTelemetry 3, v4 OTLP, v2 observation readers and the scores batch endpoint; legacy trace polling and ingestion fallback are gone.

Fresh installation needs **npm 12.2.1** in the repository's Node 24 environment. Set `PI_LANGFUSE_NPM_CLI` to its `npm-cli.js` if it is not the selected npm executable. The helper never upgrades global npm, runs install scripts, bundles the host Pi SDK, or prunes old releases. Failed stages remain for diagnosis. See [package projections](../patches/pi-packages/README.md) for build and verification commands.

**Existing shared Langfuse installations:** activation does not remove their files, declarations or old dependencies. Handle the actual installation as an explicit one-time transition: inspect its dependency sharing, retain recovery bytes, and approve exact changes without overwriting unrelated packages. Unfamiliar layouts require a specific resolution, not automatic rejection or a generic migration engine. A clean isolated-release audit is not an audit of the retained shared tree.

Pi still installs npm packages such as `pi-archimedes@2.11.1` and `@mariozechner/clipboard` into the preserved `agent/npm/` root. Normal deployment applies only the five maintained Archimedes patches there. `scripts/apply-pi-package-patches.sh --check` inspects those exact bases; apply repairs matching bases without touching Langfuse. Forks remain authoritative: sync the Langfuse gitlink and regenerated runtime projection together, or the Archimedes gitlink and patches together. `scripts/check-vendor-pins.sh` still requires published vendor commits before a root gitlink commit. Publication, integration and live deployment retain their separate approval gates.

Langfuse skill and Matt Pocock skill packages intentionally track their default branches without refs; `pi update --extensions` advances those unpinned checkouts after source review.

### Deploy one existing extension, guidance file, or lifecycle helper

For a bounded fix without reconciling unrelated config or packages:

```bash
scripts/update-pi-config.sh --dry-run --file agent/extensions/zz-output-redaction.ts
# Only after approval of this exact file, hashes, and target:
scripts/update-pi-config.sh --file agent/extensions/zz-output-redaction.ts
```

`--file` accepts one existing top-level `agent/extensions/NAME.ts` file (not `.local.ts`) or exactly `agent/bin/start-craft-mcp.sh`, `agent/AGENTS.md`, `agent/skills/token-saver/SKILL.md`, or `agent/bin/agnt_lib/work_lifecycle.py`. The two guidance paths allow output-discipline updates without bulk deployment touching local settings, packages, or runtime installations. Preview and approve each exact file before applying; reload or restart Pi afterward to load guidance. The lifecycle helper exception supports a bounded handoff repair and takes effect in the next `agnt` process. No other shell scripts, Python helpers, or arbitrary managed paths are allowed. Both paths must be regular files with no symlink components beneath the canonical roots; the Craft launcher must already be executable at source and destination. Preview prints before/after SHA-256 hashes and writes nothing. Apply preserves destination permissions, checks for preparation-time drift, atomically replaces only that file, and verifies its bytes. Identical bytes are a no-op. No package actions, config deletions, settings/MCP updates, app starts or automatic restart occur. A single-file Langfuse wrapper update additionally requires the matching installed release, settings and resolver library; otherwise use a reviewed full update.

After separately approved, verified source promotion, the Craft-only preview is:

```bash
scripts/update-pi-config.sh --dry-run --file agent/bin/start-craft-mcp.sh
# Only after approval of this exact file, hashes, and target:
scripts/update-pi-config.sh --file agent/bin/start-craft-mcp.sh
```

This replaces the existing launcher, not the Craft binaries or skill. It does not add/enable servers or authorize document operations. The changed launcher is used only at the next separately authorized app start.

Recovery bytes and a verification receipt remain in the printed private `runtime/deployment-backups/file-*/` directory as `before.ts` for an extension, `before.sh` for the Craft launcher, `before.md` for guidance, `before.py` for the lifecycle helper, and `receipt.json`. Existing extension receipt/backup behavior is unchanged. This is a one-file backup, not a full-deployment backup; no bulk `restore.sh` is generated. After separate rollback approval, verify current bytes against the receipt's `afterSha256`, preview `rsync -a --dry-run --itemize-changes <backup>/<before-file> <exact-destination-file>`, then use `rsync -a --chmod=<original-mode> <backup>/<before-file> <exact-destination-file>` and verify `beforeSha256`. Choose the matching `before.ts`, `before.sh`, `before.md`, or `before.py`; use the receipt's `beforeMode` for `<original-mode>`. Recovery bytes are deliberately mode 0600. Stop on drift or ambiguous ownership. A failed apply retains the backup; no automatic retry or rollback.

### Craft tools and native MCP — scoped installation

pi-setup now maintains the reusable launcher, named package pins, disabled MCP template and portable `crafting-apps` guidance. `agent/craft/source.json` v2 checks five maintained asset hashes/modes and retains the exact former four-file Artcraft promotion as `origin`. Historical v1 manifests remain verifiable. Edit maintained source here, update hashes, test/review and commit; do not pretend new bytes came from the old Artcraft commit. Artcraft's old source copies and acceptance evidence remain historical.

`agent/craft/packages.json` pins all thirteen macOS universal CLI releases, source commits, HTTPS asset URLs, archive sizes/SHA256 and already-verified file manifests. No binaries enter Git. The supported delivery entry point is separate from bulk deployment:

```bash
# Preview only. Local path is optional; omit it on a new machine.
scripts/update-pi-config.sh --dry-run --craft --craft-local /path/to/artcraft-setup/.artcraft
# Only within approved source/target/effect bounds:
scripts/update-pi-config.sh --craft --craft-local /path/to/artcraft-setup/.artcraft --craft-download
# Optional explicit selection and enablement (also requires approval):
scripts/update-pi-config.sh --dry-run --craft --craft-apps figcraft,designcraft --craft-enable
```

`--craft` installs selected packages (default thirteen), deploys **only** launcher, `craft/{mcp,packages,source}.json` and `skills/crafting-apps/{SKILL,vectorcraft}.md`, then reconciles native server entries. No bulk rsync, npm updates, settings/trust changes, deletions or app starts. `--craft` cannot combine with `--file`; other Craft options require `--craft`. Preview has no network or HOME writes and identifies missing archives; it cannot certify their contents until acquisition.

Package helper reuses verified local installations, otherwise cached pinned archives under `~/.artcraft/downloads/`; network requires `--craft-download`. HTTPS-only curl verifies exact size/hash before extraction. ZIP validation refuses escaping paths, links/special files, duplicates, unexpected modes and excessive expansion; bundled licenses/readme remain. Files stage under a unique `.artcraft/.<app>-stage-*`, pass content verification, universal architecture and strict all-architecture Developer ID team `DJ6XS33FX8`/online notarization checks, then move to the absent versioned destination. This is not full Gatekeeper equivalence or reproducible-build attestation. Existing installations must match exact files/modes; mismatches refuse, never overwrite. Failed downloads/stages remain for diagnosis. Success receipts live in `.artcraft/receipts/`. No quarantine removal, ad-hoc signing, GUI/model/plugin install or app execution.

MCP template contains thirteen disabled `<app>-pilot` entries, **not** runtime `agent/mcp.json`. Reconciler accepts only each named app's exact deployed launcher/selector and stdio; PhotoCraft also accepts its historic launcher for migration. Existing enablement (including absent/default), cwd, env, timeout, exposure and unrelated JSON survive. Missing entries default disabled. `--craft-enable` enables only selected apps explicitly; it does not approve arbitrary operations. Duplicate JSON/names, unowned entries, invalid templates or unsafe paths fail. Matching state is a byte/inode-preserving no-op. Bulk deployment retains its separate boundary and never implicitly acquires Craft binaries or enables missing entries.

**Capabilities:** Photo/Vector/CAD/Sound retain previously accepted global integrations. The remaining nine also passed basic native read-only smoke under artcraft-setup-l3q.12/3f0; all13 are globally enabled. One standard native Pi session,18read-only attempts (nine full retained result receipts after evidence-store correction), runner exit0/no error. Original four entries/settings preserved, R config restored, S override absent. Global config SHA25652bcbfd6782903722e441a51dace73502b7057aad0caeb62dac0f76ad573cf45; launcher SHA2566b62dbc748f762769deda715eff300215d296788d5f3b1fcc7538a74c7a91262. Final source pins e91edc0; historical failed Fig stage retained. Batch authority retired, ordinary pinned lifecycle only. Canonical outcome: artcraft-setup `.pi/plans/2026-10-20-craft-installation-batch-completion.md`, private final receipt2447300d. No more live acceptance needed for closeout. All supported launches are stdio. CAD/Fig/Design/Light/Film/Deck/Grid lack root controls; workspace cwd is **not confinement**. Photo/Vector/Sound/Effect/Word pass supported read/write roots; Pdf uses its distinct `--root`. Light defaults to an in-memory library; no persistent catalog/OCR/RAW/models promise. Launcher creates cwd-relative workspaces only on authorized starts. No OS sandbox, whole-home audit or network-denial claim.

**Installation acceptance:** pinned binary available, native tool discovery plus one useful read-only round-trip, standard Pi runner completion and useful errors; focused offline tests/idempotence. No mandatory editing campaign, two-project parity, human preview/listening gate, independent process-absence observer or destructive rollback drill. Full feature/security certification is separate. Do not rerun existing app acceptance or spend old pilot grants.

**Recovery:** exact prior asset bytes are mode0600 under `runtime/deployment-backups/craft-assets-*/before/<relative-path>`; receipt records old/new hashes/modes and per-file verification. MCP changes retain exact private `craft-*/before.json` and receipt. A partial batch is not transactional: retain completed installs and both backups. Within matching rollback approval, require current hash/mode equals recorded after-state, restore only the named previous file with its beforeMode and verify beforeSha256; stop on drift. If no previous file existed, disable matching added entries and retain files unless exact deletion is separately approved. Do not run bulk `restore.sh` for Craft-only recovery. Removing binaries/workspaces/backups or changing unrelated settings is excluded. Safe corrections may proceed inside an explicitly approved batch; never replay ambiguous mutations. Static checks do not protect against hostile concurrent writers.

```bash
python3 -B scripts/check-craft-promotion.py pi
.venv/bin/python -B -m pytest tests/test_craft_batch.py tests/test_craft_promotion.py tests/test_update_pi_config.py
# Historical source provenance plus maintained-target integrity, from artcraft-setup:
python3 -B scripts/test-craft-promotion.py /path/to/pi-setup
```

### Deployment evidence and recovery

Updater output uses `STEP:` labels and ends with `OK:`, `WARNING:`, or `FAILED:`. `WARNING` means the command succeeded but emitted diagnostics; it does not change the exit code. Noisy validation, install, patch, and apply-copy output stays in the printed `Logs:` directory (`${TMPDIR:-/tmp}/pi-update.*`, mode 0700; log files mode 0600). Stderr is always shown; stdout lines containing `warn`, `warning`, or `deprecated` are also shown. Failed commands replay their stdout as well, retaining the existing failure exit codes. Treat logs as private: tool diagnostics may contain local paths or sensitive values. Logs are not automatically pruned by the updater, but OS temporary-file cleanup may remove them; retain needed evidence separately.

Identity, backup/rollback paths, scoped receipts, and dry-run commands/itemized changes remain visible. `OK: Preview only` confirms no destination changes, not a successful deployment. Full-apply file details remain in backup `changes.txt`; logs supplement, never replace, recovery backups.

Use the script for deployment-only work; do not rebuild its steps or rerun an unchanged verified revision's full development suite. Confirm the approved source revision and compare the script's canonical source, destination, host, and user with the approved target. `--dry-run` validates source layout and runs rsync's itemized preview without changing the destination. Package install/patch steps are planned, not executed. Apply still requires the deployment approval contract. The preview is not an authorization receipt: callers must recheck source, target, and effects before apply; drift requires a new preview/approval.

Apply validates source layout, prepares the isolated Langfuse release, saves managed config under `<destination>/runtime/deployment-backups/<unique-id>/`, reconciles Archimedes packages before copying managed config, activates settings last, then validates live layout. Copying uses checksums so equal-size/equal-timestamp changes are not missed. Each mode-0700 backup contains `config/`, `identity.txt`, `changes.txt`, a dry-run-by-default `restore.sh`, and post-deploy `verification.txt` when reached. Backups exclude credentials, sessions, installed packages, metrics, and runtime stores; no full runtime copy is needed. Failures retain evidence and return nonzero. No automatic config rollback or backup pruning occurs.

For recovery, inspect the printed backup path and run `bash <backup>/restore.sh` to preview. After separate approval, `bash <backup>/restore.sh --apply` restores managed config, including deletion of newly added managed files, while preserving the current runtime `lastChangelogVersion`. Both modes check the recorded canonical paths. Run `PI_CONFIG_DIR=<destination> scripts/check-pi-config.sh` afterward. Recovery does not restore package versions/npm manifests, credentials, legacy Git metadata, or retired machine-local extensions; package reinstall failure recovery remains separate. Before restoring a prior isolated-release settings entry, verify that retained release with `install-pi-langfuse-runtime.py --check`; restoring a legacy shared entry also needs its corresponding package recovery. Review changes made since the backup before applying it.

Local deployment never applies remote evaluator changes, even when credentials are configured. Use separately approved `agnt langfuse apply` for that operation; do not move or hide credential files to make local deployment safe.

### Codex subscription defaults

The 2026-10-25 Codex 0.164.0 catalog refresh was checked against the same account used by Pi. Enabled subscription models are GPT-6 Astra, GPT-6.1 Sol, GPT-5.6 Terra and GPT-6 Luna; Spark is absent from that catalog and removed from the enabled list (not a claim of global retirement). Astra at medium remains the startup default. Sol uses the provider's 500,000-token default context; the other three retain 272,000. All four accept text/image and native low/medium/high/xhigh/max reasoning. Pi's minimal is a low alias; off is disabled. `agent/models.json` corrects bundled metadata and `agent/catalog.json` mirrors routing capabilities.

The catalog's optional 872,000-token maximum and delegation-based `ultra` are not enabled. Codex's 95% effective-context factor is client headroom, not a second model limit; Pi retains its own reserve/compaction policy. Existing Pi 128,000-token output metadata is unchanged: the refreshed Codex catalog supplies no output-token limit. No inference or large-context boundary probe was run. See [portfolio evidence](../docs/MODEL-PORTFOLIO-2026-08.md#codex-subscription-catalog-refresh--2026-10-25). Deployment remains separately approved.

### Observational memory

`pi-observational-memory@3.1.4` pins the [published worker-stream fix](https://github.com/elpapi42/pi-observational-memory/releases/tag/3.1.4). The 3.1 series improves provider-specific worker routing and preserves context when memory is empty; existing V3 settings need no migration. Compaction uses the active conversation model's context in ratio mode: `floor(model.contextWindow × 0.75)`. For Sol, 500,000 × 0.75 = 375,000 tokens; Astra, Terra and Luna remain at 272,000 × 0.75 = 204,000 tokens. Models without a usable context window fall back to the explicit 81,000-token calibrated threshold.

Pi's native auto-compaction threshold is `contextWindow - reserveTokens`: 483,616 tokens for Sol, or 255,616 for the other three, with Pi's default 16,384-token reserve. Native Pi and observational memory use different token counters, but the configured gap (108,616 tokens for Sol; 51,616 for the others) keeps routine threshold crossings separate. A narrow asynchronous race can still occur around a new prompt; observational memory rechecks after deferral and rejects duplicate compaction hooks. Native and manual compactions still use the prepared observational-memory summary.

Background observer, reflector, and dropper workers use `openai-codex/gpt-6.1-sol` with `low` thinking. The package exposes one shared worker model, so this cannot target reflection alone. Compaction itself does not call a model; it renders prepared memory state.

### Archimedes subagents

Omit `agent` for a generic subagent call:

```json
{"task": "Review the current diff", "routingTask": "review"}
```

Copy route-generated `routingTask`; wrapper removes it before child execution and uses it only as a bounded telemetry category. Omission records `peer`. Supplying `agent` selects a named definition; it is not a task label or an alias for generic mode. Create named definitions with `/agents` before using them. Current discovery paths are:

- project: `<git-root>/.pi/agents/*.md`
- user: `~/.pi/agent/agents/*.md`
- optional global/legacy: nearest `<git-root>/.agents/agents/*.md`, then `~/.agents/agents/*.md`

The current Archimedes package documentation incorrectly says generic calls default to a named `general` agent and places user definitions under `~/.pi/agents/`. In practice, explicit `"agent": "general"` requires a definition named `general`; only omission selects generic mode.

`agent/extensions/subagent-error-workaround.ts` normalizes Archimedes results for local telemetry: failed child exits are marked as errors, every nonzero exit without stronger evidence receives safe `process-error` termination, and each available `childSessionId` is copied into the parent projection, metric, and private result artifact as the exact child-trace foreign key. Metrics preserve bounded routing task, resolved effective mode/thinking, and output contract without prompt or output bodies. Parent projections also declare resolved effective mode and whether child telemetry is expected; isolated one-shot children are expected unavailable unless an already-discovered completed root proves otherwise. Absolute `time-limit` and sliding `idle-limit` failures remain distinct, with caller/operator source plus effective duration or idle evidence.

The v2.11.1 runtime projection preserves native child-session plus local model/thinking override behavior and adds per-child request, tool, token, cost, absolute-duration, sliding-idle, and fanout controls; bounded legacy/Pi 1.3 stream reconstruction; adaptive turn-token progress; bounded parallel outputs; and privacy-bounded repeated-error termination. Valid child lifecycle, model-stream, and tool-stream events renew idle time; parent display heartbeats and malformed output do not. Human `ask` waits pause idle time without pausing parent cancellation or absolute duration. Public `@pi-archimedes/subagent/agents`, `@pi-archimedes/subagent/types`, and `@pi-archimedes/core/events` ports expose configured-model resolution, complete ordered child-result evidence, and host-event payloads without moving routing, billing, persistence, or quality policy into Archimedes. One-shot mode permits one provider request, disables tools, MCP and ambient project resources, keeps explicit prompt-template macros available, and has no implicit wall deadline. `maxOutputTokens` is applied best-effort through supported provider payloads and reports requested plus exact effective applied ceilings or truthful `unsupported` evidence without dropping output or usage. Any provider `length` stop is failed `output-limit` termination; native/unsupported caps do not invent an exact ceiling. Pi's current Codex Responses payload exposes no provider output-cap field, so Codex runs unchanged with truthful `unsupported` evidence.

Script callers now receive managed JSON reports when native reports are available: `{ mode, results }`. Inspect each `results[i].executionOutcome` (`succeeded`, `failed`, `unavailable`), not promise fulfillment, to determine execution status. `outputStatus` distinguishes included, truncated, omitted and unavailable output. Inline/unspecified JSON answers share a 12,000-character budget in request order; `artifact`, `status-only` and `pass-no-findings` omit answer bodies in single and parallel JSON. Private artifacts and `details.results[]` retain complete output. Reports add `artifact.status`, opaque `artifact.refs`, and normalized `terminationEvidence`; persistence failure is explicit, not a reason to replay work. The managed wrapper retains any-failed-child `isError` behavior while returning available JSON evidence; failures without a native report still reject through the text-error path. This is a script return-type migration, not a quality verdict. See [model orchestration](agent/bin/README.md#model-orchestration).

Native `pi.events` replaces the singleton bus, and native tool-result usage replaces the cost accumulator. Progress displays live child cost; footer totals update after result persistence. `archimedes.sudo.enabled` and `archimedes.web.enabled` are explicitly false: upgrading does not enable new privilege/web tools. Native onboarding is a human-only choice flow; no onboarding state is tracked. The Archimedes vendor ref is published and locally verified; Langfuse has a separate maintained delivery boundary. These proofs do not authorize live deployment.

The tracked Archimedes wrapper reads `agent/catalog.json` rather than inferring billing from provider names. Metered one-shot children receive a 16,384-token default provider output cap; subscription-backed and agentic children receive no automatic token or cost cap. An explicit tighter call cap wins. Set `PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS` to a positive integer, `0`, or `off` to tighten or disable the local default. Output-contract prompt patterns, reasoning-budget cautions, and termination-source interpretation are documented in [`agent/bin/README.md`](agent/bin/README.md#model-orchestration).

Do not hand-edit deployed runtime copies. Make changes under tracked `pi/`, verify them, then deploy.

### Reload or restart Pi

`/reload` refreshes settings, extensions, skills, prompts, themes, and context files inside the current process. It does not load a new Node runtime.

`/restart` and agent-callable `restart_pi` share one graceful process-replacement path that resumes same persisted session by its exact file path, avoiding session-ID lookup after replacement. With no command they restart directly. `/restart <shell command>` or `restart_pi.command` runs command from Pi session cwd before resuming after status 0, nonzero, or child-only SIGINT-style status; this command capability is equivalent to `bash` for authorization and approval. Shell output inherits terminal directly and has same disclosure boundary as `bash`. Explicit whitespace-only commands and NUL are rejected, as are sessions whose exact recovery command exceeds the 1,000-character diagnostic bound. Only one process replacement may be pending; duplicate requests fail before adding another exit listener.

`/nvim` and agent-callable `nvim` use same path to open Nvim in foreground, then resume exact persisted session after exit. They accept zero paths or one relative path; slash-command spaces belong to path. Paths are trimmed and normalized, receive `--` before path, and reject absolute paths, NUL/newlines, or lexical traversal outside session cwd. Validation is lexical rather than symlink sandboxing, and missing paths remain valid so Nvim can create files.

Both flows require interactive TUI mode and Node 24 on macOS/Linux. Windows, alternate runtimes, missing `process.execve`, and ephemeral `--no-session` sessions fail before shutdown. Relay or terminal termination cannot guarantee automatic resume; diagnostics retain exact session-file recovery guidance.

### Browser permissions

`agent/extensions/browser-permissions.ts` composes BetterWright's public Pi extension. Package autoload is disabled to prevent duplicate tools. **Downloads default to `allow` in every project:** authorized task downloads need no extra dialog, including through ordinary `browser` calls. This does not authorize executing downloaded files. Browser instructions reflect the effective policy. Only a short discovery/safety pointer and download-policy summary load into the system prompt. `browser_evidence initialize` returns the full upstream operating guidance alongside the checklist; return/read that complete result before further browser calls, including when using codemode. Initialization must not share a batch with browser actions. Guidance repeats for each new journey, not on proofs/audits or ordinary browser calls, and initialization never expands the system prompt. This is guidance deferral, not a new authorization gate; existing policy enforcement remains unchanged.

Optional files live in `.perms/` directly under the Pi session working directory (canonical path, no ancestor search):

| File | Meaning |
| --- | --- |
| `.perms/downloads` | One value: `allow`, `ask`, or `deny`. `ask` uses the existing per-step `browser_download` confirmation; `deny` disables downloads. |
| `.perms/net-allowlist` | Exclusive permitted destinations. Missing file leaves destinations unrestricted; an empty/comment-only file denies all network destinations. |
| `.perms/net-blocklist` | Denied destinations. Block rules win over allow rules. |

Each network file contains one hostname or IP per line, optionally followed by a port. Blank lines and whole-line `#` comments are ignored. Example:

```text
# Exact host, not its subdomains
example.com
# Subdomains only, not example.org itself
*.example.org
localhost:3000
127.0.0.1:8000
[::1]:9000
```

Hosts match case-insensitively with a trailing DNS dot normalized. Ports match the effective port, including default 80/443. IPv6 literals require brackets; mapped IPv4 addresses match their IPv4 form. Use ASCII/punycode DNS names. URLs, paths, regex, CIDR, inline comments, malformed rules, symlinks/special files, invalid UTF-8, and files over 64 KiB are rejected rather than ignored. Both original hostname and resolved address are checked against block rules on guarded local transports; hostname allow rules do not require duplicating DNS addresses.

Use `/browser-permissions` to inspect effective policy. After creating, changing, or deleting policy files, run **`/browser-permissions approve`**. It previews the canonical project, download mode and exact parsed lists, asks once through Pi's trusted UI, saves a fingerprint-bound receipt, and reloads Pi. Reload closes browser tabs but retains persistent logins. Subsequent matching requests need no confirmation unless downloads explicitly use `ask`. Changed policy blocks browser tools/commands and new guarded network requests until approval/reload; queued work is revalidated before dispatch. Invalid policy must be fixed first. Headless runs can reuse approvals but cannot create them. No startup approval dialog is shown.

An explicit host `BETTERWRIGHT_PI_DOWNLOAD_POLICY=allow|ask|deny` overrides `.perms/downloads`; otherwise the project value overrides default `allow`. Launch Pi with the changed environment; the effective mode participates in the approval fingerprint. Ordinary Pi `/trust` and Beads approvals do not substitute for this browser policy receipt. Receipts live under `<agent-dir>/../runtime/browser-permissions/` (normally `~/.pi/runtime/browser-permissions/`) and survive config deployment. They are private runtime state, not repository content. Removing previously approved policy files also requires approval, so deletion cannot silently widen access.

**Boundary:** these rules cover BetterWright's intercepted browser traffic, including redirects/subresources—not shell commands, extensions, devices, host-side provider/vault services, or a machine-wide firewall. Public/private/loopback access remains upstream-default unless restricted here; cloud-metadata protections remain intact. Local guarded transports additionally check resolved IPs. Ordinary remote/CDP providers lack that transport guard and do not provide equivalent DNS-rebinding/egress guarantees. Existing responses/connections cannot be retroactively revoked; close/restart the browser when immediate teardown is needed. Receipts prevent accidental/project-file self-approval, not tampering by arbitrary code with the same OS user's filesystem access.

BetterWright remains unpinned; this adapter was checked against 2.9.0 on 2026-10-23. Pi 1.4 test SDK prompt sections preserve later plugin additions (including Caveman); explicit whole-prompt overrides keep their native semantics. The test SDK's upstream-constrained dependency exceptions are approved in Bead `pi-qqmy`, with exact versions and revisit conditions in [the implementation plan](../.pi/plans/2026-10-23-deferred-browser-guidance-design-plan.md). It uses public `pi-extension`, `policy`, and `prompt` exports and refuses an incompatible download-prompt contract. Review upstream changes before deployment rather than editing installed package files.

### Beads work in the footer

`agent/extensions/beads-footer.ts` adds one keyed status without replacing the active footer. `agnt work status` includes each Bead's `issueType` and orders in-progress rows from explicit Beads parent metadata: included parents come before their children; roots and siblings sort by priority, then stable `created_at`, then natural ID. Missing creation times fall back to natural ID. It never infers parentage from ID text and ignores `updated_at`, preventing footer reshuffling after edits. Rows remain newline-delimited: `◐ ◆ <id>  P<priority>  <title>` for Epics and `◐   <id>  P<priority>  <title>` otherwise. The fixed type slot keeps ID, priority, and title columns aligned. Warm theme colors mark only `◐`; non-session details stay muted, while the current-session details use bold default text. Pi's built-in footer renders the keyed status natively; the version-locked Archimedes footer patch renders each Bead entry on its own sorted, sanitized, width-bounded row without collapsing column spacing. Archimedes places the exact `caveman` and `ponytail` statuses on its first row whenever they fit—even when stats split onto a second row—otherwise together on one fallback row; other statuses retain dedicated rows. The status refreshes on session startup/reload and after tools that can change Beads; empty, malformed, or failed reads clear it. This data remains presentation-only and is not added to model context.

### Continue work or start the next Bead

Unfinished assigned work uses `handoff_bead` checkpoint/resume or assignment-scoped switching without success, commit or closure prerequisites. Same-Bead resume permits a shared direct checkout; relocation uses a reserved child in an approved existing checkout of the same canonical repository, preserving source files and immutable session history. Shell `cd` does not relocate Pi. Tool and slash-command routing use inspected source state; incompatible options fail before writes. A refusal before reservation is not an uncertain launch. Recover actual pending effects only by their exact transition ID. See [lifecycle contract](agent/bin/agnt_lib/work_lifecycle.SPEC.md) for validation and host limits. A disposable SDK-host test performs actual Node process replacement, checking target instructions, tools, headers, ledger attachment and closeout; it does not prove installed/live-TUI rollout. Helpers, adapters and matching guidance need coherent, separately approved deployment.

After recording a successful outcome, committing task-owned changes, and cleanly closing the current Bead, agents call `handoff_bead` without a target. A persisted TUI session with no ownership records may instead call `handoff_bead` with an explicit ready target; omitting the target retains automatic selection. This ready-work path requires successful outcome and cleanly closed source Bead, or a genuinely unassigned session; it is distinct from unfinished continuation. Sole ready non-epic work continues automatically; several ready choices produce one bounded selection and are revalidated before handoff. Failed or partial successful-closeout bookkeeping and malformed/conflicting ownership stop. Closed non-success work has a separate reserved departure path: its actual owning session, retained outcome, canonical closure disposition, settled effects and captured next-work scope are required. Destination must be clean and already exist; use approved isolation to preserve dirty source work. Attachment ends execution without rewriting outcomes. No terminal worktree creation, foreign-owner sweep or success-dependent push/integration authority is inferred.

Handoff stages one empty parent-linked session, gracefully shuts down current Pi process, then uses Node 24 `process.execve` to start that session with bounded Bead references and instructions to run `bd prime`, `bd ready`, and `agnt work direct-start <id> --claim`. Fresh work retrieves only referenced Beads and artifacts; source transcript is not copied. Best-effort private telemetry counts normalized attempt, preflight, selection, validation, staging, restart, shutdown, and replacement result classes plus durations; records contain no Bead/session IDs, paths, prompts, outputs, or error text and stay outside invocation/routing totals. Predictable pre-shutdown failures leave current session running. Nonzero shutdown exit removes staged session and reports fresh-session recovery; `execve` failure preserves staged session and reports exact target recovery. Diagnostics are bounded and credential-redacted. Flow is TUI-only, requires persisted session, and has same Node 24 macOS/Linux boundary as `/restart`. If automated handoff is unavailable, `/new` is human fallback. Fork and clone remain separate exploration features, not work-item transitions.

## Contents

- [`agent/AGENTS.md`](agent/AGENTS.md) — global Pi agent instructions
- `agent/AGENTS.d/roles/` — delegated-worker stances and output contracts
- `agent/AGENTS.d/models/` — family-wide and venue-specific instruction overlays
- `agent/settings.json` — shared Pi settings, package declarations, and selected runtime overrides
- `agent/catalog.json` — model family catalog: maps each family to configured direct OpenRouter/Codex targets and records cost classes, billing classes, context, rates, and model-overlay keys
- `agent/tasks/` — operational routing labels and preferred, qualified, or avoided model targets
- `agent/actions/` — action templates that bind routing task, skills, role, allowed effects, and output contract
- [`agent/bin/`](agent/bin/) — helper commands used by skills and instructions; see the [agnt command reference](agent/bin/README.md)
- `agent/evals/` — deterministic routing, prompt, and instruction checks
- `agent/extensions/` — Pi extensions
- [`agent/skills/`](agent/skills/README.md) — Pi skills, task-first selection and canonical procedure owners

For the conceptual overview, see [The agnt System](../docs/AGNT-SYSTEM.md). For the implementation map, see [Architecture](../docs/ARCHITECTURE.md).

Normal Pi sessions use direct inspect/edit/test tools. Code-changing work must have a Bead before editing. Manual `agnt work` artifact workflows remain explicit opt-in orchestration; long-lived Pi runtime automation belongs in a separate project.

Tool-output discipline lives in `agent/AGENTS.md` and the [token-saver skill](agent/skills/token-saver/SKILL.md): retain verbose logs privately, return status/excerpts/artifact paths, scope browser reads after discovery, and filter independent batches before printing. This is agent guidance, not automatic truncation or a summarization service; failures, required full reads, and proof remain intact. Static checks verify guidance presence, not measured token or latency savings.

## Provider credentials

Provider credentials belong in Pi's ignored `auth.json`, the shell environment, or ignored local env files—not in git. Pi has a built-in OpenRouter provider: run `/login openrouter` or set `OPENROUTER_API_KEY`. `models.json` uses per-model cost, context, thinking and 16,384-token output-cap overrides; it does not duplicate the provider, endpoint, or credential. OpenAI/Codex remains the default root provider; direct OpenRouter is reserved for fresh bounded delegated calls under the approved [model portfolio](../docs/MODEL-PORTFOLIO-2026-08.md). No local or relay provider is configured.

`agent/extensions/zz-output-redaction.ts` defensively redacts credential-shaped values at shared tool, assistant-output, and extension-diagnostic boundaries while preserving surrounding status, exit, path, and error evidence. Structured tool results are redacted alongside visible content, retaining MCP envelopes and error flags for codemode. Canonical base64 PNG data with a PNG signature stays opaque; this is not an image-content privacy check, and other binary formats do not yet have this exemption. RPC and JSON text/thinking deltas are withheld until complete redacted end/final events are available. User input is not rewritten; credentials still belong in managed stores or environment references, never prompts or command literals.

The Langfuse extension and official Langfuse skill share credentials from private `~/.pi/agent/pi-langfuse/config.json`. During Pi sessions, `langfuse-config-env.ts` exposes that config to Langfuse CLI child processes; explicit `LANGFUSE_*` credentials still take precedence. No second credential file is needed.

Before registering the verified maintained Langfuse release, the public wrapper sets the `conversations` preset and unconditionally disables tool I/O, tool-payload byte metadata, system prompts, cwd, and absolute-path capture. Explicit `LANGFUSE_CAPTURE_INPUTS=false` and `LANGFUSE_CAPTURE_OUTPUTS=false` remain disabled. The wrapper adds no package-event proxy sanitizer: `pi-langfuse` owns redaction and payload shaping. When `PI_LANGFUSE_MAX_STRING_LENGTH` is unset, the package's finite 12,000-character ordinary-string default applies. Valid Langfuse-extractable media may bypass that cap only in capture-enabled generation input on the transient OTel path; malformed media and other surfaces use bounded markers, and retained OTLP retries never contain raw media. Explicit operator overrides, including `PI_LANGFUSE_MAX_STRING_LENGTH=off`, remain supported; disabling the cap carries memory, network, ingestion, storage, disclosure, and denial-of-service (DoS) risks.

Tracked evaluator desired state lives in `agent/langfuse/evaluators.json`; `agnt langfuse check` reports drift and `agnt langfuse apply` creates or updates managed evaluators and rules without deleting unmanaged resources. The owned subagent extension emits explicit `interactive-result` and `subagent-result` observations with captured task/output; outcome evaluation samples 10% of interactive results and subagent quality evaluates 100% of delegated results. Parent-owned full delegated results live under `agnt runtime-path delegated-results`; tool results and telemetry expose bounded opaque refs, not absolute private paths. Parent projections, metrics, and artifacts retain the child's logical Pi session UUID as `childSessionId`, enabling exact Langfuse session lookup without timestamp/model matching. Parent projection metadata adds validated effective mode and declared child-trace expectation; improvement scans resolve count-only actual states from the existing bounded trace discovery without extra Langfuse calls or raw child IDs in safe summaries. Config deployment leaves remote evaluators unchanged; reconciliation is a separately approved `agnt langfuse apply` operation. Interactive Pi startup checks asynchronously, stays silent when current, and warns when drift exists. `langfuse-config-env.ts` composes the installed public entrypoint: subscription generations use the zero-priced `*-subscription` alias only while upstream telemetry handles `message_end`, then restore the catalog model ID before session persistence. Private improvement scans leave raw Langfuse records unchanged and normalize legacy plus versioned tool payload-byte metadata downstream without copying tool payloads. Non-null versioned values are exact UTF-8 sizes of bounded, shaped payloads, not raw unbounded payload sizes.

Example direct OpenRouter smoke test after authentication:

```bash
pi --print --provider openrouter --model minimax/minimax-m3.1-flash \
  --thinking medium "Reply with OK only."
```

## Optional service endpoints

Some helpers use environment-provided local or self-hosted services. Keep these values in a shell profile or ignored `.envrc.local.d/*.sh` files, not in git:

```bash
export SEARXNG_URL=https://your-searxng.example
```

`SEARXNG_URL` enables `agnt web-search`. No local or relay model provider is configured; restore prior provider code from Git history only after explicit approval.

### Local Laya decisions

`agent/extensions/laya.ts` registers `laya_predict`, an explicit advisory tool, not a model provider or automatic routing gate. It posts to fixed `http://127.0.0.1:8001/v1/systemone` with the English checkpoint. No custom server or project Python dependency is needed. Install the shared CLI once, then run its server separately:

```bash
uv tool install --python 3.12 'laya[serve]==0.3.20'
# First load requires a separately authorized Hugging Face model download.
LAYA_HOST=127.0.0.1 LAYA_PORT=8001 LAYA_MODELS=english laya-serve
# After weights are cached, add HF_HUB_OFFLINE=1 to prevent Hub access.
curl --fail http://127.0.0.1:8001/health
```

Keep the server on loopback: upstream defaults to all interfaces. Package environment and model cache remain outside `pi/`; config deployment neither installs Laya nor starts it. After approved config deployment, `/reload` exposes the tool across projects. In RPC, loopback means the Pi host, not the browser's computer. This adapter does not support authenticated servers or configurable endpoints.

Example tool arguments:

```json
{"state":"Please refund my duplicate payment.","questions":{"intent":{"type":"choice","instructions":"What does the customer request?","criteria":{"refund":"return money","other":"another request"}}}}
```

`choice` uses 2–10 named, described options; `score` uses 2–10 distinct ordered descriptions; `noul` asks yes/no and optionally describes `true` and `false`. Question/option IDs contain 1–40 ASCII letters, digits, underscores, or hyphens. Limits: 1–8 questions, 4,000 state characters, 300 instruction characters, 200 characters per option description, 32 KiB request and 64 KiB response. These are transport bounds, not a token-fit guarantee: the English model's 512-token total context may truncate text, so use short, front-loaded inputs and short option descriptions.

The tool returns validated `answers`, retaining probabilities unchanged and omitting unrelated server metadata. It rejects malformed/inconsistent answers, refuses redirects, and stops waiting on cancellation or a 30-second deadline. Errors do not trigger retries, server startup, downloads, or cloud fallback. Cancellation does not guarantee server-side inference stops. Server offline mode is operator-controlled.

Probabilities are advisory, not permission, a security guarantee, or verified calibration. The current English checkpoint warns about clamping its `choice:11+` calibration; this tool limits choices to 10, but still requires task-specific evaluation. Tool inputs/results participate in normal Pi session/model context; local inference does not make the surrounding Pi conversation local-only.

## Excluded runtime state

Do not commit credentials, sessions, caches, trust state, onboarding state, API keys, metrics, or ordinary run artifacts. Common excluded paths include:

- `agent/auth.json`
- `agent/mcp.json` (private runtime config; only scoped Craft reconciliation)
- `agent/mcp-auth.json`
- `agent/mcp.log*`
- `agent/sessions/`
- `agent/pi-langfuse/`
- `agent/mcp-cache.json`
- `agent/mcp-onboarding.json`
- `agent/models-store.json`
- `agent/trust.json`

Deployment preserves these local `agent/settings.json` preferences when present:

- `lastChangelogVersion`, `defaultProvider`, `defaultModel`, `defaultThinkingLevel`, `enabledModels`, and `modelThinkingLevels` (including explicit empty collections).
- Known Archimedes namespaces: `archimedes.ui`, `.footer`, `.diff`, `.notify`, `.sessionName`, `.imagePaste`, `.todo`, `.ask`, `.subagent`, `.web`, `.sudo`, and `.meta` (including the existing onboarding completion marker; deployment never creates it).

Tracked Archimedes fields override conflicting local fields recursively, so disabled tools and configured limits remain enforced; other local fields in those namespaces survive. Missing preferences use tracked defaults. Package declarations, other settings, unknown namespaces, and retired migration namespaces remain repository-managed rather than blanket-merged.

Dry-run reports the effective settings change and preserved key names, never values. Malformed settings JSON or non-object Archimedes namespaces stop the update before package/config writes. Activation remains atomic. Generated rollback scripts use the same preservation rules, with the saved settings snapshot authoritative for conflicting Archimedes fields. Older rollback scripts retain their original behavior. This prevents future preference loss; it does not recover choices already overwritten by an earlier deployment.
