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


def test_kimi_models_are_enabled_through_olla_only():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    enabled = set(settings["enabledModels"])

    assert "olla-cloud/kimi-k2.7-code" in enabled
    assert "olla-cloud/kimi-k3" in enabled
    assert "openrouter/moonshotai/kimi-k2.7-code" not in enabled
    assert "openrouter/moonshotai/kimi-k3" not in enabled

    models = json.loads(MODELS.read_text(encoding="utf-8"))
    configured_ids = {
        f"{provider}/{model['id']}"
        for provider, config in models["providers"].items()
        for model in config.get("models", [])
    }
    assert "openrouter-localish/moonshotai/kimi-k2.7-code" not in configured_ids
    assert "openrouter-localish/moonshotai/kimi-k3" not in configured_ids


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
    assert k27["maxTokens"] == 32_768
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
    assert k3["maxTokens"] == 131_072
    assert k3["compat"]["supportsReasoningEffort"] is False


def test_deepseek_v4_flash_is_enabled_as_a_cheap_review_challenger():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    target = "openrouter-localish/deepseek/deepseek-v4-flash"
    assert target in settings["enabledModels"]

    models = json.loads(MODELS.read_text(encoding="utf-8"))
    configured = {
        f"{provider}/{model['id']}": model
        for provider, config in models["providers"].items()
        for model in config.get("models", [])
    }
    model = configured[target]
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
        }
    ]
    review = (AGENT / "tasks" / "review.md").read_text(encoding="utf-8")
    assert f"  - {target}" in review


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
            "maxTokens": 32_768,
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
            "maxTokens": 131_072,
        }
    ]

    expected_roles = {
        "kimi-k2.7-code": {"implementation", "planning", "review"},
        "kimi-k3": {"frontier-advisor", "implementation", "planning", "research"},
    }
    for model, roles in expected_roles.items():
        target = f"olla-cloud/{model}"
        for role in roles:
            task = (AGENT / "tasks" / f"{role}.md").read_text(encoding="utf-8")
            assert f"  - {target}" in task, f"{target} missing from {role} dispatch"

    orchestration = (AGENT / "tasks" / "orchestration.md").read_text(encoding="utf-8")
    assert "olla-cloud/kimi-" not in orchestration
    review = (AGENT / "tasks" / "review.md").read_text(encoding="utf-8")
    assert "  - olla-cloud/kimi-k3" not in review
    assert "escalationTarget: olla-cloud/kimi-k3" in review
