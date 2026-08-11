import { redactOutputText } from "../zz-output-redaction.ts";

type Execve = NonNullable<typeof process.execve>;
type NonzeroExitHandler = (code: number) => string | undefined;

let replacementPending = false;

export interface ProcessReplacement {
  executable: string;
  execve: Execve;
  argv: string[];
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

  return {
    executable: process.execPath,
    execve,
    argv: [process.execPath, ...process.execArgv, entrypoint],
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

  const reportFailure = (label: string, message: string): void => {
    console.error(`${label}: ${redactOutputText(message).slice(0, 1000)}`);
  };
  const replaceOnExit = (code: number): void => {
    replacementPending = false;
    if (code !== 0) {
      reportFailure(
        `${failureLabel} cancelled`,
        `shutdown exited with code ${code}.${onNonzeroExit?.(code) ?? failureHint}`,
      );
      return;
    }
    try {
      replacement.execve(replacement.executable, args, process.env);
    } catch (error) {
      process.exitCode = 1;
      const message = error instanceof Error ? error.message : String(error);
      reportFailure(`${failureLabel} failed`, `${message}${failureHint}`);
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
