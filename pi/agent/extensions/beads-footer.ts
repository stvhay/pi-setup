import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { runAgntJson } from "./lib/run-agnt-json.ts";

const STATUS_KEY = "beads-work";
const BEAD_ID = /^[a-z][a-z0-9]*-[A-Za-z0-9._-]+$/;
const WORK_MUTATING_TOOLS = new Set([
  "bash",
  "handoff_bead",
  "ticket_approval",
  "ticket_decision_resolve",
  "ticket_gateway",
  "ticket_question",
]);

type WorkItem = { id: string; priority: number; title: string };
type WorkStatus = { activeBeadId?: string; items: WorkItem[] };

function workStatus(result: Record<string, unknown>): WorkStatus | undefined {
  if (result.schemaVersion !== 1 || result.status !== "ok" || !Array.isArray(result.items)) return undefined;
  const active = result.activeBeadId;
  if (active !== null && active !== undefined && (typeof active !== "string" || !BEAD_ID.test(active))) return undefined;

  const items: WorkItem[] = [];
  for (const value of result.items) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
    const { id, priority, title } = value as Record<string, unknown>;
    if (
      typeof id !== "string" ||
      !BEAD_ID.test(id) ||
      typeof priority !== "number" ||
      !Number.isInteger(priority) ||
      priority < 0 ||
      priority > 4 ||
      typeof title !== "string" ||
      !title.trim() ||
      /[\x00-\x1f\x7f]/.test(title)
    ) return undefined;
    items.push({ id, priority, title });
  }
  return { activeBeadId: typeof active === "string" ? active : undefined, items };
}

function statusText(state: WorkStatus, ctx: ExtensionContext): string | undefined {
  if (state.items.length === 0) return undefined;
  const idWidth = Math.max(...state.items.map((item) => item.id.length));
  return state.items.map((item) => {
    const text = `◐ ${item.id.padEnd(idWidth)}  P${item.priority}  ${item.title}`;
    return item.id === state.activeBeadId
      ? ctx.ui.theme.fg("mdHeading", ctx.ui.theme.bold(text))
      : ctx.ui.theme.fg("syntaxString", text);
  }).join("\n");
}

export default function beadsFooter(pi: ExtensionAPI): void {
  let refreshVersion = 0;

  const refresh = async (ctx: ExtensionContext): Promise<void> => {
    const version = ++refreshVersion;
    let text: string | undefined;
    try {
      const result = await runAgntJson(
        ["work", "status", "--session-id", ctx.sessionManager.getSessionId()],
        ctx.cwd,
        undefined,
        "agnt work status",
      );
      const state = workStatus(result);
      if (state) text = statusText(state, ctx);
    } catch {
      // Footer state is best-effort and presentation-only.
    }
    if (version === refreshVersion) ctx.ui.setStatus(STATUS_KEY, text);
  };

  pi.on("session_start", async (_event, ctx) => refresh(ctx));
  pi.on("tool_execution_end", async (event, ctx) => {
    if (WORK_MUTATING_TOOLS.has(event.toolName)) await refresh(ctx);
  });
}
