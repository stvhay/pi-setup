from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "agent-os-compat.ts"
ARCHIMEDES_WRAPPER = ROOT / "pi" / "agent" / "extensions" / "archimedes.ts"
MATRIX = ROOT / "docs" / "extension-web-compatibility.md"
SETTINGS = ROOT / "pi" / "agent" / "settings.json"


def run_node(script: str, env: dict[str, str] | None = None):
    subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def package_fixture(tmp_path: Path, global_packages: list[str] | None = None):
    agent_dir = tmp_path / "agent"
    project = tmp_path / "project"
    agent_dir.mkdir()
    (project / ".pi").mkdir(parents=True)
    fake_npm = tmp_path / "fake-npm.mjs"
    fake_npm.write_text(
        """
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
const [action, source, flag, prefix] = process.argv.slice(2);
if (flag !== "--prefix") process.exit(2);
const spec = source.replace(/^npm:/, "");
const slash = spec.startsWith("@") ? spec.indexOf("/") : -1;
const versionAt = spec.lastIndexOf("@");
const name = versionAt > slash ? spec.slice(0, versionAt) : spec;
const version = versionAt > slash ? spec.slice(versionAt + 1) : "1.2.3";
const target = join(prefix, "node_modules", ...name.split("/"));
if (name === "broken-package") process.exit(1);
if (action === "install") {
  mkdirSync(target, { recursive: true });
  writeFileSync(join(prefix, "last-source.txt"), source);
  writeFileSync(join(target, "package.json"), JSON.stringify({ name, version }));
} else if (action === "uninstall") {
  rmSync(target, { recursive: true, force: true });
} else process.exit(2);
""",
        encoding="utf-8",
    )
    (agent_dir / "settings.json").write_text(
        json.dumps(
            {"npmCommand": ["node", str(fake_npm)], "packages": global_packages or []}
        ),
        encoding="utf-8",
    )
    return agent_dir, project


def test_rpc_adapter_leaves_ask_to_global_extension_and_uses_text_todo_widget():
    assert EXTENSION.exists(), "tracked agent-os compatibility extension is required"
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      let toolRegistrations = 0;
      const commands = new Map();
      const pi = {{
        on(name, handler) {{ handlers[name] = handler; }},
        registerTool() {{ toolRegistrations++; }},
        registerCommand(name, candidate) {{ commands.set(name, {{ name, ...candidate }}); }},
      }};
      installAgentOSCompat(pi, true);

      const command = commands.get("reload");
      assert.equal(command.name, "reload");
      const packageCommand = commands.get("agent-os-package");
      assert.equal(packageCommand.description, "Apply an approved project package change from the agent-os Packages control");
      await assert.rejects(
        () => packageCommand.handler("install ../local", {{}}),
        new RegExp("Usage: /agent-os-package"),
      );
      await assert.rejects(
        () => packageCommand.handler("install npm:valid-package latest", {{}}),
        new RegExp("Usage: /agent-os-package"),
      );
      await assert.rejects(
        () => packageCommand.handler("update npm:valid-package latest", {{}}),
        new RegExp("Usage: /agent-os-package"),
      );
      await assert.rejects(
        () => packageCommand.handler("update npm:valid-package 2.0.0 npm:valid-package 2.1.0", {{}}),
        new RegExp("Duplicate package"),
      );
      const reloadCalls = [];
      const commandContext = {{
        waitForIdle: async () => reloadCalls.push("idle"),
        reload: async () => reloadCalls.push("reload"),
      }};
      assert.equal(await command.handler("", commandContext), undefined);
      assert.deepEqual(reloadCalls, ["idle", "reload"]);
      await assert.rejects(() => command.handler("now", commandContext), new RegExp("Usage: /reload"));
      await handlers.session_start?.({{ type: "session_start" }}, {{ ui: {{}} }});
      assert.equal(toolRegistrations, 0);

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
      handlers.tool_execution_update({{
        toolName: "subagent",
        toolCallId: "peer-1",
        partialResult: {{ details: {{ progress: [
          {{ status: "running", agent: "reviewer", currentTool: "read", toolCount: 2, task: "private first task" }},
          {{ status: "completed", agent: "subagent", toolCount: 0, task: "private second task" }},
        ] }} }},
      }}, {{ ui: activityUI }});
      assert.deepEqual(activities.get("agent-os-subagent-peer-1"), [
        "→ 1. reviewer · read · 2 tools",
        "✓ 2. subagent",
      ]);
      assert.doesNotMatch(JSON.stringify([...activities.values()]), /private/);
      handlers.tool_execution_update({{ toolName: "read", toolCallId: "peer-1" }}, {{ ui: activityUI }});
      handlers.tool_execution_update({{ toolName: "subagent", toolCallId: "peer-1", partialResult: {{}} }}, {{ ui: activityUI }});
      assert.equal(activities.get("agent-os-subagent-peer-1").length, 2);
      handlers.tool_execution_end({{ toolName: "subagent", toolCallId: "peer-1" }}, {{ ui: activityUI }});
      assert.deepEqual([...activities], [
        ["agent-os-subagent-peer-2", ["Running 1 task"]],
      ]);
    """
    run_node(script)


def test_archimedes_wrapper_preserves_public_components_and_registers_one_portable_ask(tmp_path):
    assert ARCHIMEDES_WRAPPER.exists(), "tracked Archimedes wrapper is required"
    agent_dir = tmp_path / "agent"
    package_dir = agent_dir / "npm" / "node_modules" / "pi-archimedes"
    bus_dir = agent_dir / "npm" / "node_modules" / "@pi-archimedes" / "core"
    package_dir.mkdir(parents=True)
    bus_dir.mkdir(parents=True)
    (agent_dir / "npm" / "package.json").write_text('{"private":true}', encoding="utf-8")
    (package_dir / "package.json").write_text(
        json.dumps({"name": "pi-archimedes", "version": "1.8.3", "type": "module", "main": "./index.js"}),
        encoding="utf-8",
    )
    (package_dir / "index.js").write_text(
        """
