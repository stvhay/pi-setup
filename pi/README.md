# Pi Config

Deployable Pi configuration for this setup repository. The repository root [README](../README.md) is the documentation entry point; this file focuses on the contents and deployment behavior of `pi/`.

The tracked `pi/` tree is the source of truth. The default Pi runtime directory, `~/.pi`, is a deployed copy that may also contain ignored runtime state.

## Deploy or update the runtime copy

From the repository root:

```bash
scripts/bootstrap-pi-config.sh --dry-run
scripts/bootstrap-pi-config.sh --apply
```

The deploy helper preserves runtime secrets/state and installs helper commands into `~/.pi/agent/bin`, including:

```bash
agnt --help
```

Do not hand-edit deployed runtime copies. Make changes under tracked `pi/`, verify them, then deploy.

## Contents

- [`agent/AGENTS.md`](agent/AGENTS.md) — global Pi agent instructions
- `agent/settings.json` — shared Pi settings
- `agent/models.json` — custom model providers, including OpenRouter alternatives
- `agent/catalog.json` — model family catalog: maps each family to venues such as local Ollama, remote Olla-compatible endpoints, and OpenRouter; records cost classes, GPU-watt assumptions, opportunity-cost rates, and model-overlay keys
- `agent/actions/` — action templates that bind routing task, skills, role, allowed effects, and output contract
- [`agent/bin/`](agent/bin/) — helper commands used by skills and instructions; see the [agnt command reference](agent/bin/README.md)
- `agent/evals/` — deterministic routing, prompt, and instruction checks
- `agent/extensions/` — Pi extensions
- `agent/skills/` — Pi skills
- `agent/mcp.json` — MCP configuration, when used

For the conceptual overview, see [The agnt System](../docs/AGNT-SYSTEM.md). For the implementation map, see [Architecture](../docs/ARCHITECTURE.md).

Normal Pi sessions use direct inspect/edit/test tools. Code-changing work must have a Bead before editing. The runner and `agnt work` artifact workflow are preserved as explicit opt-in orchestration paths; deploying this config does not require or automatically start the runner.

## Provider credentials

Provider credentials belong in the shell environment or ignored local env files, not in git. For OpenRouter:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

With direnv, put that export in a private file such as `.envrc.local.d/openrouter.sh` in projects that need it, or in a shell profile for broader use.

Example smoke test after the key is set:

```bash
pi --print --provider openrouter-localish --model meta-llama/llama-3.1-8b-instruct "Reply with OK only."
```

## Optional service endpoints

Some helpers use environment-provided local or self-hosted services. Keep these values in a shell profile or ignored `.envrc.local.d/*.sh` files, not in git:

```bash
export SEARXNG_URL=https://your-searxng.example
export OLLA_HOST=https://your-olla-compatible-router.example
```

`SEARXNG_URL` enables `agnt web-search`. `OLLA_HOST` enables optional `olla-local`/`olla-cloud` providers; without it, the Olla extension uses localhost Ollama only.

## Excluded runtime state

Do not commit credentials, sessions, caches, trust state, onboarding state, API keys, metrics, or ordinary run artifacts. Common excluded paths include:

- `agent/auth.json`
- `agent/sessions/`
- `agent/mcp-cache.json`
- `agent/mcp-onboarding.json`
- `agent/trust.json`
