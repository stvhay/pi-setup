from __future__ import annotations

from pathlib import Path

import pytest

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "process-restart.ts"
NVIM_EXTENSION = ROOT / "pi" / "agent" / "extensions" / "nvim.ts"
README = ROOT / "pi" / "README.md"
MATRIX = ROOT / "docs" / "extension-web-compatibility.md"


def loader_prelude(runtime_setup: str = "", extension_path: Path = EXTENSION) -> str:
    return f"""
      import assert from "node:assert/strict";
      import {{ dirname, resolve }} from "node:path";
      import {{ fileURLToPath, pathToFileURL }} from "node:url";
      const piEntry = fileURLToPath(import.meta.resolve("@earendil-works/pi-coding-agent"));
      const loader = await import(pathToFileURL(resolve(dirname(piEntry), "core/extensions/loader.js")).href);
      const runtime = loader.createExtensionRuntime();
      {runtime_setup}
      const exitListenersBeforeLoad = process.listenerCount("exit");
      const loaded = await loader.loadExtensions([{str(extension_path)!r}], process.cwd(), undefined, runtime);
      assert.deepEqual(loaded.errors, []);
      const extension = loaded.extensions[0];
    """


def test_restart_command_and_tool_share_direct_process_replacement():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude(
        'runtime.sendUserMessage = () => { throw new Error("restart command was queued instead of executed"); };'
    ) + """
      assert.equal(process.listenerCount("exit"), exitListenersBeforeLoad);
      const command = extension.commands.get("restart");
      assert.match(command.description, /Restart Pi/);
      const tool = extension.tools.get("restart_pi").definition;
      assert.equal(tool.label, "Restart Pi");
      assert.match(tool.description, /equivalent to bash/i);
      assert.match(tool.promptGuidelines.join(" "), /authorization, safety review, and approval/i);
      assert.equal(tool.parameters.additionalProperties, false);
      assert.equal(tool.parameters.properties.command.type, "string");
      let exitHandler;
      let shutdowns = 0;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.execve = () => {};
      process.once = (_name, listener) => { exitHandler = listener; return process; };
      try {
        const result = await tool.execute("call", {}, undefined, undefined, {
          cwd: "/repo",
          mode: "tui",
          sessionManager: {
            getSessionFile: () => "/sessions/session.jsonl",
            getSessionDir: () => "/sessions",
            getSessionId: () => "session-uuid",
          },
          shutdown() { shutdowns++; },
        });
        assert.equal(typeof exitHandler, "function");
        assert.equal(shutdowns, 1);
        assert.equal(result.content[0].text, "Restarting Pi; process replacement requested.");
        assert.equal(result.terminate, true);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_slash_and_tool_commands_build_same_fixed_relay():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      const command = extension.commands.get("restart");
      const tool = extension.tools.get("restart_pi").definition;
      const commandText = "printf '%s\\n' \\\"quoted value\\\";\\nexit 7";
      const calls = [];
      let exitHandler;
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
      process.once = (_name, listener) => { exitHandler = listener; return process; };
      process.execve = (file, args, env) => { calls.push({ file, args, env }); };
      const ctx = {
        cwd: "/repo with spaces",
        mode: "tui",
        sessionManager: {
          getSessionFile: () => "/sessions/session file.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        },
        shutdown() {},
      };
      try {
        await command.handler(commandText, ctx);
        exitHandler(0);
        await tool.execute("call", { command: commandText }, undefined, undefined, ctx);
        exitHandler(0);

        assert.equal(calls.length, 2);
        assert.deepEqual(calls[0], calls[1]);
        assert.equal(calls[0].file, "/bin/sh");
        assert.equal(calls[0].args[0], "/bin/sh");
        assert.equal(calls[0].args[1], "-c");
        assert.equal(calls[0].args[2].includes(commandText), false);
        assert.equal(calls[0].args[2].includes(ctx.cwd), false);
        assert.deepEqual(calls[0].args.slice(3), [
          "pi-command-relay",
          ctx.cwd,
          commandText,
          "/opt/node-24/bin/node",
          "--no-warnings",
          "/opt/pi/dist/cli.js",
          "--session-dir",
          "/sessions",
          "--session",
          "/sessions/session file.jsonl",
        ]);
        assert.equal(calls[0].env, process.env);
      } finally {
        process.argv = original.argv;
        process.execArgv = original.execArgv;
        process.execPath = original.execPath;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_relay_runs_from_session_cwd_and_resumes_after_ordinary_statuses():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      import { spawnSync } from "node:child_process";
      import { mkdtempSync, rmSync } from "node:fs";
      import { tmpdir } from "node:os";
      import { join } from "node:path";
      const command = extension.commands.get("restart");
      let exitHandler;
      let execCall;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.once = (_name, listener) => { exitHandler = listener; return process; };
      process.execve = (file, args) => { execCall = { file, args }; };
      const cwd = mkdtempSync(join(tmpdir(), "pi-command-relay-"));
      const ctx = {
        cwd,
        mode: "tui",
        sessionManager: {
          getSessionFile: () => "/sessions/session.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        },
        shutdown() {},
      };
      try {
        for (const [childCommand, expectedStatus] of [
          ["printf 'cwd:%s\\n' \\\"$PWD\\\"", 0],
          ["exit 7", 7],
          ["exit 130", 130],
        ]) {
          await command.handler(childCommand, ctx);
          exitHandler(0);
          const resume = ["/bin/sh", "-c", "printf 'resumed\\n'", "pi-resume"];
          const result = spawnSync(execCall.file, [...execCall.args.slice(1, 6), ...resume], {
            encoding: "utf8",
          });
          assert.equal(result.status, 0);
          assert.match(result.stderr, new RegExp(`Command exited with status ${expectedStatus}; resuming Pi\\.`));
          assert.match(result.stdout, /resumed/);
          if (expectedStatus === 0) assert.match(result.stdout, new RegExp(`cwd:${cwd}`));
        }

        ctx.cwd = `${cwd}/missing`;
        await command.handler("exit 99", ctx);
        exitHandler(0);
        const result = spawnSync(
          execCall.file,
          [...execCall.args.slice(1, 6), "/bin/sh", "-c", "printf 'resumed\\n'", "pi-resume"],
          { encoding: "utf8" },
        );
        assert.equal(result.status, 0);
        assert.match(result.stderr, /working directory is unavailable/);
        assert.match(result.stderr, /status 125/);
        assert.match(result.stdout, /resumed/);
      } finally {
        rmSync(cwd, { recursive: true, force: true });
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_rejects_invalid_explicit_commands_before_shutdown():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      const command = extension.commands.get("restart");
      const tool = extension.tools.get("restart_pi").definition;
      let listeners = 0;
      let shutdowns = 0;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.execve = () => { throw new Error("must not execute"); };
      process.once = () => { listeners++; return process; };
      const ctx = {
        cwd: "/repo",
        mode: "tui",
        sessionManager: {
          getSessionFile: () => "/sessions/session.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        },
        shutdown() { shutdowns++; },
      };
      try {
        await assert.rejects(() => command.handler("   ", ctx), /non-whitespace/);
        await assert.rejects(() => command.handler("echo ok\\0bad", ctx), /NUL/);
        for (const value of ["", "   ", "echo ok\\0bad"]) {
          await assert.rejects(
            () => tool.execute("call", { command: value }, undefined, undefined, ctx),
            /non-whitespace|NUL/,
          );
        }
        assert.equal(listeners, 0);
        assert.equal(shutdowns, 0);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_rejects_second_pending_replacement_and_resets_after_nonzero_exit():
    assert EXTENSION.exists(), "tracked process restart extension is required"
    script = loader_prelude() + """
      const command = extension.commands.get("restart");
      const exitHandlers = [];
      let shutdowns = 0;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.execve = () => { throw new Error("must not execute"); };
      process.once = (_name, listener) => { exitHandlers.push(listener); return process; };
      const ctx = {
        mode: "tui",
        sessionManager: {
          getSessionFile: () => "/sessions/session.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        },
        shutdown() { shutdowns++; },
      };
      try {
        await command.handler("", ctx);
        await assert.rejects(() => command.handler("", ctx), /process replacement is already pending/);
        assert.equal(exitHandlers.length, 1);
        assert.equal(shutdowns, 1);

        exitHandlers[0](1);
        await command.handler("", ctx);
        assert.equal(exitHandlers.length, 2);
        assert.equal(shutdowns, 2);
        exitHandlers[1](1);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_orders_graceful_shutdown_before_exact_session_file_exec():
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
            `${sessionDir}/session.jsonl`,
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
        (
            'ctx.sessionManager.getSessionDir = () => "/" + "d".repeat(600); '
            'ctx.sessionManager.getSessionFile = () => "/" + "d".repeat(600) + "/session.jsonl";',
            "",
            "recovery command exceeds",
        ),
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
        await extension.commands.get("restart").handler("printf command-mode", {
          cwd: "/repo",
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
      const fakeCredential = ["ghp", "syntheticabcdefghijklmnopqrstuvwxyz1234"].join("_");
      process.execve = () => { throw new Error(`replacement denied ${fakeCredential} ${"x".repeat(5000)}`); };
      try {
        await extension.commands.get("restart").handler("printf hidden-command", {
          cwd: "/repo",
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
    assert "Pi restart failed: replacement denied [REDACTED_CREDENTIAL]" in result.stderr
    assert "hidden-command" not in result.stderr
    assert "pi --session-dir '/sessions' --session '/sessions/session.jsonl'" in result.stderr
    assert "ghp_" not in result.stderr
    assert len(result.stderr) < 1200


def test_nvim_slash_and_tool_generate_safe_restart_commands():
    script = loader_prelude(extension_path=NVIM_EXTENSION) + """
      const command = extension.commands.get("nvim");
      const tool = extension.tools.get("nvim").definition;
      assert.match(command.description, /Nvim/);
      assert.equal(tool.label, "Nvim");
      assert.equal(tool.parameters.additionalProperties, false);
      assert.equal(tool.parameters.properties.path.type, "string");
      const calls = [];
      let exitHandler;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.once = (_name, listener) => { exitHandler = listener; return process; };
      process.execve = (file, args, env) => { calls.push({ file, args, env }); };
      const ctx = {
        cwd: "/repo",
        mode: "tui",
        sessionManager: {
          getSessionFile: () => "/sessions/session.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        },
        shutdown() {},
      };
      const invoke = async (handler) => {
        const result = await handler();
        exitHandler(0);
        return result;
      };
      try {
        await invoke(() => command.handler("", ctx));
        await invoke(() => command.handler("   ", ctx));
        await invoke(() => command.handler(" docs/file name.md ", ctx));
        await invoke(() => command.handler("docs/../src/main.ts", ctx));
        await invoke(() => command.handler("docs/O'Brien file.md", ctx));
        const result = await invoke(() => tool.execute("call", {}, undefined, undefined, ctx));
        await invoke(() => tool.execute("call", { path: "-u NONE" }, undefined, undefined, ctx));

        assert.deepEqual(calls.map((call) => call.args[5]), [
          "nvim",
          "nvim",
          "nvim -- 'docs/file name.md'",
          "nvim -- 'src/main.ts'",
          "nvim -- 'docs/O'\\\\''Brien file.md'",
          "nvim",
          "nvim -- '-u NONE'",
        ]);
        for (const call of calls) {
          assert.equal(call.file, "/bin/sh");
          assert.deepEqual(call.args.slice(-5), [
            "/opt/pi/dist/cli.js",
            "--session-dir",
            "/sessions",
            "--session",
            "/sessions/session.jsonl",
          ]);
          assert.equal(call.env, process.env);
        }
        assert.equal(result.terminate, true);
        assert.match(result.content[0].text, /Nvim/);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_nvim_rejects_unsafe_paths_before_shutdown():
    script = loader_prelude(extension_path=NVIM_EXTENSION) + """
      const command = extension.commands.get("nvim");
      const tool = extension.tools.get("nvim").definition;
      let listeners = 0;
      let shutdowns = 0;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.execve = () => { throw new Error("must not execute"); };
      process.once = () => { listeners++; return process; };
      const ctx = {
        cwd: "/repo",
        mode: "tui",
        sessionManager: {
          getSessionFile: () => "/sessions/session.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        },
        shutdown() { shutdowns++; },
      };
      try {
        for (const path of [
          "/tmp/file",
          "../outside",
          "a/../../outside",
          "bad\\0path",
          "bad\\rpath",
          "bad\\npath",
          " \\n ",
        ]) {
          await assert.rejects(() => command.handler(path, ctx), /relative|NUL|newline/);
          await assert.rejects(
            () => tool.execute("call", { path }, undefined, undefined, ctx),
            /relative|NUL|newline/,
          );
        }
        ctx.mode = "rpc";
        await assert.rejects(
          () => command.handler("file.ts", ctx),
          new RegExp("/nvim requires interactive TUI"),
        );
        assert.equal(listeners, 0);
        assert.equal(shutdowns, 0);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_nvim_duplicate_replacement_uses_shared_lifecycle_guard():
    script = loader_prelude(extension_path=NVIM_EXTENSION) + """
      const command = extension.commands.get("nvim");
      const exitHandlers = [];
      let shutdowns = 0;
      const original = { argv: process.argv, execve: process.execve, once: process.once };
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.execve = () => {};
      process.once = (_name, listener) => { exitHandlers.push(listener); return process; };
      const ctx = {
        cwd: "/repo",
        mode: "tui",
        sessionManager: {
          getSessionFile: () => "/sessions/session.jsonl",
          getSessionDir: () => "/sessions",
          getSessionId: () => "session-uuid",
        },
        shutdown() { shutdowns++; },
      };
      try {
        await command.handler("file.ts", ctx);
        await assert.rejects(() => command.handler("other.ts", ctx), /process replacement is already pending/);
        assert.equal(exitHandlers.length, 1);
        assert.equal(shutdowns, 1);
        exitHandlers[0](1);
      } finally {
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }
    """
    run_node(script)


def test_restart_documentation_states_reload_and_platform_boundary():
    text = README.read_text(encoding="utf-8")
    matrix = MATRIX.read_text(encoding="utf-8")

    for marker in (
        "`/reload`",
        "`/restart`",
        "`restart_pi`",
        "`/nvim`",
        "`nvim`",
        "Node 24",
        "macOS/Linux",
        "Windows",
        "persisted session",
    ):
        assert marker in text
    assert "`process-restart.ts`" in matrix
    assert "`nvim.ts`" in matrix
    assert "TUI" in matrix
    assert "unavailable in RPC" in matrix
