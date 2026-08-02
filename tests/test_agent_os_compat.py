from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "agent-os-compat.ts"
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


def test_rpc_adapter_uses_portable_ask_and_text_todo_widget():
    assert EXTENSION.exists(), "tracked agent-os compatibility extension is required"
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};

      const handlers = {{}};
      let tool;
      const commands = new Map();
      const pi = {{
        on(name, handler) {{ handlers[name] = handler; }},
        registerTool(candidate) {{ tool = candidate; }},
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
      await commands.get("agent-os-package").handler(
        "update npm:update-package 2.0.0 npm:broken-package 2.0.0",
        {{
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
        }},
      );
      assert.equal(JSON.parse(readFileSync({str(project / ".pi" / "npm" / "node_modules" / "update-package" / "package.json")!r}, "utf8")).version, "2.0.0");
      assert.equal(JSON.parse(readFileSync({str(project / ".pi" / "npm" / "node_modules" / "broken-package" / "package.json")!r}, "utf8")).version, "1.0.0");
      assert.match(events.find((event) => event.startsWith("notify:warning:")), /broken-package/);
      assert.equal(events.at(-2), "status:clear");
      assert.equal(events.at(-1), "reload");
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_does_not_reload_when_all_updates_fail(tmp_path):
    agent_dir, project = package_fixture(tmp_path)
    (project / ".pi" / "settings.json").write_text(
        json.dumps({"packages": ["npm:broken-package"]}), encoding="utf-8"
    )
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      const commands = new Map();
      installAgentOSCompat({{
        on() {{}}, registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      await assert.rejects(
        () => commands.get("agent-os-package").handler("update npm:broken-package 2.0.0", {{
          cwd: {str(project)!r},
          isProjectTrusted: () => true,
          ui: {{ setStatus() {{}}, notify() {{}} }},
          reload: async () => assert.fail("all-failed update must not reload"),
        }}),
        new RegExp("No package updates succeeded.*broken-package"),
      );
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_rejects_managed_or_pinned_updates(tmp_path):
    agent_dir, project = package_fixture(tmp_path, ["npm:baseline-package"])
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
      const ctx = {{
        cwd: {str(project)!r},
        isProjectTrusted: () => true,
        ui: {{ setStatus() {{}}, notify() {{}} }},
        reload: async () => assert.fail("rejected update must not reload"),
      }};
      await assert.rejects(
        () => commands.get("agent-os-package").handler("update npm:baseline-package 2.0.0", ctx),
        new RegExp("managed by the Pi baseline"),
      );
      await assert.rejects(
        () => commands.get("agent-os-package").handler("update npm:pinned-package 2.0.0", ctx),
        new RegExp("pinned project package"),
      );
      await assert.rejects(
        () => commands.get("agent-os-package").handler("update npm:missing-package 2.0.0", ctx),
        new RegExp("not installed in project scope"),
      );
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_rejects_baseline_duplicate(tmp_path):
    agent_dir, project = package_fixture(tmp_path, ["npm:catalog-package@1.0.0"])
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      const commands = new Map();
      installAgentOSCompat({{
        on() {{}}, registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      const ctx = {{
        cwd: {str(project)!r},
        isProjectTrusted: () => true,
        ui: {{ setStatus() {{}}, notify() {{}} }},
        reload: async () => assert.fail("duplicate must not reload"),
      }};
      await assert.rejects(
        () => commands.get("agent-os-package").handler("install npm:catalog-package 1.2.3", ctx),
        new RegExp("already configured in user scope"),
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


def test_rpc_package_command_rejects_baseline_and_missing_removal(tmp_path):
    agent_dir, project = package_fixture(tmp_path, ["npm:baseline-package@1.0.0"])
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      const commands = new Map();
      installAgentOSCompat({{
        on() {{}}, registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      const ctx = {{
        cwd: {str(project)!r},
        isProjectTrusted: () => true,
        ui: {{ setStatus() {{}}, notify() {{}} }},
        reload: async () => assert.fail("rejected removal must not reload"),
      }};
      await assert.rejects(
        () => commands.get("agent-os-package").handler("remove npm:baseline-package", ctx),
        new RegExp("managed by the Pi baseline"),
      );
      await assert.rejects(
        () => commands.get("agent-os-package").handler("remove npm:missing-package", ctx),
        new RegExp("not installed in project scope"),
      );
    """
    run_node(script, {"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_rpc_package_command_rejects_untrusted_project(tmp_path):
    agent_dir, project = package_fixture(tmp_path)
    script = f"""
      import assert from "node:assert/strict";
      import {{ installAgentOSCompat }} from {EXTENSION.as_uri()!r};
      const commands = new Map();
      installAgentOSCompat({{
        on() {{}}, registerTool() {{}},
        registerCommand(name, command) {{ commands.set(name, command); }},
      }}, true);
      await assert.rejects(
        () => commands.get("agent-os-package").handler("install npm:catalog-package 1.2.3", {{
          cwd: {str(project)!r},
          isProjectTrusted: () => false,
          ui: {{ setStatus() {{}}, notify() {{}} }},
          reload: async () => assert.fail("untrusted install must not reload"),
        }}),
        new RegExp("Project is not trusted"),
      );
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
