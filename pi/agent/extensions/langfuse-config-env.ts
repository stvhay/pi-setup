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
  if (role !== "user") return undefined;

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

function sanitizeMessages(value: unknown, budget: { remaining: number }): JsonObject[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const messages: JsonObject[] = [];
  for (const item of value.slice(0, MAX_TELEMETRY_MESSAGES)) {
    const message = asObject(item);
    const role = message?.role;
    if (role !== "user" && role !== "assistant" && role !== "model") continue;
    if (typeof message.content === "string") {
      const content = takeText(message.content, budget);
      if (content !== undefined) messages.push({ role, content });
      continue;
    }
    const source = Array.isArray(message.content)
      ? message.content
      : Array.isArray(message.parts) ? message.parts : undefined;
    if (!source) continue;
    const content = source
      .slice(0, MAX_TELEMETRY_BLOCKS)
      .map((block) => sanitizeContentBlock(block, role, budget))
      .filter((block): block is JsonObject => block !== undefined);
    if (content.length > 0) messages.push({ role, [Array.isArray(message.parts) ? "parts" : "content"]: content });
  }
  return messages.length > 0 ? messages : undefined;
}

function sanitizeProviderPayload(value: unknown): JsonObject | undefined {
  const payload = asObject(value);
  if (!payload) return undefined;
  const output: JsonObject = {};
  for (const key of SAFE_PAYLOAD_FIELDS) {
    const field = payload[key];
    if (typeof field === "number" || typeof field === "string") {
      output[key] = typeof field === "string" ? field.slice(0, 512) : field;
    }
  }

  const budget = { remaining: MAX_TELEMETRY_MEDIA_CHARS };
  const messages = sanitizeMessages(payload.messages, budget);
  if (messages) output.messages = messages;
  const input = sanitizeMessages(payload.input, budget);
  if (input) output.input = input;
  const contents = sanitizeMessages(payload.contents, budget);
  if (contents) output.contents = contents;
  return output;
}

function langfuseTelemetryApi(pi: ExtensionAPI): ExtensionAPI {
  return new Proxy(pi, {
    get(target, property, receiver) {
      if (property === "on") {
        return (event: string, handler: EventHandler) => {
          if (event !== "before_provider_request") {
            (target.on as unknown as (event: string, handler: EventHandler) => void)(event, handler);
            return;
          }
          target.on("before_provider_request", async (providerEvent, ctx) => {
            await handler({ ...providerEvent, payload: sanitizeProviderPayload(providerEvent.payload) }, ctx);
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
