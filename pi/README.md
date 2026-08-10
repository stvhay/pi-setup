# Pi Config

Deployable Pi configuration for this setup repository. The repository root [README](../README.md) is the documentation entry point; this file focuses on the contents and deployment behavior of `pi/`.

The tracked `pi/` tree is the source of truth. The default Pi runtime directory, `~/.pi`, is a deployed copy that may also contain ignored runtime state.

## Deploy or update the runtime copy

From the repository root:

```bash
scripts/update-pi-config.sh --dry-run    # preview changes
scripts/update-pi-config.sh              # update ~/.pi
scripts/apply-pi-package-patches.sh      # after Pi installs pinned packages
```

The update helper preserves runtime secrets/state and installs helper commands into `~/.pi/agent/bin`, including:

```bash
agnt --help
```

Pi installs packages declared in `agent/settings.json` into the preserved `~/.pi/agent/npm/` user package root when they are missing. This includes exact pins for `pi-langfuse@1.5.10`, `pi-archimedes@2.0.1`, and the `@mariozechner/clipboard` native addon. Langfuse 1.5.10 natively includes logical session correlation and score entity IDs. Until upstream releases also include byte-bounded ingestion and media-safe payload bounds, run `scripts/apply-pi-package-patches.sh --check` and then the apply command after package installation. The helper is idempotent and rejects version/source mismatches; tracked patches live under `patches/pi-packages/`.

### Observational memory

