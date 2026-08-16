import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const agentDir = getAgentDir();
const PROJECTION_OBSERVE_REQUEST = "pi-setup:langfuse-projection-observe";
type LangfuseFactory = (pi: ExtensionAPI) => void | Promise<void>;
type QualityModule = typeof import("pi-langfuse/quality");
type ProjectionObserve = (
  name: string,
  attributes: {
    input?: unknown;
    output?: unknown;
    metadata?: Record<string, unknown>;
    level?: "DEFAULT" | "ERROR";
  },
  options: { asType: "agent"; sessionId?: string; flush?: boolean },
) => void | Promise<void>;

export default async function langfuseConfigEnv(pi?: ExtensionAPI) {
  process.env.LANGFUSE_PRIVACY_PRESET = "conversations";
  process.env.LANGFUSE_CAPTURE_TOOL_IO = "false";
  process.env.LANGFUSE_CAPTURE_TOOL_IO_BYTES = "false";
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

  let langfuseEntry: string | undefined;
  let qualityEntry: string | undefined;
  try {
    const require = createRequire(resolve(agentDir, "npm", "package.json"));
    langfuseEntry = require.resolve("pi-langfuse");
    qualityEntry = require.resolve("pi-langfuse/quality");
  } catch {
    console.error("[langfuse-projection] pi-langfuse package is unavailable");
  }

  let registered = false;
  if (langfuseEntry) {
    try {
      const { default: registerLangfuse } = await import(pathToFileURL(langfuseEntry).href) as {
        default: LangfuseFactory;
      };
      await registerLangfuse(pi);
      registered = true;
    } catch {
      console.error("[langfuse-projection] pi-langfuse registration is unavailable");
    }
  }

  if (registered && pi.events && qualityEntry) {
    try {
      const { createObservationCapturePort } = await import(pathToFileURL(qualityEntry).href) as QualityModule;
      const port = createObservationCapturePort();
      const observe: ProjectionObserve = async (name, attributes, options) => {
        const result = await port.capture({
          name,
          ...attributes,
          sessionId: options.sessionId,
          delivery: options.flush ? "flush" : "buffered",
        });
        if (!result.complete) {
          const gaps = result.gaps.map((gap) => `${gap.scope}:${gap.code}`).join(",");
          throw new Error(`pi-langfuse observation capture was incomplete${gaps ? ` (${gaps})` : ""}`);
        }
      };
      pi.events.on(PROJECTION_OBSERVE_REQUEST, (accept) => {
        if (typeof accept === "function") (accept as (value: ProjectionObserve) => void)(observe);
      });
    } catch {
      console.error("[langfuse-projection] observation capture is unavailable");
    }
  }

  pi.on("message_end", ({ message }) => {
    const originalModel = originalModels.get(message);
    if (originalModel === undefined) return;
    return { message: { ...message, model: originalModel } };
  });
}
