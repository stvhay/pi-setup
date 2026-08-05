from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "subagent-error-workaround.ts"
RUNTIME_ARTIFACTS = ROOT / "pi" / "agent" / "extensions" / "lib" / "runtime-artifacts.ts"


def run_node(script: str, env: dict[str, str] | None = None):
    subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent"), **(env or {})},
    )


def test_subagent_workaround_exposes_failures_without_touching_successes():
    assert EXTENSION.exists(), "tracked subagent failure workaround is required"

    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }}, {{
        observe() {{}},
        persistDelegatedResult(_root, payload) {{
          return `runtime:delegated-results/${{payload.invocationId}}/child-${{payload.childIndex}}.json`;
        }},
      }});
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
      assert.equal(childFailure.isError, true);
      assert.equal(childFailure.details.results[0].artifact.status, "persisted");
      assert.match(childFailure.content.at(-1).text, /^Delegated artifacts:/);

      const success = await handler({{
        toolName: "subagent",
        toolCallId: "success",
        input: {{ task: "Pass" }},
        content: [{{ type: "text", text: "passed" }}],
        details: {{ mode: "single", results: [{{ exitCode: 0 }}] }},
        isError: false,
      }}, {{ cwd: process.cwd() }});
      assert.equal(success.isError, undefined);
      assert.equal(success.details.results[0].artifact.status, "persisted");
      assert.match(success.content.at(-1).text, /^Delegated artifacts:/);

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
      import install, {{ providerFailureClass }} from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const circuits = [];
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }}, {{
        observe() {{}},
        providerCircuit(action, provider, reason) {{ circuits.push({{ action, provider, reason }}); }},
        activeProviderCircuits() {{ return ["olla-cloud"]; }},
      }});
      assert.equal(typeof handlers.message_end, "function");
      assert.deepEqual([
        providerFailureClass("429: insufficient_quota"),
        providerFailureClass("HTTP 402: available credits can only cover 505 tokens"),
        providerFailureClass("401 Unauthorized: invalid API key"),
        providerFailureClass("No auth credentials found"),
        providerFailureClass("HTTP 503 Service Unavailable"),
        providerFailureClass("provider returned HTTP 503"),
        providerFailureClass("pi invocation timed out after 60s"),
      ], ["quota", "credit", "authentication", "authentication", "availability", "availability", undefined]);

      const originalSocket = process.env.PI_SUBAGENT_SOCKET;
      const originalExitCode = process.exitCode;
      const originalError = console.error;
      const errors = [];
      delete process.env.PI_SUBAGENT_SOCKET;
      process.exitCode = undefined;
      console.error = (...args) => errors.push(args.join(" "));

      try {{
        await handlers.session_start({{}}, {{ cwd: process.cwd() }});
        await handlers.message_end({{ message: {{ role: "assistant", provider: "olla-cloud", stopReason: "stop" }} }}, {{ cwd: process.cwd() }});
        assert.deepEqual(circuits, [{{ action: "success", provider: "olla-cloud", reason: undefined }}]);
        circuits.length = 0;
        process.env.PI_SUBAGENT_SOCKET = "/tmp/test-subagent.sock";

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
        assert.deepEqual(circuits, [
          {{ action: "open", provider: "olla-cloud", reason: "quota" }},
          {{ action: "open", provider: "olla-cloud", reason: "quota" }},
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
        assert.deepEqual(circuits.at(-1), {{ action: "success", provider: "olla-cloud", reason: undefined }});
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
      const ctx = {{ sessionManager: {{ getSessionFile() {{ return "/private/2026-07-28T00-00-00Z_private-session.jsonl"; }} }} }};
      await handlers.agent_settled({{}}, ctx);
      assert.deepEqual(observations, [{{
        name: "interactive-result",
        attributes: {{ input: "Fix auth", output: "Auth fixed", metadata: {{ executionOutcome: "succeeded" }} }},
        options: {{ asType: "agent", sessionId: "2026-07-28T00-00-00Z_private-session" }},
      }}]);

      await handlers.before_agent_start({{ prompt: "Ask for a choice" }});
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: [] }}] }});
      await handlers.agent_settled({{}}, ctx);
      assert.equal(observations.length, 1, "empty assistant output must not be evaluated");

      await handlers.before_agent_start({{ prompt: "No captured result" }});
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: null }}] }});
      await handlers.agent_settled({{}}, ctx);
      assert.equal(observations.length, 1, "null assistant output must not be evaluated");

      process.env.PI_SUBAGENT_SOCKET = "/tmp/test-subagent.sock";
      await handlers.before_agent_start({{ prompt: "Headless work" }});
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: [{{ type: "text", text: "Done" }}] }}] }});
      await handlers.agent_settled({{}});
      delete process.env.PI_SUBAGENT_SOCKET;
      await handlers.before_agent_start({{ prompt: "Fail visibly" }});
      await handlers.agent_end({{ messages: [{{
        role: "assistant",
        content: [{{ type: "text", text: "Useful partial report" }}],
        stopReason: "error",
        errorMessage: "403: OpenrouterException - Key limit exceeded (monthly limit): https://openrouter.ai/settings/keys?id=secret",
      }}] }});
      await handlers.agent_settled({{}});
      assert.equal(
        observations[1].attributes.output,
        "Useful partial report\\n\\n[execution failed: upstream OpenRouter monthly limit exceeded (HTTP 403 via Olla)]",
      );
      assert.deepEqual(observations[1].attributes.metadata, {{
        executionOutcome: "failed",
        failureClass: "provider",
        providerFailureClass: "quota",
      }});
      if (originalSocket === undefined) delete process.env.PI_SUBAGENT_SOCKET;
      else process.env.PI_SUBAGENT_SOCKET = originalSocket;
      assert.equal(observations.length, 2);
    """
    run_node(script)


def test_aborted_interactive_result_is_unavailable_not_successful():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes) {{ observations.push({{ name, attributes }}); }},
      }});

      delete process.env.PI_SUBAGENT_SOCKET;
      await handlers.before_agent_start({{ prompt: "Stop work" }});
      await handlers.agent_end({{ messages: [{{
        role: "assistant",
        content: [{{ type: "text", text: "Partial work" }}],
        stopReason: "aborted",
      }}] }});
      await handlers.agent_settled({{}});

      assert.equal(observations[0].attributes.output, "Partial work");
      assert.deepEqual(observations[0].attributes.metadata, {{ executionOutcome: "unavailable" }});
    """
    run_node(script)


