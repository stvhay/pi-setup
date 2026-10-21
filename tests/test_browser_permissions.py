import json
from pathlib import Path

from conftest import run_node
from test_process_restart import loader_prelude

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "pi/agent/extensions/lib/browser-permissions.ts"
EXTENSION = ROOT / "pi/agent/extensions/browser-permissions.ts"
OLD_GUIDANCE = "- Remote files require explicit user approval and the host's approval-gated download surface; never enable downloads in an ordinary run."


def library_script(tmp_path):
    assert LIB.exists(), "browser permission policy implementation is required"
    return f'''
      import assert from "node:assert/strict";
      import {{ mkdirSync, writeFileSync, unlinkSync, symlinkSync, readFileSync, statSync }} from "node:fs";
      import {{ join }} from "node:path";
      import {{ readPolicy, networkDecision, approvalMatches, saveApproval }} from {str(LIB)!r};
      const root = {str(tmp_path)!r};
      const project = join(root, "project");
      const receipts = join(root, "runtime", "browser-permissions");
      mkdirSync(join(project, ".perms"), {{recursive: true}});
      const put = (name, value) => writeFileSync(join(project, ".perms", name), value);
      const policy = () => readPolicy(project, undefined);
      const allowed = (p, url, details) => networkDecision(p, url, details).allowed;
    '''


def test_policy_defaults_parser_and_destination_matching(tmp_path):
    run_node(library_script(tmp_path) + r'''
      let p = policy();
      assert.equal(p.downloads, "allow");
      assert.equal(p.configured, false);
      assert.equal(approvalMatches(p, receipts), true);
      assert.equal(allowed(p, "https://example.com"), true);
      put("downloads", "# deliberate restriction\nask\n");
      assert.equal(policy().downloads, "ask");
      assert.equal(readPolicy(project, "deny").downloads, "deny");
      assert.throws(() => readPolicy(project, "sometimes"), /download/i);
      put("net-allowlist", "# endpoints\nExample.COM.\n*.example.org\nlocalhost:3000\n127.0.0.1:8000\n[::1]:9000\n");
      p = policy();
      for (const url of ["https://example.com", "https://EXAMPLE.COM./", "https://a.example.org", "https://a.b.example.org", "http://localhost:3000", "http://127.0.0.1:8000", "http://[::1]:9000"]) {
        assert.equal(allowed(p, url), true, url);
      }
      for (const url of ["https://other.test", "https://sub.example.com", "https://example.org", "https://badexample.org", "https://example.com.evil.test", "http://localhost:3001", "http://127.0.0.1:8001", "http://[::1]:9001"]) {
        assert.equal(allowed(p, url), false, url);
      }
      put("net-allowlist", "example.com:443\n");
      assert.equal(allowed(policy(), "https://example.com"), true);
      assert.equal(allowed(policy(), "wss://example.com"), true);
      assert.equal(allowed(policy(), "http://example.com"), false);
      put("net-blocklist", "example.com\n");
      assert.equal(allowed(policy(), "https://example.com"), false, "block wins");
      unlinkSync(join(project, ".perms", "net-blocklist"));
      put("net-allowlist", "# intentionally empty\n");
      assert.equal(allowed(policy(), "https://example.com"), false);
      unlinkSync(join(project, ".perms", "net-allowlist"));
      assert.equal(allowed(policy(), "https://example.com"), true);
      for (const line of ["https://example.com", "example.com/path", "user@example.com", "*", "*.127.0.0.1", "foo.*.com", "example.com:0", "example.com:65536", "example.com:", "exa mple.com", "127.1", "0x7f000001", "a..com", "-bad.com", "[::1", "::1", "a.com?x", "a.com\\evil", "foo\u0000bar"]) {
        put("net-allowlist", line);
        assert.throws(policy, /policy|rule|host|port/i, line);
      }
      put("net-allowlist", "a".repeat(65537));
      assert.throws(policy, /large|size/i);
      unlinkSync(join(project, ".perms", "net-allowlist"));
      put("downloads", "");
      assert.throws(policy, /download/i);
      put("downloads", "allow\ndeny");
      assert.throws(policy, /download/i);
      unlinkSync(join(project, ".perms", "downloads"));
      symlinkSync(join(root, "missing"), join(project, ".perms", "downloads"));
      assert.throws(policy, /symbolic|symlink|link/i);
    ''')