export default function registerArchimedes(pi) {
  pi.on("session_start", () => {});
  pi.registerTool({ name: "manage_todo_list" });
  pi.registerTool({
    name: "ask",
    upstream: true,
    async execute(_id, params, _signal, _onUpdate, ctx) {
      (globalThis.__upstreamAskCalls ??= []).push({ params, mode: ctx.mode });
      return {
        content: [{ type: "text", text: "legacy" }],
        details: {
          usedUpstream: true,
          multi: params.questions[0].multi,
          results: params.questions.map((question) => ({
            id: question.id,
            multi: question.multi,
            selectedOptions: [question.options[0].label],
          })),
        },
      };
    },
  });
  pi.registerCommand("todos", {});
  pi.registerCommand("archimedes", {});
}
""",
        encoding="utf-8",
    )
    (bus_dir / "package.json").write_text(
        json.dumps({
            "name": "@pi-archimedes/core",
            "type": "module",
            "exports": {"./bus": "./bus.js"},
        }),
        encoding="utf-8",
    )
    (bus_dir / "bus.js").write_text(
        'export const Events = { ASK_REQUEST: "ask" }; export const getBus = () => ({ emit() {} });',
        encoding="utf-8",
    )
    script = f"""
      import assert from "node:assert/strict";
      import archimedes from {ARCHIMEDES_WRAPPER.as_uri()!r};

      globalThis.__upstreamAskCalls = [];
      for (const mode of ["tui", "rpc"]) {{
        const tools = [];
        const commands = [];
        const events = [];
        await archimedes({{
          on(name) {{ events.push(name); }},
          registerTool(tool) {{ tools.push(tool); }},
          registerCommand(name) {{ commands.push(name); }},
        }});

        assert.deepEqual(tools.map((tool) => tool.name), ["manage_todo_list", "ask"]);
        assert.equal(tools.some((tool) => tool.upstream), false);
        assert.deepEqual(commands, ["todos", "archimedes"]);
        assert.deepEqual(events, ["session_start"]);

        const ask = tools.at(-1);
        const questionSchema = ask.parameters.properties.questions.items;
        assert(questionSchema.required.includes("selectionMode"));
        assert.deepEqual(questionSchema.properties.selectionMode.enum, ["single", "multi"]);
        assert.equal("multi" in questionSchema.properties, false);

        const legacy = ask.prepareArguments({{ questions: [
          {{ id: "one", question: "One?", options: [{{ label: "A" }}], multi: false }},
          {{ id: "many", question: "Many?", options: [{{ label: "B" }}], multi: true }},
        ] }});
        assert.deepEqual(legacy.questions.map((question) => question.selectionMode), ["single", "multi"]);
        assert.equal(legacy.questions.some((question) => "multi" in question), false);

        const missing = ask.prepareArguments({{
          questions: [{{ id: "missing", question: "Missing?", options: [{{ label: "A" }}] }}],
        }});
        assert.equal(missing.questions[0].selectionMode, undefined);

        const upstreamCallsBefore = globalThis.__upstreamAskCalls.length;
        if (mode === "tui") {{
          const result = await ask.execute("single", {{ questions: [{{
            id: "target",
            question: "Choose target",
            options: [{{ label: "Alpha" }}, {{ label: "Beta" }}],
            selectionMode: "single",
            recommended: 1,
          }}] }}, undefined, undefined, {{ mode, hasUI: true, ui: {{
            select: async () => assert.fail("portable picker replaced upstream TUI"),
          }} }});
          assert.deepEqual(result.details.results[0].selectedOptions, ["Alpha"]);
          assert.equal(result.details.results[0].selectionMode, "single");
          assert.equal(result.details.usedUpstream, true);
          assert.equal(globalThis.__upstreamAskCalls.length, upstreamCallsBefore + 1);
          const upstreamCall = globalThis.__upstreamAskCalls.at(-1);
          assert.equal(upstreamCall.mode, "tui");
          assert.equal(upstreamCall.params.questions[0].multi, false);
          assert.equal("selectionMode" in upstreamCall.params.questions[0], false);
        }} else {{
          const confirmations = [false, true, true];
          const result = await ask.execute("multi", {{ questions: [{{
            id: "features",
            question: "Choose features",
            options: [{{ label: "One" }}, {{ label: "Two" }}],
            selectionMode: "multi",
          }}] }}, undefined, undefined, {{ mode, hasUI: true, ui: {{
            confirm: async () => confirmations.shift(),
            input: async () => "custom value",
          }} }});
          assert.deepEqual(result.details.results[0].selectedOptions, ["Two"]);
          assert.equal(result.details.results[0].customInput, "custom value");
          assert.equal(result.details.results[0].selectionMode, "multi");
          assert.equal(globalThis.__upstreamAskCalls.length, upstreamCallsBefore);
        }}

        const headlessCallsBefore = globalThis.__upstreamAskCalls.length;
        const headless = await ask.execute("headless", {{ questions: [{{
          id: "delegated",
          question: "Delegate?",
          options: [{{ label: "One" }}],
          selectionMode: "multi",
        }}] }}, undefined, undefined, {{ mode: "print", hasUI: false }});
        assert.deepEqual(headless.details.results[0].selectedOptions, ["One"]);
        assert.equal(headless.details.results[0].selectionMode, "multi");
        assert.equal("multi" in headless.details.results[0], false);
        assert.equal("multi" in headless.details, false);
        assert.equal(headless.details.usedUpstream, true);
        assert.equal(globalThis.__upstreamAskCalls.length, headlessCallsBefore + 1);
        const headlessCall = globalThis.__upstreamAskCalls.at(-1);
        assert.equal(headlessCall.mode, "print");
        assert.equal(headlessCall.params.questions[0].multi, true);
        assert.equal("selectionMode" in headlessCall.params.questions[0], false);
      }}
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_installs_project_package_before_reload(tmp_path):
    agent_dir, project = package_fixture(tmp_path)
    (project / ".pi" / "settings.json").write_text(
        json.dumps({"packages": [{"source": "npm:filtered-package", "skills": []}]}),
        encoding="utf-8",
    )
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFileSync }} from "node:fs";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};

      const commands = new Map();
      installAgentOSCompat({{
        on() {{}},
        registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      const events = [];
      const ctx = {{
        cwd: {str(project)!r},
        isProjectTrusted: () => true,
        ui: {{
          setStatus: (_key, value) => events.push(`status:${{value ?? "clear"}}`),
          notify: (message, type) => events.push(`notify:${{type}}:${{message}}`),
        }},
        reload: async () => {{
          const settings = JSON.parse(readFileSync({str(project / ".pi" / "settings.json")!r}, "utf8"));
          assert.deepEqual(settings.packages, [
            {{ source: "npm:filtered-package", skills: [] }},
            "npm:catalog-package",
          ]);
          events.push("reload");
        }},
      }};

      await commands.get("agent-os-package").handler("install npm:catalog-package 1.2.3", ctx);
      assert.equal(JSON.parse(readFileSync({str(project / ".pi" / "npm" / "node_modules" / "catalog-package" / "package.json")!r}, "utf8")).version, "1.2.3");
      assert.equal(readFileSync({str(project / ".pi" / "npm" / "last-source.txt")!r}, "utf8"), "catalog-package@1.2.3");
      assert.equal(events.at(-2), "status:clear");
      assert.equal(events.at(-1), "reload");
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_updates_selected_versions_and_reports_partial_failure(tmp_path):
    agent_dir, project = package_fixture(tmp_path)
    project_settings = [
        {"source": "npm:update-package", "extensions": ["extensions/index.js"]},
        "npm:broken-package",
    ]
    (project / ".pi" / "settings.json").write_text(
        json.dumps({"packages": project_settings}), encoding="utf-8"
    )
    for name in ("update-package", "broken-package"):
        package_dir = project / ".pi" / "npm" / "node_modules" / name
        package_dir.mkdir(parents=True)
        (package_dir / "package.json").write_text(
            json.dumps({"name": name, "version": "1.0.0"}), encoding="utf-8"
        )
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFileSync }} from "node:fs";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      const commands = new Map();
      installAgentOSCompat({{
        on() {{}}, registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      const events = [];
      const ctx = {{
        cwd: {str(project)!r},
        isProjectTrusted: () => true,
        ui: {{
          setStatus: (_key, value) => events.push(`status:${{value ?? "clear"}}`),
          notify: (message, type) => events.push(`notify:${{type}}:${{message}}`),
        }},
        reload: async () => {{
          const settings = JSON.parse(readFileSync({str(project / ".pi" / "settings.json")!r}, "utf8"));
          assert.deepEqual(settings.packages, {json.dumps(project_settings)});
          events.push("reload");
        }},
      }};
      await commands.get("agent-os-package").handler(
        "update npm:update-package 2.0.0 npm:broken-package 2.0.0",
        ctx,
      );
      assert.equal(JSON.parse(readFileSync({str(project / ".pi" / "npm" / "node_modules" / "update-package" / "package.json")!r}, "utf8")).version, "2.0.0");
      assert.equal(JSON.parse(readFileSync({str(project / ".pi" / "npm" / "node_modules" / "broken-package" / "package.json")!r}, "utf8")).version, "1.0.0");
      assert.match(events.find((event) => event.startsWith("notify:warning:")), /broken-package/);
      assert.equal(events.at(-2), "status:clear");
      assert.equal(events.at(-1), "reload");
      const reloads = events.filter((event) => event === "reload").length;
      await assert.rejects(
        () => commands.get("agent-os-package").handler("update npm:broken-package 2.0.0", ctx),
        new RegExp("No package updates succeeded.*broken-package"),
      );
      assert.equal(events.filter((event) => event === "reload").length, reloads);
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_rejects_disallowed_changes(tmp_path):
    agent_dir, project = package_fixture(
        tmp_path, ["npm:baseline-package", "npm:catalog-package@1.0.0"]
    )
    (project / ".pi" / "settings.json").write_text(
        json.dumps({"packages": ["npm:pinned-package@1.0.0"]}), encoding="utf-8"
    )
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      const commands = new Map();
      installAgentOSCompat({{
        on() {{}}, registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      const command = commands.get("agent-os-package");
      const ctx = {{
        cwd: {str(project)!r},
        isProjectTrusted: () => true,
        ui: {{ setStatus() {{}}, notify() {{}} }},
        reload: async () => assert.fail("rejected change must not reload"),
      }};
      for (const [args, error] of [
        ["update npm:baseline-package 2.0.0", /managed by the Pi baseline/],
        ["update npm:pinned-package 2.0.0", /pinned project package/],
        ["update npm:missing-package 2.0.0", /not installed in project scope/],
        ["install npm:catalog-package 1.2.3", /already configured in user scope/],
        ["remove npm:baseline-package", /managed by the Pi baseline/],
        ["remove npm:missing-package", /not installed in project scope/],
      ]) await assert.rejects(() => command.handler(args, ctx), error);
      await assert.rejects(
        () => command.handler("install npm:new-package 1.2.3", {{ ...ctx, isProjectTrusted: () => false }}),
        /Project is not trusted/,
      );
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_removes_project_package_before_reload(tmp_path):
    agent_dir, project = package_fixture(tmp_path)
    package_dir = project / ".pi" / "npm" / "node_modules" / "catalog-package"
    package_dir.mkdir(parents=True)
    (package_dir / "package.json").write_text(
        json.dumps({"name": "catalog-package", "version": "1.2.3"}), encoding="utf-8"
    )
    (project / ".pi" / "settings.json").write_text(
        json.dumps({"packages": ["npm:catalog-package"]}), encoding="utf-8"
    )
    script = f"""
      import assert from "node:assert/strict";
      import {{ existsSync, readFileSync }} from "node:fs";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      const commands = new Map();
      installAgentOSCompat({{
        on() {{}}, registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      const events = [];
      await commands.get("agent-os-package").handler("remove npm:catalog-package", {{
        cwd: {str(project)!r},
        isProjectTrusted: () => true,
        ui: {{ setStatus() {{}}, notify() {{}} }},
        reload: async () => {{
          const settings = JSON.parse(readFileSync({str(project / ".pi" / "settings.json")!r}, "utf8"));
          assert.deepEqual(settings.packages, []);
          assert.equal(existsSync({str(package_dir)!r}), false);
          events.push("reload");
        }},
      }});
      assert.deepEqual(events, ["reload"]);
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


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
