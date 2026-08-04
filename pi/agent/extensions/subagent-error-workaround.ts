import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join, parse } from "node:path";
import { pathToFileURL } from "node:url";
import { runAgntJson } from "./lib/run-agnt-json.ts";

const agentDir = process.env.PI_CODING_AGENT_DIR || join(homedir(), ".pi", "agent");

type SubagentInput = {
  agent?: string;
  task?: string;
  model?: string;
  tasks?: Array<{ agent?: string; task: string; model?: string }>;
};

type SubagentResult = {
  exitCode?: number;
  task?: string;
  model?: string;
  finalOutput?: string;
  error?: string;
  usage?: {
    input?: number;
    output?: number;
    cacheRead?: number;
    cacheWrite?: number;
    cost?: number;
    turns?: number;
  };
  progressSummary?: { tokens?: number; durationMs?: number };
};

type SubagentDetails = {
  mode: "single" | "parallel";
  results: SubagentResult[];
  progress?: unknown[];
};

type ObservationAttributes = {
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  level?: "DEFAULT" | "ERROR";
};

type Observe = (
  name: string,
  attributes: ObservationAttributes,
  options: { asType: "agent"; sessionId?: string },
) => void | Promise<void>;

type ToolErrorSignal = {
  toolName: string;
  inputHash: string;
  count: number;
  exitCode?: number;
  cancelled: boolean;
  timedOut: boolean;
  recovered: boolean;
};

type Dependencies = { observe?: Observe };

function assistantOutput(messages: unknown): unknown {
  if (!Array.isArray(messages)) return undefined;
  const message = messages.findLast((item) => item && typeof item === "object" && (item as { role?: string }).role === "assistant") as { content?: unknown; stopReason?: string; errorMessage?: string } | undefined;
  if (message?.stopReason === "error") return providerError(message.errorMessage);
  if (!Array.isArray(message?.content)) return message?.content;
  const text = message.content
    .map((item) => item && typeof item === "object" && (item as { type?: string; text?: string }).type === "text" ? (item as { text?: string }).text ?? "" : "")
    .filter(Boolean)
    .join("\n");
  return text || undefined;
}

async function loadDefaultObserve(): Promise<Observe> {
  const modules = join(agentDir, "npm", "node_modules");
  const [{ startObservation, propagateAttributes }, { redactValue }, { createCapturePolicy }] = await Promise.all([
    import(pathToFileURL(join(modules, "@langfuse", "tracing", "dist", "index.mjs")).href),
    import(pathToFileURL(join(modules, "pi-langfuse", "src", "redaction.ts")).href),
    import(pathToFileURL(join(modules, "pi-langfuse", "src", "capture-policy.ts")).href),
  ]);
  return (name, attributes, options) => {
    let saved: Record<string, unknown> = {};
    try {
      saved = JSON.parse(readFileSync(join(agentDir, "pi-langfuse", "config.json"), "utf8"));
    } catch {
      // pi-langfuse owns missing/invalid config handling.
    }
    const capture = saved.capture && typeof saved.capture === "object" ? saved.capture as Record<string, string> : {};
    const policy = createCapturePolicy({
      ...capture,
      ...(typeof saved.privacyPreset === "string" ? { LANGFUSE_PRIVACY_PRESET: saved.privacyPreset } : {}),
      ...process.env,
    });
    const record = () => {
      const observation = startObservation(name, {
        ...attributes,
        input: policy.captureInputs ? redactValue(attributes.input) : undefined,
        output: policy.captureOutputs ? redactValue(attributes.output) : undefined,
        metadata: redactValue(attributes.metadata),
      }, { asType: options.asType });
      observation.end();
    };
    return options.sessionId
      ? propagateAttributes({ sessionId: options.sessionId }, record)
      : record();
  };
}

