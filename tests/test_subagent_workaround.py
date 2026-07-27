from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "subagent-error-workaround.ts"


def run_node(script: str):
    subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )


def test_subagent_workaround_exposes_failures_without_touching_successes():
    assert EXTENSION.exists(), "tracked subagent failure workaround is required"

    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }});
      const handler = handlers.tool_result;
      assert.equal(typeof handler, "function");

      const message = 'Unknown agent: "reviewer". Available: none';
      const emptyFailure = await handler({{
        toolName: "subagent",
        toolCallId: "empty",
        input: {{ agent: "reviewer", task: "Review current diff" }},
        content: [{{ type: "text", text: message }}],
        details: {{ mode: "single", results: [], progress: undefined }},
        isError: false,
      }}, {{ cwd: process.cwd() }});
      assert.equal(emptyFailure.isError, true);
      assert.equal(emptyFailure.details.results.length, 1);
      assert.equal(emptyFailure.details.results[0].agent, "reviewer");
      assert.equal(emptyFailure.details.results[0].task, "Review current diff");
      assert.equal(emptyFailure.details.results[0].exitCode, 1);
      assert.equal(emptyFailure.details.results[0].error, message);

      const childFailure = await handler({{
        toolName: "subagent",
        toolCallId: "failure",
        input: {{ task: "Fail" }},
        content: [{{ type: "text", text: "failed" }}],
        details: {{ mode: "single", results: [{{ exitCode: 2 }}] }},
        isError: false,
      }}, {{ cwd: process.cwd() }});
      assert.deepEqual(childFailure, {{ isError: true }});

      const success = await handler({{
        toolName: "subagent",
        toolCallId: "success",
        input: {{ task: "Pass" }},
        content: [{{ type: "text", text: "passed" }}],
        details: {{ mode: "single", results: [{{ exitCode: 0 }}] }},
        isError: false,
      }}, {{ cwd: process.cwd() }});
      assert.equal(success, undefined);

      const unrelated = await handler({{
        toolName: "bash",
        toolCallId: "bash",
        input: {{}},
        content: [{{ type: "text", text: "failed" }}],
        details: {{ exitCode: 1 }},
        isError: false,
      }}, {{ cwd: process.cwd() }});
      assert.equal(unrelated, undefined);
    """
    run_node(script)


def test_subagent_provider_errors_exit_nonzero_with_upstream_context():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }});
      assert.equal(typeof handlers.message_end, "function");

      const originalSocket = process.env.PI_SUBAGENT_SOCKET;
      const originalExitCode = process.exitCode;
      const originalError = console.error;
      const errors = [];
      process.env.PI_SUBAGENT_SOCKET = "/tmp/test-subagent.sock";
      process.exitCode = undefined;
      console.error = (...args) => errors.push(args.join(" "));

      try {{
        await handlers.message_end({{
          message: {{
            role: "assistant",
            provider: "olla-cloud",
            model: "gpt-4.1-mini",
            stopReason: "error",
            errorMessage: "403: upstream monthly limit exceeded",
          }},
        }});
        assert.equal(process.exitCode, 1);
        assert.deepEqual(errors, [
          "[subagent] olla-cloud/gpt-4.1-mini failed: 403: upstream monthly limit exceeded",
        ]);

        process.exitCode = undefined;
        errors.length = 0;
        await handlers.message_end({{
          message: {{
            role: "assistant",
            provider: "olla-cloud",
            model: "gpt-4.1-mini",
            stopReason: "error",
            errorMessage: '403: {{"message":"litellm.APIError: OpenrouterException - Key limit exceeded (monthly limit). Manage it using https://openrouter.ai/workspaces/default/keys/private-key-id"}}',
          }},
        }});
        assert.equal(process.exitCode, 1);
        assert.deepEqual(errors, [
          "[subagent] olla-cloud/gpt-4.1-mini failed: upstream OpenRouter monthly limit exceeded (HTTP 403 via Olla)",
        ]);

        process.exitCode = undefined;
        errors.length = 0;
        await handlers.message_end({{
          message: {{
            role: "assistant",
            provider: "olla-cloud",
            model: "gpt-4.1-mini",
            stopReason: "stop",
            content: [],
          }},
        }});
        assert.equal(process.exitCode, undefined);
        assert.deepEqual(errors, []);
      }} finally {{
        console.error = originalError;
        process.exitCode = originalExitCode;
        if (originalSocket === undefined) delete process.env.PI_SUBAGENT_SOCKET;
        else process.env.PI_SUBAGENT_SOCKET = originalSocket;
      }}
    """
    run_node(script)


