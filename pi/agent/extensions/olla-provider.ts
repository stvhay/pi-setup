// olla-provider.ts
//
// Registers two server-backed Pi providers:
//   - olla-local: remote Ollama-compatible upstream
//   - olla-cloud: remote OpenAI-compatible upstream
//
// Laptop-local Ollama is machine state, registered by an ignored
// ~/.pi/agent/extensions/ollama.local.ts when wanted.
//
// Olla exposes each upstream on its own stable path: /olla/ollama for Knuth's
// local models and /olla/litellm for LiteLLM/OpenRouter cloud aliases.
//
// Loaded from ~/.pi/agent/extensions/ via jiti.

const OLLA_HOST = (process.env.OLLA_HOST ?? "").replace(/\/$/, "");
// baseUrl MUST include /v1 — Pi's openai-completions adapter does not append it.
const CLOUD_BASE = OLLA_HOST ? `${OLLA_HOST}/olla/litellm/v1` : null;
const LOCAL_BASE = OLLA_HOST ? `${OLLA_HOST}/olla/ollama/v1` : null;

const VISION_PATTERNS: RegExp[] = [
  /^claude-/,
  /^gpt-4\.1/,
  /^gemini-/,
  /^gemma-4-31b-it(?::free)?$/,
  /^qwen3\.5-9b$/,
  /^gemma3:/,
  /^gemma4:/,
  /^kimi-k(?:2\.7-code|3)$/,
  /^llava/,
  /^moondream/,
  /^granite3\.3-vision/,
];

// Olla's cloud OpenAI-compatible surface is the same provider used by
// olla-cloud/gpt-4.1-mini. Some Ollama Cloud models may not appear in /v1/models
// until first use, so keep known cloud-only ids here.
const KNOWN_OLLA_CLOUD_MODEL_IDS = ["glm-5.2"];

// Keep this conservative: Pi maps this to reasoning-effort compatibility, which
// is not the same as a model having a native "thinking" capability in Ollama.
const REASONING_PATTERNS: RegExp[] = [
  /^deepseek-r1/,
  /^deepseek-v4-(?:flash|pro)$/,
  /^glm-5\.2$/,
  /^kimi-k(?:2\.7-code|3)$/,
];

// Excluded from registration (not chat-capable through openai-completions).
const SKIP_PATTERNS: RegExp[] = [
  /^bge-/,
  /^all-minilm/,
  /^nomic-embed/,
  /reranker/i,
  /^flux-/,
  /^nano-banana/,
  /^gpt-audio/,
  /granite-docling/,
];

async function fetchModelIds(base: string | null): Promise<string[] | null> {
  if (!base) return null;
  try {
    const res = await fetch(`${base}/models`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = (await res.json()) as { data?: Array<{ id?: string }> };
    return (payload.data ?? [])
      .map((m) => m.id)
      .filter((id): id is string => typeof id === "string");
  } catch {
    return null;
  }
}

type ProviderSurface = "cloud" | "ollama";

type ModelCost = {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
};

type ModelMetadata = {
  contextWindow: number;
  maxTokens: number;
};

type ThinkingLevelMap = Record<string, string | null>;

const DEFAULT_METADATA: ModelMetadata = {
  contextWindow: 128000,
  maxTokens: 16384,
};

const ZERO_COST: ModelCost = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };

// Opportunity-cost rates from OpenRouter, in USD per million tokens. GPT calls
// should still use subscription-backed providers when available; these rates make
// subscription usage comparable in Pi/agnt metrics without routing through OpenRouter.
const CLOUD_COSTS: Array<[RegExp, ModelCost]> = [
  [/^gpt-4\.1$/, { input: 2.0, output: 8.0, cacheRead: 0, cacheWrite: 0 }],
  [/^gpt-4\.1-mini$/, { input: 0.40, output: 1.60, cacheRead: 0, cacheWrite: 0 }],
  [/^gemma-4-31b-it$/, { input: 0.12, output: 0.37, cacheRead: 0, cacheWrite: 0 }],
  [/^qwen3\.5-9b$/, { input: 0.04, output: 0.15, cacheRead: 0, cacheWrite: 0 }],
  [/^qwen3-coder-flash$/, { input: 0.195, output: 0.975, cacheRead: 0.039, cacheWrite: 0.24375 }],
  [/^deepseek-v4-flash$/, { input: 0.0938, output: 0.1876, cacheRead: 0.01876, cacheWrite: 0 }],
  [/^deepseek-v4-pro$/, { input: 0.435, output: 0.87, cacheRead: 0.003625, cacheWrite: 0 }],
];

