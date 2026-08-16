# pi-archimedes Result Port Contract

**Status:** Proposed; unreleased
**Target:** `danielcherubini/pi-archimedes` `main`
**Consumer:** pi-setup peer-result persistence, telemetry, and quality normalization
**Scope:** Contract proposal only; no upstream or runtime mutation

## Proven need

pi-setup consumes complete per-child execution evidence from the Archimedes
`subagent` tool, but currently repeats output-contract, limits, result,
termination, usage, and child-trace shapes. Its wrapper also derives the private
`agents` sibling path from the installed subagent entrypoint and casts bus
exports locally. Public ports must remove those copies and layout assumptions
without moving pi-setup policy into Archimedes.

## Public package exports

A satisfying release exposes these package subpaths without callers resolving
package files or deriving sibling paths:

```json
{
  "@pi-archimedes/subagent": {
    "exports": {
      ".": "./src/index.ts",
      "./agents": "./src/agents.ts",
      "./types": "./src/types.ts"
    }
  },
  "@pi-archimedes/core": {
    "exports": {
      "./bus": "./src/bus.ts"
    }
  }
}
```

`"./types"` publicly exports the result-port constants and types below.
`"./agents"` exports the narrow `resolveAgentModel` function below. `"./bus"`
exports `Events`, `getBus`, its typed bus interface, event map, and every payload
type below. Published type declarations must expose the same names and fields.

## Result and execution evidence

```ts
import type { Usage } from "@earendil-works/pi-ai";

export const SUBAGENT_OUTPUT_CONTRACTS = [
  "inline",
  "artifact",
  "status-only",
  "pass-no-findings",
] as const;
export type SubagentOutputContract =
  (typeof SUBAGENT_OUTPUT_CONTRACTS)[number];

export interface SubagentLimits {
  maxProviderRequests?: number;
  maxToolCalls?: number;
  maxTotalTokens?: number;
  maxOutputTokens?: number;
  maxCostUsd?: number;
  maxDurationMs?: number;
}

export type SubagentExecutionMode = "agentic" | "one-shot";

export interface SubagentExecutionProfile {
  mode: SubagentExecutionMode;
  thinking?: string;
}

export interface OutputLimitEvidence {
  requested: number;
  effective?: number;
  enforcement: "applied" | "unsupported";
}

export interface ResolvedChildExecution {
  profile: SubagentExecutionProfile;
  limits?: SubagentLimits;
  outputLimit?: OutputLimitEvidence;
}

export type SubagentTerminationReason =
  | "completed"
  | "user-abort"
  | "request-limit"
  | "tool-limit"
  | "token-limit"
  | "output-limit"
  | "cost-limit"
  | "time-limit"
  | "usage-unknown"
  | "repeated-error"
  | "process-error";

export type SubagentUsageState = "complete" | "partial" | "unknown";

export interface SubagentTermination {
  reason: SubagentTerminationReason;
  limit?: number;
  observed?: number;
  usageState: SubagentUsageState;
}

export interface SubagentUsage {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  cost: number;
  costBreakdown?: Usage["cost"];
  turns: number;
}

export interface SubagentChildTraceRef {
  sessionId: string;
  traceId?: string;
}

export interface SubagentProgressSummary {
  toolCount: number;
  tokens: number;
  durationMs: number;
}

export interface SubagentResult {
  agent: string;
  task: string;
  childSessionId?: string;
  childTrace?: SubagentChildTraceRef;
  exitCode: number;
  usage: SubagentUsage;
  provider?: string;
  model?: string;
  execution?: ResolvedChildExecution;
  outputContract?: SubagentOutputContract;
  finalOutput?: string;
  error?: string;
  termination?: SubagentTermination;
  progress?: SubagentProgress;
  progressSummary?: SubagentProgressSummary;
}

export interface SubagentDetails {
  mode: "single" | "parallel";
  results: SubagentResult[];
  progress?: SubagentProgress[];
}

export interface SubagentToolResult {
  content: Array<{ type: "text"; text: string }>;
  details: SubagentDetails;
  isError?: boolean;
  usage?: Usage;
}
```

Existing public progress types may remain where upstream owns them; the
published `SubagentResult` declaration must reference them through the public
`"./types"` surface, not a package-private import required from consumers.

All numeric limits are positive and finite when present. `execution.limits`
contains effective child limits after operator, caller, and execution-profile
resolution. `outputLimit` reports requested and actually applied provider
ceiling without claiming enforcement when unsupported.

Termination is terminal execution evidence, not a success score. `completed`
is the only successful reason. A nonzero exit may still carry useful
`finalOutput`, partial or complete usage, and exact termination evidence; those
fields must not be erased. Unknown usage remains `usageState: "unknown"` rather
than zero-filled proof.

`SubagentOutputContract` is a caller-supplied transport label. Archimedes may
copy it into each result but does not decide artifact persistence, quality,
acceptance, or review policy. Missing legacy labels remain distinguishable from
a requested value.

