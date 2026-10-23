import { createHash } from "node:crypto";
import { lstatSync, readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

const PREFIX = "../runtime/pi-langfuse/releases/";
const HASH = /^[a-f0-9]{64}$/;
const sha256 = (value: string | Buffer) => createHash("sha256").update(value).digest("hex");

type Hashes = Record<string, string>;
function hashes(value: unknown): Hashes {
  if (!value || typeof value !== "object" || Array.isArray(value) || !Object.keys(value).length) {
    throw new Error("invalid release inventory");
  }
  for (const [path, hash] of Object.entries(value)) {
    if (path.includes("\\") || path.includes("\0") || path.split("/").some(part => !part || part === "." || part === "..") ||
        typeof hash !== "string" || !HASH.test(hash)) throw new Error("invalid release entry");
  }
  return value as Hashes;
}

function assertNoSymlink(path: string): void {
  for (let current = path; ; current = dirname(current)) {
    if (lstatSync(current).isSymbolicLink()) throw new Error("symlinked release path");
    if (dirname(current) === current) break;
  }
}

function inventory(root: string, prefix = ""): Hashes {
  const result: Hashes = Object.create(null);
  for (const name of readdirSync(resolve(root, prefix)).sort()) {
    const key = prefix ? `${prefix}/${name}` : name;
    const path = resolve(root, key);
    const stat = lstatSync(path);
    if (stat.isSymbolicLink()) throw new Error("symlinked release file");
    if (stat.isDirectory()) Object.assign(result, inventory(root, key));
    else if (stat.isFile()) result[key] = sha256(readFileSync(path));
    else throw new Error("nonregular release file");
  }
  return result;
}

/** Verify before either import. Settings choose one immutable release; no npm fallback. */
export function resolveLangfuseRuntime(agentDir: string): { entry: string; quality: string } {
  const settings = JSON.parse(readFileSync(resolve(agentDir, "settings.json"), "utf8"));
  const candidates = (settings.packages as unknown[]).filter(item => {
    const source = typeof item === "string" ? item : (item as { source?: unknown })?.source;
    return typeof source === "string" && (source.startsWith(PREFIX) || source.startsWith("npm:pi-langfuse"));
  });
  if (candidates.length !== 1) throw new Error("one isolated Langfuse release required");
  const candidate = candidates[0] as { source?: string; extensions?: unknown[] };
  const id = candidate.source?.slice(PREFIX.length);
  if (!candidate.source?.startsWith(PREFIX) || !id || !HASH.test(id) || !Array.isArray(candidate.extensions) || candidate.extensions.length) {
    throw new Error("Langfuse package must disable automatic extension registration");
  }
  const release = resolve(agentDir, candidate.source);
  assertNoSymlink(release);
  const raw = readFileSync(resolve(release, "release.json"));
  const proof = JSON.parse(raw.toString("utf8"));
  const payload = { inputs: hashes(proof.inputs), files: hashes(proof.files), dependencies: hashes(proof.dependencies) };
  if (proof.schemaVersion !== 1 || proof.id !== id || sha256(JSON.stringify(payload)) !== id) {
    throw new Error("release identity mismatch");
  }
  if (Object.keys(payload.files).some(path => path === "release.json" || path === "node_modules" || path.startsWith("node_modules/"))) {
    throw new Error("reserved release entry");
  }
  const expected = { ...payload.files, "release.json": sha256(raw),
    ...Object.fromEntries(Object.entries(payload.dependencies).map(([path, hash]) => [`node_modules/${path}`, hash])) };
  const actual = inventory(release);
  if (Object.keys(actual).length !== Object.keys(expected).length || Object.entries(expected).some(([path, hash]) => actual[path] !== hash)) {
    throw new Error("release file mismatch");
  }
  if (!payload.files["index.js"] || !payload.files["src/quality.js"]) throw new Error("missing runtime entrypoint");
  return { entry: resolve(release, "index.js"), quality: resolve(release, "src/quality.js") };
}