def test_policy_transport_checks_names_and_resolved_addresses(tmp_path):
    run_node(library_script(tmp_path) + r'''
      put("net-allowlist", "example.com:443\n");
      const details = {resourceType: "transport-address", resolvedFrom: "example.com"};
      assert.equal(allowed(policy(), "https://93.184.216.34:443", details), true);
      assert.equal(allowed(policy(), "https://93.184.216.34:443"), false);
      assert.equal(allowed(policy(), "https://93.184.216.34:443", {...details, resolvedFrom: "evil.test"}), false);
      put("net-blocklist", "93.184.216.34\n");
      assert.equal(allowed(policy(), "https://93.184.216.34:443", details), false);
      put("net-blocklist", "example.com\n");
      assert.equal(allowed(policy(), "https://93.184.216.34:443", details), false);
      put("net-blocklist", "127.0.0.1\n");
      assert.equal(allowed(policy(), "https://[::ffff:127.0.0.1]:443", details), false);
      put("net-blocklist", "");
      for (const bad of ["example.com/path", "user@example.com", "example.com:443", "*.example.com"]) {
        assert.equal(allowed(policy(), "https://93.184.216.34:443", {...details, resolvedFrom: bad}), false);
      }
      assert.equal(allowed(policy(), "https://evil.test", {resourceType: "document", resolvedFrom: "example.com"}), false);
      assert.equal(allowed(policy(), "file:///etc/passwd"), false);
    ''')


def test_receipts_bind_root_content_and_policy_removal(tmp_path):
    run_node(library_script(tmp_path) + r'''
      put("net-allowlist", "example.com\n");
      const p = policy();
      assert.equal(approvalMatches(p, receipts), false);
      const target = saveApproval(p, receipts);
      assert.equal(approvalMatches(p, receipts), true);
      assert.equal(statSync(target).mode & 0o777, 0o600);
      assert.equal(statSync(receipts).mode & 0o777, 0o700);
      put("net-allowlist", "example.org\n");
      assert.equal(approvalMatches(policy(), receipts), false);
      unlinkSync(join(project, ".perms", "net-allowlist"));
      assert.equal(approvalMatches(policy(), receipts), false, "deletion cannot widen saved policy");
      const other = join(root, "other");
      mkdirSync(join(other, ".perms"), {recursive: true});
      writeFileSync(join(other, ".perms", "net-allowlist"), "example.com\n");
      assert.equal(approvalMatches(readPolicy(other), receipts), false);
      writeFileSync(target, "garbage");
      assert.throws(() => approvalMatches(p, receipts), /receipt/i);
      unlinkSync(target);
      symlinkSync(join(root, "elsewhere"), target);
      assert.throws(() => saveApproval(p, receipts), /symbolic|symlink|link/i);
      unlinkSync(target);
      writeFileSync(target, JSON.stringify({schemaVersion: 1, root: other, fingerprint: p.fingerprint}));
      assert.throws(() => approvalMatches(p, receipts), /receipt/i);
    ''')


def fake_package(agent_dir, *, prompt=OLD_GUIDANCE):
    package = agent_dir / "npm/node_modules/betterwright"
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"type": "module", "exports": {
        "./pi-extension": "./extension.js", "./policy": "./policy.js", "./prompt": "./prompt.js",
    }}))
    (package / "prompt.js").write_text(f"export const agentSystemPrompt = () => {json.dumps(prompt)};\n")
    (package / "policy.js").write_text('''
      export class NetworkPolicy {
        constructor(options = {}) { this.custom = options.custom; }
        check(url, details = {}) {
          if (url.includes("169.254.169.254") || url.includes("metadata.google.internal")) return {allowed: false, reason: "metadata"};
          if (!/^https?:|^wss?:/.test(url)) return {allowed: false, reason: "scheme"};
          return this.custom?.(url, details) ?? {allowed: true};
        }
      }
    ''')
    (package / "extension.js").write_text('''
      import {agentSystemPrompt} from './prompt.js';
      export function createPiExtension(options) {
        globalThis.bw = {options, calls: 0, confirms: 0, closed: 0};
        return (pi) => {
          let instance;
          let tail = Promise.resolve();
          const serialize = operation => {
            const result = tail.then(operation);
            tail = result.catch(() => {});
            return result;
          };
          const get = () => instance ??= {...options.browserOptions};
          for (const name of ["browser", "browser_download", "browser_evidence", "browser_login", "browser_visibility"]) {
            pi.registerTool({name, label: name, description: "Browser. This approval-gated variant may save a remote file.",
              parameters: {type: "object", properties: {}},
              execute: (_id, _params, _signal, _update, ctx) => serialize(async () => {
                const browser = get();
                if (name === "browser_download") {
                  if (browser.downloadPolicy === "deny") throw new Error("downloads disabled");
                  if (browser.downloadPolicy === "ask") {
                    if (!ctx.hasUI) throw new Error("no approval UI");
                    globalThis.bw.confirms++;
                    if (!await ctx.ui.confirm("Allow browser download?", "One step")) throw new Error("not approved");
                  }
                }
                globalThis.bw.calls++;
                globalThis.bw.onStart?.();
                if (globalThis.bw.hold) await globalThis.bw.hold;
                return {content: [{type: "text", text: browser.downloadPolicy}], details: {}};
              })});
          }
          pi.registerCommand("browser-visibility", {description: "visibility", handler: () => {globalThis.bw.calls++;}});
          pi.on("before_agent_start", event => ({systemPrompt: event.systemPrompt + "\\n" + agentSystemPrompt()}));
          pi.on("session_shutdown", async () => {await tail; globalThis.bw.closed++;});
        };
      }
    ''')


