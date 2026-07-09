// Beads-backed ask/approval bridge.
//
// Durable state lives in Beads and .pi/runs via `agnt approvals`. This Pi
// extension is intentionally thin: it exposes structured tools for interactive
// sessions, creates the Beads decision/blocker before any UI prompt, and records
// any final approval decision back through the same deterministic CLI.

import { execFile } from "node:child_process";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";

const AGNT_BIN = join(getAgentDir(), "bin", "agnt");

const PreviewSchema = Type.Object({
	action: Type.String({ description: "What action is being approved or decided" }),
	scope: Type.String({ description: "What changes and what does not" }),
	consequences: Type.String({ description: "Immediate/downstream consequence statement" }),
	reversibility: Type.String({ description: "Whether/how the action can be undone" }),
	closeoutPath: Type.String({ description: "How the decision will be closed out and evidenced" }),
});

const RequestProperties = {
	targetBead: Type.String({ description: "Bead blocked by this human decision" }),
	question: Type.String({ description: "Question shown to the user and stored in Beads" }),
	context: Type.String({ description: "Decision context sufficient for handoff" }),
	options: Type.Array(Type.String(), { description: "Available answers/options" }),
	default: Type.Optional(Type.String({ description: "Requested default option" })),
	requestingRun: Type.Optional(Type.String({ description: "Run id requesting the decision" })),
	runBundle: Type.Optional(Type.String({ description: "Path to .pi/runs/<id> bundle to update" })),
	preview: PreviewSchema,
};

const RequestSchema = Type.Object(RequestProperties);

const ApprovalSchema = Type.Object({
	...RequestProperties,
	promptUser: Type.Optional(Type.Boolean({ description: "If true and UI exists, ask for confirm after creating the Beads blocker" })),
});

const ResolveSchema = Type.Object({
	decisionBead: Type.String({ description: "Decision/approval bead to resolve" }),
	outcome: StringEnum(["approved", "answered", "rejected", "cancelled", "timed-out"] as const),
	answer: Type.Optional(Type.String({ description: "Human answer or reason" })),
	runBundle: Type.Optional(Type.String({ description: "Path to .pi/runs/<id> bundle to update" })),
});

interface RequestParams {
	targetBead: string;
	question: string;
	context: string;
	options: string[];
	default?: string;
	requestingRun?: string;
	runBundle?: string;
	preview: {
		action: string;
		scope: string;
		consequences: string;
		reversibility: string;
		closeoutPath: string;
	};
	promptUser?: boolean;
}

interface ResolveParams {
	decisionBead: string;
	outcome: "approved" | "answered" | "rejected" | "cancelled" | "timed-out";
	answer?: string;
	runBundle?: string;
}

function runAgnt(args: string[], cwd: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
	return new Promise((resolve, reject) => {
		const proc = execFile(AGNT_BIN, args, { cwd, encoding: "utf-8", maxBuffer: 8 * 1024 * 1024, signal }, (err, stdout, stderr) => {
			if (err) {
				reject(new Error((stderr || stdout || err.message).trim()));
				return;
			}
			try {
				resolve(JSON.parse(stdout || "{}") as Record<string, unknown>);
			} catch (parseErr) {
				reject(new Error(`agnt did not return JSON: ${(parseErr as Error).message}; output=${stdout}`));
			}
		});
		if (signal) {
			signal.addEventListener("abort", () => proc.kill(), { once: true });
		}
	});
}

function requestArgs(kind: "question" | "approval", params: RequestParams): string[] {
	const args = [
		"approvals",
		"request",
		"--kind",
		kind,
		"--target-bead",
		params.targetBead,
		"--question",
		params.question,
		"--context",
		params.context,
		"--preview-action",
		params.preview.action,
		"--preview-scope",
		params.preview.scope,
		"--preview-consequences",
		params.preview.consequences,
		"--preview-reversibility",
		params.preview.reversibility,
		"--preview-closeout-path",
		params.preview.closeoutPath,
		"--json",
	];
	for (const option of params.options) args.push("--option", option);
	if (params.default) args.push("--default", params.default);
	if (params.requestingRun) args.push("--requesting-run", params.requestingRun);
	if (params.runBundle) args.push("--run-bundle", params.runBundle);
	return args;
}

