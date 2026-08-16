# Architecture

pi-setup is configuration-as-code for a reusable Pi agent environment. It has
one deployable artifact (the `pi/` tree), one orchestration CLI (`agnt`), and
a feedback loop that lets routing and prompts improve from observed outcomes.
For the narrative overview, start with [The agnt System](AGNT-SYSTEM.md). For
the feedback loop, see [Self-Improvement Loop](SELF-IMPROVEMENT.md).

## Repository vs runtime

```text
pi-setup/ (this repo, source of truth)
├── pi/                  deployable Pi config  ──rsync──▶  ~/.pi (runtime copy)
├── .beads/              Beads work graph export/config; local DB ignored
├── docs/                architecture, procedures, design decisions, audits
├── scripts/             deploy, layout checks, behavioral eval suite
├── tests/               pytest for agnt/agent-instructions internals
├── forks/               pinned submodules for active upstream contributions
└── .pi/                 project plans; optional ignored runtime/scratch
```

- `scripts/update-pi-config.sh` deploys `pi/` → `~/.pi` by default;
  `--dry-run` previews changes. Runtime secrets/state (`auth.json`, `sessions/`,
  `trust.json`, `~/.pi/metrics/`, caches) are rsync-excluded and survive deploys.
  Missing, mismatched, or stale-patch exact package bases are installed before
  tracked patches run; current exact installs stay untouched to avoid broad npm reification.
  Patch-base entries remain exact in the runtime npm manifest so installing one
  cannot upgrade another through npm's default caret ranges.
- Edits go in this repo, then deploy. The live `~/.pi` is never the place to
  change config; `rsync --delete` will overwrite it.
- `scripts/apply-pi-package-patches.sh` applies temporary, version-locked patches
  from `patches/pi-packages/`. Normal deployment invokes it automatically after
  exact base reconciliation. It is idempotent and fails closed on version or
  source-context mismatch. The Langfuse 1.5.14 projection keeps ordinary strings
  finite, permits valid media only on the transient OTel extraction path, stores
  bounded omission markers in REST fallback, emits privacy-controlled versioned
  tool-payload byte states, and exposes bounded local quality ports without making
  them released-package evidence. The Archimedes 2.0.1
  projection adds bounded agentic/one-shot execution, dual legacy/Pi 0.84 child-stream
  parsing, bounded parent-visible outputs, adaptive token progress, and repeated-error
  termination while preserving native v2 child session/model behavior.
- Two instruction levels share one filename: the repo root `AGENTS.md` is
  *project* instructions for working on pi-setup itself; `pi/agent/AGENTS.md`
  is the *global* instruction file every Pi session loads after deploy.

## Layers (data flows top to bottom, evidence flows back up)

```text
catalog.json      model families -> venues, cost classes, watt/rate facts
      │
tasks/*.md        routing policy per task (preferred/qualified/avoid targets)
      │
agnt route        constraint filter (enabledModels, modality, context, access)
      │           + billing/risk gates + outcome-history demotion
      │           (repository=agentic; subscription default; metered=budgeted fresh worker)
      │
      ├─ Archimedes `subagent` for interactive, one-shot, and parallel peers
      └─ internal headless worker for evals and run artifacts
                         │
subagent observer + internal worker metrics
                         │
resolved private metrics records ──consolidate──▶ ~/.pi/metrics/
      │                                              (global store)
      └──────── outcome annotations feed back into `agnt route` ───────┘
```

### Model catalog (`pi/agent/catalog.json`)

