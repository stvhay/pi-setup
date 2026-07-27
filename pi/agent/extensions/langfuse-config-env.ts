import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";

export default function langfuseConfigEnv(pi?: {
  on: (event: "message_end", handler: (event: { message: Record<string, any> }) => unknown) => void;
}) {
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
