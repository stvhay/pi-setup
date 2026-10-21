import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, symlink, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

// Copied into the integrity-checked projected package by the package proof.
test("managed wrapper composes actual package privacy, quality and subscription contracts", async () => {
  const wrapper = process.env.PI_LANGFUSE_MANAGED_WRAPPER;
  assert.ok(wrapper, "package proof must supply the tracked wrapper path");
  const root = await mkdtemp(join(tmpdir(), "langfuse-wrapper-proof-"));
  const agent = join(root, "agent");
  const originalEnv = { ...process.env };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("live network forbidden in wrapper proof"); };
  try {
    await mkdir(join(agent, "npm", "node_modules"), { recursive: true });
    await mkdir(join(agent, "pi-langfuse"), { recursive: true });
    await writeFile(join(agent, "npm", "package.json"), '{"private":true}');
    await symlink(fileURLToPath(new URL("../", import.meta.url)), join(agent, "npm", "node_modules", "pi-langfuse"));
    await writeFile(join(agent, "pi-langfuse", "config.json"), JSON.stringify({
      publicKey: "pk-test", secretKey: "test-only", host: "https://example.invalid",
      privacyPreset: "full-debug",
      capture: {
        LANGFUSE_CAPTURE_PATHS: "true", LANGFUSE_CAPTURE_TOOL_IO: "true",
        LANGFUSE_CAPTURE_TOOL_IO_BYTES: "true", LANGFUSE_CAPTURE_SYSTEM_PROMPT: "true", LANGFUSE_CAPTURE_CWD: "true",
      },
    }));
    process.env.PI_CODING_AGENT_DIR = agent;
    for (const key of ["PATHS", "TOOL_IO", "TOOL_IO_BYTES", "SYSTEM_PROMPT", "CWD"]) {
      process.env[`LANGFUSE_CAPTURE_${key}`] = "true";
    }
    process.env.LANGFUSE_CAPTURE_INPUTS = "false";
    process.env.LANGFUSE_CAPTURE_OUTPUTS = "false";
    const handlers = new Map<string, Function[]>();
    const events = new Map<string, Function>();
    const commands = new Map<string, unknown>();
    const pi = {
      on(name: string, fn: Function) {
        handlers.set(name, [...(handlers.get(name) ?? []), fn]);
      },
      registerCommand(name: string, command: unknown) { commands.set(name, command); },
      events: { on(name: string, fn: Function) { events.set(name, fn); } },
    };
    const { default: install } = await import(pathToFileURL(resolve(wrapper)).href);
    await install(pi);
    assert.ok(commands.has("langfuse-status"), "actual package registered");
    const { state } = await import("../src/state.ts");
    assert.equal(state.config?.capturePolicy?.capturePaths, false);
    for (const key of ["captureInputs", "captureOutputs", "captureToolIo", "captureToolIoBytes", "captureSystemPrompt", "captureCwd"]) {
      assert.equal((state.config?.capturePolicy as any)?.[key], false, key);
    }
    const { redactValue } = await import("../src/redaction.ts");
    assert.match(String(redactValue("/Users/private/repository")), /PATH_HASH/);

    let captured: any;
    let flushed = 0;
    const { __setRuntimeForTest } = await import("../src/langfuse.ts");
    __setRuntimeForTest({
      startObservation(_name: string, body: unknown) {
        captured = body;
        return { id: "obs", traceId: "trace", update() { return this; }, end() {} };
      },
      propagateAttributes(_attrs: unknown, fn: Function) { return fn(); },
      tracerProvider: { forceFlush: async () => { flushed++; } },
      scoreClient: {},
    } as any);
    let observe: Function | undefined;
    events.get("pi-setup:langfuse-projection-observe")?.((value: Function) => { observe = value; });
    assert.equal(typeof observe, "function");
    await observe!("proof", { input: "private input", output: "private output", metadata: { path: "/Users/private/repository" } }, { asType: "agent", flush: true });
    assert.equal(captured.input, undefined);
    assert.equal(captured.output, undefined);
    assert.doesNotMatch(JSON.stringify(captured), /private/);
    assert.equal(flushed, 1);
    __setRuntimeForTest(null);

    const observed: any[] = [];
    const chain = handlers.get("message_end")!;
    assert.equal(chain.length, 3, "alias, actual telemetry, restore handlers");
    chain.splice(2, 0, ({ message }: any) => { observed.push(message); });
    const original = { role: "assistant", provider: "openai-codex", model: "proof-model", content: [], usage: { cost: { total: 4 } } };
    let message: any = original;
    for (const fn of chain) {
      const result = await fn({ message }, {});
      if (result?.message) message = result.message;
    }
    assert.equal(observed[0].model, "proof-model-subscription");
    assert.equal(observed[0].usage.cost.total, 0);
    assert.equal(message.model, "proof-model");
    assert.equal(original.usage.cost.total, 4, "original message not mutated");
    const metered = { ...original, provider: "openrouter" };
    message = metered;
    for (const fn of chain) {
      const result = await fn({ message }, {});
      if (result?.message) message = result.message;
    }
    assert.equal(message, metered);
    assert.equal(observed[1].usage.cost.total, 4);
  } finally {
    globalThis.fetch = originalFetch;
    for (const key of Object.keys(process.env)) if (!(key in originalEnv)) delete process.env[key];
    Object.assign(process.env, originalEnv);
    await rm(root, { recursive: true, force: true });
  }
});
