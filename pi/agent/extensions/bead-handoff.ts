import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { runAgntJson } from "./lib/run-agnt-json.ts";

const BEAD_ID = /^[a-z][a-z0-9]*-[A-Za-z0-9._-]+$/;

function validBeadId(value: string): boolean {
  return value.length <= 200 && BEAD_ID.test(value);
}

function targetFromPreflight(result: Record<string, unknown>): string | undefined {
  const target = result.target;
  if (!target || typeof target !== "object" || Array.isArray(target)) return undefined;
  const beadId = (target as Record<string, unknown>).beadId;
  return typeof beadId === "string" ? beadId : undefined;
}

export default function beadHandoff(pi: ExtensionAPI): void {
  pi.registerCommand("handoff-bead", {
    description: "Start a ready Bead in a fresh Pi session",
    handler: async (args, ctx) => {
      const targetBead = args.trim();
      if (!validBeadId(targetBead)) throw new Error("Usage: /handoff-bead <valid Bead ID>");
      if (ctx.mode !== "tui") throw new Error("/handoff-bead requires interactive TUI mode");

      const parentSession = ctx.sessionManager.getSessionFile();
      if (!parentSession) throw new Error("/handoff-bead requires a persisted session");
      const sourceSessionId = ctx.sessionManager.getSessionId();
      const preflight = await runAgntJson(
        ["work", "handoff-check", targetBead, "--session-id", sourceSessionId],
        ctx.cwd,
        undefined,
        "agnt work handoff-check",
      );
      if (preflight.status !== "ready" || targetFromPreflight(preflight) !== targetBead) {
        throw new Error("agnt work handoff-check did not validate the target Bead");
      }

      const kickoff = `Work ${targetBead} in this fresh Pi session. Run \`agnt work direct-start ${targetBead}\` before code changes, then continue from Beads and tracked repository artifacts only. No prior transcript was copied.`;
      const result = await ctx.newSession({
        parentSession,
        withSession: async (replacementCtx) => {
          if (replacementCtx.sessionManager.getSessionId() === sourceSessionId) {
            throw new Error("Bead handoff did not create a fresh Pi session");
          }
          await replacementCtx.sendUserMessage(kickoff);
        },
      });
      if (result.cancelled) ctx.ui.notify("Bead handoff cancelled", "info");
    },
  });

  pi.registerTool({
    name: "handoff_bead",
    label: "Handoff Bead",
    description: "After current Bead closeout, start one existing ready Bead in a fresh Pi session without copying the transcript",
    promptSnippet: "Start the next ready Bead in a fresh Pi session after current Bead closeout",
    promptGuidelines: [
      "Use handoff_bead only after recording the current Bead outcome, committing task-owned changes, and closing the current Bead.",
      "Pass handoff_bead the next existing ready Bead ID; use /new only as a human fallback when the tool is unavailable.",
    ],
    parameters: Type.Object({
      targetBead: Type.String({ description: "Existing ready Bead ID" }),
    }),
    async execute(_toolCallId, params) {
      const targetBead = params.targetBead.trim();
      if (!validBeadId(targetBead)) throw new Error("targetBead must be a valid Bead ID");
      pi.sendUserMessage(`/handoff-bead ${targetBead}`, { deliverAs: "followUp" });
      return {
        content: [{ type: "text", text: `Queued fresh-session handoff to ${targetBead}.` }],
        details: { targetBead },
        terminate: true,
      };
    },
  });
}
