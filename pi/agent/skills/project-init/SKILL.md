---
name: project-init
description: Use when scaffolding a new project or auditing one for Pi-native workflow, Beads, plans, and direnv/Nix setup.
---

# Project Init

Initialize or audit Pi-native project scaffolding.

Announce one:

- Fresh: "I'm using the project-init skill to set up Pi project scaffolding."
- Existing: "I'm using the project-init skill to audit this project against Pi project standards."

Read shared conventions when needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Hard safety rules

- Inspect before deciding fresh-init versus audit mode.
- Do not overwrite existing files or apply audit fixes without explicit approval.
- Do not commit, push, create PRs, change branch protection, initialize Beads, change Beads remotes/history, or install hooks without explicit approval.
- Treat GitHub issues as optional adapters; Beads is canonical agent-facing work state.
- Add only needed scaffolding. Release automation and GitHub templates remain opt-in.

An invocation that explicitly approves named standard scaffolding counts as approval to create those files, not to replace existing files or perform restricted actions.

## Standard scaffolding

Required or normally proposed:

```text
AGENTS.md
CONTRIBUTING.md
.project-init
.beads/                 # only through approved bd init --skip-agents --skip-hooks
.pi/plans/
.worktrees/
.envrc
.envrc.d/gh.sh
flake.nix
.gitignore entries for .worktrees/, .envrc.local.d/, and .direnv/
```

Optional only when requested:

```text
.github/ISSUE_TEMPLATE/*
.github/pull_request_template.md
.envrc.d/dolt.sh
scripts/install-hooks.sh
CHANGELOG.md
release/versioning automation
```

Do not generate `CLAUDE.md`; Pi project instructions belong in `AGENTS.md`.

## Detect mode

```bash
git rev-parse --show-toplevel 2>/dev/null || pwd
git status --short 2>/dev/null || true
find . -maxdepth 3 \( -name AGENTS.md -o -name CONTRIBUTING.md -o -name .project-init -o -name flake.nix -o -name .envrc -o -path './.github/pull_request_template.md' \) | sort
```

| State | Mode | Action |
|---|---|---|
| `.project-init` exists | update/audit | report current drift |
| partial scaffolding exists | adoption/audit | preserve files; propose gaps |
| little exists | fresh init | propose file list and defaults |

## Fresh init

1. Infer project purpose and stack from repository files.
2. List files to create, exact files to update, and restricted actions excluded.
3. Ask approval unless current prompt already approved that exact scope.
4. Create only missing files. Initialize Beads only when separately approved.
5. Verify created paths and report next commands.

Use repository templates instead of duplicating them:

- `templates/AGENTS.md`
- `templates/CONTRIBUTING.md`
- `templates/envrc`
- `templates/flake.nix`
- `templates/gh.sh`
- optional GitHub templates under `templates/`

Adapt stack tools only when detection is obvious:

| Detected file | Nix tools |
|---|---|
| `package.json` | `nodejs_22` |
| `pyproject.toml` or `requirements.txt` | `uv`, `python313`, `ruff` |
| `Cargo.toml` | `cargo`, `rustc`, `rustfmt`, `clippy` |
| `go.mod` | `go` |

Keep `.envrc`, `.envrc.d/`, `flake.nix`, and `flake.lock` tracked. Ignore `.worktrees/`, `.envrc.local.d/`, and `.direnv/`.

## Audit/update

Read `references/audit-checklist.md` when useful, adapting legacy names to Pi conventions.

For every standard artifact, report `OK`, `MISSING`, `DRIFT`, or `SKIP`, then propose minimum remediation. Ask approval before edits.

```markdown
## Project Init Audit

**Mode:** fresh/adoption/update
**Verdict:** PASS | NEEDS_SCAFFOLDING | DRIFT | NOT_SURE

### Results
- `<path>` — OK/MISSING/DRIFT/SKIP — <reason>

### Proposed remediation
1. <change>

Apply? all / numbers / none
```

Preserve existing project choices unless they violate an explicit requirement. Do not replace a working custom setup merely because it differs from templates.

## Marker

For fresh initialization, create `.project-init` with tool `pi`, skill `project-init`, version `pi-1`, UTC initialization time, environment pattern `.envrc+.envrc.d+flake.nix`, and work tracking `beads`.

## Verification

```bash
find . -maxdepth 3 \( -name AGENTS.md -o -name CONTRIBUTING.md -o -name .project-init -o -name flake.nix -o -name .envrc -o -path './.envrc.d/*' -o -path './.github/*' \) | sort
test -d .worktrees
git status --short
```

When available and permitted, optionally run:

```bash
nix flake check --no-build 2>/dev/null || nix flake metadata
```

Report created/updated paths, skipped optional work, verification evidence, and remaining drift.
