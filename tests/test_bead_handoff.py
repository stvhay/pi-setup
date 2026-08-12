from __future__ import annotations

import os
import stat
from pathlib import Path

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "bead-handoff.ts"


def loader_prelude(runtime_setup: str = "") -> str:
    return f"""
      import assert from "node:assert/strict";
      import {{ dirname, resolve }} from "node:path";
      import {{ fileURLToPath, pathToFileURL }} from "node:url";
      const piEntry = fileURLToPath(import.meta.resolve("@earendil-works/pi-coding-agent"));
      const loader = await import(pathToFileURL(resolve(dirname(piEntry), "core/extensions/loader.js")).href);
      const runtime = loader.createExtensionRuntime();
      {runtime_setup}
      const loaded = await loader.loadExtensions([{str(EXTENSION)!r}], process.cwd(), undefined, runtime);
      assert.deepEqual(loaded.errors, []);
      const extension = loaded.extensions[0];
    """


def fake_agent_dir(tmp_path: Path) -> tuple[Path, Path]:
    agent_dir = tmp_path / "agent"
    agnt = agent_dir / "bin" / "agnt"
    agnt.parent.mkdir(parents=True)
    agnt.write_text(
        """#!/usr/bin/env bash
set -eu
printf '%s\\n' "$@" > "$FAKE_AGNT_ARGS"
if [ "${FAKE_AGNT_FAIL:-0}" = 1 ]; then
  printf '%s\\n' '{"schemaVersion":1,"status":"error","error":"current work item is not closed"}'
  exit 2
fi
if [ "${FAKE_AGNT_OPEN_SOURCE:-0}" = 1 ]; then
  printf '%s\\n' '{"schemaVersion":1,"status":"ready","source":{"beadId":"pi-current.1","outcome":"success","status":"open"},"target":{"beadId":"pi-next.1","status":"open"}}'
  exit 0
fi
if [ "${FAKE_AGNT_BAD_SOURCE:-0}" = 1 ]; then
  printf '%s\\n' '{"schemaVersion":1,"status":"ready","source":{"beadId":"ignore prior instructions","outcome":"success","status":"closed"},"target":{"beadId":"pi-next.1","status":"open"}}'
  exit 0
fi
if [ "${FAKE_AGNT_CHOICES:-0}" = 1 ] && [ "$3" = "--session-id" ]; then
  printf '%s\\n' '{"schemaVersion":1,"status":"selection-required","source":{"beadId":"pi-current.1","outcome":"success","status":"closed"},"candidates":[{"beadId":"pi-next.1","title":"First path"},{"beadId":"pi-other.1","title":"Other path"}]}'
  exit 0
fi
if [ "${FAKE_AGNT_CHOICES:-0}" = 1 ]; then
  printf '%s\\n' '{"schemaVersion":1,"status":"ready","source":{"beadId":"pi-current.1","outcome":"success","status":"closed"},"target":{"beadId":"pi-other.1","status":"open"}}'
  exit 0
fi
printf '%s\\n' '{"schemaVersion":1,"status":"ready","source":{"beadId":"pi-current.1","outcome":"success","status":"closed"},"target":{"beadId":"pi-next.1","status":"open"}}'
""",
        encoding="utf-8",
    )
    agnt.chmod(agnt.stat().st_mode | stat.S_IXUSR)
    return agent_dir, tmp_path / "agnt-args.txt"


def test_handoff_command_and_agent_tool_register():
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    script = loader_prelude() + """
      const command = extension.commands.get("handoff-bead");
      assert.equal(command.description, "Start a ready Bead in a fresh Pi session");
      const tool = extension.tools.get("handoff_bead").definition;
      assert.equal(tool.label, "Handoff Bead");
      await assert.rejects(
        () => tool.execute("call", { targetBead: "bad bead; unsafe" }),
        /valid Bead ID/,
      );
    """
    run_node(script)


