import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { requestProcessReplacement, requireProcessReplacement } from "./lib/process-replacement.ts";

type RestartContext = Pick<ExtensionContext, "cwd" | "mode" | "sessionManager" | "shutdown">;

const MAX_FAILURE_DIAGNOSTIC_LENGTH = 1000;

const COMMAND_RELAY = `cwd=$1
command=$2
shift 2
if cd "$cwd"; then
  /bin/sh -c "$command"
  status=$?
else
  status=125
  printf '%s\n' 'Command not run: Pi session working directory is unavailable.' >&2
fi
printf 'Command exited with status %d; resuming Pi.\n' "$status" >&2
exec "$@"`;

function shellQuote(value: string): string {
  return `'${value.replaceAll("'", "'\\''")}'`;
}

function validateCommand(command: string): void {
  if (!command.trim()) throw new Error("restart_pi.command must contain a non-whitespace shell command");
  if (command.includes("\0")) throw new Error("restart command must not contain NUL");
}

export function restartPi(ctx: RestartContext, command?: string, requestName = "/restart"): void {
  if (command !== undefined) validateCommand(command);
  if (ctx.mode !== "tui") throw new Error(`${requestName} requires interactive TUI mode`);
  const replacement = requireProcessReplacement(requestName);
  const sessionFile = ctx.sessionManager.getSessionFile();
  if (!sessionFile) {
    throw new Error(`${requestName} requires a persisted session; restart Pi without --no-session`);
  }
  const sessionDir = ctx.sessionManager.getSessionDir();
  const resumeArgs = [...replacement.argv, "--session-dir", sessionDir, "--session", sessionFile];
  const failureHint = ` Resume with: pi --session-dir ${shellQuote(sessionDir)} --session ${shellQuote(sessionFile)}`;
  if (failureHint.length > MAX_FAILURE_DIAGNOSTIC_LENGTH) {
    throw new Error(`${requestName} recovery command exceeds 1000-character diagnostic limit; no shutdown requested`);
  }

  requestProcessReplacement(
    command === undefined ? replacement : { ...replacement, executable: "/bin/sh" },
    command === undefined
      ? resumeArgs
      : ["/bin/sh", "-c", COMMAND_RELAY, "pi-command-relay", ctx.cwd, command, ...resumeArgs],
    () => ctx.shutdown(),
    "Pi restart",
    failureHint,
  );
}

export default function processRestart(pi: ExtensionAPI): void {
  pi.registerCommand("restart", {
    description: "Restart Pi and resume this session, optionally after a shell command",
    handler: async (args, ctx) => {
      restartPi(ctx, args ? args : undefined);
    },
  });

  pi.registerTool({
    name: "restart_pi",
    label: "Restart Pi",
    description:
      "Gracefully restart Pi and resume the current persisted session. Optional command runs from session cwd and is equivalent to bash for authorization and approval.",
    promptGuidelines: [
      "Treat restart_pi.command as equivalent to bash for authorization, safety review, and approval; never use it to bypass bash restrictions.",
    ],
    parameters: Type.Object(
      {
        command: Type.Optional(Type.String({ description: "Optional shell command to run before Pi resumes" })),
      },
      { additionalProperties: false },
    ),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      restartPi(ctx, params.command);
      return {
        content: [{ type: "text", text: "Restarting Pi; process replacement requested." }],
        details: {},
        terminate: true,
      };
    },
  });
}
