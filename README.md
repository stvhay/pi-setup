# Pi Setup

This repository manages a reusable Pi configuration. The tracked `pi/` directory is the source of truth; live `~/.pi` is a deployed runtime copy.

## Repository layout

```text
pi-setup/
├── pi/          # deployable Pi config source
├── docs/        # architecture, self-improvement loop, migration notes
├── scripts/     # checks and deployment helpers
├── tests/       # pytest for agnt/agent-instructions internals
├── .beads/      # tracked Beads work graph export/config; local DB ignored
└── .pi/         # project-local plans/reviews/runs/scratch, not deployable config
```

See `docs/ARCHITECTURE.md` for the layer map (catalog → tasks → route →
invoke → metrics), `docs/SELF-IMPROVEMENT.md` for how routing and per-model
prompts learn from observed outcomes, and
`docs/SELF-IMPROVEMENT-PRINCIPLES.md` for occasional design guidance when
refactoring agent workflows or context architecture.

## Initialize this setup repository

```bash
scripts/check-pi-config.sh
bd bootstrap --dry-run --json
```

## Work tracking with Beads

Beads is the canonical agent-facing work graph for this repository:

```bash
bd prime      # dynamic workflow context
bd status     # work graph summary
bd ready      # unblocked work
bd show <id>  # inspect a bead
```

Tracked Beads files live under `.beads/`; local database/runtime files are
ignored by `.beads/.gitignore`. GitHub issues are not mirrored now; see
`docs/GITHUB-ADAPTER.md` for the adapter decision.

Nontrivial runs can write inspectable invocation/result artifacts under
`.pi/runs/` with `agnt runs` or `agnt action render`; see
`docs/RUN-ARTIFACTS.md`.

## Deploy the config to `~/.pi`

Preview changes first:

```bash
scripts/bootstrap-pi-config.sh --dry-run
```

Apply when the preview looks right:

```bash
scripts/bootstrap-pi-config.sh --apply
```

The deploy helper treats this repository as the source of truth and preserves runtime secrets/local state such as `agent/auth.json`, `agent/trust.json`, sessions, caches, and local environment files. If an old live `~/.pi/.git` checkout exists, the helper moves its git metadata aside instead of deleting it so `~/.pi` no longer looks like an independently updated config repo.

After deployment, `~/.pi/agent/bin` should be on your shell `PATH`, making helpers available as:

```bash
agnt --help
```

## Graphify knowledge graphs

This config includes the Graphify Pi skill under `pi/agent/skills/graphify/`.
Use `/graphify .` in Pi, or run the CLI through the helper surface:

```bash
agnt graphify --help
agnt graphify extract . --no-cluster
agnt graphify query "How is routing implemented?"
```

`agnt graphify` uses an installed `graphify` binary when present and otherwise
falls back to `uv tool run --from graphifyy graphify`. It does not install
project hooks implicitly. Manage hooks explicitly with
`agnt graphify hooks install|status|uninstall`; install/uninstall requires
approval in agent workflows because hooks change repository behavior.

## OpenRouter API key

The config includes curated OpenRouter model entries under `openrouter-localish`. Put the key in your shell environment; do not commit it:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

With direnv, use a private ignored file such as `.envrc.local.d/openrouter.sh`.

## Verification

Fast local checks:

```bash
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m pytest tests/
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agent-instructions --check
pi/agent/bin/agnt action validate
pi/agent/bin/agnt context-health --strict
pi/agent/bin/agnt prompt inventory >/tmp/agnt-prompt-inventory.json
python -m json.tool /tmp/agnt-prompt-inventory.json >/dev/null
git diff --check
```

Workflow eval smoke suite, the default:

```bash
./scripts/eval-workflow-compliance.sh
# equivalent to:
./scripts/eval-workflow-compliance.sh --smoke
```

Run selected cases or the full suite:

```bash
./scripts/eval-workflow-compliance.sh --list
./scripts/eval-workflow-compliance.sh --case writing_plans_creates_plan
./scripts/eval-workflow-compliance.sh --full
./scripts/eval-workflow-compliance.sh --full --parallel 3
```

## Private/generated state

The config repository must not track runtime secrets, sessions, caches, or onboarding state:

- `agent/auth.json`
- `agent/sessions/`
- `agent/mcp-cache.json`
- `agent/mcp-onboarding.json`
- `agent/trust.json`
