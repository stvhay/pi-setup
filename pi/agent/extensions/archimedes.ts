import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { runAgntJson } from "./lib/run-agnt-json.ts";

type ArchimedesBusModule = typeof import("@pi-archimedes/core/bus");
type ArchimedesAgentsModule = typeof import("@pi-archimedes/subagent/agents");
type ArchimedesTypesModule = typeof import("@pi-archimedes/subagent/types");

type SelectionMode = "single" | "multi";
type Question = {
  id: string;
  question: string;
  description?: string;
  options: Array<{ label: string }>;
  selectionMode: SelectionMode;
  recommended?: number;
};
type Answer = {
  id: string;
  question: string;
  description?: string;
  options: string[];
  selectionMode: SelectionMode;
  selectedOptions: string[];
  customInput?: string;
};
type ToolDefinition = {
  name: string;
  label?: string;
  description?: string;
  parameters?: any;
  prepareArguments?: (args: unknown) => unknown;
  execute?: (...args: any[]) => Promise<any>;
  [key: string]: any;
};
type ArchimedesFactory = (pi: ExtensionAPI) => void | Promise<void>;
type AskEmitter = (questions: Question[]) => void;
type AgentModelResolver = ArchimedesAgentsModule["resolveAgentModel"];
type OutputContracts = ArchimedesTypesModule["SUBAGENT_OUTPUT_CONTRACTS"];
type BillingClass = "metered" | "subscription";
type RouteIntent = {
  task: string;
  risk?: "low" | "medium" | "high";
  budget?: "cheap" | "balanced" | "quality";
  contextTokens?: number;
  modality?: "text" | "image" | "audio" | "video";
  sourceAccess?: "auto" | "self-contained" | "repository";
  estimatedInputTokens?: number;
  estimatedOutputTokens?: number;
  maxMarginalUsd?: number;
  meteredJustification?: "quality-benefit" | "missing-capability";
  ignoreHistory?: boolean;
};
type RouteReceipt = {
  schemaVersion: 1;
  authority: "agnt-route";
  routingTask: string;
  target: string;
  provider: string;
  model: string;
  mode: "agentic" | "one-shot";
  thinking: "off" | "minimal" | "low" | "medium" | "high" | "xhigh";
  sourceAccess: "auto" | "self-contained" | "repository";
  contextPolicy: string;
  billingClass: "metered" | "subscription";
  estimatedCostUsd?: number;
  meteredJustification?: "quality-benefit" | "missing-capability";
  limits: Record<string, number>;
};

const METERED_ONE_SHOT_CAP_ENV = "PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS";
const DEFAULT_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS = 16_384;

function outputContractParameter(outputContracts: OutputContracts): Record<string, unknown> {
  return {
    type: "string",
    enum: outputContracts,
    description: "Expected result shape used for parent artifact persistence and quality evaluation.",
  };
}
const routingTaskParameter = {
  type: "string",
  pattern: "^[a-z][a-z0-9-]{0,63}$",
  description: "Safe route task category used only for telemetry; stripped before child execution.",
};
const sourceAccessParameter = {
  type: "string",
  enum: ["self-contained", "repository"],
  description: "Evidence access required by the child; repository access requires agentic mode.",
};
const meteredJustificationParameter = {
  type: "string",
  enum: ["quality-benefit", "missing-capability"],
  description: "Why bounded metered agentic repository access is justified.",
};
const estimatedCostParameter = {
  type: "number",
  exclusiveMinimum: 0,
  description: "Estimated marginal USD for bounded metered agentic repository access.",
};
const maxMarginalParameter = {
  type: "number",
  exclusiveMinimum: 0,
  description: "Aggregate marginal USD budget for parallel metered repository work.",
};
const routeParameter = {
  type: "object",
  additionalProperties: false,
  required: ["task"],
  properties: {
    task: {
      type: "string",
      pattern: "^[a-z][a-z0-9-]{0,63}$",
      description: "agnt routing task policy to select before launch.",
    },
    risk: { type: "string", enum: ["low", "medium", "high"] },
    budget: { type: "string", enum: ["cheap", "balanced", "quality"] },
    contextTokens: { type: "integer", minimum: 0 },
    modality: { type: "string", enum: ["text", "image", "audio", "video"] },
    sourceAccess: { type: "string", enum: ["auto", "self-contained", "repository"] },
    estimatedInputTokens: { type: "integer", minimum: 0 },
    estimatedOutputTokens: { type: "integer", minimum: 0 },
    maxMarginalUsd: estimatedCostParameter,
    meteredJustification: meteredJustificationParameter,
    ignoreHistory: { type: "boolean" },
  },
};

