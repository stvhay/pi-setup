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
- **Check:** `.project-init` exists and records `tool: pi`, `skill: project-init`, and `work_tracking: beads`
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
- **Check:** project docs permit exact initially approved local branch/worktree creation, one guarded local integration bound to target checkout/branch plus expected target HEAD/source SHA, and verified post-integration cleanup; they stop on ambiguity, unrelated or untracked data, conflict/divergence, missing recovery proof, remote deletion, force, or history rewrite; push, alternate merge strategies, and branch protection remain separately gated
- **Severity:** DRIFT

### SAFE-2: Verification commands documented
- **Check:** README, CONTRIBUTING, or AGENTS documents test/lint/typecheck commands
- **Severity:** DRIFT

## Beads/Pi lifecycle profile

### BEADS-1: Tested compatibility
- **Check:** `bd version --json` matches the project's CI pin and documented profile (this Pi integration tests 1.3.1); `bd comments --help` and `bd provenance --help` succeed. Pi is a custom integration, not a generic `bd setup` recipe. Report drift; do not install binaries, migrate databases, or enable hooks/remotes automatically.
- **Severity:** DRIFT

### BEADS-2: Session lifecycle and Git authority
- **Check:** quickrefs use `bd prime`, `bd ready`, `agnt work direct-start <id> --claim`, then, for successful completion, verified task-owned commit and `agnt work direct-closeout <id> --outcome success --reason ...`. Unfinished work uses checkpoint/resume through `handoff_bead` without success or closure; scoped switches and exact-reservation recovery follow shared `AGENTS.md`. Unassigned ready-work handoff and verified successful-closeout handoff remain distinct. Raw claim/close are lower-level transitions. Beads stealth/no-git-ops text does not override project Git authority.
- **Severity:** DRIFT

### BEADS-3: Portable-state boundary
- **Check:** inspect `bd config get export.auto`, `bd config get export.interval`, and `bd config get export.git-add`. Document that auto-export is optional/throttled, not an every-mutation guarantee. Direct closeout explicitly runs `bd export --readonly`, verifies canonical target parity, and commits before successful-closeout handoff, not before unfinished continuation. Dolt is canonical; JSONL is interchange, not history backup or remote sync. Test consecutive mutations/export parity in an isolated workspace, never live history.
- **Severity:** DRIFT

### BEADS-4: Audit ownership
- **Check:** inspect `bd config get audit.enabled` and `git ls-files -- .beads/interactions.jsonl`. Sidecar is optional/incomplete in 1.3.1; preserve existing tracked history. Closeout owns exact closure appends only. Dirty reopen/assignment/foreign rows require origin-owner reconciliation and persistence at that transition boundary, not deletion, untracking, or broad closeout acceptance. Do not attribute old rows to current handoff without writer evidence.
- **Severity:** DRIFT

### BEADS-5: Honest health evidence
- **Check:** `agnt doctor --json` and `bd doctor --json` report capability, not merely exit code. Embedded `embedded_unsupported` is degraded/unverified; `bd list --limit 1 --json` and supported `bd doctor --check=conventions --json` prove only queryability and conventions. No automatic reinitialization or server-mode migration.
- **Severity:** DRIFT / NOT_SURE when full health cannot be verified