def test_interactive_results_emit_evaluator_ready_observations():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes, options) {{ observations.push({{ name, attributes, options }}); }},
      }});

      const originalSocket = process.env.PI_SUBAGENT_SOCKET;
      delete process.env.PI_SUBAGENT_SOCKET;
      await handlers.before_agent_start({{ prompt: "Fix auth" }});
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: [{{ type: "text", text: "Intermediate attempt" }}] }}] }});
      assert.deepEqual(observations, []);
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: [{{ type: "text", text: "Auth fixed" }}] }}] }});
      await handlers.agent_settled({{}});
      assert.deepEqual(observations, [{{
        name: "interactive-result",
        attributes: {{ input: "Fix auth", output: "Auth fixed" }},
        options: {{ asType: "agent" }},
      }}]);

      process.env.PI_SUBAGENT_SOCKET = "/tmp/test-subagent.sock";
      await handlers.before_agent_start({{ prompt: "Headless work" }});
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: [{{ type: "text", text: "Done" }}] }}] }});
      await handlers.agent_settled({{}});
      delete process.env.PI_SUBAGENT_SOCKET;
      await handlers.before_agent_start({{ prompt: "Fail visibly" }});
      await handlers.agent_end({{ messages: [{{
        role: "assistant",
        content: [],
        stopReason: "error",
        errorMessage: "403: OpenrouterException - Key limit exceeded (monthly limit): https://openrouter.ai/settings/keys?id=secret",
      }}] }});
      await handlers.agent_settled({{}});
      assert.equal(observations[1].attributes.output, "upstream OpenRouter monthly limit exceeded (HTTP 403 via Olla)");
      if (originalSocket === undefined) delete process.env.PI_SUBAGENT_SOCKET;
      else process.env.PI_SUBAGENT_SOCKET = originalSocket;
      assert.equal(observations.length, 2);
    """
    run_node(script)


def test_subagent_results_emit_evaluator_ready_observations():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes, options) {{ observations.push({{ name, attributes, options }}); }},
      }});

      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "parallel",
        input: {{ tasks: [
          {{ task: "Review auth", model: "olla-cloud/gpt-4.1-mini" }},
          {{ task: "Check tests", model: "openai-codex/gpt-5.6-luna" }},
        ] }},
        content: [{{ type: "text", text: "summary" }}],
        details: {{ mode: "parallel", results: [
          {{ task: "Review auth", model: "gpt-4.1-mini", exitCode: 0, finalOutput: "Auth review complete" }},
          {{ task: "Check tests", model: "gpt-5.6-luna", exitCode: 1, error: "Provider unavailable" }},
        ] }},
        isError: false,
      }}, {{ cwd: process.cwd(), model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }});

      assert.deepEqual(observations, [
        {{
          name: "subagent-result",
          attributes: {{
            input: "Review auth",
            output: "Auth review complete",
            metadata: {{ index: 0, model: "gpt-4.1-mini", exitCode: 0 }},
            level: "DEFAULT",
          }},
          options: {{ asType: "agent" }},
        }},
        {{
          name: "subagent-result",
          attributes: {{
            input: "Check tests",
            output: "Provider unavailable",
            metadata: {{ index: 1, model: "gpt-5.6-luna", exitCode: 1 }},
            level: "ERROR",
          }},
          options: {{ asType: "agent" }},
        }},
      ]);
    """
    run_node(script)