`pi-observational-memory@3.0.3` matches upstream commit [`27a5195eaf90e4e2ca1302e3a31d4bb14df982a5`](https://github.com/elpapi42/pi-observational-memory/commit/27a5195eaf90e4e2ca1302e3a31d4bb14df982a5) and its [exact README](https://raw.githubusercontent.com/elpapi42/pi-observational-memory/27a5195eaf90e4e2ca1302e3a31d4bb14df982a5/README.md). Subscription-backed Codex GPT-5.6 models use their 272,000-token operational context. Compaction uses ratio mode: `floor(model.contextWindow × 0.75)`, so 272,000 × 0.75 = 204,000 tokens. Models without a usable context window fall back to the explicit 81,000-token calibrated threshold.

Pi's native auto-compaction threshold is `contextWindow - reserveTokens`, or 255,616 tokens with Pi's default 16,384-token reserve. Native Pi and observational memory use different token counters, but the 51,616-token configured gap keeps routine threshold crossings separate. A narrow asynchronous race can still occur around a new prompt; observational memory rechecks after deferral and rejects duplicate compaction hooks. Native and manual compactions still use the prepared observational-memory summary.

Background observer, reflector, and dropper workers use `openai-codex/gpt-5.6-sol` with `low` thinking. The package exposes one shared worker model, so this cannot target reflection alone. Compaction itself does not call a model; it renders prepared memory state.

### Archimedes subagents

Omit `agent` for a generic subagent call:

```json
{"task": "Review the current diff"}
```

Supplying `agent` selects a named definition; it is not a task label or an alias for generic mode. Create named definitions with `/agents` before using them. Current discovery paths are:

- project: `<git-root>/.pi/agents/*.md`
- user: `~/.pi/agent/agents/*.md`
- optional global/legacy: nearest `<git-root>/.agents/agents/*.md`, then `~/.agents/agents/*.md`

The current Archimedes package documentation incorrectly says generic calls default to a named `general` agent and places user definitions under `~/.pi/agents/`. In practice, explicit `"agent": "general"` requires a definition named `general`; only omission selects generic mode.

`agent/extensions/subagent-error-workaround.ts` normalizes Archimedes results for local telemetry: failed child exits are marked as errors, validation failures retain their original message, and each available `childSessionId` is copied into the parent projection, metric, and private result artifact as the exact child-trace foreign key. Parent projections also declare the resolved effective mode and whether child telemetry is expected; isolated one-shot children are expected unavailable unless an already-discovered completed root proves otherwise.

The v2.0.1 runtime projection preserves native child-session/model behavior and adds per-child request, tool, token, cost, duration, and fanout controls; bounded Pi 0.84 stream reconstruction; adaptive turn-token progress; bounded parallel outputs; and privacy-bounded repeated-error termination. One-shot mode permits one provider request, disables tools and ambient project resources, keeps explicit prompt-template macros available, and has no implicit wall deadline. `maxOutputTokens` is applied best-effort through supported provider payloads and reports `applied` or `unsupported` evidence without dropping output or usage. Pi's current Codex Responses payload exposes no provider output-cap field, so Codex runs unchanged with truthful `unsupported` evidence.

The tracked Archimedes wrapper reads `agent/catalog.json` rather than inferring billing from provider names. Metered one-shot children receive a 16,384-token default provider output cap; subscription-backed and agentic children receive no automatic token or cost cap. An explicit tighter call cap wins. Set `PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS` to a positive integer, `0`, or `off` to tighten or disable the local default.

Do not hand-edit deployed runtime copies. Make changes under tracked `pi/`, verify them, then deploy.

## Contents

- [`agent/AGENTS.md`](agent/AGENTS.md) — global Pi agent instructions
- `agent/AGENTS.d/roles/` — delegated-worker stances and output contracts
- `agent/AGENTS.d/models/` — family-wide and venue-specific instruction overlays
- `agent/settings.json` — shared Pi settings, package declarations, and runtime defaults
- `agent/catalog.json` — model family catalog: maps each family to configured direct OpenRouter/Codex targets and records cost classes, billing classes, context, rates, and model-overlay keys
- `agent/tasks/` — operational routing labels and preferred, qualified, or avoided model targets
- `agent/actions/` — action templates that bind routing task, skills, role, allowed effects, and output contract
- [`agent/bin/`](agent/bin/) — helper commands used by skills and instructions; see the [agnt command reference](agent/bin/README.md)
- `agent/evals/` — deterministic routing, prompt, and instruction checks
- `agent/extensions/` — Pi extensions
- `agent/skills/` — Pi skills
- `agent/mcp.json` — MCP configuration, when used

For the conceptual overview, see [The agnt System](../docs/AGNT-SYSTEM.md). For the implementation map, see [Architecture](../docs/ARCHITECTURE.md).

Normal Pi sessions use direct inspect/edit/test tools. Code-changing work must have a Bead before editing. The runner and `agnt work` artifact workflow are preserved as explicit opt-in orchestration paths; deploying this config does not require or automatically start the runner.

## Provider credentials

Provider credentials belong in Pi's ignored `auth.json`, the shell environment, or ignored local env files—not in git. Pi has a built-in OpenRouter provider: run `/login openrouter` or set `OPENROUTER_API_KEY`. `models.json` uses only per-model output-cap overrides; it does not duplicate the provider, endpoint, or credential. OpenAI/Codex remains the default root provider; direct OpenRouter is reserved for fresh bounded delegated calls under the approved [model portfolio](../docs/MODEL-PORTFOLIO-2026-08.md). No local or relay provider is configured.

The Langfuse extension and official Langfuse skill share credentials from private `~/.pi/agent/pi-langfuse/config.json`. During Pi sessions, `langfuse-config-env.ts` exposes that config to Langfuse CLI child processes; explicit `LANGFUSE_*` credentials still take precedence. No second credential file is needed.

Before registering `pi-langfuse@1.5.10`, the public wrapper sets the `conversations` preset and unconditionally disables tool I/O, system prompts, and cwd. Explicit `LANGFUSE_CAPTURE_INPUTS=false` and `LANGFUSE_CAPTURE_OUTPUTS=false` remain disabled. The wrapper adds no package-event proxy sanitizer: `pi-langfuse` owns redaction and payload shaping. When `PI_LANGFUSE_MAX_STRING_LENGTH` is unset, the package's finite 12,000-character ordinary-string default applies. Valid Langfuse-extractable media may bypass that cap only in capture-enabled generation input on the transient OTel path; malformed media and other surfaces use bounded markers, and REST fallback never retains raw media. Explicit operator overrides, including `PI_LANGFUSE_MAX_STRING_LENGTH=off`, remain supported; disabling the cap carries memory, network, ingestion, storage, disclosure, and denial-of-service (DoS) risks.

Tracked evaluator desired state lives in `agent/langfuse/evaluators.json`; `agnt langfuse check` reports drift and `agnt langfuse apply` creates or updates managed evaluators and rules without deleting unmanaged resources. The owned subagent extension emits explicit `interactive-result` and `subagent-result` observations with captured task/output; outcome evaluation samples 10% of interactive results and subagent quality evaluates 100% of delegated results. Parent-owned full delegated results live under `agnt runtime-path delegated-results`; tool results and telemetry expose bounded opaque refs, not absolute private paths. Parent projections, metrics, and artifacts retain the child's logical Pi session UUID as `childSessionId`, enabling exact Langfuse session lookup without timestamp/model matching. Parent projection metadata adds validated effective mode and declared child-trace expectation; improvement scans resolve count-only actual states from the existing bounded trace discovery without extra Langfuse calls or raw child IDs in safe summaries. Config deployment runs apply when credentials exist. Interactive Pi startup checks asynchronously, stays silent when current, and warns when drift exists. `langfuse-config-env.ts` composes the installed public entrypoint: subscription generations use the zero-priced `*-subscription` alias only while upstream telemetry handles `message_end`, then restore the catalog model ID before session persistence. Private improvement scans leave raw Langfuse records unchanged and normalize known unavailable tool payload-byte metadata downstream without copying tool payloads. Non-null payload-byte values are bounded-preview estimates, not raw payload sizes.

Example direct OpenRouter smoke test after authentication:

```bash
pi --print --provider openrouter --model minimax/minimax-m3 \
  --thinking medium "Reply with OK only."
```

## Optional service endpoints

Some helpers use environment-provided local or self-hosted services. Keep these values in a shell profile or ignored `.envrc.local.d/*.sh` files, not in git:

```bash
export SEARXNG_URL=https://your-searxng.example
```

`SEARXNG_URL` enables `agnt web-search`. No local or relay model provider is configured; restore prior provider code from Git history only after explicit approval.

## Excluded runtime state

Do not commit credentials, sessions, caches, trust state, onboarding state, API keys, metrics, or ordinary run artifacts. Common excluded paths include:

- `agent/auth.json`
- `agent/sessions/`
- `agent/pi-langfuse/`
- `agent/mcp-cache.json`
- `agent/mcp-onboarding.json`
- `agent/models-store.json`
- `agent/trust.json`

Deployment preserves Pi's runtime-managed `lastChangelogVersion` marker while replacing the remaining settings from tracked `agent/settings.json`.
