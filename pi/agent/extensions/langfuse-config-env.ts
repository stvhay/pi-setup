import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const agentDir = process.env.PI_CODING_AGENT_DIR || resolve(homedir(), ".pi", "agent");
type LangfuseFactory = (pi: ExtensionAPI) => void | Promise<void>;
type JsonObject = Record<string, unknown>;
type EventHandler = (event: unknown, ctx: unknown) => unknown | Promise<unknown>;

const MAX_TELEMETRY_MESSAGES = 50;
const MAX_TELEMETRY_BLOCKS = 50;
const MAX_TELEMETRY_TEXT_CHARS = 12_000;
const MAX_TELEMETRY_MEDIA_CHARS = 10_000_000;
const SAFE_PAYLOAD_FIELDS = [
  "id",
  "requestId",
  "request_id",
  "providerRequestId",
  "messageId",
  "turnId",
  "turnIndex",
  "provider",
  "model",
  "modelId",
  "temperature",
  "top_p",
  "topP",
  "max_tokens",
  "maxTokens",
  "max_completion_tokens",
  "presence_penalty",
  "frequency_penalty",
  "reasoning_effort",
] as const;
const SAFE_EVENT_FIELDS = [
  "id",
  "requestId",
  "request_id",
  "providerRequestId",
  "messageId",
  "turnId",
  "turnIndex",
  "sessionId",
  "provider",
  "model",
  "modelId",
  "url",
  "method",
] as const;
const SAFE_MESSAGE_FIELDS = [
  ...SAFE_EVENT_FIELDS,
  "api",
  "timestamp",
  "finishReason",
  "stopReason",
] as const;
const SAFE_USAGE_FIELDS = [
  "input",
  "inputTokens",
  "prompt_tokens",
  "promptTokens",
  "output",
  "outputTokens",
  "completion_tokens",
  "completionTokens",
  "total",
  "totalTokens",
  "total_tokens",
  "cacheRead",
  "cache_read",
  "cachedTokens",
  "cacheWrite",
  "cache_write",
] as const;
const SAFE_COST_FIELDS = [
  "input",
  "inputCost",
  "output",
  "outputCost",
  "total",
  "totalCost",
  "cacheRead",
  "cache_read",
  "cacheWrite",
  "cache_write",
] as const;
const PROVIDER_PAYLOAD_ALIASES = ["request", "payload", "body", "providerPayload", "messages"] as const;
const PACKAGE_CONVERSATION_EVENTS = new Set(["message_update", "message_end", "turn_end", "agent_end"]);
const PROVIDER_ROLES = ["user", "assistant", "model"] as const;
const CONVERSATION_ROLES = ["user", "assistant"] as const;

function asObject(value: unknown): JsonObject | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonObject
    : undefined;
}

function takeText(value: unknown, budget: { remaining: number }): string | undefined {
  if (typeof value !== "string" || budget.remaining <= 0) return undefined;
  const text = value.slice(0, Math.min(MAX_TELEMETRY_TEXT_CHARS, budget.remaining));
  budget.remaining -= text.length;
  return text;
}

function takeMedia(value: unknown, budget: { remaining: number }): string | undefined {
  if (typeof value !== "string" || value.length > budget.remaining) return undefined;
  budget.remaining -= value.length;
  return value;
}

function sanitizeMediaSource(value: unknown, budget: { remaining: number }): JsonObject | undefined {
  const source = asObject(value);
  if (!source || (source.type !== "base64" && source.type !== "url")) return undefined;
  const output: JsonObject = { type: source.type };
  for (const key of ["media_type", "mediaType"] as const) {
    if (typeof source[key] === "string") output[key] = source[key].slice(0, 128);
  }
  const media = source.type === "base64"
    ? takeMedia(source.data, budget)
    : takeMedia(source.url, budget);
  if (media === undefined) return undefined;
  output[source.type === "base64" ? "data" : "url"] = media;
  return output;
}

function sanitizeContentBlock(value: unknown, role: string, budget: { remaining: number }): JsonObject | undefined {
  const block = asObject(value);
  if (!block) return undefined;
  const type = typeof block.type === "string" ? block.type : undefined;
  const textType = type === "text"
    || (role === "user" && type === "input_text")
    || ((role === "assistant" || role === "model") && type === "output_text");
  if (textType || (type === undefined && Object.keys(block).length === 1 && typeof block.text === "string")) {
    const text = takeText(block.text, budget);
    if (text === undefined) return undefined;
    return type === undefined ? { text } : { type, text };
  }
  if ((type === "image" || type === "document") && block.source) {
    const source = sanitizeMediaSource(block.source, budget);
    return source ? { type, source } : undefined;
  }

  if (type === "image_url" || type === "input_image") {
    const raw = asObject(block.image_url);
    const url = takeMedia(raw?.url ?? block.image_url, budget);
    if (url !== undefined) {
      return raw
        ? { type, image_url: { url, ...(typeof raw.detail === "string" ? { detail: raw.detail.slice(0, 16) } : {}) } }
        : { type, image_url: url };
    }
    if (typeof block.file_id === "string") return { type, file_id: block.file_id.slice(0, 512) };
  }

  const inlineData = asObject(block.inlineData);
  if (type === undefined && Object.keys(block).length === 1 && inlineData) {
    const data = takeMedia(inlineData.data, budget);
    if (data !== undefined && typeof inlineData.mimeType === "string") {
      return { inlineData: { mimeType: inlineData.mimeType.slice(0, 128), data } };
    }
  }
  return undefined;
}

