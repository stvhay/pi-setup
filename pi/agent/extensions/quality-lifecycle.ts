import { type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import { parse } from "node:path";
import { runAgntJson } from "./lib/run-agnt-json.ts";
import { providerError, providerFailureClass } from "./subagent-error-workaround.ts";

const PROJECTION_OBSERVE_REQUEST = "pi-setup:langfuse-projection-observe";
const LOCAL_CAPTURE_TIMEOUT_MS = 5_000;
const INTERACTIVE_VALUE_MAX_CHARS = 12_000;

type ObservationAttributes = {
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  level?: "DEFAULT" | "ERROR";
};
type Observe = (
  name: string,
  attributes: ObservationAttributes,
  options: { asType: "agent"; sessionId?: string; flush?: boolean },
) => void | Promise<void>;
type RunAgnt = typeof runAgntJson;
type Dependencies = { observe?: Observe; runAgnt?: RunAgnt };
type ToolErrorSignal = {
  toolName: string;
  inputHash: string;
  count: number;
  exitCode?: number;
  cancelled: boolean;
  timedOut: boolean;
  recovered: boolean;
};
type LocalCapture = {
  localCaptureStatus: "captured" | "unavailable";
  localCaptureGap?: string;
};

function sessionId(ctx: ExtensionContext): string | undefined {
  try {
    const id = ctx.sessionManager?.getSessionId?.();
    if (typeof id === "string" && id) return id;
    const file = ctx.sessionManager?.getSessionFile?.();
    return file ? parse(file).name : undefined;
  } catch {
    return undefined;
  }
}

function lastAssistantMessage(messages: unknown): { content?: unknown; stopReason?: string; errorMessage?: string } | undefined {
  if (!Array.isArray(messages)) return undefined;
  return messages.findLast((item) => item && typeof item === "object" && (item as { role?: string }).role === "assistant") as { content?: unknown; stopReason?: string; errorMessage?: string } | undefined;
}

function assistantOutput(messages: unknown): unknown {
  const message = lastAssistantMessage(messages);
  if (!Array.isArray(message?.content)) {
    return message?.stopReason === "error" ? providerError(message.errorMessage) : message?.content;
  }
  const text = message.content
    .map((item) => item && typeof item === "object" && (item as { type?: string; text?: string }).type === "text" ? (item as { text?: string }).text ?? "" : "")
    .filter(Boolean)
    .join("\n");
  if (message.stopReason === "error") {
    const error = providerError(message.errorMessage);
    return text ? `${text}\n\n[execution failed: ${error}]` : error;
  }
  return text || undefined;
}

function boundedInteractiveValue(value: unknown): unknown {
  if (typeof value !== "string" || value.length <= INTERACTIVE_VALUE_MAX_CHARS) return value;
  const notice = "\n[interactive value truncated]";
  return value.slice(0, INTERACTIVE_VALUE_MAX_CHARS - notice.length) + notice;
}

function assistantExecutionMetadata(messages: unknown): Record<string, unknown> {
  const message = lastAssistantMessage(messages);
  if (!message) return { executionOutcome: "unknown" };
  if (message.stopReason === "aborted" || message.stopReason === "length" || message.stopReason === "toolUse" || message.stopReason === "pending") {
    return { executionOutcome: "unavailable" };
  }
  if (message.stopReason !== "error") return { executionOutcome: "succeeded" };
  const classification = providerFailureClass(message.errorMessage);
  return {
    executionOutcome: "failed",
    failureClass: "provider",
    ...(classification ? { providerFailureClass: classification } : {}),
  };
}

function toolSignalKey(event: { toolName: string; input: Record<string, unknown> }): string {
  return createHash("sha256").update(`${event.toolName}|${JSON.stringify(event.input)}`).digest("hex");
}

function recordToolSignal(
  signals: Map<string, ToolErrorSignal>,
  event: { toolName: string; input: Record<string, unknown>; details?: unknown; isError?: boolean },
): void {
  const key = toolSignalKey(event);
  const existing = signals.get(key);
  if (!event.isError) {
    if (existing) existing.recovered = true;
    return;
  }
  const details = event.details && typeof event.details === "object" ? event.details as Record<string, unknown> : {};
  const exitCode = typeof details.exitCode === "number" ? details.exitCode : undefined;
  signals.set(key, {
    toolName: event.toolName,
    inputHash: key,
    count: (existing?.count ?? 0) + 1,
    ...(exitCode === undefined ? {} : { exitCode }),
    cancelled: Boolean(details.cancelled),
    timedOut: Boolean(details.timedOut),
    recovered: existing?.recovered ?? false,
  });
}

function serializedToolSignals(signals: Map<string, ToolErrorSignal>): Array<Record<string, unknown>> {
  return [...signals.values()].map((signal) => ({
    ...signal,
    classification: signal.recovered ? "recovered" : signal.timedOut ? "infrastructure" : "unknown",
  }));
}

export default function qualityLifecycle(pi: ExtensionAPI, dependencies: Dependencies = {}): void {
  const runAgnt = dependencies.runAgnt ?? runAgntJson;
  let observe = dependencies.observe;
  let activeBeadId: string | undefined;
  let interactivePrompt: unknown;
  let interactiveOutput: unknown;
  let interactiveExecution: Record<string, unknown> = { executionOutcome: "unknown" };
  const interactiveToolSignals = new Map<string, ToolErrorSignal>();

  if (!observe) {
    pi.events?.emit(PROJECTION_OBSERVE_REQUEST, (provided: unknown) => {
      if (typeof provided === "function") observe = provided as Observe;
    });
  }

  const captureLocal = async (
    phase: "session-start" | "agent-settled",
    ctx: ExtensionContext,
  ): Promise<LocalCapture> => {
    const currentSessionId = sessionId(ctx);
    if (!currentSessionId) return { localCaptureStatus: "unavailable", localCaptureGap: "session-id-unavailable" };
    const signal = AbortSignal.timeout(LOCAL_CAPTURE_TIMEOUT_MS);

    if (!activeBeadId) {
      let status: Record<string, unknown>;
      try {
        status = await runAgnt(
          ["work", "status", "--session-id", currentSessionId],
          ctx.cwd,
          signal,
          "agnt work status",
        );
      } catch {
        return { localCaptureStatus: "unavailable", localCaptureGap: "work-item-status-unavailable" };
      }
      if (status.status !== "ok" || (status.activeBeadId !== null && typeof status.activeBeadId !== "string")) {
        return { localCaptureStatus: "unavailable", localCaptureGap: "work-item-status-invalid" };
      }
      if (status.activeBeadId === null) {
        return { localCaptureStatus: "unavailable", localCaptureGap: "work-item-unassigned" };
      }
      activeBeadId = status.activeBeadId;
    }

    const leafId = ctx.sessionManager?.getLeafId?.();
    const evidenceId = phase === "session-start"
      ? currentSessionId
      : typeof leafId === "string" && leafId ? leafId : currentSessionId;
    const evidenceRefs = [`${phase === "session-start" ? "invocation" : "result"}:${evidenceId}`];
    const payload = {
      schemaVersion: 1,
      recordType: "invocation",
      sessionId: currentSessionId,
      beadId: activeBeadId,
      evidenceRefs,
    };
    try {
      const result = await runAgnt(
        ["quality", "capture", "--payload", JSON.stringify(payload), "--json"],
        ctx.cwd,
        signal,
        "agnt quality capture",
      );
      if (result.status !== "linked" || result.beadId !== activeBeadId) {
        return { localCaptureStatus: "unavailable", localCaptureGap: "quality-capture-invalid" };
      }
    } catch {
      return { localCaptureStatus: "unavailable", localCaptureGap: "quality-capture-failed" };
    }
    return { localCaptureStatus: "captured" };
  };

  pi.on("session_start", async (_event, ctx) => {
    if (process.env.PI_SUBAGENT_SOCKET) return;
    activeBeadId = undefined;
    const capture = await captureLocal("session-start", ctx);
    if (capture.localCaptureGap && capture.localCaptureGap !== "work-item-unassigned") {
      console.error(`[quality-capture] session start unavailable: ${capture.localCaptureGap}`);
    }
  });

  pi.on("before_agent_start", (event) => {
    if (process.env.PI_SUBAGENT_SOCKET) return;
    interactivePrompt = boundedInteractiveValue(event.prompt);
    interactiveOutput = undefined;
    interactiveExecution = { executionOutcome: "unknown" };
    interactiveToolSignals.clear();
  });

  pi.on("agent_end", (event) => {
    if (process.env.PI_SUBAGENT_SOCKET) return;
    interactiveOutput = boundedInteractiveValue(assistantOutput(event.messages));
    interactiveExecution = assistantExecutionMetadata(event.messages);
  });

  pi.on("agent_settled", async (_event, ctx) => {
    if (process.env.PI_SUBAGENT_SOCKET || interactivePrompt === undefined) return;
    const input = interactivePrompt;
    const output = interactiveOutput;
    const toolErrorSignals = serializedToolSignals(interactiveToolSignals);
    const execution = interactiveExecution;
    interactivePrompt = undefined;
    interactiveOutput = undefined;
    interactiveExecution = { executionOutcome: "unknown" };
    interactiveToolSignals.clear();

    const localCapture = await captureLocal("agent-settled", ctx);
    if (output == null) return;
    if (!observe) {
      console.error("[langfuse-projection] interactive result unavailable: pi-langfuse projection observer is unavailable");
      return;
    }
    try {
      await observe("interactive-result", {
        input,
        output,
        metadata: {
          ...execution,
          ...localCapture,
          ...(toolErrorSignals.length ? { toolErrorSignals } : {}),
        },
      }, { asType: "agent", sessionId: sessionId(ctx), flush: true });
    } catch (error) {
      const reason = error instanceof Error
        && error.message.startsWith("pi-langfuse observation capture was incomplete")
        ? error.message
        : "pi-langfuse observation capture failed";
      console.error(`[langfuse-projection] interactive result unavailable: ${reason}`);
    }
  });

  pi.on("tool_result", (event) => {
    if (!process.env.PI_SUBAGENT_SOCKET) recordToolSignal(interactiveToolSignals, event);
  });
}
