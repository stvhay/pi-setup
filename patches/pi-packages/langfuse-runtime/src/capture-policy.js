import { hashPath, redactValue } from "./redaction.js";
function redactOptionsFor(policy) {
  return { redactPaths: !policy.capturePaths };
}
const PRESETS = {
  "metadata-only": {
    captureInputs: false,
    captureOutputs: false,
    captureToolIo: false,
    captureToolIoBytes: false,
    captureSystemPrompt: false,
    captureCwd: false,
    captureSourceMetadata: false,
    capturePaths: false
  },
  "prompts-only": {
    captureInputs: true,
    captureOutputs: false,
    captureToolIo: false,
    captureToolIoBytes: false,
    captureSystemPrompt: false,
    captureCwd: false,
    captureSourceMetadata: false,
    capturePaths: false
  },
  conversations: {
    captureInputs: true,
    captureOutputs: true,
    captureToolIo: false,
    captureToolIoBytes: false,
    captureSystemPrompt: false,
    captureCwd: false,
    captureSourceMetadata: false,
    capturePaths: false
  },
  "full-debug": {
    captureInputs: true,
    captureOutputs: true,
    captureToolIo: true,
    captureToolIoBytes: true,
    captureSystemPrompt: true,
    captureCwd: true,
    captureSourceMetadata: false,
    capturePaths: false
  }
};
const FLAG_TO_FIELD = {
  LANGFUSE_CAPTURE_INPUTS: "captureInputs",
  LANGFUSE_CAPTURE_OUTPUTS: "captureOutputs",
  LANGFUSE_CAPTURE_TOOL_IO: "captureToolIo",
  LANGFUSE_CAPTURE_TOOL_IO_BYTES: "captureToolIoBytes",
  LANGFUSE_CAPTURE_SYSTEM_PROMPT: "captureSystemPrompt",
  LANGFUSE_CAPTURE_CWD: "captureCwd",
  LANGFUSE_CAPTURE_SOURCE_METADATA: "captureSourceMetadata",
  LANGFUSE_CAPTURE_PATHS: "capturePaths"
};
function parseFlag(value) {
  if (value === void 0) {
    return void 0;
  }
  if (/^(1|true|yes|on)$/i.test(value)) {
    return true;
  }
  if (/^(0|false|no|off)$/i.test(value)) {
    return false;
  }
  return void 0;
}
function normalizePreset(value) {
  return value && value in PRESETS ? value : "full-debug";
}
function createCapturePolicy(env = process.env) {
  const policy = { ...PRESETS[normalizePreset(env.LANGFUSE_PRIVACY_PRESET)] };
  for (const [envName, field] of Object.entries(FLAG_TO_FIELD)) {
    const override = parseFlag(env[envName]);
    if (override !== void 0) {
      policy[field] = override;
    }
  }
  return policy;
}
function redactMetadata(metadata, policy) {
  if (!metadata) {
    return void 0;
  }
  const redactOptions = redactOptionsFor(policy);
  const output = {};
  for (const [key, value] of Object.entries(metadata)) {
    if (key === "cwd") {
      if (!policy.captureCwd) {
        continue;
      }
      output[key] = !policy.capturePaths && typeof value === "string" && /^(?:\/|[A-Za-z]:[\\/]|\\\\)/.test(value) ? hashPath(value) : redactValue(value, redactOptions);
      continue;
    }
    output[key] = redactValue(value, redactOptions);
  }
  return Object.keys(output).length > 0 ? output : void 0;
}
function applyCapturePolicy(payload, policy = createCapturePolicy(), options = {}) {
  const redactOptions = redactOptionsFor(policy);
  const captured = {
    metadata: redactMetadata(payload.metadata, policy)
  };
  if (policy.captureInputs && "input" in payload) {
    captured.input = redactValue(payload.input, { ...redactOptions, preserveMedia: options.preserveInputMedia });
  }
  if (policy.captureOutputs && "output" in payload) {
    captured.output = redactValue(payload.output, redactOptions);
  }
  if (policy.captureToolIo && "toolInput" in payload) {
    captured.toolInput = redactValue(payload.toolInput, redactOptions);
  }
  if (policy.captureToolIo && "toolOutput" in payload) {
    captured.toolOutput = redactValue(payload.toolOutput, redactOptions);
  }
  if (policy.captureSystemPrompt && "systemPrompt" in payload) {
    captured.systemPrompt = redactValue(payload.systemPrompt, redactOptions);
  }
  return captured;
}
export {
  applyCapturePolicy,
  createCapturePolicy,
  parseFlag,
  redactOptionsFor
};
