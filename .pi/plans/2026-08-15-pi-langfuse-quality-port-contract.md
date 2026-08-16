# pi-langfuse Quality Port Contract

**Status:** Maintained-fork verified 2026-08-16; unreleased upstream
**Target:** `stvhay/pi-langfuse@94fa7f0c4410ce10da1f98c8fe4b798374c8df2e`, public package subpath `pi-langfuse/quality`
**Consumer:** pi-setup quality lifecycle and bounded private evidence review
**Scope:** Contract and Q18V provenance record; no upstream or runtime mutation

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

## Q18V maintained-fork verification record

Q18V verified this exact chain on 2026-08-16:

| Layer | Verified identity |
|---|---|
| npm base | `pi-langfuse@1.5.14`, published `2026-08-13T02:02:51.103Z`; registry [`gitHead`](https://registry.npmjs.org/pi-langfuse/1.5.14) `04d55a12556bdf4c4b8b208038198dc2fd8e571b`; integrity `sha512-zzQ40IMj7NrGrluzGAqB6zJ645MaqHfAMTdlsOK/fPlQywlTlgPb8Y/PyQc8asSkqWT55KMMDV+qNSKAG1zyTg==` |
| npm provenance | Registry [SLSA/publish attestations](https://registry.npmjs.org/-/npm/v1/attestations/pi-langfuse@1.5.14) bind package/version and upstream tag `v1.5.14` to base commit `04d55a12556bdf4c4b8b208038198dc2fd8e571b` |
| Maintained source | `stvhay/pi-langfuse` branch `vendor/pi-setup-1514`; immutable [commit `94fa7f0c4410ce10da1f98c8fe4b798374c8df2e`](https://github.com/stvhay/pi-langfuse/commit/94fa7f0c4410ce10da1f98c8fe4b798374c8df2e), whose only parent is npm base `04d55a12556bdf4c4b8b208038198dc2fd8e571b` |
| Quality candidate | `feat/quality-ports-1514` at `75c8a186e48038a51a95c02ef284256a5ed6cd46`, one commit on the same npm base and integrated into maintained head |
| Superproject pin | `forks/pi-langfuse` mode-`160000` gitlink `94fa7f0c4410ce10da1f98c8fe4b798374c8df2e`; `.gitmodules` names `https://github.com/stvhay/pi-langfuse.git` and `vendor/pi-setup-1514` |
| Derived deployment artifact | `patches/pi-packages/pi-langfuse-1.5.14.patch`, SHA-256 `27abc3cbf950ceca520dd21a2ab69ed3483bc05dea25c1c4495307d6fc2a90a5`, generated from installed production/package files at maintained head |

`scripts/check-vendor-pins.sh` verified the published branch resolves to the
superproject gitlink. `scripts/verify-pi-langfuse-package-patch.sh` downloads the
exact registry tarball, verifies npm integrity plus local fork/gitlink/patch
identities, applies with zero fuzz, rejects reapplication, byte-compares every
projected file with the maintained fork, reverses to a byte-identical clean
base, reapplies, and runs the maintained 15-test quality suite against the
installed projected package. Tests cover the public `"./quality"` export and
package-visible TypeScript declarations, capture redaction/lifecycle, buffered
and flush completion/gaps, bounded trace/observation/score/annotation reads,
unavailable service behavior, and source governance exclusions. The public
consumer import is `pi-langfuse/quality`.

Projection rollback source is the integrity-pinned registry tarball above:
reinstall `pi-langfuse@1.5.14` to restore the clean base. Consumer rollback must
also restore its pre-Q20 imports because the clean npm base lacks `./quality`;
the maintained projection can be restored from the exact gitlink and tracked
patch. No live Langfuse service canary is claimed.

## Maintained-fork gate and optional upstream proposal

Maintained source is the exact `stvhay/pi-langfuse` commit pinned through
`forks/pi-langfuse`. The tracked version-locked patch is a derived deployment
artifact that projects that source onto an exact upstream npm base. Q18V may
verify the port only after recording all of:

1. exact npm base version, registry publication time, tarball integrity, and
   provenance;
2. reviewed maintained-fork base/head, published immutable `stvhay` branch ref,
   and matching superproject gitlink;
3. derived-patch provenance plus zero-fuzz clean-tarball apply, idempotence, and
   reverse evidence;
4. public package export `"./quality"` in the projected package manifest;
5. package-visible type declarations or TypeScript exports for every interface
   and factory above;
6. installed-package contract tests proving capture redaction/lifecycle,
   buffered and flush completion/gaps, bounded trace/observation/score/
   annotation reads, and unavailable-service behavior; and
7. source review showing no authority, Bead closeout, acceptance, or pi-setup
   policy behavior in the port.

Q20 must name the exact verified npm base, maintained-fork pin, gitlink,
derived-patch integrity, public imports, and rollback source before deleting
private imports. Optional upstream proposal target remains
`https://github.com/gooyoung/pi-langfuse` on `main`, with source location and
release process upstream-owned. PR submission lives in deferred epic `pi-vzqq`;
this contract authorizes no issue, branch, commit, PR, tag, publication, or
other upstream mutation. A future reviewed release may replace the maintained
projection but does not gate Q20.
