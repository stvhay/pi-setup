from __future__ import annotations

from pathlib import Path

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "quality-lifecycle.ts"


def test_root_lifecycle_captures_locally_without_projection_service():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const calls = [];
      const signals = [];
      const errors = [];
      const originalError = console.error;
      console.error = (...args) => errors.push(args.join(" "));
      try {{
        install({{
          on(name, candidate) {{ handlers[name] = candidate; }},
          events: {{ emit() {{}} }},
        }}, {{
          async runAgnt(args, _cwd, signal) {{
            calls.push(args);
            signals.push(signal);
            if (args[0] === "work") return {{ schemaVersion: 1, status: "ok", activeBeadId: "pi-work.1", items: [] }};
            return {{ schemaVersion: 1, status: "linked", beadId: "pi-work.1" }};
          }},
        }});

        const ctx = {{
          cwd: process.cwd(),
          sessionManager: {{
            getSessionId() {{ return "session-1"; }},
            getSessionFile() {{ return "/private/session-1.jsonl"; }},
            getLeafId() {{ return "leaf-1"; }},
          }},
        }};
        await handlers.session_start({{ reason: "startup" }}, ctx);
        await handlers.before_agent_start({{ prompt: "PRIVATE prompt body" }});
        await handlers.agent_end({{ messages: [{{
          role: "assistant",
          content: [{{ type: "text", text: "PRIVATE output body" }}],
          stopReason: "stop",
        }}] }});
        await handlers.agent_settled({{}}, ctx);

        assert.deepEqual(calls.map((args) => args.slice(0, 2)), [
          ["work", "status"],
          ["quality", "capture"],
          ["quality", "capture"],
        ]);
        const payloads = calls
          .filter((args) => args[0] === "quality")
          .map((args) => JSON.parse(args[args.indexOf("--payload") + 1]));
        assert.deepEqual(payloads, [
          {{
            schemaVersion: 1,
            recordType: "invocation",
            sessionId: "session-1",
            beadId: "pi-work.1",
            evidenceRefs: ["invocation:session-1"],
          }},
          {{
            schemaVersion: 1,
            recordType: "invocation",
            sessionId: "session-1",
            beadId: "pi-work.1",
            evidenceRefs: ["result:leaf-1"],
          }},
        ]);
        assert.equal(JSON.stringify(payloads).includes("PRIVATE"), false);
        assert.equal(signals.every((signal) => signal instanceof AbortSignal), true);
        assert.equal(signals[0], signals[1], "one startup deadline must bound status plus capture");
        assert.notEqual(signals[1], signals[2], "settlement gets a fresh bounded deadline");
        assert.deepEqual(errors, [
          "[langfuse-projection] interactive result unavailable: pi-langfuse projection observer is unavailable",
        ]);
      }} finally {{
        console.error = originalError;
      }}
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})


def test_projection_marks_local_capture_gap_without_exposing_tool_payloads():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }}, {{
        async runAgnt(args) {{
          assert.deepEqual(args.slice(0, 2), ["work", "status"]);
          return {{ schemaVersion: 1, status: "ok", activeBeadId: null, items: [] }};
        }},
        observe(name, attributes, options) {{ observations.push({{ name, attributes, options }}); }},
      }});

      const ctx = {{
        cwd: process.cwd(),
        sessionManager: {{
          getSessionId() {{ return "session-2"; }},
          getLeafId() {{ return "leaf-2"; }},
        }},
      }};
      await handlers.session_start({{ reason: "startup" }}, ctx);
      await handlers.before_agent_start({{ prompt: "P".repeat(13_000) }});
      await handlers.tool_result({{
        toolName: "bash",
        input: {{ command: "PRIVATE failing command" }},
        details: {{ exitCode: 1, cancelled: false, timedOut: false }},
        isError: true,
      }});
      await handlers.tool_result({{
        toolName: "bash",
        input: {{ command: "PRIVATE failing command" }},
        details: {{ exitCode: 0, cancelled: false, timedOut: false }},
        isError: false,
      }});
      await handlers.agent_end({{ messages: [{{
        role: "assistant",
        content: [{{ type: "text", text: "O".repeat(13_000) }}],
        stopReason: "stop",
      }}] }});
      await handlers.agent_settled({{}}, ctx);

      assert.equal(observations.length, 1);
      const observation = observations[0];
      assert.equal(observation.name, "interactive-result");
      assert.equal(observation.attributes.input.length <= 12_000, true);
      assert.equal(observation.attributes.output.length <= 12_000, true);
      assert.equal(observation.attributes.metadata.executionOutcome, "succeeded");
      assert.equal(observation.attributes.metadata.localCaptureStatus, "unavailable");
      assert.equal(observation.attributes.metadata.localCaptureGap, "work-item-unassigned");
      assert.equal(observation.attributes.metadata.toolErrorSignals.length, 1);
      assert.equal(observation.attributes.metadata.toolErrorSignals[0].classification, "recovered");
      assert.equal(observation.attributes.metadata.toolErrorSignals[0].inputHash.length, 64);
      assert.equal(JSON.stringify(observation.attributes.metadata).includes("PRIVATE"), false);
      assert.deepEqual(observation.options, {{ asType: "agent", sessionId: "session-2", flush: true }});
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})


