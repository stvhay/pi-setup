// Strict ticket gateway for Beads-first orchestration.
//
// The main orchestrator should not receive raw bash, raw Beads, raw subagent,
// edit, or write surfaces. This extension exposes one structured tool and a
// compact /work command that delegate to the deterministic `agnt gateway` core.

import { execFile } from "node:child_process";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";

const AGNT_BIN = join(getAgentDir(), "bin", "agnt");

const OperationEnum = StringEnum([
	"list",
	"show",
	"tree",
	"create_draft",
	"request_approval",
	"resolve_blocker",
	"runner_status",
] as const);

const PreviewSchema = Type.Object({
	action: Type.String(),
	scope: Type.String(),
	consequences: Type.String(),
	reversibility: Type.String(),
	closeoutPath: Type.String(),
});

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
	targetBead: Type.Optional(Type.String()),
	question: Type.Optional(Type.String()),
	context: Type.Optional(Type.String()),
	options: Type.Optional(Type.Array(Type.String())),
	default: Type.Optional(Type.String()),
	requestingRun: Type.Optional(Type.String()),
	preview: Type.Optional(PreviewSchema),
	runBundle: Type.Optional(Type.String()),
	decisionBead: Type.Optional(Type.String()),
	outcome: Type.Optional(StringEnum(["approved", "answered", "rejected", "cancelled", "timed-out"] as const)),
	answer: Type.Optional(Type.String()),
}, { additionalProperties: false });

type GatewayParams = Record<string, unknown> & { operation: string };

function runGateway(payload: GatewayParams, cwd: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
	return new Promise((resolve, reject) => {
		const proc = execFile(
			AGNT_BIN,
			["gateway", "--payload", JSON.stringify(payload), "--json"],
			{ cwd, encoding: "utf-8", maxBuffer: 8 * 1024 * 1024, signal },
			(err, stdout, stderr) => {
				if (err) {
					reject(new Error((stderr || stdout || err.message).trim()));
					return;
				}
				try {
					resolve(JSON.parse(stdout || "{}") as Record<string, unknown>);
				} catch (parseErr) {
					reject(new Error(`agnt gateway did not return JSON: ${(parseErr as Error).message}; output=${stdout}`));
				}
			},
		);
		if (signal) signal.addEventListener("abort", () => proc.kill(), { once: true });
	});
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
		const runner = result.runner as { status?: string } | undefined;
		return `ticket_gateway runner_status: ${runner?.status ?? "unknown"}`;
	}
	return `ticket_gateway ${operation}: ok`;
}

export default function ticketGateway(pi: ExtensionAPI) {
	pi.registerTool({
		name: "ticket_gateway",
		label: "Ticket Gateway",
		description: "Structured Beads-first ticket gateway. Supports list, show, tree, create_draft, request_approval, resolve_blocker, and runner_status without raw shell/Beads access.",
		promptSnippet: "Use ticket_gateway for durable Beads work operations instead of raw bash, raw bd, edit, write, or raw subagent calls.",
		promptGuidelines: [
			"Use ticket_gateway for work listing, ticket details, tree views, draft creation, approval requests, blocker resolution, and runner status.",
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
				ctx.ui.setWidget("ticket-gateway-work", JSON.stringify(result, null, 2).split("\n").slice(0, 20));
			} catch (err) {
				ctx.ui.notify(`ticket_gateway /work failed: ${(err as Error).message}`, "warning");
			}
		},
	});
}
