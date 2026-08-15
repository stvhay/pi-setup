import { randomUUID } from "node:crypto";
import { chmod, link, lstat, mkdir, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";

const INVOCATION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

async function privateDirectory(path: string): Promise<void> {
  await mkdir(path, { recursive: true, mode: 0o700 });
  const info = await lstat(path);
  if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("runtime artifact path is not a private directory");
  await chmod(path, 0o700);
}

export async function persistDelegatedResult(root: string, payload: {
  invocationId: string;
  parentSessionId: string | null;
  childSessionId?: string | null;
  childIndex: number;
  executionOutcome: "succeeded" | "failed" | "unavailable";
  outputContract: "inline" | "artifact" | "status-only" | "pass-no-findings" | "unknown";
  exitCode: number;
  model: string | null;
  finalOutput: string | null;
  error: string | null;
}): Promise<string> {
  if (!INVOCATION_ID.test(payload.invocationId) || !Number.isSafeInteger(payload.childIndex) || payload.childIndex < 0) {
    throw new Error("invalid delegated artifact identity");
  }

  await privateDirectory(root);
  const directory = join(root, payload.invocationId);
  await privateDirectory(directory);
  const filename = `child-${payload.childIndex}.json`;
  const target = join(directory, filename);
  const temporary = join(directory, `.${filename}.${randomUUID()}.tmp`);
  try {
    await writeFile(temporary, `${JSON.stringify({ schemaVersion: 1, ...payload }, null, 2)}\n`, {
      encoding: "utf8",
      flag: "wx",
      mode: 0o600,
    });
    try {
      await link(temporary, target);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
      const existing = await lstat(target);
      if (existing.isSymbolicLink() || !existing.isFile()) throw error;
    }
    await chmod(target, 0o600);
  } finally {
    await unlink(temporary).catch(() => undefined);
  }

  return `runtime:delegated-results/${payload.invocationId}/${filename}`;
}