// Olla's /v1/models endpoint only returns ids, so keep verified upstream
// context/output limits here.
const CLOUD_METADATA: Array<[RegExp, ModelMetadata]> = [
  [/^gpt-4\.1(?:-mini)?$/, { contextWindow: 1047576, maxTokens: 32768 }],
  [/^gemma-4-31b-it$/, { contextWindow: 262144, maxTokens: 262144 }],
  [/^gemma-4-31b-it:free$/, { contextWindow: 262144, maxTokens: 32768 }],
  [/^qwen3\.5-9b$/, { contextWindow: 262144, maxTokens: 262144 }],
  [/^qwen3-coder-flash$/, { contextWindow: 1000000, maxTokens: 65536 }],
  [/^deepseek-v4-flash$/, { contextWindow: 1048576, maxTokens: 393216 }],
  [/^deepseek-v4-pro$/, { contextWindow: 1048576, maxTokens: 384000 }],
  [/^gemini-(?:pro|flash|flash-lite)$/, { contextWindow: 1048576, maxTokens: 65536 }],
  [/^claude-(?:sonnet|haiku)$/, { contextWindow: 200000, maxTokens: 16384 }],
  [/^deepseek-(?:r1|v3\.2)$/, { contextWindow: 128000, maxTokens: 16384 }],
  [/^glm-5\.2$/, { contextWindow: 999424, maxTokens: 131072 }],
  [/^kimi-k2\.7-code$/, { contextWindow: 262144, maxTokens: 32768 }],
  [/^kimi-k3$/, { contextWindow: 1048576, maxTokens: 131072 }],
  [/^llama-3\.3-70b$/, { contextWindow: 128000, maxTokens: 8192 }],
];

// Remote olla-local values reflect Knuth runtime limits where configured.
const OLLAMA_METADATA: Array<[RegExp, ModelMetadata]> = [
  [/^gemma4:(?:31b|26b)$/, { contextWindow: 131072, maxTokens: 32768 }],
  [/^gemma4:e[24]b$/, { contextWindow: 131072, maxTokens: 32768 }],
  [/^gemma3:(?:12b|4b)$/, { contextWindow: 128000, maxTokens: 8192 }],
  [/^deepseek-coder-v2:16b$/, { contextWindow: 163840, maxTokens: 8192 }],
  [/^deepseek-r1:14b$/, { contextWindow: 131072, maxTokens: 8192 }],
  [/^llama3\.1:8b$/, { contextWindow: 131072, maxTokens: 8192 }],
  [/^qwen2\.5:14b$/, { contextWindow: 32768, maxTokens: 8192 }],
  [/^qwen3:(?:8b|4b)$/, { contextWindow: 131072, maxTokens: 8192 }],
  [/^phi4:14b$/, { contextWindow: 16384, maxTokens: 8192 }],
  [/^granite3\.3-vision:2b$/, { contextWindow: 128000, maxTokens: 4096 }],
  [/^llava(?::13b|-llama3:8b)$/, { contextWindow: 4096, maxTokens: 2048 }],
  [/^moondream:1\.8b$/, { contextWindow: 2048, maxTokens: 1024 }],
];

function getMetadata(id: string, surface: ProviderSurface): ModelMetadata {
  const table = surface === "cloud" ? CLOUD_METADATA : OLLAMA_METADATA;
  return table.find(([pattern]) => pattern.test(id))?.[1] ?? DEFAULT_METADATA;
}

function getCost(id: string, surface: ProviderSurface): ModelCost {
  if (surface !== "cloud") return ZERO_COST;
  return CLOUD_COSTS.find(([pattern]) => pattern.test(id))?.[1] ?? ZERO_COST;
}

