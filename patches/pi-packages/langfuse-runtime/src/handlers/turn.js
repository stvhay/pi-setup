import { state } from "../state.js";
import { getRuntime } from "../langfuse.js";
import { startChildObservation } from "../observation.js";
import { shapePayload, getCapturePolicy } from "../utils.js";
import { applyCapturePolicy } from "../capture-policy.js";
async function startTurnObservation(event) {
  if (state.isTracingDisabled || !state.agentState?.root) {
    return;
  }
  if (state.agentState.activeTurn) {
    state.agentState.activeTurn.end();
    state.agentState.activeTurn = void 0;
  }
  try {
    const turnIndex = event.turnIndex ?? state.turnCount;
    const captured = applyCapturePolicy(
      {
        input: shapePayload(event.context ?? event),
        metadata: { turnIndex }
      },
      getCapturePolicy()
    );
    const observation = await startChildObservation({
      parent: state.agentState.activeAttempt ?? state.agentState.root,
      runtime: getRuntime,
      name: "turn",
      body: {
        input: captured.input,
        metadata: captured.metadata
      },
      asType: "span"
    });
    state.agentState.activeTurn = observation;
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to start turn observation", e);
  }
}
function finishTurnObservation(_event) {
  if (state.isTracingDisabled || !state.agentState?.activeTurn) {
    return;
  }
  try {
    state.agentState.activeTurn.end();
    state.agentState.activeTurn = void 0;
  } catch (e) {
    console.warn("\u{1F4CA} Langfuse: Failed to finish turn observation", e);
  }
}
export {
  finishTurnObservation,
  startTurnObservation
};
