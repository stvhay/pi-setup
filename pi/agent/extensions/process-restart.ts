import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { redactOutputText } from "./zz-output-redaction.ts";

export default function processRestart(pi: ExtensionAPI): void {
  pi.registerCommand("restart", {
    description: "Restart Pi and resume this session",
    handler: async (args, ctx) => {
      if (args.trim()) throw new Error("Usage: /restart");
      if (ctx.mode !== "tui") throw new Error("/restart requires interactive TUI mode");
      if (
        process.release.name !== "node" ||
        Number.parseInt(process.versions.node, 10) < 24 ||
        (process.platform !== "darwin" && process.platform !== "linux")
      ) {
        throw new Error("/restart requires Node 24 on macOS or Linux; no shutdown requested");
      }

      const execve = process.execve;
      if (typeof execve !== "function") {
        throw new Error("/restart requires process.execve; no shutdown requested");
      }
      if (!ctx.sessionManager.getSessionFile()) {
        throw new Error("/restart requires a persisted session; restart Pi without --no-session");
      }

      const entrypoint = process.argv[1];
      if (!entrypoint) throw new Error("/restart could not determine the current Pi entrypoint");
      const executable = process.execPath;
      const resumeArgs = [
        executable,
        ...process.execArgv,
        entrypoint,
        "--session-dir",
        ctx.sessionManager.getSessionDir(),
        "--session",
        ctx.sessionManager.getSessionId(),
      ];

      const restartOnExit = (code: number): void => {
        if (code !== 0) return;
        try {
          execve(executable, resumeArgs, process.env);
        } catch (error) {
          process.exitCode = 1;
          const message = error instanceof Error ? error.message : String(error);
          console.error(`Pi restart failed: ${redactOutputText(message)}`);
        }
      };
      process.once("exit", restartOnExit);
      try {
        ctx.shutdown();
      } catch (error) {
        process.off("exit", restartOnExit);
        throw error;
      }
    },
  });

  pi.registerTool({
    name: "restart_pi",
    label: "Restart Pi",
    description: "Gracefully restart Pi and resume the current persisted session",
    parameters: Type.Object({}),
    async execute() {
      pi.sendUserMessage("/restart", { deliverAs: "followUp" });
      return {
        content: [{ type: "text", text: "Queued /restart as a follow-up command." }],
        details: {},
      };
    },
  });
}