const askParameters = {
  type: "object",
  additionalProperties: false,
  properties: {
    questions: {
      type: "array",
      minItems: 1,
      items: {
        type: "object",
        additionalProperties: false,
        required: ["id", "question", "options", "selectionMode"],
        properties: {
          id: { type: "string" },
          question: { type: "string" },
          description: { type: "string" },
          options: {
            type: "array",
            minItems: 1,
            items: {
              type: "object",
              additionalProperties: false,
              required: ["label"],
              properties: { label: { type: "string" } },
            },
          },
          selectionMode: {
            type: "string",
            enum: ["single", "multi"],
            description: "Required selection cardinality: single allows one answer; multi allows multiple answers.",
          },
          recommended: { type: "number" },
        },
      },
    },
  },
  required: ["questions"],
};

function clean(value: unknown, limit = 500): string {
  return String(value ?? "")
    .replace(/[\r\n\t]+/g, " ")
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "")
    .replace(/\s{2,}/g, " ")
    .trim()
    .slice(0, limit);
}

function prepareAskArguments(args: unknown): unknown {
  if (!args || typeof args !== "object" || !Array.isArray((args as any).questions)) return args;
  return {
    ...(args as Record<string, unknown>),
    questions: (args as any).questions.map((value: unknown) => {
      if (!value || typeof value !== "object" || Array.isArray(value)) return value;
      const { multi, ...question } = value as Record<string, unknown>;
      if (question.selectionMode === undefined && typeof multi === "boolean") {
        question.selectionMode = multi ? "multi" : "single";
      }
      return question;
    }),
  };
}

function questionTitle(question: Question): string {
  const description = clean(question.description, 1000);
  return description ? `${clean(question.question)} — ${description}` : clean(question.question);
}

async function askCustomInput(ui: any): Promise<string | undefined> {
  while (true) {
    const raw = await ui.input("Other answer", "Type a custom response");
    if (raw === undefined) return undefined;
    const value = clean(raw);
    if (value) return value;
    ui.notify("Custom response cannot be empty.", "warning");
  }
}

async function answerQuestion(question: Question, ui: any): Promise<Answer> {
  const labels = question.options.map(({ label }) => clean(label));
  const selectedOptions: string[] = [];
  let customInput: string | undefined;

  if (question.selectionMode === "multi") {
    for (const label of labels) {
      if (await ui.confirm(questionTitle(question), `Select “${label}”?`)) selectedOptions.push(label);
    }
    if (await ui.confirm(questionTitle(question), "Add a custom response (“Other…”)?")) {
      customInput = await askCustomInput(ui);
    }
  } else {
    const choices = labels.map(
      (label, index) => `${index + 1}. ${label}${index === question.recommended ? " (Recommended)" : ""}`,
    );
    const selected = await ui.select(questionTitle(question), [...choices, "Other…"]);
    const index = choices.indexOf(selected);
    if (index >= 0) selectedOptions.push(labels[index]);
    if (selected === "Other…") customInput = await askCustomInput(ui);
  }

  return {
    id: clean(question.id) || "unknown",
    question: clean(question.question),
    description: clean(question.description, 1000) || undefined,
    options: labels,
    selectionMode: question.selectionMode,
    selectedOptions,
    customInput,
  };
}

function formatAnswer(answer: Answer): string {
  const selected = answer.selectionMode === "multi"
    ? `[${answer.selectedOptions.join(", ")}]`
    : answer.selectedOptions[0];
  if (selected && answer.customInput) return `${answer.id}: ${selected} + Other: “${answer.customInput}”`;
  if (answer.customInput) return `${answer.id}: “${answer.customInput}”`;
  return `${answer.id}: ${selected || "(cancelled)"}`;
}

function normalizeLegacyResult(result: any, questions: Question[]): any {
  const details = result?.details;
  if (!details || !Array.isArray(details.results)) return result;
  const { multi: _multi, ...currentDetails } = details;
  return {
    ...result,
    details: {
      ...currentDetails,
      results: details.results.map((legacy: any, index: number) => {
        const { multi: _multi, ...answer } = legacy;
        const question = questions[index];
        return {
          ...answer,
          id: clean(question?.id) || clean(answer.id) || "unknown",
          question: clean(question?.question) || clean(answer.question),
          description: clean(question?.description, 1000) || clean(answer.description, 1000) || undefined,
          options: question
            ? question.options.map(({ label }) => clean(label))
            : Array.isArray(answer.options) ? answer.options.map((option: unknown) => clean(option)) : [],
          selectionMode: question?.selectionMode ?? "single",
          selectedOptions: Array.isArray(answer.selectedOptions)
            ? answer.selectedOptions.map((option: unknown) => clean(option))
            : [],
          customInput: clean(answer.customInput) || undefined,
        };
      }),
    },
  };
}

