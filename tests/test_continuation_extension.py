"""Actual SDK loading and process-replacement adapter; no live restart."""
from __future__ import annotations

import json
import subprocess

import pytest

from conftest import run_node
from test_bead_handoff import loader_prelude


def fixture_agent(tmp_path):
    agent = tmp_path / "agent"
    script = agent / "bin" / "agnt"
    script.parent.mkdir(parents=True)
    tx = {"id": "a" * 32, "sourceSession": "source-session", "sourceBead": "pi-a", "targetBead": "pi-a",
          "checkpointRef": "b" * 32, "targetCheckout": str(tmp_path), "sourceSessionFile": str(tmp_path / "source.jsonl"),
          "childSession": "11111111-1111-4111-8111-111111111111",
          "childSessionFile": str(tmp_path / "children" / "child.jsonl"), "state": "prepared", "mode": "resume"}
    (tmp_path / "transition.json").write_text(json.dumps(tx))
    (tmp_path / "source.jsonl").write_text(json.dumps({"type": "session", "id": "source-session", "cwd": str(tmp_path)}) + "\n")
    script.write_text('''#!/usr/bin/env python3
import hashlib, json, os, pathlib, sys
root = pathlib.Path(os.environ["FIXTURE_ROOT"])
args = sys.argv[1:]
with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps({"args": args, "session": os.environ.get("PI_SESSION_ID")}) + "\\n")
tx = json.loads((root / "transition.json").read_text())
command = args[1]
exit_code = 0
if command == "transition-context":
    if "--session-id" in args and args[args.index("--session-id")+1] == tx["childSession"]:
        result = {"status": "child", "transition": tx}
    else:
        result = {"status": "continuable", "beadId": "pi-a"}
        if os.environ.get("PENDING_TRANSITION"): result["pendingTransition"] = tx
elif command == "checkpoint":
    if "--input-file" in args and args[args.index("--input-file")+1] == "-":
        (root / "received-progress.json").write_text(sys.stdin.read())
    result = {"status": "checkpointed", "checkpoint": {"id": tx["checkpointRef"]}}
else:
    if command == "transition-bind-child":
        if tx["childSessionFile"] is None:
            tx["childSessionFile"] = str(root / "children" / "child.jsonl")
        if os.environ.get("CHANGE_BIND_RESERVATION"):
            tx["childSession"] = "22222222-2222-4222-8222-222222222222"
    if command == "transition-isolate":
        if os.environ.get("BLOCK_ISOLATION"):
            exit_code = 2
        else:
            tx["state"] = "prepared"
            if os.environ.get("CHANGE_RESERVATION"):
                tx["childSession"] = "22222222-2222-4222-8222-222222222222"
    if command == "transition-cancel":
        if os.environ.get("BLOCK_CANCELLATION"):
            exit_code = 2
        else:
            tx["state"] = "cancelled"
    if command == "transition-stage": tx["state"] = "staged"
    if command in {"transition-launch", "transition-abort-launch"}:
        proof = json.load(os.fdopen(int(os.environ["AGNT_WORK_LAUNCH_PROOF_FD"])))
        assert proof["transition"] == tx["id"] and proof["sourceSession"] == tx["sourceSession"]
        proof_hash = hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest()
        if command == "transition-launch":
            if tx["state"] != "staged": sys.exit(2)
            tx["state"] = "launch-requested"
            tx["launchProofHash"] = proof_hash
            if os.environ.get("FAIL_AFTER_LAUNCH"): exit_code = 2
        else:
            assert tx["state"] != "launch-requested" or proof_hash == tx["launchProofHash"]
            tx["state"] = "cancelled"
    if command == "transition-attach":
        if os.environ.get("FAIL_ATTACH"): sys.exit(2)
        assert os.environ.get("PI_SESSION_ID") == tx["childSession"]
        tx["state"] = "attached"
    result = {"status": "blocked" if exit_code else "ok", "transition": tx}
(root / "transition.json").write_text(json.dumps(tx))
if exit_code and os.environ.get("BLOCK_NO_TRANSITION"):
    result.pop("transition", None)
print(json.dumps(result))
sys.exit(int(os.environ.get("FAILURE_EXIT_CODE", exit_code)) if exit_code else 0)
''')
    script.chmod(0o755)
    return {"PI_CODING_AGENT_DIR": str(agent), "FIXTURE_ROOT": str(tmp_path)}


