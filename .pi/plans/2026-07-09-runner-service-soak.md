# Runner Service Controlled Soak

**Date:** 2026-07-09
**Epic:** `pi-2m1` — Project-local runner service and orchestrator-only Pi startup
**Task:** `pi-2m1.10` — Run controlled single-user runner service soak
**Run bundle:** `.pi/runs/runner-service-task10-soak`
**Approval:** `pi-16b` approved by user for the controlled repo-local soak.

## Scope

This soak verified the repository-local runner service path without deploying to
live `~/.pi`, committing, pushing, installing host-level services, adding hooks,
or running live work dispatch.

Commands used the repository source command `pi/agent/bin/agnt`. Runtime outputs
were captured under `.pi/runs/runner-service-task10-soak/artifacts/`.

## Pre-flight

- Branch: `main`.
- Working tree: dirty with accumulated approved Task 1-9 implementation/doc
  changes, plus this soak record. This is expected for the current batch.
- Unrelated untracked file noted and not modified: `references/bigpowers-research.md`.
- No deployment to `~/.pi` was performed.

## Command Evidence

| Step | Command | Result | Notes |
|---|---|---:|---|
| Startup doctor | `pi/agent/bin/agnt doctor --profile orchestrator-startup --strict --json` | rc 0 | `passed=true`, `failures=0`, `warnings=0`, `acknowledgedWarnings=0`. |
| Pre-start daemon status | `pi/agent/bin/agnt work daemon status --json` | rc 0 | `status=not-running`, `running=false`. |
| Start service | `pi/agent/bin/agnt work daemon start --json --concurrency 1` | rc 0 | `started=true`, pid `70635`, service became `running`, `acceptingNewWork=true`, loopback metadata written under `.pi/runner/`. |
| Runner client status | `pi/agent/bin/agnt work runner status --json` | rc 0 | Service reported `status=running`, `running=true`, `draining=false`, `paused=false`, `activeRuns=[]`. |
| Gateway runner status | `pi/agent/bin/agnt gateway --payload '{"operation":"runner_status"}' --json` | rc 0 | Gateway reported `connected=true`, service `state=present`, `status=running`, `activeCount=0`, `acceptingNewWork=true`. |
| Dry-run tick | `pi/agent/bin/agnt work runner tick --dry-run --json --limit 1` | rc 0 | `dryRun=true`; no live starts. One action was `would_block` for `pi-ede` because `metadata.pi` is required for automatic dispatch. |
| Health while service running | `pi/agent/bin/agnt work health --json` | rc 0 | `passed=true`, `failureCount=0`, `warningCount=1`; warning was expected `dirty-main-checkout`. |
| Drain stop | `pi/agent/bin/agnt work daemon stop --json --drain` | rc 0 | `draining=true`, `acceptingNewWork=false`, `activeRuns=[]`. |
| Post-stop daemon status | `pi/agent/bin/agnt work daemon status --json` | rc 0 | `status=not-running`, `running=false`, connection refused as expected after drain exit. |
| Post-stop health | `pi/agent/bin/agnt work health --json` | rc 0 | `passed=true`, `failureCount=0`, `warningCount=1`; warning remained expected dirty checkout. |
| Post-stop gateway status | `pi/agent/bin/agnt gateway --payload '{"operation":"runner_status"}' --json` | rc 0 | Gateway reported absent service: `status=not-running`, `connected=false`, `service.state=absent`, `activeCount=0`. |
| Runtime ignore check | `git check-ignore -v .pi/runner/service.json .pi/runner/state.json .pi/runner/token .pi/runner/events.jsonl` | rc 0 | All checked runner runtime files are ignored by `.gitignore:.pi/runner/`. |

## Observations

- The startup health profile passed strictly with no failures or warnings.
- The service started as a project-local loopback runner and exposed REST-backed
  runner and gateway status.
- Dry-run queue processing did not dispatch live work. It correctly identified
  blocked ready work (`pi-ede`) without starting it.
- Drain stop set `acceptingNewWork=false`, found no active runs, and the service
  exited. Later daemon and gateway status calls reported the service absent.
- Health checks passed before and after drain. The only health warning was
  `dirty-main-checkout`, expected because this branch contains the approved
  accumulated Task 1-10 changes.
- Runtime `.pi/runner/` files are gitignored and should not be committed.

## Result

The controlled repo-local soak passed: the service can start, report status,
serve REST-backed gateway visibility, dry-run schedule, drain, stop, and leave no
tracked runner runtime artifacts.

## Live Acceptance Follow-up Boundary

The user requested live acceptance after this soak. That is intentionally a
separate gate because it deploys repository Pi config to live `~/.pi` and tests
actual `pi` startup/shutdown behavior.

Proposed live acceptance scope:

1. Run `scripts/bootstrap-pi-config.sh --apply` to deploy tracked `pi/` config to
   live `~/.pi`.
2. Launch `pi` from this repository.
3. Verify the orchestrator service extension runs `session_start`, applies the
   startup doctor gate, starts or attaches the project-local runner service,
   creates a service lease, restricts main-thread tools, and surfaces runner
   status/widget information.
4. Exit `pi` and verify `session_shutdown` releases the lease and requests drain.
5. Confirm no host-level launch agent, hook, push, merge, or commit is performed.

This live acceptance should require a separate Beads-backed approval before the
`--apply` deployment step.