def test_subagent_results_write_payload_free_agnt_metrics(tmp_path):
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFile, readdir }} from "node:fs/promises";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }});
      assert.equal(typeof handlers.tool_call, "function");
      assert.equal(typeof handlers.tool_result, "function");

      const cwd = {str(tmp_path)!r};
      const secretPrompt = "SECRET prompt body must not be persisted";
      const secretOutput = "SECRET response body must not be persisted";
      const input = {{ task: secretPrompt, model: "openai-codex/gpt-5.6-luna" }};
      const singleStarted = Date.now();
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "single", input }}, {{ cwd }});
      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "single",
        input,
        content: [{{ type: "text", text: secretOutput }}],
        details: {{ mode: "single", results: [{{
          agent: "subagent",
          task: secretPrompt,
          exitCode: 0,
          usage: {{ input: 120, output: 30, cacheRead: 40, cacheWrite: 0, cost: 0.12, turns: 3 }},
          model: "gpt-5.6-luna",
          finalOutput: secretOutput,
          error: undefined,
          progressSummary: {{ toolCount: 2, tokens: 190, durationMs: 1500 }},
        }}], progress: [] }},
        isError: false,
      }}, {{ cwd, model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }});

      const parallelInput = {{ tasks: [
        {{ task: "first private task", model: "olla-cloud/gemini-flash" }},
        {{ task: "second private task", model: "olla-cloud/gpt-4.1-mini" }},
      ] }};
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "parallel", input: parallelInput }}, {{ cwd }});
      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "parallel",
        input: parallelInput,
        content: [{{ type: "text", text: "summary" }}],
        details: {{ mode: "parallel", results: [
          {{ agent: "subagent", task: "first private task", exitCode: 0, usage: {{ input: 10, output: 5, cacheRead: 0, cacheWrite: 0, cost: 0.01, turns: 1 }}, model: "gemini-flash", finalOutput: "first private output", progressSummary: {{ toolCount: 1, tokens: 15, durationMs: 500 }} }},
          {{ agent: "subagent", task: "second private task", exitCode: 0, usage: {{ input: 20, output: 8, cacheRead: 2, cacheWrite: 0, cost: 0.02, turns: 2 }}, model: "gpt-4.1-mini", finalOutput: "second private output", progressSummary: {{ toolCount: 0, tokens: 30, durationMs: 700 }} }},
        ], progress: [] }},
        isError: false,
      }}, {{ cwd, model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }});

      const inheritedInput = {{ task: "inherited private task" }};
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "inherited", input: inheritedInput }}, {{ cwd }});
      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "inherited",
        input: inheritedInput,
        content: [{{ type: "text", text: "inherited output" }}],
        details: {{ mode: "single", results: [{{
          agent: "subagent",
          task: "inherited private task",
          exitCode: 0,
          usage: {{ input: 6, output: 3, cacheRead: 0, cacheWrite: 0, cost: 0.01, turns: 1 }},
          model: "google/gemma-4-31b-it",
          finalOutput: "inherited output",
          progressSummary: {{ toolCount: 0, tokens: 9, durationMs: 100 }},
        }}], progress: [] }},
        isError: false,
      }}, {{ cwd, model: {{ provider: "openrouter-localish", id: "google/gemma-4-31b-it" }} }});

      const namedInput = {{ agent: "configured-reviewer", task: "named private task", model: "olla-cloud/gpt-4.1-mini" }};
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "named", input: namedInput }}, {{ cwd }});
      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "named",
        input: namedInput,
        content: [{{ type: "text", text: "named output" }}],
        details: {{ mode: "single", results: [{{
          agent: "configured-reviewer",
          task: "named private task",
          exitCode: 0,
          usage: {{ input: 4, output: 2, cacheRead: 0, cacheWrite: 0, cost: 0.01, turns: 1 }},
          model: "different-model-from-agent-profile",
          finalOutput: "named output",
          progressSummary: {{ toolCount: 0, tokens: 6, durationMs: 200 }},
        }}], progress: [] }},
        isError: false,
      }}, {{ cwd, model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }});

      const finished = Date.now();
      const dir = `${{cwd}}/.pi/metrics/invocations`;
      const files = await readdir(dir);
      assert.equal(files.length, 4, "named profiles must be skipped when actual provider is unavailable");
      const records = await Promise.all(files.map(async (file) => JSON.parse(await readFile(`${{dir}}/${{file}}`, "utf8"))));
      const single = records.find((record) => record.target === "openai-codex/gpt-5.6-luna");
      assert.equal(single.schemaVersion, 1);
      assert.equal(single.invocationMode, "subagent");
      assert.equal(single.kind, "subagent");
      assert.equal(single.task, "peer");
      assert.equal(single.exitCode, 0);
      assert.ok(Date.parse(single.startedAt) >= singleStarted);
      assert.ok(Date.parse(single.endedAt) <= finished);
      assert.equal(single.elapsedMs, Date.parse(single.endedAt) - Date.parse(single.startedAt));
      assert.equal(single.workerElapsedMs, 1500);
      assert.equal(single.contextChars, secretPrompt.length);
      assert.equal(single.responseChars, secretOutput.length);
      assert.equal(single.providerRequests, 3);
      assert.equal(single.usage.totalTokens, 190);
      assert.equal(single.usage.cost.total, 0.12);
      assert.equal(records.find((record) => record.target === "olla-cloud/gemini-flash").workerElapsedMs, 500);
      assert.equal(records.find((record) => record.target === "olla-cloud/gpt-4.1-mini").workerElapsedMs, 700);
      assert.ok(records.some((record) => record.target === "openrouter-localish/google/gemma-4-31b-it"));

      const serialized = JSON.stringify(records);
      for (const secret of [secretPrompt, secretOutput, "first private task", "second private task", "first private output", "second private output", "inherited private task", "inherited output"]) {{
        assert.equal(serialized.includes(secret), false, `persisted secret: ${{secret}}`);
      }}
    """
    run_node(script)