function copyScalarFields(source: JsonObject, output: JsonObject, fields: readonly string[]) {
  for (const key of fields) {
    const value = source[key];
    if (typeof value === "string") output[key] = value.slice(0, 512);
    else if (typeof value === "number" && Number.isFinite(value)) output[key] = value;
  }
}

function sanitizeNumbers(value: unknown, fields: readonly string[]): JsonObject | undefined {
  const source = asObject(value);
  if (!source) return undefined;
  const output: JsonObject = {};
  for (const key of fields) {
    const field = source[key];
    if (typeof field === "number" && Number.isFinite(field)) output[key] = field;
    else if (typeof field === "string" && field.trim() && Number.isFinite(Number(field))) output[key] = field;
  }
  return Object.keys(output).length > 0 ? output : undefined;
}

function sanitizeUsage(value: unknown): JsonObject | undefined {
  const source = asObject(value);
  if (!source) return undefined;
  const output = sanitizeNumbers(source, SAFE_USAGE_FIELDS) ?? {};
  const cost = sanitizeNumbers(source.cost, SAFE_COST_FIELDS);
  if (cost) output.cost = cost;
  return Object.keys(output).length > 0 ? output : undefined;
}

function sanitizeMessage(
  value: unknown,
  budget: { remaining: number },
  roles: readonly string[],
): JsonObject | undefined {
  const message = asObject(value);
  const role = message?.role;
  if (typeof role !== "string" || !roles.includes(role)) return undefined;

  const output: JsonObject = { role };
  copyScalarFields(message, output, SAFE_MESSAGE_FIELDS);
  const usage = sanitizeUsage(message.usage);
  if (usage) output.usage = usage;
  const cost = sanitizeNumbers(message.cost, SAFE_COST_FIELDS);
  if (cost) output.cost = cost;
  const costDetails = sanitizeNumbers(message.costDetails, SAFE_COST_FIELDS);
  if (costDetails) output.costDetails = costDetails;

  if (typeof message.content === "string") {
    const content = takeText(message.content, budget);
    if (content !== undefined) output.content = content;
  } else {
    const source = Array.isArray(message.content)
      ? message.content
      : Array.isArray(message.parts) ? message.parts : undefined;
    const content = source
      ?.slice(0, MAX_TELEMETRY_BLOCKS)
      .map((block) => sanitizeContentBlock(block, role, budget))
      .filter((block): block is JsonObject => block !== undefined);
    if (content?.length) output[Array.isArray(message.parts) ? "parts" : "content"] = content;
  }

  return Object.keys(output).length > 1 ? output : undefined;
}

function sanitizeMessages(
  value: unknown,
  budget: { remaining: number },
  roles: readonly string[] = PROVIDER_ROLES,
): JsonObject[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const messages = value
    .slice(0, MAX_TELEMETRY_MESSAGES)
    .map((message) => sanitizeMessage(message, budget, roles))
    .filter((message): message is JsonObject => message !== undefined);
  return messages.length > 0 ? messages : undefined;
}

function sanitizeProviderPayload(
  value: unknown,
  budget = { remaining: MAX_TELEMETRY_MEDIA_CHARS },
): JsonObject | undefined {
  const payload = asObject(value);
  if (!payload) return undefined;
  const output: JsonObject = {};
  copyScalarFields(payload, output, SAFE_PAYLOAD_FIELDS);
  for (const key of ["messages", "input", "contents"] as const) {
    const messages = sanitizeMessages(payload[key], budget);
    if (messages) output[key] = messages;
  }
  return output;
}

function sanitizeProviderEvent(value: unknown): JsonObject {
  const event = asObject(value);
  const output: JsonObject = { type: "before_provider_request" };
  if (!event) {
    output.payload = {};
    return output;
  }
  copyScalarFields(event, output, SAFE_EVENT_FIELDS);

  const budget = { remaining: MAX_TELEMETRY_MEDIA_CHARS };
  let foundAlias = false;
  for (const alias of PROVIDER_PAYLOAD_ALIASES) {
    if (!Object.hasOwn(event, alias)) continue;
    foundAlias = true;
    output[alias] = alias === "messages"
      ? sanitizeMessages(event[alias], budget)
      : sanitizeProviderPayload(event[alias], budget);
  }
  if (!foundAlias) output.payload = sanitizeProviderPayload(event, budget) ?? {};
  return output;
}

