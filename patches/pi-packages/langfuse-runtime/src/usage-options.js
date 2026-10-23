import { parseFlag } from "./capture-policy.js";
import { state } from "./state.js";
const DEFAULT_USAGE_OPTIONS = {
  splitReasoningTokens: false
};
function createUsageOptions(env = process.env) {
  return {
    splitReasoningTokens: parseFlag(env.PI_LANGFUSE_SPLIT_REASONING_TOKENS) ?? DEFAULT_USAGE_OPTIONS.splitReasoningTokens
  };
}
function getUsageOptions() {
  return state.config?.usage ?? createUsageOptions();
}
export {
  DEFAULT_USAGE_OPTIONS,
  createUsageOptions,
  getUsageOptions
};