async function withQualityAskResults(
  result: any,
  questions: Question[],
  cwd: string | undefined,
  signal?: AbortSignal,
): Promise<any> {
  const normalized = normalizeLegacyResult(result, questions);
  const results = normalized?.details?.results;
  if (!Array.isArray(results)) return normalized;
  const qualityInput = results.map((answer: any, index: number) => {
    const options = (questions[index]?.options ?? [])
      .map(({ label }) => clean(label))
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);
    const selectedOptions = Array.isArray(answer?.selectedOptions)
      ? answer.selectedOptions.map((selected: unknown) => {
        const value = clean(selected);
        // ponytail: upstream "option - note" is ambiguous for overlapping labels; use longest until notes are structured.
        return options.find((option) => value === option || value.startsWith(`${option} - `)) ?? value;
      })
      : answer?.selectedOptions;
    return { ...answer, selectedOptions };
  });
  const quality = await runAgntJson(
    ["quality", "normalize-ask", "--json"],
    cwd || process.cwd(),
    signal,
    "ask result normalizer",
    JSON.stringify(qualityInput),
  );
  if (!Array.isArray(quality.results)) throw new Error("ask result normalizer returned invalid results");
  return {
    ...normalized,
    details: { ...normalized.details, qualityResults: quality.results },
  };
}

function subagentParameters(parameters: any, outputContracts: OutputContracts): any {
  const properties = parameters?.properties;
  const taskItems = properties?.tasks?.items;
  if (!properties || !taskItems?.properties) throw new Error("Archimedes subagent schema is unavailable");
  const outputContract = outputContractParameter(outputContracts);
  return {
    ...parameters,
    properties: {
      ...properties,
      outputContract,
      route: routeParameter,
      routingTask: routingTaskParameter,
      sourceAccess: sourceAccessParameter,
      meteredJustification: meteredJustificationParameter,
      estimatedCostUsd: estimatedCostParameter,
      maxMarginalUsd: maxMarginalParameter,
      tasks: {
        ...properties.tasks,
        items: {
          ...taskItems,
          properties: {
            ...taskItems.properties,
            outputContract,
            route: routeParameter,
            routingTask: routingTaskParameter,
            sourceAccess: sourceAccessParameter,
            meteredJustification: meteredJustificationParameter,
            estimatedCostUsd: estimatedCostParameter,
          },
        },
      },
    },
  };
}

function upstreamSubagentArguments(params: any): any {
  const {
    outputContract: _outputContract,
    route: _route,
    routingTask: _routingTask,
    sourceAccess: _sourceAccess,
    meteredJustification: _meteredJustification,
    estimatedCostUsd: _estimatedCostUsd,
    maxMarginalUsd: _maxMarginalUsd,
    ...upstream
  } = params;
  if (!Array.isArray(upstream.tasks)) return upstream;
  return {
    ...upstream,
    tasks: upstream.tasks.map((value: any) => {
      const {
        outputContract: _taskOutputContract,
        route: _taskRoute,
        routingTask: _taskRoutingTask,
        sourceAccess: _taskSourceAccess,
        meteredJustification: _taskMeteredJustification,
        estimatedCostUsd: _taskEstimatedCostUsd,
        ...task
      } = value;
      return task;
    }),
  };
}

const ROUTE_TASK = /^[a-z][a-z0-9-]{0,63}$/;
const ROUTE_THINKING = new Set(["off", "minimal", "low", "medium", "high", "xhigh"]);
const ROUTE_MODES = new Set(["agentic", "one-shot"]);
const ROUTE_ACCESS = new Set(["auto", "self-contained", "repository"]);
const ROUTE_BILLING = new Set(["metered", "subscription"]);
const ROUTE_LIMIT_KEYS = [
  "maxProviderRequests",
  "maxToolCalls",
  "maxTotalTokens",
  "maxOutputTokens",
  "maxCostUsd",
  "maxDurationMs",
  "maxIdleMs",
] as const;
const ROUTE_INTEGER_LIMITS = new Set([
  "maxProviderRequests",
  "maxToolCalls",
  "maxTotalTokens",
  "maxOutputTokens",
  "maxDurationMs",
  "maxIdleMs",
]);
const MAX_ROUTE_DURATION_MS = 2_147_483_647;
const ROUTE_MANUAL_FIELDS = [
  "agent",
  "model",
  "mode",
  "thinking",
  "sourceAccess",
  "routingTask",
  "meteredJustification",
  "estimatedCostUsd",
] as const;