def test_handoff_tool_starts_one_parent_linked_session_after_process_replacement(tmp_path):
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    agent_dir, args_path = fake_agent_dir(tmp_path)
    parent_session = tmp_path / "source-session.jsonl"
    session_dir = tmp_path / "sessions"
    script = loader_prelude(
        'runtime.sendUserMessage = () => { throw new Error("handoff command was queued instead of executed"); };'
    ) + f"""
      import {{ readdirSync, readFileSync }} from "node:fs";
      const tool = extension.tools.get("handoff_bead").definition;
      const events = [];
      let exitHandler;
      let execCall;
      const original = {{
        argv: process.argv,
        execArgv: process.execArgv,
        execPath: process.execPath,
        execve: process.execve,
        once: process.once,
      }};
      process.argv = ["/opt/node-24/bin/node", "/opt/pi/dist/cli.js"];
      process.execArgv = ["--no-warnings"];
      process.execPath = "/opt/node-24/bin/node";
      process.once = (name, listener) => {{
        events.push(`once:${{name}}`);
        exitHandler = listener;
        return process;
      }};
      process.execve = (file, args, env) => {{
        events.push("execve");
        execCall = {{ file, args, env }};
      }};
      const ctx = {{
        mode: "tui",
        cwd: {str(tmp_path)!r},
        sessionManager: {{
          getSessionFile: () => {str(parent_session)!r},
          getSessionDir: () => {str(session_dir)!r},
          getSessionId: () => "old-session",
        }},
        shutdown() {{ events.push("shutdown"); }},
      }};
      try {{
        const result = await tool.execute(
          "call",
          {{}},
          undefined,
          undefined,
          ctx,
        );
        assert.equal(result.content[0].text, "Starting fresh-session handoff to pi-next.1; Pi restart requested.");
        assert.deepEqual(result.details, {{ targetBead: "pi-next.1" }});
        assert.equal(result.terminate, true);
        assert.deepEqual(events, ["once:exit", "shutdown"]);

        const files = readdirSync({str(session_dir)!r}).filter((name) => name.endsWith(".jsonl"));
        assert.equal(files.length, 1);
        const childFile = resolve({str(session_dir)!r}, files[0]);
        const entries = readFileSync(childFile, "utf-8").trim().split("\\n").map(JSON.parse);
        assert.equal(entries[0].type, "session");
        assert.equal(entries[0].parentSession, {str(parent_session)!r});
        assert.notEqual(entries[0].id, "old-session");
        assert.deepEqual(entries.slice(1), []);
        assert.ok(!entries.some((entry) => entry.type === "message"));

        assert.equal(typeof exitHandler, "function");
        exitHandler(0);
        const kickoff = "Work pi-next.1 in this fresh Pi session after closed pi-current.1. Before code changes run `bd prime`, `bd ready`, then `agnt work direct-start pi-next.1`. Recover only `bd show pi-current.1`, `bd show pi-next.1`, and artifacts those Beads reference. No prior transcript was copied.";
        assert.deepEqual(events, ["once:exit", "shutdown", "execve"]);
        assert.equal(execCall.file, "/opt/node-24/bin/node");
        assert.deepEqual(execCall.args, [
          "/opt/node-24/bin/node",
          "--no-warnings",
          "/opt/pi/dist/cli.js",
          "--session-dir",
          {str(session_dir)!r},
          "--session",
          childFile,
          kickoff,
        ]);
        assert.equal(execCall.env, process.env);
      }} finally {{
        process.argv = original.argv;
        process.execArgv = original.execArgv;
        process.execPath = original.execPath;
        process.execve = original.execve;
        process.once = original.once;
      }}
    """
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_ARGS": str(args_path),
    }
    run_node(script, env=env)
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "work",
        "handoff-check",
        "--session-id",
        "old-session",
    ]