def context(tmp_path, session="source-session", mode="tui"):
    session_file = tmp_path / ("source.jsonl" if session == "source-session" else "children/child.jsonl")
    return f'''{{ mode: {mode!r}, cwd: {str(tmp_path)!r},
      sessionManager: {{ getSessionId: () => {session!r}, getSessionFile: () => {str(session_file)!r},
        getSessionDir: () => {str(tmp_path / "sessions")!r} }},
      shutdown() {{ shutdowns++; }}, ui: {{ notify() {{}} }} }}'''


def test_continuation_reserves_exact_child_and_no_transcript(tmp_path):
    env = fixture_agent(tmp_path)
    script = loader_prelude() + f'''
      import {{ readFileSync }} from "node:fs";
      const tool = extension.tools.get("handoff_bead").definition;
      assert.ok(tool.parameters.properties.mode, "continuation mode missing");
      let shutdowns = 0, onExit, invocation;
      const saved = {{ once: process.once, execve: process.execve, argv: process.argv }};
      process.argv = [process.execPath, "/opt/pi/cli.js"];
      process.once = (name, fn) => {{ if (name === "exit") onExit = fn; return process; }};
      process.execve = (...args) => {{ invocation = args; }};
      try {{
        const result = await tool.execute("call", {{ mode: "resume" }}, undefined, undefined, {context(tmp_path)});
        assert.equal(result.terminate, true);
        assert.equal(shutdowns, 1);
        const file = {str(tmp_path / "children" / "child.jsonl")!r};
        const lines = readFileSync(file, "utf8").trim().split("\\n");
        assert.equal(lines.length, 1);
        const header = JSON.parse(lines[0]);
        assert.equal(header.id, "11111111-1111-4111-8111-111111111111");
        assert.equal(header.parentSession, {str(tmp_path / "source.jsonl")!r});
        onExit(0);
        assert.ok(invocation[1].includes(file));
        assert.match(invocation[1].at(-1), /checkpoint/);
      }} finally {{ Object.assign(process, saved); }}
    '''
    run_node(script, env=env)


