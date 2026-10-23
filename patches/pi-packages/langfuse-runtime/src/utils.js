import { getLimits } from "./limits.js";
import { getUsageOptions } from "./usage-options.js";
import { createCapturePolicy, redactOptionsFor } from "./capture-policy.js";
import { mapMediaDataUriSegments, redactString, redactValue } from "./redaction.js";
import { state } from "./state.js";
function getCapturePolicy() {
  return state.config?.capturePolicy ?? createCapturePolicy();
}
function truncate(value, maxLength = getLimits().maxString) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}... [truncated]` : value;
}
function tryParseJson(value) {
  const trimmed = value.trim();
  if (!trimmed || !["{", "["].includes(trimmed[0])) {
    return value;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return value;
  }
}
const PAYLOAD_TOO_LARGE = "[payload too large]";
function shapePayload(value, options = {}) {
  const limits = getLimits();
  const maxString = options.maxString ?? limits.maxString;
  const depth = options.depth ?? limits.maxDepth;
  const maxNodes = options.maxNodes ?? limits.maxNodes;
  const maxArrayItems = options.maxArrayItems ?? limits.maxArrayItems;
  const maxObjectKeys = options.maxObjectKeys ?? limits.maxObjectKeys;
  const budget = { exhausted: false, nodeCount: 0 };
  const markTruncated = () => options.onTruncate?.();
  function visit(item, remainingDepth, seen) {
    if (budget.exhausted) {
      return PAYLOAD_TOO_LARGE;
    }
    budget.nodeCount++;
    if (budget.nodeCount > maxNodes) {
      budget.exhausted = true;
      markTruncated();
      return PAYLOAD_TOO_LARGE;
    }
    if (typeof item === "string") {
      if (item.length > maxString) {
        markTruncated();
      }
      if (options.parseJson !== false && options.preserveMedia) {
        const parsed2 = tryParseJson(item);
        if (parsed2 !== item) {
          return visit(parsed2, remainingDepth - 1, seen);
        }
      }
      const shaped2 = options.redact === false ? options.preserveMedia ? mapMediaDataUriSegments(item, (media) => media, (text) => truncate(text, maxString)) : truncate(item, maxString) : redactString(item, {
        ...redactOptionsFor(getCapturePolicy()),
        maxStringLength: maxString,
        preserveMedia: options.preserveMedia
      });
      if (options.parseJson === false) {
        return shaped2;
      }
      const parsed = tryParseJson(shaped2);
      if (parsed === shaped2) {
        return shaped2;
      }
      return visit(parsed, remainingDepth - 1, seen);
    }
    if (item === null || typeof item === "undefined" || typeof item === "number" || typeof item === "boolean") {
      return item;
    }
    if (typeof item === "bigint") {
      return item.toString();
    }
    if (typeof item === "function" || typeof item === "symbol") {
      return `[${typeof item}]`;
    }
    if (remainingDepth <= 0) {
      markTruncated();
      return `[max depth ${depth} reached]`;
    }
    if (Array.isArray(item)) {
      const output = [];
      const limit = Math.min(item.length, maxArrayItems);
      if (item.length > limit) {
        markTruncated();
      }
      for (let index = 0; index < limit; index++) {
        output.push(visit(item[index], remainingDepth - 1, seen));
        if (budget.exhausted) {
          break;
        }
      }
      return output;
    }
    if (item instanceof Error) {
      if (item.stack && item.stack.length > maxString) {
        markTruncated();
      }
      return {
        name: item.name,
        message: item.message,
        stack: item.stack ? truncate(item.stack, maxString) : void 0
      };
    }
    if (typeof item === "object") {
      if (seen.has(item)) {
        markTruncated();
        return "[circular]";
      }
      seen.add(item);
      const output = {};
      const record = item;
      const keys = Object.keys(record);
      const limit = Math.min(keys.length, maxObjectKeys);
      if (keys.length > limit) {
        markTruncated();
      }
      for (const key of keys.slice(0, limit)) {
        output[key] = visit(record[key], remainingDepth - 1, seen);
        if (budget.exhausted) {
          break;
        }
      }
      return output;
    }
    return String(item);
  }
  const shaped = visit(value, depth, /* @__PURE__ */ new WeakSet());
  return options.redact === false ? shaped : redactValue(shaped, {
    ...redactOptionsFor(getCapturePolicy()),
    maxDepth: depth,
    maxStringLength: maxString,
    maxArrayItems,
    maxObjectKeys,
    preserveMedia: options.preserveMedia
  });
}
function prepareToolPayload(value, maxLength = getLimits().maxToolPayload) {
  if (value === void 0) {
    return { bytesState: "absent" };
  }
  let wasTruncated = false;
  try {
    const shaped = shapePayload(value, {
      maxString: maxLength,
      onTruncate: () => {
        wasTruncated = true;
      }
    });
    const serialized = JSON.stringify(shaped, null, 2);
    if (serialized === void 0) {
      return { value: shaped, bytesState: "unknown" };
    }
    const bounded = truncate(serialized, maxLength);
    return {
      value: shaped,
      bytes: new TextEncoder().encode(bounded).length,
      bytesState: wasTruncated || bounded !== serialized ? "truncated" : "available"
    };
  } catch {
    return { value: `[unserializable ${typeof value}]`, bytesState: "unknown" };
  }
}
function extractTextContent(content, maxLength) {
  if (typeof content === "string") {
    return maxLength ? truncate(content, maxLength) : content;
  }
  if (!Array.isArray(content)) {
    return void 0;
  }
  const text = content.map((item) => {
    if (!item || typeof item !== "object") return "";
    const block = item;
    return block.type === "text" && block.text ? block.text : "";
  }).filter(Boolean).join("\n");
  if (!text) {
    return void 0;
  }
  return maxLength ? truncate(text, maxLength) : text;
}
function normalizeContentForLangfuse(content, api) {
  if (!Array.isArray(content)) {
    return content;
  }
  const toolCallItems = content.filter((item) => {
    return item && typeof item === "object" && item.type === "toolCall";
  });
  if (toolCallItems.length === 0) {
    return content;
  }
  const text = content.map((item) => {
    if (!item || typeof item !== "object") return "";
    const block = item;
    return block.type === "text" && typeof block.text === "string" ? block.text : "";
  }).filter(Boolean).join("");
  if (api === "anthropic-messages") {
    const blocks = [];
    if (text) {
      blocks.push({ type: "text", text });
    }
    for (const item of toolCallItems) {
      const toolCall = item;
      const toolInput = shapePayload(toolCall.arguments, { parseJson: false });
      blocks.push({
        type: "tool_use",
        id: String(toolCall.id ?? ""),
        name: String(toolCall.name ?? "tool"),
        input: toolInput
      });
    }
    return blocks;
  }
  return {
    role: "assistant",
    content: text || null,
    tool_calls: toolCallItems.map((item) => {
      const toolCall = item;
      const toolArguments = shapePayload(toolCall.arguments ?? {}, { parseJson: false });
      return {
        id: String(toolCall.id ?? ""),
        type: "function",
        function: {
          name: String(toolCall.name ?? "tool"),
          arguments: typeof toolArguments === "string" ? toolArguments : JSON.stringify(toolArguments)
        }
      };
    })
  };
}
function extractToolCalls(message) {
  return message.toolCalls ?? message.tool_calls ?? message.function_calls ?? (message.content && Array.isArray(message.content) ? message.content.filter((block) => {
    return block && typeof block === "object" && ["tool_use", "tool_call", "toolCall"].includes(String(block.type));
  }) : void 0);
}
function extractAssistantOutput(message) {
  if (!message || typeof message !== "object") {
    return void 0;
  }
  const msg = message;
  const normalizedContent = normalizeContentForLangfuse(msg.content, typeof msg.api === "string" ? msg.api : void 0);
  if (normalizedContent !== msg.content) {
    return shapePayload(normalizedContent, { parseJson: false });
  }
  const text = extractTextContent(msg.content);
  if (text) {
    return text;
  }
  const toolCalls = extractToolCalls(msg);
  if (Array.isArray(toolCalls) && toolCalls.length > 0) {
    return { toolCalls: shapePayload(toolCalls) };
  }
  if (toolCalls) {
    return { toolCalls: shapePayload(toolCalls) };
  }
  return shapePayload(msg);
}
function extractFinalAssistant(messages) {
  if (!Array.isArray(messages)) {
    return void 0;
  }
  return messages.filter((message) => message?.role === "assistant").pop();
}
function getRequestKey(event, fallback) {
  return String(
    event.requestId ?? event.providerRequestId ?? event.messageId ?? event.turnId ?? event.turnIndex ?? event.id ?? fallback
  );
}
function getToolCallId(event) {
  const id = event.toolCallId ?? event.id ?? event.callId ?? event.tool_use_id ?? event.toolUseId;
  return id === void 0 || id === null ? void 0 : String(id);
}
function getToolName(event) {
  return String(
    event.toolName ?? event.name ?? event.tool ?? event.functionName ?? (event.call && typeof event.call === "object" ? event.call.name : void 0) ?? "tool"
  );
}
function getToolInput(event) {
  return event.input ?? event.args ?? event.arguments ?? event.params ?? (event.call && typeof event.call === "object" ? event.call.input : void 0);
}
function getProviderPayload(event) {
  return event.request ?? event.payload ?? event.body ?? event.providerPayload ?? event.messages ?? event;
}
function inferToolUpdateTransport(payload, hasPriorSystemState) {
  let sawToolChangeBlock = false;
  let sawAdditionalTools = false;
  let sawToolSearch = false;
  let sawTopLevelTools = false;
  let sawMidConversationSystem = false;
  let visited = 0;
  const walk = (value, key) => {
    if (++visited > 2e3 || value === null || value === void 0) return;
    if (key === "additional_tools") sawAdditionalTools = true;
    if (key === "tools") sawTopLevelTools = true;
    if (key === "tool_search" || key === "tool_search_output") sawToolSearch = true;
    if (typeof value !== "object") return;
    if (Array.isArray(value)) {
      let sawNonSystem = false;
      for (const item of value) {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          const role = item.role;
          if (role === "system" && sawNonSystem) sawMidConversationSystem = true;
          if (role && role !== "system") sawNonSystem = true;
        }
        walk(item);
      }
      return;
    }
    const record = value;
    const type = record.type;
    if (type === "tool_addition" || type === "tool_removal") sawToolChangeBlock = true;
    for (const [childKey, child] of Object.entries(record)) walk(child, childKey);
  };
  walk(payload);
  if (sawToolChangeBlock) return "anthropic-native";
  if (sawAdditionalTools) return "openai-additional-tools";
  if (sawToolSearch) return "openai-tool-search";
  if (sawMidConversationSystem) return "mid-conversation-system";
  if (hasPriorSystemState && sawTopLevelTools) return "collapsed-leading-system";
  return void 0;
}
function extractModelParameters(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return void 0;
  }
  const params = {};
  const record = payload;
  for (const key of [
    "temperature",
    "top_p",
    "topP",
    "max_tokens",
    "maxTokens",
    "max_completion_tokens",
    "presence_penalty",
    "frequency_penalty",
    "reasoning_effort"
  ]) {
    const value = record[key];
    if (typeof value === "string" || typeof value === "number") {
      params[key] = typeof value === "string" ? redactString(value) : value;
    }
  }
  return Object.keys(params).length > 0 ? params : void 0;
}
function getMessageFromEvent(event) {
  if (event.message && typeof event.message === "object") {
    return event.message;
  }
  if (event.role || event.content) {
    return event;
  }
  return void 0;
}
const CACHE_READ_KEY = "cache_read_input_tokens";
const CACHE_WRITE_KEY = "cache_creation_input_tokens";
const CACHE_WRITE_5M_KEY = "input_cache_creation_5m";
const CACHE_WRITE_1H_KEY = "input_cache_creation_1h";
function extractUsageCount(usage, keys) {
  for (const key of keys) {
    if (!Object.hasOwn(usage, key)) continue;
    const value = usage[key];
    if (typeof value === "number" && Number.isFinite(value) && Number.isInteger(value) && value >= 0) {
      return value;
    }
  }
  return void 0;
}
function splitCacheWrite(cacheWrite, cacheWrite1h) {
  if (cacheWrite === void 0) {
    return {};
  }
  const longWrite = Math.min(Math.max(cacheWrite1h, 0), cacheWrite);
  if (!longWrite) {
    return { [CACHE_WRITE_KEY]: cacheWrite };
  }
  const shortWrite = cacheWrite - longWrite;
  return {
    ...shortWrite ? { [CACHE_WRITE_5M_KEY]: shortWrite } : {},
    [CACHE_WRITE_1H_KEY]: longWrite
  };
}
const REASONING_KEY = "output_reasoning_tokens";
function splitReasoning(output, reasoning, enabled) {
  if (!enabled) {
    return { output };
  }
  const bounded = Math.min(Math.max(reasoning, 0), output);
  if (!bounded) {
    return { output };
  }
  return { output: output - bounded, [REASONING_KEY]: bounded };
}
function extractUsage(messageOrEvent, options = getUsageOptions()) {
  const usage = messageOrEvent.usage ?? (messageOrEvent.message && typeof messageOrEvent.message === "object" ? messageOrEvent.message.usage : void 0);
  if (!usage || typeof usage !== "object") {
    return void 0;
  }
  const input = Number(usage.input ?? usage.inputTokens ?? usage.prompt_tokens ?? usage.promptTokens ?? 0);
  const output = Number(usage.output ?? usage.outputTokens ?? usage.completion_tokens ?? usage.completionTokens ?? 0);
  const total = Number(usage.total ?? usage.totalTokens ?? usage.total_tokens ?? input + output);
  const cacheRead = extractUsageCount(usage, ["cacheRead", "cache_read", "cachedTokens"]);
  const cacheWrite = extractUsageCount(usage, ["cacheWrite", "cache_write"]);
  const cacheWrite1h = extractUsageCount(usage, ["cacheWrite1h", "cache_write_1h"]) ?? 0;
  const reasoning = Number(
    usage.reasoning ?? usage.reasoningTokens ?? usage.reasoning_tokens ?? usage.thoughtsTokenCount ?? 0
  );
  return {
    input,
    ...splitReasoning(output, reasoning, options.splitReasoningTokens),
    total,
    ...cacheRead !== void 0 ? { [CACHE_READ_KEY]: cacheRead } : {},
    ...splitCacheWrite(cacheWrite, cacheWrite1h)
  };
}
function extractCacheMetrics(messageOrEvent) {
  const usage = messageOrEvent.usage ?? (messageOrEvent.message && typeof messageOrEvent.message === "object" ? messageOrEvent.message.usage : void 0);
  if (!usage || typeof usage !== "object") return void 0;
  const uncachedInputTokens = extractUsageCount(
    usage,
    ["input", "inputTokens", "prompt_tokens", "promptTokens"]
  ) ?? 0;
  const cacheReadTokens = extractUsageCount(usage, ["cacheRead", "cache_read", "cachedTokens"]) ?? 0;
  const cacheWriteTokens = extractUsageCount(usage, ["cacheWrite", "cache_write"]) ?? 0;
  const denominator = uncachedInputTokens + cacheReadTokens;
  return {
    cacheReadTokens,
    cacheWriteTokens,
    uncachedInputTokens,
    ...denominator > 0 ? { cacheHitRatio: cacheReadTokens / denominator } : {}
  };
}
function extractCostDetails(messageOrEvent) {
  const usage = messageOrEvent.usage ?? (messageOrEvent.message && typeof messageOrEvent.message === "object" ? messageOrEvent.message.usage : void 0);
  const cost = messageOrEvent.cost ?? usage?.cost ?? messageOrEvent.costDetails;
  if (!cost || typeof cost !== "object") {
    return void 0;
  }
  const input = Number(cost.input ?? cost.inputCost ?? 0);
  const output = Number(cost.output ?? cost.outputCost ?? 0);
  const cacheRead = Number(cost.cacheRead ?? cost.cache_read ?? 0);
  const cacheWrite = Number(cost.cacheWrite ?? cost.cache_write ?? 0);
  const total = Number(cost.total ?? cost.totalCost ?? input + output + cacheRead + cacheWrite);
  if (input === 0 && output === 0 && cacheRead === 0 && cacheWrite === 0 && total === 0) {
    return void 0;
  }
  return {
    input,
    output,
    total,
    ...cacheRead ? { [CACHE_READ_KEY]: cacheRead } : {},
    ...cacheWrite ? { [CACHE_WRITE_KEY]: cacheWrite } : {}
  };
}
function extractModelIdentity(value, provider) {
  const record = value && typeof value === "object" ? value : void 0;
  const model = record?.id ?? record?.model ?? value;
  const actualProvider = provider ?? record?.provider;
  return {
    ...typeof model === "string" && model ? { model } : {},
    ...typeof actualProvider === "string" && actualProvider ? { provider: actualProvider } : {}
  };
}
function extractToolUsage(event) {
  const result = event.result && typeof event.result === "object" ? event.result : {};
  const source = { usage: event.usage ?? result.usage, cost: event.cost ?? result.cost };
  return { usageDetails: extractUsage(source), costDetails: extractCostDetails(source) };
}
function extractResponseMetadata(event) {
  return shapePayload(
    {
      status: event.status ?? event.statusCode ?? event.httpStatus,
      headers: event.headers,
      responseHeaders: event.responseHeaders,
      providerMetadata: event.providerMetadata ?? event.metadata,
      requestId: event.requestId ?? event.providerRequestId
    },
    { depth: 4, maxString: 4e3 }
  );
}
export {
  extractAssistantOutput,
  extractCacheMetrics,
  extractCostDetails,
  extractFinalAssistant,
  extractModelIdentity,
  extractModelParameters,
  extractResponseMetadata,
  extractTextContent,
  extractToolCalls,
  extractToolUsage,
  extractUsage,
  getCapturePolicy,
  getLimits,
  getMessageFromEvent,
  getProviderPayload,
  getRequestKey,
  getToolCallId,
  getToolInput,
  getToolName,
  inferToolUpdateTransport,
  normalizeContentForLangfuse,
  prepareToolPayload,
  shapePayload,
  truncate,
  tryParseJson
};
