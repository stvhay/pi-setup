import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, extname, join } from "node:path";
import { pathToFileURL } from "node:url";

import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

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
type AgentModelResolver = (name: string, cwd: string) => string | undefined;
type BillingClass = "metered" | "subscription";

const METERED_ONE_SHOT_CAP_ENV = "PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS";
const DEFAULT_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS = 16_384;

const outputContracts = ["inline", "artifact", "status-only", "pass-no-findings"] as const;
const outputContractParameter = {
  type: "string",
  enum: outputContracts,
  description: "Expected result shape used for parent artifact persistence and quality evaluation.",
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
        return { ...answer, selectionMode: questions[index]?.selectionMode ?? "single" };
      }),
    },
  };
}

function subagentParameters(parameters: any): any {
  const properties = parameters?.properties;
  const taskItems = properties?.tasks?.items;
  if (!properties || !taskItems?.properties) throw new Error("Archimedes subagent schema is unavailable");
  return {
    ...parameters,
    properties: {
      ...properties,
      outputContract: outputContractParameter,
      tasks: {
        ...properties.tasks,
        items: {
          ...taskItems,
          properties: { ...taskItems.properties, outputContract: outputContractParameter },
        },
      },
    },
  };
}

function upstreamSubagentArguments(params: any): any {
  const { outputContract: _outputContract, ...upstream } = params;
  if (!Array.isArray(upstream.tasks)) return upstream;
  return {
    ...upstream,
    tasks: upstream.tasks.map((value: any) => {
      const { outputContract: _taskOutputContract, ...task } = value;
      return task;
    }),
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

function isOpenRouterModel(model: string | undefined, ctx: any): boolean {
  const ref = model?.trim().replace(/:(?:off|minimal|low|medium|high|xhigh|max)$/i, "").toLowerCase();
  if (!ref) return false;
  if (ref.startsWith("openrouter/")) return true;
  const matches = (ctx?.modelRegistry?.getAll?.() ?? []).filter((candidate: any) =>
    candidate.id.toLowerCase() === ref || `${candidate.provider}/${candidate.id}`.toLowerCase() === ref
  );
  return matches.length === 1 && matches[0].provider.toLowerCase() === "openrouter";
}

function isAgenticMeteredReviewSubagent(params: any, ctx: any): boolean {
  const inheritedModel = ctx?.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined;
  const tasks = Array.isArray(params.tasks)
    ? params.tasks.map((task: any) => ({
        prompt: task.task,
        model: task.model ?? inheritedModel,
        mode: task.mode ?? params.mode ?? "agentic",
      }))
    : [{ prompt: params.task, model: params.model ?? inheritedModel, mode: params.mode ?? "agentic" }];
  return tasks.some(({ prompt, model, mode }: { prompt?: string; model?: string; mode: string }) =>
    mode !== "one-shot" && /\breview(?:ed|ing)?\b/i.test(prompt ?? "") && isOpenRouterModel(model, ctx)
  );
}

function registerContractAwareSubagent(
  pi: ExtensionAPI,
  upstreamSubagent: ToolDefinition | undefined,
  classes: ReadonlyMap<string, BillingClass>,
  resolveAgentModel: AgentModelResolver,
  defaultCap: number | undefined,
): void {
  if (!upstreamSubagent?.execute || !upstreamSubagent.parameters) {
    throw new Error("Archimedes subagent tool is unavailable");
  }
  pi.registerTool({
    ...upstreamSubagent,
    parameters: subagentParameters(upstreamSubagent.parameters),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      if (isAgenticMeteredReviewSubagent(params, ctx)) {
        return {
          content: [{
            type: "text",
            text: "Metered OpenRouter reviews require subagent mode one-shot.",
          }],
          details: {
            mode: Array.isArray(params.tasks) ? "parallel" : "single",
            results: [],
            progress: undefined,
          },
          isError: true,
        };
      }
      const bounded = withMeteredOneShotCaps(params, ctx, classes, resolveAgentModel, defaultCap);
      return upstreamSubagent.execute!(toolCallId, upstreamSubagentArguments(bounded), signal, onUpdate, ctx);
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
        return normalizeLegacyResult(
          await upstreamAsk.execute(toolCallId, legacy, signal, onUpdate, ctx),
          params.questions,
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
        return {
          content: [{ type: "text", text: "User cancelled the question." }],
          details: { results },
        };
      }

      emitAsk?.(params.questions);
      const results: Answer[] = [];
      for (const question of params.questions) results.push(await answerQuestion(question, ctx.ui));
      return {
        content: [{ type: "text", text: `User answers:\n${results.map(formatAnswer).join("\n")}` }],
        details: { results },
      };
    },
  } as any);
}

export default async function archimedes(pi: ExtensionAPI): Promise<void> {
  const require = createRequire(join(getAgentDir(), "npm", "package.json"));
  const archimedesEntry = require.resolve("pi-archimedes");
  const packageRequire = createRequire(archimedesEntry);
  const busEntry = packageRequire.resolve("@pi-archimedes/core/bus");
  const subagentEntry = packageRequire.resolve("@pi-archimedes/subagent");
  const agentsEntry = join(dirname(subagentEntry), `agents${extname(subagentEntry)}`);
  const [{ default: registerArchimedes }, busModule, agentsModule] = await Promise.all([
    import(pathToFileURL(archimedesEntry).href) as Promise<{ default: ArchimedesFactory }>,
    import(pathToFileURL(busEntry).href) as Promise<{ getBus: () => { emit: (event: string, payload: unknown) => void }; Events: { ASK_REQUEST: string } }>,
    import(pathToFileURL(agentsEntry).href) as Promise<{
      discoverAgents: (cwd: string) => any[];
      findAgent: (agents: any[], name: string) => { model?: string } | undefined;
    }>,
  ]);
  const defaultCap = meteredOneShotMaxOutputTokens();
  const billingClasses = defaultCap ? loadBillingClasses() : new Map<string, BillingClass>();
  const resolveAgentModel: AgentModelResolver = (name, cwd) =>
    agentsModule.findAgent(agentsModule.discoverAgents(cwd), name)?.model;
  let upstreamAsk: ToolDefinition | undefined;
  const components = new Proxy(pi, {
    get(target, property, receiver) {
      if (property === "registerTool") {
        return (tool: ToolDefinition) => {
          if (tool.name === "ask") upstreamAsk = tool;
          else if (tool.name === "subagent") {
            registerContractAwareSubagent(target, tool, billingClasses, resolveAgentModel, defaultCap);
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
