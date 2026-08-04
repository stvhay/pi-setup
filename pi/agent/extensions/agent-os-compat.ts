import {
  DefaultPackageManager,
  getAgentDir,
  SettingsManager,
  type ExtensionAPI,
  type ExtensionCommandContext,
  type PackageSource,
} from "@earendil-works/pi-coding-agent";

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
    if (names.has(source)) throw new Error(`Duplicate package update: ${source}`);
    names.add(source);
    targets.push({ source, version });
  }
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
    if (parsed.operation === "update" && projectPackage?.source !== target.source) {
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
        await packages.install(`${source}@${version}`, { local: true });
        packages.addSourceToSettings(source, { local: true });
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

function clean(value: unknown, limit = 500): string {
  return String(value ?? "")
    .replace(/[\r\n\t]+/g, " ")
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "")
    .replace(/\s{2,}/g, " ")
    .trim()
    .slice(0, limit);
}

function todoLines(value: unknown): string[] | undefined {
  if (!Array.isArray(value) || value.length === 0 || value.every((todo) => todo?.status === "completed")) return undefined;
  const icon: Record<string, string> = { completed: "✓", "in-progress": "→", "not-started": "○" };
  return value.slice(0, 50).map((todo: any) => `${icon[todo?.status] || "○"} ${clean(todo?.title, 120) || "Untitled"}`);
}

function subagentLines(result: any): string[] | undefined {
  const progress = result?.details?.progress;
  if (!Array.isArray(progress) || progress.length === 0) return undefined;
  const icon: Record<string, string> = { completed: "✓", failed: "✗", running: "→" };
  return progress.slice(0, 50).map((task: any, index) => {
    const parts = [`${icon[task?.status] || "→"} ${index + 1}. ${clean(task?.agent, 60) || "subagent"}`];
    const tool = clean(task?.currentTool, 60);
    if (tool) parts.push(tool);
    if (Number.isSafeInteger(task?.toolCount) && task.toolCount > 0) parts.push(`${task.toolCount} tools`);
    return parts.join(" · ");
  });
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

  pi.on("tool_execution_update", (event: any, ctx: any) => {
    if (event.toolName !== "subagent") return;
    const lines = subagentLines(event.partialResult);
    if (lines) ctx.ui.setWidget(`agent-os-subagent-${clean(event.toolCallId, 80)}`, lines);
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
