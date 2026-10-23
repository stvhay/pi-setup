export type QualityPortGapScope = "capture" | "redaction" | "export" | "traces" | "observations" | "scores" | "annotations";
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
export declare function createObservationCapturePort(): ObservationCapturePort;
export declare function createServiceEvidencePort(): ServiceEvidencePort;
