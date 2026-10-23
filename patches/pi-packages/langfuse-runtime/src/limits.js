import {
  MAX_ARRAY_ITEMS,
  MAX_DEPTH,
  MAX_OBJECT_KEYS,
  MAX_PAYLOAD_NODES,
  MAX_STRING_LENGTH,
  MAX_TOOL_PAYLOAD_LENGTH
} from "./constants.js";
import { state } from "./state.js";
const DEFAULT_LIMITS = {
  maxString: MAX_STRING_LENGTH,
  maxToolPayload: MAX_TOOL_PAYLOAD_LENGTH,
  maxDepth: MAX_DEPTH,
  maxArrayItems: MAX_ARRAY_ITEMS,
  maxObjectKeys: MAX_OBJECT_KEYS,
  maxNodes: MAX_PAYLOAD_NODES
};
const UNLIMITED_WORDS = /* @__PURE__ */ new Set(["off", "none", "false", "no", "unlimited", "inf", "infinity"]);
function parseLimit(raw, fallback) {
  if (raw === void 0) {
    return fallback;
  }
  const trimmed = raw.trim().toLowerCase();
  if (trimmed === "") {
    return fallback;
  }
  if (UNLIMITED_WORDS.has(trimmed)) {
    return Number.POSITIVE_INFINITY;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  if (parsed <= 0) {
    return Number.POSITIVE_INFINITY;
  }
  return Math.floor(parsed);
}
function createPayloadLimits(env = process.env) {
  return {
    maxString: parseLimit(env.PI_LANGFUSE_MAX_STRING_LENGTH, DEFAULT_LIMITS.maxString),
    maxToolPayload: parseLimit(env.PI_LANGFUSE_MAX_TOOL_PAYLOAD_LENGTH, DEFAULT_LIMITS.maxToolPayload),
    maxDepth: parseLimit(env.PI_LANGFUSE_MAX_DEPTH, DEFAULT_LIMITS.maxDepth),
    maxArrayItems: parseLimit(env.PI_LANGFUSE_MAX_ARRAY_ITEMS, DEFAULT_LIMITS.maxArrayItems),
    maxObjectKeys: parseLimit(env.PI_LANGFUSE_MAX_OBJECT_KEYS, DEFAULT_LIMITS.maxObjectKeys),
    maxNodes: parseLimit(env.PI_LANGFUSE_MAX_PAYLOAD_NODES, DEFAULT_LIMITS.maxNodes)
  };
}
function getLimits() {
  return state.config?.limits ?? createPayloadLimits();
}
export {
  DEFAULT_LIMITS,
  createPayloadLimits,
  getLimits,
  parseLimit
};
