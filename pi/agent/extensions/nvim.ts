import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { isAbsolute, normalize, relative, resolve, sep } from "node:path";
import { Type } from "typebox";
import { restartPi } from "./process-restart.ts";

type NvimContext = Pick<ExtensionContext, "cwd" | "mode" | "sessionManager" | "shutdown">;

function shellQuote(value: string): string {
  return `'${value.replaceAll("'", "'\\''")}'`;
}

function nvimCommand(input: string | undefined, cwd: string): string {
  if (input === undefined) return "nvim";
  if (/[\0\r\n]/.test(input)) throw new Error("Nvim path must not contain NUL or newline characters");
  if (!input.trim()) return "nvim";
  const path = input.trim();
  if (isAbsolute(path)) throw new Error("Nvim path must be relative to the Pi session working directory");
  const normalized = normalize(path);
  const fromCwd = relative(cwd, resolve(cwd, normalized));
  if (fromCwd === ".." || fromCwd.startsWith(`..${sep}`)) {
    throw new Error("Nvim path must remain relative to the Pi session working directory");
  }
  return `nvim -- ${shellQuote(normalized)}`;
}

function openNvim(ctx: NvimContext, path?: string): void {
  restartPi(ctx, nvimCommand(path, ctx.cwd), "/nvim");
}

export default function nvim(pi: ExtensionAPI): void {
  pi.registerCommand("nvim", {
    description: "Open Nvim at an optional relative path, then resume this Pi session",
    handler: async (args, ctx) => openNvim(ctx, args),
  });

  pi.registerTool({
    name: "nvim",
    label: "Nvim",
    description: "Open Nvim at zero or one relative path, then resume the exact persisted Pi session",
    parameters: Type.Object(
      {
        path: Type.Optional(Type.String({ description: "Optional path relative to the Pi session cwd" })),
      },
      { additionalProperties: false },
    ),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      openNvim(ctx, params.path);
      return {
        content: [{ type: "text", text: "Opening Nvim; Pi will resume after Nvim exits." }],
        details: {},
        terminate: true,
      };
    },
  });
}
