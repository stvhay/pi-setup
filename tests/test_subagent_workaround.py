from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "subagent-error-workaround.ts"


def test_subagent_workaround_exposes_failures_without_touching_successes():
    assert EXTENSION.exists(), "tracked subagent failure workaround is required"

    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      let handler;
      install({{ on(name, candidate) {{
        if (name === "tool_result") handler = candidate;
      }} }});
      assert.equal(typeof handler, "function");

      const message = 'Unknown agent: "reviewer". Available: none';
      const emptyFailure = await handler({{
        toolName: "subagent",
        input: {{ agent: "reviewer", task: "Review current diff" }},
        content: [{{ type: "text", text: message }}],
        details: {{ mode: "single", results: [], progress: undefined }},
        isError: false,
      }});
      assert.equal(emptyFailure.isError, true);
      assert.equal(emptyFailure.details.results.length, 1);
      assert.equal(emptyFailure.details.results[0].agent, "reviewer");
      assert.equal(emptyFailure.details.results[0].task, "Review current diff");
      assert.equal(emptyFailure.details.results[0].exitCode, 1);
      assert.equal(emptyFailure.details.results[0].error, message);

      const childFailure = await handler({{
        toolName: "subagent",
        input: {{ task: "Fail" }},
        content: [{{ type: "text", text: "failed" }}],
        details: {{ mode: "single", results: [{{ exitCode: 2 }}] }},
        isError: false,
      }});
      assert.deepEqual(childFailure, {{ isError: true }});

      const success = await handler({{
        toolName: "subagent",
        input: {{ task: "Pass" }},
        content: [{{ type: "text", text: "passed" }}],
        details: {{ mode: "single", results: [{{ exitCode: 0 }}] }},
        isError: false,
      }});
      assert.equal(success, undefined);

      const unrelated = await handler({{
        toolName: "bash",
        content: [{{ type: "text", text: "failed" }}],
        details: {{ exitCode: 1 }},
        isError: false,
      }});
      assert.equal(unrelated, undefined);
    """
    subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