`childSessionId` remains the backward-compatible logical Pi session identifier.
When `childTrace` is present, `childTrace.sessionId` must equal
`childSessionId`; `traceId` is an opaque native ref and is omitted when unknown.
Archimedes must not query an optional telemetry service or infer a trace ID.
One-shot execution may omit both session and trace refs.

`details.results[]` remains the canonical complete per-child execution evidence.
Result array order remains request order. Presentation content may be bounded or truncated without changing `details.results[]`.
Pi `tool_result` remains the only result transport: no parallel result event, callback registry, or service is added. Nested `usage` on the Pi tool result remains aggregate accounting only; per-child usage stays in each result.

## Public agent-resolution seam

```ts
export function resolveAgentModel(name: string, cwd: string): string | undefined;
```

This function performs Archimedes-owned agent discovery and returns only the
configured model needed by a caller. It replaces deriving `agents.js` or
`agents.ts` from another package entrypoint. It does not select a model, rank an
agent, classify billing, or authorize dispatch.

## Typed bus payloads

```ts
export interface CostUpdatePayload {
  source: string;
  inputTokens?: number;
  outputTokens?: number;
  cacheReadTokens?: number;
  cacheWriteTokens?: number;
  cost?: number;
}

export interface TodoUpdatePayload {
  source: string;
  todos: Array<{
    id: number;
    title: string;
    description: string;
    status: "not-started" | "in-progress" | "completed";
  }>;
}

export interface TodoClearPayload {
  source: string;
}

export interface AskRequestPayload {
  source: string;
  requestId: string;
  questions: Array<{
    id: string;
    question: string;
    description?: string;
    options: Array<{ label: string }>;
    multi?: boolean;
    recommended?: number;
  }>;
}

export interface AskResponsePayload {
  requestId: string;
  cancelled: boolean;
  results: Array<{
    id: string;
    selectedOptions: string[];
    customInput?: string;
  }>;
}

export interface ArchimedesEventPayloadMap {
  "archimedes:cost_update": CostUpdatePayload;
  "archimedes:todos_update": TodoUpdatePayload;
  "archimedes:todos_clear": TodoClearPayload;
  "archimedes:ask_request": AskRequestPayload;
  "archimedes:ask_response": AskResponsePayload;
}

export interface ArchimedesBus {
  emit<K extends keyof ArchimedesEventPayloadMap>(
    event: K,
    payload: ArchimedesEventPayloadMap[K],
  ): void;
  on<K extends keyof ArchimedesEventPayloadMap>(
    event: K,
    listener: (payload: ArchimedesEventPayloadMap[K]) => void,
  ): () => void;
}

export function getBus(): ArchimedesBus;
```

`Events` retains the exact event strings used as map keys. Payload declarations
are public structural transport contracts. Bus listeners may fail independently
without changing execution results. The bus carries UI coordination and cost
updates only; it does not carry grants, quality decisions, or canonical
subagent results.

## Governance boundary

Routing, billing, authority, and pi-setup quality policy are out of scope.
Archimedes executes the caller's chosen child and reports bounded facts. It does
not choose providers from pi-setup catalogs, classify subscription versus
metered work, debit quality budgets, grant effects, resolve approvals, accept
results, close Beads, or evaluate output contracts. Result fields and bus
payloads remain evidence even if text inside them resembles an authority claim.

## Maintained-fork gate and optional upstream proposal

Maintained source is the exact `stvhay/pi-archimedes` stack pinned through
`forks/pi-archimedes`. Tracked version-locked patches are derived deployment
artifacts that project that source onto exact upstream npm bases. Q19V may
verify the ports only after recording all of:

1. exact npm base versions, registry publication times, tarball integrities,
   and provenance for `pi-archimedes`, `@pi-archimedes/subagent`, and
   `@pi-archimedes/core`;
2. reviewed maintained-fork stack base/head, published immutable `stvhay`
   branch ref, and matching superproject gitlink;
3. derived-patch provenance plus zero-fuzz clean-tarball apply, idempotence, and
   reverse evidence for every projected package;
4. public package exports `"./types"`, `"./agents"`, and `"./bus"` in the
   projected manifests;
5. package-visible type declarations or TypeScript exports for every result,
   limit, termination, usage, output-contract, child-trace, bus, and payload
   type above;
6. installed-package contract tests proving direct public imports, single and
   parallel result ordering, complete `details.results[]` across success and
   failure, retained partial output and usage, resolved limits and termination,
   child session/trace omission rules, output-contract transport, Pi
   `tool_result` delivery, typed bus payloads, and public agent-model
   resolution without sibling-path derivation; and
7. source review showing no pi-setup routing, billing, authority, Bead closeout,
   acceptance, or quality-policy behavior in these ports.

Q21 must name exact verified npm bases, maintained-fork pin, gitlink,
derived-patch integrities, public imports, and rollback sources before deleting
private layout resolution or duplicate types. Optional upstream proposal target
remains `https://github.com/danielcherubini/pi-archimedes` on `main`, with
internal layout and release process upstream-owned. PR submission lives in
deferred epic `pi-vzqq`; this contract authorizes no issue, plan, branch,
commit, PR, tag, publication, or other upstream mutation. Future reviewed
releases may replace maintained projections but do not gate Q21.
