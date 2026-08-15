import { spawn } from "node:child_process";
import { join } from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

const AGNT_BIN = join(getAgentDir(), "bin", "agnt");
const MAX_BUFFER = 8 * 1024 * 1024;

export function runAgntJson(
	args: string[],
	cwd: string,
	signal?: AbortSignal,
	parseErrorLabel = "agnt",
	input?: string,
	privateInput?: string,
): Promise<Record<string, unknown>> {
	return new Promise((resolve, reject) => {
		const proc = spawn(AGNT_BIN, args, {
			cwd,
			env: privateInput === undefined
				? process.env
				: { ...process.env, AGNT_HUMAN_UI_RESOLVER_FD: "3" },
			stdio: ["pipe", "pipe", "pipe", privateInput === undefined ? "ignore" : "pipe"],
			signal,
		});
		let stdout = "";
		let stderr = "";
		let overflow = false;
		const append = (current: string, chunk: Buffer): string => {
			const next = current + chunk.toString("utf-8");
			if (Buffer.byteLength(next) > MAX_BUFFER) {
				overflow = true;
				proc.kill();
			}
			return next;
		};
		proc.stdout.on("data", (chunk: Buffer) => { stdout = append(stdout, chunk); });
		proc.stderr.on("data", (chunk: Buffer) => { stderr = append(stderr, chunk); });
		proc.on("error", reject);
		proc.on("close", (code) => {
			if (overflow) {
				reject(new Error(`${parseErrorLabel} output exceeded ${MAX_BUFFER} bytes`));
				return;
			}
			if (code !== 0) {
				reject(new Error((stderr || stdout || `${parseErrorLabel} exited ${String(code)}`).trim()));
				return;
			}
			try {
				resolve(JSON.parse(stdout || "{}") as Record<string, unknown>);
			} catch (parseErr) {
				reject(new Error(`${parseErrorLabel} did not return JSON: ${(parseErr as Error).message}; output=${stdout}`));
			}
		});
		proc.stdin.end(input);
		if (privateInput !== undefined) proc.stdio[3]?.end(privateInput);
	});
}
