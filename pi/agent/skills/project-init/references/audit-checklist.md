# Project Init Audit Checklist

Pi-native checklist for project-init audits.

## Scaffolding

### SCAFF-1: Bug report template
- **Check:** `.github/ISSUE_TEMPLATE/bug-report.yml` exists
- **Severity:** MISSING

### SCAFF-2: Feature request template
- **Check:** `.github/ISSUE_TEMPLATE/feature-request.yml` exists
- **Severity:** MISSING

### SCAFF-3: PR template
- **Check:** `.github/pull_request_template.md` exists and includes Summary, Test Plan/Checklist, docs/review reminders
- **Severity:** MISSING/DRIFT

### SCAFF-4: CONTRIBUTING.md
- **Check:** `CONTRIBUTING.md` exists and references Pi skills plus a Test Commands section
- **Severity:** MISSING/DRIFT

### SCAFF-5: AGENTS.md
- **Check:** `AGENTS.md` exists with Workflow, Verification, Environment, and Documentation sections
- **Severity:** MISSING/DRIFT

### SCAFF-6: Plans directory
- **Check:** `.pi/plans/` exists
- **Severity:** MISSING

### SCAFF-7: Worktree directory
- **Check:** `.worktrees/` exists and `.gitignore` ignores `.worktrees/`
- **Severity:** MISSING/DRIFT

### SCAFF-8: Project marker
- **Check:** `.project-init` exists and records `tool: pi` and `skill: project-init`
- **Severity:** MISSING/DRIFT

## Environment

### ENV-1: direnv loader
- **Check:** `.envrc` exists and loads `use flake` plus `.envrc.d` and `.envrc.local.d` snippets
- **Severity:** MISSING/DRIFT

### ENV-2: Nix flake
- **Check:** `flake.nix` exists with a default dev shell
- **Severity:** MISSING

### ENV-3: GitHub CLI
- **Check:** `flake.nix` includes `gh` when GitHub CLI workflows are used
- **Severity:** MISSING

### ENV-4: Local env ignored
- **Check:** `.gitignore` ignores `.envrc.local.d/` and `.direnv/`, but does not ignore `.envrc`, `.envrc.d/`, or `flake.nix`
- **Severity:** DRIFT

## Release infrastructure (optional)

Only audit if the project has opted into generated release automation.

### REL-1: CHANGELOG.md convention
- **Check:** `CHANGELOG.md` exists and documents bump conventions
- **Severity:** MISSING if release automation adopted, otherwise SKIP

### REL-2: CI/release workflows
- **Check:** workflows match the project release plan
- **Severity:** DRIFT if release automation adopted, otherwise SKIP

## Branch/PR safety

### SAFE-1: Bounded reversible local Git authority
- **Check:** project docs permit exact initially approved local branch/worktree creation and verified post-integration cleanup, but stop on ambiguous ownership, unrelated or untracked data, missing recovery proof, remote deletion, force, or history rewrite; push, merge, and branch protection remain separately gated
- **Severity:** DRIFT

### SAFE-2: Verification commands documented
- **Check:** README, CONTRIBUTING, or AGENTS documents test/lint/typecheck commands
- **Severity:** DRIFT