function langfuseSessionId(ctx?: ExtensionContext): string | undefined {
  const sessionFile = ctx?.sessionManager?.getSessionFile?.();
  return sessionFile ? parse(sessionFile).name : undefined;
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

function providerError(message?: string): string {
  if (message && /OpenrouterException/i.test(message) && /Key limit exceeded \(monthly limit\)/i.test(message)) {
    return `upstream OpenRouter monthly limit exceeded${message.startsWith("403:") ? " (HTTP 403 via Olla)" : ""}`;
  }
  return message || "unknown upstream error";
}

async function runtimeDirectory(kind: string, cwd: string): Promise<string> {
  const result = await runAgntJson(["runtime-path", kind], cwd, undefined, "agnt runtime-path");
  if (typeof result.path !== "string" || !result.path) throw new Error("agnt runtime-path returned no path");
  return result.path;
}

function targetFor(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
  ctx: ExtensionContext,
): string | undefined {
  const requested = input.tasks?.[index]?.model ?? input.model;
  if (requested?.includes("/")) return requested;
  const model = result.model ?? requested ?? ctx.model?.id;
  return model && ctx.model ? `${ctx.model.provider}/${model}` : undefined;
}

function metricRecord(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
  toolCallId: string,
  startedMs: number,
  endedMs: number,
  ctx: ExtensionContext,
): Record<string, unknown> | undefined {
  if (input.tasks?.[index]?.agent ?? input.agent) return undefined;
  const target = targetFor(input, result, index, ctx);
  if (!target) return undefined;

  const [provider, ...modelParts] = target.split("/");
  const model = modelParts.join("/");
  const prompt = input.tasks?.[index]?.task ?? input.task ?? result.task ?? "";
  const durationMs = Math.max(0, endedMs - startedMs);
  const workerElapsedMs = Math.max(0, Math.round(result.progressSummary?.durationMs ?? durationMs));
  const startedAt = new Date(startedMs).toISOString();
  const endedAt = new Date(endedMs).toISOString();
  const usage = result.usage;
  const inputTokens = Math.max(0, Math.round(usage?.input ?? 0));
  const outputTokens = Math.max(0, Math.round(usage?.output ?? 0));
  const cacheRead = Math.max(0, Math.round(usage?.cacheRead ?? 0));
  const cacheWrite = Math.max(0, Math.round(usage?.cacheWrite ?? 0));
  const totalTokens = Math.max(
    0,
    Math.round(result.progressSummary?.tokens ?? (inputTokens + outputTokens + cacheRead + cacheWrite)),
  );
  const cost = Math.max(0, Number(usage?.cost ?? 0));
  const providerRequests = Math.max(0, Math.round(usage?.turns ?? 0));
  const recordId = createHash("sha256")
    .update(`${startedAt}|${target}|peer|${toolCallId}|${index}`)
    .digest("hex")
    .slice(0, 16);

  return {
    schemaVersion: 1,
    recordId,
    startedAt,
    endedAt,
    elapsedMs: durationMs,
    workerElapsedMs,
    task: "peer",
    riskCategory: null,
    thinkingLevel: null,
    invocationMode: "subagent",
    providerRequests,
    contextChars: prompt.length,
    estimatedInputTokens: prompt ? Math.ceil(prompt.length / 4) : 0,
    outcome: "unknown",
    humanOverride: false,
    fallbackUsed: false,
    provider,
    model,
    target,
    exitCode: result.exitCode ?? 1,
    usageSource: "archimedes-subagent",
    usage: {
      input: inputTokens,
      output: outputTokens,
      cacheRead,
      cacheWrite,
      totalTokens,
      providerRequests,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: cost },
    },
    responseChars: result.finalOutput?.length ?? 0,
    stderrChars: result.error?.length ?? 0,
    kind: "subagent",
  };
}

async function recordSubagentMetrics(
  event: { toolCallId: string; input: Record<string, unknown>; details?: unknown },
  ctx: ExtensionContext,
  startedMs: number,
): Promise<void> {
  const details = event.details as SubagentDetails | undefined;
  if (!details?.results?.length) return;

  const input = event.input as SubagentInput;
  const endedMs = Date.now();
  const records = details.results
    .map((result, index) => metricRecord(input, result, index, event.toolCallId, startedMs, endedMs, ctx))
    .filter((record): record is Record<string, unknown> => record !== undefined);
  if (records.length === 0) return;

  const metricsDir = await runtimeDirectory("metrics/invocations", ctx.cwd);
  await mkdir(metricsDir, { recursive: true });
  await Promise.all(records.map((record) => {
    const target = String(record.target).replace(/[^a-zA-Z0-9._-]+/g, "__");
    const name = `${String(record.endedAt).replace(/\D/g, "").slice(0, 17)}-${target}-${record.recordId}.metrics.json`;
    return writeFile(join(metricsDir, name), `${JSON.stringify(record, null, 2)}\n`, "utf8");
  }));
}

