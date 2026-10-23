import { randomUUID } from "node:crypto";
const MAX_ACK_BYTES = 65536;
const MAX_BATCH_COUNT = 100;
const snapshots = /* @__PURE__ */ new WeakMap();
class ScoreDeliveryError extends Error {
  constructor(message, retryable = false) {
    super(message);
    this.retryable = retryable;
  }
  retryable;
}
function snapshot(score) {
  const saved = snapshots.get(score);
  if (saved) return saved;
  if (!Number.isFinite(score.value) || typeof score.name !== "string" || !score.name) {
    throw new ScoreDeliveryError("Score name or value is invalid");
  }
  score.id ??= randomUUID();
  score.timestamp ??= (/* @__PURE__ */ new Date()).toISOString();
  const json = JSON.stringify({
    id: score.id,
    timestamp: score.timestamp,
    name: score.name,
    value: score.value,
    dataType: score.dataType,
    traceId: score.traceId,
    observationId: score.observationId,
    sessionId: score.sessionId,
    environment: score.environment,
    source: "API"
  });
  const result = { json, bytes: Buffer.byteLength(json) };
  snapshots.set(score, result);
  return result;
}
function retryAt(value) {
  if (!value?.trim()) return 0;
  const seconds = Number(value);
  const result = Number.isFinite(seconds) && seconds >= 0 ? Date.now() + seconds * 1e3 : Date.parse(value);
  return Number.isFinite(result) ? Math.max(0, result) : 0;
}
async function acknowledgement(response, count) {
  const reader = response.body?.getReader();
  if (!reader) throw new ScoreDeliveryError("Score acknowledgement is missing");
  const chunks = [];
  let bytes = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      bytes += chunk.value.byteLength;
      if (bytes > MAX_ACK_BYTES) {
        await reader.cancel();
        throw new ScoreDeliveryError("Score acknowledgement exceeds the byte ceiling");
      }
      chunks.push(chunk.value);
    }
  } finally {
    reader.releaseLock();
  }
  let body;
  try {
    body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new ScoreDeliveryError("Score acknowledgement is invalid JSON");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new ScoreDeliveryError("Score acknowledgement is not an object");
  }
  if (["accepted", "rejected", "errors"].some((key) => Object.hasOwn(body, key))) {
    if (!Number.isInteger(body.accepted) || body.accepted !== count || body.rejected !== 0 || !Array.isArray(body.errors) || body.errors.length !== 0) {
      throw new ScoreDeliveryError("Score batch was rejected or its acknowledgement is invalid");
    }
  } else if (response.status === 207 || body.message !== "Accepted") {
    throw new ScoreDeliveryError("Score acknowledgement is invalid");
  }
}
async function deliverScoreQueue(queue, options) {
  if ((options.retry.scoreRetryNotBefore ?? 0) > Date.now()) return;
  const maxBytes = Math.min(3e6, options.maxBytes);
  while (queue.length > 0) {
    if (options.signal.aborted) {
      options.onError(new Error("Score delivery cancelled with pending scores"));
      return;
    }
    const batch = [];
    let bytes = 2;
    for (const score of queue.slice(0, MAX_BATCH_COUNT)) {
      let entry;
      try {
        entry = snapshot(score);
      } catch {
        if (batch.length > 0) break;
        queue.shift();
        options.onError(new Error("Score cannot be serialized for delivery"));
        continue;
      }
      if (entry.bytes + 2 > maxBytes) {
        if (batch.length > 0) break;
        queue.shift();
        options.onError(new Error("Score exceeds the request byte ceiling"));
        continue;
      }
      if (bytes + entry.bytes + (batch.length ? 1 : 0) > maxBytes) break;
      bytes += entry.bytes + (batch.length ? 1 : 0);
      batch.push(entry.json);
    }
    if (!batch.length) continue;
    let partialAcknowledgement = false;
    try {
      const response = await fetch(options.url, {
        method: "POST",
        headers: options.headers,
        body: `[${batch.join(",")}]`,
        signal: options.signal
      });
      partialAcknowledgement = response.status === 207;
      if (!response.ok) {
        await response.body?.cancel();
        const retryable = [408, 425, 429].includes(response.status) || response.status >= 500;
        if (retryable) options.retry.scoreRetryNotBefore = retryAt(response.headers.get("Retry-After"));
        throw new ScoreDeliveryError(`Score request failed with HTTP ${response.status}`, retryable);
      }
      await acknowledgement(response, batch.length);
      queue.splice(0, batch.length);
      options.retry.scoreRetryNotBefore = 0;
    } catch (error) {
      if (partialAcknowledgement || error instanceof ScoreDeliveryError && !error.retryable) {
        queue.splice(0, batch.length);
        options.onError(error instanceof ScoreDeliveryError ? error : new Error("Score partial acknowledgement was interrupted"));
        continue;
      }
      options.onError(new Error(options.signal.aborted ? "Score delivery cancelled with pending scores" : error instanceof ScoreDeliveryError ? error.message : "Score request failed during transport"));
      return;
    }
  }
}
export {
  deliverScoreQueue
};