def test_interactive_results_emit_payload_free_tool_error_signals():
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

      delete process.env.PI_SUBAGENT_SOCKET;
      const ctx = {{
        cwd: process.cwd(),
        sessionManager: {{ getSessionFile() {{ return "/private/private-session.jsonl"; }} }},
      }};
      await handlers.before_agent_start({{ prompt: "Run checks" }});
      await handlers.tool_result({{
        toolName: "bash", toolCallId: "red", input: {{ command: "SECRET failing test" }},
        details: {{ exitCode: 1, cancelled: false }}, isError: true, content: [],
      }}, ctx);
      await handlers.tool_result({{
        toolName: "bash", toolCallId: "green", input: {{ command: "SECRET failing test" }},
        details: {{ exitCode: 0, cancelled: false }}, isError: false, content: [],
      }}, ctx);
      await handlers.tool_result({{
        toolName: "bash", toolCallId: "timeout", input: {{ command: "SECRET timeout command" }},
        details: {{ timedOut: true }}, isError: true, content: [],
      }}, ctx);
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: [{{ type: "text", text: "Done" }}] }}] }});
      await handlers.agent_settled({{}}, ctx);

      const signals = observations[0].attributes.metadata.toolErrorSignals;
      assert.equal(signals.length, 2);
      assert.deepEqual(signals.map((item) => item.classification).sort(), ["infrastructure", "recovered"]);
      assert.equal(signals.every((item) => /^[0-9a-f]{{64}}$/.test(item.inputHash)), true);
      assert.equal(JSON.stringify(signals).includes("SECRET"), false);
    """
    run_node(script)


def test_subagent_results_emit_evaluator_ready_observations():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      const payloads = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes, options) {{ observations.push({{ name, attributes, options }}); }},
        persistDelegatedResult(_root, payload) {{
          payloads.push(payload);
          return `runtime:delegated-results/${{payload.invocationId}}/child-${{payload.childIndex}}.json`;
        }},
      }});

      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "parallel",
        input: {{ tasks: [
          {{ task: "Review auth", model: "olla-cloud/gpt-4.1-mini", outputContract: "inline" }},
          {{ task: "Check tests", model: "openai-codex/gpt-5.6-luna", outputContract: "artifact" }},
        ] }},
        content: [{{ type: "text", text: "summary" }}],
        details: {{ mode: "parallel", results: [
          {{ task: "Review auth", model: "gpt-4.1-mini", exitCode: 0, finalOutput: "Auth review complete" }},
          {{ task: "Check tests", model: "gpt-5.6-luna", exitCode: 1, error: "Provider unavailable" }},
        ] }},
        isError: false,
      }}, {{
        cwd: process.cwd(),
        model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }},
        sessionManager: {{ getSessionFile() {{ return "/private/private-session.jsonl"; }} }},
      }});

      const invocationIds = observations.map((item) => item.attributes.metadata.invocationId);
      const artifactRefs = invocationIds.map((id, index) => [`runtime:delegated-results/${{id}}/child-${{index}}.json`]);
      assert.equal(new Set(invocationIds).size, 2);
      assert.equal(invocationIds.every((id) => /^[0-9a-f-]{{36}}$/.test(id)), true);
      for (const observation of observations) delete observation.attributes.metadata.invocationId;
      assert.deepEqual(observations, [
        {{
          name: "subagent-result",
          attributes: {{
            input: {{
              task: "Review auth",
              outputContract: "inline",
              executionOutcome: "succeeded",
              artifactStatus: "persisted",
              artifactContentStatus: "available",
              artifactReferenceCount: 1,
              artifactFailureClass: null,
            }},
            output: "Auth review complete",
            metadata: {{
              index: 0,
              provider: "olla-cloud",
              model: "gpt-4.1-mini",
              target: "olla-cloud/gpt-4.1-mini",
              thinkingLevel: "default",
              modelDimensionsStatus: "available",
              executionOutcome: "succeeded",
              outputContract: "inline",
              artifactRefs: artifactRefs[0],
              artifactStatus: "persisted",
              exitCode: 0,
            }},
            level: "DEFAULT",
          }},
          options: {{ asType: "agent", sessionId: "private-session" }},
        }},
        {{
          name: "subagent-result",
          attributes: {{
            input: {{
              task: "Check tests",
              outputContract: "artifact",
              executionOutcome: "failed",
              artifactStatus: "persisted",
              artifactContentStatus: "available",
              artifactReferenceCount: 1,
              artifactFailureClass: null,
            }},
            output: "Provider unavailable",
            metadata: {{
              index: 1,
              provider: "openai-codex",
              model: "gpt-5.6-luna",
              target: "openai-codex/gpt-5.6-luna",
              thinkingLevel: "default",
              modelDimensionsStatus: "available",
              executionOutcome: "failed",
              outputContract: "artifact",
              artifactRefs: artifactRefs[1],
              artifactStatus: "persisted",
              exitCode: 1,
            }},
            level: "ERROR",
          }},
          options: {{ asType: "agent", sessionId: "private-session" }},
        }},
      ]);
      assert.deepEqual(payloads.map((payload) => payload.outputContract), ["inline", "artifact"]);
    """
    run_node(script)