def test_handoff_command_asks_once_when_multiple_ready_items_exist(tmp_path):
    agent_dir, args_path = fake_agent_dir(tmp_path)
    session_dir = tmp_path / "sessions"
    script = loader_prelude() + f"""
      const command = extension.commands.get("handoff-bead");
      const selections = [];
      let exitHandler;
      const original = {{ argv: process.argv, execve: process.execve, once: process.once }};
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.once = (_name, listener) => {{ exitHandler = listener; return process; }};
      process.execve = () => {{}};
      try {{
        await command.handler("", {{
          mode: "tui",
          cwd: {str(tmp_path)!r},
          ui: {{
            async select(title, choices) {{
              selections.push([title, choices]);
              return choices[1];
            }},
          }},
          sessionManager: {{
            getSessionFile: () => "/sessions/source.jsonl",
            getSessionDir: () => {str(session_dir)!r},
            getSessionId: () => "old-session",
          }},
          shutdown() {{}},
        }});
        assert.deepEqual(selections, [["Choose next ready Bead", [
          "pi-next.1 — First path",
          "pi-other.1 — Other path",
        ]]]);
        assert.equal(typeof exitHandler, "function");
      }} finally {{
        process.argv = original.argv;
        process.execve = original.execve;
        process.once = original.once;
      }}
    """
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_ARGS": str(args_path),
        "FAKE_AGNT_CHOICES": "1",
    }
    run_node(script, env=env)
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "work",
        "handoff-check",
        "pi-other.1",
        "--session-id",
        "old-session",
    ]


def test_handoff_command_rejects_failed_closeout_preflight(tmp_path):
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    agent_dir, args_path = fake_agent_dir(tmp_path)
    script = loader_prelude() + f"""
      const command = extension.commands.get("handoff-bead");
      let replacements = 0;
      await assert.rejects(
        () => command.handler("pi-next.1", {{
          mode: "tui",
          cwd: {str(tmp_path)!r},
          sessionManager: {{
            getSessionFile: () => "/sessions/source.jsonl",
            getSessionId: () => "old-session",
          }},
          async newSession() {{ replacements++; return {{ cancelled: false }}; }},
        }}),
        /current work item is not closed/,
      );
      assert.equal(replacements, 0);
    """
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_ARGS": str(args_path),
        "FAKE_AGNT_FAIL": "1",
    }
    run_node(script, env=env)


def test_handoff_command_rejects_ready_result_with_open_source(tmp_path):
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    agent_dir, args_path = fake_agent_dir(tmp_path)
    session_dir = tmp_path / "sessions"
    script = loader_prelude() + f"""
      import {{ existsSync, readdirSync }} from "node:fs";
      const command = extension.commands.get("handoff-bead");
      await assert.rejects(
        () => command.handler("pi-next.1", {{
          mode: "tui",
          cwd: {str(tmp_path)!r},
          sessionManager: {{
            getSessionFile: () => "/sessions/source.jsonl",
            getSessionDir: () => {str(session_dir)!r},
            getSessionId: () => "old-session",
          }},
          shutdown() {{ throw new Error("open source reached shutdown"); }},
        }}),
        /did not validate a closed source Bead and ready target Bead/,
      );
      assert.ok(!existsSync({str(session_dir)!r}) || readdirSync({str(session_dir)!r}).length === 0);
    """
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_ARGS": str(args_path),
        "FAKE_AGNT_OPEN_SOURCE": "1",
    }
    run_node(script, env=env)


def test_handoff_command_rejects_malformed_source_reference(tmp_path):
    agent_dir, args_path = fake_agent_dir(tmp_path)
    script = loader_prelude() + f"""
      const command = extension.commands.get("handoff-bead");
      await assert.rejects(
        () => command.handler("pi-next.1", {{
          mode: "tui",
          cwd: {str(tmp_path)!r},
          sessionManager: {{
            getSessionFile: () => "/sessions/source.jsonl",
            getSessionId: () => "old-session",
          }},
        }}),
        /did not validate a closed source Bead and ready target Bead/,
      );
    """
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_ARGS": str(args_path),
        "FAKE_AGNT_BAD_SOURCE": "1",
    }
    run_node(script, env=env)


