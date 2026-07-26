import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";

export default function langfuseConfigEnv() {
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
}