function sanitizeConversationEvent(eventName: string, value: unknown): JsonObject {
  const event = asObject(value);
  const output: JsonObject = { type: eventName };
  if (!event) return output;
  copyScalarFields(event, output, SAFE_MESSAGE_FIELDS);
  const usage = sanitizeUsage(event.usage);
  if (usage) output.usage = usage;
  const cost = sanitizeNumbers(event.cost, SAFE_COST_FIELDS);
  if (cost) output.cost = cost;
  const costDetails = sanitizeNumbers(event.costDetails, SAFE_COST_FIELDS);
  if (costDetails) output.costDetails = costDetails;

  const budget = { remaining: MAX_TELEMETRY_MEDIA_CHARS };
  const message = sanitizeMessage(event.message, budget, CONVERSATION_ROLES);
  if (message) output.message = message;
  const messages = sanitizeMessages(event.messages, budget, CONVERSATION_ROLES);
  if (messages) output.messages = messages;
  if (!Object.hasOwn(event, "message") && !Object.hasOwn(event, "messages")) {
    const direct = sanitizeMessage(event, budget, CONVERSATION_ROLES);
    if (direct) Object.assign(output, direct);
  }
  return output;
}

function langfuseTelemetryApi(pi: ExtensionAPI): ExtensionAPI {
  return new Proxy(pi, {
    get(target, property, receiver) {
      if (property === "on") {
        return (event: string, handler: EventHandler) => {
          if (event !== "before_provider_request" && !PACKAGE_CONVERSATION_EVENTS.has(event)) {
            (target.on as unknown as (event: string, handler: EventHandler) => void)(event, handler);
            return;
          }
          (target.on as unknown as (event: string, handler: EventHandler) => void)(event, async (packageEvent, ctx) => {
            await handler(
              event === "before_provider_request"
                ? sanitizeProviderEvent(packageEvent)
                : sanitizeConversationEvent(event, packageEvent),
              ctx,
            );
          });
        };
      }
      const value = Reflect.get(target, property, receiver);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}

export default async function langfuseConfigEnv(pi?: ExtensionAPI) {
  // Truncating data URIs corrupts media before Langfuse can extract it.
  process.env.PI_LANGFUSE_MAX_STRING_LENGTH ||= "off";

  process.env.LANGFUSE_PRIVACY_PRESET = "conversations";
  process.env.LANGFUSE_CAPTURE_TOOL_IO = "false";
  process.env.LANGFUSE_CAPTURE_SYSTEM_PROMPT = "false";
  process.env.LANGFUSE_CAPTURE_CWD = "false";

  try {
    const config = JSON.parse(
      readFileSync(resolve(agentDir, "pi-langfuse", "config.json"), "utf8"),
    ) as Record<string, unknown>;
    const values = {
      LANGFUSE_PUBLIC_KEY: config.publicKey,
      LANGFUSE_SECRET_KEY: config.secretKey,
      LANGFUSE_BASE_URL: config.host,
    };

    for (const [name, value] of Object.entries(values)) {
      if (!process.env[name] && typeof value === "string" && value) process.env[name] = value;
    }
  } catch {
    // pi-langfuse handles missing or invalid config during its own setup.
  }

  if (!pi) return;

  pi?.on("session_start", (event, ctx) => {
    if (event.reason !== "startup" || !ctx.hasUI) return;
    void pi.exec(resolve(agentDir, "bin", "agnt"), ["langfuse", "check", "--quiet"], { timeout: 5000 }).then(({ code }) => {
      if (code === 1) ctx.ui.notify("Langfuse evaluator configuration is outdated; run `agnt langfuse apply`.", "warning");
    }).catch(() => {});
  });

  const originalModels = new WeakMap<object, string>();
  pi.on("message_end", ({ message }) => {
    if (message.role !== "assistant" || message.provider !== "openai-codex") return;

    const telemetryMessage = {
      ...message,
      model: `${message.model}-subscription`,
      usage: {
        ...message.usage,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
    };
    originalModels.set(telemetryMessage, message.model);
    return { message: telemetryMessage };
  });

  const require = createRequire(resolve(agentDir, "npm", "package.json"));
  const langfuseEntry = require.resolve("pi-langfuse");
  const { default: registerLangfuse } = await import(pathToFileURL(langfuseEntry).href) as {
    default: LangfuseFactory;
  };
  await registerLangfuse(langfuseTelemetryApi(pi));

  pi.on("message_end", ({ message }) => {
    const originalModel = originalModels.get(message);
    if (originalModel === undefined) return;
    return { message: { ...message, model: originalModel } };
  });
}
