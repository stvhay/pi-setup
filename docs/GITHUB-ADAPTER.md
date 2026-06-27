# GitHub Adapter Decision

**Date:** 2026-06-27
**Status:** Decided — no GitHub issue adapter for now

## Context

The revised agent architecture uses Beads as the canonical agent-facing work
graph. GitHub issues can be useful for collaboration, public tracking, or
repository hosting workflows, but using GitHub and Beads as equal task trackers
would reintroduce two sources of truth.

## Decision

Do not implement GitHub issue mirroring for this repository now.

- Agents should use Beads: `bd ready`, `bd show <id>`, `bd update`, `bd close`.
- GitHub issues may be drafted or exported later only through an explicit
  adapter workflow.
- Any future adapter must make directionality clear: Beads remains canonical;
  GitHub is a publication/integration surface.

## Consequences

- Local agent work is simpler: one queue, one dependency graph, one state model.
- There is no automatic public issue mirror.
- If collaboration needs change, a future adapter can be designed as an
  explicit export/import tool with tests and conflict rules.

## Future adapter requirements

A future GitHub adapter should define:

1. Which beads are exported.
2. Whether sync is one-way or bidirectional.
3. How conflicts are handled.
4. How labels/statuses map.
5. Which operation requires approval.
6. How secrets/tokens are provided without tracking them.
7. How adapter actions are recorded in run artifacts.
