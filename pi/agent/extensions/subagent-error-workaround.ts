import { getAgentDir, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createHash, randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { join, parse } from "node:path";
import { pathToFileURL } from "node:url";
import type {
  SubagentDetails as PublicSubagentDetails,
  SubagentLimits,
  SubagentOutputContract,
  SubagentResult as PublicSubagentResult,
  SubagentThinkingLevel,
} from "@pi-archimedes/subagent/types";
import { runAgntJson } from "./lib/run-agnt-json.ts";
import { persistDelegatedResult as persistRuntimeDelegatedResult } from "./lib/runtime-artifacts.ts";

const agentDir = getAgentDir();
type ArchimedesTypesModule = typeof import("@pi-archimedes/subagent/types");

type NormalizedOutputContract = SubagentOutputContract | "unknown";
type EffectiveMode = "agentic" | "one-shot" | "unknown";
type ChildTraceAvailability = "expected-available" | "expected-unavailable" | "unknown";
type RouteReceipt = {
  schemaVersion: 1;
  authority: "agnt-route";
  routingTask: string;
  target: string;
  provider: string;
  model: string;
  mode: "agentic" | "one-shot";
  thinking: SubagentThinkingLevel;
};

const PROJECTION_OBSERVE_REQUEST = "pi-setup:langfuse-projection-observe";
const EVALUATION_OUTPUT_MAX_CHARS = 12_000;
const INLINE_OUTPUT_MAX_CHARS = 12_000;
const ARTIFACT_MESSAGE_MAX_CHARS = 4_000;
const TERMINATION_MESSAGE_MAX_CHARS = 4_000;
const ROUTING_TASK = /^[a-z][a-z0-9-]{0,63}$/;
const THINKING_LEVELS = new Set<SubagentThinkingLevel>(["off", "minimal", "low", "medium", "high", "xhigh"]);

type SubagentLimitKey = keyof SubagentLimits;
type SubagentTaskInput = {
  agent?: string;
  task: string;
  model?: string;
  mode?: "agentic" | "one-shot";
  limits?: SubagentLimits;
  outputContract?: SubagentOutputContract;
  routingTask?: string;
  route?: { task?: string };
  thinking?: SubagentThinkingLevel;
};
type SubagentInput = {
  agent?: string;
  task?: string;
  model?: string;
  mode?: "agentic" | "one-shot";
  limits?: SubagentLimits;
  outputContract?: SubagentOutputContract;
  routingTask?: string;
  route?: { task?: string };
  thinking?: SubagentThinkingLevel;
  tasks?: SubagentTaskInput[];
};

type ArtifactEnvelope = {
  status: "persisted" | "failed";
  refs: string[];
  failureClass?: "resolution" | "write";
};

type SubagentResult = PublicSubagentResult & { artifact?: ArtifactEnvelope; routeReceipt?: RouteReceipt };
type SubagentDetails = Omit<PublicSubagentDetails, "results"> & {
  results: SubagentResult[];
  routeFailure?: boolean;
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
  options: { asType: "agent"; sessionId?: string; flush?: boolean },
) => void | Promise<void>;

type ProviderFailureClass = "quota" | "credit" | "authentication" | "availability";
type ProviderCircuit = (
  action: "open" | "success",
  provider: string,
  reason: ProviderFailureClass | undefined,
  cwd: string,
) => void | Promise<void>;
type ActiveProviderCircuits = (cwd: string) => string[] | Promise<string[]>;
type RuntimeDirectories = (kinds: string[], cwd: string) => Promise<Record<string, string>>;
type Dependencies = {
  observe?: Observe;
  providerCircuit?: ProviderCircuit;
  activeProviderCircuits?: ActiveProviderCircuits;
  runtimeDirectories?: RuntimeDirectories;
  persistDelegatedResult?: typeof persistRuntimeDelegatedResult;
  outputContracts?: readonly SubagentOutputContract[];
};

type InvocationStart = {
  startedMs: number;
  invocationIds: string[];
};

type TerminationEvidence = {
  reason: string;
  source: "caller" | "operator" | "execution-profile" | "wrapper" | "parent-cancellation" | "worker-startup" | "worker" | "provider";
  limit?: number;
  observed?: number;
  usageState: "complete" | "partial" | "unknown";
};

const LIMIT_KEY_BY_REASON: Partial<Record<string, SubagentLimitKey>> = {
  "request-limit": "maxProviderRequests",
  "tool-limit": "maxToolCalls",
  "token-limit": "maxTotalTokens",
  "output-limit": "maxOutputTokens",
  "cost-limit": "maxCostUsd",
  "time-limit": "maxDurationMs",
  "idle-limit": "maxIdleMs",
};

function positiveFinite(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : undefined;
}

function callerLimit(input: SubagentInput, index: number, key: SubagentLimitKey): number | undefined {
  const values = [
    positiveFinite(input.limits?.[key]),
    positiveFinite(input.tasks?.[index]?.limits?.[key]),
  ].filter((value): value is number => value !== undefined);
  return values.length ? Math.min(...values) : undefined;
}

function startupTimeoutMs(error: string | undefined): number | undefined {
  const match = error?.match(/no output within ([0-9]+(?:\.[0-9]+)?) minutes? of startup/i);
  return match ? Number(match[1]) * 60_000 : undefined;
}

function terminationEvidence(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
): TerminationEvidence | undefined {
  const rawReason = result.termination?.reason;
  const validReason = typeof rawReason === "string" && /^[a-z][a-z0-9-]{0,40}$/.test(rawReason)
    ? rawReason
    : undefined;
  const startupLimit = startupTimeoutMs(result.error);
  if ((!validReason || validReason === "process-error") && startupLimit !== undefined) {
    return {
      reason: "time-limit",
      source: "worker-startup",
      limit: startupLimit,
      usageState: "unknown",
    };
  }
  if ((!validReason || validReason === "process-error") && result.exitCode === 124) {
    const effective = positiveFinite(result.execution?.limits?.maxDurationMs);
    const requested = callerLimit(input, index, "maxDurationMs");
    return {
      reason: "time-limit",
      source: requested !== undefined && requested === effective ? "caller" : effective !== undefined ? "operator" : "worker",
      ...(effective !== undefined ? { limit: effective } : {}),
      usageState: result.finalOutput ? "partial" : "unknown",
    };
  }
  if (!validReason || validReason === "completed") {
    if ((result.exitCode ?? 1) === 0) return undefined;
    return {
      reason: "process-error",
      source: "worker",
      usageState: result.finalOutput ? "partial" : "unknown",
    };
  }
  const usageState = result.termination?.usageState === "complete" || result.termination?.usageState === "partial"
    ? result.termination.usageState
    : "unknown";
  const limit = positiveFinite(result.termination?.limit);
  const observed = positiveFinite(result.termination?.observed);
  const key = LIMIT_KEY_BY_REASON[validReason];
  const effective = key ? positiveFinite(result.execution?.limits?.[key]) : undefined;
  const requested = key ? callerLimit(input, index, key) : undefined;
  let source: TerminationEvidence["source"];
  if (validReason === "user-abort") source = "parent-cancellation";
  else if (validReason === "output-limit") {
    const applied = result.execution?.outputLimit?.enforcement === "applied";
    const providerCeiling = positiveFinite(result.execution?.outputLimit?.effective);
    if (
      requested !== undefined &&
      applied &&
      requested === providerCeiling &&
      limit === providerCeiling
    ) source = "caller";
    else if (
      requested === undefined &&
      effective !== undefined &&
      applied &&
      effective === providerCeiling &&
      limit === providerCeiling
    ) source = "wrapper";
    else source = "provider";
  }
  else if (requested !== undefined && requested === effective) source = "caller";
  else if (
    validReason === "request-limit" &&
    result.execution?.profile?.mode === "one-shot" &&
    effective === 1
  ) source = "execution-profile";
  else if (effective !== undefined) source = "operator";
  else if (providerFailureClass(result.error)) source = "provider";
  else source = "worker";

  return {
    reason: validReason,
    source,
    ...(limit !== undefined ? { limit } : {}),
    ...(observed !== undefined ? { observed } : {}),
    usageState,
  };
}

function resultExecutionOutcome(result: SubagentResult): "succeeded" | "failed" | "unavailable" {
  if ((result.exitCode ?? 1) === 0) return "succeeded";
  const reason = result.termination?.reason;
  return result.exitCode === 124 || reason === "time-limit" || reason === "idle-limit" || reason === "user-abort" || startupTimeoutMs(result.error)
    ? "unavailable"
    : "failed";
}

function trustedRouteReceipt(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
): RouteReceipt | undefined {
  const receipt = result.routeReceipt;
  const intentTask = input.tasks?.[index]?.route?.task ?? input.route?.task;
  if (
    receipt?.schemaVersion !== 1
    || receipt.authority !== "agnt-route"
    || receipt.routingTask !== intentTask
    || !ROUTING_TASK.test(receipt.routingTask)
    || !existsSync(join(agentDir, "tasks", `${receipt.routingTask}.md`))
    || !receipt.target
    || receipt.target !== `${receipt.provider}/${receipt.model}`
    || !["agentic", "one-shot"].includes(receipt.mode)
    || !THINKING_LEVELS.has(receipt.thinking)
  ) return undefined;
  return receipt;
}

function routingTask(input: SubagentInput, result: SubagentResult, index: number): string {
  const receipt = trustedRouteReceipt(input, result, index);
  if (receipt) return receipt.routingTask;
  const value = input.tasks?.[index]?.routingTask ?? input.routingTask;
  return typeof value === "string" &&
    ROUTING_TASK.test(value) &&
    existsSync(join(agentDir, "tasks", `${value}.md`))
    ? value
    : "peer";
}

function outputContract(
  input: SubagentInput,
  index: number,
  outputContracts: ReadonlySet<SubagentOutputContract>,
): NormalizedOutputContract {
  const value = input.tasks?.[index]?.outputContract ?? input.outputContract;
  return value && outputContracts.has(value) ? value : "unknown";
}

async function loadOutputContracts(): Promise<readonly SubagentOutputContract[]> {
  const require = createRequire(join(agentDir, "npm", "package.json"));
  const entry = require.resolve("@pi-archimedes/subagent/types");
  const module = await import(pathToFileURL(entry).href) as ArchimedesTypesModule;
  return module.SUBAGENT_OUTPUT_CONTRACTS;
}

function terminationMetadata(
  result: SubagentResult,
  evidence: TerminationEvidence | undefined,
): Record<string, unknown> {
  if (!evidence) return {};
  return {
    terminationReason: evidence.reason,
    terminationSource: evidence.source,
    terminationLimit: evidence.limit ?? null,
    terminationObserved: evidence.observed ?? null,
    terminationUsageState: evidence.usageState,
    effectiveMaxDurationMs: positiveFinite(result.execution?.limits?.maxDurationMs) ?? null,
    effectiveMaxIdleMs: positiveFinite(result.execution?.limits?.maxIdleMs) ?? null,
  };
}

function evaluationContext(
  task: string | undefined,
  result: SubagentResult,
  contract: NormalizedOutputContract,
  termination: TerminationEvidence | undefined,
): Record<string, unknown> {
  return {
    task: task ?? null,
    outputContract: contract,
    executionOutcome: resultExecutionOutcome(result),
    artifactStatus: result.artifact?.status ?? "failed",
    artifactContentStatus: result.artifact?.status === "persisted" && Boolean(result.finalOutput ?? result.error)
      ? "available"
      : "unavailable",
    artifactReferenceCount: result.artifact?.refs.length ?? 0,
    artifactFailureClass: result.artifact?.failureClass ?? null,
    ...terminationMetadata(result, termination),
  };
}

function terminationDescription(evidence: TerminationEvidence): string {
  return [
    evidence.reason,
    `source=${evidence.source}`,
    ...(evidence.limit !== undefined ? [`limit=${evidence.limit}`] : []),
    ...(evidence.observed !== undefined ? [`observed=${evidence.observed}`] : []),
    `output=${evidence.usageState}`,
  ].join("; ");
}

function evaluationOutput(result: SubagentResult, termination: TerminationEvidence | undefined): string {
  const value = result.finalOutput ?? result.error;
  if (!termination) {
    if (!value) return "[delegated output unavailable]";
    if (value.length <= EVALUATION_OUTPUT_MAX_CHARS) return value;
    return `${value.slice(0, EVALUATION_OUTPUT_MAX_CHARS)}\n[delegated output truncated at ${EVALUATION_OUTPUT_MAX_CHARS} characters]`;
  }

  const suffix = `\n\n[delegated termination: ${terminationDescription(termination)}]`;
  if (!value) return suffix.trim();
  if (value.length + suffix.length <= EVALUATION_OUTPUT_MAX_CHARS) return value + suffix;
  const notice = "\n[delegated output truncated]";
  const available = Math.max(0, EVALUATION_OUTPUT_MAX_CHARS - notice.length - suffix.length);
  return value.slice(0, available) + notice + suffix;
}

function artifactReferenceMessage(refs: string[]): { type: "text"; text: string } | undefined {
  if (refs.length === 0) return undefined;
  let text = "Delegated artifacts:";
  for (const [index, ref] of refs.entries()) {
    const line = `\n- ${ref}`;
    const omitted = refs.length - index;
    const notice = `\n[${omitted} artifact refs omitted; complete refs remain in details.results]`;
    if (text.length + line.length + notice.length > ARTIFACT_MESSAGE_MAX_CHARS) {
      text += notice;
      break;
    }
    text += line;
  }
  return { type: "text", text };
}

function terminationEvidenceMessage(
  input: SubagentInput,
  details: SubagentDetails,
): { type: "text"; text: string } | undefined {
  const rows = details.results.flatMap((result, index) => {
    const evidence = terminationEvidence(input, result, index);
    return evidence ? [`- Child ${index + 1}: ${terminationDescription(evidence)}`] : [];
  });
  if (!rows.length) return undefined;

  let text = "Delegated termination evidence:";
  for (const [index, row] of rows.entries()) {
    const line = `\n${row}`;
    const omitted = rows.length - index;
    const notice = `\n[${omitted} termination records omitted; complete evidence remains in details.results]`;
    if (text.length + line.length + notice.length > TERMINATION_MESSAGE_MAX_CHARS) {
      text += notice;
      break;
    }
    text += line;
  }
  return { type: "text", text };
}

function parallelInlineOutputMessages(
  input: SubagentInput,
  details: SubagentDetails,
  outputContracts: ReadonlySet<SubagentOutputContract>,
): Array<{ type: "text"; text: string }> {
  if (details.mode !== "parallel") return [];
  const outputs = details.results.flatMap((result, index) => {
    const value = typeof result.finalOutput === "string"
      ? result.finalOutput
      : typeof result.error === "string" ? result.error : undefined;
    const contract = outputContract(input, index, outputContracts);
    return (contract === "inline" || contract === "unknown") && value
      ? [{ index, value }]
      : [];
  });
  const messageMaxChars = Math.floor(INLINE_OUTPUT_MAX_CHARS / Math.max(1, outputs.length));
  const suffix = "\n[delegated output truncated]";
  const lastIndex = outputs.at(-1)?.index;
  if (lastIndex !== undefined && messageMaxChars <= `Child ${lastIndex + 1} output:\n`.length) {
    const { index, value } = outputs[0]!;
    const header = `Child ${index + 1} output:\n`;
    const omitted = outputs.length - 1;
    let notice = `\n[${omitted} later child outputs omitted; complete results remain in delegated artifacts]`;
    let outputChars = INLINE_OUTPUT_MAX_CHARS - header.length - notice.length;
    if (value.length > outputChars) {
      notice = `\n[delegated output truncated; ${omitted} later child outputs omitted; complete results remain in delegated artifacts]`;
      outputChars = INLINE_OUTPUT_MAX_CHARS - header.length - notice.length;
    }
    return [{ type: "text", text: `${header}${value.slice(0, Math.max(0, outputChars))}${notice}` }];
  }
  return outputs.flatMap(({ index, value }) => {
    const header = `Child ${index + 1} output:\n`;
    const available = messageMaxChars - header.length;
    if (available <= 0) return [];
    if (value.length <= available) return [{ type: "text" as const, text: `${header}${value}` }];
    const outputChars = Math.max(0, available - suffix.length);
    return [{
      type: "text" as const,
      text: `${header}${value.slice(0, outputChars)}${outputChars ? suffix : ""}`,
    }];
  });
}

function langfuseSessionId(ctx?: ExtensionContext): string | undefined {
  try {
    const sessionId = ctx?.sessionManager?.getSessionId?.();
    if (typeof sessionId === "string" && sessionId) return sessionId;

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

function effectiveMode(input: SubagentInput, result: SubagentResult, index: number): EffectiveMode {
  const mode = trustedRouteReceipt(input, result, index)?.mode
    ?? result.execution?.profile?.mode
    ?? input.tasks?.[index]?.mode
    ?? input.mode;
  return mode === "agentic" || mode === "one-shot" ? mode : "unknown";
}

function effectiveThinking(input: SubagentInput, result: SubagentResult, index: number): SubagentThinkingLevel | "default" {
  const thinking = trustedRouteReceipt(input, result, index)?.thinking
    ?? result.execution?.profile?.thinking
    ?? input.tasks?.[index]?.thinking
    ?? input.thinking;
  return THINKING_LEVELS.has(thinking as SubagentThinkingLevel) ? thinking as SubagentThinkingLevel : "default";
}

function childTraceAvailability(result: SubagentResult, mode: EffectiveMode): ChildTraceAvailability {
  if (mode === "one-shot") return "expected-unavailable";
  return mode === "agentic" && childSessionId(result) ? "expected-available" : "unknown";
}

export function providerFailureClass(message?: string): ProviderFailureClass | undefined {
  const text = String(message ?? "").slice(0, 12_000).toLowerCase();
  if (/\b(?:insufficient[_ -]?quota|quota (?:has been )?exceeded|monthly limit|key limit exceeded|usage limit exceeded)\b/.test(text)) return "quota";
  if (/\b(?:http\s*)?402\b|\binsufficient (?:credits?|credit balance)\b|\bcredit balance\b|\bavailable credits? can only cover\b|\bcan afford (?:only )?\d+ tokens\b/.test(text)) return "credit";
  if (/\b(?:http\s*)?401\b|\bunauthorized\b|\bauthentication failed\b|\b(?:invalid|missing|expired|revoked) (?:api[ _-]?key|token|credentials?)\b|\bno (?:api[ _-]?key|auth credentials?|credentials?)(?: found)?\b/.test(text)) return "authentication";
  if (/\b(?:http(?: status)?|status code|returned(?: http)?)\s*[:=]?\s*(?:502|503|504)\b|\b(?:502 bad gateway|503 service unavailable|504 gateway timeout)\b/.test(text)) return "availability";
  return undefined;
}

export function providerError(message?: string): string {
  if (message && /OpenrouterException/i.test(message) && /Key limit exceeded \(monthly limit\)/i.test(message)) {
    return "upstream OpenRouter monthly limit exceeded";
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

async function runtimeDirectories(kinds: string[], cwd: string): Promise<Record<string, string>> {
  const result = await runAgntJson(["runtime-path", ...kinds], cwd, undefined, "agnt runtime-path");
  const paths = result.paths;
  if (!paths || typeof paths !== "object" || Array.isArray(paths)) {
    throw new Error("agnt runtime-path returned no paths");
  }
  return Object.fromEntries(kinds.map((kind) => {
    const path = (paths as Record<string, unknown>)[kind];
    if (typeof path !== "string" || !path) throw new Error(`agnt runtime-path returned no path for ${kind}`);
    return [kind, path];
  }));
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
  persist: typeof persistRuntimeDelegatedResult,
  outputContracts: ReadonlySet<SubagentOutputContract>,
  resolvedRoot?: string,
): Promise<SubagentDetails> {
  let root = resolvedRoot;
  try {
    root ??= await runtimeDirectory("delegated-results", ctx.cwd);
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
          executionOutcome: resultExecutionOutcome(result),
          outputContract: outputContract(input, childIndex, outputContracts),
          exitCode: result.exitCode ?? 1,
          model: trustedRouteReceipt(input, result, childIndex)?.target ?? result.model ?? null,
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
  thinkingLevel: SubagentThinkingLevel | "default" | null;
  modelDimensionsStatus: "available" | "unavailable" | "unavailable-named-agent";
};

function modelDimensions(
  input: SubagentInput,
  result: SubagentResult,
  index: number,
  ctx: ExtensionContext,
): ModelDimensions {
  const receipt = trustedRouteReceipt(input, result, index);
  if (receipt) {
    return {
      provider: receipt.provider,
      model: receipt.model,
      target: receipt.target,
      thinkingLevel: receipt.thinking,
      modelDimensionsStatus: "available",
    };
  }
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
    thinkingLevel: target ? effectiveThinking(input, result, index) : null,
    modelDimensionsStatus: target ? "available" : "unavailable",
  };
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
  outputContracts: ReadonlySet<SubagentOutputContract>,
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
  const termination = terminationEvidence(input, result, index);
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
    executionOutcome: resultExecutionOutcome(result),
    failureClass: exitCode === 0
      ? null
      : termination?.reason === "time-limit" || termination?.reason === "idle-limit"
        ? "timeout"
        : failureClass ? "provider" : "process",
    providerFailureClass: exitCode === 0 ? null : failureClass ?? null,
    ...terminationMetadata(result, termination),
    artifactRefs: result.artifact?.refs ?? [],
    artifactStatus: result.artifact?.status ?? "failed",
    artifactFailureClass: result.artifact?.failureClass ?? null,
    outputContract: outputContract(input, index, outputContracts),
    workerElapsedMs,
    task: routingTask(input, result, index),
    riskCategory: null,
    thinkingLevel: dimensions.thinkingLevel,
    invocationMode: effectiveMode(input, result, index),
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
  outputContracts: ReadonlySet<SubagentOutputContract>,
  resolvedMetricsDir?: string,
): Promise<void> {
  const details = event.details as SubagentDetails | undefined;
  if (!details?.results?.length) return;

  const input = event.input as SubagentInput;
  const endedMs = Date.now();
  const records = details.results
    .map((result, index) => metricRecord(
      input,
      result,
      index,
      invocation.invocationIds[index],
      event.toolCallId,
      invocation.startedMs,
      endedMs,
      ctx,
      providerFailureClasses[index],
      outputContracts,
    ))
    .filter((record): record is Record<string, unknown> => record !== undefined);
  if (records.length === 0) return;

  const metricsDir = resolvedMetricsDir ?? await runtimeDirectory("metrics/invocations", ctx.cwd);
  await mkdir(metricsDir, { recursive: true });
  await Promise.all(records.map((record) => {
    const target = String(record.target).replace(/[^a-zA-Z0-9._-]+/g, "__");
    const name = `${String(record.endedAt).replace(/\D/g, "").slice(0, 17)}-${target}-${record.recordId}.metrics.json`;
    return writeFile(join(metricsDir, name), `${JSON.stringify(record, null, 2)}\n`, "utf8");
  }));
}

export default function subagentErrorWorkaround(pi: ExtensionAPI, dependencies: Dependencies = {}): void {
  const starts = new Map<string, InvocationStart>();
  let outputContractsPromise: Promise<ReadonlySet<SubagentOutputContract>> | undefined;
  const getOutputContracts = () => outputContractsPromise ??= Promise
    .resolve(dependencies.outputContracts ?? loadOutputContracts())
    .then((contracts) => new Set(contracts));
  const providerCircuit = dependencies.providerCircuit ?? updateProviderCircuit;
  const activeProviderCircuits = dependencies.activeProviderCircuits ?? loadActiveProviderCircuits;
  const resolveRuntimeDirectories = dependencies.runtimeDirectories ?? runtimeDirectories;
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
  if (!observe) {
    pi.events?.emit(PROJECTION_OBSERVE_REQUEST, (provided: unknown) => {
      if (typeof provided === "function") observe = provided as Observe;
    });
  }
  const getObserve = () => observe
    ? Promise.resolve(observe)
    : Promise.reject(new Error("pi-langfuse projection observer is unavailable"));

  pi.on("session_start", async (_event, ctx) => {
    if (process.env.PI_SUBAGENT_SOCKET) return;
    try {
      for (const provider of await activeProviderCircuits(ctx.cwd)) openProviders.add(provider);
    } catch (error) {
      console.error("[provider-circuit] could not read provider state:", error);
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
    if (event.toolName !== "subagent") return;

    let details = event.details as SubagentDetails | undefined;
    const invocation = starts.get(event.toolCallId) ?? { startedMs: Date.now(), invocationIds: [] };
    starts.delete(event.toolCallId);
    if (!details || !Array.isArray(details.results)) return;
    const input = event.input as SubagentInput;
    const routed = input.route !== undefined
      || (Array.isArray(input.tasks) && input.tasks.some((task) => task.route !== undefined));
    if (details.results.length === 0 && (details.routeFailure === true || routed)) return;

    const outputContracts = await getOutputContracts();
    const synthesized = details.results.length === 0;
    if (synthesized) {
      const tasks = Array.isArray(input.tasks) ? input.tasks : [];
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
    const needsMetrics = details.results.some((result, index) =>
      !(input.tasks?.[index]?.agent ?? input.agent) && modelDimensions(input, result, index, ctx).target !== null
    );
    let runtimePaths: Record<string, string> | undefined;
    if (needsMetrics) {
      try {
        runtimePaths = await resolveRuntimeDirectories(["delegated-results", "metrics/invocations"], ctx.cwd);
      } catch {
        // Preserve independent artifact and metric fallback behavior.
      }
    }
    details = await persistSubagentArtifacts(
      input,
      details,
      invocation,
      ctx,
      dependencies.persistDelegatedResult ?? persistRuntimeDelegatedResult,
      outputContracts,
      runtimePaths?.["delegated-results"],
    );
    const providerFailureClasses = details.results.map((result) => providerFailureClass(result.error));
    await Promise.all(details.results.map(async (result, index) => {
      if (input.tasks?.[index]?.agent ?? input.agent) return;
      const target = modelDimensions(input, result, index, ctx).target;
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
      await recordSubagentMetrics(
        { ...event, details },
        ctx,
        invocation,
        providerFailureClasses,
        outputContracts,
        runtimePaths?.["metrics/invocations"],
      );
    } catch (error) {
      console.error("[subagent-metrics] could not record invocation:", error);
    }

    await Promise.all(details.results.map(async (result, index) => {
      const task = input.tasks?.[index]?.task ?? input.task ?? result.task;
      const dimensions = modelDimensions(input, result, index, ctx);
      const contract = outputContract(input, index, outputContracts);
      const mode = effectiveMode(input, result, index);
      const termination = terminationEvidence(input, result, index);
      try {
        await (await getObserve())("subagent-result", {
          input: evaluationContext(task, result, contract, termination),
          output: evaluationOutput(result, termination),
          metadata: {
            invocationId: invocation.invocationIds[index],
            index,
            ...dimensions,
            executionOutcome: resultExecutionOutcome(result),
            routingTask: routingTask(input, result, index),
            effectiveMode: mode,
            childTraceAvailability: childTraceAvailability(result, mode),
            outputContract: contract,
            ...artifactMetadata(result),
            ...terminationMetadata(result, termination),
            exitCode: result.exitCode ?? 1,
            ...(providerFailureClasses[index] ? { providerFailureClass: providerFailureClasses[index] } : {}),
          },
          level: result.exitCode === 0 ? "DEFAULT" : "ERROR",
        }, { asType: "agent", sessionId: langfuseSessionId(ctx) });
      } catch (error) {
        console.error("[langfuse-projection] could not record subagent result:", error);
      }
    }));

    const normalizeParallelOutputs = details.mode === "parallel" && (
      input.outputContract !== undefined
      || (Array.isArray(input.tasks) && input.tasks.some((task) => task.outputContract !== undefined))
    );
    const baseContent = normalizeParallelOutputs ? event.content.slice(0, 1) : event.content;
    const inlineOutputMessages = normalizeParallelOutputs
      ? parallelInlineOutputMessages(input, details, outputContracts)
      : [];
    const terminationMessage = terminationEvidenceMessage(input, details);
    const persistedRefs = details.results.flatMap((result) => result.artifact?.refs ?? []);
    const artifactReference = artifactReferenceMessage(persistedRefs);
    const artifactMessages = [
      ...(artifactReference ? [artifactReference] : []),
      ...details.results.flatMap((result, index) => result.artifact?.status === "failed"
        ? [{ type: "text" as const, text: `Delegated artifact unavailable for child ${index} (${result.artifact.failureClass}).` }]
        : []),
    ];
    const patch = {
      content: [
        ...baseContent,
        ...inlineOutputMessages,
        ...(terminationMessage ? [terminationMessage] : []),
        ...artifactMessages,
      ],
      details,
    };
    if (synthesized || details.results.some((result) => result.exitCode !== 0)) return { ...patch, isError: true };
    return patch;
  });
}
