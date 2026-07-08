// guidance-edit-guard.ts
//
// Hard gate: when an agent edits or writes a guidance/context file, run
// `agnt context-health` against the projected post-edit content and block the
// edit on failure (stale terms, gate-weakening language).
//
// Design intent: the things in ~/.pi EXECUTE the self-improvement principles
// rather than restating them. This extension is deterministic behavior, fires
// only on guidance edits, adds zero context load otherwise, and ships globally
// via the pi/ config sync. The principles design doc lives in pi-setup/docs/
// and is intentionally not deployed; this gate is its executable counterpart.
//
// The scan logic is owned by `agnt context-health` (single source of truth);
// this extension only computes projected post-edit content and invokes it.

import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { basename, join, relative } from "node:path";
import {
	type ExtensionAPI,
	getAgentDir,
	isToolCallEventType,
} from "@earendil-works/pi-coding-agent";

const AGNT_BIN = join(getAgentDir(), "bin", "agnt");

// Files whose content is Pi agent guidance / context architecture. Matches the
// set `agnt context-health` scans in the deployed tree, plus the project-local
// equivalents (any AGENTS.md / SKILL.md / SOUL.md anywhere in a project).
function isGuidanceFile(absPath: string): boolean {
	const norm = absPath.replace(/\\/g, "/");
	const base = basename(norm);

	// Root instruction files, anywhere (global or project-local).
	if (["agents.md", "agent.md", "skill.md", "soul.md"].includes(base.toLowerCase())) {
		return true;
	}

	// Layered context packages: <root-stem>.d/roles/** and <root-stem>.d/models/**
	if (/(?:^|\/)[^/]+\.d\/(?:roles|models)\//.test(norm)) {
		return true;
	}

	// Tracked Pi architecture under agent/: skills/*/SKILL.md, tasks/*.md, actions/*.md
	if (/(?:^|\/)skills\/[^/]+\/skill\.md$/i.test(norm)) return true;
	if (/(?:^|\/)tasks\/[^/]+\.md$/i.test(norm)) return true;
	if (/(?:^|\/)actions\/[^/]+\.md$/i.test(norm)) return true;

	return false;
}

// Apply edit[] replacements to current file text to produce projected content.
// Mirrors the semantics of the built-in edit tool: each oldText must match a
// unique region and is replaced (first occurrence). The gate only needs an
// accurate-enough projection; the real edit tool still enforces uniqueness.
function applyEdits(text: string, edits: Array<{ oldText: string; newText: string }>): string {
	let out = text;
	for (const e of edits) {
		const idx = out.indexOf(e.oldText);
		if (idx === -1) {
			// oldText not found (edit would fail anyway). Use the unmodified text;
			// the built-in edit tool will report the real error. We do not block.
			continue;
		}
		out = out.slice(0, idx) + e.newText + out.slice(idx + e.oldText.length);
	}
	return out;
}

interface HealthFailure {
	kind: string;
	path?: string;
	term?: string;
	replacement?: string;
	line?: number;
	pattern?: string;
	text?: string;
}

interface HealthReport {
	schemaVersion: number;
	passed: boolean;
	failures: HealthFailure[];
	warnings: unknown[];
	summary: { failureCount: number; warningCount: number };
}

function scanContent(content: string, relPath: string): Promise<HealthReport> {
	return new Promise<HealthReport>((resolve) => {
		const proc = execFile(
			AGNT_BIN,
			["context-health", "--stdin", "--path", relPath, "--strict"],
			{ maxBuffer: 8 * 1024 * 1024, encoding: "utf-8" },
			(_err, stdout, stderr) => {
				const out = (stdout ?? "").trim();
				try {
					const report = JSON.parse(out) as HealthReport;
					resolve(report);
				} catch {
					// If the scanner itself is broken, do not block work. Fail open
					// rather than turning a tooling fault into a hard stop. Leave an
					// audit trail so the failure is discoverable.
					console.error(
						`[guidance-edit-guard] scanner did not return JSON for ${relPath}:`,
						out || (stderr ?? ""),
					);
					resolve({
						schemaVersion: 1,
						passed: true,
						failures: [],
						warnings: [],
						summary: { failureCount: 0, warningCount: 0 },
					});
				}
			},
		);
		if (proc.stdin) {
			proc.stdin.end(content);
		}
	});
}

function summarizeFailures(failures: HealthFailure[]): string {
	return failures
		.map((f) => {
			const where = f.line ? `:${f.line}` : "";
			if (f.kind === "stale-term") {
				return `  - stale term "${f.term}"${where}: ${f.replacement ?? ""}`.trimEnd();
			}
			if (f.kind === "gate-weakening") {
				return `  - gate-weakening${where}: "${f.text ?? ""}" (matched /${f.pattern ?? ""}/)`;
			}
			return `  - ${f.kind}${where}`;
		})
		.join("\n");
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", async (event, ctx) => {
		// `write` tool: { path: string; content: string }
		if (isToolCallEventType("write", event)) {
			const { path, content } = event.input;
			if (!path || !isGuidanceFile(path)) return undefined;

			const rel = relative(ctx.cwd, path) || path;
			const report = await scanContent(content ?? "", rel);
			if (!report.passed) {
				if (ctx.hasUI) {
					ctx.ui.notify(`Guidance guard blocked write to ${rel}`, "warning");
				}
				return {
					block: true,
					reason:
						`Refusing to write guidance file ${rel}: it would introduce ` +
						`context-health failures. Fix and retry.\n` +
						summarizeFailures(report.failures),
				};
			}
			return undefined;
		}

		// `edit` tool: { path: string; edits: Array<{ oldText; newText }> }
		if (isToolCallEventType("edit", event)) {
			const { path, edits } = event.input;
			if (!path || !Array.isArray(edits) || !isGuidanceFile(path)) return undefined;

			const rel = relative(ctx.cwd, path) || path;
			let current = "";
			try {
				current = await readFile(path, "utf-8");
			} catch {
				// New/nonexistent file being "edited" — the built-in edit tool will
				// surface the real error. Nothing to project; do not block.
				return undefined;
			}
			const projected = applyEdits(current, edits);
			if (projected === current) return undefined; // no-op projection

			const report = await scanContent(projected, rel);
			if (!report.passed) {
				if (ctx.hasUI) {
					ctx.ui.notify(`Guidance guard blocked edit to ${rel}`, "warning");
				}
				return {
					block: true,
					reason:
						`Refusing to edit guidance file ${rel}: the projected result would ` +
						`introduce context-health failures. Adjust the edit and retry.\n` +
						summarizeFailures(report.failures),
				};
			}
			return undefined;
		}

		return undefined;
	});
}
