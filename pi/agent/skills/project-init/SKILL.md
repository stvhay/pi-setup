---
name: project-init
description: Scaffold a new project or audit an existing one for Pi-native development. Creates Beads work tracking, CONTRIBUTING, AGENTS.md, .pi/plans, worktree defaults, optional GitHub templates, and direnv/Nix environment files using .envrc/.envrc.d/flake.nix.
---

# Project Init

Initialize or audit project scaffolding for Pi-native development.

Announce:

- Fresh init: "I'm using the project-init skill to set up Pi project scaffolding."
- Audit/update: "I'm using the project-init skill to audit this project against Pi project standards."

At start, read shared conventions if needed:

```text
~/.pi/agent/skills/dev-workflow-common/SKILL.md
```

## Hard safety rules

- Do not overwrite existing files without explicit approval.
- Do not create or modify many files without approval. If the user's invocation explicitly says they approve creating the named standard scaffolding, that counts as approval; still summarize what was created afterward.
- Do not commit, push, create a PR, configure branch protection, initialize Beads, change Beads remotes/history, or install hooks unless explicitly approved.
- Prefer Beads for persistent agent-facing work tracking and Pi plans for implementation plans. Treat GitHub issues as optional external adapters/exports.

## Current standard scaffolding

Fresh init creates or proposes:

```text
CONTRIBUTING.md
AGENTS.md
.project-init
.beads/                 # via approved `bd init --skip-agents --skip-hooks`
.pi/plans/
.worktrees/
.gitignore entries for .worktrees/ and local env dirs
.envrc
.envrc.d/gh.sh
flake.nix
```

Optional, only if requested:

```text
.github/ISSUE_TEMPLATE/bug-report.yml
.github/ISSUE_TEMPLATE/feature-request.yml
.github/pull_request_template.md
.envrc.d/dolt.sh
scripts/install-hooks.sh
CHANGELOG.md
release/versioning scripts and workflows
```

Do not generate `CLAUDE.md`; Pi project instructions belong in `AGENTS.md`.

## Environment pattern

Use the `.envrc` / `.envrc.d` / `flake.nix` pattern from this repository's templates, adapted for the target project.

### `.envrc`

```bash
# Load Nix flake environment if available
if has nix; then
    use flake
fi

for init_dir in .envrc.d .envrc.local.d
do
    if [[ -d "$init_dir" ]]
    then
        for f in "$init_dir"/*
        do
            [[ -f "$f" ]] && source "$f"
        done
    fi
done
```

### `.envrc.d/gh.sh`

Install/update GitHub CLI to `~/.local/bin` if needed, then `PATH_add "$HOME/.local/bin"`. Use the helper implementation from the source pattern. Keep update checks daily with a stamp under `~/.local/share/gh/`.

### `flake.nix`

Create a minimal dev shell. Default tools:

- `git`
- `gh`
- `jq`
- `ripgrep`
- `direnv`

Add detected stack tools when obvious:

| Detected file | Add tools |
|---|---|
| `package.json` | `nodejs_22` |
| `pyproject.toml` or `requirements.txt` | `uv`, `python313`, `ruff` |
| `Cargo.toml` | `cargo`, `rustc`, `rustfmt`, `clippy` |
| `go.mod` | `go` |

## Mode detection

Run:

```bash
git rev-parse --show-toplevel 2>/dev/null || pwd
git status --short 2>/dev/null || true
find . -maxdepth 3 \( -name AGENTS.md -o -name CONTRIBUTING.md -o -name .project-init -o -name flake.nix -o -name .envrc -o -path './.github/pull_request_template.md' \) | sort
```

Modes:

| State | Mode | Behavior |
|---|---|---|
| `.project-init` exists | Update/audit | audit against current standard |
| some scaffolding exists | First adoption/audit | report missing/drift and propose fixes |
| little/no scaffolding | Fresh init | propose file list and ask before writing |

## Fresh init process

1. Inspect repo and infer project name/purpose/stack.
2. Present proposed files and defaults if approval has not already been given.
3. Ask for approval before writing unless the user explicitly approved the standard scaffolding in the current prompt.
4. Write only missing files unless user approves replacing/updating existing files. Create required directories explicitly, including `.pi/plans/` and `.worktrees/`. Initialize Beads only when explicitly approved, using `bd init --skip-agents --skip-hooks` unless the user requested generated agent files or hooks.
5. Verify with `find`, `test -f`, `test -d .worktrees`, `bd status` when Beads is initialized, and `git status --short`.
6. Present summary and suggested next commands.

