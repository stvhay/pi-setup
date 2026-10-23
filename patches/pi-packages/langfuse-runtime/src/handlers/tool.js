import { state } from "../state.js";
import { getRuntime, sendScore } from "../langfuse.js";
import { startChildObservation } from "../observation.js";
import {
  getToolCallId,
  getToolName,
  getToolInput,
  shapePayload,
  extractTextContent,
  prepareToolPayload,
  getCapturePolicy,
  getLimits,
  extractToolUsage
} from "../utils.js";
import { applyCapturePolicy, redactOptionsFor } from "../capture-policy.js";
import { redactString } from "../redaction.js";
const TOOL_PAYLOAD_BYTES_VERSION = 1;
function payloadByteMetadata(direction, payload, policy) {
  const absent = payload.bytesState === "absent";
  const captureState = absent ? "absent" : payload.bytesState === "unknown" && policy.captureToolIo ? "unknown" : policy.captureToolIo ? "captured" : "redacted";
  const bytesState = absent ? "absent" : policy.captureToolIoBytes || policy.captureToolIo && payload.bytesState !== "available" ? payload.bytesState : "unavailable";
  return {
    toolPayloadBytesVersion: TOOL_PAYLOAD_BYTES_VERSION,
    [`${direction}CaptureState`]: captureState,
    [`${direction}BytesState`]: bytesState,
    ...policy.captureToolIoBytes && payload.bytes !== void 0 ? { [`${direction}Bytes`]: payload.bytes } : {}
  };
}
async function startToolObservation(event) {
  if (state.isTracingDisabled || !state.agentState?.root) {
    return;
  }
  const toolCallId = getToolCallId(event);
  if (!toolCallId || state.agentState.activeTools.has(toolCallId)) {
    return;
  }
  try {
    const toolName = getToolName(event);
    const parentToolCallId = typeof event.parentToolCallId === "string" ? event.parentToolCallId : void 0;
    const policy = getCapturePolicy();
    const preparedInput = prepareToolPayload(getToolInput(event), getLimits().maxToolPayload);
    const inputByteMetadata = payloadByteMetadata("input", preparedInput, policy);
    const captured = applyCapturePolicy(
      {
        toolInput: preparedInput.value,
        metadata: shapePayload({ toolName, toolCallId, parentToolCallId })
      },
      policy
    );
    const parentTool = parentToolCallId ? state.agentState.activeTools.get(parentToolCallId) : void 0;
    const parent = parentTool?.observation ?? state.agentState.activeTurn ?? state.agentState.activeAttempt ?? state.agentState.root;
    const tool = await startChildObservation({
      parent,
      runtime: getRuntime,
      name: toolName,
      body: {
        input: captured.toolInput,
        metadata: { ...captured.metadata ?? {}, ...inputByteMetadata }
      },
      asType: "tool"
    });
    state.toolCallCount++;
    state.agentState.activeTools.set(toolCallId, {
      observation: tool,
      toolName,
      ended: false,
      startedAt: Date.now(),
      inputByteMetadata,
      parentToolCallId
    });
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to start tool observation", e);
  }
}
async function finishToolObservation(event) {
  if (state.isTracingDisabled || !state.agentState) {
    return;
  }
  const toolCallId = getToolCallId(event);
  if (!toolCallId) {
    return;
  }
  const activeTool = state.agentState.activeTools.get(toolCallId);
  if (!activeTool || activeTool.ended) {
    return;
  }
  activeTool.ended = true;
  const isError = Boolean(event.isError ?? event.error ?? event.status === "error");
  const output = extractTextContent(event.content, getLimits().maxToolPayload) ?? event.output ?? event.result ?? event.error ?? event.content;
  try {
    const policy = getCapturePolicy();
    const preparedOutput = prepareToolPayload(output, getLimits().maxToolPayload);
    const outputByteMetadata = payloadByteMetadata("output", preparedOutput, policy);
    const captured = applyCapturePolicy(
      {
        toolOutput: preparedOutput.value,
        metadata: shapePayload({
          toolName: activeTool.toolName,
          toolCallId,
          parentToolCallId: activeTool.parentToolCallId,
          isError
        })
      },
      policy
    );
    const durationMs = Math.max(0, Date.now() - activeTool.startedAt);
    const { usageDetails, costDetails } = extractToolUsage(event);
    if (usageDetails || costDetails) {
      try {
        const usage = await startChildObservation({
          parent: activeTool.observation,
          runtime: getRuntime,
          name: "tool-usage",
          body: {
            usageDetails,
            costDetails,
            metadata: applyCapturePolicy({ metadata: shapePayload({
              toolName: activeTool.toolName,
              toolCallId,
              parentToolCallId: activeTool.parentToolCallId,
              usageSource: "tool-result"
            }) }, policy).metadata
          },
          asType: "generation"
        });
        usage.end();
      } catch (error) {
        console.warn("\u{1F4CA} Langfuse: Failed to record tool usage", error);
      }
    }
    activeTool.observation.update({
      output: captured.toolOutput,
      level: isError ? "ERROR" : "DEFAULT",
      statusMessage: isError ? policy.captureToolIo ? redactString(String(event.error ?? output), { ...redactOptionsFor(policy), maxStringLength: 1e3 }) : "Tool execution failed" : void 0,
      metadata: {
        ...captured.metadata ?? {},
        durationMs,
        ...activeTool.inputByteMetadata,
        ...outputByteMetadata
      }
    }).end();
    if (isError) {
      state.errorCount++;
      await sendScore("tool_is_error", 1, {
        traceId: state.agentState.traceId,
        observationId: activeTool.observation.id
      });
    }
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to finish tool observation", e);
  } finally {
    state.agentState.activeTools.delete(toolCallId);
  }
}
function closeDanglingObservations(statusMessage) {
  if (state.isTracingDisabled || !state.agentState) {
    return;
  }
  for (const activeTool of state.agentState.activeTools.values()) {
    if (!activeTool.ended) {
      activeTool.observation.update({ level: "WARNING", statusMessage, metadata: { toolName: activeTool.toolName, cancelled: true } }).end();
      activeTool.ended = true;
    }
  }
  for (const generation of state.agentState.activeGenerations.values()) {
    if (!generation.ended) {
      generation.observation.update({ level: "WARNING", statusMessage, metadata: { ...generation.metadata, cancelled: true } }).end();
      generation.ended = true;
    }
  }
  state.agentState.activeTools.clear();
}
export {
  closeDanglingObservations,
  finishToolObservation,
  startToolObservation
};
