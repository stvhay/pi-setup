import { randomUUID } from "node:crypto";
import { createRequire } from "node:module";
import { join } from "node:path";
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
  execute?: (...args: any[]) => Promise<any>;
};
type ArchimedesFactory = (pi: ExtensionAPI) => void | Promise<void>;
type AskEmitter = (questions: Question[]) => void;

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

async function answerQuestion(question: Question, ui: any): Promise<Answer> {
  const labels = question.options.map(({ label }) => clean(label));
  const selectedOptions: string[] = [];
  let customInput: string | undefined;

  if (question.selectionMode === "multi") {
    for (const label of labels) {
      if (await ui.confirm(questionTitle(question), `Select “${label}”?`)) selectedOptions.push(label);
    }
    if (await ui.confirm(questionTitle(question), "Add another answer?")) {
      customInput = clean(await ui.input("Other answer", "Type another answer")) || undefined;
    }
  } else {
    const choices = labels.map(
      (label, index) => `${index + 1}. ${label}${index === question.recommended ? " (Recommended)" : ""}`,
    );
    const selected = await ui.select(questionTitle(question), [...choices, "Other…"]);
    const index = choices.indexOf(selected);
    if (index >= 0) selectedOptions.push(labels[index]);
    if (selected === "Other…") {
      customInput = clean(await ui.input("Other answer", "Type another answer")) || undefined;
    }
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
      if (!ctx.hasUI && upstreamAsk?.execute) {
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
  const busEntry = createRequire(archimedesEntry).resolve("@pi-archimedes/core/bus");
  const [{ default: registerArchimedes }, busModule] = await Promise.all([
    import(pathToFileURL(archimedesEntry).href) as Promise<{ default: ArchimedesFactory }>,
    import(pathToFileURL(busEntry).href) as Promise<{ getBus: () => { emit: (event: string, payload: unknown) => void }; Events: { ASK_REQUEST: string } }>,
  ]);
  let upstreamAsk: ToolDefinition | undefined;
  const components = new Proxy(pi, {
    get(target, property, receiver) {
      if (property === "registerTool") {
        return (tool: ToolDefinition) => {
          if (tool.name === "ask") upstreamAsk = tool;
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
