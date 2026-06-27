# Pi Config

Deployable Pi configuration. In this setup repository, `pi/` is the tracked source of truth and live `~/.pi` is a deployed runtime copy.

## Install/update live `~/.pi`

From the repository root:

```bash
scripts/bootstrap-pi-config.sh --dry-run
scripts/bootstrap-pi-config.sh --apply
```

The deploy helper preserves runtime secrets/local state and installs helper commands into `~/.pi/agent/bin`, including:

```bash
agnt --help
```

## Contents

- `agent/AGENTS.md` — global Pi agent instructions
- `agent/settings.json` — shared Pi settings
- `agent/models.json` — custom model providers, including OpenRouter local-model alternatives
- `agent/catalog.json` — model family catalog: maps each model family to its venues (local Ollama, remote GPU, OpenRouter), cost classes, GPU-watt assumptions, and opportunity-cost rates; keys the `AGENTS.d/models/<family>.md` prompt overlays
- `agent/bin/` — helper commands used by skills and instructions
- `agent/extensions/` — Pi extensions
- `agent/skills/` — Pi skills
- `agent/mcp.json` — MCP configuration, when used

## OpenRouter

OpenRouter models are configured under the `openrouter-localish` provider. Put the API key in your shell environment; do not commit it:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

With direnv, put that export in a private file such as `.envrc.local.d/openrouter.sh` in projects that need it, or in your shell profile for global use.

Example smoke test after the key is set:

```bash
pi --print --provider openrouter-localish --model meta-llama/llama-3.1-8b-instruct "Reply with OK only."
```

## Optional local service endpoints

Some helpers use environment-provided local or self-hosted services. Keep these
values in your shell profile or ignored `.envrc.local.d/*.sh` files, not in git:

```bash
export SEARXNG_URL=https://your-searxng.example
export OLLA_HOST=https://your-olla-compatible-router.example
```

`SEARXNG_URL` enables `agnt web-search`. `OLLA_HOST` enables optional remote
`olla-local`/`olla-cloud` providers; without it, the Olla extension only tries
localhost Ollama.

## Excluded local state

Do not commit credentials, sessions, caches, trust state, onboarding state, or API keys:

- `agent/auth.json`
- `agent/sessions/`
- `agent/mcp-cache.json`
- `agent/mcp-onboarding.json`
- `agent/trust.json`
