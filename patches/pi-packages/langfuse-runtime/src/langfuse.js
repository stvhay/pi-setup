import { state } from "./state.js";
import { deliverScoreQueue } from "./score-delivery.js";
let runtime = null;
let registeredContextManager = null;
const activeSessions = /* @__PURE__ */ new Set();
let lastRuntimeError = null;
const DEFAULT_SHUTDOWN_STEP_TIMEOUT_MS = 2e3;
const DEFAULT_SCORE_SHUTDOWN_TIMEOUT_MS = 2e3;
const DEFAULT_LANGFUSE_REQUEST_TIMEOUT_SECONDS = 5;
const DEFAULT_SCORE_FLUSH_AT = 10;
const DEFAULT_SCORE_FLUSH_INTERVAL_MS = 1e3;
const MAX_SCORE_QUEUE_SIZE = 1e5;
const MAX_INGESTION_REQUEST_BYTES = 3e6;
const DEFAULT_MAX_INGESTION_BATCH_BYTES = MAX_INGESTION_REQUEST_BYTES;
const DEFAULT_MAX_RETRY_TOTAL_BYTES = Number.POSITIVE_INFINITY;
let shutdownStepTimeoutMs = DEFAULT_SHUTDOWN_STEP_TIMEOUT_MS;
function resolvePositiveEnvNumber(name, fallback, integer = false) {
  const parsed = Number(process.env[name]);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return integer ? Math.floor(parsed) : parsed;
}
function getScoreShutdownTimeoutMs() {
  return resolvePositiveEnvNumber(
    "PI_LANGFUSE_SCORE_SHUTDOWN_TIMEOUT",
    DEFAULT_SCORE_SHUTDOWN_TIMEOUT_MS / 1e3
  ) * 1e3;
}
function getMaxIngestionBatchBytes() {
  return Math.min(MAX_INGESTION_REQUEST_BYTES, resolvePositiveEnvNumber(
    "PI_LANGFUSE_MAX_INGESTION_BATCH_BYTES",
    DEFAULT_MAX_INGESTION_BATCH_BYTES,
    true
  ));
}
function getMaxRetryTotalBytes() {
  return resolvePositiveEnvNumber(
    "PI_LANGFUSE_MAX_FALLBACK_TOTAL_BYTES",
    DEFAULT_MAX_RETRY_TOTAL_BYTES,
    true
  );
}
function debugLog(message) {
  if (process.env.PI_LANGFUSE_DEBUG === "1" || process.env.PI_LANGFUSE_DEBUG === "true") {
    console.log(message);
  }
}
function ensureOtelContextManager(contextApi, AsyncHooksContextManager) {
  if (registeredContextManager) {
    return true;
  }
  const contextManager = new AsyncHooksContextManager().enable();
  if (contextApi.setGlobalContextManager(contextManager)) {
    registeredContextManager = contextManager;
    return true;
  }
  contextManager.disable();
  return false;
}
function rememberRuntimeError(scope, error) {
  lastRuntimeError = {
    scope,
    message: error instanceof Error ? error.message : String(error),
    timestamp: /* @__PURE__ */ new Date()
  };
}
function getLastRuntimeError() {
  return lastRuntimeError;
}
function isAbortError(error) {
  return error instanceof Error && error.name === "AbortError";
}
async function withShutdownDeadline(label, startOperation, deadline, signal) {
  const remainingMs = deadline - Date.now();
  if (remainingMs <= 0) {
    debugLog(`\u{1F4CA} Langfuse: Skipped ${label}; shutdown deadline elapsed`);
    return void 0;
  }
  const operation = startOperation();
  if (!operation) {
    return void 0;
  }
  let timeout;
  try {
    return await Promise.race([
      operation,
      new Promise((resolve) => {
        timeout = setTimeout(() => {
          debugLog(`\u{1F4CA} Langfuse: ${label} timed out; shutdown deadline elapsed`);
          resolve(void 0);
        }, remainingMs);
      })
    ]);
  } catch (error) {
    if (signal?.aborted && isAbortError(error)) {
      debugLog(`\u{1F4CA} Langfuse: ${label} aborted; shutdown deadline elapsed`);
      return void 0;
    }
    throw error;
  } finally {
    if (timeout) {
      clearTimeout(timeout);
    }
  }
}
async function runShutdownStep(label, startOperation, deadline, signal) {
  try {
    return await withShutdownDeadline(label, startOperation, deadline, signal);
  } catch (error) {
    rememberRuntimeError(`runtime shutdown: ${label}`, error);
    console.warn(`\u{1F4CA} Langfuse: Failed ${label} during shutdown`, error);
    return void 0;
  }
}
function getRuntimeConfig(rt) {
  return rt.runtimeConfig ?? state.config;
}
function scoreHeaders(rt) {
  const config = getRuntimeConfig(rt);
  if (!config) {
    throw new Error("Langfuse runtime config is unavailable");
  }
  const auth = Buffer.from(`${config.publicKey}:${config.secretKey}`).toString("base64");
  return {
    Authorization: `Basic ${auth}`,
    "Content-Type": "application/json",
    "x-langfuse-sdk-name": "pi-langfuse",
    "x-langfuse-sdk-version": "1.7.0",
    "x-langfuse-public-key": config.publicKey
  };
}
async function flushPendingScores(rt, signal) {
  if (!rt.pendingScores?.length) return;
  const config = getRuntimeConfig(rt);
  if (!config) throw new Error("Langfuse runtime config is unavailable");
  await deliverScoreQueue(rt.pendingScores, {
    url: `${config.host.replace(/\/$/, "")}/api/public/scores`,
    headers: scoreHeaders(rt),
    maxBytes: getMaxIngestionBatchBytes(),
    signal,
    retry: rt,
    onError(error) {
      rememberRuntimeError("score delivery", error);
      console.warn("\u{1F4CA} Langfuse: Score delivery failed", error);
    }
  });
}
function clearScoreFlushTimer(rt) {
  if (rt.scoreFlushTimer) {
    clearTimeout(rt.scoreFlushTimer);
    rt.scoreFlushTimer = void 0;
  }
}
function scheduleScoreFlush(rt) {
  if (rt.scoreFlushStopped || rt.scoreFlushTimer || rt.scoreFlushPromise || !rt.pendingScores?.length) {
    return;
  }
  rt.scoreFlushTimer = setTimeout(() => {
    rt.scoreFlushTimer = void 0;
    void startScoreFlush(rt);
  }, Math.min(2147483647, Math.max(
    rt.scoreFlushIntervalMs ?? DEFAULT_SCORE_FLUSH_INTERVAL_MS,
    (rt.scoreRetryNotBefore ?? 0) - Date.now()
  )));
  rt.scoreFlushTimer.unref?.();
}
function startScoreFlush(rt) {
  if (rt.scoreFlushPromise) {
    return rt.scoreFlushPromise;
  }
  clearScoreFlushTimer(rt);
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(new DOMException("Langfuse score request timed out", "AbortError")),
    rt.scoreRequestTimeoutMs ?? DEFAULT_LANGFUSE_REQUEST_TIMEOUT_SECONDS * 1e3
  );
  timeout.unref?.();
  rt.scoreFlushController = controller;
  const promise = flushPendingScores(rt, controller.signal).finally(() => {
    clearTimeout(timeout);
    if (rt.scoreFlushPromise === promise) {
      rt.scoreFlushPromise = void 0;
    }
    if (rt.scoreFlushController === controller) {
      rt.scoreFlushController = void 0;
    }
    scheduleScoreFlush(rt);
  });
  rt.scoreFlushPromise = promise;
  return promise;
}
function stopScoreFlush(rt) {
  rt.scoreFlushStopped = true;
  clearScoreFlushTimer(rt);
  rt.scoreFlushController?.abort(
    new DOMException("Langfuse score flushing stopped", "AbortError")
  );
}
const PROPAGATED_STRING_ATTRIBUTES = {
  sessionId: "session.id",
  userId: "user.id",
  traceName: "langfuse.trace.name",
  version: "langfuse.version"
};
const OTEL_TRACE_TAGS_ATTRIBUTE = "langfuse.trace.tags";
const OTEL_TRACE_METADATA_PREFIX = "langfuse.trace.metadata.";
function readPropagatedAttributes(observation) {
  const attributes = observation?.otelSpan?.attributes ?? {};
  const propagated = {};
  for (const [key, attribute] of Object.entries(PROPAGATED_STRING_ATTRIBUTES)) {
    const value = attributes[attribute];
    if (typeof value === "string" && value) {
      propagated[key] = value;
    }
  }
  const tags = attributes[OTEL_TRACE_TAGS_ATTRIBUTE];
  if (Array.isArray(tags)) {
    const validTags = tags.filter((tag) => typeof tag === "string" && tag.length > 0);
    if (validTags.length > 0) {
      propagated.tags = validTags;
    }
  }
  const metadata = /* @__PURE__ */ Object.create(null);
  for (const [key, value] of Object.entries(attributes)) {
    if (key.startsWith(OTEL_TRACE_METADATA_PREFIX) && typeof value === "string") {
      try {
        metadata[key.slice(OTEL_TRACE_METADATA_PREFIX.length)] = JSON.parse(value);
      } catch {
      }
    }
  }
  if (Object.keys(metadata).length > 0) {
    propagated.metadata = metadata;
  }
  return propagated;
}
function assertRuntimeActive(owner) {
  if (runtime !== owner || owner.otelDelivery?.signal.aborted) {
    throw new Error("Cannot create observations on a stopped runtime");
  }
}
function wrapObservation(owner, observation, root = observation) {
  return {
    ...observation,
    id: observation.id,
    traceId: observation.traceId,
    update(updateBody) {
      const updated = observation.update(updateBody);
      return updated === observation ? this : updated;
    },
    end(endBody) {
      if (endBody && typeof endBody === "object") observation.update(endBody);
      return observation.end();
    },
    startObservation(childName, childBody, options) {
      assertRuntimeActive(owner);
      const inherited = readPropagatedAttributes(observation);
      const fallbackSessionId = state.currentSessionId?.slice(0, 200);
      if (!inherited.sessionId && fallbackSessionId) inherited.sessionId = fallbackSessionId;
      const createChild = () => observation.startObservation(childName, childBody, options);
      const createInheritingChild = Object.keys(inherited).length > 0 ? () => owner.propagateAttributes(inherited, createChild) : createChild;
      const child = owner.withRootContext ? owner.withRootContext(createInheritingChild) : createInheritingChild();
      return wrapObservation(owner, child, root);
    },
    // V4 trace IO belongs to the logical root observation, including when the
    // compatibility alias is called on a child. Never invent a separate trace.
    setTraceIO(traceBody) {
      return root.update(traceBody);
    }
  };
}
async function getRuntime() {
  if (!state.config) {
    throw new Error("Langfuse config is not set");
  }
  const sessionId = state.currentSessionId;
  if (sessionId) {
    activeSessions.add(sessionId);
  }
  if (!runtime) {
    const [
      { TracerProvider },
      resources,
      { context, ROOT_CONTEXT },
      { AsyncLocalStorageContextManager },
      { LangfuseSpanProcessor },
      tracing,
      { OtlpDelivery }
    ] = await Promise.all([
      import("@opentelemetry/sdk-trace"),
      import("@opentelemetry/resources"),
      import("@opentelemetry/api"),
      import("@opentelemetry/context-async-hooks"),
      import("@langfuse/otel"),
      import("@langfuse/tracing"),
      import("./otlp-delivery.js")
    ]);
    if (runtime) return runtime;
    try {
      ensureOtelContextManager(context, AsyncLocalStorageContextManager);
      const scoreFlushAt = resolvePositiveEnvNumber("LANGFUSE_FLUSH_AT", DEFAULT_SCORE_FLUSH_AT, true);
      const scoreFlushIntervalMs = resolvePositiveEnvNumber("LANGFUSE_FLUSH_INTERVAL", DEFAULT_SCORE_FLUSH_INTERVAL_MS / 1e3) * 1e3;
      const scoreRequestTimeoutMs = resolvePositiveEnvNumber("LANGFUSE_TIMEOUT", DEFAULT_LANGFUSE_REQUEST_TIMEOUT_SECONDS) * 1e3;
      const otelDelivery = new OtlpDelivery({
        baseUrl: state.config.host,
        publicKey: state.config.publicKey,
        secretKey: state.config.secretKey,
        timeoutMs: scoreRequestTimeoutMs,
        maxBatchBytes: Math.min(64 * 1024 * 1024, resolvePositiveEnvNumber("LANGFUSE_OTEL_MAX_BATCH_SIZE_BYTES", 64 * 1024 * 1024, true)),
        maxRetryBytes: getMaxIngestionBatchBytes(),
        maxRetryTotalBytes: getMaxRetryTotalBytes(),
        onError: (error) => rememberRuntimeError("OTLP delivery", error)
      });
      const spanProcessor = new LangfuseSpanProcessor({
        exporter: otelDelivery,
        mediaUploadSignal: otelDelivery.signal,
        publicKey: state.config.publicKey,
        secretKey: state.config.secretKey,
        baseUrl: state.config.host
      });
      const resource = resources.defaultResource().merge(
        resources.detectResources({ detectors: [resources.envDetector] })
      );
      const tracerProvider = new TracerProvider({ resource, spanProcessors: [spanProcessor] });
      tracing.setLangfuseTracerProvider(tracerProvider);
      const owner = {
        startObservation: ((name, body, options) => {
          assertRuntimeActive(owner);
          const observation = tracing.startObservation(name, body, options);
          return wrapObservation(owner, observation);
        }),
        propagateAttributes: tracing.propagateAttributes,
        withRootContext: (fn) => context.with(ROOT_CONTEXT, fn),
        spanProcessor,
        tracerProvider,
        otelDelivery,
        clearTracerProvider: () => tracing.setLangfuseTracerProvider(null),
        pendingScores: [],
        scoreFlushAt,
        scoreFlushIntervalMs,
        scoreRequestTimeoutMs,
        scoreFlushStopped: false,
        runtimeConfig: {
          publicKey: state.config.publicKey,
          secretKey: state.config.secretKey,
          host: state.config.host
        }
      };
      runtime = owner;
      lastRuntimeError = null;
    } catch (e) {
      rememberRuntimeError("runtime init", e);
      throw e;
    }
  }
  return runtime;
}
function doShutdownRuntime() {
  return (async () => {
    if (!runtime) {
      return;
    }
    const rt = runtime;
    runtime = null;
    const deadline = Date.now() + shutdownStepTimeoutMs;
    const controller = new AbortController();
    const abortTimeout = setTimeout(() => controller.abort(), shutdownStepTimeoutMs);
    rt.otelDelivery?.beginShutdown(deadline, controller.signal);
    const scoreController = new AbortController();
    const scoreShutdownTimeoutMs = Math.min(getScoreShutdownTimeoutMs(), shutdownStepTimeoutMs);
    const scoreDeadline = Math.min(deadline, Date.now() + scoreShutdownTimeoutMs);
    const scoreAbortTimeout = setTimeout(
      () => scoreController.abort(),
      scoreShutdownTimeoutMs
    );
    scoreAbortTimeout.unref?.();
    stopScoreFlush(rt);
    try {
      await runShutdownStep(
        "Active score flush",
        () => rt.scoreFlushPromise,
        deadline
      );
      await runShutdownStep(
        "Pending score flush",
        () => flushPendingScores(rt, scoreController.signal),
        scoreDeadline,
        scoreController.signal
      );
      await runShutdownStep("OTel force flush", () => rt.tracerProvider?.forceFlush?.(), deadline);
      await runShutdownStep("OTel tracer shutdown", () => rt.tracerProvider?.shutdown?.(), deadline);
    } finally {
      rt.otelDelivery?.abort();
      controller.abort();
      clearTimeout(abortTimeout);
      clearTimeout(scoreAbortTimeout);
      scoreController.abort();
      clearScoreFlushTimer(rt);
      rt.scoreFlushController?.abort();
      rt.scoreFlushController = void 0;
      rt.scoreFlushPromise = void 0;
      if (!runtime) {
        rt.clearTracerProvider?.();
      }
    }
  })();
}
async function shutdownRuntime(sessionId) {
  const sid = sessionId ?? state.currentSessionId;
  if (sid) {
    activeSessions.delete(sid);
  }
  if (activeSessions.size > 0) {
    return;
  }
  await doShutdownRuntime();
}
async function forceShutdownRuntime() {
  activeSessions.clear();
  await doShutdownRuntime();
}
function __setRuntimeForTest(rt, timeoutMs = DEFAULT_SHUTDOWN_STEP_TIMEOUT_MS) {
  if (runtime && runtime !== rt) {
    stopScoreFlush(runtime);
  }
  runtime = rt;
  if (rt) {
    rt.scoreFlushStopped = false;
  }
  shutdownStepTimeoutMs = timeoutMs;
  activeSessions.clear();
}
async function sendScore(name, value, options = {}) {
  try {
    const rt = await getRuntime();
    const score = {
      name,
      value,
      dataType: name === "session_had_errors" || name === "tool_is_error" ? "BOOLEAN" : "NUMERIC",
      traceId: options.traceId,
      observationId: options.observationId,
      sessionId: options.traceId ? void 0 : state.currentSessionId || void 0,
      ...process.env.LANGFUSE_TRACING_ENVIRONMENT ? { environment: process.env.LANGFUSE_TRACING_ENVIRONMENT } : {}
    };
    if (!rt.pendingScores) {
      return;
    }
    if (rt.pendingScores.length >= MAX_SCORE_QUEUE_SIZE) {
      const error = new Error(
        `Langfuse score queue is full (${MAX_SCORE_QUEUE_SIZE}); dropping score`
      );
      rememberRuntimeError("score queue", error);
      console.warn(`\u{1F4CA} Langfuse: ${error.message}`);
      return;
    }
    rt.pendingScores.push(score);
    if (rt.pendingScores.length >= (rt.scoreFlushAt ?? DEFAULT_SCORE_FLUSH_AT)) {
      void startScoreFlush(rt);
    } else {
      scheduleScoreFlush(rt);
    }
  } catch (e) {
    rememberRuntimeError(`score ${name}`, e);
    console.warn(`\u{1F4CA} Langfuse: Failed to send score ${name}`, e);
  }
}
export {
  __setRuntimeForTest,
  ensureOtelContextManager,
  forceShutdownRuntime,
  getLastRuntimeError,
  getRuntime,
  sendScore,
  shutdownRuntime
};