export default function subagentErrorWorkaround(pi: ExtensionAPI, dependencies: Dependencies = {}): void {
  const starts = new Map<string, number>();
  let observe = dependencies.observe;
  let observeLoad: Promise<Observe> | undefined;
  const getObserve = () => observe
    ? Promise.resolve(observe)
    : (observeLoad ??= loadDefaultObserve().then((loaded) => (observe = loaded)));
  let interactivePrompt: unknown;
  let interactiveOutput: unknown;
  const interactiveToolSignals = new Map<string, ToolErrorSignal>();

  pi.on("session_start", async () => {
    if (!observe) await getObserve();
  });

  pi.on("before_agent_start", (event) => {
    if (!process.env.PI_SUBAGENT_SOCKET) {
      interactivePrompt = event.prompt;
      interactiveToolSignals.clear();
    }
  });

  pi.on("agent_end", (event) => {
    if (!process.env.PI_SUBAGENT_SOCKET) interactiveOutput = assistantOutput(event.messages);
  });

  pi.on("agent_settled", async (_event, ctx) => {
    if (process.env.PI_SUBAGENT_SOCKET || interactivePrompt === undefined) return;
    const input = interactivePrompt;
    const output = interactiveOutput;
    const toolErrorSignals = serializedToolSignals(interactiveToolSignals);
    interactivePrompt = undefined;
    interactiveOutput = undefined;
    interactiveToolSignals.clear();
    if (output == null) return;
    try {
      await (await getObserve())("interactive-result", {
        input,
        output,
        ...(toolErrorSignals.length ? { metadata: { toolErrorSignals } } : {}),
      }, { asType: "agent", sessionId: langfuseSessionId(ctx) });
    } catch (error) {
      console.error("[langfuse-projection] could not record interactive result:", error);
    }
  });

  pi.on("message_end", (event) => {
    const message = event.message as { role?: string; provider?: string; model?: string; stopReason?: string; errorMessage?: string };
    if (!process.env.PI_SUBAGENT_SOCKET || message.role !== "assistant" || message.stopReason !== "error") return;
    const target = [message.provider, message.model].filter(Boolean).join("/") || "provider";
    console.error(`[subagent] ${target} failed: ${providerError(message.errorMessage)}`);
    process.exitCode = 1;
  });

  pi.on("tool_call", (event) => {
    if (event.toolName === "subagent") starts.set(event.toolCallId, Date.now());
  });

  pi.on("tool_result", async (event, ctx) => {
    if (!process.env.PI_SUBAGENT_SOCKET) recordToolSignal(interactiveToolSignals, event);
    if (event.toolName !== "subagent") return;

    const startedMs = starts.get(event.toolCallId) ?? Date.now();
    starts.delete(event.toolCallId);
    try {
      await recordSubagentMetrics(event, ctx, startedMs);
    } catch (error) {
      console.error("[subagent-metrics] could not record invocation:", error);
    }

    const details = event.details as SubagentDetails | undefined;
    if (details?.results?.length) {
      await Promise.all(details.results.map(async (result, index) => {
        const task = (event.input as SubagentInput).tasks?.[index]?.task ?? (event.input as SubagentInput).task ?? result.task;
        try {
          await (await getObserve())("subagent-result", {
            input: task,
            output: result.finalOutput ?? result.error,
            metadata: { index, model: result.model, exitCode: result.exitCode ?? 1 },
            level: result.exitCode === 0 ? "DEFAULT" : "ERROR",
          }, { asType: "agent", sessionId: langfuseSessionId(ctx) });
        } catch (error) {
          console.error("[langfuse-projection] could not record subagent result:", error);
        }
      }));
    }
    if (!details || !Array.isArray(details.results)) return;
    if (details.results.some((result) => result.exitCode !== 0)) return { isError: true };
    if (details.results.length > 0) return;

    const input = event.input as SubagentInput;
    const error = event.content.find((part) => part.type === "text")?.text
      ?? "Subagent failed without error details";
    const tasks = input.tasks ?? [];

    return {
      isError: true,
      details: {
        ...details,
        results: [{
          agent: input.agent ?? (tasks.map((task) => task.agent).filter(Boolean).join(", ") || "subagent"),
          task: input.task ?? tasks.map((task) => task.task).join("; "),
          exitCode: 1,
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, turns: 0 },
          model: input.model ?? tasks[0]?.model,
          finalOutput: undefined,
          error,
          progress: undefined,
          progressSummary: undefined,
        }],
      },
    };
  });
}
