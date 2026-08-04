from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


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


def fake_sanitizer_langfuse_agent_dir(tmp_path: Path) -> Path:
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
        function messagesFrom(event) {
          const payload = event.request ?? event.payload ?? event.body ?? event.providerPayload ?? event.messages ?? event;
          if (Array.isArray(payload)) return payload;
          return payload?.messages ?? payload?.input ?? payload?.contents ?? event.messages ?? (event.message ? [event.message] : []);
        }

        function mutateConversation(event) {
          for (const message of messagesFrom(event)) {
            if (!Array.isArray(message?.content)) continue;
            const text = message.content.find((block) => typeof block?.text === "string");
            if (text) text.text = "package-mutated";
            message.toolCalls = [{ name: "package-mutated" }];
          }
          event.packageOnlyMutation = true;
        }

        export default function register(pi) {
          pi.registerCommand("fake-sanitizer-command", { handler: async () => {} });
          pi.on("before_provider_request", (event) => {
            globalThis.__piLangfuseProviderObserved = structuredClone(event);
            mutateConversation(event);
            return { hijacked: true };
          });
          for (const eventName of ["message_update", "message_end", "turn_end", "agent_end"]) {
            pi.on(eventName, (event) => {
              globalThis.__piLangfuseConversationObserved[eventName] = structuredClone(event);
              mutateConversation(event);
              return { message: { role: "tool", content: "PACKAGE_REPLACEMENT_SECRET" } };
            });
          }
        }
        """,
        encoding="utf-8",
    )
    return agent_dir


def fake_all_paths_langfuse_agent_dir(tmp_path: Path) -> Path:
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
          for (const eventName of [
            "before_agent_start",
            "agent_start",
            "turn_start",
            "after_provider_response",
            "tool_execution_start",
            "tool_call",
            "tool_result",
            "tool_execution_end",
            "session_compact",
          ]) {
            pi.on(eventName, (event) => {
              globalThis.__piLangfuseAllPathsObserved[eventName] = structuredClone(event);
              event.packageMutation = "CANARY_PACKAGE_MUTATION";
              return { replacement: "CANARY_PACKAGE_REPLACEMENT" };
            });
          }
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


@pytest.mark.parametrize("alias", ["request", "payload", "body", "providerPayload", "messages"])
def test_provider_event_sanitizes_every_payload_alias_without_mutation(tmp_path, alias):
    agent_dir = fake_sanitizer_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      globalThis.__piLangfuseConversationObserved = {{}};
      const {{ default: install }} = await import({EXTENSION.as_uri()!r});
      const handlers = new Map();
      let localBefore;
      let localAfter;
      handlers.set("before_provider_request", [(event) => {{ localBefore = event; }}]);
      const pi = {{
        on(event, callback) {{
          const callbacks = handlers.get(event) ?? [];
          callbacks.push(callback);
          handlers.set(event, callbacks);
        }},
        registerCommand() {{}},
      }};
      await install(pi);
      handlers.get("before_provider_request").push((event) => {{ localAfter = event; }});

      const canaries = {{
        user: "CANARY_ALIAS_USER_7a29",
        assistant: "CANARY_ALIAS_ASSISTANT_9d51",
        media: "Q0FOQVJZX0FMSUFTX01FRElBXzdlODM=",
        system: "CANARY_ALIAS_SYSTEM_1f24",
        args: "CANARY_ALIAS_ARGS_6a42",
        result: "CANARY_ALIAS_RESULT_8c17",
        unknown: "CANARY_ALIAS_UNKNOWN_5e93",
      }};
      const messages = [
        {{ role: "system", content: canaries.system }},
        {{
          role: "user",
          content: [
            {{ type: "text", text: canaries.user }},
            {{ type: "image", source: {{ type: "base64", media_type: "image/png", data: canaries.media }} }},
            {{ type: "tool_result", content: canaries.result }},
            {{ type: "future_block", payload: canaries.unknown }},
          ],
          tool_calls: [{{ function: {{ arguments: canaries.args }} }}],
        }},
        {{
          role: "assistant",
          content: [
            {{ type: "text", text: canaries.assistant }},
            {{ type: "toolCall", arguments: canaries.args }},
          ],
          function_calls: [{{ arguments: canaries.args }}],
        }},
        {{ role: "tool", content: canaries.result }},
      ];
      const payload = {{
        requestId: "payload-request-42",
        provider: "anthropic",
        model: "claude-canary",
        temperature: 0.2,
        messages,
        tools: [{{ description: canaries.unknown }}],
        unknown: {{ secret: canaries.unknown }},
      }};
      payload.self = payload;
      const original = {{
        type: "before_provider_request",
        requestId: "event-request-42",
        provider: "anthropic",
        model: "claude-canary",
        url: "https://provider.invalid/v1/messages",
        method: "POST",
        unknown: {{ secret: canaries.unknown }},
      }};
      original.self = original;
      const alias = {json.dumps(alias)};
      original[alias] = alias === "messages" ? messages : payload;
      const before = structuredClone(original);

      for (const handler of handlers.get("before_provider_request") ?? []) {{
        await handler(original, {{}});
      }}

      assert.equal(localBefore, original);
      assert.equal(localAfter, original);
      assert.deepEqual(original, before);
      const observed = globalThis.__piLangfuseProviderObserved;
      assert.deepEqual(Object.keys(observed).sort(), [
        alias,
        "method",
        "model",
        "provider",
        "requestId",
        "type",
        "url",
      ].sort());
      assert.equal(observed.type, "before_provider_request");
      assert.equal(observed.requestId, "event-request-42");
      assert.equal(observed.provider, "anthropic");
      assert.equal(observed.model, "claude-canary");
      assert.equal(observed.url, "https://provider.invalid/v1/messages");
      assert.equal(observed.method, "POST");
      const sanitized = alias === "messages" ? observed.messages : observed[alias].messages;
      assert.deepEqual(sanitized, [
        {{
          role: "user",
          content: [
            {{ type: "text", text: canaries.user }},
            {{ type: "image", source: {{ type: "base64", media_type: "image/png", data: canaries.media }} }},
          ],
        }},
        {{ role: "assistant", content: [{{ type: "text", text: canaries.assistant }}] }},
      ]);
      if (alias !== "messages") {{
        assert.equal(observed[alias].requestId, "payload-request-42");
        assert.equal(observed[alias].temperature, 0.2);
        assert.equal(Object.hasOwn(observed[alias], "self"), false);
      }}
      const telemetry = JSON.stringify(observed);
      for (const secret of [canaries.system, canaries.args, canaries.result, canaries.unknown]) {{
        assert.equal(telemetry.includes(secret), false, secret);
      }}
    """
    run_extension_script(script)


