import { createHash, randomUUID } from "node:crypto";
import {
  closeSync, constants, fstatSync, lstatSync, mkdirSync, openSync,
  readSync, realpathSync, renameSync, unlinkSync, writeFileSync,
} from "node:fs";
import { isIP } from "node:net";
import { join } from "node:path";

export type DownloadPolicy = "allow" | "ask" | "deny";
type Rule = { host: string; port: number | null; wildcard: boolean };
export type BrowserPolicy = {
  root: string;
  downloads: DownloadPolicy;
  allow: Rule[] | null;
  block: Rule[];
  fingerprint: string;
  configured: boolean;
};
export type Decision = { allowed: boolean; reason?: string };
export type RequestDetails = { resourceType?: string; resolvedFrom?: string };
const FILES = ["downloads", "net-allowlist", "net-blocklist"] as const;
const MAX_BYTES = 64 * 1024;
const hash = (text: string) => createHash("sha256").update(text).digest("hex");

function stat(path: string) {
  try { return lstatSync(path); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
}

function directory(path: string): void {
  const info = stat(path);
  if (info && (!info.isDirectory() || info.isSymbolicLink())) {
    throw new Error(`Browser policy directory must not be a symbolic link: ${path}`);
  }
}

function optionalFile(path: string): string | null {
  const info = stat(path);
  if (!info) return null;
  if (!info.isFile() || info.isSymbolicLink()) throw new Error(`Browser policy file must not be a symbolic link or special file: ${path}`);
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    if (!fstatSync(fd).isFile()) throw new Error(`Browser policy requires a regular file: ${path}`);
    const buffer = Buffer.alloc(MAX_BYTES + 1);
    let length = 0;
    while (length < buffer.length) {
      const count = readSync(fd, buffer, length, buffer.length - length, null);
      if (!count) break;
      length += count;
    }
    if (length > MAX_BYTES) throw new Error(`Browser policy file too large: ${path}`);
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer.subarray(0, length));
  } finally { closeSync(fd); }
}

function lines(text: string): string[] {
  return text.split(/\r?\n/).map(line => line.trim()).filter(line => line && !line.startsWith("#"));
}

function normalizeHost(value: string): string {
  let host = value.toLowerCase().replace(/\.$/, "");
  if (isIP(host) === 6) {
    host = new URL(`http://[${host}]/`).hostname.slice(1, -1);
    const mapped = /^::ffff:([\da-f]+):([\da-f]+)$/.exec(host);
    if (mapped) {
      const high = parseInt(mapped[1], 16), low = parseInt(mapped[2], 16);
      return [high >> 8, high & 255, low >> 8, low & 255].join(".");
    }
    return host;
  }
  if (host.length > 253 || !host.split(".").every(label => /^[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?$/.test(label))) {
    throw new Error(`Invalid browser policy host: ${JSON.stringify(value)}`);
  }
  // URL's legacy numeric IPv4 spellings must not disagree with literal rule matching.
  if (new URL(`http://${host}/`).hostname !== host) throw new Error(`Ambiguous browser policy host: ${JSON.stringify(value)}`);
  return host;
}

function parseRule(value: string): Rule {
  const match = /^(\*\.)?(?:\[([\da-fA-F:.]+)\]|([^:\s]+))(?::([0-9]+))?$/.exec(value);
  if (!match || (match[2] && isIP(match[2]) !== 6)) throw new Error(`Invalid browser policy rule: ${JSON.stringify(value)}`);
  const host = normalizeHost(match[2] || match[3]);
  const port = match[4] === undefined ? null : Number(match[4]);
  if (port !== null && (!Number.isInteger(port) || port < 1 || port > 65535)) throw new Error(`Invalid browser policy port: ${JSON.stringify(value)}`);
  if (match[1] && isIP(host)) throw new Error("Browser policy wildcard requires a DNS host");
  return { host, port, wildcard: Boolean(match[1]) };
}

export function readPolicy(cwd: string, override?: string): BrowserPolicy {
  const root = realpathSync(cwd);
  const dir = join(root, ".perms");
  directory(dir);
  const texts = FILES.map(name => optionalFile(join(dir, name)));
  const projectDownload = texts[0] === null ? "allow" : lines(texts[0]).join("\n");
  if (!["allow", "ask", "deny"].includes(projectDownload)) throw new Error("Browser downloads policy must be allow, ask, or deny");
  const downloads = override?.trim() || projectDownload;
  if (!["allow", "ask", "deny"].includes(downloads)) throw new Error("Browser downloads override must be allow, ask, or deny");
  return {
    root, downloads: downloads as DownloadPolicy,
    allow: texts[1] === null ? null : lines(texts[1]).map(parseRule),
    block: texts[2] === null ? [] : lines(texts[2]).map(parseRule),
    fingerprint: hash(JSON.stringify({ texts, downloads })),
    configured: texts.some(text => text !== null),
  };
}

function matches(rule: Rule, host: string, port: number): boolean {
  return (rule.port === null || rule.port === port) &&
    (rule.wildcard ? host.endsWith(`.${rule.host}`) : host === rule.host);
}

export function networkDecision(policy: BrowserPolicy, url: string, details: RequestDetails = {}): Decision {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:", "ws:", "wss:"].includes(parsed.protocol)) return { allowed: false, reason: "Non-network URL" };
    const host = normalizeHost(parsed.hostname.replace(/^\[|\]$/g, ""));
    const port = Number(parsed.port || (["https:", "wss:"].includes(parsed.protocol) ? 443 : 80));
    let source = host;
    if (details.resolvedFrom !== undefined) {
      if (details.resourceType !== "transport-address" || !isIP(host)) throw new Error("Invalid resolved-address attribution");
      source = normalizeHost(details.resolvedFrom);
    }
    if (policy.block.some(rule => matches(rule, host, port) || matches(rule, source, port))) {
      return { allowed: false, reason: "Destination blocked by .perms/net-blocklist" };
    }
    if (policy.allow !== null && !policy.allow.some(rule => matches(rule, source, port))) {
      return { allowed: false, reason: "Destination not in .perms/net-allowlist" };
    }
    return { allowed: true };
  } catch {
    return { allowed: false, reason: "Invalid destination or attribution for browser policy" };
  }
}

