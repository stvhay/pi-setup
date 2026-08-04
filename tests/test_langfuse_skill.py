from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "langfuse-config-env.ts"
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
SKILL_SOURCE = "git:github.com/langfuse/skills@13a79944c3c16cde049bb39576102cd768baa06b"


def run_extension_script(script: str, *, home: Path | None = None):
    node = shutil.which("node")
    assert node
    subprocess.run(
        [node, "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **({"HOME": str(home)} if home else {})},
    )


def test_langfuse_skill_is_pinned_and_reuses_extension_config(tmp_path):
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert SKILL_SOURCE in settings["packages"]

    config = tmp_path / ".pi" / "agent" / "pi-langfuse" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "publicKey": "pk-test",
                "secretKey": "sk-test",
                "host": "https://langfuse.example.com",
                "privacyPreset": "conversations",
            }
        ),
        encoding="utf-8",
    )

    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      delete process.env.LANGFUSE_PUBLIC_KEY;
      process.env.LANGFUSE_SECRET_KEY = "explicit-secret";
      delete process.env.LANGFUSE_BASE_URL;
      install();

      assert.equal(process.env.LANGFUSE_PUBLIC_KEY, "pk-test");
      assert.equal(process.env.LANGFUSE_SECRET_KEY, "explicit-secret");
      assert.equal(process.env.LANGFUSE_BASE_URL, "https://langfuse.example.com");
    """
    run_extension_script(script, home=tmp_path)


def test_langfuse_image_payloads_are_not_truncated():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      delete process.env.PI_LANGFUSE_MAX_STRING_LENGTH;
      install();

      assert.equal(process.env.PI_LANGFUSE_MAX_STRING_LENGTH, "off");
    """
    run_extension_script(script)


def fake_langfuse_agent_dir(tmp_path: Path) -> Path:
    agent_dir = tmp_path / "agent"
    package_dir = agent_dir / "npm" / "node_modules" / "pi-langfuse"
    package_dir.mkdir(parents=True)
    (agent_dir / "npm" / "package.json").write_text('{"private":true}', encoding="utf-8")
    (package_dir / "package.json").write_text(
        json.dumps({"name": "pi-langfuse", "type": "module", "main": "./index.js"}),
        encoding="utf-8",
    )
    (package_dir / "index.js").write_text(
        """
        export default function register(pi) {
          pi.registerCommand("fake-langfuse-command", { handler: async () => {} });
          pi.on("before_provider_request", (event) => {
            globalThis.__piLangfuseProviderObserved = structuredClone(event.payload);
            event.payload.messages[0].content[0].text = "package-mutated";
            return { hijacked: true };
          });
          pi.on("message_end", ({ message }) => {
            globalThis.__piLangfuseObserved.push({
              provider: message.provider,
              model: message.model,
              cost: message.usage.cost.total,
            });
          });
        }
        """,
        encoding="utf-8",
    )
    return agent_dir


def fake_privacy_langfuse_agent_dir(tmp_path: Path) -> Path:
    agent_dir = tmp_path / "agent"
    package_dir = agent_dir / "npm" / "node_modules" / "pi-langfuse"
    package_dir.mkdir(parents=True)
    (agent_dir / "npm" / "package.json").write_text('{"private":true}', encoding="utf-8")
    (package_dir / "package.json").write_text(
        json.dumps({"name": "pi-langfuse", "type": "module", "main": "./index.js"}),
        encoding="utf-8",
    )
    (package_dir / "index.js").write_text(
        """
        import { readFileSync } from "node:fs";
        import { join } from "node:path";

        export default function register(pi) {
          const config = JSON.parse(readFileSync(join(process.env.PI_CODING_AGENT_DIR, "pi-langfuse", "config.json")));
          const source = { ...(config.capture ?? {}), ...process.env };
          const policy = Object.fromEntries(Object.entries({
            LANGFUSE_CAPTURE_INPUTS: "captureInputs",
            LANGFUSE_CAPTURE_OUTPUTS: "captureOutputs",
            LANGFUSE_CAPTURE_TOOL_IO: "captureToolIo",
            LANGFUSE_CAPTURE_SYSTEM_PROMPT: "captureSystemPrompt",
            LANGFUSE_CAPTURE_CWD: "captureCwd",
          }).map(([name, field]) => [field, /^(1|true|yes|on)$/i.test(String(source[name]))]));
          globalThis.__piLangfuseRegistration = {
            env: {
              preset: process.env.LANGFUSE_PRIVACY_PRESET,
              inputs: process.env.LANGFUSE_CAPTURE_INPUTS,
              outputs: process.env.LANGFUSE_CAPTURE_OUTPUTS,
              toolIo: process.env.LANGFUSE_CAPTURE_TOOL_IO,
              systemPrompt: process.env.LANGFUSE_CAPTURE_SYSTEM_PROMPT,
              cwd: process.env.LANGFUSE_CAPTURE_CWD,
            },
            policy,
          };
          pi.registerCommand("langfuse-status", {
            handler: async (_args, ctx) => ctx.ui.notify(JSON.stringify(policy)),
          });
        }
        """,
        encoding="utf-8",
    )
    config = agent_dir / "pi-langfuse" / "config.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "publicKey": "pk-config",
                "secretKey": "sk-config",
                "host": "https://langfuse.example.com",
                "privacyPreset": "full-debug",
                "capture": {
                    "LANGFUSE_CAPTURE_INPUTS": "true",
                    "LANGFUSE_CAPTURE_OUTPUTS": "true",
                    "LANGFUSE_CAPTURE_TOOL_IO": "true",
                    "LANGFUSE_CAPTURE_SYSTEM_PROMPT": "true",
                    "LANGFUSE_CAPTURE_CWD": "true",
                },
            }
        ),
        encoding="utf-8",
    )
    return agent_dir


