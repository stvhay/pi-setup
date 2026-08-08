from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
MODELS = ROOT / "pi" / "agent" / "models.json"
CATALOG = ROOT / "pi" / "agent" / "catalog.json"
PI_README = ROOT / "pi" / "README.md"
KEYBINDINGS = ROOT / "pi" / "agent" / "keybindings.json"
ARCHIMEDES_PACKAGE = {"source": "npm:pi-archimedes@1.8.3", "extensions": []}
ARCHIMEDES_WRAPPER = ROOT / "pi" / "agent" / "extensions" / "archimedes.ts"
LANGFUSE_PACKAGE = {"source": "npm:pi-langfuse@1.5.10", "extensions": []}
LANGFUSE_WRAPPER = ROOT / "pi" / "agent" / "extensions" / "langfuse-config-env.ts"
ARCHITECTURE_SKILL_PACKAGE = {
    "source": "git:github.com/mattpocock/skills@2ab958093e83e0ec752e6c1c5932da465bf23e0c",
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


def run_node(script: str):
    subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ,
    )


def test_architecture_skill_package_is_pinned_and_filtered_to_dependencies():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert ARCHITECTURE_SKILL_PACKAGE in settings["packages"]


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
    run_node(script)


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
    assert ARCHIMEDES_WRAPPER.is_file()
    wrapper = ARCHIMEDES_WRAPPER.read_text(encoding="utf-8")
    assert 'require.resolve("pi-archimedes")' in wrapper
    assert '.resolve("@pi-archimedes/core/bus")' in wrapper
    assert 'tool.name === "subagent"' in wrapper
    assert '"pass-no-findings"' in wrapper
    assert "/src/" not in wrapper


def test_langfuse_package_entrypoint_is_disabled_for_tracked_public_wrapper():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert LANGFUSE_PACKAGE in settings["packages"]
    assert "npm:pi-langfuse@1.5.7" not in settings["packages"]
    assert "npm:pi-langfuse@1.5.9" not in settings["packages"]
    wrapper = LANGFUSE_WRAPPER.read_text(encoding="utf-8")
    assert 'require.resolve("pi-langfuse")' in wrapper
    assert "/src/" not in wrapper


def test_native_clipboard_package_is_pinned_for_archimedes_image_paste():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert ARCHIMEDES_PACKAGE in settings["packages"]
    assert "npm:@mariozechner/clipboard@0.3.9" in settings["packages"]


def test_builtin_image_paste_keybinding_is_disabled_for_archimedes():
    keybindings = json.loads(KEYBINDINGS.read_text(encoding="utf-8"))

    assert keybindings["app.clipboard.pasteImage"] == []


def test_gpt56_codex_subscription_context_matches_routing_catalog():
    assert MODELS.is_file(), "tracked models.json must enforce the Codex subscription context"
    models = json.loads(MODELS.read_text(encoding="utf-8"))
    provider = models["providers"]["openai-codex"]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]

    assert set(provider) == {"modelOverrides"}
    for family in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        assert provider["modelOverrides"][family] == {"contextWindow": 272_000}
        assert catalog[family]["venues"][0]["contextWindow"] == 272_000


def test_observational_memory_compaction_precedes_native_threshold():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = settings["observational-memory"]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    sol_context = catalog["gpt-5.6-sol"]["venues"][0]["contextWindow"]

    assert "npm:pi-observational-memory@3.0.3" in settings["packages"]
    assert config["compactAfterTokens"] == 81_000
    assert config["compactAfterTokensMode"] == "ratio"
    assert config["compactAfterTokensRatio"] == 0.75

    effective_threshold = int(sol_context * config["compactAfterTokensRatio"])
    native_threshold = sol_context - 16_384
    assert effective_threshold == 204_000
    assert native_threshold == 255_616
    assert native_threshold - effective_threshold == 51_616

    def threshold_for(context):
        if isinstance(context, (int, float)) and context > 0:
            return int(context * config["compactAfterTokensRatio"])
        return config["compactAfterTokens"]

    assert all(threshold_for(context) == 81_000 for context in (None, 0, -1))

    docs = PI_README.read_text(encoding="utf-8")
    assert "27a5195eaf90e4e2ca1302e3a31d4bb14df982a5" in docs
    assert "272,000 × 0.75 = 204,000" in docs
    assert "51,616" in docs
    assert "different token counters" in docs
    assert "81,000" in docs


def test_observational_memory_workers_use_low_thinking_sol():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = settings["observational-memory"]

    assert config["model"] == {
        "provider": "openai-codex",
        "id": "gpt-5.6-sol",
        "thinking": "low",
    }
    assert config["model"]["thinking"] not in {"medium", "high", "xhigh"}

    docs = PI_README.read_text(encoding="utf-8")
    assert "observer, reflector, and dropper" in docs
    assert "Compaction itself does not call a model" in docs