function getThinkingLevelMap(id: string): ThinkingLevelMap | null {
  if (id === "glm-5.2") {
    return { minimal: null, low: null, medium: null, high: "high", xhigh: "xhigh" };
  }
  if (id === "kimi-k2.7-code") {
    // K2.7 Code always thinks and does not expose effort levels.
    return { off: null };
  }
  if (id === "kimi-k3") {
    // K3 always thinks and currently exposes only max effort.
    return { off: null, minimal: null, low: null, medium: null, high: null, xhigh: null, max: "max" };
  }
  return null;
}

function getCompat(id: string, reasoning: boolean) {
  if (id === "glm-5.2") {
    return {
      supportsStore: false,
      supportsDeveloperRole: false,
      // Olla accepts OpenRouter-compatible nested reasoning controls for GLM.
      supportsReasoningEffort: true,
      thinkingFormat: "openrouter",
    };
  }
  if (/^deepseek-(?:r1|v4-(?:flash|pro))$/.test(id)) {
    return {
      supportsDeveloperRole: false,
      supportsReasoningEffort: true,
      thinkingFormat: "openrouter",
    };
  }
  if (id === "kimi-k2.7-code" || id === "kimi-k3") {
    return {
      supportsDeveloperRole: false,
      // Olla enables Kimi thinking upstream but rejects reasoning_effort.
      supportsReasoningEffort: false,
    };
  }
  return {
    supportsDeveloperRole: false,
    supportsReasoningEffort: reasoning,
  };
}

function withKnownOllaCloudIds(ids: string[] | null): string[] | null {
  if (ids === null) return null;
  return [...new Set([...ids, ...KNOWN_OLLA_CLOUD_MODEL_IDS])];
}

export function buildModels(ids: string[], surface: ProviderSurface) {
  const models = [];
  const skipped: string[] = [];
  for (const id of ids) {
    if (SKIP_PATTERNS.some((p) => p.test(id))) {
      skipped.push(id);
      continue;
    }
    const reasoning = REASONING_PATTERNS.some((p) => p.test(id));
    const vision = VISION_PATTERNS.some((p) => p.test(id));
    const metadata = getMetadata(id, surface);
    const thinkingLevelMap = getThinkingLevelMap(id);
    models.push({
      id,
      name: id,
      reasoning,
      ...(thinkingLevelMap ? { thinkingLevelMap } : {}),
      input: vision ? ["text", "image"] : ["text"],
      // Pi's registerProvider path doesn't apply defaults the way parseModels does
      // (model-registry.js applyProviderConfig copies these fields raw). Setting
      // explicit values avoids a downstream crash in formatTokenCount(undefined).
      cost: getCost(id, surface),
      ...metadata,
      compat: getCompat(id, reasoning),
    });
  }
  return { models, skipped };
}

export default async function olla(pi: any): Promise<void> {
  const [cloudIdsRaw, localIdsRaw] = await Promise.all([
    fetchModelIds(CLOUD_BASE),
    fetchModelIds(LOCAL_BASE),
  ]);
  const cloudIds = withKnownOllaCloudIds(cloudIdsRaw);
  const localIds = localIdsRaw;

  if (cloudIds === null && localIds === null) {
    pi.logger?.warn?.("olla-provider: OLLA_HOST is not configured or reachable — no providers registered");
    return;
  }

  if (localIds && localIds.length > 0) {
    const { models, skipped } = buildModels(localIds, "ollama");
    pi.registerProvider("olla-local", {
      baseUrl: LOCAL_BASE,
      apiKey: "olla",
      api: "openai-completions",
      authHeader: true,
      models,
    });
    pi.logger?.info?.(
      `olla-provider: olla-local registered ${models.length} models (skipped ${skipped.length}: ${skipped.join(", ") || "none"})`,
    );
  }

  if (cloudIds && cloudIds.length > 0) {
    const { models, skipped } = buildModels(cloudIds, "cloud");
    pi.registerProvider("olla-cloud", {
      baseUrl: CLOUD_BASE,
      apiKey: "olla",
      api: "openai-completions",
      authHeader: true,
      models,
    });
    pi.logger?.info?.(
      `olla-provider: olla-cloud registered ${models.length} models (skipped ${skipped.length}: ${skipped.join(", ") || "none"})`,
    );
  }
}
