import { createHash } from "node:crypto";
import { getLimits } from "./limits.js";
import { state } from "./state.js";
const REDACTED = "[REDACTED_SECRET]";
function defaultOptions() {
  const limits = getLimits();
  return {
    maxDepth: limits.maxDepth,
    maxArrayItems: limits.maxArrayItems,
    maxObjectKeys: limits.maxObjectKeys,
    maxStringLength: limits.maxString,
    preserveMedia: false,
    redactPaths: !(state.config?.capturePolicy?.capturePaths ?? false)
  };
}
const MEDIA_DATA_URI_CANDIDATE_RE = /(?<![A-Za-z0-9])data:[^,\s"\\)}\]]*(?:,[^\s"'\\)}\]]*)?/gi;
const MIME_TOKEN = "[!#$%&'*+.^_`|~0-9A-Za-z-]+";
const SAFE_MEDIA_TYPE_RE = new RegExp(`^${MIME_TOKEN}/${MIME_TOKEN}$`);
const BASE64_VALUE_RE = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}(?:==)?|[A-Za-z0-9+/]{3}=?)?$/;
const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const MALFORMED_MEDIA_DATA_URI = "[malformed media data URI]";
const OMITTED_MEDIA_DATA_URI = "[media data URI omitted]";
const SECRET_ASSIGNMENT_RE = /\b([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASS|API[_-]?KEY|PRIVATE[_-]?KEY|AUTH|COOKIE)[A-Z0-9_]*)\s*=\s*([^\s"'`]+)/gi;
const PRIVATE_KEY_RE = /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g;
const BEARER_RE = /\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/gi;
const KNOWN_TOKEN_RE = /\b(?:sk-(?:lf|ant|proj|live|test)[A-Za-z0-9_-]*|pk-lf-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9_]{20,}|npm_[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b/g;
const ABSOLUTE_PATH_RE = /(?:\/Users\/[^/\s]+|\/home\/[^/\s]+|\/private\/tmp|\/tmp|[A-Za-z]:\\Users\\[^\\\s]+)(?:[^\s"'`]*)/g;
const SENSITIVE_FIELD_RE = /^(authorization|cookie|setcookie|xapikey|apikey|token|accesstoken|refreshtoken|secret|secretkey|password|passwd|privatekey)$/;
function hashPath(path) {
  return `[PATH_HASH:${createHash("sha256").update(path).digest("hex").slice(0, 12)}]`;
}
function redactSensitiveText(value, redactPaths = true) {
  const secretsRedacted = value.replace(PRIVATE_KEY_RE, REDACTED).replace(BEARER_RE, REDACTED).replace(KNOWN_TOKEN_RE, REDACTED).replace(SECRET_ASSIGNMENT_RE, (_match, key) => `${key}=${REDACTED}`);
  if (!redactPaths) {
    return secretsRedacted;
  }
  return secretsRedacted.replace(ABSOLUTE_PATH_RE, (path) => {
    const envSuffix = path.match(/([/\\]\.env(?:\.[A-Za-z0-9_-]+)?)$/)?.[1];
    return `${hashPath(envSuffix ? path.slice(0, -envSuffix.length) : path)}${envSuffix ?? ""}`;
  });
}
function hasValidBase64Encoding(value) {
  if (!value || !BASE64_VALUE_RE.test(value)) {
    return false;
  }
  const unpadded = value.replace(/=+$/, "");
  const remainder = unpadded.length % 4;
  const finalIndex = BASE64_ALPHABET.indexOf(unpadded.at(-1) ?? "");
  return remainder === 0 || remainder === 2 && (finalIndex & 15) === 0 || remainder === 3 && (finalIndex & 3) === 0;
}
function isLangfuseMediaDataUri(value) {
  const separator = ";base64,";
  const separatorIndex = value.indexOf(separator);
  if (!value.startsWith("data:") || separatorIndex < 6) {
    return false;
  }
  const mediaType = value.slice(5, separatorIndex);
  const encoded = value.slice(separatorIndex + separator.length);
  return SAFE_MEDIA_TYPE_RE.test(mediaType) && hasValidBase64Encoding(encoded) && redactSensitiveText(value) === value;
}
function mapMediaDataUriSegments(value, replaceMedia, replaceText = (text) => text) {
  let output = "";
  let offset = 0;
  let matched = false;
  for (const match of value.matchAll(MEDIA_DATA_URI_CANDIDATE_RE)) {
    matched = true;
    output += replaceText(value.slice(offset, match.index));
    output += isLangfuseMediaDataUri(match[0]) ? replaceMedia(match[0]) : MALFORMED_MEDIA_DATA_URI;
    offset = match.index + match[0].length;
  }
  return matched ? output + replaceText(value.slice(offset)) : replaceText(value);
}
function truncate(value, maxStringLength) {
  return value.length > maxStringLength ? `${value.slice(0, maxStringLength)}... [truncated]` : value;
}
function redactString(value, options = {}) {
  if (value === MALFORMED_MEDIA_DATA_URI || value === OMITTED_MEDIA_DATA_URI) {
    return value;
  }
  const merged = { ...defaultOptions(), ...options };
  const redactText = (text) => truncate(redactSensitiveText(text, merged.redactPaths), merged.maxStringLength);
  return mapMediaDataUriSegments(
    value,
    merged.preserveMedia ? (media) => media : () => OMITTED_MEDIA_DATA_URI,
    redactText
  );
}
function visit(value, options, depth, seen) {
  if (value === null || value === void 0 || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "bigint") {
    return value.toString();
  }
  if (typeof value === "string") {
    return redactString(value, options);
  }
  if (typeof value === "function" || typeof value === "symbol") {
    return `[${typeof value}]`;
  }
  if (depth <= 0) {
    return `[max depth ${options.maxDepth} reached]`;
  }
  if (value instanceof Error) {
    return {
      name: redactString(value.name, options),
      message: redactString(value.message, options),
      stack: value.stack ? redactString(value.stack, options) : void 0
    };
  }
  if (typeof value !== "object") {
    return redactString(String(value), options);
  }
  if (seen.has(value)) {
    return "[circular]";
  }
  seen.add(value);
  if (Array.isArray(value)) {
    const output2 = value.slice(0, options.maxArrayItems).map((item) => visit(item, options, depth - 1, seen));
    if (value.length > options.maxArrayItems) {
      output2.push(`[${value.length - options.maxArrayItems} truncated items]`);
    }
    return output2;
  }
  const entries = Object.entries(value);
  const output = {};
  for (const [key, item] of entries.slice(0, options.maxObjectKeys)) {
    const normalizedKey = key.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
    output[key] = SENSITIVE_FIELD_RE.test(normalizedKey) ? REDACTED : visit(item, options, depth - 1, seen);
  }
  if (entries.length > options.maxObjectKeys) {
    output.__truncatedKeys = entries.length - options.maxObjectKeys;
  }
  return output;
}
function redactValue(value, options = {}) {
  const merged = { ...defaultOptions(), ...options };
  return visit(value, merged, merged.maxDepth, /* @__PURE__ */ new WeakSet());
}
export {
  MALFORMED_MEDIA_DATA_URI,
  OMITTED_MEDIA_DATA_URI,
  REDACTED,
  hashPath,
  isLangfuseMediaDataUri,
  mapMediaDataUriSegments,
  redactString,
  redactValue
};
