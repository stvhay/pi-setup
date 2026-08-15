from __future__ import annotations

import json
from pathlib import Path

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "agent-os-compat.ts"
ARCHIMEDES_WRAPPER = ROOT / "pi" / "agent" / "extensions" / "archimedes.ts"
MATRIX = ROOT / "docs" / "extension-web-compatibility.md"
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
LANGFUSE_QUALITY_PORT = ROOT / ".pi" / "plans" / "2026-08-15-pi-langfuse-quality-port-contract.md"
ARCHIMEDES_RESULT_PORT = ROOT / ".pi" / "plans" / "2026-08-15-pi-archimedes-result-port-contract.md"


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

      handlers.tool_execution_start({{
        toolName: "read",
        toolCallId: "read-1",
        args: {{ path: "/private/secret" }},
      }}, {{ ui: activityUI }});
      handlers.tool_execution_start({{
        toolName: "bash",
        toolCallId: "bash-1",
        args: {{ command: "echo private" }},
      }}, {{ ui: activityUI }});
      assert.deepEqual(activities.get("agent-os-activity"), ["→ read", "→ bash"]);
      assert.doesNotMatch(JSON.stringify(activities.get("agent-os-activity")), /private|secret|echo/);

      handlers.tool_execution_end({{ toolName: "read", toolCallId: "read-1" }}, {{ ui: activityUI }});
      assert.deepEqual(activities.get("agent-os-activity"), ["→ bash"]);
      handlers.tool_execution_end({{ toolName: "bash", toolCallId: "bash-1" }}, {{ ui: activityUI }});
      assert.equal(activities.has("agent-os-activity"), false);
    """
    run_node(script)


def test_archimedes_custom_input_wrapper_preserves_public_components_and_one_portable_ask(tmp_path):
    assert ARCHIMEDES_WRAPPER.exists(), "tracked Archimedes wrapper is required"
    agent_dir = tmp_path / "agent"
    package_dir = agent_dir / "npm" / "node_modules" / "pi-archimedes"
    bus_dir = agent_dir / "npm" / "node_modules" / "@pi-archimedes" / "core"
    subagent_dir = agent_dir / "npm" / "node_modules" / "@pi-archimedes" / "subagent"
    package_dir.mkdir(parents=True)
    bus_dir.mkdir(parents=True)
    subagent_dir.mkdir(parents=True)
    (agent_dir / "bin").mkdir()
    (agent_dir / "bin" / "agnt").symlink_to(ROOT / "pi" / "agent" / "bin" / "agnt")
    (agent_dir / "npm" / "package.json").write_text('{"private":true}', encoding="utf-8")
    (package_dir / "package.json").write_text(
        json.dumps({"name": "pi-archimedes", "version": "2.0.1", "type": "module", "main": "./index.js"}),
        encoding="utf-8",
    )
    (agent_dir / "catalog.json").write_text(
        json.dumps({
            "schemaVersion": 1,
            "families": {
                "metered": {"venues": [{
                    "target": "openrouter/anthropic/claude-opus-5",
                    "billingClass": "metered",
                }]},
                "subscription": {"venues": [{
                    "target": "openai-codex/gpt-5.6-terra",
                    "billingClass": "subscription",
                }]},
            },
        }),
        encoding="utf-8",
    )
    (package_dir / "index.js").write_text(
        """
