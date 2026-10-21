import os
from pathlib import Path

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "pi/agent/extensions/lib/subagent-report.ts"
OBSERVER = ROOT / "pi/agent/extensions/subagent-error-workaround.ts"
NATIVE_SCHEMA = Path(os.environ.get("PI_ARCHIMEDES_TEST_SCHEMA", ROOT / "forks/pi-archimedes/packages/subagent/src/tool-schema.ts"))


def test_managed_report_matches_native_schema_and_survives_sdk_composition(tmp_path):
    script = f"""
      import assert from "node:assert/strict";
      import {{ dirname, resolve }} from "node:path";
      import {{ fileURLToPath, pathToFileURL }} from "node:url";
      import {{ createRequire }} from "node:module";
      import {{ Check }} from "typebox/value";
      import {{ ExtensionRunner, SessionManager }} from "@earendil-works/pi-coding-agent";
      import {{ managedSubagentSchema, managedSubagentReport }} from {REPORT.as_uri()!r};
      import install from {OBSERVER.as_uri()!r};
      const require = createRequire(import.meta.resolve("@earendil-works/pi-coding-agent"));
      const {{ createJiti }} = require("jiti");
      const jiti = createJiti(import.meta.url);
      const {{ SUBAGENT_OUTPUT_SCHEMA, subagentStructuredContent }} = await jiti.import({str(NATIVE_SCHEMA)!r});
      const schemaBefore = JSON.stringify(SUBAGENT_OUTPUT_SCHEMA);
      const schema = managedSubagentSchema(SUBAGENT_OUTPUT_SCHEMA);
      assert.equal(JSON.stringify(SUBAGENT_OUTPUT_SCHEMA), schemaBefore);
      const piEntry = fileURLToPath(import.meta.resolve("@earendil-works/pi-coding-agent"));
      const loader = await import(pathToFileURL(resolve(dirname(piEntry), "core/extensions/loader.js")).href);
      const runtime = loader.createExtensionRuntime();
      const contracts = ["inline", "artifact", "status-only", "pass-no-findings"];
      const ext = await loader.loadExtensionFromFactory((pi) => install(pi, {{
        outputContracts: contracts, observe() {{}},
        runtimeDirectories: async () => ({{
          "delegated-results": {str(tmp_path / 'delegated')!r},
          "metrics/invocations": {str(tmp_path / 'metrics')!r},
        }}),
        providerCircuit: async () => {{}},
        persistDelegatedResult(_root, payload) {{
          return `runtime:delegated-results/${{payload.invocationId}}/child-${{payload.childIndex}}.json`;
        }},
      }}), process.cwd(), undefined, runtime);
      const runner = new ExtensionRunner([ext], runtime, process.cwd(), SessionManager.inMemory(process.cwd()), {{}});
      const errors = [];
      runner.onError((error) => errors.push(error));
      for (const outputContract of contracts) {{
        const result = {{
          agent: "subagent", model: "fixture", task: "Task", exitCode: 0,
          finalOutput: "x".repeat(13000), childTrace: {{ sessionId: "child-session" }},
          usage: {{ input: 1, output: 2, cacheRead: 0, cacheWrite: 0, cost: 0, turns: 1,
            costBreakdown: {{ input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }} }},
          execution: {{ profile: {{ mode: "agentic" }} }},
          termination: {{ reason: "completed", usageState: "complete" }},
        }};
        const input = {{ task: "Task", model: "test/fixture", outputContract }};
        const details = {{ mode: "single", results: [result] }};
        const native = subagentStructuredContent("single", [result]);
        const wrapped = managedSubagentReport(native, details, input, new Set(contracts));
        assert.equal(Check(schema, wrapped), true, JSON.stringify(wrapped));
        const composed = await runner.emitToolResult({{
          type: "tool_result", toolName: "subagent", toolCallId: outputContract,
          input, content: [{{ type: "text", text: "answer" }}], details,
          structuredContent: wrapped, isError: false,
        }});
        assert.equal(Check(schema, composed.structuredContent), true, JSON.stringify(composed));
        assert.equal(composed.structuredContent.results[0].artifact.status, "persisted");
        assert.equal(composed.structuredContent.results[0].usage.cost, 0);
        assert.equal(composed.details.results[0].finalOutput.length, 13000);
      }}
      assert.deepEqual(errors, []);
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(tmp_path / "agent")})


def test_managed_parallel_json_shares_inline_budget():
    script = f"""
      import assert from "node:assert/strict";
      import {{ managedSubagentReport }} from {REPORT.as_uri()!r};
      const results = [0, 1].map((i) => ({{ agent: "subagent", task: `Task ${{i}}`, exitCode: 0, finalOutput: "x".repeat(13000) }}));
      const native = {{ mode: "parallel", results }};
      const report = managedSubagentReport(native, native, {{ outputContract: "inline" }}, new Set(["inline"]));
      assert(report.results.reduce((n, r) => n + (r.finalOutput?.length ?? 0), 0) <= 12000);
      assert.deepEqual(report.results.map((r) => r.outputStatus), ["truncated", "truncated"]);
      assert.equal(results[1].finalOutput.length, 13000);
    """
    run_node(script)
