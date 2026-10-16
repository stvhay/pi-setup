from __future__ import annotations

from pathlib import Path

import pytest

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "zz-output-redaction.ts"


def test_shared_output_boundary_redacts_credentials_and_preserves_diagnostics():
    script = f"""
      import assert from "node:assert/strict";
      import {{ inspect }} from "node:util";
      import install, {{ REDACTED, redactOutputText, redactOutputValue }} from {EXTENSION.as_uri()!r};

      const fakeGithub = ["ghp", "syntheticabcdefghijklmnopqrstuvwxyz1234"].join("_");
      const fakeAws = ["AKIA", "SYNTHETIC1234567"].join("");
      const fakeAwsSecret = ["synthetic", "aws", "secret", "access", "key", "1234567890"].join("/");
      const fakeSlack = ["xoxb", "123456789012", "syntheticabcdefghijklmnop"].join("-");
      const fakeStripe = ["sk", "live", "syntheticabcdefghijklmnopqrstuvwxyz"].join("_");
      const fakeJwt = ["eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiJzeW50aGV0aWMifQ", "syntheticsignature123456"].join(".");
      const fakeKey = ["sk", "syntheticabcdefghijklmnopqrstuvwxyz"].join("-");
      const privateKey = [
        "-----BEGIN PRIVATE KEY-----",
        "c3ludGhldGljLW5vdC1hLXJlYWwta2V5",
        "-----END PRIVATE KEY-----",
      ].join("\\n");
      const secrets = [fakeGithub, fakeAws, fakeAwsSecret, fakeSlack, fakeStripe, fakeJwt, fakeKey, privateKey];
      const raw = [
        `OPENAI_API_KEY=${{fakeKey}}`,
        `AWS_SECRET_ACCESS_KEY=${{fakeAwsSecret}}`,
        `Authorization: Bearer ${{fakeGithub}}`,
        `debug={{"password":"synthetic password","status":"failed"}}`,
        `command --client-secret ${{fakeSlack}} --mode check`,
        `https://service.invalid/check?access_token=${{fakeJwt}}&page=2`,
        fakeAws,
        fakeStripe,
        privateKey,
      ].join("\\n");

      const text = redactOutputText(raw);
      for (const secret of secrets) assert.equal(text.includes(secret), false, `exposed ${{secret.slice(0, 8)}}`);
      assert.match(text, new RegExp(REDACTED.replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&")));
      for (const safe of ["OPENAI_API_KEY=", "AWS_SECRET_ACCESS_KEY=", "Authorization: ", '"status":"failed"', "--mode check", "page=2"]) {{
        assert.equal(text.includes(safe), true, `missing safe diagnostic: ${{safe}}`);
      }}
      assert.equal(
        redactOutputText("HTTP 401 Unauthorized; inputTokens=120; tokenPath=/tmp/runtime-token; provider=openrouter"),
        "HTTP 401 Unauthorized; inputTokens=120; tokenPath=/tmp/runtime-token; provider=openrouter",
      );

      const nested = redactOutputValue({{
        status: "failed",
        request: {{ apiKey: fakeKey, attempts: 2 }},
        diagnostics: [`stderr token=${{fakeGithub}}`, "HTTP 503 Service Unavailable"],
      }});
      assert.deepEqual(nested, {{
        status: "failed",
        request: {{ apiKey: REDACTED, attempts: 2 }},
        diagnostics: [`stderr token=${{REDACTED}}`, "HTTP 503 Service Unavailable"],
      }});
      const error = new Error(`request token=${{fakeGithub}}`);
      error.code = "E_SYNTHETIC_AUTH";
      error.exitCode = 7;
      const redactedError = redactOutputValue(error);
      assert.equal(redactedError.message.includes(fakeGithub), false);
      assert.equal(redactedError.code, "E_SYNTHETIC_AUTH");
      assert.equal(redactedError.exitCode, 7);

      const handlers = {{}};
      let markdownTransformer;
      const captured = [];
      const original = {{ log: console.log, error: console.error, debug: console.debug }};
      console.log = (...args) => captured.push(["log", ...args]);
      console.error = (...args) => captured.push(["error", ...args]);
      console.debug = (...args) => captured.push(["debug", ...args]);
      install({{
        on(name, handler) {{ handlers[name] = handler; }},
        registerMarkdownTransformer(handler) {{ markdownTransformer = handler; }},
      }});

      try {{
        for (const [label, isError] of [["stdout", false], ["stderr", true], ["debug", false]]) {{
          const secret = secrets[captured.length];
          const patch = await handlers.tool_result({{
            toolName: label,
            toolCallId: label,
            input: {{}},
            content: [
              {{ type: "text", text: `${{label}} credential=${{secret}}; exitCode=${{isError ? 1 : 0}}` }},
              {{ type: "image", data: "synthetic-image", mimeType: "image/png" }},
            ],
            details: {{ isError, authorization: `Bearer ${{secret}}`, exitCode: isError ? 1 : 0 }},
            isError,
          }});
          assert.equal(JSON.stringify(patch).includes(secret), false);
          assert.equal(patch.isError, undefined, "redaction must not alter tool status");
          assert.equal(patch.content[0].text.includes(`exitCode=${{isError ? 1 : 0}}`), true);
          assert.equal(patch.content[1].data, "synthetic-image");
          assert.equal(patch.details.exitCode, isError ? 1 : 0);
        }}

        for (const [name, field] of [["tool_execution_update", "partialResult"], ["tool_execution_end", "result"]]) {{
          const event = {{
            [field]: {{
              content: [{{ type: "text", text: `stream credential=${{fakeStripe}}; progress=50` }}],
              details: {{ authorization: `Bearer ${{fakeGithub}}`, progress: 50 }},
            }},
          }};
          await handlers[name](event, {{}});
          assert.equal(JSON.stringify(event).includes(fakeStripe), false);
          assert.equal(JSON.stringify(event).includes(fakeGithub), false);
          assert.equal(JSON.stringify(event).includes("progress"), true);
        }}

        const finalToolResult = await handlers.message_end({{ message: {{
          role: "toolResult",
          toolCallId: "late-tool",
          toolName: "late-tool",
          content: [{{ type: "text", text: `late credential=${{fakeGithub}}; exitCode=1` }}],
          details: {{ password: fakeKey, exitCode: 1 }},
          isError: true,
        }} }});
        assert.equal(JSON.stringify(finalToolResult).includes(fakeGithub), false);
        assert.equal(JSON.stringify(finalToolResult).includes(fakeKey), false);
        assert.equal(finalToolResult.message.isError, true);
        assert.equal(finalToolResult.message.details.exitCode, 1);

        const assistant = await handlers.message_end({{ message: {{
          role: "assistant",
          content: [
            {{ type: "text", text: `Result: ${{fakeGithub}}; status=failed` }},
            {{ type: "thinking", thinking: `debug token=${{fakeSlack}}` }},
          ],
          errorMessage: `request failed with ${{fakeKey}}`,
        }} }});
        assert.equal(JSON.stringify(assistant).includes(fakeGithub), false);
        assert.equal(JSON.stringify(assistant).includes(fakeSlack), false);
        assert.equal(JSON.stringify(assistant).includes(fakeKey), false);
        assert.equal(JSON.stringify(assistant).includes("status=failed"), true);

        assert.equal(markdownTransformer(`stream ${{fakeJwt}}; HTTP 401`, {{ messageType: "assistant", isStreaming: true }}).includes(fakeJwt), false);
        assert.equal(markdownTransformer(`user supplied ${{fakeJwt}}`, {{ messageType: "user", isStreaming: false }}).includes(fakeJwt), true);

        const delta = {{
          message: {{ role: "assistant", content: [] }},
          assistantMessageEvent: {{ type: "text_delta", contentIndex: 0, delta: fakeGithub, partial: {{ role: "assistant", content: [] }} }},
        }};
        await handlers.message_update(delta, {{ mode: "json" }});
        assert.equal(delta.assistantMessageEvent.delta, "", "JSON/RPC deltas must be withheld until redacted final content exists");
        const end = {{
          message: {{ role: "assistant", content: [] }},
          assistantMessageEvent: {{ type: "text_end", contentIndex: 0, content: `done ${{fakeGithub}}; HTTP 401`, partial: {{ role: "assistant", content: [] }} }},
        }};
        await handlers.message_update(end, {{ mode: "rpc" }});
        assert.equal(end.assistantMessageEvent.content.includes(fakeGithub), false);
        assert.equal(end.assistantMessageEvent.content.includes("HTTP 401"), true);
        const done = {{
          message: {{ role: "assistant", content: [] }},
          assistantMessageEvent: {{ type: "done", reason: "stop", message: {{ role: "assistant", content: [{{ type: "text", text: fakeGithub }}] }} }},
        }};
        await handlers.message_update(done, {{ mode: "json" }});
        assert.equal(JSON.stringify(done.assistantMessageEvent).includes(fakeGithub), false);

        console.log(`standard token=${{fakeGithub}}`, {{ status: "failed", password: fakeKey }});
        console.error(`error Authorization: Bearer ${{fakeSlack}}`);
        console.debug(`debug ${{fakeAws}}`);
        console.error("mapped diagnostics", new Map([["authorization", `Bearer ${{fakeGithub}}`], ["status", "failed"]]));
        const serialized = inspect(captured, {{ depth: 10 }});
        for (const secret of [fakeGithub, fakeSlack, fakeAws, fakeKey]) assert.equal(serialized.includes(secret), false);
        for (const safe of ["standard", "status", "failed", "error", "debug", "mapped diagnostics"]) assert.equal(serialized.includes(safe), true);
      }} finally {{
        await handlers.session_shutdown?.({{}}, {{}});
        console.log = original.log;
        console.error = original.error;
        console.debug = original.debug;
      }}
    """

    run_node(script)


