import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { runAgntJson } from "./lib/run-agnt-json.ts";

/** Explicit owner commands own migration; model tools can only inspect/check.
 * Historical migration deliberately does not claim authenticated input origin.
 * This is a trusted host integration, not a sandbox against arbitrary shell.
 */
export default function standingAuthority(pi: ExtensionAPI): void {
  pi.registerCommand("authority", {
    description: "Inspect owner-global standing authority (no activation)",
    handler: async (_args, ctx) => {
      const result = await runAgntJson(["authority", "inspect"], ctx.cwd);
      ctx.ui.notify(JSON.stringify(result), "info");
    },
  });
  pi.registerCommand("authority-import", {
    description: "Import an explicitly authorized historical owner consent record once",
    handler: async (args, ctx) => {
      const path = args.trim();
      if (!path) throw new Error("Usage: /authority-import <private historical consent JSON path>");
      const result = await runAgntJson(["authority", "import-historical", "--input-file", path], ctx.cwd);
      ctx.ui.notify(`Historical standing policy import: ${String(result.status)}. Input origin is not retained.`, "info");
    },
  });
  pi.registerTool({
    name: "standing_authority",
    label: "Standing authority",
    description: "Inspect standing delivery policy or check a resolved action against a private assignment. Does not activate policy, grant intent, or execute effects.",
    promptGuidelines: [
      "Standing permission does not create an assignment or prove target identity. Resolve current assignment, target, platform controls, downstream effects, verification, and recovery before an effect.",
      "Historical import is an explicit owner-authorized rollout operation, not a routine task or a way to approve arbitrary project text. Checks never activate policy.",
      "Retain explicit restrictions, rejected/pending decisions, and revocation. Exact quality experiment grants remain separate. This tool does not intercept arbitrary shell commands.",
    ],
    parameters: Type.Object({
      assignment: Type.Optional(Type.String({ description: "Existing private assignment ID; omit to inspect policy" })),
      actionFile: Type.Optional(Type.String({ description: "Resolved action JSON path, required with assignment" })),
    }),
    async execute(_id, params, signal, _update, ctx) {
      if (Boolean(params.assignment) !== Boolean(params.actionFile)) {
        throw new Error("assignment and actionFile must be supplied together");
      }
      const args = params.assignment
        ? ["authority", "check", params.assignment, "--input-file", params.actionFile!]
        : ["authority", "inspect"];
      const result = await runAgntJson(args, ctx.cwd, signal);
      return { content: [{ type: "text", text: JSON.stringify(result) }], details: result };
    },
  });
}
