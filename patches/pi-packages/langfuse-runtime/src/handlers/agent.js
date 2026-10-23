import { state, resetRunState, computeEvaluationScores } from "../state.js";
import { getRuntime, sendScore } from "../langfuse.js";
import { ensureConfig } from "../config.js";
import { shapePayload, truncate, extractFinalAssistant, extractAssistantOutput, getCapturePolicy, getLimits } from "../utils.js";
import { closeDanglingObservations } from "./tool.js";
import { applyCapturePolicy } from "../capture-policy.js";
import { collectSourceMetadata } from "../source-metadata.js";
import { startChildObservation } from "../observation.js";
function stringMetadata(metadata) {
  if (!metadata) {
    return void 0;
  }
  const output = {};
  for (const [key, value] of Object.entries(metadata)) {
    if (typeof value === "string") {
      output[key] = value;
    } else if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
      output[key] = String(value);
    }
  }
  return Object.keys(output).length > 0 ? output : void 0;
}
function updateTraceIO(input, output) {
  const root = state.agentState?.root;
  if (!root?.setTraceIO) {
    return;
  }
  try {
    root.setTraceIO({ input, output });
  } catch {
  }
}
async function startAgentRun(event, ctx) {
  if (!await ensureConfig(ctx)) {
    state.isTracingDisabled = true;
    return;
  }
  try {
    const rt = await getRuntime();
    const cwd = String(
      (event.systemPromptOptions && typeof event.systemPromptOptions === "object" ? event.systemPromptOptions.cwd : void 0) ?? process.cwd()
    );
    if (!state.currentModel && ctx.model) {
      state.currentModel = ctx.model.id || "";
      state.currentProvider = ctx.model.provider || "";
    }
    const rawPromptInput = shapePayload({
      prompt: event.prompt,
      images: event.images,
      context: event.context ?? event.attachments
    });
    const capturePolicy = getCapturePolicy();
    const sourceMetadata = collectSourceMetadata(cwd, capturePolicy.captureSourceMetadata);
    const captured = applyCapturePolicy(
      {
        input: rawPromptInput,
        metadata: {
          cwd,
          ...sourceMetadata,
          ...state.currentModel ? { model: state.currentModel } : {},
          ...state.currentProvider ? { provider: state.currentProvider } : {},
          sessionId: state.currentSessionId || void 0,
          sessionLeafId: ctx?.sessionManager?.getLeafId?.() || void 0
        }
      },
      capturePolicy
    );
    state.agentState = {
      cwd,
      promptInput: captured.input,
      generationSeq: 0,
      activeGenerations: /* @__PURE__ */ new Map(),
      generationOrder: [],
      activeTools: /* @__PURE__ */ new Map(),
      sourceMetadata,
      providerMetadataByRequest: /* @__PURE__ */ new Map(),
      attemptCount: 0,
      systemStateChangeCount: 0,
      cacheReadTokens: 0,
      cacheWriteTokens: 0,
      uncachedInputTokens: 0
    };
    const root = rt.propagateAttributes(
      {
        sessionId: state.currentSessionId ? truncate(state.currentSessionId, 200) : void 0,
        userId: state.config?.userId,
        traceName: "pi-agent",
        metadata: stringMetadata(captured.metadata)
      },
      () => rt.startObservation(
        "pi-agent",
        {
          input: captured.input,
          metadata: captured.metadata ?? {}
        },
        { asType: "agent" }
      )
    );
    state.agentState.root = root;
    state.agentState.traceId = root.traceId;
    updateTraceIO(captured.input, void 0);
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to create agent observation", e);
    state.isTracingDisabled = true;
  }
}
async function startAgentAttempt() {
  const agent = state.agentState;
  if (state.isTracingDisabled || !agent?.root) return;
  if (agent.activeAttempt) {
    agent.activeAttempt.update({ level: "WARNING", statusMessage: "A new agent attempt started before the previous attempt ended" }).end();
  }
  try {
    agent.attemptCount++;
    agent.activeAttempt = await startChildObservation({
      parent: agent.root,
      runtime: getRuntime,
      name: "agent-attempt",
      body: { metadata: { attemptIndex: agent.attemptCount } },
      asType: "span"
    });
  } catch (error) {
    console.warn("\u{1F4CA} Langfuse: Failed to start agent attempt", error);
  }
}
function finishAgentAttempt(event = {}) {
  const agent = state.agentState;
  if (!agent) return;
  agent.lastAgentEndEvent = event;
  closeDanglingObservations("Agent attempt ended before observation finalized");
  if (agent.activeTurn) {
    agent.activeTurn.update({ level: "WARNING", statusMessage: "Agent attempt ended before turn finalized" }).end();
    agent.activeTurn = void 0;
  }
  if (!agent.activeAttempt) return;
  try {
    const lastAssistant = extractFinalAssistant(event.messages);
    const captured = applyCapturePolicy(
      { output: lastAssistant ? extractAssistantOutput(lastAssistant) : void 0 },
      getCapturePolicy()
    );
    agent.activeAttempt.update({ output: captured.output }).end();
  } catch (error) {
    console.warn("\u{1F4CA} Langfuse: Failed to finish agent attempt", error);
  } finally {
    agent.activeAttempt = void 0;
  }
}
function cancelAgentRun(reason) {
  const agent = state.agentState;
  if (!agent?.root) {
    resetRunState();
    return;
  }
  closeDanglingObservations(reason);
  if (agent.activeTurn) {
    agent.activeTurn.update({ level: "WARNING", statusMessage: reason, metadata: { cancelled: true } }).end();
    agent.activeTurn = void 0;
  }
  if (agent.activeAttempt) {
    agent.activeAttempt.update({ level: "WARNING", statusMessage: reason, metadata: { cancelled: true } }).end();
    agent.activeAttempt = void 0;
  }
  agent.root.update({
    level: "WARNING",
    statusMessage: reason,
    metadata: { completed: false, cancelled: true }
  }).end();
  resetRunState();
}
async function recordSystemPrompt(ctx) {
  const root = state.agentState?.root;
  if (state.isTracingDisabled || !root) {
    return;
  }
  let systemPrompt = void 0;
  try {
    if (ctx.getSystemPrompt) {
      systemPrompt = await ctx.getSystemPrompt();
    }
  } catch {
  }
  if (!systemPrompt) {
    return;
  }
  const captured = applyCapturePolicy(
    { systemPrompt: truncate(String(systemPrompt), getLimits().maxString) },
    getCapturePolicy()
  );
  if (!captured.systemPrompt) {
    return;
  }
  try {
    root.update({ metadata: { systemPrompt: captured.systemPrompt } });
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to record system prompt", e);
  }
}
async function finishAgentRun(event = {}) {
  if (!state.agentState?.root) {
    resetRunState();
    return;
  }
  const finalEvent = Object.keys(event).length > 0 ? event : state.agentState.lastAgentEndEvent ?? {};
  const lastAssistant = extractFinalAssistant(finalEvent.messages);
  const rawOutput = lastAssistant ? extractAssistantOutput(lastAssistant) : state.agentState.latestAssistantOutput;
  const captured = applyCapturePolicy(
    {
      output: rawOutput,
      metadata: {
        cwd: state.agentState.cwd,
        ...state.agentState.sourceMetadata ?? {},
        completed: true,
        model: state.currentModel || void 0,
        provider: state.currentProvider || void 0,
        totalTools: state.toolCallCount,
        agentAttemptCount: state.agentState.attemptCount,
        systemStateChangeCount: state.agentState.systemStateChangeCount,
        promptStateHash: state.agentState.promptStateHash,
        toolStateHash: state.agentState.toolStateHash,
        activeToolCount: state.agentState.activeToolCount,
        cacheReadTokens: state.agentState.cacheReadTokens,
        cacheWriteTokens: state.agentState.cacheWriteTokens,
        uncachedInputTokens: state.agentState.uncachedInputTokens,
        cacheHitRatio: state.agentState.cacheReadTokens + state.agentState.uncachedInputTokens > 0 ? state.agentState.cacheReadTokens / (state.agentState.cacheReadTokens + state.agentState.uncachedInputTokens) : void 0,
        ...computeEvaluationScores()
      }
    },
    getCapturePolicy()
  );
  const scores = computeEvaluationScores();
  closeDanglingObservations("Agent run ended before observation finalized");
  if (state.agentState.activeAttempt) {
    state.agentState.activeAttempt.end();
    state.agentState.activeAttempt = void 0;
  }
  try {
    state.agentState.root.update({
      output: captured.output,
      metadata: captured.metadata
    }).end();
    updateTraceIO(state.agentState.promptInput, captured.output);
    await sendScore("tool_call_count", scores.tool_call_count, { traceId: state.agentState.traceId });
    await sendScore("turn_count", scores.turn_count, { traceId: state.agentState.traceId });
    await sendScore("total_tool_errors", scores.total_tool_errors, { traceId: state.agentState.traceId });
    await sendScore("tool_success_rate", scores.tool_success_rate, { traceId: state.agentState.traceId });
    await sendScore("session_had_errors", scores.session_had_errors, { traceId: state.agentState.traceId });
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to finish agent observation", e);
  } finally {
    resetRunState();
  }
}
export {
  cancelAgentRun,
  finishAgentAttempt,
  finishAgentRun,
  recordSystemPrompt,
  startAgentAttempt,
  startAgentRun,
  updateTraceIO
};