function receiptPath(policy: BrowserPolicy, receipts: string): string {
  directory(receipts);
  return join(receipts, `${hash(policy.root)}.json`);
}

export function approvalMatches(policy: BrowserPolicy, receipts: string): boolean {
  const text = optionalFile(receiptPath(policy, receipts));
  if (text === null) return !policy.configured;
  try {
    const record = JSON.parse(text);
    if (record.schemaVersion !== 1 || record.root !== policy.root || !/^[a-f0-9]{64}$/.test(record.fingerprint)) throw new Error();
    return record.fingerprint === policy.fingerprint;
  } catch { throw new Error("Invalid browser permission receipt; inspect host runtime state before approving again"); }
}

export function saveApproval(policy: BrowserPolicy, receipts: string): string {
  directory(receipts);
  mkdirSync(receipts, { recursive: true, mode: 0o700 });
  const target = receiptPath(policy, receipts);
  optionalFile(target);
  const temp = join(receipts, `.${randomUUID()}.tmp`);
  try {
    writeFileSync(temp, JSON.stringify({ schemaVersion: 1, root: policy.root, fingerprint: policy.fingerprint }) + "\n", { mode: 0o600, flag: "wx" });
    renameSync(temp, target);
  } finally {
    if (stat(temp)) unlinkSync(temp);
  }
  return target;
}

export function policyPreview(policy: BrowserPolicy): string {
  const format = (rule: Rule) => `${rule.wildcard ? "*." : ""}${isIP(rule.host) === 6 ? `[${rule.host}]` : rule.host}${rule.port === null ? "" : `:${rule.port}`}`;
  return [
    `Project: ${policy.root}`, `Downloads: ${policy.downloads}`,
    `Allowlist: ${policy.allow === null ? "unrestricted" : JSON.stringify(policy.allow.map(format))}`,
    `Blocklist: ${JSON.stringify(policy.block.map(format))}`,
    `Fingerprint: ${policy.fingerprint}`,
  ].join("\n");
}

export const UPSTREAM_DOWNLOAD_GUIDANCE = "- Remote files require explicit user approval and the host's approval-gated download surface; never enable downloads in an ordinary run.";
export function downloadGuidance(mode: DownloadPolicy): string {
  if (mode === "allow") return "- Browser downloads policy: allow. Downloads needed for the authorized task may use browser or browser_download without another confirmation. Download permission does not authorize executing files or expanding the task.";
  if (mode === "ask") return "- Browser downloads policy: ask. Use browser_download for remote file saves; its host UI obtains approval for each step. Do not ask for duplicate chat or Beads approval for the same download. Never enable downloads in an ordinary browser run.";
  return "- Browser downloads policy: deny. Downloads are disabled by host policy; do not try another tool to bypass this restriction.";
}