def test_subagent_evaluator_view_bounds_output_and_marks_unavailable():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(_name, attributes) {{ observations.push(attributes); }},
        persistDelegatedResult() {{ throw new Error("write failed"); }},
      }});

      const longOutput = "x".repeat(12_050);
      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "bounded",
        input: {{ tasks: [
          {{ task: "Write artifact", outputContract: "artifact" }},
          {{ task: "Return findings", outputContract: "inline" }},
        ] }},
        content: [{{ type: "text", text: "summary" }}],
        details: {{ mode: "parallel", results: [
          {{ exitCode: 0, finalOutput: longOutput }},
          {{ exitCode: 0 }},
        ] }},
        isError: false,
      }}, {{ cwd: process.cwd(), model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }});

      assert.deepEqual(observations.map((item) => item.input.outputContract), ["artifact", "inline"]);
      assert.deepEqual(observations.map((item) => item.input.artifactStatus), ["failed", "failed"]);
      assert.deepEqual(observations.map((item) => item.input.artifactContentStatus), ["unavailable", "unavailable"]);
      assert.deepEqual(observations.map((item) => item.input.artifactReferenceCount), [0, 0]);
      assert.deepEqual(observations.map((item) => item.input.artifactFailureClass), ["write", "write"]);
      assert.equal(observations[0].output.startsWith("x".repeat(12_000)), true);
      assert.match(observations[0].output, /delegated output truncated at 12000 characters/);
      assert.equal(observations[0].output.length < 12_100, true);
      assert.equal(observations[1].output, "[delegated output unavailable]");
    """
    run_node(script)


def test_subagent_evaluator_marks_persisted_artifact_without_output_unavailable():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(_name, attributes) {{ observations.push(attributes); }},
        persistDelegatedResult(_root, payload) {{
          return `runtime:delegated-results/${{payload.invocationId}}/child-${{payload.childIndex}}.json`;
        }},
      }});

      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "missing-artifact-output",
        input: {{ task: "Write artifact", outputContract: "artifact" }},
        content: [{{ type: "text", text: "done" }}],
        details: {{ mode: "single", results: [{{ exitCode: 0 }}] }},
        isError: false,
      }}, {{ cwd: process.cwd(), model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }});

      assert.equal(observations[0].input.artifactStatus, "persisted");
      assert.equal(observations[0].input.artifactContentStatus, "unavailable");
      assert.equal(observations[0].input.outputContract, "artifact");
      assert.equal(observations[0].output, "[delegated output unavailable]");
    """
    run_node(script)


