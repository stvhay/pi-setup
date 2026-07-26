import { execFile } from "node:child_process";
import { join } from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

const AGNT_BIN = join(getAgentDir(), "bin", "agnt");

export function runAgntJson(
	args: string[],
	cwd: string,
	signal?: AbortSignal,
	parseErrorLabel = "agnt",
): Promise<Record<string, unknown>> {
	return new Promise((resolve, reject) => {
		const proc = execFile(AGNT_BIN, args, { cwd, encoding: "utf-8", maxBuffer: 8 * 1024 * 1024, signal }, (err, stdout, stderr) => {
			if (err) {
				reject(new Error((stderr || stdout || err.message).trim()));
				return;
			}
			try {
				resolve(JSON.parse(stdout || "{}") as Record<string, unknown>);
			} catch (parseErr) {
				reject(new Error(`${parseErrorLabel} did not return JSON: ${(parseErr as Error).message}; output=${stdout}`));
			}
		});
		if (signal) signal.addEventListener("abort", () => proc.kill(), { once: true });
	});
}
