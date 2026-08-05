// Beads-backed ask/approval bridge.
//
// Durable state lives in Beads and .pi/runs via `agnt approvals`. This Pi
// extension is intentionally thin: it exposes structured tools for interactive
// sessions, creates the Beads decision/blocker before any UI prompt, and records
// any final approval decision back through the same deterministic CLI.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { runAgntJson } from "./lib/run-agnt-json.ts";

const OTHER_CHOICE = "Other… (type a custom response)";

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

const RequestSchema = Type.Object({
	...RequestProperties,
	selectionMode: StringEnum(["single", "multi"] as const),
});

const ApprovalSchema = Type.Object({
	...RequestProperties,
	promptUser: Type.Optional(Type.Boolean({ description: "If true and UI exists, ask for confirm after creating the Beads blocker" })),
});

const ResolveSchema = Type.Object({
	decisionBead: Type.String({ description: "Decision/approval bead to resolve" }),
	outcome: StringEnum(["approved", "answered", "rejected", "cancelled", "timed-out"] as const),
	answer: Type.Optional(Type.String({ description: "Human answer or reason" })),
	selectedOptions: Type.Optional(Type.Array(Type.String(), { description: "Predefined question choices selected by the human" })),
	customInput: Type.Optional(Type.String({ description: "Typed custom response for an answered question" })),
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
	selectionMode?: "single" | "multi";
	promptUser?: boolean;
}

interface ResolveParams {
	decisionBead: string;
	outcome: "approved" | "answered" | "rejected" | "cancelled" | "timed-out";
	answer?: string;
	selectedOptions?: string[];
	customInput?: string;
	runBundle?: string;
}

type QuestionAnswer = {
	answered: boolean;
	selectedOptions: string[];
	customInput?: string;
};

function requestArgs(kind: "question" | "approval", params: RequestParams): string[] {
	const targetBead = params.targetBead;
	const args = [
		"approvals",
		"request",
		"--kind",
		kind,
		"--target-bead",
		targetBead,
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
	if (kind === "question") {
		if (!params.selectionMode) throw new Error("selectionMode is required for questions");
		args.push("--selection-mode", params.selectionMode);
	}
	if (params.default) args.push("--default", params.default);
	if (params.requestingRun) args.push("--requesting-run", params.requestingRun);
	if (params.runBundle) args.push("--run-bundle", params.runBundle);
	return args;
}

function resolveArgs(params: ResolveParams, resolver?: { kind: "human-ui"; sessionId: string }): string[] {
	const args = ["approvals", "resolve", params.decisionBead, "--outcome", params.outcome, "--json"];
	if (resolver) args.push("--resolver-kind", resolver.kind, "--resolver-session", resolver.sessionId);
	if (params.answer) args.push("--answer", params.answer);
	if (params.selectedOptions !== undefined || params.customInput !== undefined) args.push("--structured-answer");
	for (const option of params.selectedOptions ?? []) args.push("--selected-option", option);
	if (params.customInput !== undefined) args.push("--custom-input", params.customInput);
	if (params.runBundle) args.push("--run-bundle", params.runBundle);
	return args;
}

function cleanAnswer(value: unknown): string {
	return String(value ?? "")
		.replace(/[\r\n\t]+/g, " ")
		.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "")
		.replace(/\s{2,}/g, " ")
		.trim()
		.slice(0, 2000);
}

async function askCustomInput(ui: any): Promise<string | undefined> {
	while (true) {
		const raw = await ui.input("Other answer", "Type a custom response");
		if (raw === undefined) return undefined;
		const value = cleanAnswer(raw);
		if (value) return value;
		ui.notify("Custom response cannot be empty.", "warning");
	}
}

async function askQuestion(params: RequestParams, ui: any, title: string): Promise<QuestionAnswer> {
	const selectedOptions: string[] = [];
	let customInput: string | undefined;
	if (params.selectionMode === "multi") {
		for (const option of params.options) {
			const select = `Select “${option}”`;
			const choice = await ui.select(title, [select, `Skip “${option}”`]);
			if (choice === undefined) return { answered: false, selectedOptions: [] };
			if (choice === select) selectedOptions.push(option);
		}
		const customChoice = await ui.select(title, [OTHER_CHOICE, "No custom response"]);
		if (customChoice === undefined) return { answered: false, selectedOptions: [] };
		if (customChoice === OTHER_CHOICE) {
			customInput = await askCustomInput(ui);
			if (customInput === undefined) return { answered: false, selectedOptions: [] };
		}
	} else {
		let otherChoice = OTHER_CHOICE;
		while (params.options.includes(otherChoice)) otherChoice += "…";
		const selected = await ui.select(title, [...params.options, otherChoice]);
		if (selected === undefined) return { answered: false, selectedOptions: [] };
		if (selected === otherChoice) {
			customInput = await askCustomInput(ui);
			if (customInput === undefined) return { answered: false, selectedOptions: [] };
		} else selectedOptions.push(selected);
	}
	return {
		answered: true,
		selectedOptions,
		...(customInput ? { customInput } : {}),
	};
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
		promptSnippet: "Create a durable Beads-backed question only for handoff, later resumption, or a Bead blocker.",
		promptGuidelines: [
			"Use ticket_question only when the answer must survive the current session for handoff, a Bead blocker, or later resumption.",
			"Use transient ask for current-session clarification or exploration.",
			"Set selectionMode explicitly and keep typed custom input available.",
			"Do not chain durable questions for ideation; persist only the final blocking decision when needed.",
		],
		parameters: RequestSchema,
		async execute(_toolCallId, params: RequestParams, signal, _onUpdate, ctx) {
			const request = await runAgntJson(requestArgs("question", params), ctx.cwd, signal);
			const decisionBead = String(request.decisionBead ?? "");
			if (!ctx.hasUI) {
				return {
					content: [{ type: "text", text: `Created Beads-backed question ${decisionBead}; blocker remains visible until a human resolves it.` }],
					details: request,
				};
			}

			const answer = await askQuestion(params, ctx.ui, approvalMessage(params, decisionBead));
			const outcome = answer.answered ? "answered" : "cancelled";
			const resolution = await runAgntJson(resolveArgs({
				decisionBead,
				outcome,
				...(answer.answered ? {
					selectedOptions: answer.selectedOptions,
					customInput: answer.customInput,
				} : { answer: "Cancelled in Pi UI" }),
				runBundle: params.runBundle,
			}, { kind: "human-ui", sessionId: ctx.sessionManager.getSessionId() }), ctx.cwd, signal);
			return {
				content: [{ type: "text", text: `Question ${decisionBead} ${outcome}.` }],
				details: { request, resolution },
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
			const request = await runAgntJson(requestArgs("approval", params), ctx.cwd, signal);
			const decisionBead = String(request.decisionBead ?? "");

			if (!params.promptUser || !ctx.hasUI) {
				return {
					content: [{ type: "text", text: `Created Beads-backed approval ${decisionBead}; blocker remains visible until resolved.` }],
					details: request,
				};
			}

			const approved = await ctx.ui.confirm("Approval requested", approvalMessage(params, decisionBead));
			const outcome = approved ? "approved" : "rejected";
			const resolution = await runAgntJson(resolveArgs({
				decisionBead,
				outcome,
				answer: approved ? "Approved in Pi UI" : "Rejected in Pi UI",
				runBundle: params.runBundle,
			}, { kind: "human-ui", sessionId: ctx.sessionManager.getSessionId() }), ctx.cwd, signal);
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
			let outcome: ResolveParams["outcome"] = params.outcome;
			let answer = params.answer;
			if (params.customInput !== undefined && !cleanAnswer(params.customInput)) {
				throw new Error("Custom response cannot be empty.");
			}
			if (outcome === "approved" && (params.selectedOptions !== undefined || params.customInput !== undefined)) {
				throw new Error("Structured question answers cannot approve an action.");
			}
			let resolver: { kind: "human-ui"; sessionId: string } | undefined;
			if (outcome === "approved" || outcome === "answered") {
				if (!ctx.hasUI) {
					throw new Error("decision resolution requires an interactive human UI");
				}
				const responsePreview = [
					...(answer ? [`Answer: ${answer}`] : []),
					...(params.selectedOptions?.length ? [`Selected: [${params.selectedOptions.join(", ")}]`] : []),
					...(params.customInput ? [`Custom response: ${params.customInput}`] : []),
				];
				const confirmed = await ctx.ui.confirm(
					"Human confirmation required",
					`Resolve ${params.decisionBead} as ${outcome}?${responsePreview.length ? `\n\n${responsePreview.join("\n")}` : ""}`,
				);
				if (!confirmed) {
					outcome = outcome === "approved" ? "rejected" : "cancelled";
					answer = "Not confirmed in Pi UI";
				} else {
					resolver = { kind: "human-ui", sessionId: ctx.sessionManager.getSessionId() };
				}
			}
			const result = await runAgntJson(resolveArgs({
				decisionBead: params.decisionBead,
				outcome,
				answer,
				...(outcome === "answered" ? {
					selectedOptions: params.selectedOptions,
					customInput: params.customInput,
				} : {}),
				runBundle: params.runBundle,
			}, resolver), ctx.cwd, signal);
			return {
				content: [{ type: "text", text: `Resolved ${params.decisionBead} as ${outcome}; blocker visible=${String(result.blockerVisible)}.` }],
				details: result,
			};
		},
	});
}