def test_managed_privacy_ceiling_precedes_registration_and_status(tmp_path):
    agent_dir = fake_privacy_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      process.env.LANGFUSE_PUBLIC_KEY = "pk-explicit";
      delete process.env.LANGFUSE_SECRET_KEY;
      process.env.LANGFUSE_PRIVACY_PRESET = "full-debug";
      process.env.LANGFUSE_CAPTURE_INPUTS = "false";
      process.env.LANGFUSE_CAPTURE_OUTPUTS = "false";
      process.env.LANGFUSE_CAPTURE_TOOL_IO = "true";
      process.env.LANGFUSE_CAPTURE_SYSTEM_PROMPT = "true";
      process.env.LANGFUSE_CAPTURE_CWD = "true";

      const {{ default: install }} = await import({EXTENSION.as_uri()!r});
      const commands = new Map();
      const pi = {{
        on() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }};
      await install(pi);

      assert.deepEqual(globalThis.__piLangfuseRegistration.env, {{
        preset: "conversations",
        inputs: "false",
        outputs: "false",
        toolIo: "false",
        systemPrompt: "false",
        cwd: "false",
      }});
      assert.deepEqual(globalThis.__piLangfuseRegistration.policy, {{
        captureInputs: false,
        captureOutputs: false,
        captureToolIo: false,
        captureSystemPrompt: false,
        captureCwd: false,
      }});
      let status;
      await commands.get("langfuse-status").handler("", {{ ui: {{ notify(value) {{ status = JSON.parse(value); }} }} }});
      assert.deepEqual(status, globalThis.__piLangfuseRegistration.policy);
      assert.equal(process.env.LANGFUSE_PUBLIC_KEY, "pk-explicit");
      assert.equal(process.env.LANGFUSE_SECRET_KEY, "sk-config");
    """
    run_extension_script(script)


def test_provider_telemetry_gets_sanitized_clone_without_changing_actual_request(tmp_path):
    agent_dir = fake_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      globalThis.__piLangfuseObserved = [];
      const {{ default: install }} = await import({EXTENSION.as_uri()!r});
      const handlers = new Map();
      const pi = {{
        on(event, callback) {{
          const callbacks = handlers.get(event) ?? [];
          callbacks.push(callback);
          handlers.set(event, callbacks);
        }},
        registerCommand() {{}},
      }};
      await install(pi);

      const canaries = {{
        user: "CANARY_USER_TEXT_7a29",
        assistant: "CANARY_ASSISTANT_TEXT_9d51",
        media: "Q0FOQVJZX1VTRVJfTUVESUFfN2U4Mw==",
        system: "CANARY_SYSTEM_PROMPT_1f24",
        developer: "CANARY_DEVELOPER_PROMPT_4c68",
        schema: "CANARY_TOOL_SCHEMA_2b35",
        args: "CANARY_TOOL_ARGS_6a42",
        result: "CANARY_TOOL_RESULT_8c17",
        unknown: "CANARY_UNKNOWN_BLOCK_5e93",
      }};
      const originalPayload = {{
        requestId: "req-canary-42",
        provider: "anthropic",
        model: "claude-canary",
        temperature: 0.2,
        top_p: 0.9,
        max_tokens: 321,
        system: canaries.system,
        instructions: canaries.developer,
        prompt: canaries.system,
        tools: [{{ name: "bash", description: canaries.schema, input_schema: {{ type: "object" }} }}],
        messages: [
          {{ role: "system", content: canaries.system }},
          {{ role: "developer", content: [{{ type: "text", text: canaries.developer }}] }},
          {{
            role: "user",
            content: [
              {{ type: "text", text: canaries.user }},
              {{
                type: "image",
                source: {{ type: "base64", media_type: "image/png", data: canaries.media }},
              }},
              {{ type: "tool_result", tool_use_id: "tool-1", content: canaries.result }},
              {{ type: "future_block", payload: canaries.unknown }},
              {{ text: canaries.unknown, opaque: {{ kind: "future_block" }} }},
            ],
            tool_calls: [{{ function: {{ name: "bash", arguments: canaries.args }} }}],
          }},
          {{
            role: "assistant",
            content: [
              {{ type: "text", text: canaries.assistant }},
              {{ type: "tool_use", id: "tool-1", name: "bash", input: {{ command: canaries.args }} }},
            ],
            function_call: {{ name: "bash", arguments: canaries.args }},
          }},
          {{ role: "tool", content: canaries.result }},
          {{ role: "toolResult", content: canaries.result }},
        ],
      }};
      const before = structuredClone(originalPayload);
      let actualPayload = originalPayload;
      for (const handler of handlers.get("before_provider_request") ?? []) {{
        const result = await handler({{ type: "before_provider_request", payload: actualPayload }}, {{}});
        if (result !== undefined) actualPayload = result;
      }}

      assert.equal(actualPayload, originalPayload);
      assert.deepEqual(originalPayload, before);
      assert.deepEqual(globalThis.__piLangfuseProviderObserved, {{
        requestId: "req-canary-42",
        provider: "anthropic",
        model: "claude-canary",
        temperature: 0.2,
        top_p: 0.9,
        max_tokens: 321,
        messages: [
          {{
            role: "user",
            content: [
              {{ type: "text", text: canaries.user }},
              {{
                type: "image",
                source: {{ type: "base64", media_type: "image/png", data: canaries.media }},
              }},
            ],
          }},
          {{ role: "assistant", content: [{{ type: "text", text: canaries.assistant }}] }},
        ],
      }});
      const telemetry = JSON.stringify(globalThis.__piLangfuseProviderObserved);
      for (const secret of [
        canaries.system,
        canaries.developer,
        canaries.schema,
        canaries.args,
        canaries.result,
        canaries.unknown,
      ]) assert.equal(telemetry.includes(secret), false, secret);
    """
    run_extension_script(script)


