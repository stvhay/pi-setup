import { state } from "../state.js";
import { getRuntime } from "../langfuse.js";
import { startChildObservation } from "../observation.js";
import {
  getRequestKey,
  getProviderPayload,
  shapePayload,
  extractResponseMetadata,
  getMessageFromEvent,
  extractAssistantOutput,
  extractUsage,
  extractCostDetails,
  getCapturePolicy,
  extractModelParameters,
  extractCacheMetrics,
  inferToolUpdateTransport,
  extractModelIdentity
} from "../utils.js";
import { applyCapturePolicy } from "../capture-policy.js";
import { redactString } from "../redaction.js";
function getOpenGeneration() {
  if (state.isTracingDisabled || !state.agentState) {
    return void 0;
  }
  for (let i = state.agentState.generationOrder.length - 1; i >= 0; i--) {
    const key = state.agentState.generationOrder[i];
    const genState = state.agentState.activeGenerations.get(key);
    if (genState && !genState.ended) {
      return genState;
    }
  }
  return void 0;
}
async function startGeneration(event, selectedModel) {
  if (state.isTracingDisabled || !state.agentState?.root) {
    return;
  }
  try {
    const key = getRequestKey(event, `generation-${++state.agentState.generationSeq}`);
    const payload = getProviderPayload(event);
    const modelParameters = extractModelParameters(payload);
    const selected = extractModelIdentity(selectedModel ?? state.currentModel, selectedModel ? void 0 : state.currentProvider);
    const payloadModel = payload && typeof payload === "object" ? payload.model : void 0;
    const actual = extractModelIdentity(event.model ?? event.modelId ?? payloadModel, event.provider);
    const toolUpdateTransport = inferToolUpdateTransport(payload, (state.agentState.systemStateSequence ?? 0) > 1);
    const metadata = shapePayload({
      provider: actual.provider ?? selected.provider,
      selectedModel: selected.model,
      selectedProvider: selected.provider,
      actualModel: actual.model,
      actualProvider: actual.provider,
      requestId: key,
      url: event.url,
      method: event.method,
      promptStateHash: state.agentState.promptStateHash,
      toolStateHash: state.agentState.toolStateHash,
      systemStateSequence: state.agentState.systemStateSequence,
      activeToolCount: state.agentState.activeToolCount,
      toolUpdateTransport,
      cachePreservationExpected: toolUpdateTransport === "anthropic-native" || toolUpdateTransport === "openai-additional-tools" || toolUpdateTransport === "openai-tool-search" || toolUpdateTransport === "mid-conversation-system" ? true : toolUpdateTransport === "collapsed-leading-system" ? false : void 0
    });
    const capturePolicy = getCapturePolicy();
    const preserveInputMedia = capturePolicy.captureInputs;
    const captured = applyCapturePolicy(
      {
        input: shapePayload(payload, { preserveMedia: preserveInputMedia }),
        metadata
      },
      capturePolicy,
      { preserveInputMedia }
    );
    const parent = state.agentState.activeTurn ?? state.agentState.activeAttempt ?? state.agentState.root;
    const generation = await startChildObservation({
      parent,
      runtime: getRuntime,
      name: "llm-generation",
      body: {
        input: captured.input,
        model: actual.model ?? selected.model,
        modelParameters,
        metadata: captured.metadata
      },
      asType: "generation"
    });
    state.agentState.activeGenerations.set(key, {
      observation: generation,
      requestKey: key,
      ended: false,
      metadata: captured.metadata ?? {},
      modelParameters
    });
    state.agentState.generationOrder.push(key);
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to start generation", e);
  }
}
function updateGenerationMetadata(event) {
  if (state.isTracingDisabled || !state.agentState) {
    return;
  }
  const key = getRequestKey(event, "");
  const metadata = applyCapturePolicy({ metadata: extractResponseMetadata(event) }, getCapturePolicy()).metadata ?? {};
  if (!key) {
    const generation2 = getOpenGeneration();
    if (generation2) {
      generation2.metadata = { ...generation2.metadata, ...metadata };
      const isError = typeof metadata.status === "number" && metadata.status >= 400 || event.error || event.isError;
      if (isError) {
        generation2.observation.update({
          metadata: generation2.metadata,
          level: "ERROR",
          statusMessage: redactString(String(event.error ?? metadata.statusMessage ?? "Provider request failed"))
        }).end();
        generation2.ended = true;
      } else {
        generation2.observation.update({ metadata: generation2.metadata });
      }
    }
    return;
  }
  const generation = state.agentState.activeGenerations.get(key) ?? getOpenGeneration();
  if (generation) {
    generation.metadata = { ...generation.metadata, ...metadata };
    const isError = typeof metadata.status === "number" && metadata.status >= 400 || event.error || event.isError;
    if (isError) {
      generation.observation.update({
        metadata: generation.metadata,
        level: "ERROR",
        statusMessage: redactString(String(event.error ?? metadata.statusMessage ?? "Provider request failed"))
      }).end();
      generation.ended = true;
    } else {
      generation.observation.update({ metadata: generation.metadata });
    }
  }
}
function recordTTFT(event) {
  if (state.isTracingDisabled || !state.agentState) {
    return;
  }
  const key = getRequestKey(event, "");
  const generation = key ? state.agentState.activeGenerations.get(key) : getOpenGeneration();
  if (generation && !generation.ttftRecorded && !generation.ended) {
    generation.ttftRecorded = true;
    try {
      generation.observation.update({ completionStartTime: /* @__PURE__ */ new Date() });
    } catch (e) {
    }
  }
}
function recordGenerationIdentity(event) {
  const generation = getOpenGeneration();
  if (!generation) return;
  const actual = extractModelIdentity(event.model, event.provider);
  if (!actual.model && !actual.provider) return;
  if (generation.metadata.actualModel === actual.model && generation.metadata.actualProvider === actual.provider) return;
  generation.metadata = applyCapturePolicy({ metadata: shapePayload({
    ...generation.metadata,
    ...actual.model ? { actualModel: actual.model } : {},
    ...actual.provider ? { provider: actual.provider, actualProvider: actual.provider } : {}
  }) }, getCapturePolicy()).metadata ?? {};
  generation.observation.update({ model: actual.model, metadata: generation.metadata });
}
async function finishGenerationFromMessage(event) {
  if (state.isTracingDisabled || !state.agentState) {
    return;
  }
  const message = getMessageFromEvent(event);
  if (!message || message.role !== "assistant") {
    return;
  }
  const generation = getOpenGeneration();
  const rawOutput = extractAssistantOutput(message);
  const captured = applyCapturePolicy({ output: rawOutput }, getCapturePolicy());
  const output = captured.output;
  state.agentState.latestAssistantOutput = output;
  if (!generation) {
    return;
  }
  const usageDetails = extractUsage({ ...event, message });
  const costDetails = extractCostDetails({ ...event, message });
  const cacheMetrics = extractCacheMetrics({ ...event, message });
  const modelParameters = extractModelParameters(getProviderPayload(event)) ?? generation.modelParameters;
  const actual = extractModelIdentity(message.model ?? event.model, message.provider ?? event.provider);
  const update = {
    output,
    model: actual.model ?? generation.metadata.actualModel ?? (state.currentModel || void 0),
    modelParameters,
    usageDetails,
    ...costDetails ? { costDetails } : {},
    metadata: {
      ...generation.metadata,
      ...actual.model ? { actualModel: actual.model } : {},
      ...actual.provider ? { provider: actual.provider, actualProvider: actual.provider } : {},
      finishReason: message.finishReason ?? message.stopReason ?? event.finishReason,
      ...cacheMetrics
    }
  };
  update.metadata = applyCapturePolicy({ metadata: update.metadata }, getCapturePolicy()).metadata;
  try {
    generation.observation.update(update).end();
    generation.ended = true;
    if (cacheMetrics) {
      state.agentState.cacheReadTokens = (state.agentState.cacheReadTokens ?? 0) + cacheMetrics.cacheReadTokens;
      state.agentState.cacheWriteTokens = (state.agentState.cacheWriteTokens ?? 0) + cacheMetrics.cacheWriteTokens;
      state.agentState.uncachedInputTokens = (state.agentState.uncachedInputTokens ?? 0) + cacheMetrics.uncachedInputTokens;
    }
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to finish generation", e);
  }
}
async function createFallbackGenerationFromTurn(event, message) {
  if (state.isTracingDisabled || !state.agentState?.root || state.agentState.generationOrder.length > 0) {
    return;
  }
  try {
    const usageDetails = extractUsage({ ...event, message });
    const costDetails = extractCostDetails({ ...event, message });
    const cacheMetrics = extractCacheMetrics({ ...event, message });
    const modelParameters = extractModelParameters(getProviderPayload(event));
    const actual = extractModelIdentity(message.model ?? event.model, message.provider ?? event.provider);
    const captured = applyCapturePolicy(
      {
        input: state.agentState.promptInput,
        output: extractAssistantOutput(message),
        metadata: {
          provider: actual.provider ?? (state.currentProvider || void 0),
          selectedModel: state.currentModel || void 0,
          selectedProvider: state.currentProvider || void 0,
          actualModel: actual.model,
          actualProvider: actual.provider,
          sourceEvent: "turn_end",
          promptStateHash: state.agentState.promptStateHash,
          toolStateHash: state.agentState.toolStateHash,
          systemStateSequence: state.agentState.systemStateSequence,
          activeToolCount: state.agentState.activeToolCount,
          ...cacheMetrics
        }
      },
      getCapturePolicy()
    );
    const parent = state.agentState.activeTurn ?? state.agentState.activeAttempt ?? state.agentState.root;
    const generation = await startChildObservation({
      parent,
      runtime: getRuntime,
      name: "llm-generation",
      body: {
        input: captured.input,
        output: captured.output,
        model: actual.model ?? (state.currentModel || void 0),
        modelParameters,
        usageDetails,
        ...costDetails ? { costDetails } : {},
        metadata: captured.metadata
      },
      asType: "generation"
    });
    generation.end();
    state.agentState.generationOrder.push("turn-end-fallback");
    if (cacheMetrics) {
      state.agentState.cacheReadTokens = (state.agentState.cacheReadTokens ?? 0) + cacheMetrics.cacheReadTokens;
      state.agentState.cacheWriteTokens = (state.agentState.cacheWriteTokens ?? 0) + cacheMetrics.cacheWriteTokens;
      state.agentState.uncachedInputTokens = (state.agentState.uncachedInputTokens ?? 0) + cacheMetrics.uncachedInputTokens;
    }
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to create fallback generation", e);
  }
}
export {
  createFallbackGenerationFromTurn,
  finishGenerationFromMessage,
  getOpenGeneration,
  recordGenerationIdentity,
  recordTTFT,
  startGeneration,
  updateGenerationMetadata
};
