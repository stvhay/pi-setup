from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "pi" / "agent"
SETTINGS = AGENT / "settings.json"
MODELS = AGENT / "models.json"
CATALOG = AGENT / "catalog.json"
OLLA_PROVIDER = AGENT / "extensions" / "olla-provider.ts"


def built_models(ids: list[str], surface: str = "cloud") -> dict[str, dict]:
    script = f"""
      import {{ buildModels }} from {json.dumps(OLLA_PROVIDER.as_uri())};
      const {{ models }} = buildModels({json.dumps(ids)}, {json.dumps(surface)});
      console.log(JSON.stringify(models));
    """
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return {model["id"]: model for model in json.loads(result.stdout)}


def test_tracked_models_use_server_backed_olla_providers_only():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    enabled = set(settings["enabledModels"])
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    catalog_targets = {
        venue["target"]
        for family in catalog.values()
        for venue in family.get("venues", [])
    }

    assert not any(target.startswith("openrouter-localish/") for target in enabled | catalog_targets)
    assert not any(target.startswith("ollama/") for target in enabled | catalog_targets)
    models_config = json.loads(MODELS.read_text(encoding="utf-8"))
    assert set(models_config["providers"]) == {"openai-codex"}
    assert "models" not in models_config["providers"]["openai-codex"]

    models = built_models([
        "gemma-4-31b-it", "gemma-4-31b-it:free", "qwen3.5-9b",
        "qwen3-coder-flash", "deepseek-v4-flash", "deepseek-v4-pro",
    ])
    assert models["gemma-4-31b-it"]["contextWindow"] == 262_144
    assert models["gemma-4-31b-it"]["maxTokens"] == 16_384
    assert models["gemma-4-31b-it:free"]["maxTokens"] == 16_384
    assert models["qwen3.5-9b"]["input"] == ["text", "image"]
    assert models["qwen3.5-9b"]["maxTokens"] == 16_384
    assert models["qwen3-coder-flash"]["contextWindow"] == 1_000_000
    assert models["qwen3-coder-flash"]["maxTokens"] == 16_384
    assert models["deepseek-v4-flash"]["contextWindow"] == 1_048_576
    assert models["deepseek-v4-flash"]["maxTokens"] == 16_384
    assert models["deepseek-v4-pro"]["maxTokens"] == 16_384

    deploy = (ROOT / "scripts" / "update-pi-config.sh").read_text(encoding="utf-8")
    assert "agent/extensions/*.local.ts" in deploy


def test_metered_olla_models_require_fresh_delegation_context():
    instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Metered `olla-cloud` models must run in fresh workers" in instructions
    assert "never switch a long-running root conversation to them" in instructions


def test_review_skill_uses_codex_first_and_never_automatic_kimi():
    skill = (AGENT / "skills" / "requesting-code-review" / "SKILL.md").read_text(encoding="utf-8")
    assert "**Subscription-backed default:** `openai-codex/gpt-5.6-sol`" in skill
    assert "Kimi K2.7 and Kimi K3 are never automatic review targets" in skill
    assert "never switch a long-running root conversation to it" in skill


def test_kimi_models_are_enabled_through_olla_only():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    enabled = set(settings["enabledModels"])

    assert "olla-cloud/kimi-k2.7-code" in enabled
    assert "olla-cloud/kimi-k3" in enabled
    assert "openrouter/moonshotai/kimi-k2.7-code" not in enabled
    assert "openrouter/moonshotai/kimi-k3" not in enabled


def test_kimi_olla_metadata_matches_verified_capabilities():
    script = f"""
      import {{ buildModels }} from {json.dumps(OLLA_PROVIDER.as_uri())};
      const {{ models }} = buildModels(["kimi-k2.7-code", "kimi-k3"], "cloud");
      console.log(JSON.stringify(models));
    """
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    models = {model["id"]: model for model in json.loads(result.stdout)}

    k27 = models["kimi-k2.7-code"]
    assert k27["reasoning"] is True
    assert k27["thinkingLevelMap"]["off"] is None
    assert k27["input"] == ["text", "image"]
    assert k27["contextWindow"] == 262_144
    assert k27["maxTokens"] == 16_384
    assert k27["compat"]["supportsReasoningEffort"] is False

    k3 = models["kimi-k3"]
    assert k3["reasoning"] is True
    assert k3["thinkingLevelMap"] == {
        "off": None,
        "minimal": None,
        "low": None,
        "medium": None,
        "high": None,
        "xhigh": None,
        "max": "max",
    }
    assert k3["input"] == ["text", "image"]
    assert k3["contextWindow"] == 1_048_576
    assert k3["maxTokens"] == 16_384
    assert k3["compat"]["supportsReasoningEffort"] is False


def test_deepseek_reasoning_uses_openrouter_payload_format():
    models = built_models([
        "deepseek-r1", "deepseek-v4-flash", "deepseek-v4-pro"
    ])
    for model in models.values():
        assert model["reasoning"] is True
        assert model["compat"]["supportsReasoningEffort"] is True
        assert model["compat"]["thinkingFormat"] == "openrouter"


