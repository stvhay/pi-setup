import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type Question = {
  id: string;
  question: string;
  description?: string;
  options: Array<{ label: string }>;
  multi?: boolean;
  recommended?: number;
};

type Answer = {
  id: string;
  question: string;
  description?: string;
  options: string[];
  multi: boolean;
  selectedOptions: string[];
  customInput?: string;
};

const askParameters = {
  type: "object",
  properties: {
    questions: {
      type: "array",
      minItems: 1,
      items: {
        type: "object",
        required: ["id", "question", "options"],
        properties: {
          id: { type: "string" },
          question: { type: "string" },
          description: { type: "string" },
          options: {
            type: "array",
            minItems: 1,
            items: {
              type: "object",
              required: ["label"],
              properties: { label: { type: "string" } },
            },
          },
          multi: { type: "boolean" },
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

function questionTitle(question: Question): string {
  const description = clean(question.description, 1000);
  return description ? `${clean(question.question)} — ${description}` : clean(question.question);
}

async function answerQuestion(question: Question, ui: any): Promise<Answer> {
  const labels = question.options.map(({ label }) => clean(label));
  const selectedOptions: string[] = [];
  let customInput: string | undefined;

  if (question.multi) {
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
    multi: question.multi ?? false,
    selectedOptions,
    customInput,
  };
}

function formatAnswer(answer: Answer): string {
  const selected = answer.multi
    ? `[${answer.selectedOptions.join(", ")}]`
    : answer.selectedOptions[0];
  if (selected && answer.customInput) return `${answer.id}: ${selected} + Other: “${answer.customInput}”`;
  if (answer.customInput) return `${answer.id}: “${answer.customInput}”`;
  return `${answer.id}: ${selected || "(cancelled)"}`;
}

function todoLines(value: unknown): string[] | undefined {
  if (!Array.isArray(value) || value.length === 0 || value.every((todo) => todo?.status === "completed")) return undefined;
  const icon: Record<string, string> = { completed: "✓", "in-progress": "→", "not-started": "○" };
  return value.slice(0, 50).map((todo: any) => `${icon[todo?.status] || "○"} ${clean(todo?.title, 120) || "Untitled"}`);
}

export function isRPCMode(argv = process.argv): boolean {
  return argv.includes("--mode=rpc") || argv.some((arg, index) => arg === "--mode" && argv[index + 1] === "rpc");
}

export function installAgentOSCompat(pi: ExtensionAPI, rpc = isRPCMode()): void {
  if (!rpc) return;

  pi.registerCommand("reload", {
    description: "Reload Pi settings, extensions, skills, prompts, and context files",
    handler: async (args, ctx) => {
      if (clean(args)) throw new Error("Usage: /reload");
      await ctx.waitForIdle();
      await ctx.reload();
      return;
    },
  });

  pi.on("session_start", () => {
    pi.registerTool({
      name: "ask",
      label: "Ask",
      description: "Ask the user one or more questions when their choice materially affects the outcome.",
      parameters: askParameters as any,
      async execute(_toolCallId, params: { questions: Question[] }, _signal, _onUpdate, ctx) {
        const results: Answer[] = [];
        for (const question of params.questions) results.push(await answerQuestion(question, ctx.ui));
        return {
          content: [{ type: "text", text: `User answers:\n${results.map(formatAnswer).join("\n")}` }],
          details: { results },
        };
      },
    });
  });

  pi.on("tool_execution_start", (event: any, ctx: any) => {
    if (event.toolName === "subagent") {
      const count = Math.max(1, Array.isArray(event.args?.tasks) ? event.args.tasks.length : 1);
      ctx.ui.setWidget(`agent-os-subagent-${clean(event.toolCallId, 80)}`, [
        `Running ${count} ${count === 1 ? "task" : "tasks"}`,
      ]);
      return;
    }
    const todos = event.args?.todoList;
    if (event.toolName === "manage_todo_list" && Array.isArray(todos)) {
      ctx.ui.setWidget("agent-os-todos", todoLines(todos));
    }
  });

  pi.on("tool_execution_end", (event: any, ctx: any) => {
    if (event.toolName === "subagent") {
      ctx.ui.setWidget(`agent-os-subagent-${clean(event.toolCallId, 80)}`, undefined);
    }
  });
}

export default function agentOSCompat(pi: ExtensionAPI): void {
  installAgentOSCompat(pi);
}
