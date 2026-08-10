from __future__ import annotations

from pathlib import Path

import pytest

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "process-restart.ts"
README = ROOT / "pi" / "README.md"
MATRIX = ROOT / "docs" / "extension-web-compatibility.md"


def loader_prelude(runtime_setup: str = "") -> str:
    return f"""
      import assert from "node:assert/strict";
      import {{ dirname, resolve }} from "node:path";
      import {{ fileURLToPath, pathToFileURL }} from "node:url";
      const piEntry = fileURLToPath(import.meta.resolve("@earendil-works/pi-coding-agent"));
      const loader = await import(pathToFileURL(resolve(dirname(piEntry), "core/extensions/loader.js")).href);
      const runtime = loader.createExtensionRuntime();
      {runtime_setup}
      const exitListenersBeforeLoad = process.listenerCount("exit");
      const loaded = await loader.loadExtensions([{str(EXTENSION)!r}], process.cwd(), undefined, runtime);
      assert.deepEqual(loaded.errors, []);
      const extension = loaded.extensions[0];
    """


def test_restart_command_and_tool_register_without_installing_exit_listener():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude(
        'runtime.sendUserMessage = (message, options) => queued.push([message, options]);\nconst queued = [];'
    ) + """
      assert.equal(process.listenerCount("exit"), exitListenersBeforeLoad);
      const command = extension.commands.get("restart");
      assert.equal(command.description, "Restart Pi and resume this session");
      const tool = extension.tools.get("restart_pi").definition;
      assert.equal(tool.label, "Restart Pi");
      const result = await tool.execute();
      assert.equal(process.listenerCount("exit"), exitListenersBeforeLoad);
      assert.deepEqual(queued, [["/restart", { deliverAs: "followUp" }]]);
      assert.equal(result.content[0].text, "Queued /restart as a follow-up command.");
    """
    run_node(script)