@pytest.mark.parametrize("target", [None, "pi-a", "pi-b"])
def test_handoff_carries_curated_progress_in_same_call(tmp_path, target):
    env = fixture_agent(tmp_path)
    if target == "pi-b":
        path = tmp_path / "transition.json"
        tx = json.loads(path.read_text())
        tx.update(targetBead=target, mode="switch")
        path.write_text(json.dumps(tx))
    progress = {"objective": "Finish recovery", "decisions": ["Keep API"], "completed": ["Fix prepared path"],
                "next": ["Run remaining checks"], "blockers": [], "verification": ["Focused tests passed"],
                "ownedPaths": ["src/recovery.py"], "artifactRefs": [".pi/plans/recovery.md"]}
    script = loader_prelude() + f'''
      const tool = extension.tools.get("handoff_bead").definition;
      let shutdowns = 0;
      process.argv = [process.execPath, "/opt/pi/cli.js"];
      process.once = () => process;
      const result = await tool.execute("call", {{ ...{json.dumps({'targetBead': target} if target else {})}, progress: {json.dumps(progress)} }}, undefined, undefined, {context(tmp_path)});
      assert.equal(result.terminate, true);
      assert.equal(shutdowns, 1);
      assert.ok(tool.parameters.properties.progress, "missing typed progress");
    '''
    run_node(script, env=env)
    assert json.loads((tmp_path / "received-progress.json").read_text()) == progress
    calls = [json.loads(line)["args"] for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [args for args in calls if args[1] == "checkpoint"] == [["work", "checkpoint", "pi-a", "--input-file", "-"]]
    prepared = next(args for args in calls if args[1] == "transition-prepare")
    assert prepared[prepared.index("--mode") + 1] == ("switch" if target == "pi-b" else "resume")
    assert "Keep API" not in (tmp_path / "children" / "child.jsonl").read_text()


@pytest.mark.parametrize("reserved", ["checkpoint", "transition", "pending"])
def test_curated_progress_cannot_replace_reserved_checkpoint(tmp_path, reserved):
    env = fixture_agent(tmp_path)
    if reserved == "pending":
        env["PENDING_TRANSITION"] = "1"
    extra = {"checkpointRef": "b" * 32} if reserved == "checkpoint" else {"transitionId": "a" * 32} if reserved == "transition" else {}
    script = loader_prelude() + f'''
      let shutdowns = 0;
      process.argv = [process.execPath, "/opt/pi/cli.js"];
      process.once = () => process;
      const tool = extension.tools.get("handoff_bead").definition;
      await assert.rejects(() => tool.execute("call", {{ ...{json.dumps(extra)}, progress: {{ objective: "replace" }} }},
        undefined, undefined, {context(tmp_path)}), /progress.*checkpoint|checkpoint.*progress/i);
      assert.equal(shutdowns, 0);
    '''
    run_node(script, env=env)
    calls = [json.loads(line)["args"][1] for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert set(calls) == {"transition-context"}


@pytest.mark.parametrize("launch_kind", ["plain", "prompt", "node", "node-env", "extension-flag"])
def test_cross_checkout_refuses_unbound_launch_options(tmp_path, launch_kind):
    env = fixture_agent(tmp_path)
    target = tmp_path / "other"
    target.mkdir()
    (target / "policy.txt").write_text("different checkout prompt")
    tx_path = tmp_path / "transition.json"
    tx = json.loads(tx_path.read_text())
    tx.update(targetCheckout=str(target), targetBead="pi-b", mode="switch")
    tx_path.write_text(json.dumps(tx))
    flags = ["--append-system-prompt", "policy.txt"] if launch_kind == "prompt" else ["--custom-policy", "policy.txt"] if launch_kind == "extension-flag" else []
    node_flags = ["--require", "./guard.cjs"] if launch_kind == "node" else []
    script = loader_prelude() + f'''
      let shutdowns = 0;
      process.argv = [process.execPath, "/opt/pi/cli.js", ...{json.dumps(flags)}];
      process.execArgv = {json.dumps(node_flags)};
      process.env.NODE_OPTIONS = {json.dumps('--require ./guard.cjs' if launch_kind == 'node-env' else '')};
      process.once = () => process;
      const tool = extension.tools.get("handoff_bead").definition;
      const run = () => tool.execute("call", {{ targetBead: "pi-b" }}, undefined, undefined, {context(tmp_path)});
      if ({json.dumps(launch_kind)} === "plain") {{
        assert.equal((await run()).terminate, true);
        assert.equal(shutdowns, 1);
      }} else {{
        await assert.rejects(run, /Cross-checkout.*launch options/);
        assert.equal(shutdowns, 0);
      }}
    '''
    run_node(script, env=env)
    calls = [json.loads(line)["args"][1] for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    if launch_kind == "plain":
        assert "transition-stage" in calls and "transition-launch" in calls
    else:
        assert "transition-stage" not in calls and "transition-launch" not in calls
        assert not (tmp_path / "children" / "child.jsonl").exists()


@pytest.mark.parametrize("flag,value", [
    ("--system-prompt", ""), ("--append-system-prompt", ""),
    ("--append-system-prompt", "~/policy.txt"),
])
def test_same_checkout_preserves_original_prompt_tokens(tmp_path, flag, value):
    env = fixture_agent(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (home / "policy.txt").write_text("must not replace literal prompt")
    env["HOME"] = str(home)
    script = loader_prelude() + f'''
      let shutdowns = 0, onExit, invocation;
      process.argv = [process.execPath, "/opt/pi/cli.js", {json.dumps(flag)}, {json.dumps(value)}];
      process.once = (name, fn) => {{ if (name === "exit") onExit = fn; return process; }};
      process.execve = (...args) => {{ invocation = args; }};
      const tool = extension.tools.get("handoff_bead").definition;
      await tool.execute("call", {{ mode: "resume" }}, undefined, undefined, {context(tmp_path)});
      onExit(0);
      assert.equal(invocation[1][invocation[1].indexOf({json.dumps(flag)}) + 1], {json.dumps(value)});
    '''
    run_node(script, env=env)


def test_continuation_preserves_cli_restrictions_not_old_payload(tmp_path):
    env = fixture_agent(tmp_path)
    script = loader_prelude() + f'''
      let shutdowns = 0, onExit, invocation;
      process.argv = [process.execPath, "/opt/pi/cli.js", "--offline", "--no-approve", "--no-tools",
        "--tools", "read", "--exclude-tools", "bash", "--no-context-files", "--no-extensions",
        "--no-skills", "--no-prompt-templates", "--no-mcp", "--session", "old-session.jsonl",
        "--model", "fixture-model", "--provider", "fixture-provider", "--thinking", "high",
        "OLD_PROMPT_MUST_NOT_REPLAY", "@old-attachment.txt"];
      process.once = (name, fn) => {{ if (name === "exit") onExit = fn; return process; }};
      process.execve = (...args) => {{ invocation = args; }};
      const tool = extension.tools.get("handoff_bead").definition;
      await tool.execute("call", {{ mode: "resume" }}, undefined, undefined, {context(tmp_path)});
      onExit(0);
      const argv = invocation[1];
      for (const flag of ["--offline", "--no-approve", "--no-tools", "--no-context-files", "--no-extensions",
        "--no-skills", "--no-prompt-templates", "--no-mcp"]) assert.ok(argv.includes(flag), `lost ${{flag}}`);
      for (const [flag, value] of [["--tools", "read"], ["--exclude-tools", "bash"], ["--model", "fixture-model"],
        ["--provider", "fixture-provider"], ["--thinking", "high"]]) assert.equal(argv[argv.indexOf(flag) + 1], value);
      assert.equal(argv.filter(x => x === "--session").length, 1);
      assert.ok(!argv.includes("old-session.jsonl"));
      assert.ok(!argv.includes("OLD_PROMPT_MUST_NOT_REPLAY"));
      assert.ok(!argv.includes("@old-attachment.txt"));
    '''
    run_node(script, env=env)


def test_shutdown_request_failure_cancels_known_unlaunched_child(tmp_path):
    env = fixture_agent(tmp_path)
    script = loader_prelude() + f'''
      let shutdowns = 0;
      const ctx = {context(tmp_path)};
      ctx.shutdown = () => {{ throw new Error("shutdown rejected"); }};
      process.argv = [process.execPath, "/opt/pi/cli.js"];
      const tool = extension.tools.get("handoff_bead").definition;
      await assert.rejects(() => tool.execute("call", {{ mode: "resume" }}, undefined, undefined, ctx), /shutdown rejected/);
    '''
    run_node(script, env=env)
    assert json.loads((tmp_path / "transition.json").read_text())["state"] == "cancelled"


def test_nonzero_shutdown_compensates_without_launch(tmp_path):
    env = fixture_agent(tmp_path)
    script = loader_prelude() + f'''
      let shutdowns = 0, onExit;
      const saved = {{ once: process.once, execve: process.execve, argv: process.argv }};
      process.argv = [process.execPath, "/opt/pi/cli.js"];
      process.once = (name, fn) => {{ if (name === "exit") onExit = fn; return process; }};
      process.execve = () => {{ throw new Error("must not exec"); }};
      try {{
        const tool = extension.tools.get("handoff_bead").definition;
        await tool.execute("call", {{ mode: "resume" }}, undefined, undefined, {context(tmp_path)});
        onExit(1);
      }} finally {{ Object.assign(process, saved); }}
    '''
    run_node(script, env=env)
    assert json.loads((tmp_path / "transition.json").read_text())["state"] == "cancelled"


def test_malformed_or_legacy_reservation_has_bounded_diagnostic(tmp_path):
    env = fixture_agent(tmp_path)
    path = tmp_path / "transition.json"
    tx = json.loads(path.read_text())
    tx.pop("sourceSessionFile")
    path.write_text(json.dumps(tx))
    script = loader_prelude() + f'''
      let shutdowns = 0;
      process.argv = [process.execPath, "/opt/pi/cli.js"];
      const tool = extension.tools.get("handoff_bead").definition;
      await assert.rejects(() => tool.execute("call", {{ mode: "resume" }}, undefined, undefined, {context(tmp_path)}), /Invalid continuation reservation/);
      assert.equal(shutdowns, 0);
    '''
    run_node(script, env=env)


def test_headless_continuation_returns_manifest_without_mutation(tmp_path):
    env = fixture_agent(tmp_path)
    script = loader_prelude() + f'''
      let shutdowns = 0;
      const tool = extension.tools.get("handoff_bead").definition;
      const result = await tool.execute("call", {{ mode: "resume" }}, undefined, undefined, {context(tmp_path, mode="rpc")});
      assert.equal(result.details.status, "host-required");
      assert.equal(shutdowns, 0);
      assert.notEqual(result.terminate, true);
    '''
    run_node(script, env=env)
    calls = [json.loads(line)["args"][1] for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert calls == ["transition-context"]


def test_startup_attaches_reserved_child_before_tools(tmp_path):
    env = fixture_agent(tmp_path)
    script = loader_prelude() + f'''
      let shutdowns = 0;
      const handler = extension.handlers.get("session_start")?.[0];
      assert.equal(typeof handler, "function");
      await handler({{ reason: "startup" }}, {context(tmp_path, session="11111111-1111-4111-8111-111111111111")});
      assert.equal(shutdowns, 0);
    '''
    run_node(script, env=env)
    assert json.loads((tmp_path / "transition.json").read_text())["state"] == "attached"


def test_failed_startup_attachment_blocks_tools_and_shuts_down(tmp_path):
    env = {**fixture_agent(tmp_path), "FAIL_ATTACH": "1"}
    script = loader_prelude() + f'''
      let shutdowns = 0;
      await extension.handlers.get("session_start")[0]({{ reason: "startup" }}, {context(tmp_path, session="11111111-1111-4111-8111-111111111111")});
      assert.equal(shutdowns, 1);
      const blocked = await extension.handlers.get("tool_call")[0]({{ toolName: "bash" }});
      assert.equal(blocked.block, true);
    '''
    run_node(script, env=env)


def run_host(tmp_path, env, body):
    script = loader_prelude() + f"""
      import {{ existsSync }} from "node:fs";
      let shutdowns = 0;
      const ctx = {context(tmp_path)};
      const tool = extension.tools.get("handoff_bead").definition;
      const saved = {{ once: process.once, execve: process.execve, argv: process.argv }};
      process.argv = [process.execPath, "/opt/pi/cli.js"];
      process.once = () => process;
      process.execve = () => {{ throw new Error("test must not execute replacement"); }};
      const childFile = {str(tmp_path / "children" / "child.jsonl")!r};
      try {{ {body} }} finally {{ Object.assign(process, saved); }}
    """
    try:
        run_node(script, env=env)
    except subprocess.CalledProcessError as exc:
        pytest.fail(exc.stderr, pytrace=False)


def pending_isolation(tmp_path):
    env = {**fixture_agent(tmp_path), "PENDING_TRANSITION": "1"}
    path = tmp_path / "transition.json"
    tx = json.loads(path.read_text())
    tx.update(state="isolating", mode="switch", targetBead="pi-b")
    path.write_text(json.dumps(tx))
    return env, tx


def commands(tmp_path):
    return [json.loads(line)["args"][1] for line in (tmp_path / "calls.jsonl").read_text().splitlines()]


@pytest.mark.parametrize("explicit", [True, False])
def test_host_recovers_reserved_isolation_once(tmp_path, explicit):
    env, tx = pending_isolation(tmp_path)
    options = {"transitionId": tx["id"]} if explicit else {}
    run_host(tmp_path, env, f"""
      const result = await tool.execute("call", {json.dumps(options)}, undefined, undefined, ctx);
      assert.equal(result.details.status, "restart-requested");
      assert.equal(result.details.targetBead, "pi-b");
      assert.equal(result.terminate, true);
      assert.equal(shutdowns, 1);
      assert.ok(existsSync(childFile));
    """)
    calls = commands(tmp_path)
    assert calls.count("transition-isolate") == 1
    assert "transition-prepare" not in calls and "checkpoint" not in calls


def test_host_preserves_blocked_isolation_without_staging(tmp_path):
    env, tx = pending_isolation(tmp_path)
    env["BLOCK_ISOLATION"] = "1"
    run_host(tmp_path, env, f"""
      const result = await tool.execute("call", {{ transitionId: {tx["id"]!r} }}, undefined, undefined, ctx);
      assert.equal(result.details.status, "reconciliation-required");
      assert.equal(result.details.transition.state, "isolating");
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)
    assert commands(tmp_path).count("transition-isolate") == 1
    assert "transition-stage" not in commands(tmp_path)


@pytest.mark.parametrize("blocked", [False, True])
def test_host_finishes_recorded_cancellation_without_restarting_effect(tmp_path, blocked):
    env, tx = pending_isolation(tmp_path)
    tx["cancelRequested"] = True
    (tmp_path / "transition.json").write_text(json.dumps(tx))
    if blocked:
        env["BLOCK_CANCELLATION"] = "1"
    expected = "reconciliation-required" if blocked else "cancelled"
    run_host(tmp_path, env, f"""
      const result = await tool.execute("call", {{ transitionId: {tx["id"]!r} }}, undefined, undefined, ctx);
      assert.equal(result.details.status, {expected!r});
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)
    assert commands(tmp_path).count("transition-cancel") == 1
    assert "transition-isolate" not in commands(tmp_path)


def test_host_rejects_changed_isolation_reservation(tmp_path):
    env, tx = pending_isolation(tmp_path)
    env["CHANGE_RESERVATION"] = "1"
    run_host(tmp_path, env, f"""
      await assert.rejects(() => tool.execute("call", {{ transitionId: {tx["id"]!r} }},
        undefined, undefined, ctx), /reservation changed/);
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)
    assert "transition-stage" not in commands(tmp_path)


@pytest.mark.parametrize("options", [
    {"mode": "resume"},
    {"targetBead": "pi-c"},
    {"checkpointRef": "c" * 32},
])
def test_host_does_not_ignore_changed_pending_request(tmp_path, options):
    env, tx = pending_isolation(tmp_path)
    tx["state"] = "prepared"
    (tmp_path / "transition.json").write_text(json.dumps(tx))
    options = {**options, "transitionId": tx["id"]}
    run_host(tmp_path, env, f"""
      await assert.rejects(() => tool.execute("call", {json.dumps(options)},
        undefined, undefined, ctx), /conflicts with reserved transition/);
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)
    assert "transition-stage" not in commands(tmp_path)


def test_lost_launch_acknowledgement_compensates_before_shutdown(tmp_path):
    env = {**fixture_agent(tmp_path), "FAIL_AFTER_LAUNCH": "1"}
    run_host(tmp_path, env, """
      await assert.rejects(() => tool.execute("call", { mode: "resume" }, undefined, undefined, ctx));
      assert.equal(shutdowns, 0);
    """)
    calls = [json.loads(line)["args"] for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    compensation = next(args for args in calls if args[1] == "transition-abort-launch")
    assert compensation[-1] == "launch-request-failed"
    assert json.loads((tmp_path / "transition.json").read_text())["state"] == "cancelled"


def test_isolation_failure_does_not_present_stale_state_as_current(tmp_path):
    env, tx = pending_isolation(tmp_path)
    env.update(BLOCK_ISOLATION="1", BLOCK_NO_TRANSITION="1")
    run_host(tmp_path, env, f"""
      const result = await tool.execute("call", {{ transitionId: {tx["id"]!r} }}, undefined, undefined, ctx);
      assert.equal(result.details.status, "reconciliation-required");
      assert.equal(result.details.transition, undefined);
      assert.equal(result.details.lastObservedTransition.id, {tx["id"]!r});
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)


def test_unexpected_isolation_exit_remains_failure(tmp_path):
    env, tx = pending_isolation(tmp_path)
    env.update(BLOCK_ISOLATION="1", FAILURE_EXIT_CODE="1")
    run_host(tmp_path, env, f"""
      await assert.rejects(() => tool.execute("call", {{ transitionId: {tx["id"]!r} }},
        undefined, undefined, ctx));
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)


@pytest.mark.parametrize("cancelling", [False, True])
@pytest.mark.parametrize("unbound", [False, True])
def test_headless_pending_isolation_is_read_only(tmp_path, cancelling, unbound):
    env, tx = pending_isolation(tmp_path)
    tx["cancelRequested"] = cancelling
    if unbound:
        tx["childSessionFile"] = None
    (tmp_path / "transition.json").write_text(json.dumps(tx))
    run_host(tmp_path, env, f"""
      ctx.mode = "rpc";
      const result = await tool.execute("call", {{ transitionId: {tx["id"]!r} }}, undefined, undefined, ctx);
      assert.equal(result.details.status, "host-required");
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)
    assert commands(tmp_path) == ["transition-context"]


def test_slash_recovery_displays_blocked_outcome(tmp_path):
    env, tx = pending_isolation(tmp_path)
    env["BLOCK_ISOLATION"] = "1"
    run_host(tmp_path, env, f"""
      const notices = [];
      ctx.ui.notify = (message, level) => notices.push({{ message, level }});
      await extension.commands.get("handoff-bead").handler("recover {tx["id"]}", ctx);
      assert.equal(shutdowns, 0);
      assert.equal(notices.length, 1);
      assert.equal(notices[0].level, "warning");
      assert.match(notices[0].message, /reconciliation-required/);
      assert.ok(notices[0].message.includes({tx["id"]!r}));
    """)


@pytest.mark.parametrize("state,cancelling", [("prepared", False), ("isolating", False), ("isolating", True)])
def test_host_recovers_crash_before_child_path_binding(tmp_path, state, cancelling):
    env, tx = pending_isolation(tmp_path)
    tx.update(state=state, childSessionFile=None, cancelRequested=cancelling)
    (tmp_path / "transition.json").write_text(json.dumps(tx))
    expected = "cancelled" if cancelling else "restart-requested"
    run_host(tmp_path, env, f"""
      const result = await tool.execute("call", {{ transitionId: {tx['id']!r} }}, undefined, undefined, ctx);
      assert.equal(result.details.status, {expected!r});
      assert.equal(shutdowns, {0 if cancelling else 1});
    """)
    assert commands(tmp_path).count("transition-bind-child") == 1
    repaired = json.loads((tmp_path / "transition.json").read_text())
    assert repaired["childSession"] == tx["childSession"]
    assert repaired["id"] == tx["id"]
    if cancelling:
        assert "transition-isolate" not in commands(tmp_path)
        assert not (tmp_path / "children" / "child.jsonl").exists()


def test_child_path_repair_cannot_change_other_identity(tmp_path):
    env, tx = pending_isolation(tmp_path)
    tx["childSessionFile"] = None
    (tmp_path / "transition.json").write_text(json.dumps(tx))
    env["CHANGE_BIND_RESERVATION"] = "1"
    run_host(tmp_path, env, f"""
      await assert.rejects(() => tool.execute("call", {{ transitionId: {tx['id']!r} }},
        undefined, undefined, ctx), /reservation changed/);
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)
    assert "transition-isolate" not in commands(tmp_path)


def test_cancelled_unbound_reservation_needs_no_repair(tmp_path):
    env, tx = pending_isolation(tmp_path)
    tx.update(state="cancelled", childSessionFile=None)
    (tmp_path / "transition.json").write_text(json.dumps(tx))
    run_host(tmp_path, env, f"""
      const result = await tool.execute("call", {{ transitionId: {tx['id']!r} }}, undefined, undefined, ctx);
      assert.equal(result.details.status, "cancelled");
      assert.equal(shutdowns, 0);
      assert.ok(!existsSync(childFile));
    """)
    assert commands(tmp_path) == ["transition-context", "transition-recover"]