def test_named_agent_projection_marks_provider_and_thinking_unavailable():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes) {{ observations.push({{ name, attributes }}); }},
      }});

      const input = {{ agent: "configured-reviewer", task: "Review auth" }};
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "named", input }});
      await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "named",
        input,
        content: [{{ type: "text", text: "done" }}],
        details: {{ mode: "single", results: [{{
          agent: "configured-reviewer",
          model: "openai/gpt-oss-120b",
          exitCode: 0,
          finalOutput: "done",
        }}] }},
        isError: false,
      }}, {{ cwd: process.cwd(), model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }});

      const metadata = observations[0].attributes.metadata;
      assert.equal(metadata.provider, null);
      assert.equal(metadata.model, "openai/gpt-oss-120b");
      assert.equal(metadata.target, null);
      assert.equal(metadata.thinkingLevel, null);
      assert.equal(metadata.modelDimensionsStatus, "unavailable-named-agent");
    """
    run_node(script)


def test_subagent_telemetry_schema_v2_joins_parallel_metrics_and_projections(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".pi/metrics/\n.pi/delegated-results/\n", encoding="utf-8")
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFile, readdir, stat }} from "node:fs/promises";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes, options) {{ observations.push({{ name, attributes, options }}); }},
        providerCircuit() {{}},
      }});

      const cwd = {str(tmp_path)!r};
      const input = {{ tasks: [
        {{ task: "SECRET first task", model: "openai/openai/gpt-oss-120b", outputContract: "artifact" }},
        {{ task: "SECRET second task", model: "openai-codex/gpt-5.6-luna", outputContract: "status-only" }},
      ] }};
      const ctx = {{
        cwd,
        model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }},
        sessionManager: {{ getSessionFile() {{ return "/private/parent-session.jsonl"; }} }},
      }};
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "parallel", input }}, ctx);
      const patch = await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "parallel",
        input,
        content: [{{ type: "text", text: "summary" }}],
        details: {{ mode: "parallel", results: [
          {{ exitCode: 0, model: "openai/gpt-oss-120b", finalOutput: "SECRET first output", usage: {{ turns: 1 }} }},
          {{ exitCode: 2, model: "gpt-5.6-luna", finalOutput: "SECRET partial second output", error: "HTTP 402: available credits can only cover 505 tokens", usage: {{ turns: 1 }} }},
        ] }},
        isError: false,
      }}, ctx);

      const dir = `${{cwd}}/.pi/metrics/invocations`;
      const files = await readdir(dir);
      const records = await Promise.all(files.map(async (file) => JSON.parse(await readFile(`${{dir}}/${{file}}`, "utf8"))));
      records.sort((left, right) => left.childIndex - right.childIndex);
      const ids = records.map((record) => record.invocationId);

      assert.deepEqual(records.map((record) => record.schemaVersion), [2, 2]);
      assert.equal(new Set(ids).size, 2);
      assert.equal(ids.every((id) => /^[0-9a-f-]{{36}}$/.test(id)), true);
      assert.deepEqual(records.map((record) => record.childIndex), [0, 1]);
      assert.deepEqual(records.map((record) => record.parentSessionId), ["parent-session", "parent-session"]);
      assert.deepEqual(records.map((record) => record.status), ["succeeded", "failed"]);
      assert.deepEqual(records.map((record) => record.executionOutcome), ["succeeded", "failed"]);
      assert.deepEqual(records.map((record) => record.failureClass), [null, "provider"]);
      assert.deepEqual(records.map((record) => record.providerFailureClass), [null, "credit"]);
      assert.deepEqual(records.map((record) => record.outputContract), ["artifact", "status-only"]);
      const refs = patch.details.results.map((result) => result.artifact.refs[0]);
      assert.deepEqual(refs, ids.map((id, index) => `runtime:delegated-results/${{id}}/child-${{index}}.json`));
      assert.equal(refs.every((ref) => ref.length < 256), true);
      assert.equal(patch.content.at(-1).text, `Delegated artifacts:\n- ${{refs[0]}}\n- ${{refs[1]}}`);
      assert.deepEqual(records.map((record) => record.artifactRefs), refs.map((ref) => [ref]));
      assert.deepEqual(records.map((record) => record.artifactStatus), ["persisted", "persisted"]);
      assert.deepEqual(records.map((record) => [record.provider, record.model, record.target, record.thinkingLevel]), [
        ["openai", "openai/gpt-oss-120b", "openai/openai/gpt-oss-120b", "default"],
        ["openai-codex", "gpt-5.6-luna", "openai-codex/gpt-5.6-luna", "default"],
      ]);
      assert.deepEqual(observations.map((item) => item.attributes.metadata.invocationId), ids);
      assert.deepEqual(observations.map((item) => item.attributes.metadata.executionOutcome), ["succeeded", "failed"]);
      assert.deepEqual(observations.map((item) => item.attributes.metadata.outputContract), ["artifact", "status-only"]);
      assert.deepEqual(observations.map((item) => item.attributes.input.outputContract), ["artifact", "status-only"]);
      assert.deepEqual(observations.map((item) => item.attributes.metadata.artifactRefs), refs.map((ref) => [ref]));
      assert.deepEqual(observations.map((item) => item.attributes.metadata.artifactStatus), ["persisted", "persisted"]);
      assert.deepEqual(observations.map((item) => item.attributes.metadata.providerFailureClass ?? null), [null, "credit"]);
      assert.deepEqual(observations.map((item) => {{
        const metadata = item.attributes.metadata;
        return [metadata.provider, metadata.model, metadata.target, metadata.thinkingLevel, metadata.modelDimensionsStatus];
      }}), [
        ["openai", "openai/gpt-oss-120b", "openai/openai/gpt-oss-120b", "default", "available"],
        ["openai-codex", "gpt-5.6-luna", "openai-codex/gpt-5.6-luna", "default", "available"],
      ]);
      const artifactRoot = `${{cwd}}/.pi/delegated-results`;
      const artifacts = await Promise.all(ids.map((id, index) => readFile(`${{artifactRoot}}/${{id}}/child-${{index}}.json`, "utf8").then(JSON.parse)));
      assert.deepEqual(artifacts.map((item) => [
        item.schemaVersion,
        item.invocationId,
        item.parentSessionId,
        item.childIndex,
        item.executionOutcome,
        item.outputContract,
        item.finalOutput,
        item.error,
      ]), [
        [1, ids[0], "parent-session", 0, "succeeded", "artifact", "SECRET first output", null],
        [1, ids[1], "parent-session", 1, "failed", "status-only", "SECRET partial second output", "HTTP 402: available credits can only cover 505 tokens"],
      ]);
      assert.equal((await stat(artifactRoot)).mode & 0o777, 0o700);
      assert.equal((await stat(`${{artifactRoot}}/${{ids[0]}}`)).mode & 0o777, 0o700);
      assert.equal((await stat(`${{artifactRoot}}/${{ids[0]}}/child-0.json`)).mode & 0o777, 0o600);
      assert.equal((await readdir(artifactRoot, {{ recursive: true }})).filter((name) => name.endsWith(".json")).length, 2);
      assert.equal((await readdir(artifactRoot, {{ recursive: true }})).some((name) => name.includes(".tmp")), false);
      assert.equal(JSON.stringify(records).includes("SECRET"), false);
    """
    run_node(script, env={"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})


def test_runtime_artifact_rejects_symlink_target_without_temp(tmp_path):
    script = f"""
      import assert from "node:assert/strict";
      import {{ mkdir, readFile, readdir, symlink, writeFile }} from "node:fs/promises";
      import {{ persistDelegatedResult }} from {RUNTIME_ARTIFACTS.as_uri()!r};

      const root = {str(tmp_path / "delegated-results")!r};
      const invocationId = "018f47a8-62c4-7e91-a969-7b4f6c78d308";
      const directory = `${{root}}/${{invocationId}}`;
      const outside = {str(tmp_path / "outside.json")!r};
      await mkdir(directory, {{ recursive: true }});
      await writeFile(outside, "outside");
      await symlink(outside, `${{directory}}/child-0.json`);

      await assert.rejects(() => persistDelegatedResult(root, {{
        invocationId,
        parentSessionId: null,
        childIndex: 0,
        executionOutcome: "succeeded",
        exitCode: 0,
        model: null,
        finalOutput: "private output",
        error: null,
      }}));

      assert.equal(await readFile(outside, "utf8"), "outside");
      assert.deepEqual(await readdir(directory), ["child-0.json"]);
    """
    run_node(script)


def test_parent_owned_artifacts_support_concurrent_calls(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".pi/metrics/\n.pi/delegated-results/\n", encoding="utf-8")
    script = f"""
      import assert from "node:assert/strict";
      import {{ readdir }} from "node:fs/promises";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe() {{}},
        providerCircuit() {{}},
      }});

      const cwd = {str(tmp_path)!r};
      const ctx = {{ cwd, model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }};
      const calls = [
        {{ id: "first", input: {{ task: "first", model: "openai-codex/gpt-5.6-sol" }}, output: "first output" }},
        {{ id: "second", input: {{ task: "second", model: "openai-codex/gpt-5.6-luna" }}, output: "second output" }},
      ];
      for (const call of calls) await handlers.tool_call({{ toolName: "subagent", toolCallId: call.id, input: call.input }}, ctx);
      const patches = await Promise.all(calls.map((call) => handlers.tool_result({{
        toolName: "subagent",
        toolCallId: call.id,
        input: call.input,
        content: [{{ type: "text", text: "summary" }}],
        details: {{ mode: "single", results: [{{ exitCode: 0, finalOutput: call.output }}] }},
        isError: false,
      }}, ctx)));

      const refs = patches.map((patch) => patch.details.results[0].artifact.refs[0]);
      assert.equal(new Set(refs).size, 2);
      assert.equal(refs.every((ref) => /^runtime:delegated-results[/][0-9a-f-]{{36}}[/]child-0[.]json$/.test(ref)), true);
      const files = await readdir(`${{cwd}}/.pi/delegated-results`, {{ recursive: true }});
      assert.equal(files.filter((name) => name.endsWith(".json")).length, 2);
      assert.equal(files.some((name) => name.includes(".tmp")), false);
    """
    run_node(script, env={"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})


def test_artifact_write_failure_preserves_execution_result(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".pi/metrics/\n.pi/delegated-results/\n", encoding="utf-8")
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFile, readdir }} from "node:fs/promises";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      let writes = 0;
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes) {{ observations.push({{ name, attributes }}); }},
        providerCircuit() {{}},
        async persistDelegatedResult() {{
          writes += 1;
          throw new Error("PRIVATE write path and payload");
        }},
      }});

      const cwd = {str(tmp_path)!r};
      const input = {{ task: "review", model: "openai-codex/gpt-5.6-sol" }};
      const ctx = {{ cwd, model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }};
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "write-failure", input }}, ctx);
      const patch = await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "write-failure",
        input,
        content: [{{ type: "text", text: "summary" }}],
        details: {{ mode: "single", results: [{{ exitCode: 0, finalOutput: "useful output" }}] }},
        isError: false,
      }}, ctx);

      assert.equal(writes, 1);
      assert.equal(patch.isError, undefined, "artifact failure must not change successful tool status");
      assert.equal(patch.details.results[0].finalOutput, "useful output");
      assert.deepEqual(patch.details.results[0].artifact, {{ status: "failed", refs: [], failureClass: "write" }});
      assert.equal(patch.content.at(-1).text, "Delegated artifact unavailable for child 0 (write).");
      assert.deepEqual(observations[0].attributes.metadata.artifactRefs, []);
      assert.equal(observations[0].attributes.metadata.artifactStatus, "failed");
      assert.equal(observations[0].attributes.metadata.artifactFailureClass, "write");

      const metricsDir = `${{cwd}}/.pi/metrics/invocations`;
      const metricFiles = await readdir(metricsDir);
      const metric = JSON.parse(await readFile(`${{metricsDir}}/${{metricFiles[0]}}`, "utf8"));
      assert.deepEqual(metric.artifactRefs, []);
      assert.equal(metric.artifactStatus, "failed");
      assert.equal(metric.artifactFailureClass, "write");
      assert.equal(JSON.stringify({{ patch, observations, metric }}).includes("PRIVATE write path"), false);
    """
    run_node(script, env={"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})


def test_empty_subagent_failure_emits_one_metric_and_projection(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".pi/metrics/\n.pi/delegated-results/\n", encoding="utf-8")
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFile, readdir }} from "node:fs/promises";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{
        on(name, candidate) {{ handlers[name] = candidate; }},
      }}, {{
        observe(name, attributes, options) {{ observations.push({{ name, attributes, options }}); }},
      }});

      const cwd = {str(tmp_path)!r};
      const input = {{ task: "private task", model: "openai-codex/gpt-5.6-luna" }};
      const ctx = {{ cwd, model: {{ provider: "openai-codex", id: "gpt-5.6-sol" }} }};
      await handlers.tool_call({{ toolName: "subagent", toolCallId: "empty", input }}, ctx);
      const result = await handlers.tool_result({{
        toolName: "subagent",
        toolCallId: "empty",
        input,
        content: [{{ type: "text", text: "worker failed before yielding results" }}],
        details: {{ mode: "single", results: [] }},
        isError: false,
      }}, ctx);

      const dir = `${{cwd}}/.pi/metrics/invocations`;
      let records = [];
      try {{
        const files = await readdir(dir);
        records = await Promise.all(files.map(async (file) => JSON.parse(await readFile(`${{dir}}/${{file}}`, "utf8"))));
      }} catch {{}}

      assert.equal(result.isError, true);
      assert.equal(result.details.results.length, 1);
      assert.equal(records.length, 1);
      const invocationId = records[0].invocationId;
      assert.equal(records[0].status, "failed");
      assert.equal(records[0].executionOutcome, "failed");
      assert.equal(records[0].outputContract, "unknown");
      const artifactRef = `runtime:delegated-results/${{invocationId}}/child-0.json`;
      assert.deepEqual(records[0].artifactRefs, [artifactRef]);
      assert.equal(records[0].artifactStatus, "persisted");
      assert.deepEqual([
        records[0].provider,
        records[0].model,
        records[0].target,
        records[0].thinkingLevel,
      ], ["openai-codex", "gpt-5.6-luna", "openai-codex/gpt-5.6-luna", "default"]);
      assert.equal(observations.length, 1);
      assert.equal(observations[0].attributes.metadata.invocationId, invocationId);
      assert.deepEqual(observations[0].attributes.metadata, {{
        invocationId,
        index: 0,
        provider: "openai-codex",
        model: "gpt-5.6-luna",
        target: "openai-codex/gpt-5.6-luna",
        thinkingLevel: "default",
        modelDimensionsStatus: "available",
        executionOutcome: "failed",
        outputContract: "unknown",
        artifactRefs: [artifactRef],
        artifactStatus: "persisted",
        exitCode: 1,
      }});
      assert.equal(result.details.results[0].artifact.refs[0], artifactRef);
      assert.equal(/^[0-9a-f-]{{36}}$/.test(invocationId), true);
    """
    run_node(script, env={"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})


def test_subagent_results_write_payload_free_agnt_metrics(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFile, readdir }} from "node:fs/promises";
      import {{ join }} from "node:path";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }}, {{ observe() {{}} }});
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
          model: "gemma-4-31b-it",
          finalOutput: "inherited output",
          progressSummary: {{ toolCount: 0, tokens: 9, durationMs: 100 }},
        }}], progress: [] }},
        isError: false,
      }}, {{ cwd, model: {{ provider: "olla-cloud", id: "gemma-4-31b-it" }} }});

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
      const runtimeRoot = join({str(home)!r}, ".pi", "runtime");
      const keys = await readdir(runtimeRoot);
      assert.equal(keys.length, 1);
      assert.match(keys[0], /^[0-9a-f]{{64}}$/);
      const dir = join(runtimeRoot, keys[0], "metrics", "invocations");
      const files = await readdir(dir);
      assert.equal(files.length, 4, "named profiles must be skipped when actual provider is unavailable");
      const records = await Promise.all(files.map(async (file) => JSON.parse(await readFile(`${{dir}}/${{file}}`, "utf8"))));
      const single = records.find((record) => record.target === "openai-codex/gpt-5.6-luna");
      assert.equal(single.schemaVersion, 2);
      assert.equal(/^[0-9a-f-]{{36}}$/.test(single.invocationId), true);
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
      assert.ok(records.some((record) => record.target === "olla-cloud/gemma-4-31b-it"));

      const serialized = JSON.stringify(records);
      for (const secret of [secretPrompt, secretOutput, "first private task", "second private task", "first private output", "second private output", "inherited private task", "inherited output"]) {{
        assert.equal(serialized.includes(secret), false, `persisted secret: ${{secret}}`);
      }}
    """
    run_node(script, env={
        "HOME": str(home),
        "PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent"),
    })
