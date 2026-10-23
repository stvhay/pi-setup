import { ExportResultCode } from "@opentelemetry/core";
import { JsonTraceSerializer } from "@opentelemetry/otlp-transformer";
import { LANGFUSE_SDK_VERSION } from "@langfuse/core";
import { gzipSync } from "node:zlib";
import { redactString, redactValue } from "./redaction.js";
import { getLimits } from "./limits.js";
const PREFIX = '{"resourceSpans":[';
const SUFFIX = "]}";
const MAX_RESPONSE_BYTES = 65536;
function sanitizeAttributes(attributes) {
  return attributes?.map((attribute) => {
    const name = String(attribute.key).split(".").at(-1);
    function clean(value) {
      if (typeof value.stringValue === "string") {
        let decoded = value.stringValue;
        let encoded = false;
        try {
          decoded = JSON.parse(value.stringValue);
          encoded = true;
        } catch {
        }
        const wrapped = redactValue({ [name]: decoded }, { maxDepth: getLimits().maxDepth + 1 });
        const redacted = wrapped[name];
        return { stringValue: encoded ? JSON.stringify(redacted) : String(redacted) };
      }
      if (value.arrayValue) return { arrayValue: { values: value.arrayValue.values.map(clean) } };
      if (value.kvlistValue) return { kvlistValue: { values: sanitizeAttributes(value.kvlistValue.values) } };
      return value;
    }
    return { ...attribute, value: clean(attribute.value) };
  });
}
function sanitizedResource(resource) {
  return {
    ...resource,
    resource: { ...resource.resource, attributes: sanitizeAttributes(resource.resource?.attributes) },
    scopeSpans: resource.scopeSpans.map((scope) => ({
      ...scope,
      scope: { ...scope.scope, attributes: sanitizeAttributes(scope.scope?.attributes) },
      spans: scope.spans.map((span) => ({
        ...span,
        name: redactString(span.name),
        attributes: sanitizeAttributes(span.attributes),
        ...span.status ? { status: { ...span.status, ...span.status.message ? { message: redactString(span.status.message) } : {} } } : {},
        events: span.events?.map((event) => ({ ...event, name: redactString(event.name), attributes: sanitizeAttributes(event.attributes) })),
        links: span.links?.map((link) => ({ ...link, attributes: sanitizeAttributes(link.attributes) }))
      }))
    }))
  };
}
class OtlpDelivery {
  constructor(options) {
    this.options = options;
    this.url = `${options.baseUrl.replace(/\/+$/, "")}/api/public/otel/v1/traces`;
    const endpoint = new URL(this.url);
    if (!["http:", "https:"].includes(endpoint.protocol) || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) {
      throw new Error("Langfuse OTLP endpoint must be an HTTP(S) base URL without credentials, query or fragment");
    }
    this.headers = {
      Authorization: `Basic ${Buffer.from(`${options.publicKey}:${options.secretKey}`).toString("base64")}`,
      "Content-Type": "application/json",
      "x-langfuse-sdk-name": "javascript",
      "x-langfuse-sdk-version": LANGFUSE_SDK_VERSION,
      "x-langfuse-public-key": options.publicKey,
      "x-langfuse-ingestion-version": "4"
    };
    const compression = [
      process.env.LANGFUSE_OTEL_COMPRESSION,
      process.env.OTEL_EXPORTER_OTLP_TRACES_COMPRESSION,
      process.env.OTEL_EXPORTER_OTLP_COMPRESSION
    ].map((value) => value?.trim().toLowerCase()).find((value) => value === "gzip" || value === "none") ?? "gzip";
    this.gzip = compression === "gzip";
  }
  options;
  url;
  headers;
  gzip;
  abortController = new AbortController();
  pending = /* @__PURE__ */ new Map();
  inFlight = /* @__PURE__ */ new Set();
  shutdownDeadline = Number.POSITIVE_INFINITY;
  closed = false;
  retrySuppressed = false;
  flushPromise;
  get signal() {
    return this.abortController.signal;
  }
  beginShutdown(deadline, signal) {
    this.shutdownDeadline = Math.min(this.shutdownDeadline, deadline);
    if (signal.aborted) this.abort();
    else signal.addEventListener("abort", () => this.abort(), { once: true });
  }
  abort() {
    this.closed = true;
    this.abortController.abort();
    this.pending.clear();
  }
  export(spans, callback) {
    if (this.closed) {
      callback({ code: ExportResultCode.FAILED, error: new Error("OTLP delivery is closed") });
      return;
    }
    let units;
    try {
      units = spans.map((span) => {
        const bytes = JsonTraceSerializer.serializeRequest([span]);
        if (!bytes) throw new Error("OTLP span serialization failed");
        const resource = JSON.parse(Buffer.from(bytes).toString()).resourceSpans[0];
        const context = span.spanContext();
        return { id: `${context.traceId}:${context.spanId}`, primary: JSON.stringify(resource), safe: JSON.stringify(sanitizedResource(resource)) };
      });
    } catch {
      callback({ code: ExportResultCode.FAILED, error: new Error("OTLP span serialization failed") });
      return;
    }
    const task = this.deliver(units).then(() => callback({ code: ExportResultCode.SUCCESS }), (error) => {
      this.options.onError(error);
      callback({ code: ExportResultCode.FAILED, error });
    });
    this.inFlight.add(task);
    void task.finally(() => this.inFlight.delete(task));
  }
  batches(units, ceiling, errors) {
    const batches = [];
    let selected = [];
    let bytes = Buffer.byteLength(PREFIX + SUFFIX);
    const finish = () => {
      if (selected.length) batches.push({ body: PREFIX + selected.map((unit) => unit.safe).join(",") + SUFFIX, units: selected });
      selected = [];
      bytes = Buffer.byteLength(PREFIX + SUFFIX);
    };
    for (const unit of units) {
      const size = Buffer.byteLength(unit.safe);
      if (size + Buffer.byteLength(PREFIX + SUFFIX) > ceiling) {
        this.pending.delete(unit.id);
        errors.push(new Error(`OTLP single span exceeds the ${ceiling} byte request ceiling`));
        continue;
      }
      if (bytes + size + (selected.length ? 1 : 0) > ceiling) finish();
      bytes += size + (selected.length ? 1 : 0);
      selected.push(unit);
    }
    finish();
    return batches;
  }
  enqueue(units) {
    if (this.closed || this.retrySuppressed) return;
    for (const unit of units) this.pending.set(unit.id, unit);
    if (!Number.isFinite(this.options.maxRetryTotalBytes)) return;
    const bytes = [...this.pending.values()].reduce(
      (sum, unit) => sum + Buffer.byteLength(unit.safe),
      Buffer.byteLength(PREFIX + SUFFIX) + Math.max(0, this.pending.size - 1)
    );
    if (bytes > this.options.maxRetryTotalBytes) {
      this.retrySuppressed = true;
      this.pending.clear();
      this.options.onError(new Error("OTLP replay exceeds the configured total fallback byte ceiling; replay suppressed"));
    }
  }
  async deliver(units) {
    const deadline = Math.min(Date.now() + this.options.timeoutMs, this.shutdownDeadline);
    const errors = [];
    const safe = new Map(units.map((unit) => [unit.id, unit.safe]));
    const retryIds = /* @__PURE__ */ new Set();
    const primaryBatches = this.batches(units.map((unit) => ({ id: unit.id, safe: unit.primary, retryAt: 0 })), this.options.maxBatchBytes, errors);
    for (const unit of units) unit.primary = "";
    for (const batch of primaryBatches) {
      const result = await this.send(batch.body, deadline);
      batch.body = "";
      for (const unit of batch.units) unit.safe = "";
      if (result.kind === "success") {
        for (const unit of batch.units) this.pending.delete(unit.id);
      } else if (result.kind === "retryable") {
        for (const unit of batch.units) retryIds.add(unit.id);
        this.enqueue(batch.units.map((unit) => ({ id: unit.id, safe: safe.get(unit.id), retryAt: result.retryAt ?? Date.now() + 1e3 })));
        if (this.retrySuppressed || this.closed) errors.push(result.error);
      } else errors.push(result.error);
    }
    await this.retry(retryIds, deadline, 5, errors);
    if (errors.length) throw errors[0];
  }
  async retry(ids, deadline, attempts, errors) {
    for (let attempt = 0; attempt < attempts; attempt++) {
      if ((this.closed || this.retrySuppressed) && ids.size) break;
      const pending = [...this.pending.values()].filter((unit) => ids.has(unit.id));
      if (!pending.length) return;
      const earliest = Math.min(...pending.map((unit) => unit.retryAt));
      const stopAt = Math.min(deadline, this.shutdownDeadline);
      if (this.closed || earliest >= stopAt || Date.now() >= stopAt) break;
      if (earliest > Date.now()) {
        await new Promise((resolve) => {
          const done = () => {
            clearTimeout(timer);
            this.abortController.signal.removeEventListener("abort", done);
            resolve();
          };
          const timer = setTimeout(done, earliest - Date.now());
          this.abortController.signal.addEventListener("abort", done, { once: true });
        });
      }
      if (this.closed || this.retrySuppressed) break;
      const ready = pending.filter((unit) => unit.retryAt <= Date.now());
      for (const batch of this.batches(ready, Math.min(this.options.maxBatchBytes, this.options.maxRetryBytes), errors)) {
        const result = await this.send(batch.body, deadline);
        if (result.kind === "retryable") {
          for (const unit of batch.units) unit.retryAt = result.retryAt ?? Date.now() + Math.min(5e3, 1e3 * 2 ** (attempt + 1));
        } else {
          for (const unit of batch.units) this.pending.delete(unit.id);
          if (result.kind === "terminal") errors.push(result.error);
        }
      }
    }
    if ((this.closed || this.retrySuppressed) && ids.size > 0 || [...this.pending.keys()].some((id) => ids.has(id))) {
      errors.push(new Error(this.retrySuppressed ? "OTLP replay suppressed by the configured total fallback byte ceiling" : "OTLP delivery failed within its retry/deadline budget"));
    }
  }
  async send(body, deadline) {
    const remaining = Math.min(deadline, this.shutdownDeadline) - Date.now();
    if (this.closed || remaining <= 0) return { kind: "retryable", error: new Error("OTLP delivery deadline expired") };
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, this.abortController.signal]);
    const timer = setTimeout(() => controller.abort(), remaining);
    let acknowledgedStatus = false;
    try {
      const bytes = Buffer.from(body);
      const response = await fetch(this.url, {
        method: "POST",
        redirect: "manual",
        signal,
        headers: { ...this.headers, ...this.gzip ? { "Content-Encoding": "gzip" } : {} },
        body: Uint8Array.from(this.gzip ? gzipSync(bytes) : bytes)
      });
      if (!response.ok) {
        const retryable = [429, 502, 503, 504].includes(response.status);
        const rawRetry = response.headers.get("retry-after");
        const seconds = rawRetry !== null && /^\d+$/.test(rawRetry) ? Number(rawRetry) : Number.NaN;
        const date = rawRetry !== null ? Date.parse(rawRetry) : Number.NaN;
        const retryAt = Number.isFinite(seconds) ? Date.now() + seconds * 1e3 : Number.isFinite(date) ? Math.max(Date.now(), date) : void 0;
        return { kind: retryable ? "retryable" : "terminal", error: new Error(`OTLP request failed with HTTP ${response.status}`), retryAt };
      }
      acknowledgedStatus = true;
      const chunks = [];
      let size = 0;
      if (response.body) for await (const chunk of response.body) {
        size += chunk.byteLength;
        if (size > MAX_RESPONSE_BYTES) throw new Error("oversized acknowledgement");
        chunks.push(chunk);
      }
      const text = Buffer.concat(chunks).toString();
      const reply = text ? JSON.parse(text) : {};
      if (!reply || typeof reply !== "object" || Array.isArray(reply)) throw new Error("invalid acknowledgement");
      if (reply.partialSuccess !== void 0) {
        const partial = reply.partialSuccess;
        if (!partial || typeof partial !== "object" || Array.isArray(partial)) throw new Error("invalid partial acknowledgement");
        const rejected = Object.hasOwn(partial, "rejectedSpans") ? partial.rejectedSpans : 0;
        if (!(typeof rejected === "number" && Number.isSafeInteger(rejected) || typeof rejected === "string" && /^\d+$/.test(rejected)) || Number(rejected) < 0) throw new Error("invalid rejected count");
        if (Number(rejected) > 0) return { kind: "terminal", error: new Error("OTLP partial rejection; rejected IDs unavailable, batch not replayed") };
      }
      return { kind: "success" };
    } catch {
      return { kind: acknowledgedStatus ? "terminal" : "retryable", error: new Error(acknowledgedStatus ? "OTLP acknowledgement was invalid, incomplete or timed out" : "OTLP request failed or timed out") };
    } finally {
      clearTimeout(timer);
      controller.abort();
    }
  }
  forceFlush() {
    if (this.flushPromise) return this.flushPromise;
    const work = (async () => {
      await Promise.allSettled([...this.inFlight]);
      const errors = [];
      await this.retry(new Set(this.pending.keys()), Math.min(Date.now() + this.options.timeoutMs, this.shutdownDeadline), 1, errors);
      if (errors.length) {
        this.options.onError(errors[0]);
        throw errors[0];
      }
    })();
    this.flushPromise = work;
    void work.finally(() => {
      this.flushPromise = void 0;
    }).catch(() => {
    });
    return work;
  }
  async shutdown() {
    if (this.closed) return;
    try {
      await this.forceFlush();
    } finally {
      this.abort();
    }
  }
}
export {
  OtlpDelivery
};