function routeFailure(params: any, message: string): any {
  return {
    content: [{ type: "text", text: message }],
    details: {
      mode: Array.isArray(params?.tasks) ? "parallel" : "single",
      results: [],
      progress: undefined,
      routeFailure: true,
    },
    isError: true,
  };
}

function routeConflict(params: any): string | undefined {
  if (Array.isArray(params?.tasks)) {
    if (params.route !== undefined) return "Top-level route is only valid for single subagent calls.";
    for (const [index, task] of params.tasks.entries()) {
      if (task?.route === undefined) continue;
      const field = ROUTE_MANUAL_FIELDS.find((key) => task[key] !== undefined || params[key] !== undefined);
      if (field) return `Routed subagent task ${index + 1} cannot also set ${field}.`;
    }
    return undefined;
  }
  if (params?.route === undefined) return undefined;
  if (typeof params.task !== "string" || !params.task) return "Top-level route requires a subagent task.";
  const field = ROUTE_MANUAL_FIELDS.find((key) => params[key] !== undefined);
  return field ? `Routed subagent cannot also set ${field}.` : undefined;
}

function routeArguments(intent: RouteIntent): string[] {
  if (!intent || !ROUTE_TASK.test(intent.task)) throw new Error("invalid route intent");
  const args = ["route", "--task", intent.task];
  const values: Array<[unknown, string]> = [
    [intent.risk, "--risk"],
    [intent.budget, "--budget"],
    [intent.contextTokens, "--context-tokens"],
    [intent.modality, "--modality"],
    [intent.sourceAccess, "--access"],
    [intent.estimatedInputTokens, "--estimated-input-tokens"],
    [intent.estimatedOutputTokens, "--estimated-output-tokens"],
    [intent.maxMarginalUsd, "--max-marginal-usd"],
    [intent.meteredJustification, "--metered-justification"],
  ];
  for (const [value, flag] of values) if (value !== undefined) args.push(flag, String(value));
  if (intent.ignoreHistory) args.push("--ignore-history");
  return args;
}

function positiveRouteLimits(value: unknown): Record<string, number> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const limits = value as Record<string, unknown>;
  if (Object.keys(limits).some((key) => !ROUTE_LIMIT_KEYS.includes(key as typeof ROUTE_LIMIT_KEYS[number]))) {
    return undefined;
  }
  const normalized: Record<string, number> = {};
  for (const key of ROUTE_LIMIT_KEYS) {
    const limit = limits[key];
    if (limit === undefined) continue;
    if (
      typeof limit !== "number"
      || !Number.isFinite(limit)
      || limit <= 0
      || (ROUTE_INTEGER_LIMITS.has(key) && !Number.isInteger(limit))
      || (key === "maxOutputTokens" && !Number.isSafeInteger(limit))
      || ((key === "maxDurationMs" || key === "maxIdleMs") && limit > MAX_ROUTE_DURATION_MS)
    ) return undefined;
    normalized[key] = limit;
  }
  return normalized;
}

function expectedRouteMode(intent: RouteIntent): "agentic" | "one-shot" {
  if (intent.sourceAccess === "repository") return "agentic";
  if (intent.sourceAccess === "self-contained") return "one-shot";
  return intent.task === "review" ? "one-shot" : "agentic";
}