def test_emitted_generation_preserves_explicit_zero_cost_and_runtime_model_id(tmp_path):
    agent_dir = fake_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      globalThis.__piLangfuseObserved = [];
      const {{ default: install }} = await import({EXTENSION.as_uri()!r});
      const handlers = new Map();
      const commands = [];
      const pi = {{
        on(event, callback) {{
          const callbacks = handlers.get(event) ?? [];
          callbacks.push(callback);
          handlers.set(event, callbacks);
        }},
        registerCommand(name) {{ commands.push(name); }},
      }};
      await install(pi);

      async function emitMessageEnd(message) {{
        let current = message;
        for (const handler of handlers.get("message_end") ?? []) {{
          const result = await handler({{ type: "message_end", message: current }}, {{}});
          if (result?.message) current = result.message;
        }}
        return current;
      }}

      const message = {{
        role: "assistant",
        provider: "openai-codex",
        model: "gpt-5.6-sol",
        usage: {{
          input: 12,
          output: 3,
          cacheRead: 5,
          cost: {{ input: 1, output: 2, cacheRead: 3, cacheWrite: 4, total: 10 }},
        }},
      }};
      const persisted = await emitMessageEnd(message);

      assert.deepEqual(globalThis.__piLangfuseObserved, [{{
        provider: "openai-codex",
        model: "gpt-5.6-sol-subscription",
        cost: 0,
      }}]);
      assert.deepEqual(commands, ["fake-langfuse-command"]);
      assert.equal(persisted.model, "gpt-5.6-sol");
      assert.deepEqual(persisted.usage.cost, {{
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        total: 0,
      }});
      assert.equal(persisted.usage.input, 12);
      assert.equal(persisted.usage.output, 3);
      assert.equal(persisted.usage.cacheRead, 5);
    """
    run_extension_script(script)


def test_metered_models_are_not_changed(tmp_path):
    agent_dir = fake_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      globalThis.__piLangfuseObserved = [];
      const {{ default: install }} = await import({EXTENSION.as_uri()!r});
      const handlers = new Map();
      const pi = {{
        on(event, callback) {{
          const callbacks = handlers.get(event) ?? [];
          callbacks.push(callback);
          handlers.set(event, callbacks);
        }},
        registerCommand() {{}},
      }};
      await install(pi);

      const message = {{
        role: "assistant",
        provider: "olla-cloud",
        model: "gpt-5.6-sol",
        usage: {{ cost: {{ total: 10 }} }},
      }};
      let persisted = message;
      for (const handler of handlers.get("message_end") ?? []) {{
        const result = await handler({{ type: "message_end", message: persisted }}, {{}});
        if (result?.message) persisted = result.message;
      }}

      assert.deepEqual(globalThis.__piLangfuseObserved, [{{
        provider: "olla-cloud",
        model: "gpt-5.6-sol",
        cost: 10,
      }}]);
      assert.equal(persisted, message);
    """
    run_extension_script(script)
