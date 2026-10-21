import type { JsonValue } from "@earendil-works/pi-ai";
import type { SubagentResult } from "@pi-archimedes/subagent/types";

export const SUBAGENT_INLINE_CHARS = 12_000;
const ERROR_CHARS = 4_000;
const TRUNCATION_MARKER = "\n[output truncated]";

type ContractInput = {
  outputContract?: string;
  tasks?: Array<{ outputContract?: string }>;
};
type ManagedResult = SubagentResult & {
  artifact?: { status: "persisted" | "failed"; refs: string[]; failureClass?: "resolution" | "write" };
};
type Details = { mode: string; results: ManagedResult[] };

export function startupTimeoutMs(error: string | undefined): number | undefined {
  const match = error?.match(/no output within ([0-9]+(?:\.[0-9]+)?) minutes? of startup/i);
  return match ? Number(match[1]) * 60_000 : undefined;
}

export function resultExecutionOutcome(result: SubagentResult): "succeeded" | "failed" | "unavailable" {
  if ((result.exitCode ?? 1) === 0) return "succeeded";
  const reason = result.termination?.reason;
  return result.exitCode === 124 || reason === "time-limit" || reason === "idle-limit" || reason === "user-abort" || startupTimeoutMs(result.error)
    ? "unavailable"
    : "failed";
}

export function boundedSubagentText(text: string, maximum = SUBAGENT_INLINE_CHARS): string {
  if (text.length <= maximum) return text;
  if (maximum <= TRUNCATION_MARKER.length) return text.slice(0, Math.max(0, maximum));
  return text.slice(0, maximum - TRUNCATION_MARKER.length) + TRUNCATION_MARKER;
}

/** Extend upstream's report schema, rather than maintaining a second native schema. */
export function managedSubagentSchema(schema: any): any {
  if (!schema?.properties?.results?.items?.properties) {
    throw new Error("Archimedes subagent output schema is missing run-report properties");
  }
  const copy = structuredClone(schema);
  const run = copy.properties.results.items;
  Object.assign(run.properties, {
    executionOutcome: { type: "string", enum: ["succeeded", "failed", "unavailable"] },
    outputStatus: { type: "string", enum: ["included", "truncated", "omitted", "unavailable"] },
    artifact: {
      type: "object",
      properties: {
        status: { type: "string", enum: ["persisted", "failed"] },
        refs: { type: "array", items: { type: "string" } },
        failureClass: { type: "string", enum: ["resolution", "write"] },
      },
      required: ["status", "refs"],
    },
    terminationEvidence: {
      type: "object",
      properties: {
        reason: { type: "string" },
        source: { type: "string", enum: ["caller", "operator", "execution-profile", "wrapper", "parent-cancellation", "worker-startup", "worker", "provider"] },
        limit: { type: "number" },
        observed: { type: "number" },
        usageState: { type: "string", enum: ["complete", "partial", "unknown"] },
      },
      required: ["reason", "source", "usageState"],
    },
  });
  run.required = [...new Set([...(run.required ?? []), "executionOutcome", "outputStatus"])];
  return copy;
}

/**
 * Native facts remain native; managed transport follows the caller's contract.
 * Full output stays in details/private artifacts, never in an omitted JSON field.
 * Missing or mismatched native data is not invented: the host falls back to text.
 */
export function managedSubagentReport(
  structured: unknown,
  details: Details | undefined,
  input: ContractInput,
  contracts: ReadonlySet<string>,
  evidence?: (result: ManagedResult, index: number) => unknown,
): JsonValue | undefined {
  if (!structured || typeof structured !== "object" || !details) return undefined;
  const native = structured as { mode?: string; results?: Array<Record<string, JsonValue>> };
  if (native.mode !== details.mode || !Array.isArray(native.results) || native.results.length !== details.results.length) return undefined;
  if (native.results.some((report) => !report || typeof report !== "object" || Array.isArray(report))) return undefined;
  let remainingOutput = SUBAGENT_INLINE_CHARS;
  return {
    mode: details.mode,
    results: native.results.map((source, index) => {
      const result = details.results[index]!;
      const report = structuredClone(source);
      const requested = input.tasks?.[index]?.outputContract ?? input.outputContract ?? result.outputContract;
      const contract = requested && contracts.has(requested) ? requested : undefined;
      const includeOutput = !contract || contract === "inline";
      delete report.finalOutput;
      delete report.artifact;
      delete report.terminationEvidence;
      if (contract) report.outputContract = contract;
      report.executionOutcome = resultExecutionOutcome(result);
      report.outputStatus = !includeOutput ? "omitted"
        : typeof result.finalOutput !== "string" ? "unavailable"
        : result.finalOutput.length > remainingOutput ? "truncated" : "included";
      if (includeOutput && typeof result.finalOutput === "string") {
        report.finalOutput = boundedSubagentText(result.finalOutput, remainingOutput);
        remainingOutput -= report.finalOutput.length;
      }
      if (typeof result.error === "string") report.error = boundedSubagentText(result.error, ERROR_CHARS);
      if (result.artifact) report.artifact = JSON.parse(JSON.stringify(result.artifact)) as JsonValue;
      const termination = evidence?.(result, index);
      if (termination) report.terminationEvidence = JSON.parse(JSON.stringify(termination)) as JsonValue;
      return report;
    }),
  };
}