function resolveArgs(params: ResolveParams): string[] {
	const args = ["approvals", "resolve", params.decisionBead, "--outcome", params.outcome, "--json"];
	if (params.answer) args.push("--answer", params.answer);
	if (params.runBundle) args.push("--run-bundle", params.runBundle);
	return args;
}

function approvalMessage(params: RequestParams, decisionBead: string): string {
	return [
		params.question,
		"",
		`Decision bead: ${decisionBead}`,
		`Target bead: ${params.targetBead}`,
		"",
		`Action: ${params.preview.action}`,
		`Scope: ${params.preview.scope}`,
		`Consequences: ${params.preview.consequences}`,
		`Reversibility: ${params.preview.reversibility}`,
		`Closeout path: ${params.preview.closeoutPath}`,
	].join("\n");
}

export default function beadsAskBridge(pi: ExtensionAPI) {
	pi.registerTool({
		name: "ticket_question",
		label: "Ticket Question",
		description: "Create a durable Beads-backed human question that blocks a target bead until resolved.",
		promptSnippet: "Create a Beads-backed question/blocker before asking for human input.",
		promptGuidelines: [
			"Use ticket_question when a human preference or answer is needed; do not leave the answer only in chat or UI state.",
		],
		parameters: RequestSchema,
		async execute(_toolCallId, params: RequestParams, signal, _onUpdate, ctx) {
			const result = await runAgnt(requestArgs("question", params), ctx.cwd, signal);
			const decisionBead = String(result.decisionBead ?? "");
			return {
				content: [{ type: "text", text: `Created Beads-backed question ${decisionBead}. Resolve it with ticket_decision_resolve after the human answers.` }],
				details: result,
			};
		},
	});

	pi.registerTool({
		name: "ticket_approval",
		label: "Ticket Approval",
		description: "Create a durable Beads-backed approval gate and optionally ask the user through the Pi UI.",
		promptSnippet: "Create a Beads-backed approval/blocker before requesting human approval.",
		promptGuidelines: [
			"Use ticket_approval for consequential actions requiring approval; the Beads decision is created before any UI confirmation.",
		],
		parameters: ApprovalSchema,
		async execute(_toolCallId, params: RequestParams, signal, _onUpdate, ctx) {
			const request = await runAgnt(requestArgs("approval", params), ctx.cwd, signal);
			const decisionBead = String(request.decisionBead ?? "");

			if (!params.promptUser || !ctx.hasUI) {
				return {
					content: [{ type: "text", text: `Created Beads-backed approval ${decisionBead}; blocker remains visible until resolved.` }],
					details: request,
				};
			}

			const approved = await ctx.ui.confirm("Approval requested", approvalMessage(params, decisionBead));
			const outcome = approved ? "approved" : "rejected";
			const resolution = await runAgnt(resolveArgs({
				decisionBead,
				outcome,
				answer: approved ? "Approved in Pi UI" : "Rejected in Pi UI",
				runBundle: params.runBundle,
			}), ctx.cwd, signal);
			return {
				content: [{ type: "text", text: `Approval ${decisionBead} ${outcome}.` }],
				details: { request, resolution },
			};
		},
	});

	pi.registerTool({
		name: "ticket_decision_resolve",
		label: "Resolve Ticket Decision",
		description: "Record the final answer/rejection/cancellation/timeout for a Beads-backed question or approval.",
		parameters: ResolveSchema,
		async execute(_toolCallId, params: ResolveParams, signal, _onUpdate, ctx) {
			const result = await runAgnt(resolveArgs(params), ctx.cwd, signal);
			return {
				content: [{ type: "text", text: `Resolved ${params.decisionBead} as ${params.outcome}; blocker visible=${String(result.blockerVisible)}.` }],
				details: result,
			};
		},
	});
}
