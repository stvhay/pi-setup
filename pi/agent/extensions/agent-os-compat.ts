import {
  DefaultPackageManager,
  getAgentDir,
  SettingsManager,
  type ExtensionAPI,
  type ExtensionCommandContext,
  type PackageSource,
} from "@earendil-works/pi-coding-agent";

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

const packageSourcePattern = /^npm:(?:@[a-z0-9][a-z0-9._~-]*\/)?[a-z0-9][a-z0-9._~-]*$/;
const packageVersionPattern = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

type PackageTarget = { source: string; version?: string };
type PackageOperation = { operation: "install" | "remove" | "update"; targets: PackageTarget[] };

function parsePackageOperation(args: string): PackageOperation | undefined {
  const [operation, ...values] = clean(args, 8000).split(" ");
  if (operation === "remove" && values.length === 1 && packageSourcePattern.test(values[0])) {
    return { operation, targets: [{ source: values[0] }] };
  }
  if (operation !== "install" && operation !== "update") return undefined;
  if (values.length < 2 || values.length % 2 !== 0 || values.length > (operation === "install" ? 2 : 40)) return undefined;
  const targets: PackageTarget[] = [];
  const names = new Set<string>();
  for (let index = 0; index < values.length; index += 2) {
    const source = values[index];
    const version = values[index + 1];
    if (!packageSourcePattern.test(source) || !packageVersionPattern.test(version)) return undefined;
    const name = npmPackageName(source);
    if (names.has(name || "")) throw new Error(`Duplicate package update: ${source}`);
    names.add(name || "");
    targets.push({ source, version });
  }
  if (operation === "install" && targets.length !== 1) return undefined;
  return { operation, targets };
}

function npmPackageName(source: PackageSource): string | undefined {
  const value = typeof source === "string" ? source : source.source;
  if (!value.startsWith("npm:")) return undefined;
  const spec = value.slice(4);
  const slash = spec.startsWith("@") ? spec.indexOf("/") : -1;
  const versionAt = spec.lastIndexOf("@");
  return versionAt > slash ? spec.slice(0, versionAt) : spec;
}

function npmPackagePinned(source: string): boolean {
  const spec = source.slice(4);
  const slash = spec.startsWith("@") ? spec.indexOf("/") : -1;
  return spec.lastIndexOf("@") > slash;
}

async function applyProjectPackage(args: string, ctx: ExtensionCommandContext): Promise<void> {
  const parsed = parsePackageOperation(args);
  if (!parsed) {
    throw new Error(
      "Usage: /agent-os-package install npm:<package> <version> | remove npm:<package> | update npm:<package> <version> [...]",
    );
  }

  if (!ctx.isProjectTrusted()) throw new Error("Project is not trusted; package change cancelled");
  const settings = SettingsManager.create(ctx.cwd, getAgentDir(), { projectTrusted: true });
  const packages = new DefaultPackageManager({ cwd: ctx.cwd, agentDir: getAgentDir(), settingsManager: settings });
  const configuredPackages = packages.listConfiguredPackages();
  for (const target of parsed.targets) {
    const configured = configuredPackages.filter((pkg) => npmPackageName(pkg.source) === npmPackageName(target.source));
    const projectPackage = configured.find((pkg) => pkg.scope === "project");
    if (parsed.operation === "install" && configured.length > 0) {
      throw new Error(`${target.source} is already configured in ${configured[0].scope} scope`);
    }
    if ((parsed.operation === "remove" || parsed.operation === "update") && !projectPackage) {
      if (configured.length > 0) throw new Error(`${target.source} is managed by the Pi baseline and cannot be changed here`);
      throw new Error(`${target.source} is not installed in project scope`);
    }
    if (parsed.operation === "update" && projectPackage && npmPackagePinned(projectPackage.source)) {
      throw new Error(`${target.source} is a pinned project package; reinstall a chosen version explicitly`);
    }
  }
  packages.setProgressCallback((event) => {
    if (event.type === "start") ctx.ui.setStatus("agent-os-packages", event.message || "Changing project packages");
  });
  try {
    if (parsed.operation === "update") {
      const updated: string[] = [];
      const failed: string[] = [];
      for (const { source, version } of parsed.targets) {
        try {
          await packages.install(`${source}@${version}`, { local: true });
          updated.push(`${source}@${version}`);
        } catch (error) {
          failed.push(`${source}: ${clean(error instanceof Error ? error.message : error, 300)}`);
        }
      }
      if (updated.length === 0) throw new Error(`No package updates succeeded. ${failed.join("; ")}`);
      await settings.flush();
      const errors = settings.drainErrors();
      if (errors.length > 0) throw errors[0].error;
      ctx.ui.notify(
        `Updated ${updated.join(", ")}.${failed.length ? ` Failed ${failed.join("; ")}.` : ""} Reloading Pi resources.`,
        failed.length ? "warning" : "info",
      );
    } else {
      const { source, version } = parsed.targets[0];
      if (parsed.operation === "install") {
        await packages.installAndPersist(`${source}@${version}`, { local: true });
        settings.setProjectPackages(
          (settings.getProjectSettings().packages || []).map((configuredSource) =>
            npmPackageName(configuredSource) === npmPackageName(source) ? source : configuredSource,
          ),
        );
      } else await packages.removeAndPersist(source, { local: true });
      await settings.flush();
      const errors = settings.drainErrors();
      if (errors.length > 0) throw errors[0].error;
      ctx.ui.notify(`${parsed.operation === "install" ? "Installed" : "Removed"} ${source}. Reloading Pi resources.`, "info");
    }
  } finally {
    ctx.ui.setStatus("agent-os-packages", undefined);
  }
  await ctx.reload();
}

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

  pi.registerCommand("agent-os-package", {
    description: "Apply an approved project package change from the agent-os Packages control",
    handler: applyProjectPackage,
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