function routeReceipt(
  intent: RouteIntent,
  result: Record<string, unknown>,
  classes: ReadonlyMap<string, BillingClass>,
): RouteReceipt {
  const selection = result.selection;
  if (
    result.schemaVersion !== 1
    || result.task !== intent.task
    || result.routeStatus !== "selected"
    || !selection
    || typeof selection !== "object"
    || Array.isArray(selection)
  ) throw new Error("invalid selected route");
  const selected = selection as Record<string, unknown>;
  const target = selected.target;
  const separator = typeof target === "string" ? target.indexOf("/") : -1;
  const thinking = selected.thinkingLevel;
  const mode = selected.executionMode;
  const sourceAccess = selected.sourceAccess;
  const contextPolicy = selected.contextPolicy;
  const billingClass = selected.billingClass;
  const limits = positiveRouteLimits(selected.limits);
  const estimatedCost = selected.estimatedCostUsd;
  const justification = selected.meteredJustification;
  const catalogBilling = typeof target === "string" ? classes.get(normalizeModelRef(target)!) : undefined;
  if (
    result.risk !== (intent.risk ?? "medium")
    || result.budget !== (intent.budget ?? "balanced")
    || result.modality !== (intent.modality ?? "text")
    || result.contextTokens !== (intent.contextTokens ?? 0)
    || result.selected !== target
    || result.thinkingLevel !== thinking
    || result.contextPolicy !== contextPolicy
    || result.sourceAccess !== sourceAccess
    || result.executionMode !== mode
    || separator <= 0
    || separator === (target as string).length - 1
    || typeof thinking !== "string"
    || !ROUTE_THINKING.has(thinking)
    || typeof mode !== "string"
    || !ROUTE_MODES.has(mode)
    || typeof sourceAccess !== "string"
    || !ROUTE_ACCESS.has(sourceAccess)
    || sourceAccess !== (intent.sourceAccess ?? "auto")
    || typeof contextPolicy !== "string"
    || !contextPolicy
    || typeof billingClass !== "string"
    || !ROUTE_BILLING.has(billingClass)
    || billingClass !== catalogBilling
    || limits === undefined
    || (estimatedCost !== null && estimatedCost !== undefined && positiveFinite(estimatedCost) === undefined && estimatedCost !== 0)
    || (justification !== null && justification !== undefined && !["quality-benefit", "missing-capability"].includes(String(justification)))
    || mode !== expectedRouteMode(intent)
    || (intent.maxMarginalUsd !== undefined && typeof estimatedCost === "number" && estimatedCost > intent.maxMarginalUsd)
  ) throw new Error("invalid selected route");
  if (billingClass === "metered" && mode === "agentic" && sourceAccess === "auto") {
    throw new Error("metered agentic routes require explicit repository sourceAccess and bounded routing evidence");
  }
  return {
    schemaVersion: 1,
    authority: "agnt-route",
    routingTask: intent.task,
    target: target as string,
    provider: (target as string).slice(0, separator),
    model: (target as string).slice(separator + 1),
    mode: mode as RouteReceipt["mode"],
    thinking: thinking as RouteReceipt["thinking"],
    sourceAccess: sourceAccess as RouteReceipt["sourceAccess"],
    contextPolicy,
    billingClass: billingClass as RouteReceipt["billingClass"],
    ...(typeof estimatedCost === "number" ? { estimatedCostUsd: estimatedCost } : {}),
    ...(typeof justification === "string" ? { meteredJustification: justification as RouteReceipt["meteredJustification"] } : {}),
    limits,
  };
}

function effectiveRouteLimits(...values: unknown[]): Record<string, number> {
  const limits: Record<string, number> = {};
  for (const value of values) {
    if (value === undefined) continue;
    const normalized = positiveRouteLimits(value);
    if (normalized === undefined) throw new Error("subagent limits must contain only positive finite values");
    for (const [key, limit] of Object.entries(normalized)) {
      limits[key] = Math.min(limits[key] ?? limit, limit);
    }
  }
  return limits;
}

function withReceiptSelection(task: any, receipt: RouteReceipt, topLimits?: unknown): any {
  const limits = effectiveRouteLimits(receipt.limits, topLimits, task.limits);
  if (receipt.mode === "agentic" && limits.maxOutputTokens !== undefined) {
    throw new Error("maxOutputTokens is supported only for one-shot routed children");
  }
  if (receipt.mode === "one-shot" && (limits.maxTotalTokens !== undefined || limits.maxCostUsd !== undefined)) {
    throw new Error("maxTotalTokens and maxCostUsd cannot bound one-shot routed children; use maxOutputTokens");
  }
  if (receipt.mode === "one-shot") limits.maxProviderRequests = Math.min(limits.maxProviderRequests ?? 1, 1);
  return {
    ...task,
    model: receipt.target,
    mode: receipt.mode,
    thinking: receipt.thinking,
    ...(receipt.sourceAccess === "auto" ? {} : { sourceAccess: receipt.sourceAccess }),
    ...(receipt.estimatedCostUsd !== undefined ? { estimatedCostUsd: receipt.estimatedCostUsd } : {}),
    ...(receipt.meteredJustification ? { meteredJustification: receipt.meteredJustification } : {}),
    ...(Object.keys(limits).length ? { limits } : {}),
  };
}

async function resolveRoutedArguments(
  params: any,
  cwd: string,
  classes: ReadonlyMap<string, BillingClass>,
  signal?: AbortSignal,
): Promise<{ params: any; receipts: Array<RouteReceipt | undefined> }> {
  if (Array.isArray(params.tasks)) {
    const receipts = await Promise.all(params.tasks.map(async (task: any): Promise<RouteReceipt | undefined> => {
      if (!task.route) return undefined;
      const result = await runAgntJson(
        routeArguments(task.route),
        task.cwd ?? params.cwd ?? cwd,
        signal,
        "agnt route",
      );
      return routeReceipt(task.route, result, classes);
    }));
    const tasks = params.tasks.map((task: any, index: number) =>
      receipts[index] ? withReceiptSelection(task, receipts[index]!, params.limits) : task
    );
    const routedEstimate = receipts.reduce((sum, receipt) =>
      sum + (receipt?.sourceAccess === "repository" && receipt.billingClass === "metered"
        ? receipt.estimatedCostUsd ?? 0
        : 0), 0);
    return {
      params: {
        ...params,
        tasks,
        ...(params.maxMarginalUsd === undefined && routedEstimate > 0 ? { maxMarginalUsd: routedEstimate } : {}),
      },
      receipts,
    };
  }
  if (!params.route) return { params, receipts: [undefined] };
  const result = await runAgntJson(routeArguments(params.route), params.cwd ?? cwd, signal, "agnt route");
  const receipt = routeReceipt(params.route, result, classes);
  return { params: withReceiptSelection(params, receipt), receipts: [receipt] };
}