A **family** is one set of weights (or a close equivalent) reachable through
one or more provider venues. Active policy keeps OpenAI/Codex as the root and
uses Pi's built-in OpenRouter provider for bounded metered diversity. The
catalog contains only configured Codex and OpenRouter venues and remains the
single source for routing facts: cost class, billing class, modalities, context
window, reasoning capability, and rates. `agnt` and `agent-instructions` read it
via shared `bin/_agnt_common.py`; no model facts live in code.
Every metered OpenRouter model runs only in a fresh subagent, never as a
continuation model for a long root conversation. Repository routes use agentic mode
and prefer qualified subscription venues at zero marginal cost. Metered agentic
repository candidates require catalog-rate estimates, `quality-benefit` or
`missing-capability` justification, an aggregate marginal budget, and per-child
request/token/cost/duration limits. The tracked Archimedes wrapper rejects repository
one-shot calls and incomplete metered repository evidence. It also uses this catalog's
`billingClass`—not provider-name inference—to inject a configurable 16,384-token
provider output cap only for metered one-shot children. Explicit tighter caps win;
subscription and other agentic children receive no automatic token or cost cap.
Applied evidence distinguishes that deliberate ceiling
from a lower existing provider/model ceiling, while every provider `length` stop is
failed `output-limit` termination with usable partial output preserved in parent-owned
artifacts. Review discovery packets cap contracted JSON at 6,000 characters so valid
work fits below the deliberate metered ceiling. Provider output allowance can include
reasoning before visible final output, so prompt character targets do not justify a low
ad hoc token cap. Malformed JSON alone does not identify caller, wrapper, provider,
context, or network failure; normalized termination evidence does. See the approved
[Model Portfolio Decision](MODEL-PORTFOLIO-2026-08.md).

### Work, tasks, prompts, skills, roles, and tools

The context system uses small orthogonal primitives. See
[Self-Improvement Principles](SELF-IMPROVEMENT-PRINCIPLES.md) for the design
rationale.

- **Work item / bead**: durable task-graph node. Answers "what unit of work is
  scheduled, blocked, or complete?" Beads is the canonical agent-facing work
  queue for dependencies, approvals, blockers, closeout, and quality follow-up
  work. GitHub issues are not mirrored now; any future integration should
  follow the [GitHub Adapter Decision](GITHUB-ADAPTER.md) and remain an adapter
  rather than a second source of truth.
- **Invocation/result message**: structured interface between orchestration and
  workers. Answers "what should run now?" and "what happened with what
  evidence?" Invocation v2 records ticket metadata, selected model/thinking,
  dispatch/session/memory policy, todo seeds, and worktree snapshots. Result v2
  records evidence, follow-ups, session/transcript/memory refs, approval/decision
  refs, health checks, and closeout checks.
- **Task** (`pi/agent/tasks/*.md`): operational routing label (`review`,
  `orchestration`, …) with preferred/qualified/avoid target lists in
  frontmatter. Answers "which model or execution default?" A task named
  `orchestration` is a routing category, not the orchestration engine itself.
- **Prompt / action template** (`pi/agent/actions/*.md`): explicit invocation pattern. Answers
  "what action is being started now, with which arguments?" Actions select
  tasks, skills, roles, effects, and output contracts.
- **Skill** (`pi/agent/skills/*/SKILL.md`): reusable capability package —
  method, domain expertise, references, helper scripts, or any mix of prose and
  code. Answers "what method or capability should be loaded?"
- **Role** (`pi/agent/AGENTS.d/roles/*.md`): delegated-worker stance and output
  contract (code-reviewer, verifier, …). Answers "how should this peer behave
  and report?" Roles may reference relevant skills, but reusable workflow
  belongs in skills and model preference policy belongs in tasks.
- **Tool/eval/gate** (`pi/agent/bin/`, `pi/agent/evals/`, scripts):
  deterministic operation or check. Answers "what should code perform or
  verify instead of prose?"

### Instruction composition (`agnt instructions` / `agent-instructions`)

Append-only concatenation of context packages: a root file (`AGENTS.md`,
`SKILL.md`, `SOUL.md`) plus supplements in a sibling `<stem>.d/` directory.
Default composition order: global `pi/agent/AGENTS.md` → global model/role
overlays → discovered project instruction files (`AGENTS.md`, `AGENT.md`,
`CLAUDE.md` from git root to cwd) → project overlays, deduplicated.

Model overlays resolve **family first, then venue**:
`AGENTS.d/models/<family>.md` (family ids from the catalog) applies to every
venue of the same weights; slash-style `AGENTS.d/models/<provider>/...` files
refine one venue. `--check` validates structure and scans all composed files
for gate-weakening phrases.

### Orchestration CLI (`pi/agent/bin/agnt`)

Front controller for: `route` (recommend model + thinking level for
task/risk/budget, JSON with explicit reasons and rejected candidates),
`review` (validate/summarize structured findings), `metrics`
(status/annotate/consolidate), `eval`
(filesystem-defined deterministic evals), `instructions`, `prompt`, `action`,
`runs`, `work` (including guarded local integration), `approvals`, `gateway`,
`web-search`/`web-fetch`, and `plans-dir`.

