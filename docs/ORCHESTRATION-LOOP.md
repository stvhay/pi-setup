# Orchestration Loop Decision

**Date:** 2026-06-27
**Updated:** 2026-08-11
**Status:** Accepted

## Context

The repository supports two execution paths:

1. direct Pi coding in the current session; and
2. explicit Beads-backed dispatch through private run artifacts.

Both paths use Beads as the durable work graph. Artifact-backed dispatch adds invocation/result evidence, policy-selected headless workers, worktree policy, and closeout gates. Long-lived scheduling and Pi runtime automation now belong to a separate project rather than this reusable configuration repository.

## Decision

Use **direct Pi coding by default**. Before code edits, confirm a Bead exists; then inspect, edit, verify, and commit in the current Pi session.

Keep **manual artifact-backed dispatch** as an explicit option for delegated or unusually strict work:

```bash
agnt work plan <bead-id> --action <action> --target <ref> --dry-run
agnt work run <bead-id> --action <action> --target <ref> --claim --close-bead
```

Do not add a background daemon, scheduler, service protocol, or TUI lifecycle manager here. Automation wrappers may consume Pi and `agnt` through their public interfaces from a separate project.

## Consequences

- Direct work stays lightweight while retaining the Bead requirement.
- Strict dispatch can preserve policy, approvals, worker sessions, evidence, and closeout state in inspectable artifacts.
- This repository avoids owning long-lived process, retry, scheduling, lease, and recovery state.
- Remote or destructive git operations, deployments, hook installs, Beads deletion, Beads remote changes, and Dolt history rewrites still require explicit approval.

## Canonical details

- [Invocation and Result Artifacts](RUN-ARTIFACTS.md) — bundle schemas and artifact commands.
- [The agnt System](AGNT-SYSTEM.md) — overall command and workflow architecture.
