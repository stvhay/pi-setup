import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { format, inspect } from "node:util";

export const REDACTED = "[REDACTED_CREDENTIAL]";

const PRIVATE_KEY_RE = /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/gi;
const KNOWN_CREDENTIAL_RE = /\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|npm_[A-Za-z0-9_-]{20,}|pypi-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{35}|xox[baprs]-[A-Za-z0-9-]{20,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b/g;
const SENSITIVE_NAME = "(?:[A-Z0-9_-]*(?:API[_-]?KEY|SECRET[_-]?(?:ACCESS[_-]?)?KEY|ACCESS[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE[_-]?KEY|CREDENTIALS?)|AUTHORIZATION|PROXY[_-]?AUTHORIZATION|COOKIE|SET[_-]?COOKIE)";
const SAFE_VALUE_RE = /^(?:\[?REDACTED(?:_[A-Z]+)?\]?|<redacted>|missing|unset|none|null|true|false|invalid|expired|revoked|not[-_ ]?found|configured|present)$/i;
const QUOTED_ASSIGNMENT_RE = new RegExp(
  `((?:["']?)${SENSITIVE_NAME}(?:["']?)\\s*[:=]\\s*)(["'\`])([^\\r\\n]*?)\\2`,
  "gi",
);
const UNQUOTED_ASSIGNMENT_RE = new RegExp(`(${SENSITIVE_NAME}\\s*[:=]\\s*)([^\\s,;}&\\]]+)`, "gi");
const COMMAND_OPTION_RE = /(--(?:api[-_]?key|access[-_]?token|refresh[-_]?token|client[-_]?secret|password|passwd|secret|token|credentials?)(?:=|\s+))(?:(['"`])([^\r\n]*?)\2|([^\s]+))/gi;
const AUTH_HEADER_RE = /(\b(?:authorization|proxy-authorization)\s*[:=]\s*)(?:bearer|basic|token)\s+[^\s,;}&\]]+/gi;
const COOKIE_HEADER_RE = /(^|[\r\n])(\s*(?:set-cookie|cookie)\s*:\s*)[^\r\n]*/gi;
const QUERY_CREDENTIAL_RE = /([?&;](?:access[_-]?token|refresh[_-]?token|api[_-]?key|client[_-]?secret|password|passwd|secret|token|sig|signature)=)[^&#;\s]+/gi;
const URL_PASSWORD_RE = /([a-z][a-z0-9+.-]*:\/\/[^/\s:@]+:)[^@\s/]+(@)/gi;
const SENSITIVE_FIELD_RE = /(?:apikey|accesskey|secretaccesskey|accesstoken|refreshtoken|clientsecret|secretkey|password|passwd|privatekey|authorization|proxyauthorization|cookie|setcookie|credentials?|token|secret)$/;

function replacement(value: string): string {
  return SAFE_VALUE_RE.test(value.trim()) ? value : REDACTED;
}

export function redactOutputText(value: string): string {
  return value
    .replace(PRIVATE_KEY_RE, REDACTED)
    .replace(URL_PASSWORD_RE, `$1${REDACTED}$2`)
    .replace(QUERY_CREDENTIAL_RE, `$1${REDACTED}`)
    .replace(COOKIE_HEADER_RE, `$1$2${REDACTED}`)
    .replace(AUTH_HEADER_RE, `$1${REDACTED}`)
    .replace(COMMAND_OPTION_RE, (_match, prefix: string, quote: string | undefined, quoted: string | undefined, plain: string | undefined) => {
      const value = quoted ?? plain ?? "";
      const redacted = replacement(value);
      return quote ? `${prefix}${quote}${redacted}${quote}` : `${prefix}${redacted}`;
    })
    .replace(QUOTED_ASSIGNMENT_RE, (_match, prefix: string, quote: string, assigned: string) => `${prefix}${quote}${replacement(assigned)}${quote}`)
    .replace(UNQUOTED_ASSIGNMENT_RE, (_match, prefix: string, assigned: string) => `${prefix}${replacement(assigned)}`)
    .replace(KNOWN_CREDENTIAL_RE, REDACTED);
}

function hasSensitiveField(key: string): boolean {
  return SENSITIVE_FIELD_RE.test(key.replace(/[^a-zA-Z0-9]/g, "").toLowerCase());
}

function redactFieldValue(value: unknown): unknown {
  if (value === null || value === undefined || value === "" || typeof value === "boolean" || typeof value === "number") return value;
  if (typeof value === "string" && SAFE_VALUE_RE.test(value.trim())) return value;
  return REDACTED;
}

function visit(value: unknown, seen: WeakMap<object, unknown>): unknown {
  if (typeof value === "string") return redactOutputText(value);
  if (value === null || value === undefined || typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") return value;
  if (typeof value !== "object") return value;
  if (seen.has(value)) return seen.get(value);

  if (Array.isArray(value)) {
    const output: unknown[] = [];
    seen.set(value, output);
    output.push(...value.map((item) => visit(item, seen)));
    return output;
  }

  if (value instanceof Error) {
    const output = new Error(redactOutputText(value.message));
    seen.set(value, output);
    output.name = redactOutputText(value.name);
    if (value.stack) output.stack = redactOutputText(value.stack);
    for (const [key, item] of Object.entries(value)) {
      (output as unknown as Record<string, unknown>)[key] = hasSensitiveField(key) ? redactFieldValue(item) : visit(item, seen);
    }
    if (value.cause !== undefined) output.cause = visit(value.cause, seen);
    return output;
  }

  if (value instanceof Map) {
    const output = new Map<unknown, unknown>();
    seen.set(value, output);
    for (const [key, item] of value) {
      output.set(visit(key, seen), typeof key === "string" && hasSensitiveField(key) ? redactFieldValue(item) : visit(item, seen));
    }
    return output;
  }

  if (value instanceof Set) {
    const output = new Set<unknown>();
    seen.set(value, output);
    for (const item of value) output.add(visit(item, seen));
    return output;
  }

  if (value instanceof URL) {
    const text = value.toString();
    const redacted = redactOutputText(text);
    return redacted === text ? value : redacted;
  }

  if (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) {
    const rendered = inspect(value, { depth: 10, breakLength: Number.POSITIVE_INFINITY });
    const redacted = redactOutputText(rendered);
    return redacted === rendered ? value : redacted;
  }
  const output: Record<string, unknown> = {};
  seen.set(value, output);
  for (const [key, item] of Object.entries(value)) {
    output[key] = hasSensitiveField(key) ? redactFieldValue(item) : visit(item, seen);
  }
  return output;
}

export function redactOutputValue(value: unknown): unknown {
  return visit(value, new WeakMap<object, unknown>());
}

function redactAssistantMessage<T extends { content: unknown; errorMessage?: string }>(message: T): T {
  const content = redactContent(message.content);
  const errorMessage = message.errorMessage ? redactOutputText(message.errorMessage) : message.errorMessage;
  return content.changed || errorMessage !== message.errorMessage
    ? { ...message, content: content.content, errorMessage } as T
    : message;
}

function redactContent(content: unknown): { content: unknown; changed: boolean } {
  if (!Array.isArray(content)) return { content, changed: false };
  let changed = false;
  const redacted = content.map((part) => {
    if (!part || typeof part !== "object") return part;
    const item = part as Record<string, unknown>;
    if (item.type === "text" && typeof item.text === "string") {
      const text = redactOutputText(item.text);
      if (text !== item.text) {
        changed = true;
        return { ...item, text };
      }
    }
    if (item.type === "thinking" && typeof item.thinking === "string") {
      const thinking = redactOutputText(item.thinking);
      if (thinking !== item.thinking) {
        changed = true;
        return { ...item, thinking };
      }
    }
    return part;
  });
  return { content: changed ? redacted : content, changed };
}

function redactToolPayload(value: unknown): void {
  if (!value || typeof value !== "object") return;
  const payload = value as Record<string, unknown>;
  if ("content" in payload) payload.content = redactContent(payload.content).content;
  if ("details" in payload) payload.details = redactOutputValue(payload.details);
}

export default function outputRedaction(pi: ExtensionAPI): void {
  const consoleMethods = ["log", "error", "warn", "debug"] as const;
  const originalConsole = new Map<(typeof consoleMethods)[number], (...args: unknown[]) => void>();
  const wrappedConsole = new Map<(typeof consoleMethods)[number], (...args: unknown[]) => void>();
  for (const method of consoleMethods) {
    const original = console[method] as (...args: unknown[]) => void;
    const wrapped = (...args: unknown[]) => original.call(console, redactOutputText(format(...args)));
    originalConsole.set(method, original);
    wrappedConsole.set(method, wrapped);
    console[method] = wrapped;
  }

  pi.registerMarkdownTransformer((markdown, context) =>
    context.messageType === "assistant" || context.messageType === "assistant-thinking"
      ? redactOutputText(markdown)
      : markdown,
  );

  pi.on("tool_execution_update", (event) => {
    redactToolPayload(event.partialResult);
  });

  pi.on("tool_execution_end", (event) => {
    redactToolPayload(event.result);
  });

  pi.on("tool_result", (event) => {
    const content = redactContent(event.content);
    const details = redactOutputValue(event.details);
    return { content: content.content as typeof event.content, details };
  });

  pi.on("message_update", (event, ctx) => {
    if (ctx.mode !== "json" && ctx.mode !== "rpc") return;
    const update = event.assistantMessageEvent;
    if (update.type === "text_delta" || update.type === "thinking_delta") {
      update.delta = "";
    } else if (update.type === "text_end" || update.type === "thinking_end") {
      update.content = redactOutputText(update.content);
    } else if (update.type === "done") {
      update.message = redactAssistantMessage(update.message);
    } else if (update.type === "error") {
      update.error = redactAssistantMessage(update.error);
    }
  });

  pi.on("message_end", (event) => {
    if (event.message.role === "assistant") {
      const message = redactAssistantMessage(event.message);
      return message === event.message ? undefined : { message };
    }
    if (event.message.role === "toolResult") {
      return {
        message: {
          ...event.message,
          content: redactContent(event.message.content).content as typeof event.message.content,
          details: redactOutputValue(event.message.details),
        },
      };
    }
  });

  pi.on("session_shutdown", () => {
    for (const method of consoleMethods) {
      if (console[method] === wrappedConsole.get(method)) console[method] = originalConsole.get(method)!;
    }
  });
}