function finalizedReceipts(
  params: any,
  receipts: Array<RouteReceipt | undefined>,
): Array<RouteReceipt | undefined> {
  return receipts.map((receipt, index) => {
    if (!receipt) return undefined;
    const limits = Array.isArray(params.tasks) ? params.tasks[index]?.limits : params.limits;
    return { ...receipt, limits: positiveRouteLimits(limits ?? {}) ?? receipt.limits };
  });
}

function withRouteReceipts(result: any, receipts: Array<RouteReceipt | undefined>): any {
  if (!receipts.some(Boolean) || !Array.isArray(result?.details?.results)) return result;
  return {
    ...result,
    details: {
      ...result.details,
      results: result.details.results.map((child: any, index: number) =>
        receipts[index] ? { ...child, routeReceipt: receipts[index] } : child
      ),
    },
  };
}

function meteredOneShotMaxOutputTokens(): number | undefined {
  const raw = process.env[METERED_ONE_SHOT_CAP_ENV]?.trim();
  if (!raw) return DEFAULT_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS;
  if (raw === "0" || raw.toLowerCase() === "off") return undefined;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new Error(`${METERED_ONE_SHOT_CAP_ENV} must be a positive integer, 0, or off`);
  }
  return value;
}

function normalizeModelRef(model: string | undefined): string | undefined {
  const ref = model?.trim().replace(/:(?:off|minimal|low|medium|high|xhigh|max)$/i, "").toLowerCase();
  return ref || undefined;
}

function loadBillingClasses(): Map<string, BillingClass> {
  const path = join(getAgentDir(), "catalog.json");
  let parsed: any;
  try {
    parsed = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new Error(`Cannot load model billing catalog ${path}: ${error instanceof Error ? error.message : error}`);
  }
  if (!parsed?.families || typeof parsed.families !== "object" || Array.isArray(parsed.families)) {
    throw new Error(`Invalid model billing catalog ${path}: families must be an object`);
  }

  const classes = new Map<string, BillingClass>();
  for (const family of Object.values(parsed.families) as any[]) {
    if (!Array.isArray(family?.venues)) continue;
    for (const venue of family.venues) {
      const target = normalizeModelRef(venue?.target);
      const billingClass = venue?.billingClass;
      if (!target || (billingClass !== "metered" && billingClass !== "subscription")) {
        throw new Error(`Invalid model billing catalog ${path}: every venue needs target and billingClass`);
      }
      const previous = classes.get(target);
      if (previous && previous !== billingClass) {
        throw new Error(`Invalid model billing catalog ${path}: conflicting billingClass for ${target}`);
      }
      classes.set(target, billingClass);
    }
  }
  return classes;
}

function modelBillingClass(
  model: string | undefined,
  ctx: any,
  classes: ReadonlyMap<string, BillingClass>,
): BillingClass | undefined {
  const ref = normalizeModelRef(model);
  if (!ref) return undefined;
  const direct = classes.get(ref);
  if (direct) return direct;
  const matches = (ctx?.modelRegistry?.getAll?.() ?? []).filter((candidate: any) =>
    normalizeModelRef(candidate?.id) === ref ||
    normalizeModelRef(`${candidate?.provider}/${candidate?.id}`) === ref
  );
  if (matches.length !== 1) return undefined;
  return classes.get(normalizeModelRef(`${matches[0].provider}/${matches[0].id}`)!);
}

function positiveOutputLimit(value: unknown): number | undefined {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value : undefined;
}

