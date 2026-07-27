# Pi Config

Deployable Pi configuration for this setup repository. The repository root [README](../README.md) is the documentation entry point; this file focuses on the contents and deployment behavior of `pi/`.

The tracked `pi/` tree is the source of truth. The default Pi runtime directory, `~/.pi`, is a deployed copy that may also contain ignored runtime state.

## Deploy or update the runtime copy

From the repository root:

```bash
scripts/update-pi-config.sh --dry-run # preview changes
scripts/update-pi-config.sh           # update ~/.pi
```

The update helper preserves runtime secrets/state and installs helper commands into `~/.pi/agent/bin`, including:

```bash
agnt --help
```

Pi installs packages declared in `agent/settings.json` into the preserved `~/.pi/agent/npm/` user package root when they are missing. This includes the pinned `@mariozechner/clipboard` native addon required by the Archimedes image-paste extension.

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

`agent/extensions/subagent-error-workaround.ts` compensates for Archimedes 1.8.2 error signaling and rendering defects: failed child exits are marked as errors, and validation failures show their original message instead of `no results`.

Do not hand-edit deployed runtime copies. Make changes under tracked `pi/`, verify them, then deploy.

## Contents

- [`agent/AGENTS.md`](agent/AGENTS.md) — global Pi agent instructions
- `agent/AGENTS.d/roles/` — delegated-worker stances and output contracts
- `agent/AGENTS.d/models/` — family-wide and venue-specific instruction overlays
- `agent/settings.json` — shared Pi settings, package declarations, and runtime defaults
- `agent/models.json` — custom model providers, including OpenRouter alternatives
- `agent/catalog.json` — model family catalog: maps each family to venues such as local Ollama, remote Olla-compatible endpoints, and OpenRouter; records cost classes, GPU-watt assumptions, opportunity-cost rates, and model-overlay keys
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

Provider credentials belong in the shell environment or ignored local env files, not in git. OpenRouter credentials live on Knuth behind LiteLLM; Pi needs only `OLLA_HOST` to reach Olla.

The Langfuse extension and official Langfuse skill share credentials from private `~/.pi/agent/pi-langfuse/config.json`. During Pi sessions, `langfuse-config-env.ts` exposes that config to Langfuse CLI child processes; explicit `LANGFUSE_*` environment variables still take precedence. No second credential file is needed. Tracked evaluator desired state lives in `agent/langfuse/evaluators.json`; `agnt langfuse check` reports drift and `agnt langfuse apply` creates or updates managed evaluators and rules without deleting unmanaged resources. The owned subagent extension emits explicit `interactive-result` and `subagent-result` observations with captured task/output; outcome evaluation samples 10% of interactive results and subagent quality evaluates 100% of delegated results. Config deployment runs apply when credentials exist. Interactive Pi startup checks asynchronously, stays silent when current, and warns when drift exists. The same extension records `openai-codex` usage at zero marginal cost while preserving catalog model IDs so sessions resume correctly.

Example cloud smoke test:

```bash
pi --print --provider olla-cloud --model gemma-4-31b-it "Reply with OK only."
```

## Optional service endpoints

Some helpers use environment-provided local or self-hosted services. Keep these values in a shell profile or ignored `.envrc.local.d/*.sh` files, not in git:

```bash
export SEARXNG_URL=https://your-searxng.example
export OLLA_HOST=https://your-olla-compatible-router.example
```

`SEARXNG_URL` enables `agnt web-search`. `OLLA_HOST` enables `olla-local` for Knuth Ollama and `olla-cloud` for Knuth LiteLLM. Laptop Ollama is optional machine state supplied by ignored `~/.pi/agent/extensions/ollama.local.ts`.

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
