import { chmodSync, mkdirSync, readFileSync, existsSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { CONFIG_PATH, DEFAULT_LANGFUSE_HOST } from "./constants.js";
import { state } from "./state.js";
import { forceShutdownRuntime } from "./langfuse.js";
import { createCapturePolicy } from "./capture-policy.js";
import { createPayloadLimits } from "./limits.js";
import { createUsageOptions } from "./usage-options.js";
const MAX_LANGFUSE_USER_ID_LENGTH = 200;
function normalizeUserId(value) {
  if (typeof value !== "string") {
    return void 0;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, MAX_LANGFUSE_USER_ID_LENGTH) : void 0;
}
function loadConfigFromFile(path = CONFIG_PATH, env = process.env) {
  if (existsSync(path)) {
    try {
      const content = readFileSync(path, "utf-8");
      const config = JSON.parse(content);
      if (config.publicKey && config.secretKey) {
        const captureSource = {
          ...config.capture ?? {},
          ...config.privacyPreset ? { LANGFUSE_PRIVACY_PRESET: config.privacyPreset } : {},
          ...env
        };
        return {
          publicKey: config.publicKey,
          secretKey: config.secretKey,
          host: config.host || DEFAULT_LANGFUSE_HOST,
          userId: normalizeUserId(config.userId) ?? normalizeUserId(env.LANGFUSE_USER_ID),
          capturePolicy: createCapturePolicy(captureSource),
          limits: createPayloadLimits(env),
          usage: createUsageOptions(captureSource)
        };
      }
    } catch (e) {
      console.warn("\u{1F4CA} Langfuse: Failed to load config.json", e);
    }
  }
  return null;
}
function loadConfigFromEnv(env = process.env) {
  const publicKey = env.LANGFUSE_PUBLIC_KEY || "";
  const secretKey = env.LANGFUSE_SECRET_KEY || "";
  if (!publicKey || !secretKey) {
    return null;
  }
  return {
    publicKey,
    secretKey,
    host: env.LANGFUSE_BASE_URL || env.LANGFUSE_HOST || DEFAULT_LANGFUSE_HOST,
    userId: normalizeUserId(env.LANGFUSE_USER_ID),
    capturePolicy: createCapturePolicy(env),
    limits: createPayloadLimits(env),
    usage: createUsageOptions(env)
  };
}
function loadConfig(env = process.env, path = CONFIG_PATH) {
  return loadConfigFromFile(path, env) || loadConfigFromEnv(env);
}
function saveConfig(config, path = CONFIG_PATH) {
  mkdirSync(dirname(path), { recursive: true, mode: 448 });
  chmodSync(dirname(path), 448);
  writeFileSync(path, `${JSON.stringify(config, null, 2)}
`, { encoding: "utf-8", mode: 384 });
  chmodSync(path, 384);
}
function maskPublicKey(value) {
  if (value.length <= 9) {
    return "[REDACTED_SECRET]";
  }
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}
function sanitizeConfigForLog(config) {
  if (!config) {
    return null;
  }
  return {
    publicKey: maskPublicKey(config.publicKey),
    secretKey: "[REDACTED_SECRET]",
    host: config.host || DEFAULT_LANGFUSE_HOST
  };
}
async function collectConfigFromUI(ctx, reason) {
  if (!ctx.hasUI) {
    console.log(`\u{1F4CA} Langfuse: ${reason}. Run this extension in Pi UI to complete setup, or set LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL.`);
    return null;
  }
  ctx.ui.notify("Langfuse setup required. Enter your API keys to enable tracing.", "info");
  const publicKey = (await ctx.ui.input("Langfuse public key:", "pk-lf-..."))?.trim();
  if (!publicKey) {
    ctx.ui.notify("Langfuse setup cancelled.", "warning");
    return null;
  }
  const secretKey = (await ctx.ui.input("Langfuse secret key:", "sk-lf-..."))?.trim();
  if (!secretKey) {
    ctx.ui.notify("Langfuse setup cancelled.", "warning");
    return null;
  }
  const hostInput = (await ctx.ui.input("Langfuse host:", DEFAULT_LANGFUSE_HOST))?.trim();
  const userId = normalizeUserId(await ctx.ui.input("Langfuse user ID (optional):", ""));
  return {
    publicKey,
    secretKey,
    host: hostInput || DEFAULT_LANGFUSE_HOST,
    ...userId ? { userId } : {},
    capturePolicy: createCapturePolicy()
  };
}
async function saveConfigFromUI(ctx, config) {
  state.config = config;
  try {
    saveConfig(state.config);
    ctx.ui.notify(`Langfuse config saved to ${CONFIG_PATH}`, "info");
    return true;
  } catch (error) {
    console.warn("\u{1F4CA} Langfuse: Failed to save config.json", error);
    ctx.ui.notify(`Failed to save Langfuse config.json to ${CONFIG_PATH}. Check Pi config directory permissions.`, "error");
    state.config = null;
    return false;
  }
}
async function ensureConfig(ctx) {
  if (!state.config) {
    state.config = loadConfig();
  }
  if (state.config) {
    return true;
  }
  if (state.setupAttemptedThisSession) {
    return false;
  }
  state.setupAttemptedThisSession = true;
  const config = await collectConfigFromUI(ctx, "Missing config");
  if (!config) {
    return false;
  }
  return saveConfigFromUI(ctx, config);
}
async function promptForConfig(ctx) {
  state.setupAttemptedThisSession = false;
  state.config = null;
  await forceShutdownRuntime();
  const config = await collectConfigFromUI(ctx, "Manual setup requested");
  if (!config) {
    state.config = loadConfig();
    return false;
  }
  const saved = await saveConfigFromUI(ctx, config);
  if (saved) {
    ctx.ui.notify("Langfuse tracing enabled for future agent runs.", "info");
  }
  return saved;
}
export {
  ensureConfig,
  loadConfig,
  loadConfigFromEnv,
  loadConfigFromFile,
  promptForConfig,
  sanitizeConfigForLog,
  saveConfig
};
