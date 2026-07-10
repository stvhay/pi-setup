# Live Pi Acceptance — Orchestrator Runner Service

**Date:** 2026-07-09
**Epic:** `pi-2m1` — Project-local runner service and orchestrator-only Pi startup
**Task:** `pi-2m1.11` — Run live Pi acceptance for orchestrator runner service
**Run bundle:** `.pi/runs/runner-service-live-acceptance`
**Approval:** `pi-8u6` approved by user instruction: “task 10 soak approved, then follow up with live acceptance”.

## Scope

This acceptance deployed tracked repository Pi config to live `~/.pi`, then used
live `pi` / `~/.pi/agent/bin/agnt` from this repository to exercise startup and
shutdown behavior.

Allowed actions performed:

- `scripts/bootstrap-pi-config.sh --apply`
- live config validation with `PI_CONFIG_DIR=/Users/hays/.pi scripts/check-pi-config.sh`
- live startup doctor with `~/.pi/agent/bin/agnt doctor --profile orchestrator-startup --strict --json`
- bounded `pi --mode rpc` lifecycle checks without model prompts or live work dispatch
- live runner/gateway status checks

Forbidden actions not performed: commit, push, merge, branch deletion, worktree
removal, Beads history rewrite, host-level launch agent/service/hook install,
and uncontrolled live implementation dispatch.

## Deployment Evidence

| Check | Result | Notes |
|---|---:|---|
| `scripts/bootstrap-pi-config.sh --dry-run` | rc 0 | Planned `rsync -a --delete` from tracked `pi/` to `/Users/hays/.pi/` while excluding secrets/runtime state. |
| Pre-deploy live extension | observed absent | `/Users/hays/.pi/agent/extensions/orchestrator-service.ts` did not exist before deploy. |
| `scripts/bootstrap-pi-config.sh --apply` | rc 0 | Live config deployed successfully. |
| Live file parity | matched | SHA-256 parity confirmed for `agent/extensions/orchestrator-service.ts`, `agent/bin/agnt`, and `agent/bin/agnt_lib/runner_service.py`. |
| Live settings | matched source | Packages remained `npm:pi-archimedes` and `npm:pi-observational-memory@3.0.3`; default model `gpt-5.5`; thinking level now `medium` from tracked source. |
| Live config check | rc 0 | `PASS: Pi config layout is valid: /Users/hays/.pi`. |

## Startup Health Evidence

`~/.pi/agent/bin/agnt doctor --profile orchestrator-startup --strict --json`
returned rc 0 with:

- `passed=true`
- `status=passed`
- `failures=0`
- `warnings=0`
- `acknowledgedWarnings=0`
- `startup.backgroundDispatchAllowed=true`

Before launching live Pi RPC, live daemon status was `not-running` and gateway
runner status reported `service.state=absent`, `connected=false`, `activeCount=0`.

## Live Pi RPC Lifecycle Evidence

Two bounded RPC launches were used to avoid an uncontrolled model call:

1. `pi --mode rpc --no-session --approve --name runner-service-live-acceptance`
2. `pi --mode rpc --approve --session-dir .pi/runs/runner-service-live-acceptance/artifacts/pi-rpc-sessions --session-id runner-live-acceptance --name runner-service-live-acceptance`

Both returned successful `get_state` responses without prompting a model. The
persisted-session response recorded:

- `sessionId=runner-live-acceptance`
- `sessionName=runner-service-live-acceptance`
- `sessionFile=.pi/runs/runner-service-live-acceptance/artifacts/pi-rpc-sessions/...jsonl`
- model `openai-codex/gpt-5.5`
- thinking level `medium`
- `messageCount=0`
- `pendingMessageCount=0`

The live extension emitted UI requests showing that the deployed extension ran:

- `setStatus` → `orch checking`
- `setStatus` → `orch starting`
- `setStatus` → `orch draining`
- `setWidget` for `orchestrator-service` with runner state lines

Live `~/.pi/agent/bin/agnt work runner status --json` observed the runner service
running with a Pi lease attached:

- `running=true`
- `leaseCount=1`
- `activeRuns=0`
- `paused=false`
- `status=draining`
- `acceptingNewWork=false`

Live gateway status during the run reported:

- `connected=true`
- `service.state=present`
- `leaseCount=1`
- `activeCount=0`
- `status=draining`

After closing RPC stdin, live daemon status returned:

- `status=not-running`
- `running=false`
- `connected=false`

No live implementation work was dispatched.

## Finding: Headless RPC Startup/Shutdown Race

The live extension loaded, started the runner service, attached a lease, emitted
status/widget UI requests, and drained/stopped the service. However, both RPC
runs entered `draining` before a stable non-draining `running` observation could
be captured. The RPC stdout also showed a later widget update:

```text
orch error
Orchestrator service error: fetch failed
```

This appears to be a startup/shutdown ordering race in headless RPC mode: a
`session_shutdown` path can run while `session_start` is still completing, after
which startup/status polling continues and reports a noisy fetch failure once the
service has drained.

Follow-up filed: `pi-2m1.12` — Harden orchestrator-service startup shutdown race
in headless RPC.

## Result

Live deployment and core lifecycle were verified, but live acceptance is not a
clean pass because the headless RPC lifecycle revealed a shutdown/startup race.
The issue is captured as `pi-2m1.12`; no extra implementation was performed under
this verification approval.

## Runtime Hygiene

- No host-level launch agent, hook, or service was installed.
- Runtime runner files remained under project-local `.pi/runner/` and are ignored
  by `.gitignore`.
- Live Pi session artifacts from the persisted RPC test were written under the
  run bundle session directory, not the default live session directory.
- Repository source remains the source of truth for future live deployments.
