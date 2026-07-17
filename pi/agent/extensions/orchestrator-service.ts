// Optional project-local runner service orchestration for Pi.
//
// Normal Pi sessions retain direct coding tools and do not start or health-gate
// the runner. Explicit `--orchestrator-service` or environment opt-in enables
// the preserved orchestrator/client workflow and its restricted tool surface.

import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { CONFIG_DIR_NAME, getAgentDir, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";

const AGNT_BIN = join(getAgentDir(), "bin", "agnt");
const STATUS_KEY = "orchestrator-service";
const WIDGET_KEY = "orchestrator-service";
const POLL_MS = 5000;

const ORCHESTRATOR_SAFE_TOOLS = [
	"read",
	"ticket_gateway",
	"ticket_question",
	"ticket_approval",
	"ticket_decision_resolve",
	"recall",
] as const;

const ORCHESTRATOR_REPAIR_TOOLS = [
	"read",
	"bash",
	"edit",
	"write",
	"grep",
	"find",
	"ls",
	"ticket_gateway",
	"ticket_question",
	"ticket_approval",
	"ticket_decision_resolve",
	"recall",
] as const;

type JsonObject = Record<string, unknown>;

interface ServiceConnection {
	baseUrl: string;
	token: string;
}

interface SessionState {
	leaseId?: string;
	pendingLeaseId?: string;
	pollTimer?: ReturnType<typeof setInterval>;
	startupAbort?: AbortController;
	shutdownStarted: boolean;
	repairToolsActive: boolean;
}

function asObject(value: unknown): JsonObject {
	return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function truncateLine(text: string, max = 120): string {
	return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function statusText(ctx: ExtensionContext, label: string, level: "ok" | "warn" | "error" = "ok"): string {
	if (level === "error") return ctx.ui.theme.fg("error", label);
	if (level === "warn") return ctx.ui.theme.fg("warning", label);
	return ctx.ui.theme.fg("accent", label);
}

function runnerDir(cwd: string): string {
	return join(cwd, CONFIG_DIR_NAME, "runner");
}

async function readJsonFile(path: string): Promise<JsonObject> {
	const text = await readFile(path, "utf-8");
	return asObject(JSON.parse(text));
}

async function runAgnt(args: string[], cwd: string, signal?: AbortSignal): Promise<JsonObject> {
	return new Promise((resolve, reject) => {
		const proc = execFile(
			AGNT_BIN,
			args,
			{ cwd, encoding: "utf-8", maxBuffer: 8 * 1024 * 1024, signal },
			(err, stdout, stderr) => {
				if (err) {
					reject(new Error((stderr || stdout || err.message).trim()));
					return;
				}
				try {
					resolve(asObject(JSON.parse(stdout || "{}")));
				} catch (parseErr) {
					reject(new Error(`agnt did not return JSON: ${(parseErr as Error).message}; output=${stdout}`));
				}
			},
		);
		if (signal) signal.addEventListener("abort", () => proc.kill(), { once: true });
	});
}

async function loadServiceConnection(cwd: string): Promise<ServiceConnection> {
	const dir = runnerDir(cwd);
	const metadata = await readJsonFile(join(dir, "service.json"));
	const baseUrl = String(metadata.baseUrl || "").replace(/\/$/, "");
	const tokenPath = String(metadata.tokenPath || join(dir, "token"));
	if (!baseUrl) throw new Error("runner service metadata does not include baseUrl");
	const token = (await readFile(tokenPath, "utf-8")).trim();
	if (!token) throw new Error("runner service token is empty");
	return { baseUrl, token };
}

async function runnerRequest(cwd: string, path: string, init: RequestInit = {}): Promise<JsonObject> {
	const connection = await loadServiceConnection(cwd);
	const headers = new Headers(init.headers);
	headers.set("Authorization", `Bearer ${connection.token}`);
	headers.set("Accept", "application/json");
	if (init.body !== undefined) headers.set("Content-Type", "application/json");
	const response = await fetch(`${connection.baseUrl}${path}`, { ...init, headers });
	const text = await response.text();
	const payload = text ? asObject(JSON.parse(text)) : {};
	if (!response.ok) {
		throw new Error(String(payload.error || `runner request failed: HTTP ${response.status}`));
	}
	return payload;
}

function startupReady(report: JsonObject): boolean {
	const startup = asObject(report.startup);
	return report.status === "passed" && startup.backgroundDispatchAllowed === true;
}

function failureLines(report: JsonObject): string[] {
	const failures = Array.isArray(report.failures) ? report.failures : [];
	const warnings = Array.isArray(report.warnings) ? report.warnings : [];
	const rows = [...failures, ...warnings]
		.map((entry) => asObject(entry))
		.map((entry) => `${String(entry.id || "check")}: ${String(entry.message || entry.status || "not ready")}`)
		.map((line) => `• ${truncateLine(line, 140)}`)
		.slice(0, 8);
	return rows.length > 0 ? rows : ["• Startup profile did not report a ready state."];
}

function formatContext(contextValue: unknown): string {
	const context = asObject(contextValue);
	const percent = context.percent;
	if (typeof percent === "number") return `${percent}%`;
	if (typeof percent === "string" && percent.trim()) return percent;
	const used = context.used;
	const limit = context.limit;
	if ((typeof used === "number" || typeof used === "string") && (typeof limit === "number" || typeof limit === "string")) {
		return `${used}/${limit}`;
	}
	return "unknown";
}

function formatCost(costValue: unknown): string {
	const cost = asObject(costValue);
	const usd = cost.usd;
	if (typeof usd === "number") return `$${usd.toFixed(2)}`;
	if (typeof usd === "string" && usd.trim()) return `$${usd}`;
	return "unknown";
}

function formatActiveRun(runValue: unknown): string {
	const run = asObject(runValue);
	const slug = String(run.slug || run.bead || "work").slice(0, 80);
	const model = String(run.model || "model unknown");
	const effort = String(run.thinkingLevel || "effort unknown");
	return `work: ${slug} · model: ${model} · effort: ${effort} · context: ${formatContext(run.context)} · cost: ${formatCost(run.cost)}`;
}

function summarizeRunnerStatus(payload: JsonObject): string[] {
	const activeRuns = Array.isArray(payload.activeRuns) ? payload.activeRuns : [];
	const firstActive = payload.firstActive ? asObject(payload.firstActive) : asObject(activeRuns[0]);
	const budget = asObject(payload.budget);
	const state = String(payload.status || (payload.running ? "running" : "not-running"));
	const activeCount = Number(payload.activeCount ?? activeRuns.length);
	const lines = [
		`runner: ${state}${payload.paused ? " paused" : ""}${payload.draining ? " draining" : ""}`,
		`active: ${activeCount}`,
		`accepting: ${payload.acceptingNewWork === false ? "no" : "yes"}`,
	];
	if (firstActive.bead || firstActive.slug) {
		lines.push(formatActiveRun(firstActive));
	}
	if (budget.limitsEnforced !== undefined) {
		lines.push(`budget enforced: ${budget.limitsEnforced ? "yes" : "no"}`);
	}
	return lines.slice(0, 8);
}

function showBlockedStartup(ctx: ExtensionContext, report: JsonObject): void {
	ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch blocked", "error"));
	ctx.ui.setWidget("orchestrator-service", [
		"Orchestrator startup blocked: fix or acknowledge warnings before background dispatch.",
		...failureLines(report),
	]);
	if (ctx.hasUI) ctx.ui.notify("Orchestrator startup blocked; see runner widget for readiness details.", "warning");
}

function showRunnerStatus(ctx: ExtensionContext, payload: JsonObject): void {
	const status = String(payload.status || (payload.running ? "running" : "unknown"));
	const level = payload.draining || payload.paused ? "warn" : "ok";
	ctx.ui.setStatus("orchestrator-service", statusText(ctx, `orch ${status}`, level));
	ctx.ui.setWidget("orchestrator-service", summarizeRunnerStatus(payload));
}

function showFailure(ctx: ExtensionContext, error: unknown): void {
	const message = error instanceof Error ? error.message : String(error);
	ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch error", "error"));
	ctx.ui.setWidget("orchestrator-service", [`Orchestrator service error: ${truncateLine(message, 180)}`]);
	if (ctx.hasUI) ctx.ui.notify(`orchestrator-service failed: ${message}`, "warning");
}

function isExpectedShutdownError(error: unknown): boolean {
	const message = (error instanceof Error ? error.message : String(error)).toLowerCase();
	return ["abort", "fetch failed", "connection refused", "econnrefused", "enoent", "no such file or directory"].some((item) =>
		message.includes(item),
	);
}

function showShutdownWarning(ctx: ExtensionContext): void {
	ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch draining", "warn"));
}

function showShutdownFailure(ctx: ExtensionContext, error: unknown): void {
	if (isExpectedShutdownError(error)) {
		showShutdownWarning(ctx);
		return;
	}
	showFailure(ctx, error);
}

function handleAsyncFailure(ctx: ExtensionContext, state: SessionState, error: unknown): void {
	if (state.shutdownStarted && isExpectedShutdownError(error)) {
		showShutdownWarning(ctx);
		return;
	}
	showFailure(ctx, error);
}

async function abortStartup(state: SessionState): Promise<void> {
	if (state.startupAbort) {
		state.startupAbort.abort();
		state.startupAbort = undefined;
	}
	if (state.pollTimer) {
		clearInterval(state.pollTimer);
		state.pollTimer = undefined;
	}
}

async function refreshRunnerStatus(ctx: ExtensionContext, signal?: AbortSignal): Promise<JsonObject> {
	const payload = await runAgnt(["work", "runner", "status", "--json"], ctx.cwd, signal);
	showRunnerStatus(ctx, payload);
	return payload;
}

async function ensureDaemon(ctx: ExtensionContext, signal?: AbortSignal): Promise<void> {
	const status = await runAgnt(["work", "daemon", "status", "--json"], ctx.cwd, signal);
	const service = asObject(status.service);
	const activeRuns = Array.isArray(service.activeRuns) ? service.activeRuns : [];
	if (status.running === true && status.connected === true) {
		if (service.schedulerEnabled !== true && activeRuns.length === 0) {
			ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch upgrading", "warn"));
			await runAgnt(["work", "daemon", "stop", "--force", "--json"], ctx.cwd, signal);
			await runAgnt(["work", "daemon", "start", "--json"], ctx.cwd, signal);
			return;
		}
		if (service.draining === true || service.paused === true || service.acceptingNewWork === false) {
			ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch resuming", "warn"));
			await runAgnt(["work", "runner", "resume", "--json"], ctx.cwd, signal);
		}
		return;
	}
	ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch starting", "warn"));
	await runAgnt(["work", "daemon", "start", "--json"], ctx.cwd, signal);
}

async function attachLease(ctx: ExtensionContext, state: SessionState, signal?: AbortSignal): Promise<void> {
	if (state.leaseId || state.pendingLeaseId) return;
	const leaseId = `pi-${Date.now()}-${randomUUID()}`;
	state.pendingLeaseId = leaseId;
	try {
		await runnerRequest(ctx.cwd, "/v1/leases", {
			method: "POST",
			signal,
			body: JSON.stringify({ leaseId, sessionId: leaseId, client: "pi-tui" }),
		});
		if (state.pendingLeaseId !== leaseId) {
			await runnerRequest(ctx.cwd, `/v1/leases/${encodeURIComponent(leaseId)}`, { method: "DELETE" }).catch(() => undefined);
			return;
		}
		state.leaseId = leaseId;
		state.pendingLeaseId = undefined;
	} catch (err) {
		const releasedDuringAttach = state.pendingLeaseId !== leaseId;
		if (!releasedDuringAttach) state.pendingLeaseId = undefined;
		if (releasedDuringAttach) {
			await runnerRequest(ctx.cwd, `/v1/leases/${encodeURIComponent(leaseId)}`, { method: "DELETE" }).catch(() => undefined);
		}
		throw err;
	}
}

async function releaseLease(ctx: ExtensionContext, state: SessionState): Promise<void> {
	const leaseId = state.leaseId || state.pendingLeaseId;
	if (!leaseId) return;
	state.leaseId = undefined;
	state.pendingLeaseId = undefined;
	await runnerRequest(ctx.cwd, `/v1/leases/${encodeURIComponent(leaseId)}`, { method: "DELETE" });
}

function restrictTools(pi: ExtensionAPI): void {
	pi.setActiveTools(ORCHESTRATOR_SAFE_TOOLS as unknown as string[]);
}

function enableRepairTools(pi: ExtensionAPI): void {
	pi.setActiveTools(ORCHESTRATOR_REPAIR_TOOLS as unknown as string[]);
}

function getBooleanFlag(pi: ExtensionAPI, name: string): boolean {
	const getFlag = (pi as unknown as { getFlag?: (flagName: string) => unknown }).getFlag;
	return getFlag?.(name) === true;
}

function orchestrationEnabled(pi: ExtensionAPI): boolean {
	return getBooleanFlag(pi, "orchestrator-service")
		|| process.env.PI_ORCHESTRATOR_SERVICE === "1"
		|| process.env.PI_ORCHESTRATOR_REPAIR_TOOLS === "1";
}

function repairToolsEnabled(pi: ExtensionAPI): boolean {
	return getBooleanFlag(pi, "orchestrator-repair-tools") || process.env.PI_ORCHESTRATOR_REPAIR_TOOLS === "1";
}

async function applyToolMode(pi: ExtensionAPI, ctx: ExtensionContext, state: SessionState): Promise<void> {
	state.repairToolsActive = repairToolsEnabled(pi) || state.repairToolsActive;
	if (state.repairToolsActive) {
		enableRepairTools(pi);
		ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch repair-tools", "warn"));
		ctx.ui.setWidget("orchestrator-service", [
			"Orchestrator repair-tools mode is active.",
			"Runner lifecycle is enabled; bash/edit/write are temporarily available for bootstrap repair.",
		]);
		return;
	}
	restrictTools(pi);
}

function startStatusPolling(ctx: ExtensionContext, state: SessionState): void {
	if (state.shutdownStarted) return;
	if (state.pollTimer) clearInterval(state.pollTimer);
	state.pollTimer = setInterval(() => {
		if (state.shutdownStarted) return;
		refreshRunnerStatus(ctx).catch((err) => handleAsyncFailure(ctx, state, err));
	}, POLL_MS);
}

export default function orchestratorService(pi: ExtensionAPI) {
	pi.registerFlag("orchestrator-service", {
		description: "Opt in to the project-local runner and orchestrator-only tool surface",
		type: "boolean",
		default: false,
	});

	pi.registerFlag("orchestrator-repair-tools", {
		description: "Keep orchestrator-service running but enable write tools for temporary bootstrap repair",
		type: "boolean",
		default: false,
	});

	const state: SessionState = { shutdownStarted: false, repairToolsActive: false };

	pi.on("session_start", async (_event, ctx) => {
		if (!orchestrationEnabled(pi)) return;
		state.shutdownStarted = false;
		const startupAbort = new AbortController();
		state.startupAbort = startupAbort;
		await applyToolMode(pi, ctx, state);
		if (!state.repairToolsActive) ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch checking", "warn"));
		try {
			const startup = await runAgnt(["doctor", "--profile", "orchestrator-startup", "--json"], ctx.cwd, startupAbort.signal);
			if (state.shutdownStarted) return;
			if (!startupReady(startup)) {
				showBlockedStartup(ctx, startup);
				return;
			}
			await ensureDaemon(ctx, startupAbort.signal);
			if (state.shutdownStarted) return;
			await attachLease(ctx, state, startupAbort.signal);
			if (state.shutdownStarted) {
				await releaseLease(ctx, state).catch((err) => {
					if (!isExpectedShutdownError(err)) throw err;
				});
				return;
			}
			await refreshRunnerStatus(ctx, startupAbort.signal);
			if (state.shutdownStarted) return;
			startStatusPolling(ctx, state);
		} catch (err) {
			handleAsyncFailure(ctx, state, err);
		} finally {
			if (state.startupAbort === startupAbort) state.startupAbort = undefined;
		}
	});

	// idempotent shutdown: Pi may emit shutdown during reload/session replacement/quit.
	pi.on("session_shutdown", async (_event, ctx) => {
		if (!orchestrationEnabled(pi)) return;
		if (state.shutdownStarted) return;
		state.shutdownStarted = true;
		await abortStartup(state);
		try {
			await releaseLease(ctx, state);
			ctx.ui.setStatus("orchestrator-service", statusText(ctx, "orch detached", "ok"));
		} catch (err) {
			// Shutdown must tolerate an already-stopped service.
			if (isExpectedShutdownError(err)) {
				showShutdownWarning(ctx);
				return;
			}
			showShutdownFailure(ctx, err);
		}
	});

	pi.registerCommand("runner", {
		description: "Inspect the optional project runner or manage explicit repair-tools mode",
		handler: async (args, ctx) => {
			const parts = String(args || "").trim().split(/\s+/).filter(Boolean);
			if (parts[0] === "repair-tools") {
				const action = parts[1] || "status";
				if (action === "on") {
					state.repairToolsActive = true;
					await applyToolMode(pi, ctx, state);
					ctx.ui.notify("orchestrator repair-tools mode enabled for this session", "warning");
					return;
				}
				if (action === "off") {
					state.repairToolsActive = false;
					restrictTools(pi);
					ctx.ui.notify("orchestrator repair-tools mode disabled; safe orchestrator tools restored", "info");
					await refreshRunnerStatus(ctx).catch(() => undefined);
					return;
				}
				ctx.ui.notify(`orchestrator repair-tools mode: ${state.repairToolsActive ? "on" : "off"}`, state.repairToolsActive ? "warning" : "info");
				ctx.ui.setStatus("orchestrator-service", statusText(ctx, state.repairToolsActive ? "orch repair-tools" : "orch normal", state.repairToolsActive ? "warn" : "ok"));
				return;
			}
			try {
				await refreshRunnerStatus(ctx);
			} catch (err) {
				showFailure(ctx, err);
			}
		},
	});
}
