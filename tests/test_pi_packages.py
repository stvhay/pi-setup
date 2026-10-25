from __future__ import annotations

import json
from pathlib import Path

from conftest import run_node


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
MODELS = ROOT / "pi" / "agent" / "models.json"
CATALOG = ROOT / "pi" / "agent" / "catalog.json"
PI_README = ROOT / "pi" / "README.md"
KEYBINDINGS = ROOT / "pi" / "agent" / "keybindings.json"
ARCHIMEDES_PACKAGE = {"source": "npm:pi-archimedes@2.11.1", "extensions": []}
ARCHIMEDES_WRAPPER = ROOT / "pi" / "agent" / "extensions" / "archimedes.ts"
LANGFUSE_WRAPPER = ROOT / "pi" / "agent" / "extensions" / "langfuse-config-env.ts"
ARCHITECTURE_SKILL_PACKAGE = {
    "source": "git:github.com/mattpocock/skills",
    "extensions": [],
    "skills": [
        "skills/engineering/codebase-design",
        "skills/engineering/domain-modeling",
        "skills/engineering/improve-codebase-architecture",
        "skills/productivity/grilling",
    ],
    "prompts": [],
    "themes": [],
}
PONYTAIL_PACKAGE = {
    "source": "git:github.com/DietrichGebert/ponytail",
    "skills": [],
}
PONYTAIL_INPUT = ROOT / "pi" / "agent" / "extensions" / "ponytail-skill-input.ts"


def test_architecture_skill_package_is_unpinned_and_filtered_to_dependencies():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert ARCHITECTURE_SKILL_PACKAGE in settings["packages"]
    assert not any(
        isinstance(package, dict)
        and str(package.get("source", "")).startswith("git:github.com/mattpocock/skills@")
        for package in settings["packages"]
    )


def test_ponytail_discovery_filters_package_skills_without_disabling_extension():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert PONYTAIL_PACKAGE in settings["packages"]
    assert "git:github.com/DietrichGebert/ponytail" not in settings["packages"]
    assert "extensions" not in PONYTAIL_PACKAGE


def test_ponytail_discovery_package_filter_disables_skills_only(tmp_path):
    agent_dir = tmp_path / "agent"
    project = tmp_path / "project"
    package_root = tmp_path / "ponytail-package"
    (package_root / "skills" / "ponytail").mkdir(parents=True)
    agent_dir.mkdir()
    project.mkdir()
    (package_root / "package.json").write_text(
        json.dumps({"pi": {"extensions": ["./extension.js"], "skills": ["./skills"]}}),
        encoding="utf-8",
    )
    (package_root / "extension.js").write_text("export default () => {};\n", encoding="utf-8")
    (package_root / "skills" / "ponytail" / "SKILL.md").write_text(
        "---\nname: ponytail\ndescription: fixture\n---\nbody\n",
        encoding="utf-8",
    )
    (agent_dir / "settings.json").write_text(
        json.dumps({"packages": [{"source": str(package_root), "skills": []}]}),
        encoding="utf-8",
    )

    script = f"""
      import assert from "node:assert/strict";
      import {{ DefaultPackageManager, SettingsManager }} from "@earendil-works/pi-coding-agent";

      const cwd = {str(project)!r};
      const agentDir = {str(agent_dir)!r};
      const settings = SettingsManager.create(cwd, agentDir, {{ projectTrusted: true }});
      const resources = await new DefaultPackageManager({{ cwd, agentDir, settingsManager: settings }}).resolve();
      assert.equal(resources.extensions.filter((resource) => resource.enabled).length, 1);
      assert.match(resources.extensions.find((resource) => resource.enabled).path, /extension\\.js$/);
      assert.equal(resources.skills.length, 1);
      assert.equal(resources.skills[0].enabled, false);
    """
    # SDK discovers ~/.agents independently of explicit agentDir. Keep this
    # package-filter test independent of installed user skills.
    run_node(script, env={"HOME": str(tmp_path)})


