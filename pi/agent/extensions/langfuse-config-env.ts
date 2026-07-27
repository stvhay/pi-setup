import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";

export default function langfuseConfigEnv(pi?: ExtensionAPI) {
  try {
    const config = JSON.parse(
      readFileSync(resolve(homedir(), ".pi", "agent", "pi-langfuse", "config.json"), "utf8"),
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

  pi?.on("session_start", (event, ctx) => {
    if (event.reason !== "startup" || !ctx.hasUI) return;
    void pi.exec("agnt", ["langfuse", "check", "--quiet"], { timeout: 5000 }).then(({ code }) => {
      if (code === 1) ctx.ui.notify("Langfuse evaluator configuration is outdated; run `agnt langfuse apply`.", "warning");
    }).catch(() => {});
  });

  pi?.on("message_end", ({ message }) => {
    if (message.role !== "assistant" || message.provider !== "openai-codex") return;

    const usage = message.usage as Record<string, any>;
    return {
      message: {
        ...message,
        model: `${message.model}-subscription`,
        usage: {
          ...usage,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
      },
    };
  });
}
