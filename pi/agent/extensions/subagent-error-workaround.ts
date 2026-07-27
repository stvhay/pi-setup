import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import { access, mkdir, writeFile } from "node:fs/promises";
import { dirname, join, parse, resolve } from "node:path";

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

function providerError(message?: string): string {
  if (message && /OpenrouterException/i.test(message) && /Key limit exceeded \(monthly limit\)/i.test(message)) {
    return `upstream OpenRouter monthly limit exceeded${message.startsWith("403:") ? " (HTTP 403 via Olla)" : ""}`;
  }
  return message || "unknown upstream error";
}

async function repositoryRoot(cwd: string): Promise<string> {
  let current = resolve(cwd);
  const filesystemRoot = parse(current).root;
  while (true) {
    try {
      await access(join(current, ".git"));
      return current;
    } catch {
      if (current === filesystemRoot) return resolve(cwd);
      current = dirname(current);
    }
  }
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

  const root = await repositoryRoot(ctx.cwd);
  const metricsDir = join(root, ".pi", "metrics", "invocations");
  await mkdir(metricsDir, { recursive: true });
  await Promise.all(records.map((record) => {
    const target = String(record.target).replace(/[^a-zA-Z0-9._-]+/g, "__");
    const name = `${String(record.endedAt).replace(/\D/g, "").slice(0, 17)}-${target}-${record.recordId}.metrics.json`;
    return writeFile(join(metricsDir, name), `${JSON.stringify(record, null, 2)}\n`, "utf8");
  }));
}

export default function subagentErrorWorkaround(pi: ExtensionAPI): void {
  const starts = new Map<string, number>();

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
    if (event.toolName !== "subagent") return;

    const startedMs = starts.get(event.toolCallId) ?? Date.now();
    starts.delete(event.toolCallId);
    try {
      await recordSubagentMetrics(event, ctx, startedMs);
    } catch (error) {
      console.error("[subagent-metrics] could not record invocation:", error);
    }

    const details = event.details as SubagentDetails | undefined;
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
