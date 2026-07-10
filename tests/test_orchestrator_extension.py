from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "orchestrator-service.ts"
SETTINGS = ROOT / "pi" / "agent" / "settings.json"


def source() -> str:
    return EXTENSION.read_text(encoding="utf-8")


def parse_safe_tools(text: str) -> list[str]:
    match = re.search(r"ORCHESTRATOR_SAFE_TOOLS\s*=\s*\[([\s\S]*?)\]\s*as const", text)
    assert match, "ORCHESTRATOR_SAFE_TOOLS const array is required"
    return re.findall(r'"([a-zA-Z0-9_]+)"', match.group(1))


def extract_async_function_body(text: str, name: str) -> str:
    marker = f"async function {name}"
    start = text.index(marker)
    open_brace = text.index("{", start)
    depth = 0
    for index in range(open_brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1 : index]
    raise AssertionError(f"could not extract {name}")


def js_async_function(text: str, name: str, params: str) -> str:
    return f"async function {name}({params}) {{\n{extract_async_function_body(text, name)}\n}}"


def test_orchestrator_extension_file_exists_and_registers_lifecycle_hooks():
    text = source()

    assert "export default function orchestratorService" in text
    assert 'pi.on("session_start"' in text
    assert 'pi.on("session_shutdown"' in text
    assert "idempotent" in text.lower()


def test_orchestrator_extension_runs_startup_health_and_daemon_lifecycle():
    text = source()

    assert '"doctor", "--profile", "orchestrator-startup", "--json"' in text
    assert '"work", "daemon", "status", "--json"' in text
    assert '"work", "daemon", "start", "--json"' in text
    assert '"work", "daemon", "stop", "--force", "--json"' in text
    assert '"work", "runner", "status", "--json"' in text
    assert '"work", "runner", "resume", "--json"' in text
    assert "schedulerEnabled" in text
    assert '"/v1/leases"' in text
    assert 'method: "POST"' in text
    assert 'method: "DELETE"' in text
    assert '"/v1/drain"' not in text


def test_orchestrator_extension_stops_async_startup_after_shutdown_begins():
    text = source()

    assert "abortStartup" in text
    assert "if (state.shutdownStarted) return;" in text
    assert "await abortStartup(state);" in text
    assert "if (state.shutdownStarted) return;\n\t\t\tstartStatusPolling(ctx, state);" in text


def test_orchestrator_extension_suppresses_expected_shutdown_fetch_failures():
    text = source()

    assert "isExpectedShutdownError" in text
    assert "showShutdownWarning" in text
    shutdown = text.split('pi.on("session_shutdown"', 1)[1]
    assert "isExpectedShutdownError(err)" in shutdown
    assert "showFailure(ctx, err)" not in shutdown.split('pi.registerCommand("runner"', 1)[0]


def test_orchestrator_extension_releases_lease_accepted_during_inflight_attach(tmp_path):
    text = source()
    harness = tmp_path / "lease-race-harness.mjs"
    harness.write_text(
        textwrap.dedent(
            f"""
            const randomUUID = () => "test-uuid";
            const ctx = {{ cwd: "/tmp/pi-test" }};
            const state = {{ shutdownStarted: false }};
            const activeLeases = new Set();
            let acceptedLeaseId;
            let postAccepted;
            const accepted = new Promise((resolve) => {{ postAccepted = resolve; }});
            let resolvePost;
            const finishPost = new Promise((resolve) => {{ resolvePost = resolve; }});

            async function runnerRequest(cwd, path, init = {{}}) {{
              if (path === "/v1/leases" && init.method === "POST") {{
                const body = JSON.parse(init.body);
                acceptedLeaseId = body.leaseId;
                activeLeases.add(acceptedLeaseId);
                postAccepted();
                await finishPost;
                return {{ ok: true }};
              }}
              if (path.startsWith("/v1/leases/") && init.method === "DELETE") {{
                activeLeases.delete(decodeURIComponent(path.slice("/v1/leases/".length)));
                return {{ released: true }};
              }}
              throw new Error(`unexpected request ${{init.method}} ${{path}}`);
            }}

            {js_async_function(text, "attachLease", "ctx, state, signal")}
            {js_async_function(text, "releaseLease", "ctx, state")}

            const attachPromise = attachLease(ctx, state);
            await accepted;
            await releaseLease(ctx, state);
            if (activeLeases.size !== 0) {{
              throw new Error(`orphaned accepted lease ${{acceptedLeaseId}}; state=${{JSON.stringify(state)}}`);
            }}
            resolvePost({{ ok: true }});
            await attachPromise;
            if (activeLeases.size !== 0 || state.leaseId || state.pendingLeaseId) {{
              throw new Error(`lease revived after shutdown; active=${{activeLeases.size}} state=${{JSON.stringify(state)}}`);
            }}
            """
        ),
        encoding="utf-8",
    )

    result = subprocess.run(["node", str(harness)], text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr or result.stdout


def test_orchestrator_extension_restricts_tools_to_safe_orchestrator_surface():
    text = source()
    tools = parse_safe_tools(text)

    assert tools == [
        "read",
        "ticket_gateway",
        "ticket_question",
        "ticket_approval",
        "ticket_decision_resolve",
        "recall",
    ]
    assert "pi.setActiveTools(ORCHESTRATOR_SAFE_TOOLS" in text
    forbidden = {"bash", "edit", "write", "subagent", "manage_todo_list", "ask"}
    assert forbidden.isdisjoint(tools)


def test_orchestrator_extension_has_explicit_repair_tools_mode():
    text = source()

    assert 'pi.registerFlag("orchestrator-repair-tools"' in text
    assert "PI_ORCHESTRATOR_REPAIR_TOOLS" in text
    assert "repairToolsEnabled" in text
    assert "repairToolsActive" in text
    assert "orch repair-tools" in text
    assert "repair-tools" in text.split('pi.registerCommand("runner"', 1)[1]


def test_orchestrator_extension_only_skips_tool_restriction_in_repair_mode():
    text = source()
    session_start = text.split('pi.on("session_start"', 1)[1].split('// idempotent shutdown', 1)[0]

    assert "restrictTools(pi);" not in session_start
    assert "applyToolMode(pi, ctx, state);" in session_start
    assert "restrictTools(pi);" in extract_async_function_body(text, "applyToolMode")
    assert "state.repairToolsActive" in extract_async_function_body(text, "applyToolMode")


def test_orchestrator_extension_surfaces_status_without_large_json_dumps():
    text = source()

    assert 'ctx.ui.setStatus("orchestrator-service"' in text
    assert 'ctx.ui.setWidget("orchestrator-service"' in text
    assert "summarizeRunnerStatus" in text
    assert "slice(0, 8)" in text or "slice(0, 10)" in text


def test_orchestrator_extension_does_not_shell_to_raw_beads_or_mutating_tools():
    text = source()

    forbidden_patterns = [
        r'execFile\(\s*["\']bd["\']',
        r'execFile\(\s*["\']beads["\']',
        r'pi\.exec\(\s*["\']bd["\']',
        r'pi\.exec\(\s*["\']beads["\']',
        r'registerTool\(\{\s*name:\s*["\']bash["\']',
        r'registerTool\(\{\s*name:\s*["\']edit["\']',
        r'registerTool\(\{\s*name:\s*["\']write["\']',
        r'registerTool\(\{\s*name:\s*["\']subagent["\']',
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, text), pattern


def test_orchestrator_extension_is_project_configured_by_autodiscovery():
    assert SETTINGS.is_file()
    assert EXTENSION.parent == ROOT / "pi" / "agent" / "extensions"