def test_restart_orders_graceful_shutdown_before_exact_same_session_exec():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      for (const sessionDir of [
        "/home/user/.pi/agent/sessions/--repo--",
        "/tmp/custom sessions",
      ]) {
        const events = [];
        let exitHandler;
        let execCall;
        const original = {
          argv: process.argv,
          execArgv: process.execArgv,
          execPath: process.execPath,
          execve: process.execve,
          once: process.once,
        };
        process.argv = ["/opt/node-24/bin/node", "/opt/pi/dist/cli.js"];
        process.execArgv = ["--no-warnings"];
        process.execPath = "/opt/node-24/bin/node";
        process.once = (name, listener) => {
          events.push(`once:${name}`);
          exitHandler = listener;
          return process;
        };
        process.execve = (file, args, env) => {
          events.push("execve");
          execCall = { file, args, env };
        };
        try {
          await extension.commands.get("restart").handler("", {
            mode: "tui",
            sessionManager: {
              getSessionFile: () => `${sessionDir}/session.jsonl`,
              getSessionDir: () => sessionDir,
              getSessionId: () => "session-uuid",
            },
            shutdown() { events.push("shutdown"); },
          });

          assert.deepEqual(events, ["once:exit", "shutdown"]);
          assert.equal(typeof exitHandler, "function");
          exitHandler(0);
          assert.deepEqual(events, ["once:exit", "shutdown", "execve"]);
          assert.equal(execCall.file, "/opt/node-24/bin/node");
          assert.deepEqual(execCall.args, [
            "/opt/node-24/bin/node",
            "--no-warnings",
            "/opt/pi/dist/cli.js",
            "--session-dir",
            sessionDir,
            "--session",
            "session-uuid",
          ]);
          assert.equal(execCall.env, process.env);
        } finally {
          process.argv = original.argv;
          process.execArgv = original.execArgv;
          process.execPath = original.execPath;
          process.execve = original.execve;
          process.once = original.once;
        }
      }
    """
    run_node(script)


@pytest.mark.parametrize(
    ("setup", "args", "message"),
    [
        ("", "now", "Usage: /restart"),
        ("ctx.mode = 'rpc';", "", "interactive TUI"),
        (
            "Object.defineProperty(process, 'platform', { value: 'win32', configurable: true });",
            "",
            "Node 24 on macOS or Linux",
        ),
        (
            "Object.defineProperty(process, 'release', { value: { name: 'bun' }, configurable: true });",
            "",
            "Node 24 on macOS or Linux",
        ),
        ("process.execve = undefined;", "", "process.execve"),
        ("ctx.sessionManager.getSessionFile = () => undefined;", "", "persisted session"),
        ("process.argv = [process.execPath];", "", "Pi entrypoint"),
    ],
)
def test_restart_rejects_unsupported_state_before_shutdown(setup: str, args: str, message: str):
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + f"""
      const original = {{
        argv: process.argv,
        execve: process.execve,
        once: process.once,
        platform: Object.getOwnPropertyDescriptor(process, "platform"),
        release: Object.getOwnPropertyDescriptor(process, "release"),
      }};
      let listeners = 0;
      let shutdowns = 0;
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.execve = () => {{ throw new Error("must not execute"); }};
      process.once = () => {{ listeners++; return process; }};
      const ctx = {{
        mode: "tui",
        sessionManager: {{
          getSessionFile: () => "/sessions/session.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        }},
        shutdown() {{ shutdowns++; }},
      }};
      try {{
        {setup}
        await assert.rejects(
          () => extension.commands.get("restart").handler({args!r}, ctx),
          new RegExp({message!r}),
        );
        assert.equal(listeners, 0);
        assert.equal(shutdowns, 0);
      }} finally {{
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
        Object.defineProperty(process, "platform", original.platform);
        Object.defineProperty(process, "release", original.release);
      }}
    """
    run_node(script)


def test_restart_skips_replacement_after_nonzero_shutdown_exit():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      let exitHandler;
      let execCalls = 0;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.once = (_name, listener) => { exitHandler = listener; return process; };
      process.execve = () => { execCalls++; };
      try {
        await extension.commands.get("restart").handler("", {
          mode: "tui",
          sessionManager: {
            getSessionFile: () => "/sessions/session.jsonl",
            getSessionDir: () => "/sessions",
            getSessionId: () => "session-uuid",
          },
          shutdown() {},
        });
        exitHandler(1);
        assert.equal(execCalls, 0);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_removes_listener_when_shutdown_request_throws():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      let exitHandler;
      let removed;
      const original = { argv: process.argv, execve: process.execve, off: process.off, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.once = (_name, listener) => { exitHandler = listener; return process; };
      process.off = (name, listener) => { removed = [name, listener]; return process; };
      process.execve = () => { throw new Error("must not execute"); };
      try {
        await assert.rejects(
          () => extension.commands.get("restart").handler("", {
            mode: "tui",
            sessionManager: {
              getSessionFile: () => "/sessions/session.jsonl",
              getSessionDir: () => "/sessions",
              getSessionId: () => "session-uuid",
            },
            shutdown() { throw new Error("shutdown rejected"); },
          }),
          /shutdown rejected/,
        );
        assert.deepEqual(removed, ["exit", exitHandler]);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.off = original.off;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_reports_exec_failure_synchronously():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      let exitHandler;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.once = (_name, listener) => { exitHandler = listener; return process; };
      process.execve = () => { throw new Error("replacement denied"); };
      try {
        await extension.commands.get("restart").handler("", {
          mode: "tui",
          sessionManager: {
            getSessionFile: () => "/sessions/session.jsonl",
            getSessionDir: () => "/sessions",
            getSessionId: () => "session-uuid",
          },
          shutdown() {},
        });
        assert.equal(typeof exitHandler, "function");
        exitHandler(0);
        assert.equal(process.exitCode, 1);
        process.exitCode = 0;
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    result = run_node(script)
    assert "Pi restart failed: replacement denied" in result.stderr


def test_restart_documentation_states_reload_and_platform_boundary():
    text = README.read_text(encoding="utf-8")
    matrix = MATRIX.read_text(encoding="utf-8")

    for marker in ("`/reload`", "`/restart`", "`restart_pi`", "Node 24", "macOS/Linux", "Windows", "persisted session"):
        assert marker in text
    assert "`process-restart.ts`" in matrix
    assert "TUI" in matrix
    assert "unavailable in RPC" in matrix