def test_provider_event_uses_sanitized_payload_fallback_and_drops_nonobjects(tmp_path):
    agent_dir = fake_sanitizer_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      globalThis.__piLangfuseConversationObserved = {{}};
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

      const event = {{
        type: "before_provider_request",
        requestId: "fallback-request-42",
        provider: "google",
        model: "gemini-canary",
        input: [{{ role: "user", content: [{{ type: "text", text: "SAFE_FALLBACK_TEXT" }}] }}],
        unknown: {{ secret: "CANARY_FALLBACK_UNKNOWN" }},
      }};
      event.self = event;
      const before = structuredClone(event);
      for (const handler of handlers.get("before_provider_request") ?? []) await handler(event, {{}});

      assert.deepEqual(event, before);
      assert.deepEqual(globalThis.__piLangfuseProviderObserved, {{
        type: "before_provider_request",
        requestId: "fallback-request-42",
        provider: "google",
        model: "gemini-canary",
        payload: {{
          requestId: "fallback-request-42",
          provider: "google",
          model: "gemini-canary",
          input: [{{ role: "user", content: [{{ type: "text", text: "SAFE_FALLBACK_TEXT" }}] }}],
        }},
      }});

      const nonobject = {{
        type: "before_provider_request",
        requestId: "nonobject-request-42",
        request: "CANARY_RAW_NONOBJECT",
        unknown: "CANARY_RAW_UNKNOWN",
      }};
      for (const handler of handlers.get("before_provider_request") ?? []) await handler(nonobject, {{}});
      const observed = globalThis.__piLangfuseProviderObserved;
      assert.equal(observed.requestId, "nonobject-request-42");
      assert.notEqual(observed.request, nonobject.request);
      assert.equal(JSON.stringify(observed).includes("CANARY_RAW"), false);
      assert.equal(Object.hasOwn(observed, "unknown"), false);
    """
    run_extension_script(script)


@pytest.mark.parametrize("event_name", ["message_update", "message_end", "turn_end", "agent_end"])
def test_package_message_events_keep_safe_conversation_metadata_without_mutation(tmp_path, event_name):
    agent_dir = fake_sanitizer_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      globalThis.__piLangfuseConversationObserved = {{}};
      const {{ default: install }} = await import({EXTENSION.as_uri()!r});
      const handlers = new Map();
      let localBefore;
      let localAfter;
      const eventName = {json.dumps(event_name)};
      handlers.set(eventName, [(event) => {{ localBefore = event; }}]);
      const pi = {{
        on(event, callback) {{
          const callbacks = handlers.get(event) ?? [];
          callbacks.push(callback);
          handlers.set(event, callbacks);
        }},
        registerCommand() {{}},
      }};
      await install(pi);
      handlers.get(eventName).push((event) => {{ localAfter = event; }});

      const canaries = {{
        user: "CANARY_EVENT_USER_7a29",
        assistant: "CANARY_EVENT_ASSISTANT_9d51",
        media: "https://media.invalid/CANARY_EVENT_MEDIA_7e83",
        system: "CANARY_EVENT_SYSTEM_1f24",
        args: "CANARY_EVENT_ARGS_6a42",
        result: "CANARY_EVENT_RESULT_8c17",
        unknown: "CANARY_EVENT_UNKNOWN_5e93",
      }};
      const usage = {{
        input: 12,
        output: 3,
        cacheRead: 5,
        totalTokens: 20,
        cost: {{ input: 0.1, output: 0.2, cacheRead: 0, cacheWrite: 0, total: 0.3 }},
        privateStructured: {{ secret: canaries.unknown }},
      }};
      const user = {{
        role: "user",
        content: [
          {{ type: "text", text: canaries.user }},
          {{ type: "image_url", image_url: {{ url: canaries.media, detail: "high" }} }},
          {{ type: "tool_result", content: canaries.result }},
          {{ type: "future_block", payload: canaries.unknown }},
        ],
        tool_calls: [{{ function: {{ arguments: canaries.args }} }}],
      }};
      const assistant = {{
        role: "assistant",
        provider: "olla-cloud",
        model: "runtime-model",
        content: [
          {{ type: "text", text: canaries.assistant }},
          {{ type: "image_url", image_url: {{ url: canaries.media, detail: "high" }} }},
          {{ type: "toolCall", arguments: canaries.args }},
          {{ type: "future_block", payload: canaries.unknown }},
        ],
        usage,
        finishReason: "stop",
        stopReason: "stop",
        toolCalls: [{{ arguments: canaries.args }}],
        tool_calls: [{{ function: {{ arguments: canaries.args }} }}],
        function_calls: [{{ arguments: canaries.args }}],
      }};
      const event = {{
        type: eventName,
        requestId: "event-request-42",
        turnIndex: 7,
        provider: "olla-cloud",
        model: "runtime-model",
        usage,
        cost: {{ input: 0.1, output: 0.2, total: 0.3 }},
        costDetails: {{ input: 0.1, output: 0.2, total: 0.3 }},
        finishReason: "stop",
        unknown: {{ secret: canaries.unknown }},
        assistantMessageEvent: {{ type: "toolcall_delta", delta: canaries.args }},
        toolResults: [{{ role: "toolResult", content: canaries.result }}],
      }};
      if (eventName === "agent_end") {{
        event.messages = [
          {{ role: "system", content: canaries.system }},
          user,
          assistant,
          {{ role: "tool", content: canaries.result }},
          {{ role: "toolResult", content: canaries.result }},
        ];
      }} else {{
        event.message = assistant;
      }}
      const before = structuredClone(event);
      let current = event;
      for (const handler of handlers.get(eventName) ?? []) {{
        const result = await handler(current, {{}});
        if (eventName === "message_end" && result?.message) current = {{ ...current, message: result.message }};
      }}

      assert.equal(localBefore, event);
      assert.equal(localAfter, event);
      assert.equal(current, event);
      assert.deepEqual(event, before);
      const observed = globalThis.__piLangfuseConversationObserved[eventName];
      assert.equal(observed.type, eventName);
      assert.equal(observed.requestId, "event-request-42");
      assert.equal(observed.turnIndex, 7);
      assert.equal(observed.provider, "olla-cloud");
      assert.equal(observed.model, "runtime-model");
      assert.deepEqual(observed.usage, {{
        input: 12,
        output: 3,
        cacheRead: 5,
        totalTokens: 20,
        cost: {{ input: 0.1, output: 0.2, cacheRead: 0, cacheWrite: 0, total: 0.3 }},
      }});
      assert.deepEqual(observed.cost, {{ input: 0.1, output: 0.2, total: 0.3 }});
      assert.deepEqual(observed.costDetails, {{ input: 0.1, output: 0.2, total: 0.3 }});
      assert.equal(observed.finishReason, "stop");
      assert.equal(Object.hasOwn(observed, "assistantMessageEvent"), false);
      assert.equal(Object.hasOwn(observed, "toolResults"), false);
      assert.equal(Object.hasOwn(observed, "unknown"), false);

      const safeAssistant = {{
        role: "assistant",
        provider: "olla-cloud",
        model: "runtime-model",
        content: [
          {{ type: "text", text: canaries.assistant }},
          {{ type: "image_url", image_url: {{ url: canaries.media, detail: "high" }} }},
        ],
        usage: {{
          input: 12,
          output: 3,
          cacheRead: 5,
          totalTokens: 20,
          cost: {{ input: 0.1, output: 0.2, cacheRead: 0, cacheWrite: 0, total: 0.3 }},
        }},
        finishReason: "stop",
        stopReason: "stop",
      }};
      if (eventName === "agent_end") {{
        assert.deepEqual(observed.messages, [
          {{
            role: "user",
            content: [
              {{ type: "text", text: canaries.user }},
              {{ type: "image_url", image_url: {{ url: canaries.media, detail: "high" }} }},
            ],
          }},
          safeAssistant,
        ]);
      }} else {{
        assert.deepEqual(observed.message, safeAssistant);
      }}
      const telemetry = JSON.stringify(observed);
      for (const secret of [canaries.system, canaries.args, canaries.result, canaries.unknown]) {{
        assert.equal(telemetry.includes(secret), false, secret);
      }}
    """
    run_extension_script(script)


