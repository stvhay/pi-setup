import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join, parse } from "node:path";
import { pathToFileURL } from "node:url";
import { runAgntJson } from "./lib/run-agnt-json.ts";
import {
  persistDelegatedResult as persistRuntimeDelegatedResult,
  type DelegatedArtifactPayload,
} from "./lib/runtime-artifacts.ts";

const agentDir = process.env.PI_CODING_AGENT_DIR || join(homedir(), ".pi", "agent");

type OutputContract = "inline" | "artifact" | "status-only" | "pass-no-findings";
type NormalizedOutputContract = OutputContract | "unknown";

const OUTPUT_CONTRACTS = new Set<OutputContract>(["inline", "artifact", "status-only", "pass-no-findings"]);
const EVALUATION_OUTPUT_MAX_CHARS = 12_000;

type SubagentInput = {
  agent?: string;
  task?: string;
  model?: string;
  outputContract?: OutputContract;
  tasks?: Array<{ agent?: string; task: string; model?: string; outputContract?: OutputContract }>;
};

type ArtifactEnvelope = {
  status: "persisted" | "failed";
  refs: string[];
  failureClass?: "resolution" | "write";
};

type SubagentResult = {
  agent?: string;
  childSessionId?: string;
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
  artifact?: ArtifactEnvelope;
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

type ProviderFailureClass = "quota" | "credit" | "authentication" | "availability";
type ProviderCircuit = (
  action: "open" | "success",
  provider: string,
  reason: ProviderFailureClass | undefined,
  cwd: string,
) => void | Promise<void>;
type ActiveProviderCircuits = (cwd: string) => string[] | Promise<string[]>;
type PersistDelegatedResult = (root: string, payload: DelegatedArtifactPayload) => Promise<string>;
type Dependencies = {
  observe?: Observe;
  providerCircuit?: ProviderCircuit;
  activeProviderCircuits?: ActiveProviderCircuits;
  persistDelegatedResult?: PersistDelegatedResult;
};

type InvocationStart = {
  startedMs: number;
  invocationIds: string[];
};

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

function resultExecutionOutcome(exitCode: number): "succeeded" | "failed" | "unavailable" {
  return exitCode === 0 ? "succeeded" : exitCode === 124 ? "unavailable" : "failed";
}

function outputContract(input: SubagentInput, index: number): NormalizedOutputContract {
  const value = input.tasks?.[index]?.outputContract ?? input.outputContract;
  return OUTPUT_CONTRACTS.has(value as OutputContract) ? value as OutputContract : "unknown";
}

function evaluationContext(
  task: string | undefined,
  result: SubagentResult,
  contract: NormalizedOutputContract,
): Record<string, unknown> {
  return {
    task: task ?? null,
    outputContract: contract,
    executionOutcome: resultExecutionOutcome(result.exitCode ?? 1),
    artifactStatus: result.artifact?.status ?? "failed",
    artifactContentStatus: result.artifact?.status === "persisted" && Boolean(result.finalOutput ?? result.error)
      ? "available"
      : "unavailable",
    artifactReferenceCount: result.artifact?.refs.length ?? 0,
    artifactFailureClass: result.artifact?.failureClass ?? null,
  };
}

function evaluationOutput(result: SubagentResult): string {
  const value = result.finalOutput ?? result.error;
  if (!value) return "[delegated output unavailable]";
  if (value.length <= EVALUATION_OUTPUT_MAX_CHARS) return value;
  return `${value.slice(0, EVALUATION_OUTPUT_MAX_CHARS)}\n[delegated output truncated at ${EVALUATION_OUTPUT_MAX_CHARS} characters]`;
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
  try {
    const sessionId = ctx?.sessionManager?.getSessionId?.();
    if (typeof sessionId === "string" && sessionId) return sessionId;
  } catch {
    // Keep compatibility with older session managers.
  }
  try {
    const sessionFile = ctx?.sessionManager?.getSessionFile?.();
    return sessionFile ? parse(sessionFile).name : undefined;
  } catch {
    return undefined;
  }
}

function childSessionId(result: SubagentResult): string | null {
  const value = result.childSessionId;
  return typeof value === "string" && value.length > 0 && value.length <= 200 ? value : null;
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

export function providerFailureClass(message?: string): ProviderFailureClass | undefined {
  const text = String(message ?? "").slice(0, 12_000).toLowerCase();
  if (/\b(?:insufficient[_ -]?quota|quota (?:has been )?exceeded|monthly limit|key limit exceeded|usage limit exceeded)\b/.test(text)) return "quota";
  if (/\b(?:http\s*)?402\b|\binsufficient (?:credits?|credit balance)\b|\bcredit balance\b|\bavailable credits? can only cover\b|\bcan afford (?:only )?\d+ tokens\b/.test(text)) return "credit";
  if (/\b(?:http\s*)?401\b|\bunauthorized\b|\bauthentication failed\b|\b(?:invalid|missing|expired|revoked) (?:api[ _-]?key|token|credentials?)\b|\bno (?:api[ _-]?key|auth credentials?|credentials?)(?: found)?\b/.test(text)) return "authentication";
  if (/\b(?:http(?: status)?|status code|returned(?: http)?)\s*[:=]?\s*(?:502|503|504)\b|\b(?:502 bad gateway|503 service unavailable|504 gateway timeout)\b/.test(text)) return "availability";
  return undefined;
}

function providerError(message?: string): string {
  if (message && /OpenrouterException/i.test(message) && /Key limit exceeded \(monthly limit\)/i.test(message)) {
    return `upstream OpenRouter monthly limit exceeded${message.startsWith("403:") ? " (HTTP 403 via Olla)" : ""}`;
  }
  return message || "unknown upstream error";
}

async function loadActiveProviderCircuits(cwd: string): Promise<string[]> {
  const result = await runAgntJson(["provider-circuit", "status"], cwd, undefined, "agnt provider-circuit");
  const circuits = result.circuits;
  return circuits && typeof circuits === "object" && !Array.isArray(circuits) ? Object.keys(circuits) : [];
}

async function updateProviderCircuit(
  action: "open" | "success",
  provider: string,
  reason: ProviderFailureClass | undefined,
  cwd: string,
): Promise<void> {
  const args = action === "open"
    ? ["provider-circuit", "open", "--provider", provider, "--reason", String(reason)]
    : ["provider-circuit", "success", "--provider", provider];
  await runAgntJson(args, cwd, undefined, "agnt provider-circuit");
}

async function runtimeDirectory(kind: string, cwd: string): Promise<string> {
  const result = await runAgntJson(["runtime-path", kind], cwd, undefined, "agnt runtime-path");
  if (typeof result.path !== "string" || !result.path) throw new Error("agnt runtime-path returned no path");
  return result.path;
}

function artifactMetadata(result: SubagentResult): Record<string, unknown> {
  const sessionId = childSessionId(result);
  return {
    ...(sessionId ? { childSessionId: sessionId } : {}),
    artifactRefs: result.artifact?.refs ?? [],
    artifactStatus: result.artifact?.status ?? "failed",
    ...(result.artifact?.failureClass ? { artifactFailureClass: result.artifact.failureClass } : {}),
  };
}

async function persistSubagentArtifacts(
  input: SubagentInput,
  details: SubagentDetails,
  invocation: InvocationStart,
  ctx: ExtensionContext,
  persist: PersistDelegatedResult,
): Promise<SubagentDetails> {
  let root: string;
  try {
    root = await runtimeDirectory("delegated-results", ctx.cwd);
  } catch {
    return {
      ...details,
      results: details.results.map((result) => ({
        ...result,
        artifact: { status: "failed", refs: [], failureClass: "resolution" },
      })),
    };
  }

  const parentSessionId = langfuseSessionId(ctx) ?? null;
  return {
    ...details,
    results: await Promise.all(details.results.map(async (result, childIndex): Promise<SubagentResult> => {
      const invocationId = invocation.invocationIds[childIndex];
      try {
        const ref = await persist(root, {
          invocationId,
          parentSessionId,
          childSessionId: childSessionId(result),
          childIndex,
          executionOutcome: resultExecutionOutcome(result.exitCode ?? 1),
          outputContract: outputContract(input, childIndex),
          exitCode: result.exitCode ?? 1,
          model: result.model ?? null,
          finalOutput: result.finalOutput ?? null,
          error: result.error ?? null,
        });
        return { ...result, artifact: { status: "persisted", refs: [ref] } };
      } catch {
        return {
          ...result,
          artifact: { status: "failed", refs: [], failureClass: "write" },
        };
      }
    })),
  };
}

type ModelDimensions = {
  provider: string | null;
  model: string | null;
  target: string | null;
  thinkingLevel: "default" | null;
  modelDimensionsStatus: "available" | "unavailable" | "unavailable-named-agent";
};

function modelDimensions(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
  ctx: ExtensionContext,
): ModelDimensions {
  const task = input.tasks?.[index];
  const namedAgent = task?.agent ?? input.agent;
  if (namedAgent) {
    return {
      provider: null,
      model: result.model ?? null,
      target: null,
      thinkingLevel: null,
      modelDimensionsStatus: "unavailable-named-agent",
    };
  }

  const requested = task?.model ?? input.model;
  const separator = requested?.indexOf("/") ?? -1;
  const requestedProvider = separator > 0 ? requested!.slice(0, separator) : undefined;
  const requestedModel = separator > 0 ? requested!.slice(separator + 1) : requested;
  const provider = requestedProvider ?? ctx.model?.provider ?? null;
  const model = result.model ?? requestedModel ?? ctx.model?.id ?? null;
  const target = provider && model ? `${provider}/${model}` : null;
  return {
    provider,
    model,
    target,
    thinkingLevel: target ? "default" : null,
    modelDimensionsStatus: target ? "available" : "unavailable",
  };
}

function targetFor(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
  ctx: ExtensionContext,
): string | undefined {
  return modelDimensions(input, result, index, ctx).target ?? undefined;
}

function metricRecord(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
  invocationId: string,
  toolCallId: string,
  startedMs: number,
  endedMs: number,
  ctx: ExtensionContext,
  failureClass: ProviderFailureClass | undefined,
): Record<string, unknown> | undefined {
  if (input.tasks?.[index]?.agent ?? input.agent) return undefined;
  const dimensions = modelDimensions(input, result, index, ctx);
  const target = dimensions.target;
  if (!target) return undefined;

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

  const exitCode = result.exitCode ?? 1;
  return {
    schemaVersion: 2,
    invocationId,
    recordId,
    parentSessionId: langfuseSessionId(ctx) ?? null,
    childSessionId: childSessionId(result),
    workItem: null,
    childIndex: index,
    startedAt,
    endedAt,
    durationMs,
    elapsedMs: durationMs,
    status: exitCode === 0 ? "succeeded" : "failed",
    executionOutcome: resultExecutionOutcome(exitCode),
    failureClass: exitCode === 0 ? null : exitCode === 124 ? "timeout" : failureClass ? "provider" : "process",
    providerFailureClass: exitCode === 0 ? null : failureClass ?? null,
    artifactRefs: result.artifact?.refs ?? [],
    artifactStatus: result.artifact?.status ?? "failed",
    artifactFailureClass: result.artifact?.failureClass ?? null,
    outputContract: outputContract(input, index),
    workerElapsedMs,
    task: "peer",
    riskCategory: null,
    thinkingLevel: dimensions.thinkingLevel,
    invocationMode: "subagent",
    providerRequests,
    contextChars: prompt.length,
    estimatedInputTokens: prompt ? Math.ceil(prompt.length / 4) : 0,
    outcome: "unknown",
    humanOverride: false,
    fallbackUsed: false,
    provider: dimensions.provider,
    model: dimensions.model,
    target,
    exitCode,
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
  invocation: InvocationStart,
  providerFailureClasses: Array<ProviderFailureClass | undefined>,
): Promise<void> {
  const details = event.details as SubagentDetails | undefined;
  if (!details?.results?.length) return;

  const input = event.input as SubagentInput;
  const endedMs = Date.now();
  const records = details.results
    .map((result, index) => metricRecord(input, result, index, invocation.invocationIds[index], event.toolCallId, invocation.startedMs, endedMs, ctx, providerFailureClasses[index]))
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
  const starts = new Map<string, InvocationStart>();
  const persistDelegatedResult = dependencies.persistDelegatedResult ?? persistRuntimeDelegatedResult;
  const providerCircuit = dependencies.providerCircuit ?? updateProviderCircuit;
  const activeProviderCircuits = dependencies.activeProviderCircuits ?? loadActiveProviderCircuits;
  const openProviders = new Set<string>();
  const setProviderCircuit = async (
    action: "open" | "success",
    provider: string,
    reason: ProviderFailureClass | undefined,
    cwd: string,
  ): Promise<void> => {
    if (action === "success" && !openProviders.has(provider)) return;
    await providerCircuit(action, provider, reason, cwd);
    if (action === "open") openProviders.add(provider);
    else openProviders.delete(provider);
  };
  let observe = dependencies.observe;
  let observeLoad: Promise<Observe> | undefined;
  const getObserve = () => observe
    ? Promise.resolve(observe)
    : (observeLoad ??= loadDefaultObserve().then((loaded) => (observe = loaded)));
  let interactivePrompt: unknown;
  let interactiveOutput: unknown;
  let interactiveExecution: Record<string, unknown> = { executionOutcome: "unknown" };
  const interactiveToolSignals = new Map<string, ToolErrorSignal>();

  pi.on("session_start", async (_event, ctx) => {
    const work: Array<Promise<unknown>> = [];
    if (!observe) work.push(getObserve());
    if (!process.env.PI_SUBAGENT_SOCKET) {
      work.push(Promise.resolve(activeProviderCircuits(ctx.cwd)).then((providers) => {
        for (const provider of providers) openProviders.add(provider);
      }).catch((error) => {
        console.error("[provider-circuit] could not read provider state:", error);
      }));
    }
    await Promise.all(work);
  });

  pi.on("before_agent_start", (event) => {
    if (!process.env.PI_SUBAGENT_SOCKET) {
      interactivePrompt = event.prompt;
      interactiveOutput = undefined;
      interactiveExecution = { executionOutcome: "unknown" };
      interactiveToolSignals.clear();
    }
  });

  pi.on("agent_end", (event) => {
    if (!process.env.PI_SUBAGENT_SOCKET) {
      interactiveOutput = assistantOutput(event.messages);
      interactiveExecution = assistantExecutionMetadata(event.messages);
    }
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
    if (output == null) return;
    try {
      await (await getObserve())("interactive-result", {
        input,
        output,
        metadata: {
          ...execution,
          ...(toolErrorSignals.length ? { toolErrorSignals } : {}),
        },
      }, { asType: "agent", sessionId: langfuseSessionId(ctx) });
    } catch (error) {
      console.error("[langfuse-projection] could not record interactive result:", error);
    }
  });

  pi.on("message_end", async (event, ctx) => {
    const message = event.message as { role?: string; provider?: string; model?: string; stopReason?: string; errorMessage?: string };
    if (message.role !== "assistant") return;
    const classification = providerFailureClass(message.errorMessage);
    if (message.provider && (message.stopReason !== "error" || classification)) {
      try {
        await setProviderCircuit(
          message.stopReason === "error" ? "open" : "success",
          message.provider,
          classification,
          ctx?.cwd ?? process.cwd(),
        );
      } catch (error) {
        console.error("[provider-circuit] could not update provider state:", error);
      }
    }
    if (!process.env.PI_SUBAGENT_SOCKET || message.stopReason !== "error") return;
    const target = [message.provider, message.model].filter(Boolean).join("/") || "provider";
    console.error(`[subagent] ${target} failed: ${providerError(message.errorMessage)}`);
    process.exitCode = 1;
  });

  pi.on("tool_call", (event) => {
    if (event.toolName !== "subagent") return;
    const input = event.input as SubagentInput;
    const count = Math.max(1, input.tasks?.length ?? 1);
    starts.set(event.toolCallId, {
      startedMs: Date.now(),
      invocationIds: Array.from({ length: count }, () => randomUUID()),
    });
  });

  pi.on("tool_result", async (event, ctx) => {
    if (!process.env.PI_SUBAGENT_SOCKET) recordToolSignal(interactiveToolSignals, event);
    if (event.toolName !== "subagent") return;

    let details = event.details as SubagentDetails | undefined;
    const invocation = starts.get(event.toolCallId) ?? { startedMs: Date.now(), invocationIds: [] };
    starts.delete(event.toolCallId);
    if (!details || !Array.isArray(details.results)) return;

    const input = event.input as SubagentInput;
    const synthesized = details.results.length === 0;
    if (synthesized) {
      const tasks = input.tasks ?? [];
      details = {
        ...details,
        results: [{
          agent: input.agent ?? (tasks.map((task) => task.agent).filter(Boolean).join(", ") || "subagent"),
          task: input.task ?? tasks.map((task) => task.task).join("; "),
          exitCode: 1,
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, turns: 0 },
          error: event.content.find((part) => part.type === "text")?.text
            ?? "Subagent failed without error details",
        }],
      };
    }
    while (invocation.invocationIds.length < Math.max(1, details.results.length)) {
      invocation.invocationIds.push(randomUUID());
    }
    details = await persistSubagentArtifacts(input, details, invocation, ctx, persistDelegatedResult);
    const providerFailureClasses = details.results.map((result) => providerFailureClass(result.error));
    await Promise.all(details.results.map(async (result, index) => {
      if (input.tasks?.[index]?.agent ?? input.agent) return;
      const target = targetFor(input, result, index, ctx);
      if (!target) return;
      const provider = target.split("/", 1)[0];
      const classification = providerFailureClasses[index];
      if (result.exitCode !== 0 && !classification) return;
      try {
        await setProviderCircuit(result.exitCode === 0 ? "success" : "open", provider, classification, ctx.cwd);
      } catch (error) {
        console.error("[provider-circuit] could not update provider state:", error);
      }
    }));
    try {
      await recordSubagentMetrics({ ...event, details }, ctx, invocation, providerFailureClasses);
    } catch (error) {
      console.error("[subagent-metrics] could not record invocation:", error);
    }

    await Promise.all(details.results.map(async (result, index) => {
      const task = input.tasks?.[index]?.task ?? input.task ?? result.task;
      const dimensions = modelDimensions(input, result, index, ctx);
      const contract = outputContract(input, index);
      try {
        await (await getObserve())("subagent-result", {
          input: evaluationContext(task, result, contract),
          output: evaluationOutput(result),
          metadata: {
            invocationId: invocation.invocationIds[index],
            index,
            ...dimensions,
            executionOutcome: resultExecutionOutcome(result.exitCode ?? 1),
            outputContract: contract,
            ...artifactMetadata(result),
            exitCode: result.exitCode ?? 1,
            ...(providerFailureClasses[index] ? { providerFailureClass: providerFailureClasses[index] } : {}),
          },
          level: result.exitCode === 0 ? "DEFAULT" : "ERROR",
        }, { asType: "agent", sessionId: langfuseSessionId(ctx) });
      } catch (error) {
        console.error("[langfuse-projection] could not record subagent result:", error);
      }
    }));

    const persistedRefs = details.results.flatMap((result) => result.artifact?.refs ?? []);
    const artifactMessages = [
      ...(persistedRefs.length ? [{ type: "text" as const, text: `Delegated artifacts:\n${persistedRefs.map((ref) => `- ${ref}`).join("\n")}` }] : []),
      ...details.results.flatMap((result, index) => result.artifact?.status === "failed"
        ? [{ type: "text" as const, text: `Delegated artifact unavailable for child ${index} (${result.artifact.failureClass}).` }]
        : []),
    ];
    const patch = { content: [...event.content, ...artifactMessages], details };
    if (synthesized || details.results.some((result) => result.exitCode !== 0)) return { ...patch, isError: true };
    return patch;
  });
}