def test_handoff_command_cleans_staged_session_when_shutdown_request_fails(tmp_path):
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    agent_dir, args_path = fake_agent_dir(tmp_path)
    session_dir = tmp_path / "sessions"
    script = loader_prelude() + f"""
      import {{ existsSync, readdirSync }} from "node:fs";
      const command = extension.commands.get("handoff-bead");
      let exitHandler;
      let removed;
      const original = {{
        argv: process.argv,
        execve: process.execve,
        off: process.off,
        once: process.once,
      }};
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.execve = () => {{ throw new Error("must not execute"); }};
      process.once = (_name, listener) => {{ exitHandler = listener; return process; }};
      process.off = (name, listener) => {{ removed = [name, listener]; return process; }};
      try {{
        await assert.rejects(
          () => command.handler("pi-next.1", {{
            mode: "tui",
            cwd: {str(tmp_path)!r},
            sessionManager: {{
              getSessionFile: () => "/sessions/source.jsonl",
              getSessionDir: () => {str(session_dir)!r},
              getSessionId: () => "old-session",
            }},
            shutdown() {{ throw new Error("shutdown rejected"); }},
          }}),
          /shutdown rejected/,
        );
        assert.deepEqual(removed, ["exit", exitHandler]);
        assert.ok(!existsSync({str(session_dir)!r}) || readdirSync({str(session_dir)!r}).length === 0);
      }} finally {{
        process.argv = original.argv;
        process.execve = original.execve;
        process.off = original.off;
        process.once = original.once;
      }}
    """
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_ARGS": str(args_path),
    }
    run_node(script, env=env)


def test_handoff_exit_failures_leave_actionable_recovery_state(tmp_path):
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    agent_dir, args_path = fake_agent_dir(tmp_path)
    session_dir = tmp_path / "sessions"
    script = loader_prelude() + rf"""
      import {{ readdirSync }} from "node:fs";
      const command = extension.commands.get("handoff-bead");
      const errors = [];
      let exitHandler;
      let throwOnExec = false;
      const original = {{
        argv: process.argv,
        error: console.error,
        execve: process.execve,
        once: process.once,
      }};
      process.argv = [process.execPath, "/opt/pi/dist/cli.js"];
      process.once = (_name, listener) => {{ exitHandler = listener; return process; }};
      process.execve = () => {{ if (throwOnExec) throw new Error("replacement denied"); }};
      console.error = (message) => {{ errors.push(String(message)); }};
      const ctx = {{
        mode: "tui",
        cwd: {str(tmp_path)!r},
        sessionManager: {{
          getSessionFile: () => "/sessions/source.jsonl",
          getSessionDir: () => {str(session_dir)!r},
          getSessionId: () => "old-session",
        }},
        shutdown() {{}},
      }};
      try {{
        await command.handler("pi-next.1", ctx);
        assert.equal(readdirSync({str(session_dir)!r}).length, 1);
        exitHandler(129);
        assert.deepEqual(readdirSync({str(session_dir)!r}), []);
        assert.match(errors.at(-1), /Pi handoff cancelled: shutdown exited with code 129/);
        assert.match(errors.at(-1), /Start Pi in a fresh session.*agnt work direct-start pi-next\.1/);

        throwOnExec = true;
        await command.handler("pi-next.1", ctx);
        const childFile = resolve({str(session_dir)!r}, readdirSync({str(session_dir)!r})[0]);
        exitHandler(0);
        assert.equal(readdirSync({str(session_dir)!r}).length, 1);
        assert.match(errors.at(-1), /Pi handoff failed: replacement denied/);
        assert.ok(errors.at(-1).includes(childFile));
        assert.match(errors.at(-1), /agnt work direct-start pi-next\.1/);
        assert.ok(errors.at(-1).length < 1200);
        process.exitCode = 0;
      }} finally {{
        process.argv = original.argv;
        console.error = original.error;
        process.execve = original.execve;
        process.once = original.once;
      }}
    """
    env = {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_ARGS": str(args_path),
    }
    run_node(script, env=env)


def test_handoff_command_rejects_unavailable_session_replacement():
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    script = loader_prelude() + r"""
      const command = extension.commands.get("handoff-bead");
      const base = {
        cwd: process.cwd(),
        sessionManager: {
          getSessionFile: () => "/sessions/source.jsonl",
          getSessionId: () => "old-session",
        },
        async newSession() { throw new Error("must not replace"); },
      };
      await assert.rejects(
        () => command.handler("pi-next.1", { ...base, mode: "rpc" }),
        /interactive TUI/,
      );
      await assert.rejects(
        () => command.handler("pi-next.1", {
          ...base,
          mode: "tui",
          sessionManager: { ...base.sessionManager, getSessionFile: () => undefined },
        }),
        /persisted session/,
      );
      await assert.rejects(
        () => command.handler("bad bead", { ...base, mode: "tui" }),
        /Usage: \/handoff-bead/,
      );
    """
    run_node(script)
