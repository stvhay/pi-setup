// Optional structured ticket gateway for Beads-backed orchestration.
//
// Direct Pi sessions retain normal workspace tools. When structured
// orchestration is explicitly selected, this extension provides a constrained
// ticket tool and compact /work command backed by `agnt gateway`.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { runAgntJson } from "./lib/run-agnt-json.ts";

const OperationEnum = StringEnum([
	"list",
	"show",
	"tree",
	"create_draft",
	"runner_status",
] as const);

const GatewayParamsSchema = Type.Object({
	operation: OperationEnum,
	bead: Type.Optional(Type.String({ description: "Bead id for show" })),
	root: Type.Optional(Type.String({ description: "Root bead/epic id for tree" })),
	epic: Type.Optional(Type.String({ description: "Alias for root in tree" })),
	limit: Type.Optional(Type.Number({ description: "Positive list limit" })),
	includeEpics: Type.Optional(Type.Boolean()),
	runsDir: Type.Optional(Type.String()),
	title: Type.Optional(Type.String()),
	description: Type.Optional(Type.String()),
	issueType: Type.Optional(StringEnum(["bug", "feature", "task", "epic", "chore", "decision"] as const)),
	priority: Type.Optional(Type.Number()),
	labels: Type.Optional(Type.Array(Type.String())),
	metadata: Type.Optional(Type.Any()),
	parent: Type.Optional(Type.String()),
	acceptance: Type.Optional(Type.String()),
}, { additionalProperties: false });

type GatewayParams = Record<string, unknown> & { operation: string };

function runGateway(payload: GatewayParams, cwd: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
	return runAgntJson(["gateway", "--payload", JSON.stringify(payload), "--json"], cwd, signal, "agnt gateway");
}

function asRecord(value: unknown): Record<string, unknown> {
	return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function summarizeRunnerStatus(runnerValue: unknown): string {
	const runner = asRecord(runnerValue);
	const firstActive = asRecord(runner.firstActive);
	const activeCount = Number(runner.activeCount ?? 0);
	const state = String(runner.status ?? "unknown");
	const flags = [runner.paused ? "paused" : "", runner.draining ? "draining" : ""]
		.filter(Boolean)
		.join("/");
	const slug = String(firstActive.slug || firstActive.bead || "").slice(0, 80);
	const work = slug ? ` first=${slug}` : "";
	return `ticket_gateway runner_status: ${state}${flags ? ` ${flags}` : ""} active=${activeCount}${work}`;
}

function summarize(result: Record<string, unknown>): string {
	const operation = String(result.operation ?? "gateway");
	if (operation === "list" && Array.isArray(result.items)) {
		return `ticket_gateway list: ${result.items.length} item(s)`;
	}
	if (operation === "show") {
		const item = result.item as { id?: string; title?: string } | undefined;
		return `ticket_gateway show: ${item?.id ?? "unknown"} ${item?.title ?? ""}`.trim();
	}
	if (operation === "tree") {
		const tree = result.tree as { root?: string; nodes?: Record<string, unknown> } | undefined;
		return `ticket_gateway tree: ${tree?.root ?? "unknown"} (${Object.keys(tree?.nodes ?? {}).length} node(s))`;
	}
	if (operation === "runner_status") {
		return summarizeRunnerStatus(result.runner);
	}
	return `ticket_gateway ${operation}: ok`;
}

function widgetLines(result: Record<string, unknown>): string[] {
	const operation = String(result.operation ?? "gateway");
	if (operation === "runner_status") {
		return [summarizeRunnerStatus(result.runner)];
	}
	if (operation === "list" && Array.isArray(result.items)) {
		return [summarize(result), ...result.items.slice(0, 8).map((item) => {
			const row = asRecord(item);
			return `• ${String(row.id ?? "?")} ${String(row.title ?? "").slice(0, 80)}`.trim();
		})];
	}
	if (operation === "tree") {
		const tree = asRecord(result.tree);
		const nodes = asRecord(tree.nodes);
		return [summarize(result), ...Object.keys(nodes).slice(0, 8).map((id) => `• ${id}`)];
	}
	return [summarize(result)];
}

export default function ticketGateway(pi: ExtensionAPI) {
	pi.registerTool({
		name: "ticket_gateway",
		label: "Ticket Gateway",
		description: "Optional structured Beads ticket gateway. Supports list, show, tree, create_draft, and runner_status.",
		promptSnippet: "Use ticket_gateway when the structured orchestration workflow is explicitly selected; direct Pi coding remains the default.",
		promptGuidelines: [
			"For direct coding, confirm a Bead exists before code edits; use normal workspace tools for inspection, editing, and verification.",
			"Use ticket_gateway for structured work listing, ticket details, tree views, draft creation, and runner status when orchestration is selected.",
			"Do not send shell commands or raw Beads commands to ticket_gateway; choose one enum operation and structured fields only.",
		],
		parameters: GatewayParamsSchema,
		async execute(_toolCallId, params: GatewayParams, signal, _onUpdate, ctx) {
			const result = await runGateway(params, ctx.cwd, signal);
			return {
				content: [{ type: "text", text: summarize(result) }],
				details: result,
			};
		},
	});

	pi.registerCommand("work", {
		description: "Show compact Beads work tree/status through the ticket gateway",
		handler: async (args, ctx) => {
			const trimmed = (args ?? "").trim();
			const payload: GatewayParams = trimmed
				? { operation: "tree", root: trimmed }
				: { operation: "list", limit: 10, includeEpics: true };
			try {
				const result = await runGateway(payload, ctx.cwd);
				ctx.ui.notify(summarize(result), "info");
				ctx.ui.setWidget("ticket-gateway-work", widgetLines(result));
			} catch (err) {
				ctx.ui.notify(`ticket_gateway /work failed: ${(err as Error).message}`, "warning");
			}
		},
	});
}
