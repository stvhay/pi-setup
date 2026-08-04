# Orchestration Loop Decision

**Date:** 2026-06-27
**Updated:** 2026-07-27
**Status:** Accepted

## Context

The repository supports two execution paths:

1. direct Pi coding in the current session; and
2. optional Beads-backed dispatch through run artifacts and a project-local runner.

Both paths use Beads as the durable work graph. The optional path adds private run-bundle evidence and a scheduling boundary, but also adds lifecycle, state, and recovery machinery.

## Decision

Use **direct Pi coding by default**. Before code edits, confirm a Bead exists; then inspect, edit, verify, and commit in the current Pi session. Normal work does not require runner startup, run bundles, orchestrator-only tools, or worktree-per-epic dispatch.

Keep **artifact-backed dispatch and the project-local runner** as explicit opt-in tools for delegated, scheduled, or unusually strict work:

```bash
# Manual artifact-backed dispatch
agnt work plan <bead-id> --action <action> --target <ref> --dry-run
agnt work run <bead-id> --action <action> --target <ref> --claim --close-bead

# Optional service
agnt work daemon start --json --concurrency 1
agnt work runner status --json
agnt work daemon stop --json --drain
```

The runner is project-local and loopback-only. It is never started by a normal Pi session and is not a global daemon, launch agent, hook, or remote scheduler.

## Consequences

- Direct work stays lightweight while retaining the Bead requirement.
- Strict dispatch can preserve policy, approvals, worker sessions, evidence, and closeout state in inspectable artifacts.
- Orchestration complexity remains opt-in rather than becoming a tax on ordinary coding.
- Remote/destructive git operations, deployments, hook installs, Beads deletion, Beads remote changes, and Dolt history rewrites still require explicit approval in either path.

## Canonical details

- [Project-Local Runner Service](RUNNER-SERVICE.md) — lifecycle, API, scheduling, security, and runtime state.
- [Invocation and Result Artifacts](RUN-ARTIFACTS.md) — bundle schemas and artifact commands.
- [The agnt System](AGNT-SYSTEM.md) — overall command and workflow architecture.
