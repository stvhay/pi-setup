from __future__ import annotations

import json
from pathlib import Path

from conftest import run_node
from test_approvals import approval_preview
from test_bead_handoff import EXTENSION as HANDOFF, loader_prelude


EXTENSION = Path(__file__).resolve().parents[1] / "pi/agent/extensions/beads-ask-bridge.ts"


def fixture(tmp_path, kind):
    agent = tmp_path / "agent"
    executable = agent / "bin/agnt"
    executable.parent.mkdir(parents=True)
    request = {"kind": kind, "targetBead": "pi-work.1", "question": "Original question?",
               "context": "Original context", "options": ["Safe", "Stop"], "default": "Stop",
               "selectionMode": "single", "preview": {**approval_preview(), "scope": "Original scope"}}
    (tmp_path / "request.json").write_text(json.dumps(request))
    executable.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ["FIXTURE_ROOT"])
args = sys.argv[1:]
proof = None
if "AGNT_HUMAN_UI_RESOLVER_FD" in os.environ:
    proof = json.load(os.fdopen(int(os.environ["AGNT_HUMAN_UI_RESOLVER_FD"])))
    assert proof["sessionId"] == "child-session" and proof["toolName"] == "ticket_decision_resolve"
with (root / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps({"args": args, "hasProof": proof is not None}) + "\\n")
if args[1] in {"rebind", "recover-context"}:
    assert proof is not None
    print(json.dumps({"status": "pending", "decisionBead": args[2], "request": json.loads((root / "request.json").read_text()), "legacySelectionModeRequired": os.environ.get("LEGACY_QUESTION") == "1"}))
elif args[1] == "resolve":
    print(json.dumps({"blockerVisible": False}))
else:
    raise AssertionError("must reuse original decision, never create another")
''')
    executable.chmod(0o755)
    return {"PI_CODING_AGENT_DIR": str(agent), "FIXTURE_ROOT": str(tmp_path)}


def prelude(tmp_path):
    return loader_prelude().replace(str(HANDOFF), str(EXTENSION)) + f'''
      const tool = extension.tools.get("ticket_decision_resolve").definition;
      const ctx = {{ hasUI: true, cwd: {str(tmp_path)!r}, sessionManager: {{
        getSessionId: () => "child-session", getSessionFile: () => "/private/child-session.jsonl"
      }}, ui: {{
        confirm: async (title, text) => {{
          assert.match(text, /Original scope/); assert.match(text, /Original context/); return true;
        }},
        select: async (title, choices) => {{ assert.match(title, /Original scope/); return choices.at(-1); }},
        input: async () => "Human chosen scope", notify() {{}}
      }} }};
      await extension.handlers.get("session_start")[0]({{ reason: "startup" }}, ctx);
    '''


def test_restarted_approval_redisplays_canonical_scope(tmp_path):
    env = fixture(tmp_path, "approval")
    run_node(prelude(tmp_path) + '''
      await tool.execute("resolve-call", { decisionBead: "pi-decision.1", outcome: "approved" }, undefined, undefined, ctx);
    ''', env=env)
    calls = [json.loads(row) for row in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [call["args"][1] for call in calls] == ["recover-context", "rebind", "resolve"]
    assert all(call["hasProof"] for call in calls)


def test_legacy_mode_not_confirmed_keeps_original_blocker(tmp_path):
    env = {**fixture(tmp_path, "question"), "LEGACY_QUESTION": "1"}
    run_node(prelude(tmp_path) + '''
      ctx.ui.confirm = async (_title, text) => { assert.match(text, /selection mode/); return false; };
      const result = await tool.execute("resolve-call", { decisionBead: "pi-decision.1", outcome: "answered" }, undefined, undefined, ctx);
      assert.equal(result.details.status, "blocked");
    ''', env=env)
    calls = [json.loads(row) for row in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [call["args"][1] for call in calls] == ["recover-context"]


def test_legacy_mode_confirmation_is_explicit_and_precedes_answer(tmp_path):
    env = {**fixture(tmp_path, "question"), "LEGACY_QUESTION": "1"}
    run_node(prelude(tmp_path) + '''
      let confirmedMode = false;
      ctx.ui.confirm = async (_title, text) => {
        assert.match(text, /did not fingerprint selection mode/);
        assert.match(text, /Confirm current mode: single/);
        confirmedMode = true;
        return true;
      };
      ctx.ui.select = async (_title, choices) => { assert(confirmedMode); return choices.at(-1); };
      await tool.execute("resolve-call", { decisionBead: "pi-decision.1", outcome: "answered" }, undefined, undefined, ctx);
    ''', env=env)
    calls = [json.loads(row) for row in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [call["args"][1] for call in calls] == ["recover-context", "rebind", "resolve"]
    flag = calls[1]["args"].index("--legacy-selection-mode")
    assert calls[1]["args"][flag + 1] == "single"


def test_recovery_session_change_cannot_confirm_old_dialog(tmp_path):
    env = fixture(tmp_path, "approval")
    run_node(prelude(tmp_path) + '''
      ctx.ui.confirm = async () => {
        await extension.handlers.get("session_shutdown")[0]({ reason: "new" }, ctx);
        return true;
      };
      await assert.rejects(() => tool.execute("resolve-call", { decisionBead: "pi-decision.1", outcome: "approved" }, undefined, undefined, ctx), /session changed/);
    ''', env=env)
    calls = [json.loads(row) for row in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [call["args"][1] for call in calls] == ["recover-context", "rebind"]


def test_restarted_question_takes_fresh_human_answer_not_agent_guess(tmp_path):
    env = fixture(tmp_path, "question")
    run_node(prelude(tmp_path) + '''
      await tool.execute("resolve-call", { decisionBead: "pi-decision.1", outcome: "answered", answer: "Agent guess" }, undefined, undefined, ctx);
    ''', env=env)
    calls = [json.loads(row) for row in (tmp_path / "calls.jsonl").read_text().splitlines()]
    args = calls[-1]["args"]
    assert args[args.index("--custom-input") + 1] == "Human chosen scope"
    assert "Agent guess" not in args
    assert [call["args"][1] for call in calls] == ["recover-context", "rebind", "resolve"]
