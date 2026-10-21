import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";
import { parseArgs } from "@earendil-works/pi-coding-agent";
import { redactOutputText } from "../zz-output-redaction.ts";

type Execve = NonNullable<typeof process.execve>;
type NonzeroExitHandler = (code: number) => string | undefined;

let replacementPending = false;

export interface ProcessReplacement {
  executable: string;
  execve: Execve;
  argv: string[];
  assertCheckout(source: string, target: string): void;
}

function continuationOptions(): { argv: string[]; cwdSensitive: boolean } {
  // Use Pi's parser: never mistake a prompt/option value for a restriction.
  // Rebuild run configuration, not old messages, attachments or session selectors.
  const parsed = parseArgs(process.argv.slice(2));
  if (parsed.diagnostics.some(item => item.type === "error")) {
    throw new Error("Current Pi launch options are invalid; no shutdown requested");
  }
  const args: string[] = [];
  const flags = { noTools: "--no-tools", noBuiltinTools: "--no-builtin-tools", noExtensions: "--no-extensions",
    noMcp: "--no-mcp", noSkills: "--no-skills", noPromptTemplates: "--no-prompt-templates", noThemes: "--no-themes",
    noContextFiles: "--no-context-files", offline: "--offline", verbose: "--verbose" } as const;
  for (const [key, flag] of Object.entries(flags)) if (parsed[key as keyof typeof flags]) args.push(flag);
  if (parsed.projectTrustOverride !== undefined) args.push(parsed.projectTrustOverride ? "--approve" : "--no-approve");
  const values = { provider: "--provider", model: "--model", apiKey: "--api-key", thinking: "--thinking",
    mode: "--mode", useTheme: "--use-theme", tuiMode: "--tui-mode" } as const;
  for (const [key, flag] of Object.entries(values)) {
    const value = parsed[key as keyof typeof values];
    if (value !== undefined) args.push(flag, value);
  }
  if (parsed.models) args.push("--models", parsed.models.join(","));
  if (parsed.tools) args.push("--tools", parsed.tools.join(","));
  if (parsed.excludeTools) args.push("--exclude-tools", parsed.excludeTools.join(","));
  const absolute = (path: string) => resolve(path.startsWith("~/") ? `${homedir()}/${path.slice(2)}` : path);
  for (const [paths, flag] of [[parsed.extensions, "--extension"], [parsed.skills, "--skill"],
    [parsed.promptTemplates, "--prompt-template"], [parsed.themes, "--theme"]] as const) {
    for (const path of paths ?? []) args.push(flag, path.startsWith("builtin:") ? path : absolute(path));
  }
  for (const [prompts, flag] of [[parsed.systemPrompt === undefined ? [] : [parsed.systemPrompt], "--system-prompt"],
    [parsed.appendSystemPrompt ?? [], "--append-system-prompt"]] as const) {
    // Pi distinguishes empty/literal/file tokens itself. These overrides are
    // same-checkout only; expanding or absolutizing changes their semantics.
    for (const prompt of prompts) args.push(flag, prompt);
  }
  for (const [name, value] of parsed.unknownFlags) args.push(value === true ? `--${name}` : `--${name}=${value}`);
  // Do not guess how arbitrary preload/extension options or prompt file/text
  // overrides rebind in another checkout. Same-checkout restart keeps them.
  const cwdSensitive = parsed.systemPrompt !== undefined || Boolean(parsed.appendSystemPrompt?.length)
    || parsed.unknownFlags.size > 0 || process.execArgv.length > 0 || Boolean(process.env.NODE_OPTIONS?.trim());
  return { argv: args, cwdSensitive };
}

export function requireProcessReplacement(command: string): ProcessReplacement {
  if (
    process.release.name !== "node" ||
    Number.parseInt(process.versions.node, 10) < 24 ||
    (process.platform !== "darwin" && process.platform !== "linux")
  ) {
    throw new Error(`${command} requires Node 24 on macOS or Linux; no shutdown requested`);
  }

  const execve = process.execve;
  if (typeof execve !== "function") {
    throw new Error(`${command} requires process.execve; no shutdown requested`);
  }
  const entrypoint = process.argv[1];
  if (!entrypoint) throw new Error(`${command} could not determine the current Pi entrypoint`);

  const options = continuationOptions();
  return {
    executable: process.execPath,
    execve,
    argv: [process.execPath, ...process.execArgv, entrypoint, ...options.argv],
    assertCheckout(source, target) {
      if (options.cwdSensitive && realpathSync(source) !== realpathSync(target)) {
        throw new Error("Cross-checkout continuation cannot rebind custom launch options; reconcile runtime setup before shutdown");
      }
    },
  };
}

export function requestProcessReplacement(
  replacement: ProcessReplacement,
  args: string[],
  shutdown: () => void,
  failureLabel: string,
  failureHint = "",
  onNonzeroExit?: NonzeroExitHandler,
): void {
  if (replacementPending) throw new Error(`${failureLabel} process replacement is already pending`);
  replacementPending = true;

  const reportFailure = (label: string, message: string, hint = ""): void => {
    const safeHint = redactOutputText(hint).slice(0, 1000);
    const safeMessage = redactOutputText(message).slice(0, 1000 - safeHint.length);
    console.error(`${label}: ${safeMessage}${safeHint}`);
  };
  const replaceOnExit = (code: number): void => {
    replacementPending = false;
    if (code !== 0) {
      reportFailure(
        `${failureLabel} cancelled`,
        `shutdown exited with code ${code}.`,
        onNonzeroExit?.(code) ?? failureHint,
      );
      return;
    }
    try {
      replacement.execve(replacement.executable, args, process.env);
    } catch (error) {
      process.exitCode = 1;
      const message = error instanceof Error ? error.message : String(error);
      reportFailure(`${failureLabel} failed`, message, failureHint);
    }
  };

  let listenerRegistered = false;
  try {
    process.once("exit", replaceOnExit);
    listenerRegistered = true;
    shutdown();
  } catch (error) {
    if (listenerRegistered) process.off("exit", replaceOnExit);
    replacementPending = false;
    throw error;
  }
}
