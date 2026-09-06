# Contributing

## Workflow

Every meaningful change follows this process:

1. Use Beads (`bd`/`beads`) for persistent work tracking. Every code-changing task must have a Bead before edits begin. Start with `bd ready`, inspect work with `bd show <id>`, and claim active work with `bd update <id> --claim`.
2. Use `/skill:brainstorming` for non-trivial design choices.
3. Use `/skill:writing-plans` to create an implementation plan under `.pi/plans/`.
4. Implement directly in the current Pi session by default, in small reviewable steps. Select run-artifact orchestration explicitly only when it adds value.
5. Use `/skill:verification-before-completion` before claiming done.
6. Use `/skill:documentation-standards` to validate docs when behavior, APIs, architecture, or workflows change.
7. Use `/skill:requesting-code-review` for non-trivial diffs.
8. Use `/skill:finishing-a-development-branch` for branch/project readiness before PR/merge or local completion.

GitHub issues may be used later through an adapter/export workflow, but Beads is the canonical agent-facing work graph.

## Vendor submodule publication

When advancing a `forks/*` gitlink:

1. Publish the vendor commit to the remote branch configured in `.gitmodules`.
2. Stage the superproject gitlink (and `.gitmodules` when changed).
3. Run `scripts/check-vendor-pins.sh` (network: fetches each configured vendor branch).
4. Commit the superproject change only after the preflight passes.

CI runs the same check before submodule initialization and fails closed when a pin is inaccessible. Do not bypass the preflight or weaken vendor-content tests.

## Test Commands

Install the locked Pi runtime used by Node-backed extension tests:

```bash
npm ci --ignore-scripts
```

Then run:

```bash
# layout and shell checks
scripts/check-pi-config.sh
bash -n scripts/*.sh

# deterministic Python checks for agnt/agent-instructions internals
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15

# deterministic agnt evals (no model calls)
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
pi/agent/bin/agnt eval run quality-process-smoke
```

During repair, run the relevant test file or node ID, not the full suite after every edit. Run the full matrix once on the stable candidate. A deployment-only request for an unchanged verified source uses the deployment script's checks instead of repeating the development suite. Use `--durations=15` to identify slow checks; do not increase timeouts or add parallel workers before checking isolation and the slowest cases. Recent isolated full runs take about two minutes locally; allow at least 300 seconds at the command runner to avoid discarding useful results.

Deployment tests strip inherited Langfuse credentials and Pi config/target overrides before child execution. Synthetic cases use a minimal config tree and fake package commands; one real-source integration retains full layout coverage. Keep this boundary intact: deterministic tests must not reach live services or the deployed `~/.pi`. Real process-termination and Beads-bootstrap tests remain part of the suite.

Manual behavioral canary (runs real models; not a routine completion gate): run
`scripts/eval-workflow-compliance.sh --skill-mode candidate` only when user
requests it or the agent recommends it for a specific behavior question that
routine telemetry cannot answer.

## Environment

This project uses direnv + Nix. After cloning:

```bash
direnv allow
npm ci --ignore-scripts
```

The committed `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/`.
Local-only snippets can go in `.envrc.local.d/`, which is gitignored.

## Code of Conduct

Be kind, be constructive, and assume good intent.