def test_encoded_media_exemption_does_not_exempt_text_or_metadata():
    script = f"""
      import assert from "node:assert/strict";
      import {{ REDACTED, redactOutputValue }} from {EXTENSION.as_uri()!r};
      const encoded = "iVBORw0KGgo/" + "AKIA" + "1234567890123456";
      const credential = ["ghp", "syntheticabcdefghijklmnopqrstuvwxyz1234"].join("_");
      const block = {{ type: "image", mimeType: "image/png", data: encoded, password: credential }};
      assert.deepEqual(redactOutputValue(block), {{ ...block, password: REDACTED }});
      assert.equal(redactOutputValue({{ ...block, data: credential }}).data, REDACTED);
      assert.notEqual(redactOutputValue({{ ...block, mimeType: "text/plain" }}).data, encoded);
      assert.notEqual(redactOutputValue({{ data: encoded }}).data, encoded);
      const plainKey = "AKIA" + "1234567890123456";
      assert.equal(redactOutputValue({{ ...block, data: plainKey }}).data, REDACTED);
    """
    run_node(script)


@pytest.mark.parametrize("surface", ["tool_result", "tool_execution_update", "tool_execution_end", "message_end"])
def test_structured_results_survive_redaction_at_every_output_boundary(surface):
    script = f"""
      import assert from "node:assert/strict";
      import install, {{ REDACTED }} from {EXTENSION.as_uri()!r};

      const handlers = new Map();
      install({{
        on(name, handler) {{ handlers.set(name, [handler]); }},
        registerMarkdownTransformer() {{}},
      }});
      try {{
        const credential = ["ghp", "syntheticabcdefghijklmnopqrstuvwxyz1234"].join("_");
        // Valid base64 can contain credential-shaped substrings; encoded media is opaque.
        const image = {{ type: "image", mimeType: "image/png", data: "iVBORw0KGgo/" + "AKIA" + "1234567890123456" }};
        for (const isError of [false, true]) {{
          const structured = {{
            content: [{{ type: "text", text: `diagnostic ${{credential}}` }}, image],
            structuredContent: {{ password: credential, completed: 1, failed: 1,
              results: [{{ ok: true }}, {{ ok: false, error: "unknown command" }}] }},
            isError,
          }};
          const payload = {{
            content: [{{ type: "text", text: "safe diagnostic" }}],
            details: {{}}, structuredContent: structured, isError,
          }};
          let result;
          const surface = {surface!r};
          if (surface === "tool_result") {{
            const patch = await handlers.get(surface)[0]({{
              type: surface, toolName: "mcp__fixture__inspect", toolCallId: "fixture",
              input: {{}}, ...payload,
            }});
            assert.ok(patch.structuredContent, "content replacement must include structured result");
            result = {{ ...payload, ...patch }};
          }} else if (surface === "message_end") {{
            result = (await handlers.get(surface)[0]({{
              message: {{ role: "toolResult", ...payload }},
            }})).message;
          }} else {{
            const field = surface === "tool_execution_update" ? "partialResult" : "result";
            const event = {{ [field]: payload }};
            await handlers.get(surface)[0](event);
            result = event[field];
          }}
          assert.ok(result.structuredContent, "structured result must survive output hook");
          assert.equal(result.isError, isError);
          assert.equal(result.structuredContent.isError, isError);
          assert.deepEqual(result.structuredContent.content[1], image);
          assert.deepEqual(result.structuredContent.structuredContent, {{
            password: REDACTED, completed: 1, failed: 1,
            results: [{{ ok: true }}, {{ ok: false, error: "unknown command" }}],
          }});
          assert.equal(result.structuredContent.content[0].text, `diagnostic ${{REDACTED}}`);
          assert.equal(JSON.stringify(result).includes(credential), false);
          assert.equal(structured.structuredContent.password, credential, "do not mutate input");
        }}
        for (const value of [null, false, 0, "safe", [1, false], {{ exit_code: 2, output: "failure" }}]) {{
          const patch = handlers.get("tool_result")[0]({{
            content: [], details: undefined, structuredContent: value, isError: false,
          }});
          assert.deepEqual(patch.structuredContent, value);
        }}
      }} finally {{
        for (const shutdown of handlers.get("session_shutdown")) shutdown();
      }}
    """
    run_node(script)
