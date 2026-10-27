import { unlinkSync, writeFileSync } from "node:fs";
import { rename, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { SessionManager, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { requestProcessReplacement, requireProcessReplacement } from "./lib/process-replacement.ts";
import { runAgntJson } from "./lib/run-agnt-json.ts";
import { continuationContext, registerContinuationStartup, reportContinuationCommand, startContinuation, type ContinuationOptions } from "./lib/work-continuation.ts";

const BEAD_ID = /^[a-z][a-z0-9]*-[A-Za-z0-9._-]+$/;

type HandoffStage = "attempt" | "preflight" | "selection" | "validation" | "session-stage" | "restart-request" | "shutdown-exit" | "process-replacement";
type HandoffResultClass = "started" | "succeeded" | "failed" | "cancelled" | "attempted";
type RecordHandoffStage = (stage: HandoffStage, resultClass: HandoffResultClass, durationMs: number) => void;

async function handoffStageRecorder(cwd: string, signal?: AbortSignal): Promise<RecordHandoffStage> {
  let directory: string;
  try {
    const timeout = AbortSignal.timeout(250);
    const result = await runAgntJson(
      ["runtime-path", "metrics/invocations"],
      cwd,
      signal ? AbortSignal.any([signal, timeout]) : timeout,
      "agnt runtime-path",
    );
    if (typeof result.path !== "string" || !result.path) return () => {};
    directory = result.path;
  } catch {
    return () => {};
  }

  let sequence = 0;
  return (stage, resultClass, durationMs) => {
    sequence += 1;
    const stamp = new Date().toISOString().replace(/\D/g, "").slice(0, 17);
    const name = `${stamp}-${process.pid}-${String(sequence).padStart(4, "0")}-handoff.metrics.json`;
    const target = join(directory, name);
    const temporary = join(directory, `.${name}.tmp`);
    void writeFile(temporary, `${JSON.stringify({
      schemaVersion: 2,
      kind: "handoff",
      stage,
      resultClass,
      durationMs: Math.max(0, Math.round(durationMs)),
    })}\n`, { encoding: "utf8", flag: "wx", mode: 0o600 })
      .then(() => rename(temporary, target))
      .catch(async () => {
        await unlink(temporary).catch(() => undefined);
        console.error("[handoff-metrics] could not record stage");
      });
  };
}

async function measureHandoffStage<T>(
  record: RecordHandoffStage,
  stage: HandoffStage,
  action: () => T | Promise<T>,
): Promise<T> {
  const startedMs = Date.now();
  try {
    const result = await action();
    record(stage, "succeeded", Date.now() - startedMs);
    return result;
  } catch (error) {
    record(stage, "failed", Date.now() - startedMs);
    throw error;
  }
}

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
  const record = await handoffStageRecorder(ctx.cwd, signal);
  record("attempt", "started", 0);
  const entryStartedMs = Date.now();
  if (ctx.mode !== "tui") {
    record("validation", "failed", Date.now() - entryStartedMs);
    throw new Error("/handoff-bead requires interactive TUI mode");
  }
  const parentSession = ctx.sessionManager.getSessionFile();
  if (!parentSession) {
    record("validation", "failed", Date.now() - entryStartedMs);
    throw new Error("/handoff-bead requires a persisted session");
  }

  const sourceSessionId = ctx.sessionManager.getSessionId();
  const preflight = async (target?: string) => measureHandoffStage(record, "preflight", () => runAgntJson(
    ["work", "handoff-check", ...(target ? [target] : []), "--session-id", sourceSessionId],
    ctx.cwd,
    signal,
    "agnt work handoff-check",
  ));
  let result = await preflight(requestedTarget);
  if (!requestedTarget && result.status === "selection-required") {
    const selectionStartedMs = Date.now();
    const choices = choicesFromPreflight(result);
    if (choices.length < 2) {
      record("selection", "failed", Date.now() - selectionStartedMs);
      throw new Error("agnt work handoff-check returned invalid ready-work choices");
    }
    const selected = await ctx.ui.select("Choose next ready Bead", choices.map(({ label }) => label));
    if (!selected) {
      record("selection", "cancelled", Date.now() - selectionStartedMs);
      throw new Error("Bead handoff selection cancelled; current session remains active");
    }
    requestedTarget = choices.find(({ label }) => label === selected)?.id;
    if (!requestedTarget) {
      record("selection", "failed", Date.now() - selectionStartedMs);
      throw new Error("Bead handoff selection was invalid; current session remains active");
    }
    record("selection", "succeeded", Date.now() - selectionStartedMs);
    result = await preflight(requestedTarget);
  }
  const validationStartedMs = Date.now();
  const source = sourceFromPreflight(result);
  const targetBead = targetFromPreflight(result);
  if (result.status !== "ready" || !source || !targetBead || (requestedTarget && targetBead !== requestedTarget)) {
    record("validation", "failed", Date.now() - validationStartedMs);
    throw new Error("agnt work handoff-check did not validate source state and ready target Bead");
  }
  record("validation", "succeeded", Date.now() - validationStartedMs);

  const { replacement, nextSession, nextSessionFile } = await measureHandoffStage(record, "session-stage", () => {
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
    return { replacement, nextSession, nextSessionFile };
  });

  const shutdownStartedMs = Date.now();
  const observedReplacement = {
    ...replacement,
    execve(file: string, args: string[], env: NodeJS.ProcessEnv): never {
      record("shutdown-exit", "attempted", Date.now() - shutdownStartedMs);
      const replacementStartedMs = Date.now();
      record("process-replacement", "attempted", 0);
      try {
        return replacement.execve(file, args, env);
      } catch (error) {
        record("process-replacement", "failed", Date.now() - replacementStartedMs);
        throw error;
      }
    },
  };
  try {
    await measureHandoffStage(record, "restart-request", () => requestProcessReplacement(
      observedReplacement,
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
        record("shutdown-exit", "cancelled", Date.now() - shutdownStartedMs);
        try {
          unlinkSync(nextSessionFile);
        } catch {
          // Best effort: shutdown is already exiting.
        }
        return ` Start Pi in a fresh session and run agnt work direct-start ${targetBead} --claim.`;
      },
    ));
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

async function routeHandoff(options: ContinuationOptions, ctx: HandoffContext, signal?: AbortSignal) {
  const current = await continuationContext(ctx, signal);
  if (options.transitionId || current.pendingTransition || current.status === "continuable" || current.status === "terminal") {
    return startContinuation(options, ctx, signal, current);
  }
  if (options.mode || options.checkpointRef || options.checkout || options.progress) {
    throw new Error(`Continuation options require unfinished assigned work; source is ${current.status}. No checkpoint was saved.`);
  }
  if (!["unassigned", "closed"].includes(String(current.status))) {
    throw new Error(`Source requires ${current.status}; inspect ownership or closeout before handoff.`);
  }
  const targetBead = await startHandoff(options.targetBead, ctx, signal);
  return {
    content: [{ type: "text" as const, text: `Starting fresh-session handoff to ${targetBead}; Pi restart requested.` }],
    details: { targetBead } as Record<string, unknown>,
    terminate: true,
  };
}

export default function beadHandoff(pi: ExtensionAPI): void {
  registerContinuationStartup(pi);
  pi.registerCommand("handoff-bead", {
    description: "Continue assigned work or start a ready Bead in a fresh Pi session",
    handler: async (args, ctx) => {
      const [verb, target, extra] = args.trim().split(/\s+/);
      let options: ContinuationOptions;
      if (["resume", "switch", "next", "recover"].includes(verb)) {
        if (extra || (target && verb !== "recover" && !validBeadId(target))) throw new Error("Usage: /handoff-bead resume|switch|next [Bead ID], or recover <transition ID>");
        if (verb === "recover") {
          if (!target || !/^[a-f0-9]{32}$/.test(target)) throw new Error("Expected exact transition ID");
          options = { transitionId: target };
        } else {
          options = { mode: verb as "resume" | "switch" | "next", targetBead: target };
        }
      } else {
        const targetBead = args.trim() || undefined;
        if (targetBead && !validBeadId(targetBead)) throw new Error("Usage: /handoff-bead [valid Bead ID]");
        if (ctx.mode !== "tui") throw new Error("/handoff-bead requires interactive TUI mode; use an explicit continuation mode for a host manifest");
        if (!ctx.sessionManager.getSessionFile()) throw new Error("/handoff-bead requires a persisted session");
        options = { targetBead };
      }
      reportContinuationCommand(await routeHandoff(options, ctx), ctx);
    },
  });

  pi.registerTool({
    name: "handoff_bead",
    label: "Handoff Bead",
    description: "Checkpoint and resume unfinished work, switch assigned Beads, or start ready work after verified closeout",
    promptSnippet: "Continue assigned work in fresh context without rewriting history or discarding dirty work",
    promptGuidelines: [
      "For unfinished linked work, handoff_bead defaults to checkpoint/resume; a different target requests an assignment-scoped switch. Supply current concise progress in this call: decisions, completed work, next steps, blockers, verification and artifact paths, not a transcript. Use checkpointRef only to retain an exact existing checkpoint, never together with new progress.",
      "Use mode=next for deterministic eligible work inside the recorded assignment; transitionId recovers the exact reservation. Settle existing reservations before changing target, mode, checkpoint or checkout. Never close unfinished work or rewrite outcomes to enable continuation.",
      "Canonically closed non-success work defaults to next within captured scope, using a reserved child. Requires its actual owning session/header, closure disposition, settled effects and a clean existing destination; preserve dirty source work in an approved isolated checkout. No success rewriting, new terminal worktree or foreign-owner sweep.",
      "After verified successful closeout, or from an unassigned session, the existing ready-work handoff remains available. Headless continuation returns a host manifest; /new is only a fallback for an unavailable runtime, never an ownership override.",
    ],
    parameters: Type.Object({
      targetBead: Type.Optional(Type.String({ description: "Optional existing assigned target Bead ID" })),
      mode: Type.Optional(Type.Union([Type.Literal("resume"), Type.Literal("switch"), Type.Literal("next")])),
      checkpointRef: Type.Optional(Type.String({ pattern: "^[a-f0-9]{32}$" })),
      progress: Type.Optional(Type.Object({
        objective: Type.String({ minLength: 1, maxLength: 16000 }),
        decisions: Type.Array(Type.String()), completed: Type.Array(Type.String()), next: Type.Array(Type.String()),
        blockers: Type.Array(Type.String()), verification: Type.Array(Type.String()),
        ownedPaths: Type.Array(Type.String({ description: "Task-owned relative path, not a deletion instruction" })),
        artifactRefs: Type.Array(Type.String({ description: "Exact durable evidence/reference path" })),
      }, { additionalProperties: false, description: "Current curated handoff, at most 64 KiB. No authority fields; scope comes from execution ownership." })),
      checkout: Type.Optional(Type.String({ description: "Optional existing isolated checkout; omit to request authorized isolation" })),
      transitionId: Type.Optional(Type.String({ pattern: "^[a-f0-9]{32}$", description: "Recover this exact reservation, never allocate another child" })),
    }),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      const requestedTarget = params.targetBead?.trim() || undefined;
      if (requestedTarget && !validBeadId(requestedTarget)) throw new Error("targetBead must be a valid Bead ID");
      return routeHandoff({ ...params, targetBead: requestedTarget }, ctx, signal);
    },
  });
}