If approval is still needed, the approval prompt should include:

```markdown
## Project Init Proposal

Project: <name>
Mode: fresh init
Detected stack: <stack or none>

### Will create
- <path> — <purpose>

### Will update
- <path> — <exact append/change>

### Will not do without later approval
- commit
- push
- branch protection
- hook installation
- release automation

Approve scaffolding? yes/no/changes
```

## Audit/update process

1. Read `references/audit-checklist.md` if useful, but adapt it for Pi:
   - `AGENTS.md`, not `CLAUDE.md`
   - `.pi/plans`, not `.claude/plans`
   - `.envrc/.envrc.d/flake.nix` included
2. Check each current-standard artifact.
3. Report `OK`, `MISSING`, `DRIFT`, or `SKIP`.
4. Propose a remediation plan.
5. Ask approval before edits.

Audit output:

```markdown
## Project Init Audit

**Mode:** fresh/adoption/update
**Verdict:** PASS | NEEDS_SCAFFOLDING | DRIFT | NOT_SURE

### Results
- `path` — OK/MISSING/DRIFT — reason

### Proposed remediation
1. <change>

Apply? all / numbers / none
```

## File templates

Templates in `templates/` may be used and adapted:

- `bug-report.yml`
- `feature-request.yml`
- `pull_request_template.md`
- `CONTRIBUTING.md`

Adapt `CONTRIBUTING.md` for Pi skills. Keep it positive: describe the Pi workflow to use, not legacy tools to avoid.

- `/skill:brainstorming`
- `/skill:writing-plans`
- `/skill:verification-before-completion`
- `/skill:requesting-code-review`
- `/skill:documentation-standards`
- `/skill:finishing-a-development-branch`

## AGENTS.md skeleton

If creating `AGENTS.md`, include concise project-specific sections:

```markdown
# Project Instructions

## Workflow

- Use Pi skills for design, planning, verification, review, docs, and branch finishing.
- Keep implementation plans under `.pi/plans/`.
- Use Beads (`bd`/`beads`) for persistent agent-facing work tracking.
- Treat GitHub issues as optional external adapters/exports, not a second source of truth.
- Do not push, merge, delete branches, remove worktrees, delete beads, change Beads remotes/history, or install hooks without explicit approval.

## Verification

Document project test/lint/typecheck commands here.

## Environment

This project uses direnv + Nix:

```bash
direnv allow
```

The `.envrc` loads `flake.nix` and shell snippets from `.envrc.d/` and `.envrc.local.d/`.

## Documentation

Keep README and relevant docs/SPEC.md files aligned with user-visible and architectural changes.
```
```

## .project-init marker

Create:

```json
{
  "tool": "pi",
  "skill": "project-init",
  "version": "pi-1",
  "initialized_at": "<ISO-8601 UTC timestamp>",
  "environment_pattern": ".envrc+.envrc.d+flake.nix",
  "work_tracking": "beads"
}
```

## Gitignore entries

Ensure `.gitignore` contains:

```gitignore
.worktrees/
.envrc.local.d/
.direnv/
```

Do not ignore `.envrc`, `.envrc.d/`, or `flake.nix`; they are committed project environment files.

## Release infrastructure

Release automation is optional. Do not generate release scripts/workflows by default. If the user asks, use a separate explicit plan and approval gate.

## Branch protection

Branch protection and squash-only settings require GitHub admin permissions. Never run `gh api` branch-protection changes unless the user explicitly asks.

## Verification after scaffolding

Run:

```bash
find . -maxdepth 3 \( -name AGENTS.md -o -name CONTRIBUTING.md -o -name .project-init -o -name flake.nix -o -name .envrc -o -path './.envrc.d/*' -o -path './.github/*' \) | sort
test -d .worktrees
git status --short
```

If Nix/direnv is available and user permits, optionally run:

```bash
nix flake check --no-build 2>/dev/null || nix flake metadata
direnv allow
```
