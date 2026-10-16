import { getAgentDir, type ExtensionAPI, type ExtensionContext, type ToolDefinition } from "@earendil-works/pi-coding-agent";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import {
  approvalMatches, downloadGuidance, networkDecision, policyPreview, readPolicy, saveApproval,
  UPSTREAM_DOWNLOAD_GUIDANCE, type BrowserPolicy, type RequestDetails,
} from "./lib/browser-permissions.ts";

export default async function browserPermissions(pi: ExtensionAPI) {
  const agentDir = getAgentDir();
  const require = createRequire(resolve(agentDir, "npm", "package.json"));
  const load = (name: string) => import(pathToFileURL(require.resolve(name)).href);
  const [{ createPiExtension }, { NetworkPolicy }, { agentSystemPrompt }] = await Promise.all([
    load("betterwright/pi-extension"), load("betterwright/policy"), load("betterwright/prompt"),
  ]);
  if (agentSystemPrompt().split(UPSTREAM_DOWNLOAD_GUIDANCE).length !== 2) {
    throw new Error("Unsupported BetterWright download guidance contract; review browser-permissions adapter before updating");
  }

  const receipts = resolve(agentDir, "..", "runtime", "browser-permissions");
  let bound: BrowserPolicy | undefined;
  let initialized = false;
  let bindingError = "Browser policy is not initialized";
  let sessionCwd = "";
  let generation = 0;
  let reloadRequired = false;
  let stopping = false;
  let operationTail: Promise<unknown> = Promise.resolve();
  const current = (cwd: string) => readPolicy(cwd, process.env.BETTERWRIGHT_PI_DOWNLOAD_POLICY);
  const baseline = new NetworkPolicy();
  const browserOptions = {
    downloadPolicy: "deny",
    policy: new NetworkPolicy({ custom: (url: string, details: RequestDetails) => {
      try {
        const policy = assertCurrent(sessionCwd);
        const decision = baseline.check(url, details);
        return decision.allowed ? networkDecision(policy, url, details) : decision;
      } catch (error) {
        return { allowed: false, reason: String(error) };
      }
    } }),
  };

  function initialize(cwd: string): void {
    if (initialized) return;
    initialized = true;
    sessionCwd = cwd;
    try {
      const policy = current(cwd);
      if (!approvalMatches(policy, receipts)) throw new Error("Browser policy needs approval: run /browser-permissions approve");
      bound = policy;
      browserOptions.downloadPolicy = policy.downloads;
    } catch (error) { bindingError = String(error); }
  }

  function assertCurrent(cwd: string): BrowserPolicy {
    initialize(cwd);
    if (stopping) throw new Error("Browser policy session is shutting down");
    if (reloadRequired) throw new Error("Browser policy changed; /reload is required");
    if (!bound) throw new Error(`${bindingError}; /reload after approval`);
    const policy = current(cwd);
    if (policy.root !== bound.root || policy.fingerprint !== bound.fingerprint || !approvalMatches(policy, receipts)) {
      throw new Error("Browser policy changed or approval is missing; run /browser-permissions approve, then reload");
    }
    return bound;
  }

  function serialize<T>(ctx: ExtensionContext, operation: () => T | Promise<T>): Promise<T> {
    const enteredGeneration = generation;
    const result = operationTail.then(() => {
      if (generation !== enteredGeneration) throw new Error("Browser policy session changed while waiting");
      assertCurrent(ctx.cwd);
      return operation();
    });
    operationTail = result.catch(() => undefined);
    return result;
  }

  pi.on("session_start", (_event, ctx) => {
    generation++;
    stopping = false;
    sessionCwd = ctx.cwd;
    initialize(ctx.cwd);
  });
  pi.on("session_shutdown", () => {
    stopping = true;
    generation++;
  });

  const wrapped = new Proxy(pi, {
    get(target, property) {
      if (property === "registerTool") return (tool: ToolDefinition) => target.registerTool({
        ...tool,
        ...(tool.name === "browser_download" ? {
          description: tool.description.replace("This approval-gated variant may save a remote file.", "Downloads follow host policy: allow by default, ask prompts, deny blocks."),
        } : {}),
        async execute(...args: Parameters<typeof tool.execute>) {
          const ctx = args[4];
          return serialize(ctx, async () => {
            const startedGeneration = generation;
            const guardedContext = new Proxy(ctx, { get(context, key) {
              if (key !== "ui") return Reflect.get(context, key);
              return new Proxy(context.ui, { get(ui, method) {
                if (method !== "confirm") return Reflect.get(ui, method);
                return async (...params: Parameters<typeof ui.confirm>) => {
                  const approved = await ui.confirm(...params);
                  if (generation !== startedGeneration) throw new Error("Browser approval session changed");
                  assertCurrent(ctx.cwd);
                  return approved;
                };
              } });
            } });
            args[4] = guardedContext;
            return tool.execute(...args);
          });
        },
      });
      if (property === "registerCommand") return (name: string, command: Parameters<ExtensionAPI["registerCommand"]>[1]) => target.registerCommand(name, {
        ...command,
        async handler(args, ctx) {
          return serialize(ctx, () => command.handler(args, ctx));
        },
      });
      if (property === "on") return (name: string, handler: (...args: any[]) => any) => {
        if (name !== "before_agent_start") return target.on(name as any, handler);
        return target.on("before_agent_start", async (event, ctx) => {
          const result = await handler(event, ctx);
          let guidance: string;
          try { guidance = downloadGuidance(assertCurrent(ctx.cwd).downloads); }
          catch { guidance = "- Browser policy is unavailable or changed. Browser tools are blocked; ask the user to inspect /browser-permissions. Do not bypass restrictions using another tool."; }
          const prefix = String(event.systemPrompt || "");
          const suffix = String(result.systemPrompt).slice(prefix.length);
          if (!String(result.systemPrompt).startsWith(prefix) || suffix.split(UPSTREAM_DOWNLOAD_GUIDANCE).length !== 2) {
            reloadRequired = true;
            throw new Error("BetterWright browser prompt contract changed; browser tools blocked");
          }
          return { ...result, systemPrompt: prefix + suffix.replace(UPSTREAM_DOWNLOAD_GUIDANCE, guidance) };
        });
      };
      return Reflect.get(target, property);
    },
  });
  createPiExtension({ browserOptions })(wrapped);

  pi.registerCommand("browser-permissions", {
    description: "Show browser policy; approve saves this project's exact policy and reloads Pi",
    async handler(args, ctx) {
      const action = args.trim();
      if (action !== "" && action !== "approve") throw new Error("Usage: /browser-permissions [approve]");
      const policy = current(ctx.cwd);
      const matches = approvalMatches(policy, receipts);
      if (!action) {
        ctx.ui.notify(`${policyPreview(policy)}\nApproval: ${matches ? "current" : "required"}`, "info");
        return;
      }
      if (!ctx.hasUI) throw new Error("Browser policy approval requires an interactive human UI");
      const startedGeneration = generation;
      const approved = await ctx.ui.confirm("Approve project browser permissions?", [
        policyPreview(policy),
        "Scope: BetterWright browser only; shell, device access and other tools are unchanged.",
        "Allow downloads removes per-step confirmation, including ordinary browser calls. Network lists apply to intercepted redirects and subresources. Full transport/resolved-IP protection requires a locally launched browser; remote CDP does not provide it. Existing metadata protections remain.",
        "Save this policy for future sessions on this host. Reload closes current browser tabs; persistent logins remain. Already completed network effects cannot be undone.",
        "To reverse: edit .perms and approve again. Rejection leaves current approval unchanged; changed policy stays blocked.",
      ].join("\n\n"));
      if (!approved) return;
      const after = current(ctx.cwd);
      if (startedGeneration !== generation || after.root !== policy.root || after.fingerprint !== policy.fingerprint) {
        throw new Error("Browser policy or session changed during approval; nothing saved");
      }
      saveApproval(policy, receipts);
      reloadRequired = true;
      await ctx.reload();
    },
  });
}
