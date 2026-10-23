import { AsyncLocalStorage } from "node:async_hooks";
const DEFAULT_SESSION_ID = "__pi_langfuse_default_session__";
let activeSessionId = DEFAULT_SESSION_ID;
const sessionScope = new AsyncLocalStorage();
function createSessionRunState() {
  return {
    currentModel: "",
    currentProvider: "",
    agentState: null,
    toolCallCount: 0,
    errorCount: 0,
    turnCount: 0,
    tracingDisabled: false,
    setupAttemptedThisSession: false,
    lastActiveTools: [],
    systemStateSequence: 0,
    seenSystemEntryIds: /* @__PURE__ */ new Set(),
    seenUsageEntryIds: /* @__PURE__ */ new Set()
  };
}
function normalizeSessionId(sessionId) {
  return sessionId || DEFAULT_SESSION_ID;
}
function getActiveSessionId() {
  return sessionScope.getStore() ?? activeSessionId;
}
function getSessionRunState(sessionId = getActiveSessionId()) {
  const normalizedSessionId = normalizeSessionId(sessionId);
  let sessionState = state.sessionStates.get(normalizedSessionId);
  if (!sessionState) {
    sessionState = createSessionRunState();
    state.sessionStates.set(normalizedSessionId, sessionState);
  }
  return sessionState;
}
function setCurrentSession(sessionId) {
  activeSessionId = normalizeSessionId(sessionId);
  getSessionRunState(activeSessionId);
}
function runWithSession(sessionId, fn) {
  const normalizedSessionId = normalizeSessionId(sessionId);
  setCurrentSession(normalizedSessionId);
  return sessionScope.run(normalizedSessionId, fn);
}
const state = {
  config: null,
  sessionStates: /* @__PURE__ */ new Map(),
  get currentSessionId() {
    const sessionId = getActiveSessionId();
    return sessionId === DEFAULT_SESSION_ID ? "" : sessionId;
  },
  set currentSessionId(sessionId) {
    setCurrentSession(sessionId);
  },
  get currentModel() {
    return getSessionRunState().currentModel;
  },
  set currentModel(model) {
    getSessionRunState().currentModel = model;
  },
  get currentProvider() {
    return getSessionRunState().currentProvider;
  },
  set currentProvider(provider) {
    getSessionRunState().currentProvider = provider;
  },
  get agentState() {
    return getSessionRunState().agentState;
  },
  set agentState(agentState) {
    getSessionRunState().agentState = agentState;
  },
  get toolCallCount() {
    return getSessionRunState().toolCallCount;
  },
  set toolCallCount(toolCallCount) {
    getSessionRunState().toolCallCount = toolCallCount;
  },
  get errorCount() {
    return getSessionRunState().errorCount;
  },
  set errorCount(errorCount) {
    getSessionRunState().errorCount = errorCount;
  },
  get turnCount() {
    return getSessionRunState().turnCount;
  },
  set turnCount(turnCount) {
    getSessionRunState().turnCount = turnCount;
  },
  get isTracingDisabled() {
    return getSessionRunState().tracingDisabled;
  },
  set isTracingDisabled(disabled) {
    getSessionRunState().tracingDisabled = disabled;
  },
  get setupAttemptedThisSession() {
    return getSessionRunState().setupAttemptedThisSession;
  },
  set setupAttemptedThisSession(attempted) {
    getSessionRunState().setupAttemptedThisSession = attempted;
  }
};
function resetRunState(sessionId = getActiveSessionId()) {
  const normalizedSessionId = normalizeSessionId(sessionId);
  const previous = state.sessionStates.get(normalizedSessionId);
  state.sessionStates.set(normalizedSessionId, {
    ...createSessionRunState(),
    setupAttemptedThisSession: previous?.setupAttemptedThisSession ?? false,
    lastPromptStateHash: previous?.lastPromptStateHash,
    lastToolStateHash: previous?.lastToolStateHash,
    lastActiveTools: previous?.lastActiveTools ?? [],
    systemStateSequence: previous?.systemStateSequence ?? 0,
    seenSystemEntryIds: previous?.seenSystemEntryIds ?? /* @__PURE__ */ new Set(),
    seenUsageEntryIds: previous?.seenUsageEntryIds ?? /* @__PURE__ */ new Set()
  });
}
function clearAllSessionStates() {
  state.sessionStates.clear();
  activeSessionId = DEFAULT_SESSION_ID;
  getSessionRunState();
}
function computeEvaluationScores(sessionId = getActiveSessionId()) {
  const sessionState = getSessionRunState(sessionId);
  const toolSuccessRate = sessionState.toolCallCount > 0 ? (sessionState.toolCallCount - sessionState.errorCount) / sessionState.toolCallCount : 1;
  const sessionHadErrors = sessionState.errorCount > 0;
  return {
    tool_call_count: sessionState.toolCallCount,
    turn_count: sessionState.turnCount,
    total_tool_errors: sessionState.errorCount,
    tool_success_rate: toolSuccessRate,
    session_had_errors: sessionHadErrors ? 1 : 0
  };
}
getSessionRunState();
export {
  clearAllSessionStates,
  computeEvaluationScores,
  getSessionRunState,
  resetRunState,
  runWithSession,
  setCurrentSession,
  state
};
