# Project-Local Runner Service

The runner service is an optional single-user execution boundary for approved Beads work. It is project-local, loopback-only, and starts only through explicit `agnt work daemon` commands or an opted-in Pi orchestrator session. A normal Pi session does not start it. It is not a host-level launch agent, login item, global daemon, hook, or remote scheduler.

## Responsibilities

The service owns scheduling and executor lifecycle for one project root:

- attach Pi TUI sessions as informational client records;
- expose runner health, status, events, active work, budget, context, and cost state;
- schedule ready Beads work through the same `agnt work` validators and `.pi/runs` artifacts used by manual dispatch;
- prevent duplicate active bead dispatch and serialize overlapping implementation write sets;
- honor pause, resume, bounded concurrency, retry/backoff, budget gates, and graceful drain;
- keep runtime state under `.pi/runner/` and evidence under `.pi/runs/`.

Beads remains the durable work graph. `.pi/runs` remains the execution evidence store. The runner state files are local runtime coordination data, not source of truth.

## Startup flow

Direct Pi coding is the default: confirm a Bead exists before changing code, then inspect, edit, and test with the normal tools. No startup doctor, runner process, lease, status polling, or tool restriction runs in this path.

To select the orchestration path, start Pi with the extension flag or environment variable:

```bash
pi --orchestrator-service
# or
PI_ORCHESTRATOR_SERVICE=1 pi
```

The opted-in extension then:

1. runs `agnt doctor --profile orchestrator-startup --json`;
2. requires a ready report before background dispatch;
3. starts or attaches the service with `agnt work daemon status|start`;
4. attaches an informational client record, restricts the session to orchestrator tools, and polls service status; and
5. exposes status through `ticket_gateway`, `/runner`, and the TUI widget.

The legacy `scripts/pi-bootstrap-repair-mode.sh`, `PI_ORCHESTRATOR_REPAIR_TOOLS=1`, and `/runner repair-tools` controls remain available for explicit recovery of the optional orchestration path. They are not needed for normal direct implementation.

## Shutdown and drain

When a Pi session exits, the extension detaches its informational client record:

```http
DELETE /v1/leases/<leaseId>
```

This does not change autonomous scheduling. An explicit operator drain stops new dispatches while active executor slots finish; the service re-evaluates drain completion after every scheduler loop and then exits. `agnt work daemon stop --json --drain` uses that graceful path. `--force` is explicit operator-only shutdown through the service API.

## Operator commands

```bash
# Lifecycle: direct process/service boundary
agnt work daemon status --json
agnt work daemon start --json --concurrency 1
agnt work daemon stop --json --drain
agnt work daemon stop --json --force

# Client operations: REST calls to the running service
agnt work runner status --json
agnt work runner pause --json --reason "operator pause"
agnt work runner resume --json
agnt work runner tick --dry-run --json --limit 1

# Model-facing structured status surface
tag='{"operation":"runner_status"}'
agnt gateway --payload "$tag" --json
```

If the service is absent, runner client commands return a clear JSON payload with `status: "not-running"`, `connected: false`, and suggested action `agnt work daemon start --json`.

`agnt work loop` is deprecated; use `agnt work daemon start` for the service lifecycle and `agnt work runner tick` for bounded debug/operator ticks.

## Runtime files

All service runtime files live under `.pi/runner/` and are gitignored.

```text
.pi/runner/service.json        # pid, host, port, baseUrl, tokenPath, root, API version
.pi/runner/token               # local bearer token; chmod 0600 where supported
.pi/runner/state.json          # paused/draining/running, informational clients, activeRuns, budget, heartbeat
.pi/runner/state.lock          # flock guard for atomic state read-modify-write transactions
.pi/runner/events.jsonl        # compact append-only service event stream
.pi/runner/active/<run-id>.json # active run snapshots for status and crash recovery
.pi/runner/lock.json           # singleton lock/stale detection
.pi/runner/service.log         # daemon child stdout/stderr
```

Do not commit these files. Do not treat them as durable closeout evidence. Promote important evidence to Beads or `.pi/runs`.

## API contract

The service binds to `127.0.0.1` by default. Clients authenticate with:

```http
Authorization: Bearer <contents of .pi/runner/token>
```

Minimum v1 endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Liveness, API version, project root, pid, base URL. |
| `GET` | `/v1/status` | Running/paused/draining state, leases, active runs, budget, service metadata. |
| `POST` | `/v1/leases` | Attach an informational Pi/client record `{leaseId, sessionId, client}`. |
| `DELETE` | `/v1/leases/<leaseId>` | Detach an informational client; autonomous scheduling is unchanged. |
| `POST` | `/v1/drain` | Explicitly stop accepting new work and exit after active work is reaped. |
| `POST` | `/v1/stop` | Operator shutdown; force mode is explicit. |
| `POST` | `/v1/pause` | Pause scheduling with a reason. |
| `POST` | `/v1/resume` | Resume scheduling unless draining. |
| `POST` | `/v1/tick` | Run one bounded service-mediated scheduling tick. |
| `GET` | `/v1/events?since=<offset>` | Read compact JSONL event catch-up. |

Status payloads expose compact active-work summaries:

```json
{
  "bead": "pi-abc.1",
  "slug": "short-work-title",
  "epicId": "pi-abc",
  "runId": "runner-pi-abc.1-YYYYmmddHHMMSS",
  "status": "running",
  "model": "provider/model",
  "thinkingLevel": "high",
  "context": {"used": 12345, "limit": null, "percent": null, "source": "metrics"},
  "cost": {"usd": 0.42, "source": "metrics"},
  "bundle": ".pi/runs/<run-id>",
  "blockers": []
}
```

When usage is unavailable, context and cost are reported as `unknown`; the service does not invent values.

## Scheduling and safety gates

The scheduler reads ready Beads, validates `metadata.pi`, and starts work only through `agnt work` run artifacts. Implementation dispatch still requires approved metadata, write sets, closeout policy, and safe worktree policy. Read-only/review work can use bounded concurrency; overlapping implementation write sets are serialized.

Budget behavior is intentionally conservative:

- default budget mode is `limitsEnforced=false` and reports `cost-unknown` / `context-unknown` when metrics are absent;
- configured enforced limits can pause/block new dispatch with a durable Beads decision;
- active work is not killed by a newly detected budget limit;
- selected model and thinking effort remain policy-selected by `agnt` routing, not service-side overrides.

Existing global safety gates remain in force: no auto-push, merge, deploy, branch deletion, hook installation, Beads deletion, Beads remote change, or Dolt history rewrite without explicit approval.

## Security model

The current security model is local single-user containment:

- loopback HTTP only by default;
- random bearer token in a gitignored local file;
- token redacted from status payloads;
- one live service per project root via `.pi/runner/lock.json`;
- no host-level service installation;
- no remote API exposure.

Future multi-project or remote dashboards must add a separate authentication, authorization, and lifecycle design rather than reusing this local token model as-is.

## Related docs

- [The agnt System](AGNT-SYSTEM.md)
- [Architecture](ARCHITECTURE.md)
- [Orchestration Loop Decision](ORCHESTRATION-LOOP.md)
- [Run Artifacts](RUN-ARTIFACTS.md)
- [agnt command reference](../pi/agent/bin/README.md)