def adapter_script(tmp_path, *, prompt=OLD_GUIDANCE):
    assert EXTENSION.exists(), "tracked browser composition is required"
    agent_dir = tmp_path / "agent"
    fake_package(agent_dir, prompt=prompt)
    project = tmp_path / "project"
    (project / ".perms").mkdir(parents=True)
    script = loader_prelude(extension_path=EXTENSION) + f'''
      import {{writeFileSync, unlinkSync}} from "node:fs";
      const project = {str(project)!r};
      const put = (name, value) => writeFileSync(project + "/.perms/" + name, value);
      let confirmations = 0, reloads = 0;
      const ctx = {{cwd: project, hasUI: true, ui: {{
        confirm: async () => {{confirmations++; return true;}}, notify() {{}},
      }}, reload: async () => {{reloads++;}}}};
      const fire = async (name, event = {{}}) => {{
        let result;
        for (const handler of extension.handlers.get(name) ?? []) result = await handler(event, ctx) ?? result;
        return result;
      }};
      const call = (name = "browser_download", context = ctx) => extension.tools.get(name).definition.execute("call", {{}}, undefined, undefined, context);
    '''
    env = {"PI_CODING_AGENT_DIR": str(agent_dir), "BETTERWRIGHT_PI_DOWNLOAD_POLICY": ""}
    return script, env


def test_adapter_defaults_prompt_and_existing_lifecycle(tmp_path):
    script, env = adapter_script(tmp_path)
    run_node(script + r'''
      await fire("session_start");
      await call(); await call();
      assert.equal(confirmations, 0);
      assert.equal(bw.calls, 2);
      await assert.rejects(() => call("browser", {...ctx, cwd: project + "/.perms"}), /policy|approval/i);
      assert.equal(bw.options.browserOptions.downloadPolicy, "allow");
      const result = await fire("before_agent_start", {systemPrompt: "User instructions stay"});
      assert.match(result.systemPrompt, /User instructions stay/);
      assert.match(result.systemPrompt, /downloads.*allow/i);
      assert.doesNotMatch(result.systemPrompt, /Remote files require explicit user approval/);
      assert.doesNotMatch(extension.tools.get("browser_download").definition.description, /approval-gated variant/);
      await extension.commands.get("browser-visibility").handler("visible", ctx);
      await fire("session_shutdown");
      assert.equal(bw.closed, 1);
      assert.equal(bw.calls, 3);
      put("downloads", "deny");
      await assert.rejects(call, /policy|approval/i);
      await assert.rejects(() => extension.commands.get("browser-visibility").handler("visible", ctx), /policy|approval/i);
      assert.equal(bw.calls, 3);
      assert.equal(bw.options.browserOptions.policy.check("https://example.com").allowed, false);
    ''', env=env)