def test_ponytail_discovery_preserves_explicit_skills_and_args(tmp_path):
    assert PONYTAIL_INPUT.is_file(), "tracked Ponytail skill input extension is required"
    package_root = tmp_path / "ponytail"
    skill_names = [
        "ponytail",
        "ponytail-review",
        "ponytail-audit",
        "ponytail-debt",
        "ponytail-gain",
        "ponytail-help",
    ]
    for name in skill_names:
        skill_dir = package_root / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: fixture\n---\n\n# {name}\n\nBody {name}\n",
            encoding="utf-8",
        )

    script = f"""
      import assert from "node:assert/strict";
      import {{ readFile, writeFile }} from "node:fs/promises";
      import {{ join }} from "node:path";
      import ponytailSkillInput from {PONYTAIL_INPUT.as_uri()!r};

      const packageRoot = {str(package_root)!r};
      const packageSource = "git:github.com/DietrichGebert/ponytail";
      const handlers = {{}};
      ponytailSkillInput({{
        on(name, handler) {{ handlers[name] = handler; }},
        getCommands() {{
          return [
            {{ source: "extension", sourceInfo: {{ source: "git:github.com/other/ponytail", origin: "package", baseDir: "/wrong" }} }},
            {{ source: "extension", sourceInfo: {{ source: packageSource, origin: "package", baseDir: packageRoot }} }},
          ];
        }},
      }});

      assert.deepEqual(Object.keys(handlers), ["input"]);
      for (const [index, name] of {json.dumps(skill_names)}.entries()) {{
        const args = "keep  internal   spacing";
        const result = await handlers.input({{
          text: `/skill:${{name}}   ${{args}}  `,
          source: index === 1 ? "extension" : "interactive",
        }});
        const skillPath = join(packageRoot, "skills", name, "SKILL.md");
        assert.equal(result.action, "transform");
        assert.equal(
          result.text,
          `<skill name="${{name}}" location="${{skillPath}}">\nReferences are relative to ${{join(packageRoot, "skills", name)}}.\n\n# ${{name}}\n\nBody ${{name}}\n</skill>\n\n${{args}}`,
        );
      }}

      const reviewPath = join(packageRoot, "skills", "ponytail-review", "SKILL.md");
      await writeFile(reviewPath, `---
name: ponytail-review
description: fixture
---

Replacement body
`);
      const reloaded = await handlers.input({{ text: "/skill:ponytail-review", source: "extension" }});
      assert.match(reloaded.text, /Replacement body/);
      assert.doesNotMatch(reloaded.text, /Body ponytail-review/);
      assert.equal((await readFile(reviewPath, "utf8")).includes("Replacement body"), true);
      assert.deepEqual(await handlers.input({{ text: "/skill:other", source: "interactive" }}), {{ action: "continue" }});
    """
    run_node(script)


def test_archimedes_package_entrypoint_is_disabled_for_tracked_public_wrapper():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert ARCHIMEDES_PACKAGE in settings["packages"]
    assert "npm:pi-archimedes" not in settings["packages"]
    assert "npm:pi-archimedes@1.8.3" not in settings["packages"]
    assert "npm:pi-archimedes@2.11.1" not in settings["packages"]
    assert ARCHIMEDES_WRAPPER.is_file()
    wrapper = ARCHIMEDES_WRAPPER.read_text(encoding="utf-8")
    assert 'require.resolve("pi-archimedes")' in wrapper
    assert '.resolve("@pi-archimedes/core/events")' in wrapper
    assert '.resolve("@pi-archimedes/subagent/agents")' in wrapper
    assert '.resolve("@pi-archimedes/subagent/types")' in wrapper
    assert "dirname(subagentEntry)" not in wrapper
    assert "discoverAgents" not in wrapper
    assert "findAgent" not in wrapper
    assert 'tool.name === "subagent"' in wrapper
    assert "SUBAGENT_OUTPUT_CONTRACTS" in wrapper
    assert "PI_ARCHIMEDES_METERED_ONE_SHOT_MAX_OUTPUT_TOKENS" in wrapper
    assert "16_384" in wrapper
    assert "billingClass" in wrapper
    assert "/src/" not in wrapper


