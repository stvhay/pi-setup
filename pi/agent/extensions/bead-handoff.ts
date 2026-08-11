import { unlinkSync, writeFileSync } from "node:fs";
import { SessionManager, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { requestProcessReplacement, requireProcessReplacement } from "./lib/process-replacement.ts";
import { runAgntJson } from "./lib/run-agnt-json.ts";

const BEAD_ID = /^[a-z][a-z0-9]*-[A-Za-z0-9._-]+$/;

function validBeadId(value: string): boolean {
  return value.length <= 200 && BEAD_ID.test(value);
}

function sourceIsClosed(result: Record<string, unknown>): boolean {
  const source = result.source;
  return Boolean(
    source &&
      typeof source === "object" &&
      !Array.isArray(source) &&
      (source as Record<string, unknown>).status === "closed",
  );
}

function targetFromPreflight(result: Record<string, unknown>): string | undefined {
  const target = result.target;
  if (!target || typeof target !== "object" || Array.isArray(target)) return undefined;
  const targetRecord = target as Record<string, unknown>;
  return targetRecord.status === "open" && typeof targetRecord.beadId === "string"
    ? targetRecord.beadId
    : undefined;
}

const kickoffFor = (targetBead: string): string =>
  `Work ${targetBead} in this fresh Pi session. Run \`agnt work direct-start ${targetBead}\` before code changes, then continue from Beads and tracked repository artifacts only. No prior transcript was copied.`;

type HandoffContext = Pick<ExtensionContext, "cwd" | "mode" | "sessionManager" | "shutdown">;

async function startHandoff(targetBead: string, ctx: HandoffContext, signal?: AbortSignal): Promise<void> {
  if (ctx.mode !== "tui") throw new Error("/handoff-bead requires interactive TUI mode");
  const parentSession = ctx.sessionManager.getSessionFile();
  if (!parentSession) throw new Error("/handoff-bead requires a persisted session");

  const sourceSessionId = ctx.sessionManager.getSessionId();
  const preflight = await runAgntJson(
    ["work", "handoff-check", targetBead, "--session-id", sourceSessionId],
    ctx.cwd,
    signal,
    "agnt work handoff-check",
  );
  if (
    preflight.status !== "ready" ||
    !sourceIsClosed(preflight) ||
    targetFromPreflight(preflight) !== targetBead
  ) {
    throw new Error("agnt work handoff-check did not validate a closed source Bead and ready target Bead");
  }

  const replacement = requireProcessReplacement("/handoff-bead");
  const nextSession = SessionManager.create(ctx.cwd, ctx.sessionManager.getSessionDir(), { parentSession });
  const nextSessionFile = nextSession.getSessionFile();
  if (!nextSessionFile || nextSession.getSessionId() === sourceSessionId) {
    throw new Error("Bead handoff could not stage a fresh persisted session; current session remains active");
  }
  try {
    writeFileSync(nextSessionFile, `${JSON.stringify(nextSession.getHeader())}\n`, { encoding: "utf-8", flag: "wx" });
  } catch {
    try {
      unlinkSync(nextSessionFile);
    } catch {
      // Nothing staged, or cleanup already complete.
    }
    throw new Error("Bead handoff could not stage the fresh session; current session remains active");
  }

  try {
    requestProcessReplacement(
      replacement,
      [
        ...replacement.argv,
        "--session-dir",
        nextSession.getSessionDir(),
        "--session",
        nextSessionFile,
        kickoffFor(targetBead),
      ],
      () => ctx.shutdown(),
      "Pi handoff",
      ` Resume staged session ${nextSessionFile} and run agnt work direct-start ${targetBead}.`,
      () => {
        try {
          unlinkSync(nextSessionFile);
        } catch {
          // Best effort: shutdown is already exiting.
        }
        return ` Start Pi in a fresh session and run agnt work direct-start ${targetBead}.`;
      },
    );
  } catch (error) {
    try {
      unlinkSync(nextSessionFile);
    } catch {
      // Best effort: staged session contains only bounded handoff metadata.
    }
    throw error;
  }
}

export default function beadHandoff(pi: ExtensionAPI): void {
  pi.registerCommand("handoff-bead", {
    description: "Start a ready Bead in a fresh Pi session",
    handler: async (args, ctx) => {
      const targetBead = args.trim();
      if (!validBeadId(targetBead)) throw new Error("Usage: /handoff-bead <valid Bead ID>");
      await startHandoff(targetBead, ctx);
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
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      const targetBead = params.targetBead.trim();
      if (!validBeadId(targetBead)) throw new Error("targetBead must be a valid Bead ID");
      await startHandoff(targetBead, ctx, signal);
      return {
        content: [{ type: "text", text: `Starting fresh-session handoff to ${targetBead}; Pi restart requested.` }],
        details: { targetBead },
        terminate: true,
      };
    },
  });
}