export default function registerArchimedes(pi) {
  pi.registerTool({ name: "manage_todo_list" });
  pi.on("session_start", () => {
    pi.registerTool({
    name: "subagent",
    label: "Upstream Subagent",
    description: "Delegate through upstream execution",
    promptSnippet: "Delegate work",
    promptGuidelines: ["Use subagent for delegation."],
    parameters: {
      type: "object",
      properties: {
        agent: { type: "string" },
        task: { type: "string" },
        model: { type: "string" },
        mode: { type: "string", enum: ["agentic", "one-shot"] },
        limits: { type: "object", properties: { maxOutputTokens: { type: "integer" } } },
        async: { type: "boolean" },
        cwd: { type: "string" },
        tasks: { type: "array", items: { type: "object", properties: {
          agent: { type: "string" }, task: { type: "string" }, model: { type: "string" },
          mode: { type: "string", enum: ["agentic", "one-shot"] },
          limits: { type: "object", properties: { maxOutputTokens: { type: "integer" } } },
          cwd: { type: "string" },
        }, required: ["task"] } },
      },
    },
    prepareArguments(args) { return args; },
    renderCall() { return "upstream-call"; },
    renderResult() { return "upstream-result"; },
    async execute(_id, params) {
      (globalThis.__upstreamSubagentCalls ??= []).push(params);
      return { content: [{ type: "text", text: "delegated" }], details: { upstream: true, params } };
    },
    });
  });
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
    (subagent_dir / "package.json").write_text(
        json.dumps({
            "name": "@pi-archimedes/subagent",
            "version": "2.0.1",
            "type": "module",
            "main": "./index.js",
        }),
        encoding="utf-8",
    )
    (subagent_dir / "index.js").write_text("export default () => {};\n", encoding="utf-8")
    (subagent_dir / "agents.js").write_text(
        """
export function discoverAgents() {
  return [
    { name: "metered-agent", model: "openrouter/anthropic/claude-opus-5" },
    { name: "subscription-agent", model: "openai-codex/gpt-5.6-terra" },
  ];
}
export function findAgent(agents, name) { return agents.find((agent) => agent.name === name); }
""",
        encoding="utf-8",
    )
    script = f"""
      import assert from "node:assert/strict";
      import archimedes from {ARCHIMEDES_WRAPPER.as_uri()!r};

      globalThis.__upstreamAskCalls = [];
      globalThis.__upstreamSubagentCalls = [];
      for (const [mode, configuredCap] of [["tui", undefined], ["rpc", "12000"]]) {{
        if (configuredCap === undefined) delete process.env.PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS;
        else process.env.PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS = configuredCap;
        const expectedCap = configuredCap === undefined ? 16384 : Number(configuredCap);
        const tools = [];
        const commands = [];
        const events = [];
        await archimedes({{
          on(name, handler) {{ events.push({{ name, handler }}); }},
          registerTool(tool) {{ tools.push(tool); }},
          registerCommand(name) {{ commands.push(name); }},
        }});

        assert.deepEqual(tools.map((tool) => tool.name), ["manage_todo_list", "ask"]);
        assert.equal(tools.some((tool) => tool.name === "subagent"), false);
        assert.deepEqual(commands, ["todos", "archimedes"]);
        assert.deepEqual(events.map((event) => event.name), ["session_start"]);
        for (const event of events) await event.handler({{}}, {{}});
        assert.deepEqual(tools.map((tool) => tool.name), ["manage_todo_list", "ask", "subagent"]);
        assert.equal(tools.some((tool) => tool.upstream), false);

        const subagent = tools.find((tool) => tool.name === "subagent");
        assert.equal(subagent.label, "Upstream Subagent");
        assert.equal(subagent.description, "Delegate through upstream execution");
        assert.equal(subagent.promptSnippet, "Delegate work");
        assert.deepEqual(subagent.promptGuidelines, ["Use subagent for delegation."]);
        assert.equal(subagent.renderCall(), "upstream-call");
        assert.equal(subagent.renderResult(), "upstream-result");
        assert.equal(subagent.prepareArguments({{ task: "prepared" }}).task, "prepared");
        assert.deepEqual(subagent.parameters.properties.outputContract.enum, ["inline", "artifact", "status-only", "pass-no-findings"]);
        assert.deepEqual(subagent.parameters.properties.tasks.items.properties.outputContract.enum, ["inline", "artifact", "status-only", "pass-no-findings"]);
        assert.deepEqual(subagent.parameters.properties.sourceAccess.enum, ["self-contained", "repository"]);
        assert.deepEqual(subagent.parameters.properties.tasks.items.properties.sourceAccess.enum, ["self-contained", "repository"]);
        assert.deepEqual(subagent.parameters.properties.meteredJustification.enum, ["quality-benefit", "missing-capability"]);
        assert.equal(subagent.parameters.properties.estimatedCostUsd.type, "number");
        assert.equal(subagent.parameters.properties.maxMarginalUsd.type, "number");
        assert.equal(subagent.parameters.properties.async.type, "boolean");
        assert.equal(subagent.parameters.properties.cwd.type, "string");
        assert.equal(subagent.parameters.properties.tasks.items.properties.cwd.type, "string");

        const singleDelegation = await subagent.execute("single-contract", {{
          task: "Review auth",
          outputContract: "status-only",
        }}, undefined, undefined, {{ mode }});
        assert.equal(singleDelegation.details.upstream, true);
        assert.deepEqual(globalThis.__upstreamSubagentCalls.at(-1), {{ task: "Review auth" }});

        const parallelDelegation = await subagent.execute("parallel-contract", {{
          tasks: [
            {{ task: "Review auth", outputContract: "inline" }},
            {{ task: "Check tests", outputContract: "artifact" }},
          ],
        }}, undefined, undefined, {{ mode }});
        assert.equal(parallelDelegation.details.upstream, true);
        assert.deepEqual(globalThis.__upstreamSubagentCalls.at(-1), {{
          tasks: [{{ task: "Review auth" }}, {{ task: "Check tests" }}],
        }});

        const callsBeforeRepositoryRejection = globalThis.__upstreamSubagentCalls.length;
        const repositoryOneShot = await subagent.execute("repository-one-shot", {{
          task: "Inspect auth callers",
          model: "openai-codex/gpt-5.6-terra",
          mode: "one-shot",
          sourceAccess: "repository",
        }}, undefined, undefined, {{ mode }});
        assert.equal(repositoryOneShot.isError, true);
        assert.match(repositoryOneShot.content[0].text, /repository access requires agentic/i);
        assert.equal(globalThis.__upstreamSubagentCalls.length, callsBeforeRepositoryRejection);

        const incompleteMeteredRepository = await subagent.execute("metered-repository-incomplete", {{
          task: "Inspect auth callers",
          model: "openrouter/anthropic/claude-opus-5",
          mode: "agentic",
          sourceAccess: "repository",
        }}, undefined, undefined, {{ mode }});
        assert.equal(incompleteMeteredRepository.isError, true);
        assert.match(incompleteMeteredRepository.content[0].text, /justification, estimated cost, and bounded limits/i);

        const overBudgetMeteredRepository = await subagent.execute("metered-repository-over-budget", {{
          task: "Inspect auth callers",
          model: "openrouter/anthropic/claude-opus-5",
          mode: "agentic",
          sourceAccess: "repository",
          meteredJustification: "quality-benefit",
          estimatedCostUsd: 0.06,
          limits: {{ maxProviderRequests: 6, maxTotalTokens: 60000, maxCostUsd: 0.05, maxDurationMs: 300000 }},
        }}, undefined, undefined, {{ mode }});
        assert.equal(overBudgetMeteredRepository.isError, true);
        assert.match(overBudgetMeteredRepository.content[0].text, /estimated cost exceeds/i);

        const allowedMeteredRepository = await subagent.execute("metered-repository-bounded", {{
          task: "Inspect auth callers",
          model: "openrouter/anthropic/claude-opus-5",
          mode: "agentic",
          sourceAccess: "repository",
          meteredJustification: "quality-benefit",
          estimatedCostUsd: 0.04,
          limits: {{ maxProviderRequests: 6, maxTotalTokens: 60000, maxCostUsd: 0.05, maxDurationMs: 300000 }},
          outputContract: "inline",
        }}, undefined, undefined, {{ mode }});
        assert.equal(allowedMeteredRepository.details.upstream, true);
        assert.deepEqual(globalThis.__upstreamSubagentCalls.at(-1), {{
          task: "Inspect auth callers",
          model: "openrouter/anthropic/claude-opus-5",
          mode: "agentic",
          limits: {{ maxProviderRequests: 6, maxTotalTokens: 60000, maxCostUsd: 0.05, maxDurationMs: 300000 }},
        }});

        const aggregateMeteredRepository = await subagent.execute("metered-repository-aggregate", {{
          sourceAccess: "repository",
          maxMarginalUsd: 0.05,
          tasks: [
            {{ task: "Inspect auth", model: "openrouter/anthropic/claude-opus-5", meteredJustification: "quality-benefit", estimatedCostUsd: 0.03, limits: {{ maxProviderRequests: 6, maxTotalTokens: 60000, maxCostUsd: 0.03, maxDurationMs: 300000 }} }},
            {{ task: "Inspect tests", model: "openrouter/anthropic/claude-opus-5", meteredJustification: "quality-benefit", estimatedCostUsd: 0.03, limits: {{ maxProviderRequests: 6, maxTotalTokens: 60000, maxCostUsd: 0.03, maxDurationMs: 300000 }} }},
          ],
        }}, undefined, undefined, {{ mode }});
        assert.equal(aggregateMeteredRepository.isError, true);
        assert.match(aggregateMeteredRepository.content[0].text, /aggregate estimated cost exceeds/i);

        const allowedMeteredFanout = await subagent.execute("metered-repository-fanout", {{
          sourceAccess: "repository",
          maxMarginalUsd: 0.06,
          tasks: [
            {{ task: "Inspect auth", model: "openrouter/anthropic/claude-opus-5", meteredJustification: "quality-benefit", estimatedCostUsd: 0.03, limits: {{ maxProviderRequests: 6, maxTotalTokens: 60000, maxCostUsd: 0.03, maxDurationMs: 300000 }} }},
            {{ task: "Inspect tests", model: "openrouter/anthropic/claude-opus-5", meteredJustification: "quality-benefit", estimatedCostUsd: 0.03, limits: {{ maxProviderRequests: 6, maxTotalTokens: 60000, maxCostUsd: 0.03, maxDurationMs: 300000 }} }},
          ],
        }}, undefined, undefined, {{ mode }});
        assert.equal(allowedMeteredFanout.details.upstream, true);
        assert.equal("sourceAccess" in globalThis.__upstreamSubagentCalls.at(-1), false);
        assert.equal("maxMarginalUsd" in globalThis.__upstreamSubagentCalls.at(-1), false);
        assert.equal("estimatedCostUsd" in globalThis.__upstreamSubagentCalls.at(-1).tasks[0], false);

        const allowedMeteredReview = await subagent.execute("metered-review-one-shot", {{
          task: "Review auth",
          model: "openrouter/anthropic/claude-opus-5",
          mode: "one-shot",
        }}, undefined, undefined, {{ mode }});
        assert.equal(allowedMeteredReview.details.upstream, true);
        assert.deepEqual(globalThis.__upstreamSubagentCalls.at(-1), {{
          task: "Review auth",
          model: "openrouter/anthropic/claude-opus-5",
          mode: "one-shot",
          limits: {{ maxOutputTokens: expectedCap }},
        }});

        const allowedMeteredNonReview = await subagent.execute("metered-research", {{
          task: "Map auth callers",
          model: "openrouter/anthropic/claude-opus-5",
        }}, undefined, undefined, {{ mode }});
        assert.equal(allowedMeteredNonReview.details.upstream, true);
        assert.deepEqual(globalThis.__upstreamSubagentCalls.at(-1), {{
          task: "Map auth callers",
          model: "openrouter/anthropic/claude-opus-5",
        }});

        await subagent.execute("metered-one-shot", {{
          task: "Map auth callers",
          mode: "one-shot",
          model: "openrouter/anthropic/claude-opus-5",
          outputContract: "inline",
        }}, undefined, undefined, {{ mode }});
        assert.deepEqual(globalThis.__upstreamSubagentCalls.at(-1), {{
          task: "Map auth callers",
          mode: "one-shot",
          model: "openrouter/anthropic/claude-opus-5",
          limits: {{ maxOutputTokens: expectedCap }},
        }});

        await subagent.execute("metered-tighter", {{
          task: "Map auth callers",
          mode: "one-shot",
          model: "openrouter/anthropic/claude-opus-5",
          limits: {{ maxOutputTokens: 8192 }},
        }}, undefined, undefined, {{ mode }});
        assert.equal(globalThis.__upstreamSubagentCalls.at(-1).limits.maxOutputTokens, 8192);

        await subagent.execute("metered-wider", {{
          task: "Map auth callers",
          mode: "one-shot",
          model: "openrouter/anthropic/claude-opus-5",
          limits: {{ maxOutputTokens: 32768 }},
        }}, undefined, undefined, {{ mode }});
        assert.equal(globalThis.__upstreamSubagentCalls.at(-1).limits.maxOutputTokens, expectedCap);

        await subagent.execute("subscription-one-shot", {{
          task: "Map auth callers",
          mode: "one-shot",
          model: "openai-codex/gpt-5.6-terra",
        }}, undefined, undefined, {{ mode }});
        assert.equal("limits" in globalThis.__upstreamSubagentCalls.at(-1), false);

        await subagent.execute("inherited-metered-one-shot", {{
          task: "Map auth callers",
          mode: "one-shot",
        }}, undefined, undefined, {{ mode, model: {{ provider: "openrouter", id: "anthropic/claude-opus-5" }} }});
        assert.equal(globalThis.__upstreamSubagentCalls.at(-1).limits.maxOutputTokens, expectedCap);

        await subagent.execute("registry-alias-metered-one-shot", {{
          task: "Map auth callers",
          mode: "one-shot",
          model: "anthropic/claude-opus-5",
        }}, undefined, undefined, {{ mode, modelRegistry: {{ getAll: () => [
          {{ provider: "openrouter", id: "anthropic/claude-opus-5" }},
        ] }} }});
        assert.equal(globalThis.__upstreamSubagentCalls.at(-1).limits.maxOutputTokens, expectedCap);

        await subagent.execute("unknown-one-shot", {{
          task: "Map auth callers",
          mode: "one-shot",
          model: "openrouter/unknown/model",
        }}, undefined, undefined, {{ mode }});
        assert.equal("limits" in globalThis.__upstreamSubagentCalls.at(-1), false);

        await subagent.execute("named-metered-one-shot", {{
          agent: "metered-agent",
          task: "Map auth callers",
          mode: "one-shot",
        }}, undefined, undefined, {{ mode, model: {{ provider: "openai-codex", id: "gpt-5.6-terra" }} }});
        assert.equal(globalThis.__upstreamSubagentCalls.at(-1).limits.maxOutputTokens, expectedCap);

        await subagent.execute("named-subscription-one-shot", {{
          agent: "subscription-agent",
          task: "Map auth callers",
          mode: "one-shot",
        }}, undefined, undefined, {{ mode, model: {{ provider: "openrouter", id: "anthropic/claude-opus-5" }} }});
        assert.equal("limits" in globalThis.__upstreamSubagentCalls.at(-1), false);

        await subagent.execute("mixed-parallel-one-shot", {{
          mode: "one-shot",
          tasks: [
            {{ task: "Metered", model: "openrouter/anthropic/claude-opus-5", outputContract: "inline" }},
            {{ task: "Subscription", model: "openai-codex/gpt-5.6-terra", outputContract: "artifact" }},
            {{ task: "Agentic metered", mode: "agentic", model: "openrouter/anthropic/claude-opus-5" }},
            {{ task: "Named metered", agent: "metered-agent" }},
          ],
        }}, undefined, undefined, {{ mode }});
        assert.deepEqual(globalThis.__upstreamSubagentCalls.at(-1), {{
          mode: "one-shot",
          tasks: [
            {{ task: "Metered", model: "openrouter/anthropic/claude-opus-5", limits: {{ maxOutputTokens: expectedCap }} }},
            {{ task: "Subscription", model: "openai-codex/gpt-5.6-terra" }},
            {{ task: "Agentic metered", mode: "agentic", model: "openrouter/anthropic/claude-opus-5" }},
            {{ task: "Named metered", agent: "metered-agent", limits: {{ maxOutputTokens: expectedCap }} }},
          ],
        }});

        const allowedSubscriptionReview = await subagent.execute("subscription-review", {{
          task: "Review auth",
          model: "openai-codex/gpt-5.6-terra",
        }}, undefined, undefined, {{ mode }});
        assert.equal(allowedSubscriptionReview.details.upstream, true);

        for (const task of ["Fix reviewer avatar rendering", "Summarize App Store reviews"]) {{
          const incidentalReviewWord = await subagent.execute("incidental-review-word", {{
            task,
            model: "openrouter/anthropic/claude-opus-5",
          }}, undefined, undefined, {{ mode }});
          assert.equal(incidentalReviewWord.details.upstream, true);
        }}

        const noContext = await subagent.execute("no-context", {{
          task: "Map auth callers",
          model: "openrouter/anthropic/claude-opus-5",
        }}, undefined, undefined, undefined);
        assert.equal(noContext.details.upstream, true);

        const ask = tools.find((tool) => tool.name === "ask");
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
          assert.equal(result.details.qualityResults[0].category, "answer");
          assert.equal(result.details.qualityResults[0].retention, "session");
          assert.equal(result.details.usedUpstream, true);
          assert.equal(globalThis.__upstreamAskCalls.length, upstreamCallsBefore + 1);
          const upstreamCall = globalThis.__upstreamAskCalls.at(-1);
          assert.equal(upstreamCall.mode, "tui");
          assert.equal(upstreamCall.params.questions[0].multi, false);
          assert.equal("selectionMode" in upstreamCall.params.questions[0], false);
        }} else {{
          const confirmations = [false, true, true];
          const customInputs = ["   ", "custom value"];
          const warnings = [];
          const result = await ask.execute("multi", {{ questions: [{{
            id: "features",
            question: "Choose features",
            options: [{{ label: "One" }}, {{ label: "Two" }}],
            selectionMode: "multi",
          }}] }}, undefined, undefined, {{ mode, hasUI: true, ui: {{
            confirm: async () => confirmations.shift(),
            input: async () => customInputs.shift(),
            notify: (message, level) => warnings.push([message, level]),
          }} }});
          assert.deepEqual(result.details.results[0].selectedOptions, ["Two"]);
          assert.equal(result.details.results[0].customInput, "custom value");
          assert.equal(result.details.results[0].selectionMode, "multi");
          assert.equal(result.details.qualityResults[0].category, "answer");
          assert.equal(result.details.qualityResults[0].authority.status, "none");
          assert.equal(result.content[0].text.includes("features: [Two] + Other: “custom value”"), true);
          assert.deepEqual(warnings, [["Custom response cannot be empty.", "warning"]]);

          const singleInputs = ["", "typed alternative"];
          const singleWarnings = [];
          const custom = await ask.execute("custom", {{ questions: [{{ id: "custom", question: "Custom?", options: [{{ label: "A" }}], selectionMode: "single" }}] }}, undefined, undefined, {{ mode, hasUI: true, ui: {{
            select: async (_title, options) => options.at(-1),
            input: async () => singleInputs.shift(),
            notify: (message, level) => singleWarnings.push([message, level]),
          }} }});
          assert.deepEqual(custom.details.results[0].selectedOptions, []);
          assert.equal(custom.details.results[0].customInput, "typed alternative");
          assert.match(custom.content[0].text, /custom: “typed alternative”/);
          assert.deepEqual(singleWarnings, [["Custom response cannot be empty.", "warning"]]);
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

      process.env.PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS = "off";
      const offTools = [];
      const offEvents = [];
      await archimedes({{
        on(name, handler) {{ offEvents.push({{ name, handler }}); }},
        registerTool(tool) {{ offTools.push(tool); }},
        registerCommand() {{}},
      }});
      for (const event of offEvents) await event.handler({{}}, {{}});
      await offTools.find((tool) => tool.name === "subagent").execute("off", {{
        task: "Map auth callers",
        mode: "one-shot",
        model: "openrouter/anthropic/claude-opus-5",
      }}, undefined, undefined, {{}});
      assert.equal("limits" in globalThis.__upstreamSubagentCalls.at(-1), false);

      process.env.PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS = "-1";
      await assert.rejects(() => archimedes({{}}), /must be a positive integer, 0, or off/);
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
        row = next((line for line in text.splitlines() if f"`{source}`" in line), None)
        assert row, f"missing compatibility row for {source}"
        if "@" not in source.split(":", 1)[1].lstrip("@"):
            assert "Intentional rolling" in row
            assert "2026-08-13" in row


def test_pi_langfuse_quality_port_contract_is_public_bounded_and_non_authoritative():
    contract = LANGFUSE_QUALITY_PORT.read_text(encoding="utf-8")

    for public_export in (
        '"./quality"',
        "createObservationCapturePort",
        "createServiceEvidencePort",
    ):
        assert public_export in contract
    for capture_owner in (
        "capture policy and redaction",
        "observation lifecycle",
        "session propagation",
        "export and requested flush",
        "completion and gaps",
    ):
        assert capture_owner in contract
    for evidence in (
        "traces",
        "observations",
        "scores",
        "annotation queue",
        "score configs",
        "complete",
        "gaps",
    ):
        assert evidence in contract
    assert "Authorization, Bead closeout, and pi-setup quality policy are out of scope" in contract


def test_pi_archimedes_result_port_contract_is_public_transport_preserving_and_non_authoritative():
    assert ARCHIMEDES_RESULT_PORT.exists(), "tracked pi-archimedes result port contract is required"
    contract = ARCHIMEDES_RESULT_PORT.read_text(encoding="utf-8")

    for public_export in (
        '"./types"',
        '"./agents"',
        '"./bus"',
    ):
        assert public_export in contract
    for public_type in (
        "SubagentOutputContract",
        "SubagentLimits",
        "SubagentTermination",
        "SubagentUsage",
        "SubagentChildTraceRef",
        "SubagentResult",
        "SubagentDetails",
        "SubagentToolResult",
        "ArchimedesEventPayloadMap",
        "AskRequestPayload",
    ):
        assert public_type in contract
    assert "`details.results[]` remains the canonical complete per-child execution evidence" in contract
    assert "Pi `tool_result` remains the only result transport" in contract
    assert "Routing, billing, authority, and pi-setup quality policy are out of scope" in contract


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