def test_langfuse_package_entrypoint_is_disabled_for_tracked_public_wrapper():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    proof = json.loads((ROOT / "patches/pi-packages/langfuse-runtime/release.json").read_text())
    assert {"source": "../runtime/pi-langfuse/releases/" + proof["id"], "extensions": []} in settings["packages"]
    assert "npm:pi-langfuse" not in SETTINGS.read_text()
    wrapper = LANGFUSE_WRAPPER.read_text(encoding="utf-8")
    assert "resolveLangfuseRuntime(agentDir)" in wrapper
    assert "runtime.entry" in wrapper and "runtime.quality" in wrapper
    assert "require.resolve" not in wrapper
    assert "result.gaps" in wrapper
    assert '"src"' not in wrapper
    for private_module in ("langfuse.js", "redaction.js", "utils.js"):
        assert private_module not in wrapper


def test_native_clipboard_package_is_pinned_for_archimedes_image_paste():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert ARCHIMEDES_PACKAGE in settings["packages"]
    assert "npm:@mariozechner/clipboard@0.3.9" in settings["packages"]


def test_builtin_image_paste_keybinding_is_disabled_for_archimedes():
    keybindings = json.loads(KEYBINDINGS.read_text(encoding="utf-8"))

    assert keybindings["app.clipboard.pasteImage"] == []


def test_codex_subscription_context_matches_routing_catalog():
    assert MODELS.is_file(), "tracked models.json must enforce the Codex subscription context"
    models = json.loads(MODELS.read_text(encoding="utf-8"))
    provider = models["providers"]["openai-codex"]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]

    assert set(provider) == {"modelOverrides"}
    for family in ("gpt-6.1-sol", "gpt-5.6-terra", "gpt-6-luna"):
        context = 500_000 if family == "gpt-6.1-sol" else 272_000
        expected = {"contextWindow": context}
        if family != "gpt-6.1-sol":
            expected["thinkingLevelMap"] = {"off": None}
        assert provider["modelOverrides"][family] == expected
        assert catalog[family]["venues"][0]["contextWindow"] == context


