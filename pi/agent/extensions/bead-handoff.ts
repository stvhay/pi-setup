import { unlinkSync, writeFileSync } from "node:fs";
import { SessionManager, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { requestProcessReplacement, requireProcessReplacement } from "./lib/process-replacement.ts";
import { runAgntJson } from "./lib/run-agnt-json.ts";

const BEAD_ID = /^[a-z][a-z0-9]*-[A-Za-z0-9._-]+$/;

function validBeadId(value: string): boolean {
  return value.length <= 200 && BEAD_ID.test(value);
}

type HandoffSource =
  | { status: "closed"; beadId: string }
  | { status: "unassigned" };

function sourceFromPreflight(result: Record<string, unknown>): HandoffSource | undefined {
  const source = result.source;
  if (!source || typeof source !== "object" || Array.isArray(source)) return undefined;
  const sourceRecord = source as Record<string, unknown>;
  if (sourceRecord.status === "unassigned") return { status: "unassigned" };
  return sourceRecord.status === "closed" &&
    typeof sourceRecord.beadId === "string" &&
    validBeadId(sourceRecord.beadId)
    ? { status: "closed", beadId: sourceRecord.beadId }
    : undefined;
}

function targetFromPreflight(result: Record<string, unknown>): string | undefined {
  const target = result.target;
  if (!target || typeof target !== "object" || Array.isArray(target)) return undefined;
  const targetRecord = target as Record<string, unknown>;
  return targetRecord.status === "open" &&
    typeof targetRecord.beadId === "string" &&
    validBeadId(targetRecord.beadId)
    ? targetRecord.beadId
    : undefined;
}

function choicesFromPreflight(result: Record<string, unknown>): Array<{ id: string; label: string }> {
  if (!Array.isArray(result.candidates)) return [];
  return result.candidates.flatMap((candidate) => {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return [];
    const { beadId, title } = candidate as Record<string, unknown>;
    if (typeof beadId !== "string" || !validBeadId(beadId) || typeof title !== "string") return [];
    return [{ id: beadId, label: `${beadId} — ${title}` }];
  });
}

const kickoffFor = (targetBead: string, source: HandoffSource): string => source.status === "closed"
  ? `Work ${targetBead} in this fresh Pi session after closed ${source.beadId}. Before code changes run \`bd prime\`, \`bd ready\`, then \`agnt work direct-start ${targetBead} --claim\`. Recover only \`bd show ${source.beadId}\`, \`bd show ${targetBead}\`, and artifacts those Beads reference. No prior transcript was copied.`
  : `Work ${targetBead} in this fresh Pi session from an unassigned source session. Before code changes run \`bd prime\`, \`bd ready\`, then \`agnt work direct-start ${targetBead} --claim\`. Recover only \`bd show ${targetBead}\` and artifacts that Bead references. No prior transcript was copied.`;

type HandoffContext = Pick<ExtensionContext, "cwd" | "mode" | "sessionManager" | "shutdown" | "ui">;

async function startHandoff(requestedTarget: string | undefined, ctx: HandoffContext, signal?: AbortSignal): Promise<string> {
  if (ctx.mode !== "tui") throw new Error("/handoff-bead requires interactive TUI mode");
  const parentSession = ctx.sessionManager.getSessionFile();
  if (!parentSession) throw new Error("/handoff-bead requires a persisted session");

  const sourceSessionId = ctx.sessionManager.getSessionId();
  const preflight = async (target?: string) => runAgntJson(
    ["work", "handoff-check", ...(target ? [target] : []), "--session-id", sourceSessionId],
    ctx.cwd,
    signal,
    "agnt work handoff-check",
  );
  let result = await preflight(requestedTarget);
  if (!requestedTarget && result.status === "selection-required") {
    const choices = choicesFromPreflight(result);
    if (choices.length < 2) throw new Error("agnt work handoff-check returned invalid ready-work choices");
    const selected = await ctx.ui.select("Choose next ready Bead", choices.map(({ label }) => label));
    if (!selected) throw new Error("Bead handoff selection cancelled; current session remains active");
    requestedTarget = choices.find(({ label }) => label === selected)?.id;
    if (!requestedTarget) throw new Error("Bead handoff selection was invalid; current session remains active");
    result = await preflight(requestedTarget);
  }
  const source = sourceFromPreflight(result);
  const targetBead = targetFromPreflight(result);
  if (result.status !== "ready" || !source || !targetBead || (requestedTarget && targetBead !== requestedTarget)) {
    throw new Error("agnt work handoff-check did not validate source state and ready target Bead");
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
        kickoffFor(targetBead, source),
      ],
      () => ctx.shutdown(),
      "Pi handoff",
      ` Resume staged session ${nextSessionFile} and run agnt work direct-start ${targetBead} --claim.`,
      () => {
        try {
          unlinkSync(nextSessionFile);
        } catch {
          // Best effort: shutdown is already exiting.
        }
        return ` Start Pi in a fresh session and run agnt work direct-start ${targetBead} --claim.`;
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
  return targetBead;
}

export default function beadHandoff(pi: ExtensionAPI): void {
  pi.registerCommand("handoff-bead", {
    description: "Start a ready Bead in a fresh Pi session",
    handler: async (args, ctx) => {
      const targetBead = args.trim() || undefined;
      if (targetBead && !validBeadId(targetBead)) throw new Error("Usage: /handoff-bead [valid Bead ID]");
      await startHandoff(targetBead, ctx);
    },
  });

  pi.registerTool({
    name: "handoff_bead",
    label: "Handoff Bead",
    description: "Start ready work after clean closeout, or an explicit target from an unassigned session",
    promptSnippet: "Start ready work in a fresh Pi session after clean closeout or from an unassigned session",
    promptGuidelines: [
      "Call handoff_bead without a target after recording a successful outcome, committing task-owned changes, and cleanly closing the current Bead, or from a persisted TUI session with no linked Bead when automatic selection is wanted.",
      "Call handoff_bead with an explicit target from a persisted TUI session only when that session has no linked Bead or current work closed successfully.",
      "handoff_bead selects a sole ready Bead automatically, asks once when several are ready, and uses /new only as a human fallback when unavailable.",
    ],
    parameters: Type.Object({
      targetBead: Type.Optional(Type.String({ description: "Optional existing ready Bead ID" })),
    }),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      const requestedTarget = params.targetBead?.trim() || undefined;
      if (requestedTarget && !validBeadId(requestedTarget)) throw new Error("targetBead must be a valid Bead ID");
      const targetBead = await startHandoff(requestedTarget, ctx, signal);
      return {
        content: [{ type: "text", text: `Starting fresh-session handoff to ${targetBead}; Pi restart requested.` }],
        details: { targetBead },
        terminate: true,
      };
    },
  });
}
