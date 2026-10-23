import { applyCapturePolicy } from "./capture-policy.js";
import { getRuntime } from "./langfuse.js";
import { state } from "./state.js";
import { getCapturePolicy, shapePayload } from "./utils.js";
const MAX_EVIDENCE_LIMIT = 100;
const MAX_ANNOTATION_LIMIT = 99;
const REQUEST_TIMEOUT_MS = 1e4;
const UTC_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/;
function gap(scope, code) {
  return { scope, code };
}
function validateCaptureRequest(request) {
  if (!request || typeof request.name !== "string" || !request.name.trim()) {
    throw new TypeError("Observation capture name is required");
  }
  if (request.delivery !== "buffered" && request.delivery !== "flush") {
    throw new TypeError("Observation capture delivery is invalid");
  }
  if (request.level !== void 0 && request.level !== "DEFAULT" && request.level !== "ERROR") {
    throw new TypeError("Observation capture level is invalid");
  }
  if (request.sessionId !== void 0 && (typeof request.sessionId !== "string" || !request.sessionId.trim())) {
    throw new TypeError("Observation capture sessionId is invalid");
  }
  if (request.metadata !== void 0 && (typeof request.metadata !== "object" || request.metadata === null || Array.isArray(request.metadata))) {
    throw new TypeError("Observation capture metadata is invalid");
  }
}
async function waitForSignal(operation, signal) {
  if (!signal) return operation;
  if (signal.aborted) throw signal.reason ?? new DOMException("Aborted", "AbortError");
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
    signal.addEventListener("abort", abort, { once: true });
    operation.then(
      (value) => {
        signal.removeEventListener("abort", abort);
        resolve(value);
      },
      (error) => {
        signal.removeEventListener("abort", abort);
        reject(error);
      }
    );
  });
}
function createObservationCapturePort() {
  return {
    async capture(request) {
      validateCaptureRequest(request);
      if (request.signal?.aborted) {
        return {
          status: "unavailable",
          complete: false,
          gaps: [gap("export", "aborted")]
        };
      }
      if (!state.config) {
        return {
          status: "unavailable",
          complete: false,
          gaps: [gap("capture", "config-unavailable")]
        };
      }
      let captured;
      try {
        const metadata = request.metadata === void 0 ? void 0 : shapePayload(request.metadata, { redact: false });
        captured = applyCapturePolicy(
          {
            ...Object.hasOwn(request, "input") ? { input: shapePayload(request.input, { redact: false }) } : {},
            ...Object.hasOwn(request, "output") ? { output: shapePayload(request.output, { redact: false }) } : {},
            metadata
          },
          getCapturePolicy()
        );
      } catch {
        return {
          status: "unavailable",
          complete: false,
          gaps: [gap("redaction", "redaction-failed")]
        };
      }
      let runtime;
      try {
        runtime = await getRuntime();
      } catch {
        return {
          status: "unavailable",
          complete: false,
          gaps: [gap("capture", "runtime-unavailable")]
        };
      }
      let observation;
      try {
        observation = runtime.propagateAttributes(
          {
            sessionId: request.sessionId,
            traceName: request.name
          },
          () => runtime.startObservation(
            request.name,
            {
              input: captured.input,
              output: captured.output,
              metadata: captured.metadata,
              level: request.level
            },
            { asType: "span" }
          )
        );
      } catch {
        return {
          status: "unavailable",
          complete: false,
          gaps: [gap("capture", "start-failed")]
        };
      }
      const ids = {
        ...typeof observation.id === "string" ? { observationId: observation.id } : {},
        ...typeof observation.traceId === "string" ? { traceId: observation.traceId } : {}
      };
      try {
        observation.end();
      } catch {
        return {
          status: "partial",
          complete: false,
          ...ids,
          gaps: [gap("capture", "end-failed")]
        };
      }
      if (request.delivery === "flush") {
        const forceFlush = runtime.tracerProvider?.forceFlush ?? runtime.spanProcessor?.forceFlush;
        if (!forceFlush) {
          return {
            status: "partial",
            complete: false,
            ...ids,
            gaps: [gap("export", "flush-unavailable")]
          };
        }
        try {
          await waitForSignal(Promise.resolve(forceFlush.call(
            runtime.tracerProvider?.forceFlush ? runtime.tracerProvider : runtime.spanProcessor
          )), request.signal);
        } catch {
          return {
            status: "partial",
            complete: false,
            ...ids,
            gaps: [gap("export", request.signal?.aborted ? "aborted" : "flush-failed")]
          };
        }
      }
      return {
        status: "complete",
        complete: true,
        ...ids,
        gaps: []
      };
    }
  };
}
function positiveInteger(value, label) {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new TypeError(`${label} must be a positive integer`);
  }
  return value;
}
function appliedLimit(limit, maximum = MAX_EVIDENCE_LIMIT) {
  return Math.min(positiveInteger(limit, "Evidence limit"), maximum);
}
function pageLimit(pageSize, limit) {
  return Math.min(
    pageSize === void 0 ? MAX_EVIDENCE_LIMIT : positiveInteger(pageSize, "Evidence pageSize"),
    MAX_EVIDENCE_LIMIT,
    limit
  );
}
function validateInterval(fromTimestamp, toTimestamp) {
  const from = typeof fromTimestamp === "string" && UTC_TIMESTAMP.test(fromTimestamp) ? Date.parse(fromTimestamp) : Number.NaN;
  const to = typeof toTimestamp === "string" && UTC_TIMESTAMP.test(toTimestamp) ? Date.parse(toTimestamp) : Number.NaN;
  if (!Number.isFinite(from) || !Number.isFinite(to) || from >= to) {
    throw new TypeError("Evidence query requires an increasing UTC interval");
  }
}
function requiredIdentifier(value, label) {
  if (typeof value !== "string" || !value.trim() || value.length > 1e3) {
    throw new TypeError(`${label} is invalid`);
  }
  return value;
}
async function requestJson(scope, path, params, signal, config = state.config) {
  if (!config) return { requestGap: gap(scope, "config-unavailable") };
  if (signal?.aborted) return { requestGap: gap(scope, "aborted") };
  const timeoutSignal = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const requestSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;
  try {
    const url = new URL(path.replace(/^\/+/, ""), `${config.host.replace(/\/+$/, "")}/`);
    for (const [key, value] of Object.entries(params)) {
      if (value !== void 0) url.searchParams.set(key, String(value));
    }
    const encoded = Buffer.from([config.publicKey, config.secretKey].join(":")).toString("base64");
    const headers = new Headers();
    headers.set(["Author", "ization"].join(""), ["Bas", "ic ", encoded].join(""));
    const response = await fetch(url, {
      headers,
      signal: requestSignal
    });
    if (!response.ok) return { requestGap: gap(scope, "request-failed") };
    const payload = await response.json();
    return payload && typeof payload === "object" && !Array.isArray(payload) ? { payload } : { requestGap: gap(scope, "malformed-response") };
  } catch {
    if (signal?.aborted) return { requestGap: gap(scope, "aborted") };
    if (timeoutSignal.aborted) return { requestGap: gap(scope, "timeout") };
    return { requestGap: gap(scope, "request-failed") };
  }
}
function responseRows(payload) {
  const value = payload.data ?? payload.items;
  return Array.isArray(value) && value.every((item) => item && typeof item === "object" && !Array.isArray(item)) ? value : void 0;
}
function responseMeta(payload) {
  return payload.meta && typeof payload.meta === "object" && !Array.isArray(payload.meta) ? payload.meta : void 0;
}
function validTotal(value) {
  return Number.isSafeInteger(value) && value >= 0;
}
function decodeObservationIo(row) {
  const result = { ...row };
  for (const field of ["input", "output"]) {
    if (typeof result[field] === "string") {
      try {
        result[field] = JSON.parse(result[field]);
      } catch {
      }
    }
  }
  return result;
}
function validRootTime(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(value) || !Number.isFinite(Date.parse(value))) return false;
  const day = value.slice(0, 10);
  return Number(value.slice(0, 4)) > 0 && (/* @__PURE__ */ new Date(`${day}T00:00:00Z`)).toISOString().slice(0, 10) === day;
}
function groupTraceRows(rows, gaps) {
  const groups = /* @__PURE__ */ new Map();
  const note = (code) => {
    if (!gaps.some((item) => item.code === code)) gaps.push(gap("traces", code));
  };
  for (const row of rows) {
    if (typeof row.traceId !== "string" || !row.traceId) {
      note("trace-id-unavailable");
      continue;
    }
    const group = groups.get(row.traceId) ?? [];
    group.push(row);
    groups.set(row.traceId, group);
  }
  return [...groups].map(([id, observations]) => {
    const physicalRoots = observations.filter((row) => row.parentObservationId === null);
    const roots = physicalRoots.length ? physicalRoots : observations.filter((row) => row.isRootObservation === true);
    const root = roots.length === 1 ? roots[0] : void 0;
    if (!root) note(roots.length ? "ambiguous-root" : "root-unavailable");
    const context = root ? { ...root } : {};
    if (!root) {
      for (const field of ["traceName", "sessionId", "userId", "tags", "release", "environment", "version", "public", "bookmarked"]) {
        const values = observations.filter((row) => Object.hasOwn(row, field)).map((row) => row[field]);
        const distinct = new Set(values.map((value) => JSON.stringify(value)));
        if (distinct.size === 1) context[field] = values[0];
        else if (distinct.size > 1) note("conflicting-trace-context");
      }
    }
    const trace = { id };
    for (const field of ["sessionId", "userId", "tags", "release", "environment", "version", "public", "bookmarked"]) {
      if (Object.hasOwn(context, field)) trace[field] = context[field];
    }
    if (context.traceName !== void 0) trace.name = context.traceName;
    else if (root && Object.hasOwn(root, "name")) trace.name = root.name;
    if (root) {
      if (validRootTime(root.startTime)) trace.timestamp = root.startTime;
      else note("root-time-unavailable");
      for (const field of ["input", "output", "metadata"]) {
        if (Object.hasOwn(root, field)) trace[field] = root[field];
      }
    }
    return trace;
  });
}
async function readObservationEndpoint(scope, query, filters) {
  validateInterval(query.fromTimestamp, query.toTimestamp);
  const requestedLimit = positiveInteger(query.limit, "Evidence limit");
  const limit = appliedLimit(requestedLimit);
  const size = pageLimit(query.pageSize, limit);
  const rows = [];
  const gaps = [];
  const seenIds = /* @__PURE__ */ new Set();
  const seenCursors = /* @__PURE__ */ new Set();
  let cursor;
  let complete = false;
  let scanned = 0;
  const config = state.config ? { ...state.config } : null;
  while (scanned < limit) {
    const requestedPageLimit = Math.min(size, limit - scanned);
    const result = await requestJson(scope, "/api/public/v2/observations", {
      fromStartTime: query.fromTimestamp,
      toStartTime: query.toTimestamp,
      fields: scope === "traces" ? "core,basic,io,metadata,trace_context" : "core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context",
      ...filters,
      limit: requestedPageLimit,
      cursor
    }, query.signal, config);
    if (!result.payload) {
      gaps.push(result.requestGap);
      break;
    }
    const pageRows = responseRows(result.payload);
    const meta = responseMeta(result.payload);
    if (!pageRows || !meta) {
      gaps.push(gap(scope, "malformed-response"));
      break;
    }
    const overrun = pageRows.length > requestedPageLimit;
    const accepted = pageRows.slice(0, requestedPageLimit);
    scanned += accepted.length;
    let invalidRows = false;
    for (const row of accepted) {
      const identity = JSON.stringify([row.traceId, row.id]);
      if (typeof row.id !== "string" || !row.id) {
        gaps.push(gap(scope, "malformed-response"));
        invalidRows = true;
      } else if (seenIds.has(identity)) {
        gaps.push(gap(scope, "non-advancing-page"));
        invalidRows = true;
      } else if (filters.traceId && row.traceId !== filters.traceId) {
        gaps.push(gap(scope, "unexpected-trace"));
        invalidRows = true;
      } else {
        seenIds.add(identity);
        rows.push(decodeObservationIo(row));
      }
    }
    const next = meta.cursor;
    if (next !== void 0 && next !== null && (typeof next !== "string" || !next || next.length > 8192)) {
      gaps.push(gap(scope, "malformed-metadata"));
      cursor = void 0;
      break;
    }
    cursor = typeof next === "string" ? next : void 0;
    if (overrun) {
      gaps.push(gap(scope, "limit-reached"));
      cursor = void 0;
      break;
    }
    if (invalidRows) break;
    if (cursor && seenCursors.has(cursor)) {
      gaps.push(gap(scope, "non-advancing-cursor"));
      break;
    }
    if (!cursor) {
      complete = true;
      break;
    }
    seenCursors.add(cursor);
    if (pageRows.length === 0) {
      gaps.push(gap(scope, "incomplete-response"));
      break;
    }
    if (scanned >= limit) gaps.push(gap(scope, "limit-reached"));
  }
  const items = scope === "traces" ? groupTraceRows(rows, gaps) : rows;
  return {
    items,
    requestedLimit,
    appliedLimit: limit,
    ...cursor && !complete ? { nextCursor: cursor } : {},
    complete: complete && gaps.length === 0,
    gaps
  };
}
async function readScores(query) {
  validateInterval(query.fromTimestamp, query.toTimestamp);
  if (![query.traceId, query.sessionId, query.name].some((value) => typeof value === "string" && value.trim())) {
    throw new TypeError("Score evidence query requires a traceId, sessionId, or name filter");
  }
  const requestedLimit = positiveInteger(query.limit, "Evidence limit");
  const limit = appliedLimit(requestedLimit);
  const size = pageLimit(query.pageSize, limit);
  const items = [];
  const gaps = [];
  let cursor;
  let totalAvailable;
  let complete = false;
  const seenCursors = /* @__PURE__ */ new Set();
  const config = state.config ? { ...state.config } : null;
  while (items.length < limit) {
    const result = await requestJson("scores", "/api/public/v3/scores", {
      fromTimestamp: query.fromTimestamp,
      toTimestamp: query.toTimestamp,
      fields: "details,subject",
      traceId: query.traceId,
      sessionId: query.sessionId,
      name: query.name,
      limit: Math.min(size, limit - items.length),
      cursor
    }, query.signal, config);
    if (!result.payload) {
      gaps.push(result.requestGap);
      break;
    }
    const rows = responseRows(result.payload);
    const meta = responseMeta(result.payload);
    if (!rows || !meta) {
      gaps.push(gap("scores", "malformed-response"));
      break;
    }
    const remaining = limit - items.length;
    const overrun = rows.length > Math.min(size, remaining);
    items.push(...rows.slice(0, remaining));
    if (meta.totalItems !== void 0) {
      if (!validTotal(meta.totalItems) || meta.totalItems < items.length || totalAvailable !== void 0 && meta.totalItems !== totalAvailable) {
        gaps.push(gap("scores", "malformed-metadata"));
        break;
      }
      totalAvailable = meta.totalItems;
    }
    if (overrun) {
      gaps.push(gap("scores", "limit-reached"));
      break;
    }
    const next = meta.cursor;
    if (next !== void 0 && next !== null && (typeof next !== "string" || !next || seenCursors.has(next))) {
      gaps.push(gap("scores", "non-advancing-cursor"));
      break;
    }
    if (!next) {
      if (totalAvailable !== void 0 && items.length < totalAvailable) {
        gaps.push(gap("scores", "malformed-metadata"));
      } else {
        complete = true;
      }
      break;
    }
    cursor = next;
    seenCursors.add(cursor);
    if (rows.length === 0) {
      gaps.push(gap("scores", "incomplete-response"));
      break;
    }
    if (items.length >= limit) {
      gaps.push(gap("scores", "limit-reached"));
      break;
    }
  }
  if (!complete && items.length >= limit && !gaps.some((item) => item.code === "limit-reached")) {
    gaps.push(gap("scores", "limit-reached"));
  }
  return {
    items,
    requestedLimit,
    appliedLimit: limit,
    ...totalAvailable !== void 0 ? { totalAvailable } : {},
    ...cursor && !complete ? { nextCursor: cursor } : {},
    complete,
    gaps
  };
}
async function readAnnotations(query) {
  const queueId = requiredIdentifier(query.queueId, "Annotation queueId");
  const requestedLimit = positiveInteger(query.limit, "Annotation limit");
  const limit = appliedLimit(requestedLimit, MAX_ANNOTATION_LIMIT);
  const encodedQueue = encodeURIComponent(queueId);
  const gaps = [];
  const completeness = { queue: false, items: false, scores: false, scoreConfigs: false };
  let queue;
  let items = [];
  let scores = [];
  const scoreConfigs = [];
  const queueResult = await requestJson(
    "annotations",
    `/api/public/annotation-queues/${encodedQueue}`,
    {},
    query.signal
  );
  if (queueResult.payload) {
    queue = queueResult.payload;
    completeness.queue = true;
  } else {
    gaps.push(queueResult.requestGap);
  }
  const itemResult = await requestJson(
    "annotations",
    `/api/public/annotation-queues/${encodedQueue}/items`,
    { limit: limit + 1, page: 1 },
    query.signal
  );
  if (itemResult.payload) {
    const rows = responseRows(itemResult.payload);
    const meta = responseMeta(itemResult.payload);
    if (rows && meta && validTotal(meta.totalItems)) {
      items = rows.slice(0, limit);
      completeness.items = rows.length <= limit && meta.totalItems === rows.length;
      if (!completeness.items) gaps.push(gap("annotations", "items-limit-reached"));
    } else {
      gaps.push(gap("annotations", "items-malformed"));
    }
  } else {
    gaps.push(itemResult.requestGap);
  }
  const scoreResult = await requestJson("annotations", "/api/public/v3/scores", {
    fields: "details,subject,annotation",
    queueId,
    source: "ANNOTATION",
    limit: limit + 1
  }, query.signal);
  if (scoreResult.payload) {
    const rows = responseRows(scoreResult.payload);
    const meta = responseMeta(scoreResult.payload);
    if (rows && meta) {
      scores = rows.slice(0, limit);
      const total = meta.totalItems;
      const totalConsistent = total === void 0 || validTotal(total) && total === rows.length;
      completeness.scores = rows.length <= limit && !meta.cursor && totalConsistent;
      if (!completeness.scores) {
        gaps.push(gap(
          "annotations",
          rows.length > limit || meta.cursor ? "scores-limit-reached" : "scores-incomplete"
        ));
      }
    } else {
      gaps.push(gap("annotations", "scores-malformed"));
    }
  } else {
    gaps.push(scoreResult.requestGap);
  }
  const configIds = queue?.scoreConfigIds;
  if (configIds === void 0) {
    if (completeness.queue) gaps.push(gap("annotations", "score-configs-unavailable"));
  } else if (!Array.isArray(configIds) || !configIds.every((id) => typeof id === "string" && id && id.length <= 1e3)) {
    gaps.push(gap("annotations", "score-configs-malformed"));
  } else {
    completeness.scoreConfigs = configIds.length <= limit;
    if (!completeness.scoreConfigs) gaps.push(gap("annotations", "score-config-limit-reached"));
    for (const configId of configIds.slice(0, limit)) {
      const configResult = await requestJson(
        "annotations",
        `/api/public/score-configs/${encodeURIComponent(configId)}`,
        {},
        query.signal
      );
      if (configResult.payload) {
        scoreConfigs.push(configResult.payload);
      } else {
        completeness.scoreConfigs = false;
        gaps.push(configResult.requestGap);
      }
    }
  }
  const complete = Object.values(completeness).every(Boolean);
  return {
    ...queue ? { queue } : {},
    items,
    scores,
    scoreConfigs,
    requestedLimit,
    appliedLimit: limit,
    completeness,
    complete,
    gaps
  };
}
function createServiceEvidencePort() {
  return {
    traces(query) {
      return readObservationEndpoint("traces", query, {});
    },
    observations(query) {
      const traceId = requiredIdentifier(query.traceId, "Observation traceId");
      return readObservationEndpoint("observations", query, { traceId });
    },
    scores: readScores,
    annotations: readAnnotations
  };
}
export {
  createObservationCapturePort,
  createServiceEvidencePort
};
