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
printf '%s\\n' '{"schemaVersion":1,"status":"ready","source":{"beadId":"pi-current.1","outcome":"success","status":"closed"},"target":{"beadId":"pi-next.1","status":"open"}}'
""",
        encoding="utf-8",
    )
    agnt.chmod(agnt.stat().st_mode | stat.S_IXUSR)
    return agent_dir, tmp_path / "agnt-args.txt"


def test_handoff_command_and_agent_tool_register():
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    script = loader_prelude(
        'runtime.sendUserMessage = (message, options) => queued.push([message, options]);\nconst queued = [];'
    ) + """
      const command = extension.commands.get("handoff-bead");
      assert.equal(command.description, "Start a ready Bead in a fresh Pi session");
      const tool = extension.tools.get("handoff_bead").definition;
      assert.equal(tool.label, "Handoff Bead");
      const result = await tool.execute("call", { targetBead: "pi-next.1" });
      assert.deepEqual(queued, [["/handoff-bead pi-next.1", { deliverAs: "followUp" }]]);
      assert.equal(result.content[0].text, "Queued fresh-session handoff to pi-next.1.");
      assert.deepEqual(result.details, { targetBead: "pi-next.1" });
      await assert.rejects(
        () => tool.execute("call", { targetBead: "bad bead; unsafe" }),
        /valid Bead ID/,
      );
    """
    run_node(script)


def test_handoff_command_uses_parent_provenance_and_replacement_context(tmp_path):
    assert EXTENSION.exists(), "tracked Bead handoff extension is required"
    agent_dir, args_path = fake_agent_dir(tmp_path)
    parent_session = tmp_path / "source-session.jsonl"
    script = loader_prelude() + f"""
      const command = extension.commands.get("handoff-bead");
      let newSessionOptions;
      const sent = [];
      const oldCtx = {{
        mode: "tui",
        cwd: {str(tmp_path)!r},
        sessionManager: {{
          getSessionFile: () => {str(parent_session)!r},
          getSessionId: () => "old-session",
        }},
        ui: {{ notify() {{ throw new Error("old UI used after replacement"); }} }},
        async newSession(options) {{
          newSessionOptions = options;
          await options.withSession({{
            sessionManager: {{ getSessionId: () => "new-session" }},
            async sendUserMessage(message) {{ sent.push(message); }},
          }});
          return {{ cancelled: false }};
        }},
      }};

      await command.handler("pi-next.1", oldCtx);
      assert.equal(newSessionOptions.parentSession, {str(parent_session)!r});
      assert.equal(typeof newSessionOptions.withSession, "function");
      assert.deepEqual(sent, [
        "Work pi-next.1 in this fresh Pi session. Run `agnt work direct-start pi-next.1` before code changes, then continue from Beads and tracked repository artifacts only. No prior transcript was copied.",
      ]);
      assert.ok(sent[0].length < 300);
      assert.ok(!sent[0].includes("conversation history"));
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
        "pi-next.1",
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