def test_adapter_ask_deny_and_metadata_floor(tmp_path):
    script, env = adapter_script(tmp_path)
    env["BETTERWRIGHT_PI_DOWNLOAD_POLICY"] = "ask"
    run_node(script + r'''
      await fire("session_start");
      await call(); await call();
      assert.equal(confirmations, 2);
      assert.match((await fire("before_agent_start", {systemPrompt: "base"})).systemPrompt, /approval.*browser_download|browser_download.*approval/i);
      await assert.rejects(() => call("browser_download", {...ctx, hasUI: false}), /approval UI/);
      ctx.ui.confirm = async () => {put("downloads", "allow"); return true;};
      await assert.rejects(call, /policy|approval/i);
      assert.equal(bw.calls, 2, "recheck policy after UI wait");
    ''', env=env)
    # A separate process uses a fresh adapter, not a previously launched client.
    (tmp_path / "project/.perms/downloads").unlink()
    env["BETTERWRIGHT_PI_DOWNLOAD_POLICY"] = "deny"
    run_node(script + r'''
      await fire("session_start");
      await assert.rejects(call, /disabled/);
      assert.equal(confirmations, 0);
      assert.equal(bw.options.browserOptions.policy.check("https://169.254.169.254").allowed, false);
      assert.match((await fire("before_agent_start", {systemPrompt: "base"})).systemPrompt, /downloads.*deny|downloads.*disabled/i);
    ''', env=env)


def test_adapter_approval_is_explicit_bound_and_persistent(tmp_path):
    script, env = adapter_script(tmp_path)
    run_node(script + r'''
      put("downloads", "allow");
      put("net-allowlist", "example.com\n");
      await fire("session_start");
      await assert.rejects(call, /approve|approval/i);
      assert.equal(confirmations, 0, "no automatic approval flooding");
      const command = extension.commands.get("browser-permissions");
      await command.handler("", ctx);
      assert.equal(confirmations, 0, "status is read-only");
      await assert.rejects(() => command.handler("approve", {...ctx, hasUI: false}), /UI|interactive/);
      ctx.ui.confirm = async () => false;
      await command.handler("approve", ctx);
      assert.equal(reloads, 0);
      await assert.rejects(call, /approve|approval/i);
      ctx.ui.confirm = async (_title, preview) => {
        assert.match(preview, /example.com/);
        assert.match(preview, /project/);
        assert.match(preview, /browser|Browser/);
        assert.match(preview, /shell|device/);
        return true;
      };
      await command.handler("approve", ctx);
      assert.equal(reloads, 1);
      // Fake reload does not replace runtime. Old instance must stay blocked.
      await assert.rejects(call, /reload|policy|approval/i);
    ''', env=env)
    run_node(script + r'''
      await fire("session_start");
      await call(); await call();
      assert.equal(confirmations, 0);
      const policy = bw.options.browserOptions.policy;
      assert.equal(policy.check("https://example.com").allowed, true);
      assert.equal(policy.check("https://other.test").allowed, false);
      assert.equal(policy.check("https://169.254.169.254", {resourceType: "transport-address", resolvedFrom: "example.com"}).allowed, false);
      unlinkSync(project + "/.perms/net-allowlist");
      await assert.rejects(call, /policy|approval/i);
      assert.equal(policy.check("https://example.com").allowed, false);
      ctx.ui.confirm = async () => {put("net-allowlist", "changed.test"); return true;};
      await assert.rejects(() => extension.commands.get("browser-permissions").handler("approve", ctx), /changed|drift/i);
      assert.equal(reloads, 0);
    ''', env=env)


def test_adapter_approval_rejects_session_change(tmp_path):
    script, env = adapter_script(tmp_path)
    run_node(script + r'''
      put("downloads", "ask");
      await fire("session_start");
      ctx.ui.confirm = async () => {await fire("session_start"); return true;};
      await assert.rejects(() => extension.commands.get("browser-permissions").handler("approve", ctx), /session changed/i);
      assert.equal(reloads, 0);
      await assert.rejects(call, /approval/i);
    ''', env=env)


def test_adapter_rechecks_queued_work_before_dispatch(tmp_path):
    script, env = adapter_script(tmp_path)
    run_node(script + r'''
      await fire("session_start");
      let release, started;
      bw.hold = new Promise(resolve => {release = resolve;});
      const ready = new Promise(resolve => {started = resolve;});
      bw.onStart = started;
      const first = call("browser");
      await ready;
      const second = call().then(() => null, error => error);
      put("downloads", "deny");
      release();
      await first;
      assert.match(String(await second), /policy|approval/i);
      assert.equal(bw.calls, 1, "queued download must not start under stale permission");
    ''', env=env)