Design constraint: `agnt` is a front controller, not the home for subsystem
logic. Command implementations live under `pi/agent/bin/agnt_lib/` (`routing`,
`invoke`, `review`, `metrics`, `evals`, `tasks`, `prompt`, `actions`, `runs`,
and `work`) and share catalog/frontmatter helpers through `_agnt_common.py`.
New shared behavior should move into those importable modules, or a new
`agnt_lib` module when the seam is clear; avoid adding another independent
model/catalog/parser table inside the executable.

Concern seams are explicit: `agnt_lib` owns deterministic domain logic; the
`agnt` CLI adapts it for humans, CI, and headless callers; Pi extensions own
lifecycle, UI, session, and provider integration; typed tools are thin
agent-facing adapters. Metadata validation lives in `orchestration.py`, approval
flow in `approvals.py`, ticket operations in `gateway.py`, worktree policy in
`worktree_policy.py`, target-ref integration semaphore and merge transaction in
`integration.py`, health checks in `health.py`, and durable quality-signal
collection in `quality.py`. Long-lived Pi process automation and scheduling live
outside this repository.

Local integration uses POSIX `fcntl.flock` under Git's common directory, keyed
by opaque target-ref identity. This serializes preflight, one merge, conflict
abort, and post-merge verification across linked worktrees. Kernel ownership
ends on descriptor close or process death; persistent owner metadata is advisory
stale-recovery evidence and contains no paths, refs, arguments, or content.
`git worktree lock` cannot provide this transaction because it protects a
worktree from administrative prune/move/remove, not commands executed inside it.
Git's own index/ref lockfiles cover individual writes rather than the complete
integration invariant. Helper Git calls clear ambient `GIT_*` overrides, pin
approved worktree, disable hooks/fsmonitor/signing/signature enforcement, and
reject command-bearing custom merge/filter/branch-options config. Timeout,
cancellation, conflict, divergence, dirty state, unsafe config, or uncertain
recovery stops without a daemon or destructive reset.

### Inspectable work backbone

The orchestration shape is a transparent work pipeline:

```text
work graph -> invocation messages -> worker runs -> result messages -> artifacts -> state transitions
```

Chat is a UI, not the system of record. Every code-changing task requires a
Bead before edits begin. The default execution path is direct Pi inspection,
editing, and verification in the current session. Nontrivial work should leave
durable artifacts — plans, reports, patches, metrics, verification logs, or
optional run records — with enough structure for a human, tool, or later agent
to inspect, retry, verify, or continue the work. Current pieces are: `.beads/`
for work graph export/config, `.pi/plans/` for plans, resolver-selected private
directories for optional invocation/result artifacts, parent-owned delegated
results, and runtime telemetry (project `.pi/runs/`, `.pi/delegated-results/`,
and `.pi/metrics/` only when Git proves each candidate ignored, untracked, and
symlink-safe; hashed `~/.pi/runtime/` fallback otherwise), `agnt action render`
and `agnt runs` for message artifacts, `agnt work` for dry-run bead dispatch
plans, plan trees, manual artifact execution, and health checks, `agnt quality`
for deterministic five-activity assessment, `agnt approvals` for durable human
decisions, `agnt gateway` for
constrained Pi extension access, Archimedes `subagent` for interactive peer
dispatch, `agnt runs invoke` / `agnt work run` for artifact-backed headless
worker execution, `agnt context-health` for context entropy checks, and
`pi/agent/evals/` for gates. See the [Orchestration Loop
Decision](ORCHESTRATION-LOOP.md) for the explicitly selected Beads-first gated
workflow.

### Lifecycle capture, metrics, and feedback

`quality-lifecycle.ts` owns root `session_start` and `agent_settled` capture. It
resolves current local session/Bead ownership and calls `agnt quality capture`
with bounded IDs and EvidenceRefs only; prompt and response bodies never cross
that local CLI boundary. The same adapter sends bounded evaluator observations
through the public `pi-langfuse/quality` capture port when available and records
an explicit gap when local ownership or optional projection is unavailable.
`langfuse-config-env.ts` treats missing package, registration, and capture ports
as optional failures; it imports no package-private runtime, redaction, or utility
modules. The subagent
observer retains only peer artifact/metric projection and provider-circuit
behavior, so pi-langfuse cannot block root startup.

