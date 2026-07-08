// olla-provider.ts
//
// Registers up to three Pi providers:
//   - ollama:     localhost ollama daemon (whatever you have locally pulled)
//   - olla-local: optional remote ollama-compatible upstream
//   - olla-cloud: optional remote OpenAI-compatible upstream
//
// Why split olla-local vs olla-cloud: /olla/openai/v1/models lists everything
// (cloud + local mixed), but /olla/openai/v1/chat/completions only routes cloud
// upstreams. Local-tagged ids 404 at chat time. /olla/ollama/v1 is the routable
// surface for ollama models. Cloud-only = ids in /openai minus ids in /ollama.
//
// localhost ollama is registered as a separate provider so heavy local models
// (e.g. gemma4:31b) skip the network hop. Same model id may appear under both
// `ollama` and `olla-local` — pick whichever via /model.
//
// Loaded from ~/.pi/agent/extensions/ via jiti.

const OLLA_HOST = (process.env.OLLA_HOST ?? "").replace(/\/$/, "");
// baseUrl MUST include /v1 — Pi's openai-completions adapter does not append it.
const CLOUD_BASE = OLLA_HOST ? `${OLLA_HOST}/olla/openai/v1` : null;
const LOCAL_BASE = OLLA_HOST ? `${OLLA_HOST}/olla/ollama/v1` : null;
const LOCALHOST_BASE = "http://localhost:11434/v1";

const VISION_PATTERNS: RegExp[] = [
  /^claude-/,
  /^gpt-4\.1/,
  /^gemini-/,
  /^gemma3:/,
  /^gemma4:/,
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
const REASONING_PATTERNS: RegExp[] = [/^deepseek-r1/, /^glm-5\.2$/];

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
];

// Olla's /v1/models endpoint only returns ids, so keep a conservative metadata
// table here. Prefer under-promising to Pi over advertising a giant context that
// may be unusably slow or rejected by the upstream router.
const CLOUD_METADATA: Array<[RegExp, ModelMetadata]> = [
  [/^gpt-4\.1(?:-mini)?$/, { contextWindow: 1047576, maxTokens: 32768 }],
  [/^gemini-(?:pro|flash|flash-lite)$/, { contextWindow: 1048576, maxTokens: 65536 }],
  [/^claude-(?:sonnet|haiku)$/, { contextWindow: 200000, maxTokens: 16384 }],
  [/^deepseek-(?:r1|v3\.2)$/, { contextWindow: 128000, maxTokens: 16384 }],
  [/^glm-5\.2$/, { contextWindow: 999424, maxTokens: 131072 }],
  [/^llama-3\.3-70b$/, { contextWindow: 128000, maxTokens: 8192 }],
];

// Remote olla-local and localhost ollama. Values are model-native context where
// known, with local-friendly output caps. Very large contexts are real for some
// models but can be slow/VRAM hungry, especially on the 4070 Ti backend.
const OLLAMA_METADATA: Array<[RegExp, ModelMetadata]> = [
  [/^gemma4:(?:31b|26b)$/, { contextWindow: 262144, maxTokens: 32768 }],
  [/^gemma4:e[24]b$/, { contextWindow: 131072, maxTokens: 32768 }],
  [/^gemma3:(?:12b|4b)$/, { contextWindow: 128000, maxTokens: 8192 }],
  [/^deepseek-coder-v2:16b$/, { contextWindow: 163840, maxTokens: 8192 }],
  [/^deepseek-r1:14b$/, { contextWindow: 131072, maxTokens: 8192 }],
  [/^llama3\.1:8b$/, { contextWindow: 131072, maxTokens: 8192 }],
  [/^qwen2\.5:14b$/, { contextWindow: 32768, maxTokens: 8192 }],
  [/^qwen3:(?:8b|4b)$/, { contextWindow: 40960, maxTokens: 8192 }],
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

function getThinkingLevelMap(_id: string): ThinkingLevelMap | null {
  return null;
}

function getCompat(id: string, reasoning: boolean) {
  if (id === "glm-5.2") {
    return {
      supportsStore: false,
      supportsDeveloperRole: false,
      // Olla routes GLM 5.2 through OpenRouter. Although the model reasons
      // natively, this proxy rejects Pi's OpenAI reasoning/thinking params.
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

function isKnownOllaCloudModel(id: string): boolean {
  return KNOWN_OLLA_CLOUD_MODEL_IDS.includes(id);
}

function buildModels(ids: string[], surface: ProviderSurface) {
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
  const [cloudIdsRaw, localIdsRaw, hostIdsRaw] = await Promise.all([
    fetchModelIds(CLOUD_BASE),
    fetchModelIds(LOCAL_BASE),
    fetchModelIds(LOCALHOST_BASE),
  ]);
  const cloudIds = withKnownOllaCloudIds(cloudIdsRaw);
  const localIds = localIdsRaw?.filter((id) => !isKnownOllaCloudModel(id)) ?? null;
  const hostIds = hostIdsRaw?.filter((id) => !isKnownOllaCloudModel(id)) ?? null;

  if (cloudIds === null && localIds === null && hostIds === null) {
    pi.logger?.warn?.("olla-provider: no remote OLLA_HOST configured/reachable and localhost is unreachable — no providers registered");
    return;
  }

  if (hostIds && hostIds.length > 0) {
    const { models, skipped } = buildModels(hostIds, "ollama");
    if (models.length > 0) {
      pi.registerProvider("ollama", {
        baseUrl: LOCALHOST_BASE,
        apiKey: "ollama",
        api: "openai-completions",
        authHeader: true,
        models,
      });
      pi.logger?.info?.(
        `olla-provider: ollama registered ${models.length} models from localhost (skipped ${skipped.length}: ${skipped.join(", ") || "none"})`,
      );
    }
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

  // Cloud-only = ids in /openai minus ids in /ollama (those route through litellm only).
  const localSet = new Set(localIds ?? []);
  const cloudOnlyIds = (cloudIds ?? []).filter((id) => isKnownOllaCloudModel(id) || !localSet.has(id));

  if (cloudOnlyIds.length > 0) {
    const { models, skipped } = buildModels(cloudOnlyIds, "cloud");
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