def test_codex_subscription_defaults_resolve_in_pi_without_network(tmp_path):
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFileSync }} from "node:fs";
      import {{ ModelRuntime }} from "@earendil-works/pi-coding-agent";
      import {{ getSupportedThinkingLevels }} from "@earendil-works/pi-ai";

      const runtime = await ModelRuntime.create({{
        authPath: {str(tmp_path / 'auth.json')!r},
        modelsPath: {str(MODELS)!r},
        modelsStorePath: {str(tmp_path / 'models-store.json')!r},
        allowModelNetwork: false,
        refreshOnCreate: false,
      }});
      assert.equal(runtime.getError(), undefined);
      const settings = JSON.parse(readFileSync({str(SETTINGS)!r}, "utf8"));
      const expected = {{
        "gpt-6-astra": 272000, "gpt-6.1-sol": 500000,
        "gpt-5.6-terra": 272000, "gpt-6-luna": 272000,
      }};
      assert.deepEqual(
        settings.enabledModels.filter(id => id.startsWith("openai-codex/")).sort(),
        Object.keys(expected).map(id => `openai-codex/${{id}}`).sort(),
      );
      for (const [id, context] of Object.entries(expected)) {{
        const model = runtime.getModel("openai-codex", id);
        assert.ok(model, id);
        assert.equal(model.api, "openai-codex-responses");
        assert.equal(model.contextWindow, context, id);
        assert.deepEqual(model.input, ["text", "image"], id);
        assert.deepEqual(getSupportedThinkingLevels(model),
          ["minimal", "low", "medium", "high", "xhigh", "max"], id);
        assert.equal(model.thinkingLevelMap.minimal, "low", id);
        assert.equal(model.maxTokens, 128000, id);
      }}
    """
    run_node(script, env={"HOME": str(tmp_path)})


def test_openrouter_overrides_resolve_in_pi_without_network(tmp_path):
    script = f"""
      import assert from "node:assert/strict";
      import {{ readFileSync }} from "node:fs";
      import {{ ModelRuntime }} from "@earendil-works/pi-coding-agent";
      import {{ getSupportedThinkingLevels, InMemoryModelsStore }} from "@earendil-works/pi-ai";

      // Simulate remotely discovered IDs absent from Pi 1.4.0's bundled catalog.
      const modelsStore = new InMemoryModelsStore();
      await modelsStore.write("openrouter", {{ models:
        ["minimax/minimax-m3.1-flash", "moonshotai/kimi-k3.1-pro",
         "moonshotai/kimi-k2.7-code", "anthropic/claude-opus-5.5", "z-ai/glm-5.3-flash"].map(id => ({{
          id, name: id, provider: "openrouter", api: "openai-completions",
          baseUrl: "https://openrouter.ai/api/v1", reasoning: true, input: ["text"],
          cost: {{ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }},
          contextWindow: 128000, maxTokens: 128000,
        }})),
      }});
      const runtime = await ModelRuntime.create({{
        authPath: {str(tmp_path / 'auth.json')!r},
        modelsPath: {str(MODELS)!r},
        modelsStore,
        allowModelNetwork: false,
      }});
      assert.equal(runtime.getError(), undefined);
      const overrides = JSON.parse(readFileSync({str(MODELS)!r}, "utf8"))
        .providers.openrouter.modelOverrides;
      for (const [id, expected] of Object.entries(overrides)) {{
        const model = runtime.getModel("openrouter", id);
        assert.ok(model, id);
        for (const field of ["contextWindow", "input", "reasoning", "maxTokens"])
          assert.deepEqual(model[field], expected[field], `${{id}} ${{field}}`);
        assert.deepEqual(model.cost, {{ ...expected.cost, tiers: undefined }}, id);
        for (const [level, value] of Object.entries(expected.thinkingLevelMap))
          assert.equal(model.thinkingLevelMap[level], value, `${{id}} ${{level}}`);
      }}
      assert.deepEqual(getSupportedThinkingLevels(runtime.getModel("openrouter", "minimax/minimax-m3.1-flash")),
        ["low", "medium", "high", "xhigh", "max"]);
      assert.deepEqual(getSupportedThinkingLevels(runtime.getModel("openrouter", "moonshotai/kimi-k3.1-pro")),
        ["off", "low", "high", "max"]);
    """
    run_node(script, env={"HOME": str(tmp_path)})


def test_betterwright_remains_unpinned_with_tracked_permission_adapter():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert {"source": "npm:betterwright", "extensions": []} in settings["packages"]
    assert "npm:betterwright" not in settings["packages"], "avoid duplicate tool registration"
    assert (SETTINGS.parent / "extensions/browser-permissions.ts").is_file()


def test_observational_memory_compaction_precedes_native_threshold():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = settings["observational-memory"]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    sol_context = catalog["gpt-6.1-sol"]["venues"][0]["contextWindow"]

    assert "npm:pi-observational-memory@3.1.4" in settings["packages"]
    assert config["compactAfterTokens"] == 81_000
    assert config["compactAfterTokensMode"] == "ratio"
    assert config["compactAfterTokensRatio"] == 0.75

    effective_threshold = int(sol_context * config["compactAfterTokensRatio"])
    native_threshold = sol_context - 16_384
    assert effective_threshold == 375_000
    assert native_threshold == 483_616
    assert native_threshold - effective_threshold == 108_616

    def threshold_for(context):
        if isinstance(context, (int, float)) and context > 0:
            return int(context * config["compactAfterTokensRatio"])
        return config["compactAfterTokens"]

    assert all(threshold_for(context) == 81_000 for context in (None, 0, -1))

    docs = PI_README.read_text(encoding="utf-8")
    assert "pi-observational-memory/releases/tag/3.1.4" in docs
    assert "500,000 × 0.75 = 375,000" in docs
    assert "108,616" in docs
    assert "different token counters" in docs
    assert "81,000" in docs


def test_settings_omit_runtime_defaults():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = settings["observational-memory"]

    assert "theme" not in settings
    assert "passive" not in config
    assert "debugLog" not in config


def test_observational_memory_workers_use_low_thinking_sol():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = settings["observational-memory"]

    assert config["model"] == {
        "provider": "openai-codex",
        "id": "gpt-6.1-sol",
        "thinking": "low",
    }
    assert config["model"]["thinking"] not in {"medium", "high", "xhigh"}

    docs = PI_README.read_text(encoding="utf-8")
    assert "observer, reflector, and dropper" in docs
    assert "Compaction itself does not call a model" in docs


def test_new_archimedes_capabilities_remain_operator_opt_in():
    settings = json.loads((ROOT / "pi" / "agent" / "settings.json").read_text())
    assert settings["archimedes.sudo"]["enabled"] is False
    assert settings["archimedes.web"]["enabled"] is False
    assert "archimedes.meta" not in settings, "runtime onboarding state must not be tracked"