Raw per-invocation records land in the resolver-selected private
`metrics/invocations` directory. The resolver uses
`<git-root>/.pi/metrics/invocations/` only when Git proves the candidate safe;
otherwise it uses the repository-keyed `~/.pi/runtime/<sha256>/` fallback.
Internal eval/run workers write their own records; the tracked subagent observer converts
completed unnamed Archimedes results to the same schema using counts and
lengths without prompt or response bodies. Before tool return, the parent writes
full child output under the resolver-selected `delegated-results` directory and
shares only bounded opaque refs in metric metadata. Named-profile metrics are
skipped because Archimedes does not expose their final provider.
`agnt metrics consolidate`
appends compact records
to the durable global store `~/.pi/metrics/agent-invocations.jsonl`; run it
manually or from a locally installed hook. `agnt route` aggregates outcomes by
family across pending and consolidated metrics and demotes families with
negative track records. `agnt quality assess --activity <id> --collect` derives
quality triggers from Beads, Git, run artifacts, health reports, context-health
warnings, and bounded eligible-unreviewed session counts. Unknown and lower-bound
evidence stays explicit; current and legacy labels suppress duplicate activity
packets, while new packets emit only `quality:<activity>`. Promoted findings keep
private matched post-change state; reviewed cohorts validate them or mark
recurrence, while public follow-up remains approval-gated. Git never tracks
telemetry; it tracks policy changes telemetry justifies.

External automation invokes receipt-bound `agnt quality assess/apply --json`.
Stable result classes and gaps distinguish no-op, review, human routing, applied,
and blocked outcomes. Under a reviewed autonomous policy, an exact active grant
may create or deduplicate one sanitized deterministic Bead through the existing
Beads adapter and Q14 claim/settlement state machine; other effects use existing
injected adapters. Caller supplies signal or periodic-backstop inputs and owns
cadence. Repository provides no scheduler, poll loop, daemon, or service.

This kernel is internal governance and evidence handling, not certification or a
parallel quality-management system. Git owns the control plan and code, private
runtime storage owns receipts, assignments, claims, and cohort state, and Beads
owns durable work and human grants. None can substitute for another.

## Quality gates

Three test tiers, cheapest first:

1. `tests/` (pytest) — pure-function coverage of catalog lookups, routing
   ranks, cost attribution, overlay resolution. Free, instant.
2. `agnt eval run routing-smoke`, `role-context-smoke`, or
   `quality-process-smoke` — deterministic CLI checks. The quality smoke gate
   reuses six named pytest checks for evidence gaps, observe suppression, grant
   bounds, one-packet emission, atomic duplicate suppression, and revocation.
   Free, instant, and model-free.
3. `scripts/eval-workflow-compliance.sh --skill-mode candidate|deployed` —
   opt-in manual behavioral canary running real models in throwaway git repos,
   asserting filesystem effects (no writes before approval, plans actually
   created, stops on main, …). It is not a routine completion gate: run it only
   on user request or for a stated behavior question routine telemetry cannot
   answer. Candidate mode isolates tracked skills; deployed mode tests live
   skills. Independent cases run concurrently, Pi JSON events reset an idle
   timeout, and each run retains event/provenance artifacts.

Layout/safety checks: `scripts/check-pi-config.sh` (required files present,
no secrets/submodule regression, action validation, context-health strict check,
and prompt inventory), `agent-instructions --check`. Optional orchestration
state is checked separately with `agnt work audit|health` when that path is used.

## Safety model

Layered gates, none overridable by overlays or `SOUL.md` (communication style
only): a Bead before every code-changing task, approval before implementation in
design workflows, fresh shell evidence before completion claims, read-only-by-
default peer work, and the suspicious-phrase scan on composed instructions.
Exact initial scope may include reversible local Git setup/cleanup, tracked
asset deletion previews, one local integration bound to target checkout/branch,
expected target HEAD, and source commit SHA through the guarded semaphore, and
one ordinary branch push after successful Bead closeout under shared approved-base, bounded-candidate, identity, remote-state, final-gate,
single-attempt, and post-push checks. PR actions, protected/production branches, unexpected divergence,
alternate merge/integration strategies, remote
deletion/ref mutation, force/reset/clean, tags/releases, and history rewrite
remain separately gated or prohibited. When
orchestration is explicitly selected, Beads-backed human decisions, recorded
worker sessions, one worktree per epic, and run health/closeout checks add
stricter optional gates.