def test_deepseek_v4_flash_is_enabled_as_a_cheap_review_challenger():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    target = "olla-cloud/deepseek-v4-flash"
    assert target in settings["enabledModels"]

    model = built_models(["deepseek-v4-flash"])["deepseek-v4-flash"]
    assert model["contextWindow"] == 1_048_576
    assert model["reasoning"] is True
    assert model["cost"] == {
        "input": 0.0938,
        "output": 0.1876,
        "cacheRead": 0.01876,
        "cacheWrite": 0,
    }

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    assert catalog["deepseek-v4-flash"]["venues"] == [
        {
            "target": target,
            "costClass": "cheap",
            "reasoning": True,
            "input": ["text"],
            "contextWindow": 1_048_576,
            "billingClass": "metered",
            "maxTokens": 16_384,
        }
    ]
    review = (AGENT / "tasks" / "review.md").read_text(encoding="utf-8")
    assert f"  - {target}" in review


def test_openrouter_challengers_replace_unrouted_legacy_models():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    enabled = set(settings["enabledModels"])
    configured = {
        f"olla-cloud/{model_id}": model
        for model_id, model in built_models([
            "qwen3-coder-flash", "deepseek-v4-pro"
        ]).items()
    }
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]

    removed = {
        "openrouter-localish/meta-llama/llama-3.1-8b-instruct",
        "openrouter-localish/meta-llama/llama-3.3-70b-instruct",
        "openrouter-localish/deepseek/deepseek-r1-distill-qwen-32b",
    }
    assert removed.isdisjoint(enabled)
    assert removed.isdisjoint(configured)

    expected = {
        "olla-cloud/qwen3-coder-flash": {
            "contextWindow": 1_000_000,
            "maxTokens": 16_384,
            "cost": {
                "input": 0.195,
                "output": 0.975,
                "cacheRead": 0.039,
                "cacheWrite": 0.24375,
            },
        },
        "olla-cloud/deepseek-v4-pro": {
            "reasoning": True,
            "contextWindow": 1_048_576,
            "maxTokens": 16_384,
            "cost": {
                "input": 0.435,
                "output": 0.87,
                "cacheRead": 0.003625,
                "cacheWrite": 0,
            },
        },
    }
    for target, metadata in expected.items():
        assert target in enabled
        for key, value in metadata.items():
            assert configured[target][key] == value

    assert catalog["qwen3-coder-flash"]["venues"][0]["target"] in enabled
    assert catalog["deepseek-v4-pro"]["venues"][0]["target"] in enabled
    assert "llama-3.1-8b" not in catalog
    assert "llama-3.3-70b" not in catalog

    implementation = (AGENT / "tasks" / "implementation.md").read_text(
        encoding="utf-8"
    )
    review = (AGENT / "tasks" / "review.md").read_text(encoding="utf-8")
    assert "  - olla-cloud/qwen3-coder-flash" in implementation
    assert "  - olla-cloud/qwen3-coder-flash" in review
    assert "  - olla-cloud/deepseek-v4-pro" in review


def test_kimi_families_and_dispatch_roles_are_cataloged():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    assert catalog["kimi-k2.7-code"]["venues"] == [
        {
            "target": "olla-cloud/kimi-k2.7-code",
            "costClass": "balanced",
            "billingClass": "metered",
            "reasoning": True,
            "thinkingLevelMap": {"off": None},
            "input": ["text", "image"],
            "contextWindow": 262_144,
            "maxTokens": 16_384,
        }
    ]
    assert catalog["kimi-k3"]["venues"] == [
        {
            "target": "olla-cloud/kimi-k3",
            "costClass": "frontier",
            "billingClass": "metered",
            "reasoning": True,
            "thinkingLevelMap": {
                "off": None,
                "minimal": None,
                "low": None,
                "medium": None,
                "high": None,
                "xhigh": None,
                "max": "max",
            },
            "input": ["text", "image"],
            "contextWindow": 1_048_576,
            "maxTokens": 16_384,
        }
    ]

    expected_roles = {
        "kimi-k2.7-code": {"implementation", "planning"},
        "kimi-k3": {"frontier-advisor"},
    }
    for model, roles in expected_roles.items():
        target = f"olla-cloud/{model}"
        for role in roles:
            task = (AGENT / "tasks" / f"{role}.md").read_text(encoding="utf-8")
            assert f"  - {target}" in task, f"{target} missing from {role} dispatch"

    orchestration = (AGENT / "tasks" / "orchestration.md").read_text(encoding="utf-8")
    assert "olla-cloud/kimi-" not in orchestration
    routine_tasks = ["cheap-peer", "implementation", "planning", "research", "review"]
    for role in routine_tasks:
        task = (AGENT / "tasks" / f"{role}.md").read_text(encoding="utf-8")
        assert "  - olla-cloud/kimi-k3" not in task
    review = (AGENT / "tasks" / "review.md").read_text(encoding="utf-8")
    assert "  - olla-cloud/kimi-k2.7-code" not in review
    assert "escalationTarget: olla-cloud/kimi-k3" in review
