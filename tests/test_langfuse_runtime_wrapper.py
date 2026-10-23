from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from conftest import run_node

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi/agent/extensions/langfuse-config-env.ts"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_release(agent: Path, code: str | None = None, *, overrides: dict[str, str] | None = None) -> Path:
    files = {
        "package.json": '{"name":"pi-langfuse","type":"module","main":"index.js"}',
        "index.js": code or """
            import { state } from './src/state.js';
            export default function register(pi) {
              state.registrations++;
              pi.registerCommand('isolated-langfuse', {});
            }
        """,
        "src/state.js": "export const state = { registrations: 0 };",
        "src/quality.js": """
            import { state } from './state.js';
            export function createObservationCapturePort() {
              return { capture: async () => {
                globalThis.__registeredState = state.registrations;
                return {complete:true, gaps:[]};
              }};
            }
        """,
    }
    files.update(overrides or {})
    payload = {"inputs": {"index.ts": digest(b"source")},
               "files": {name: digest(data.encode()) for name, data in sorted(files.items())},
               "dependencies": {"fixture/index.js": digest(b"export {};\n")}}
    identity = digest(json.dumps(payload, separators=(",", ":")).encode())
    source = "../runtime/pi-langfuse/releases/" + identity
    release = agent.parent / "runtime/pi-langfuse/releases" / identity
    for name, data in files.items():
        path = release / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
    package = release / "node_modules/fixture/index.js"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"export {};\n")
    (release / "release.json").write_text(json.dumps({"schemaVersion": 1, "id": identity, **payload}))
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "settings.json").write_text(json.dumps({"packages": [{"source": source, "extensions": []}]}))
    return release


def shared_poison(agent: Path) -> None:
    shared = agent / "npm/node_modules/pi-langfuse"
    shared.mkdir(parents=True)
    (shared / "package.json").write_text('{"name":"pi-langfuse","type":"module","main":"index.js","exports":{".":"./index.js","./quality":"./index.js"}}')
    (shared / "index.js").write_text("globalThis.__sharedLoaded = true; export default () => {};")


def test_wrapper_uses_one_verified_release_for_registration_and_quality(tmp_path):
    agent = tmp_path / ".pi/agent"
    make_release(agent)
    shared_poison(agent)
    run_node(f"""
        import assert from 'node:assert/strict';
        process.env.PI_CODING_AGENT_DIR = {str(agent)!r};
        const {{ default: install }} = await import({EXTENSION.as_uri()!r});
        const commands = [];
        let accept;
        await install({{ on() {{}}, registerCommand(name) {{ commands.push(name); }},
          events: {{ on(_name, callback) {{ accept = callback; }} }} }});
        assert.deepEqual(commands, ['isolated-langfuse']);
        let capture;
        accept(value => capture = value);
        await capture('proof', {{}}, {{asType:'agent'}});
        assert.equal(globalThis.__registeredState, 1);
        assert.equal(globalThis.__sharedLoaded, undefined);
    """)


@pytest.mark.parametrize("fault", ["code", "dependency", "extra", "symlink", "descriptor", "missing", "enabled", "duplicate"])
def test_wrapper_never_imports_unverified_or_shared_fallback(tmp_path, fault):
    agent = tmp_path / ".pi/agent"
    release = make_release(agent)
    shared_poison(agent)
    if fault == "code":
        (release / "index.js").write_text("globalThis.__unverifiedLoaded = true; export default () => {};")
    elif fault == "dependency":
        (release / "node_modules/fixture/index.js").write_text("changed")
    elif fault == "extra":
        (release / "node_modules/unlocked.js").write_text("unexpected")
    elif fault == "symlink":
        (release / "unowned").symlink_to(tmp_path)
    elif fault == "descriptor":
        data = json.loads((release / "release.json").read_text())
        data["files"]["index.js"] = "0" * 64
        (release / "release.json").write_text(json.dumps(data))
    else:
        data = json.loads((agent / "settings.json").read_text())
        if fault == "missing":
            data["packages"][0]["source"] = "../runtime/pi-langfuse/releases/" + "0" * 64
        elif fault == "enabled":
            del data["packages"][0]["extensions"]
        else:
            data["packages"].append(data["packages"][0])
        (agent / "settings.json").write_text(json.dumps(data))
    run_node(f"""
        import assert from 'node:assert/strict';
        process.env.PI_CODING_AGENT_DIR = {str(agent)!r};
        const {{ default: install }} = await import({EXTENSION.as_uri()!r});
        const commands = [];
        const diagnostics = [];
        console.error = message => diagnostics.push(message);
        await install({{ on() {{}}, registerCommand(name) {{ commands.push(name); }} }});
        assert.deepEqual(commands, []);
        assert.equal(globalThis.__sharedLoaded, undefined);
        assert.equal(globalThis.__unverifiedLoaded, undefined);
        assert.deepEqual(diagnostics, ['[langfuse-projection] verified Langfuse runtime is unavailable']);
    """)