function withMeteredOneShotCaps(
  params: any,
  ctx: any,
  classes: ReadonlyMap<string, BillingClass>,
  resolveAgentModel: AgentModelResolver,
  defaultCap: number | undefined,
): any {
  if (!defaultCap || !params || typeof params !== "object") return params;
  const inheritedModel = ctx?.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined;
  const cwd = ctx?.cwd ?? process.cwd();
  const apply = (task: any, topLevel: any): any => {
    const mode = task.mode ?? topLevel.mode ?? "agentic";
    const agentModel = typeof task.agent === "string" ? resolveAgentModel(task.agent, cwd) : undefined;
    const model = agentModel ?? task.model ?? inheritedModel;
    if (mode !== "one-shot" || modelBillingClass(model, ctx, classes) !== "metered") return task;
    const caps = [
      defaultCap,
      positiveOutputLimit(topLevel.limits?.maxOutputTokens),
      positiveOutputLimit(task.limits?.maxOutputTokens),
    ].filter((value): value is number => value !== undefined);
    return {
      ...task,
      limits: { ...(task.limits ?? {}), maxOutputTokens: Math.min(...caps) },
    };
  };

  if (Array.isArray(params.tasks)) {
    return { ...params, tasks: params.tasks.map((task: any) => apply(task, params)) };
  }
  return apply(params, {});
}

function positiveFinite(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : undefined;
}

function delegationPolicyError(
  params: any,
  ctx: any,
  classes: ReadonlyMap<string, BillingClass>,
  resolveAgentModel: AgentModelResolver,
): string | undefined {
  const inheritedModel = ctx?.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined;
  const cwd = ctx?.cwd ?? process.cwd();
  const tasks = Array.isArray(params.tasks) ? params.tasks : [params];
  let aggregateEstimatedCost = 0;
  for (const task of tasks) {
    const mode = task.mode ?? params.mode ?? "agentic";
    const sourceAccess = task.sourceAccess ?? params.sourceAccess;
    if (sourceAccess !== "repository") continue;
    if (mode === "one-shot") return "Repository access requires agentic subagent mode.";
    const agentModel = typeof task.agent === "string" ? resolveAgentModel(task.agent, cwd) : undefined;
    const model = agentModel ?? task.model ?? params.model ?? inheritedModel;
    if (modelBillingClass(model, ctx, classes) !== "metered") continue;
    const justification = task.meteredJustification ?? params.meteredJustification;
    const estimatedCost = positiveFinite(task.estimatedCostUsd ?? params.estimatedCostUsd);
    const limits = { ...(params.limits ?? {}), ...(task.limits ?? {}) };
    const maxCost = positiveFinite(limits.maxCostUsd);
    if (
      !["quality-benefit", "missing-capability"].includes(justification)
      || estimatedCost === undefined
      || positiveOutputLimit(limits.maxProviderRequests) === undefined
      || positiveOutputLimit(limits.maxTotalTokens) === undefined
      || maxCost === undefined
      || positiveOutputLimit(limits.maxDurationMs) === undefined
    ) {
      return "Metered repository access requires justification, estimated cost, and bounded limits.";
    }
    if (estimatedCost > maxCost) return "Metered repository estimated cost exceeds maxCostUsd.";
    aggregateEstimatedCost += estimatedCost;
  }
  if (Array.isArray(params.tasks) && aggregateEstimatedCost > 0) {
    const aggregateBudget = positiveFinite(params.maxMarginalUsd);
    if (aggregateBudget === undefined) return "Metered repository fanout requires aggregate maxMarginalUsd.";
    if (aggregateEstimatedCost > aggregateBudget) {
      return "Metered repository aggregate estimated cost exceeds maxMarginalUsd.";
    }
  }
  return undefined;
}

function registerContractAwareSubagent(
  pi: ExtensionAPI,
  upstreamSubagent: ToolDefinition | undefined,
  outputContracts: OutputContracts,
  classes: ReadonlyMap<string, BillingClass>,
  resolveAgentModel: AgentModelResolver,
  defaultCap: number | undefined,
): void {
  if (!upstreamSubagent?.execute || !upstreamSubagent.parameters) {
    throw new Error("Archimedes subagent tool is unavailable");
  }
  pi.registerTool({
    ...upstreamSubagent,
    parameters: subagentParameters(upstreamSubagent.parameters, outputContracts),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const conflict = routeConflict(params);
      if (conflict) return routeFailure(params, conflict);
      let routed;
      try {
        routed = await resolveRoutedArguments(params, ctx?.cwd ?? process.cwd(), classes, signal);
      } catch (error) {
        const message = error instanceof Error && error.message === "invalid selected route"
          ? "Subagent routing returned an invalid selected route."
          : `Subagent routing failed: ${clean(error instanceof Error ? error.message : error, 4000)}`;
        return routeFailure(params, message);
      }
      const policyError = delegationPolicyError(routed.params, ctx, classes, resolveAgentModel);
      if (policyError) {
        if (routed.receipts.some(Boolean)) return routeFailure(params, policyError);
        return {
          content: [{ type: "text", text: policyError }],
          details: {
            mode: Array.isArray(params.tasks) ? "parallel" : "single",
            results: [],
            progress: undefined,
          },
          isError: true,
        };
      }
      const bounded = withMeteredOneShotCaps(routed.params, ctx, classes, resolveAgentModel, defaultCap);
      const result = await upstreamSubagent.execute!(
        toolCallId,
        upstreamSubagentArguments(bounded),
        signal,
        onUpdate,
        ctx,
      );
      return withRouteReceipts(result, finalizedReceipts(bounded, routed.receipts));
    },
  } as any);
}