def test_adapter_shutdown_invalidates_waiting_calls(tmp_path):
    script, env = adapter_script(tmp_path)
    run_node(script + r'''
      await fire("session_start");
      let release;
      bw.hold = new Promise(resolve => {release = resolve;});
      const ready = new Promise(resolve => {bw.onStart = resolve;});
      const first = call("browser");
      await ready;
      const second = call().then(() => null, error => error);
      const shutdown = fire("session_shutdown");
      release();
      await first; await shutdown;
      assert.match(String(await second), /session|shutdown|policy/i);
      assert.equal(bw.calls, 1);
      assert.equal(bw.closed, 1);
    ''', env=env)


def test_adapter_rejects_upstream_prompt_contract_change(tmp_path):
    assert EXTENSION.exists(), "tracked browser composition is required"
    agent_dir = tmp_path / "agent"
    fake_package(agent_dir, prompt="Changed upstream permission instructions")
    script = loader_prelude(extension_path=EXTENSION)
    script = script.replace('assert.deepEqual(loaded.errors, []);', '''
      assert.equal(loaded.errors.length, 1);
      assert.match(loaded.errors[0].error, /prompt|guidance|contract/i);
      assert.equal(loaded.extensions.length, 0);
    ''')
    run_node(script, env={"PI_CODING_AGENT_DIR": str(agent_dir)})


def test_adapter_sdk_sections_preserve_later_plugin_prompts(tmp_path):
    script, env = adapter_script(tmp_path)
    run_node(script + r'''      const { ExtensionRunner, SessionManager } = await import("@earendil-works/pi-coding-agent");
      const { buildSystemPrompt } = await import(pathToFileURL(resolve(dirname(piEntry), "core/system-prompt.js")).href);
      const cave = await loader.loadExtensionFromFactory(pi => pi.on("before_agent_start", event => {
        event.systemPromptOptions.sections.caveman = "CAVEMAN_SECTION";
      }), project, undefined, runtime);
      const late = await loader.loadExtensionFromFactory(pi => pi.on("before_agent_start", event => {
        event.systemPromptOptions.sections.late = "LATE_SECTION";
      }), project, undefined, runtime);
      for (const extensions of [[extension, cave, late], [cave, extension, late]]) {
        const runner = new ExtensionRunner(extensions, runtime, project, SessionManager.inMemory(project), {});
        const errors = [];
        runner.onError(error => errors.push(error));
        await runner.emit({type: "session_start", reason: "startup"});
        const result = await runner.emitBeforeAgentStart({messageType: "user", prompt: "fixture"}, {
          cwd: project, sections: {fixture: "ORIGINAL_SECTION"},
        });
        const prompt = buildSystemPrompt(result.systemPromptOptions);
        for (const section of ["ORIGINAL_SECTION", "CAVEMAN_SECTION", "LATE_SECTION"]) assert(prompt.includes(section), section);
        assert.match(prompt, /Browser downloads policy: allow/);
        assert.doesNotMatch(prompt, /Remote files require explicit user approval/);
        assert.equal(result.systemPromptOptions.forceSystemPrompt, undefined);
        assert.deepEqual(errors, []);
        await runner.emit({type: "session_shutdown"});
      }
    ''', env=env)


def test_adapter_sdk_explicit_forced_prompt_stays_authoritative(tmp_path):
    script, env = adapter_script(tmp_path)
    run_node(script + r'''      const { ExtensionRunner, SessionManager } = await import("@earendil-works/pi-coding-agent");
      const runner = new ExtensionRunner([extension], runtime, project, SessionManager.inMemory(project), {});
      await runner.emit({type: "session_start", reason: "startup"});
      const result = await runner.emitBeforeAgentStart({messageType: "user", prompt: "fixture"}, {
        cwd: project, forceSystemPrompt: "EXPLICIT OVERRIDE", sections: {fixture: "NOT_SELECTED"},
      });
      assert(result.systemPromptOptions.forceSystemPrompt.startsWith("EXPLICIT OVERRIDE"));
      assert.match(result.systemPromptOptions.forceSystemPrompt, /Browser downloads policy: allow/);
      assert.doesNotMatch(result.systemPromptOptions.forceSystemPrompt, /NOT_SELECTED/);
      await runner.emit({type: "session_shutdown"});
    ''', env=env)
