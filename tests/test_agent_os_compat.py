from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "agent-os-compat.ts"
MATRIX = ROOT / "docs" / "extension-web-compatibility.md"
SETTINGS = ROOT / "pi" / "agent" / "settings.json"


def run_node(script: str):
    subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )


def test_rpc_adapter_uses_portable_ask_and_text_todo_widget():
    assert EXTENSION.exists(), "tracked agent-os compatibility extension is required"
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      let tool;
      let command;
      const pi = {{
        on(name, handler) {{ handlers[name] = handler; }},
        registerTool(candidate) {{ tool = candidate; }},
        registerCommand(name, candidate) {{ command = {{ name, ...candidate }}; }},
      }};
      installAgentOSCompat(pi, true);

      assert.equal(command.name, "reload");
      const reloadCalls = [];
      const commandContext = {{
        waitForIdle: async () => reloadCalls.push("idle"),
        reload: async () => reloadCalls.push("reload"),
      }};
      assert.equal(await command.handler("", commandContext), undefined);
      assert.deepEqual(reloadCalls, ["idle", "reload"]);
      await assert.rejects(() => command.handler("now", commandContext), new RegExp("Usage: /reload"));

      let startupUICalls = 0;
      await handlers.session_start({{ type: "session_start" }}, {{
        ui: new Proxy({{}}, {{ get() {{ startupUICalls++; return () => undefined; }} }}),
      }});
      assert.equal(startupUICalls, 0);
      assert.equal(tool.name, "ask");

      const single = await tool.execute("call-1", {{ questions: [{{
        id: "target",
        question: "Choose target",
        description: "Deployment target",
        options: [{{ label: "Alpha" }}, {{ label: "Beta" }}],
        recommended: 1,
      }}] }}, undefined, undefined, {{
        ui: {{ select: async (_title, options) => options[1] }},
      }});
      assert.match(single.content[0].text, /target: Beta/);
      assert.deepEqual(single.details.results[0].selectedOptions, ["Beta"]);

      const confirmations = [false, true, true];
      const multi = await tool.execute("call-2", {{ questions: [{{
        id: "features",
        question: "Choose features",
        options: [{{ label: "One" }}, {{ label: "Two" }}],
        multi: true,
      }}] }}, undefined, undefined, {{
        ui: {{
          confirm: async () => confirmations.shift(),
          input: async () => "custom value",
        }},
      }});
      assert.deepEqual(multi.details.results[0].selectedOptions, ["Two"]);
      assert.equal(multi.details.results[0].customInput, "custom value");

      let widget;
      handlers.tool_execution_start({{
        toolName: "manage_todo_list",
        args: {{ todoList: [
          {{ id: 1, title: "Inspect", status: "completed" }},
          {{ id: 2, title: "Adapt", status: "in-progress" }},
        ] }},
      }}, {{ ui: {{ setWidget: (key, lines) => {{ widget = {{ key, lines }}; }} }} }});
      assert.equal(widget.key, "agent-os-todos");
      assert.deepEqual(widget.lines, ["✓ Inspect", "→ Adapt"]);
      handlers.tool_execution_start({{
        toolName: "manage_todo_list",
        args: {{ operation: "read" }},
      }}, {{ ui: {{ setWidget: (key, lines) => {{ widget = {{ key, lines }}; }} }} }});
      assert.deepEqual(widget.lines, ["✓ Inspect", "→ Adapt"]);

      handlers.tool_execution_start({{
        toolName: "manage_todo_list",
        args: {{ todoList: [
          {{ id: 1, title: "Inspect", status: "completed" }},
          {{ id: 2, title: "Adapt", status: "completed" }},
        ] }},
      }}, {{ ui: {{ setWidget: (key, lines) => {{ widget = {{ key, lines }}; }} }} }});
      assert.equal(widget.key, "agent-os-todos");
      assert.equal(widget.lines, undefined);

      handlers.tool_execution_start({{
        toolName: "manage_todo_list",
        args: {{ todoList: [] }},
      }}, {{ ui: {{ setWidget: (key, lines) => {{ widget = {{ key, lines }}; }} }} }});
      assert.equal(widget.lines, undefined);

      const activities = new Map();
      const activityUI = {{ setWidget(key, lines) {{
        if (lines === undefined) activities.delete(key);
        else activities.set(key, lines);
      }} }};
      handlers.tool_execution_start({{
        toolName: "subagent",
        toolCallId: "peer-1",
        args: {{ tasks: [{{ task: "private first task" }}, {{ task: "private second task" }}] }},
      }}, {{ ui: activityUI }});
      handlers.tool_execution_start({{
        toolName: "subagent",
        toolCallId: "peer-2",
        args: {{ task: "private third task" }},
      }}, {{ ui: activityUI }});
      assert.deepEqual([...activities], [
        ["agent-os-subagent-peer-1", ["Running 2 tasks"]],
        ["agent-os-subagent-peer-2", ["Running 1 task"]],
      ]);
      assert.doesNotMatch(JSON.stringify([...activities.values()]), /private/);
      handlers.tool_execution_end({{ toolName: "subagent", toolCallId: "peer-1" }}, {{ ui: activityUI }});
      assert.deepEqual([...activities], [
        ["agent-os-subagent-peer-2", ["Running 1 task"]],
      ]);
    """
    run_node(script)


def test_adapter_stays_inactive_outside_rpc_mode():
    assert EXTENSION.exists(), "tracked agent-os compatibility extension is required"
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      let registrations = 0;
      installAgentOSCompat({{
        on() {{ registrations++; }},
        registerTool() {{ registrations++; }},
        registerCommand() {{ registrations++; }},
      }}, false);
      assert.equal(registrations, 0);
    """
    run_node(script)


def test_compatibility_matrix_covers_every_configured_package():
    assert MATRIX.exists(), "extension web compatibility matrix is required"
    text = MATRIX.read_text(encoding="utf-8")
    packages = json.loads(SETTINGS.read_text(encoding="utf-8"))["packages"]
    for package in packages:
        source = package["source"] if isinstance(package, dict) else package
        assert f"`{source}`" in text, f"missing compatibility row for {source}"


def test_tracked_extensions_use_only_portable_ui_calls():
    forbidden = {
        ".ui.custom(",
        ".ui.setEditorComponent(",
        ".ui.setHeader(",
        ".ui.setFooter(",
        ".ui.onTerminalInput(",
    }
    for path in (ROOT / "pi" / "agent" / "extensions").glob("*.ts"):
        source = path.read_text(encoding="utf-8")
        found = sorted(call for call in forbidden if call in source)
        assert not found, f"{path.name} uses TUI-only APIs: {found}"
