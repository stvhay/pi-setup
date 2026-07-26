import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type SubagentInput = {
  agent?: string;
  task?: string;
  model?: string;
  tasks?: Array<{ agent?: string; task: string; model?: string }>;
};

type SubagentDetails = {
  mode: "single" | "parallel";
  results: Array<{ exitCode?: number }>;
  progress?: unknown[];
};

export default function subagentErrorWorkaround(pi: ExtensionAPI): void {
  pi.on("tool_result", (event) => {
    if (event.toolName !== "subagent") return;

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