def test_all_package_content_paths_are_sanitized_without_changing_local_events(tmp_path):
    agent_dir = fake_all_paths_langfuse_agent_dir(tmp_path)
    script = f"""
      import assert from "node:assert/strict";

      process.env.PI_CODING_AGENT_DIR = {str(agent_dir)!r};
      globalThis.__piLangfuseAllPathsObserved = {{}};
      const {{ default: install }} = await import({EXTENSION.as_uri()!r});
      const handlers = new Map();
      const localBefore = {{}};
      const localAfter = {{}};
      const eventNames = [
        "before_agent_start",
        "agent_start",
        "turn_start",
        "after_provider_response",
        "tool_execution_start",
        "tool_call",
        "tool_result",
        "tool_execution_end",
        "session_compact",
      ];
      for (const eventName of eventNames) {{
        handlers.set(eventName, [(event) => {{ localBefore[eventName] = event; }}]);
      }}
      const pi = {{
        on(event, callback) {{
          const callbacks = handlers.get(event) ?? [];
          callbacks.push(callback);
          handlers.set(event, callbacks);
        }},
        registerCommand() {{}},
      }};
      await install(pi);
      for (const eventName of eventNames) {{
        handlers.get(eventName).push((event) => {{ localAfter[eventName] = event; }});
      }}

      const canaries = {{
        prompt: "SAFE_ROOT_PROMPT_7a29",
        user: "SAFE_CONTEXT_USER_9d51",
        assistant: "SAFE_CONTEXT_ASSISTANT_7e83",
        media: "Q0FOQVJZX1NBRkVfTUVESUFfMWYyNA==",
        system: "CANARY_ROOT_SYSTEM_4c68",
        developer: "CANARY_ROOT_DEVELOPER_2b35",
        input: "CANARY_TOOL_INPUT_6a42",
        output: "CANARY_TOOL_OUTPUT_8c17",
        error: "CANARY_TOOL_ERROR_5e93",
        summary: "CANARY_COMPACTION_SUMMARY_3f71",
        details: "CANARY_COMPACTION_DETAILS_8b26",
        response: "CANARY_PROVIDER_RESPONSE_9c14",
        unknown: "CANARY_UNKNOWN_PATH_1d52",
      }};
      const context = [
        {{ role: "system", content: canaries.system }},
        {{
          role: "user",
          content: [
            {{ type: "text", text: canaries.user }},
            {{ type: "image", data: canaries.media, mimeType: "image/png" }},
            {{ type: "tool_result", content: canaries.output }},
          ],
        }},
        {{ role: "assistant", content: [{{ type: "text", text: canaries.assistant }}] }},
        {{ role: "tool", content: canaries.output }},
      ];
      const roots = {{
        before_agent_start: {{
          type: "before_agent_start",
          prompt: canaries.prompt,
          images: [{{ type: "image", data: canaries.media, mimeType: "image/png" }}],
          context,
          systemPrompt: canaries.system,
          resources: {{ secret: canaries.unknown }},
          attachments: {{ secret: canaries.details }},
        }},
        agent_start: {{
          type: "agent_start",
          prompt: canaries.prompt,
          images: [{{ type: "image", data: canaries.media, mimeType: "image/png" }}],
          context,
          systemPrompt: canaries.system,
          instructions: canaries.developer,
        }},
      }};
      const events = {{
        ...roots,
        turn_start: {{
          type: "turn_start",
          context,
          prompt: canaries.system,
          details: {{ secret: canaries.details }},
        }},
        after_provider_response: {{
          type: "after_provider_response",
          requestId: "request-42",
          providerRequestId: "provider-request-42",
          provider: "anthropic",
          model: "claude-canary",
          status: 503,
          headers: {{ authorization: canaries.unknown }},
          responseHeaders: {{ "x-secret": canaries.unknown }},
          body: canaries.response,
          response: canaries.response,
          providerPayload: {{ secret: canaries.response }},
          error: canaries.error,
        }},
        tool_execution_start: {{
          type: "tool_execution_start",
          toolCallId: "tool-42",
          toolName: "bash",
          status: "running",
          isError: false,
          durationMs: 1,
          args: {{ command: canaries.input }},
        }},
        tool_call: {{
          type: "tool_call",
          toolCallId: "tool-42",
          toolName: "bash",
          status: "running",
          isError: false,
          durationMs: 2,
          input: {{ command: canaries.input }},
        }},
        tool_result: {{
          type: "tool_result",
          toolCallId: "tool-42",
          toolName: "bash",
          status: "error",
          isError: true,
          durationMs: 41,
          input: {{ command: canaries.input }},
          content: [{{ type: "text", text: canaries.output }}],
          details: {{ secret: canaries.details }},
          error: canaries.error,
        }},
        tool_execution_end: {{
          type: "tool_execution_end",
          toolCallId: "tool-42",
          toolName: "bash",
          status: "error",
          isError: true,
          durationMs: 42,
          result: {{ content: canaries.output }},
          output: canaries.output,
          error: canaries.error,
        }},
        session_compact: {{
          type: "session_compact",
          status: "completed",
          fromHook: true,
          compactionEntry: {{
            type: "compaction",
            id: "private-entry-id",
            timestamp: "2026-08-04T00:00:00Z",
            summary: canaries.summary,
            firstKeptEntryId: "private-kept-id",
            tokensBefore: 4321,
            details: {{ secret: canaries.details }},
            usage: {{ input: 12, output: 3, total: 15, private: canaries.unknown }},
            fromHook: true,
          }},
          summary: canaries.summary,
          details: {{ secret: canaries.details }},
        }},
      }};

      for (const eventName of eventNames) {{
        const event = events[eventName];
        const before = structuredClone(event);
        let current = event;
        for (const handler of handlers.get(eventName) ?? []) {{
          const result = await handler(current, {{}});
          if (result !== undefined) current = result;
        }}
        assert.equal(current, event, eventName);
        assert.equal(localBefore[eventName], event, eventName);
        assert.equal(localAfter[eventName], event, eventName);
        assert.deepEqual(event, before, eventName);
      }}

      const observed = globalThis.__piLangfuseAllPathsObserved;
      const safeContext = [
        {{
          role: "user",
          content: [
            {{ type: "text", text: canaries.user }},
            {{ type: "image", data: canaries.media, mimeType: "image/png" }},
          ],
        }},
        {{ role: "assistant", content: [{{ type: "text", text: canaries.assistant }}] }},
      ];
      for (const eventName of ["before_agent_start", "agent_start"]) {{
        assert.deepEqual(observed[eventName], {{
          type: eventName,
          prompt: canaries.prompt,
          images: [{{ type: "image", data: canaries.media, mimeType: "image/png" }}],
          context: safeContext,
        }});
      }}
      assert.deepEqual(observed.turn_start, {{ type: "turn_start", context: safeContext }});
      assert.deepEqual(observed.after_provider_response, {{
        type: "after_provider_response",
        requestId: "request-42",
        providerRequestId: "provider-request-42",
        provider: "anthropic",
        model: "claude-canary",
        status: 503,
        isError: true,
        error: "Provider request failed",
      }});

      for (const [eventName, durationMs] of [
        ["tool_execution_start", 1],
        ["tool_call", 2],
      ]) {{
        assert.deepEqual(Object.keys(observed[eventName]).sort(), [
          "durationMs", "isError", "status", "toolCallId", "toolName", "type",
        ].sort());
        assert.equal(observed[eventName].toolCallId, "tool-42");
        assert.equal(observed[eventName].toolName, "bash");
        assert.equal(observed[eventName].status, "running");
        assert.equal(observed[eventName].isError, false);
        assert.equal(observed[eventName].durationMs, durationMs);
      }}
      for (const [eventName, durationMs] of [
        ["tool_result", 41],
        ["tool_execution_end", 42],
      ]) {{
        assert.deepEqual(Object.keys(observed[eventName]).sort(), [
          "durationMs", "error", "isError", "status", "toolCallId", "toolName", "type",
        ].sort());
        assert.equal(observed[eventName].toolCallId, "tool-42");
        assert.equal(observed[eventName].toolName, "bash");
        assert.equal(observed[eventName].status, "error");
        assert.equal(observed[eventName].isError, true);
        assert.equal(observed[eventName].durationMs, durationMs);
        assert.equal(observed[eventName].error, "Tool failed");
      }}
      assert.equal(new Set([
        observed.tool_execution_start.toolCallId,
        observed.tool_call.toolCallId,
        observed.tool_result.toolCallId,
        observed.tool_execution_end.toolCallId,
      ]).size, 1);
      assert.deepEqual(observed.session_compact, {{
        type: "session_compact",
        status: "completed",
        fromHook: true,
        compactionEntry: {{
          tokensBefore: 4321,
          usage: {{ input: 12, output: 3, total: 15 }},
          fromHook: true,
        }},
      }});

      const telemetry = JSON.stringify(observed);
      for (const secret of [
        canaries.system,
        canaries.developer,
        canaries.input,
        canaries.output,
        canaries.error,
        canaries.summary,
        canaries.details,
        canaries.response,
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