def test_failed_aborted_and_empty_results_keep_evaluator_semantics():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      const observations = [];
      install({{ on(name, candidate) {{ handlers[name] = candidate; }} }}, {{
        async runAgnt() {{ return {{ schemaVersion: 1, status: "ok", activeBeadId: null, items: [] }}; }},
        observe(name, attributes) {{ observations.push({{ name, attributes }}); }},
      }});
      const ctx = {{
        cwd: process.cwd(),
        sessionManager: {{ getSessionId() {{ return "session-3"; }}, getLeafId() {{ return "leaf-3"; }} }},
      }};

      await handlers.before_agent_start({{ prompt: "Fail visibly" }});
      await handlers.agent_end({{ messages: [{{
        role: "assistant",
        content: [{{ type: "text", text: "Useful partial report" }}],
        stopReason: "error",
        errorMessage: "403: OpenrouterException - Key limit exceeded (monthly limit): https://openrouter.ai/settings/keys?id=secret",
      }}] }});
      await handlers.agent_settled({{}}, ctx);

      await handlers.before_agent_start({{ prompt: "Stop work" }});
      await handlers.agent_end({{ messages: [{{
        role: "assistant",
        content: [{{ type: "text", text: "Partial work" }}],
        stopReason: "aborted",
      }}] }});
      await handlers.agent_settled({{}}, ctx);

      await handlers.before_agent_start({{ prompt: "Ask for a choice" }});
      await handlers.agent_end({{ messages: [{{ role: "assistant", content: [] }}] }});
      await handlers.agent_settled({{}}, ctx);

      assert.equal(observations.length, 2);
      assert.equal(
        observations[0].attributes.output,
        "Useful partial report\\n\\n[execution failed: upstream OpenRouter monthly limit exceeded]",
      );
      assert.deepEqual(observations[0].attributes.metadata, {{
        executionOutcome: "failed",
        failureClass: "provider",
        providerFailureClass: "quota",
        localCaptureStatus: "unavailable",
        localCaptureGap: "work-item-unassigned",
      }});
      assert.equal(observations[1].attributes.output, "Partial work");
      assert.equal(observations[1].attributes.metadata.executionOutcome, "unavailable");
      assert.equal(observations[1].attributes.metadata.localCaptureGap, "work-item-unassigned");
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})


def test_subagent_worker_skips_root_lifecycle_capture():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      let calls = 0;
      const original = process.env.PI_SUBAGENT_SOCKET;
      process.env.PI_SUBAGENT_SOCKET = "/tmp/test-subagent.sock";
      try {{
        install({{ on(name, candidate) {{ handlers[name] = candidate; }} }}, {{
          runAgnt() {{ calls += 1; throw new Error("must not run"); }},
        }});
        const ctx = {{ cwd: process.cwd(), sessionManager: {{ getSessionId() {{ return "child-1"; }} }} }};
        await handlers.session_start({{ reason: "startup" }}, ctx);
        await handlers.before_agent_start({{ prompt: "child prompt" }});
        await handlers.agent_settled({{}}, ctx);
        assert.equal(calls, 0);
      }} finally {{
        if (original === undefined) delete process.env.PI_SUBAGENT_SOCKET;
        else process.env.PI_SUBAGENT_SOCKET = original;
      }}
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(ROOT / "pi" / "agent")})
