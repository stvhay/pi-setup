import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { closeSync, constants, fstatSync, fsyncSync, mkdirSync, openSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { getAgentDir, SessionManager, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";
import { redactOutputText } from "../zz-output-redaction.ts";
import { requestProcessReplacement, requireProcessReplacement } from "./process-replacement.ts";
import { AgntCommandError, runAgntJson } from "./run-agnt-json.ts";

type Context = Pick<ExtensionContext, "cwd" | "mode" | "sessionManager" | "shutdown" | "ui">;
export type ContinuationOptions = {
  mode?: "resume" | "switch" | "next";
  targetBead?: string;
  checkpointRef?: string;
  progress?: { objective: string; decisions: string[]; completed: string[]; next: string[];
    blockers: string[]; verification: string[]; ownedPaths: string[]; artifactRefs: string[] };
  checkout?: string;
  transitionId?: string;
};
type Transition = {
  id: string; sourceSession: string; sourceSessionFile: string; sourceBead: string; targetBead: string;
  checkpointRef: string; targetCheckout: string; childSession: string; childSessionFile: string; state: string;
  mode: "resume" | "switch" | "next"; cancelRequested?: boolean;
};
type Reservation = Omit<Transition, "childSessionFile"> & { childSessionFile: string | null };

function runWork(ctx: Context, args: string[], signal?: AbortSignal, launchProof?: string, input?: string) {
  return runAgntJson(["work", ...args], ctx.cwd, signal, "agnt work continuation", input, launchProof,
    { id: ctx.sessionManager.getSessionId(), file: ctx.sessionManager.getSessionFile() }, "work-launch");
}

async function runTransition(ctx: Context, args: string[], signal?: AbortSignal) {
  try { return await runWork(ctx, args, signal); }
  catch (error) {
    // Only known domain refusal is a recoverable result, never transport failure.
    if (error instanceof AgntCommandError && error.exitCode === 2 && error.result?.status === "blocked") return error.result;
    throw error;
  }
}

export function continuationContext(ctx: Context, signal?: AbortSignal) {
  return runWork(ctx, ["transition-context", "--session-id", ctx.sessionManager.getSessionId()], signal);
}

function reservationFrom(result: Record<string, unknown>): Reservation {
  const absolute = (value: unknown): value is string => typeof value === "string" && isAbsolute(value);
  const tx = result.transition as Reservation | undefined;
  const unbound = tx?.childSessionFile === null && ["prepared", "isolating", "cancelled"].includes(tx.state);
  if (!tx || !/^[a-f0-9]{32}$/.test(tx.id) || !/^[a-z][a-z0-9]*-[A-Za-z0-9._-]+$/.test(tx.targetBead)
      || !/^[a-f0-9-]{36}$/.test(tx.childSession) || (!absolute(tx.childSessionFile) && !unbound)
      || !absolute(tx.targetCheckout) || !absolute(tx.sourceSessionFile) || !/^[a-f0-9]{32}$/.test(tx.checkpointRef)) {
    throw new Error("Invalid continuation reservation; no launch requested");
  }
  return tx;
}

function transitionFrom(result: Record<string, unknown>): Transition {
  const tx = reservationFrom(result);
  if (tx.childSessionFile === null) throw new Error("Unbound child path; repair reservation before launch");
  return { ...tx, childSessionFile: tx.childSessionFile };
}

function sameReservation(previous: Reservation, result: Record<string, unknown>, bindingChild = false): Transition {
  const next = transitionFrom(result);
  const identity = ["id", "sourceSession", "sourceSessionFile", "sourceBead", "targetBead", "checkpointRef",
    "targetCheckout", "childSession", "childSessionFile", "mode"] as const;
  if (identity.some(key => !(bindingChild && key === "childSessionFile" && previous.childSessionFile === null)
      && previous[key] !== next[key])) throw new Error("Continuation reservation changed; reconcile before launch");
  return next;
}

function stageHeader(tx: Transition, parentSession: string): void {
  const header = SessionManager.inMemory(tx.targetCheckout, { id: tx.childSession, parentSession }).getHeader();
  mkdirSync(dirname(tx.childSessionFile), { recursive: true, mode: 0o700 });
  if (realpathSync(dirname(tx.childSessionFile)) !== dirname(tx.childSessionFile)) throw new Error("Unsafe child directory");
  let fd: number;
  try {
    fd = openSync(tx.childSessionFile, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
    const existingFd = openSync(tx.childSessionFile, constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      if (fstatSync(existingFd).size > 8192) throw new Error("Reserved child is not an empty staged session");
      const lines = readFileSync(existingFd, "utf8").trim().split("\n");
      const existing = JSON.parse(lines[0]);
      if (lines.length !== 1 || existing.id !== tx.childSession || existing.cwd !== tx.targetCheckout
          || existing.parentSession !== parentSession || existing.type !== "session") {
        throw new Error("Reserved child already contains different state; reconcile without overwriting");
      }
    } finally { closeSync(existingFd); }
    return;
  }
  try {
    writeFileSync(fd, `${JSON.stringify(header)}\n`);
    fsyncSync(fd);
  } finally { closeSync(fd); }
  const dir = openSync(dirname(tx.childSessionFile), constants.O_RDONLY);
  try { fsyncSync(dir); } finally { closeSync(dir); }
}

function report(details: Record<string, unknown>, terminate = false) {
  return { content: [{ type: "text" as const, text: JSON.stringify(details) }], details, ...(terminate ? { terminate: true } : {}) };
}

export async function startContinuation(options: ContinuationOptions, ctx: Context, signal?: AbortSignal) {
  const sourceSession = ctx.sessionManager.getSessionId();
  const current = await continuationContext(ctx, signal);
  if (ctx.mode !== "tui") {
    return report({ status: "host-required", mode: options.mode ?? "resume", sourceSession,
      checkpointRef: options.checkpointRef, targetBead: options.targetBead, transitionId: options.transitionId,
      progress: options.progress, source: current, reason: "Caller owns process launch. No checkpoint, reservation or shutdown performed." });
  }
  const parentSession = ctx.sessionManager.getSessionFile();
  if (!parentSession) throw new Error("Continuation requires a persisted source session");
  const replacement = requireProcessReplacement("/handoff-bead continuation");
  let result: Record<string, unknown>;
  const pendingId = (current.pendingTransition as { id?: string } | undefined)?.id;
  const recoveryId = options.transitionId ?? pendingId;
  if (options.progress && (options.checkpointRef || recoveryId)) {
    throw new Error("New progress cannot replace a reserved checkpoint; recover it unchanged or cancel before saving new progress");
  }
  if (recoveryId) {
    result = await runTransition(ctx, ["transition-recover", recoveryId], signal);
  } else {
    if (current.status !== "continuable" || typeof current.beadId !== "string") {
      throw new Error("Continuation requires unfinished assigned work; use normal closeout handoff otherwise");
    }
    let checkpointRef = options.checkpointRef;
    if (!checkpointRef) {
      const saved = await runWork(ctx, ["checkpoint", current.beadId, ...(options.progress ? ["--input-file", "-"] : [])],
        signal, undefined, options.progress ? JSON.stringify(options.progress) : undefined);
      checkpointRef = (saved.checkpoint as { id?: string } | undefined)?.id;
      if (!checkpointRef) throw new Error("Checkpoint was not persisted; no launch requested");
    }
    result = await runTransition(ctx, ["transition-prepare", ...(options.targetBead ? [options.targetBead] : []),
      "--mode", options.mode ?? (options.targetBead && options.targetBead !== current.beadId ? "switch" : "resume"),
      "--session-id", sourceSession, "--checkpoint-ref", checkpointRef,
      "--runtime-ready", ...(options.checkout ? ["--checkout", options.checkout] : [])], signal);
    if (result.status === "idle") return report(result);
  }
  const reconcile = (value: Record<string, unknown>) => report({
    reason: "Reserved transition is not launchable; inspect its recorded recovery action.",
    ...value, status: "reconciliation-required",
  });
  if (result.status === "blocked" && !result.transition) return reconcile(result);
  let pending = reservationFrom(result);
  if (pending.sourceSession !== sourceSession || realpathSync(parentSession) !== pending.sourceSessionFile) {
    throw new Error("Only the reserved persisted source may launch this continuation");
  }
  let checkoutConflict = false;
  if (recoveryId && options.checkout) {
    try { checkoutConflict = realpathSync(resolve(ctx.cwd, options.checkout)) !== pending.targetCheckout; }
    catch { checkoutConflict = true; }
  }
  if ((recoveryId && recoveryId !== pending.id) || (options.mode && options.mode !== pending.mode)
      || (options.targetBead && options.targetBead !== pending.targetBead)
      || (options.checkpointRef && options.checkpointRef !== pending.checkpointRef) || checkoutConflict) {
    throw new Error("Requested continuation conflicts with reserved transition; recover or cancel it before changing targets");
  }
  if (result.status === "blocked") return reconcile(result);
  if (pending.childSessionFile === null) {
    if (pending.state === "cancelled") return report({ ...result, status: "cancelled" });
    result = await runTransition(ctx, ["transition-bind-child", pending.id, "--session-id", sourceSession], signal);
    if (result.status === "blocked") return reconcile({ ...result, transitionId: pending.id, lastObservedTransition: pending });
    pending = sameReservation(pending, result, true);
  }
  let tx = transitionFrom({ ...result, transition: pending });
  if (recoveryId && tx.state === "isolating") {
    const cancelling = tx.cancelRequested === true;
    result = await runTransition(ctx, [cancelling ? "transition-cancel" : "transition-isolate", tx.id,
      "--session-id", sourceSession], signal);
    if (result.status === "blocked" && !result.transition) return reconcile({ ...result, transitionId: tx.id, lastObservedTransition: tx });
    tx = sameReservation(tx, result);
    if (result.status === "blocked") return reconcile(result);
    if (cancelling) return tx.state === "cancelled" ? report({ ...result, status: "cancelled" }) : reconcile(result);
  }
  if (!["prepared", "staged"].includes(tx.state)) return reconcile({ ...result, transition: tx });
  replacement.assertCheckout(ctx.cwd, tx.targetCheckout);
  const recovery = ` Inspect agnt work transition-recover ${tx.id}; do not replay an uncertain launch.`;
  const launchProof = JSON.stringify({ kind: "work-launch-v1", transition: tx.id,
    sourceSession, secret: randomBytes(32).toString("hex") });
  const abortArgs = (reason: string) => ["transition-abort-launch", tx.id, "--session-id", sourceSession, "--reason", reason];
  // Exit callbacks cannot await promises. These callbacks have observed that
  // exec did not run; a timeout/missing process never calls this compensation.
  const abortAtExit = (reason: string): string => {
    const result = spawnSync(join(getAgentDir(), "bin", "agnt"), ["work", ...abortArgs(reason)], {
      cwd: ctx.cwd, encoding: "utf8", timeout: 10_000, maxBuffer: 1024 * 1024, input: launchProof,
      env: { ...process.env, PI_SESSION_ID: sourceSession, PI_SESSION_FILE: parentSession, AGNT_WORK_LAUNCH_PROOF_FD: "0" },
    });
    return result.status === 0 ? " Launch cancelled before exec; source session remains resumable." : recovery;
  };
  let phase = "stage-failed";
  try {
    if (tx.state === "prepared") stageHeader(tx, tx.sourceSessionFile);
    tx = sameReservation(tx, await runWork(ctx, ["transition-stage", tx.id, "--session-id", sourceSession], signal));
    phase = "launch-request-failed";
    tx = sameReservation(tx, await runWork(ctx, ["transition-launch", tx.id, "--session-id", sourceSession], signal, launchProof));
    phase = "shutdown-request-failed";
    const observedReplacement = { ...replacement,
      execve(file: string, args: string[], env: NodeJS.ProcessEnv): never {
        try {
          process.chdir(tx.targetCheckout);
          return replacement.execve(file, args, env);
        } catch (error) {
          console.error(abortAtExit("exec-failed"));
          throw error;
        }
      },
    };
    requestProcessReplacement(observedReplacement,
      [...replacement.argv, "--session-dir", dirname(tx.childSessionFile), "--session", tx.childSessionFile,
        `Continue ${tx.targetBead} from checkpoint ${tx.checkpointRef}, transition ${tx.id}. Startup attaches this reserved child before tools. Run bd prime and bd show ${tx.targetBead}; inspect agnt work transition-recover ${tx.id} and referenced artifacts. Preserve prior outcomes and dirty work. No prior transcript was copied.`],
      () => ctx.shutdown(), "Pi continuation", recovery, () => abortAtExit("shutdown-nonzero"));
  } catch (error) {
    // The replacement listener is removed on synchronous shutdown failure.
    // Keep the child file as evidence; never overwrite or delete session data.
    await runWork(ctx, abortArgs(phase), undefined, launchProof).catch(() => console.error(recovery));
    throw error;
  }
  return report({ status: "restart-requested", targetBead: tx.targetBead, transitionId: tx.id,
    childSession: tx.childSession, checkpointRef: tx.checkpointRef }, true);
}

export async function runContinuationCommand(options: ContinuationOptions, ctx: Context): Promise<void> {
  const result = await startContinuation(options, ctx);
  if (result.terminate) return;
  const details = result.details;
  const transition = details.transition as { id?: string } | undefined;
  const id = transition?.id ?? details.transitionId;
  const message = `Continuation ${String(details.status)}${id ? `: ${String(id)}` : ""}`
    + (typeof details.reason === "string" ? `\n${details.reason}` : "");
  ctx.ui.notify(redactOutputText(message).slice(0, 1000), details.status === "reconciliation-required" ? "warning" : "info");
}

export function registerContinuationStartup(pi: ExtensionAPI): void {
  let blocked: string | undefined;
  pi.on("tool_call", async () => blocked ? { block: true, reason: blocked } : undefined);
  pi.on("session_start", async (_event, ctx) => {
    blocked = "Continuation ownership inspection pending";
    try {
      const current = await continuationContext(ctx);
      if (current.status === "child") {
        const tx = transitionFrom(current);
        const result = await runWork(ctx, ["transition-attach", tx.id, "--session-id", ctx.sessionManager.getSessionId()]);
        if (transitionFrom(result).state !== "attached") throw new Error("Child attachment did not complete");
      }
      blocked = undefined;
    } catch (error) {
      blocked = "Continuation ownership is unresolved; preserve current work and inspect the transition before retrying.";
      console.error(redactOutputText(`${blocked} ${String(error)}`).slice(0, 1000));
      ctx.ui.notify(blocked, "error");
      ctx.shutdown();
    }
  });
}
