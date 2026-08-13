from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "beads-footer.ts"


def fake_agent_dir(tmp_path: Path, response: dict) -> tuple[Path, Path, Path, Path]:
    agent_dir = tmp_path / "agent"
    agnt = agent_dir / "bin" / "agnt"
    agnt.parent.mkdir(parents=True)
    agnt.write_text(
        """#!/bin/sh
set -eu
{
  printf '%s' "$1"
  shift
  for arg in "$@"; do printf ' %s' "$arg"; done
  printf '\n'
} >> "$FAKE_AGNT_ARGS"
cat "$FAKE_AGNT_RESPONSE"
exit "$(cat "$FAKE_AGNT_EXIT")"
""",
        encoding="utf-8",
    )
    agnt.chmod(agnt.stat().st_mode | stat.S_IXUSR)
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    exit_path = tmp_path / "exit-code"
    exit_path.write_text("0", encoding="utf-8")
    return agent_dir, response_path, exit_path, tmp_path / "args.log"


def extension_prelude(tmp_path: Path) -> str:
    return f"""
      import assert from "node:assert/strict";
      import {{ writeFileSync }} from "node:fs";
      import {{ pathToFileURL }} from "node:url";
      const {{ default: beadsFooter }} = await import(pathToFileURL({str(EXTENSION)!r}).href);
      const handlers = new Map();
      beadsFooter({{
        on(name, handler) {{ handlers.set(name, handler); }},
      }});
      const statuses = [];
      const ctx = {{
        cwd: {str(tmp_path)!r},
        sessionManager: {{ getSessionId: () => "session-1" }},
        ui: {{
          theme: {{
            fg: (color, text) => `[${{color}}:${{text}}]`,
            bold: (text) => `<b>${{text}}</b>`,
          }},
          setStatus: (key, value) => statuses.push([key, value]),
        }},
      }};
    """


def extension_env(agent_dir: Path, response: Path, exit_path: Path, args_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "FAKE_AGNT_RESPONSE": str(response),
        "FAKE_AGNT_EXIT": str(exit_path),
        "FAKE_AGNT_ARGS": str(args_path),
    }


def status(items: list[dict], active: str | None = None) -> dict:
    return {
        "schemaVersion": 1,
        "status": "ok",
        "activeBeadId": active,
        "items": items,
    }


def test_session_start_lists_multiple_issues_and_highlights_active(tmp_path):
    items = [
        {"id": "pi-a.1", "priority": 1, "title": "First"},
        {"id": "pi-long.1", "priority": 2, "title": "Second"},
    ]
    agent_dir, response, exit_path, args_path = fake_agent_dir(
        tmp_path, status(items, "pi-long.1")
    )
    script = extension_prelude(tmp_path) + """
      await handlers.get("session_start")({ reason: "startup" }, ctx);
      assert.deepEqual(statuses, [[
        "beads-work",
        "[syntaxString:◐] [muted:  pi-a.1     P1  First]\\n[mdHeading:◐] <b>  pi-long.1  P2  Second</b>",
      ]]);
    """

    run_node(script, extension_env(agent_dir, response, exit_path, args_path))
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "work status --session-id session-1"
    ]


def test_epic_rows_use_fixed_type_slot_and_current_session_styling(tmp_path):
    items = [
        {"id": "pi-epic", "priority": 1, "title": "Epic", "issueType": "epic"},
        {"id": "pi-task", "priority": 1, "title": "Task", "issueType": "task"},
    ]
    agent_dir, response, exit_path, args_path = fake_agent_dir(
        tmp_path, status(items, "pi-epic")
    )
    script = extension_prelude(tmp_path) + """
      await handlers.get("session_start")({ reason: "startup" }, ctx);
      assert.deepEqual(statuses.at(-1), [
        "beads-work",
        "[mdHeading:◐] <b>◆ pi-epic  P1  Epic</b>\\n[syntaxString:◐] [muted:  pi-task  P1  Task]",
      ]);
    """

    run_node(script, extension_env(agent_dir, response, exit_path, args_path))


def test_absent_active_link_renders_plain_and_empty_state_clears(tmp_path):
    items = [
        {"id": "pi-a.1", "priority": 1, "title": "First"},
        {"id": "pi-long.1", "priority": 2, "title": "Second"},
    ]
    agent_dir, response, exit_path, args_path = fake_agent_dir(tmp_path, status(items))
    script = extension_prelude(tmp_path) + f"""
      await handlers.get("session_start")({{ reason: "startup" }}, ctx);
      assert.deepEqual(statuses.at(-1), ["beads-work", "[syntaxString:◐] [muted:  pi-a.1     P1  First]\\n[syntaxString:◐] [muted:  pi-long.1  P2  Second]"]);
      writeFileSync({str(response)!r}, {json.dumps(status([]))!r});
      await handlers.get("tool_execution_end")({{ toolName: "ticket_gateway" }}, ctx);
      assert.deepEqual(statuses.at(-1), ["beads-work", undefined]);
    """

    run_node(script, extension_env(agent_dir, response, exit_path, args_path))
    assert len(args_path.read_text(encoding="utf-8").splitlines()) == 2


def test_malformed_and_failed_queries_clear_status(tmp_path):
    malformed = status([{"id": "pi-a.1", "priority": "1", "title": "First"}])
    agent_dir, response, exit_path, args_path = fake_agent_dir(tmp_path, malformed)
    script = extension_prelude(tmp_path) + f"""
      await handlers.get("session_start")({{ reason: "startup" }}, ctx);
      assert.deepEqual(statuses.at(-1), ["beads-work", undefined]);
      writeFileSync({str(exit_path)!r}, "2");
      await handlers.get("tool_execution_end")({{ toolName: "bash" }}, ctx);
      assert.deepEqual(statuses.at(-1), ["beads-work", undefined]);
    """

    run_node(script, extension_env(agent_dir, response, exit_path, args_path))
    assert len(args_path.read_text(encoding="utf-8").splitlines()) == 2


def test_malformed_issue_type_clears_status(tmp_path):
    items = [{"id": "pi-a.1", "priority": 1, "title": "First", "issueType": "not-real"}]
    agent_dir, response, exit_path, args_path = fake_agent_dir(tmp_path, status(items))
    script = extension_prelude(tmp_path) + """
      await handlers.get("session_start")({ reason: "startup" }, ctx);
      assert.deepEqual(statuses.at(-1), ["beads-work", undefined]);
    """

    run_node(script, extension_env(agent_dir, response, exit_path, args_path))


def test_reload_and_work_mutating_tools_refresh_but_read_does_not(tmp_path):
    items = [{"id": "pi-a.1", "priority": 1, "title": "First"}]
    agent_dir, response, exit_path, args_path = fake_agent_dir(tmp_path, status(items))
    script = extension_prelude(tmp_path) + """
      await handlers.get("session_start")({ reason: "startup" }, ctx);
      await handlers.get("tool_execution_end")({ toolName: "read" }, ctx);
      await handlers.get("tool_execution_end")({ toolName: "bash" }, ctx);
      await handlers.get("tool_execution_end")({ toolName: "ticket_question" }, ctx);
      await handlers.get("session_start")({ reason: "reload" }, ctx);
      assert.equal(statuses.length, 4);
      assert.ok(statuses.every(([key, value]) => key === "beads-work" && value === "[syntaxString:◐] [muted:  pi-a.1  P1  First]"));
    """

    run_node(script, extension_env(agent_dir, response, exit_path, args_path))
    assert len(args_path.read_text(encoding="utf-8").splitlines()) == 4