function registerPortableAsk(pi: ExtensionAPI, upstreamAsk?: ToolDefinition, emitAsk?: AskEmitter): void {
  pi.registerTool({
    name: "ask",
    label: "Ask",
    description: [
      "Ask the user one or more questions when their choice materially affects the outcome.",
      "Every question must set selectionMode to single or multi.",
    ].join(" "),
    parameters: askParameters as any,
    prepareArguments: prepareAskArguments,
    async execute(toolCallId, params: { questions: Question[] }, signal, onUpdate, ctx) {
      if (ctx.mode !== "rpc") {
        if (!upstreamAsk?.execute) throw new Error("Archimedes ask tool is unavailable");
        const legacy = {
          questions: params.questions.map(({ selectionMode, ...question }) => ({
            ...question,
            multi: selectionMode === "multi",
          })),
        };
        return withQualityAskResults(
          await upstreamAsk.execute(toolCallId, legacy, signal, onUpdate, ctx),
          params.questions,
          ctx.cwd,
          signal,
        );
      }
      if (!ctx.hasUI) {
        const results = params.questions.map((question) => ({
          id: clean(question.id) || "unknown",
          question: clean(question.question),
          description: clean(question.description, 1000) || undefined,
          options: question.options.map(({ label }) => clean(label)),
          selectionMode: question.selectionMode,
          selectedOptions: [],
        }));
        return withQualityAskResults({
          content: [{ type: "text", text: "User cancelled the question." }],
          details: { results },
        }, params.questions, ctx.cwd, signal);
      }

      emitAsk?.(params.questions);
      const results: Answer[] = [];
      for (const question of params.questions) results.push(await answerQuestion(question, ctx.ui));
      return withQualityAskResults({
        content: [{ type: "text", text: `User answers:\n${results.map(formatAnswer).join("\n")}` }],
        details: { results },
      }, params.questions, ctx.cwd, signal);
    },
  } as any);
}

export default async function archimedes(pi: ExtensionAPI): Promise<void> {
  const require = createRequire(join(getAgentDir(), "npm", "package.json"));
  const archimedesEntry = require.resolve("pi-archimedes");
  const packageRequire = createRequire(archimedesEntry);
  const busEntry = packageRequire.resolve("@pi-archimedes/core/bus");
  const agentsEntry = packageRequire.resolve("@pi-archimedes/subagent/agents");
  const typesEntry = packageRequire.resolve("@pi-archimedes/subagent/types");
  const [{ default: registerArchimedes }, busModule, agentsModule, typesModule] = await Promise.all([
    import(pathToFileURL(archimedesEntry).href) as Promise<{ default: ArchimedesFactory }>,
    import(pathToFileURL(busEntry).href) as Promise<ArchimedesBusModule>,
    import(pathToFileURL(agentsEntry).href) as Promise<ArchimedesAgentsModule>,
    import(pathToFileURL(typesEntry).href) as Promise<ArchimedesTypesModule>,
  ]);
  const defaultCap = meteredOneShotMaxOutputTokens();
  const billingClasses = loadBillingClasses();
  const resolveAgentModel: AgentModelResolver = agentsModule.resolveAgentModel;
  let upstreamAsk: ToolDefinition | undefined;
  const components = new Proxy(pi, {
    get(target, property, receiver) {
      if (property === "registerTool") {
        return (tool: ToolDefinition) => {
          if (tool.name === "ask") upstreamAsk = tool;
          else if (tool.name === "subagent") {
            registerContractAwareSubagent(
              target,
              tool,
              typesModule.SUBAGENT_OUTPUT_CONTRACTS,
              billingClasses,
              resolveAgentModel,
              defaultCap,
            );
          }
          else target.registerTool(tool as any);
        };
      }
      const value = Reflect.get(target, property, receiver);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });

  await registerArchimedes(components);
  registerPortableAsk(pi, upstreamAsk, (questions) => busModule.getBus().emit(busModule.Events.ASK_REQUEST, {
    source: "main",
    requestId: randomUUID(),
    questions: questions.map(({ selectionMode, ...question }) => ({
      ...question,
      multi: selectionMode === "multi",
    })),
  }));
}
