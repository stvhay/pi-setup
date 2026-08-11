import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { requestProcessReplacement, requireProcessReplacement } from "./lib/process-replacement.ts";

type RestartContext = Pick<ExtensionContext, "mode" | "sessionManager" | "shutdown">;

function restartPi(ctx: RestartContext): void {
  if (ctx.mode !== "tui") throw new Error("/restart requires interactive TUI mode");
  const replacement = requireProcessReplacement("/restart");
  if (!ctx.sessionManager.getSessionFile()) {
    throw new Error("/restart requires a persisted session; restart Pi without --no-session");
  }

  requestProcessReplacement(
    replacement,
    [
      ...replacement.argv,
      "--session-dir",
      ctx.sessionManager.getSessionDir(),
      "--session",
      ctx.sessionManager.getSessionId(),
    ],
    () => ctx.shutdown(),
    "Pi restart",
  );
}

export default function processRestart(pi: ExtensionAPI): void {
  pi.registerCommand("restart", {
    description: "Restart Pi and resume this session",
    handler: async (args, ctx) => {
      if (args.trim()) throw new Error("Usage: /restart");
      restartPi(ctx);
    },
  });

  pi.registerTool({
    name: "restart_pi",
    label: "Restart Pi",
    description: "Gracefully restart Pi and resume the current persisted session",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      restartPi(ctx);
      return {
        content: [{ type: "text", text: "Restarting Pi; process replacement requested." }],
        details: {},
        terminate: true,
      };
    },
  });
}
