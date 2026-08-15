# pi-langfuse Quality Port Contract

**Status:** Proposed; unreleased
**Target:** `gooyoung/pi-langfuse` `main`, public package subpath `pi-langfuse/quality`
**Consumer:** pi-setup quality lifecycle and bounded private evidence review
**Scope:** Contract proposal only; no upstream or runtime mutation

## Proven need

pi-setup currently imports `src/langfuse.js`, `src/redaction.js`, and
`src/utils.js` to write one bounded `interactive-result` observation. Its
private review client separately reads bounded traces, observations, scores,
annotation queue items, annotation scores, and score configs. Public ports must
replace those package-private imports and preserve explicit incomplete or
unavailable evidence.

## Public package export

A satisfying release exposes this subpath without requiring callers to resolve
package files:

```json
{
  "exports": {
    ".": "./index.ts",
    "./quality": "./src/quality.ts"
  }
}
```

`"./quality"` publicly exports the types below plus
`createObservationCapturePort` and `createServiceEvidencePort`. Published type
declarations must expose the same names and fields.

## Observation capture port

```ts
export type QualityPortGapScope =
  | "capture"
  | "redaction"
  | "export"
  | "traces"
  | "observations"
  | "scores"
  | "annotations";

export interface QualityPortGap {
  scope: QualityPortGapScope;
  code: string;
}

export interface ObservationCaptureRequest {
  name: string;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  level?: "DEFAULT" | "ERROR";
  sessionId?: string;
  delivery: "buffered" | "flush";
  signal?: AbortSignal;
}

export interface ObservationCaptureResult {
  status: "complete" | "partial" | "unavailable";
  complete: boolean;
  observationId?: string;
  traceId?: string;
  gaps: readonly QualityPortGap[];
}

export interface ObservationCapturePort {
  capture(request: ObservationCaptureRequest): Promise<ObservationCaptureResult>;
}

export function createObservationCapturePort(): ObservationCapturePort;
```

pi-langfuse owns, in order:

1. capture policy and redaction of input, output, and metadata;
2. observation lifecycle, including start and exactly one end attempt;
3. session propagation when `sessionId` is supplied;
4. export and requested flush within the caller's abort signal; and
5. completion and gaps in the returned result.

`complete: true` means the requested delivery level completed: the observation
ended and was accepted by the exporter for `buffered`, or the requested flush
also completed for `flush`. It does not prove remote query visibility or task
acceptance. Partial or unavailable work returns `complete: false` and at least
one stable gap code. Expected package/config/service/export unavailability is a
result, not an uncaught exception. Invalid request shape or bounds may reject.
The result never returns captured bodies or credentials.

Caller owns only request selection, its pre-call size ceiling, and handling the
result as optional evidence. Caller must not import runtime, redaction, capture
policy, or utility modules from package-private paths.

## Service evidence port

```ts
export type LangfuseEvidenceRow = Readonly<Record<string, unknown>>;

export interface BoundedEvidencePage<T = LangfuseEvidenceRow> {
  items: readonly T[];
  requestedLimit: number;
  appliedLimit: number;
  totalAvailable?: number;
  nextCursor?: string;
  complete: boolean;
  gaps: readonly QualityPortGap[];
}

export interface TraceEvidenceQuery {
  fromTimestamp: string;
  toTimestamp: string;
  limit: number;
  pageSize?: number;
  signal?: AbortSignal;
}

export interface ObservationEvidenceQuery {
  fromTimestamp: string;
  toTimestamp: string;
  traceId: string;
  limit: number;
  pageSize?: number;
  signal?: AbortSignal;
}

export interface ScoreEvidenceQuery {
  fromTimestamp: string;
  toTimestamp: string;
  limit: number;
  pageSize?: number;
  traceId?: string;
  sessionId?: string;
  name?: string;
  signal?: AbortSignal;
}

export interface AnnotationEvidenceQuery {
  queueId: string;
  limit: number;
  signal?: AbortSignal;
}

export interface AnnotationEvidenceResult {
  queue?: LangfuseEvidenceRow;
  items: readonly LangfuseEvidenceRow[];
  scores: readonly LangfuseEvidenceRow[];
  scoreConfigs: readonly LangfuseEvidenceRow[];
  requestedLimit: number;
  appliedLimit: number;
  completeness: {
    queue: boolean;
    items: boolean;
    scores: boolean;
    scoreConfigs: boolean;
  };
  complete: boolean;
  gaps: readonly QualityPortGap[];
}

export interface ServiceEvidencePort {
  traces(query: TraceEvidenceQuery): Promise<BoundedEvidencePage>;
  observations(query: ObservationEvidenceQuery): Promise<BoundedEvidencePage>;
  scores(query: ScoreEvidenceQuery): Promise<BoundedEvidencePage>;
  annotations(query: AnnotationEvidenceQuery): Promise<AnnotationEvidenceResult>;
}

export function createServiceEvidencePort(): ServiceEvidencePort;
```

Every query requires a positive finite `limit`; time-series queries require a
non-empty UTC interval with `fromTimestamp < toTimestamp`. Observation queries
require one trace. Score queries require at least one of `traceId`, `sessionId`,
or `name`. Annotation queries cover one annotation queue and bound queue items,
annotation scores, and score configs by the same limit. Internal page-size caps
may be lower than requested and must be reported as `appliedLimit`.

The service port stops at the applied limit or service end. It returns no more
than `appliedLimit` rows in any collection. `complete: true` requires positive
end-of-results evidence from stable total/page/cursor metadata. A limit,
non-advancing page, malformed metadata, abort, timeout, unsupported endpoint, or
service failure yields `complete: false` plus a scoped gap; unavailable
collections are empty, never inferred successful. Annotation `complete` is true
only when all four component completeness fields are true.

Rows remain private telemetry evidence. The port reads only: it does not write
scores, annotations, Beads, files, or policy state. Credentials stay inside the
configured pi-langfuse adapter and never enter requests or results.

## Governance boundary

Authorization, Bead closeout, and pi-setup quality policy are out of scope.
These ports neither accept nor return grants, approvals, allowed effects,
quality modes, acceptance decisions, or closeout state. Observation metadata
and service rows are evidence only, even if their stored text resembles an
authority claim. Ports cannot authorize mutation, accept a result, close work,
or override deterministic local state.

## Upstream proposal and release gate

Proposal target is `https://github.com/gooyoung/pi-langfuse`, base branch
`main`, with the new public package export `"./quality"`. Suggested source
location is `src/quality.ts`; exact internal layout remains upstream-owned. No
issue, branch, commit, PR, tag, package publication, or other upstream mutation
is authorized by this contract.

No released package currently satisfies this contract. Q18R may mark the port
released only after recording all of:

1. exact npm version and registry publication time;
2. npm tarball integrity and provenance evidence;
3. reviewed source commit and immutable tag resolving to that commit;
4. public package export `"./quality"` in the published package manifest;
5. published type declarations for every interface and factory above;
6. installed-package contract tests proving capture redaction/lifecycle,
   buffered and flush completion/gaps, bounded trace/observation/score/
   annotation reads, and unavailable-service behavior; and
7. source review showing no authority, Bead closeout, acceptance, or pi-setup
   policy behavior in the port.

A fork branch, draft PR, or local package patch is not release evidence. Q20
must name the exact verified version and public imports before deleting private
imports or the version-locked projection.
