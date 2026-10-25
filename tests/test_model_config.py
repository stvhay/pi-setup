from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "pi" / "agent"
SETTINGS = AGENT / "settings.json"
MODELS = AGENT / "models.json"
CATALOG = AGENT / "catalog.json"
APPROVED_OPENROUTER_MODELS = {
    "openrouter/anthropic/claude-opus-5.5",
    "openrouter/minimax/minimax-m3.1-flash",
    "openrouter/moonshotai/kimi-k2.7-code",
    "openrouter/moonshotai/kimi-k3.1-pro",
    "openrouter/z-ai/glm-5.3-flash",
}


def test_active_routes_use_builtin_openrouter_without_local_or_olla_targets():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    enabled = set(settings["enabledModels"])
    task_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((AGENT / "tasks").glob("*.md"))
    )

    assert {target for target in enabled if target.startswith("openrouter/")} == APPROVED_OPENROUTER_MODELS
    assert settings["defaultProvider"] == "openai-codex"
    assert settings["defaultModel"] == "gpt-6-astra"
    assert settings["defaultThinkingLevel"] == "medium"
    assert not any(target.startswith(("olla-local/", "olla-cloud/", "ollama/")) for target in enabled)
    assert "olla-local/" not in task_text
    assert "olla-cloud/" not in task_text
    assert "ollama/" not in task_text


def test_catalog_and_extensions_have_no_dormant_olla_stack():
    catalog_text = CATALOG.read_text(encoding="utf-8")

    assert "olla-cloud/" not in catalog_text
    assert "olla-local/" not in catalog_text
    assert not (AGENT / "extensions" / "olla-provider.ts").exists()


def test_builtin_openrouter_uses_only_bounded_model_overrides():
    models = json.loads(MODELS.read_text(encoding="utf-8"))
    provider = models["providers"]["openrouter"]

    assert set(models["providers"]) == {"openai-codex", "openrouter"}
    assert set(provider) == {"modelOverrides"}
    assert set(provider["modelOverrides"]) == {
        "anthropic/claude-opus-5.5",
        "minimax/minimax-m3.1-flash",
        "moonshotai/kimi-k2.7-code",
        "moonshotai/kimi-k3.1-pro",
        "z-ai/glm-5.3-flash",
    }
    assert all(item["maxTokens"] == 16_384 for item in provider["modelOverrides"].values())
    assert "models" not in provider
    assert "apiKey" not in provider


def test_metered_openrouter_models_require_fresh_budgeted_delegation_context():
    instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Metered OpenRouter runs only in fresh subagents" in instructions
    assert "with estimates, justification, and aggregate budget" in instructions
    assert "repository routes add request/token/cost limits" in instructions
    assert "Route unnamed `subagent` once via `route`" in instructions
    assert "Keep subscription OpenAI/Codex as controller" in instructions


def test_delegation_guidance_uses_evidence_bounded_output_contract_defaults():
    instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")

    assert "`artifact` for deferred full results" in instructions
    assert "`status-only` for deterministic checks" in instructions
    assert "`inline` when content is needed now" in instructions
    assert "`pass-no-findings` only when explicitly requested" in instructions


def test_review_skill_matches_approved_astra_first_diversity_matrix():
    skill = (AGENT / "skills" / "requesting-code-review" / "SKILL.md").read_text(encoding="utf-8")

    assert "**Subscription-backed default:** `openai-codex/gpt-6-astra` at routed medium or high thinking" in skill
    assert "**Subscription-backed challenger:** `openai-codex/gpt-5.6-terra`" in skill
    assert "openrouter/moonshotai/kimi-k2.7-code" in skill
    assert "openrouter/anthropic/claude-opus-5.5" in skill
    assert "Kimi K3.1 Pro is never an automatic review target" in skill
    assert "Only tracked Codex and OpenRouter routes are configured" in skill


def test_lasting_routing_and_output_policy_documents_evidence_and_rollback():
    portfolio = (ROOT / "docs" / "MODEL-PORTFOLIO-2026-08.md").read_text(encoding="utf-8")

    assert "## Lasting routing and output policy" in portfolio
    assert "`pi-04q7.8`" in portfolio
    assert "Low confidence" in portfolio
    assert "policy-only revert" in portfolio
    assert "`artifact`" in portfolio
    assert "`status-only`" in portfolio
    assert "`pass-no-findings`" in portfolio
    assert "pi/agent/skills/requesting-code-review/SKILL.md" in portfolio
    assert "docs/SELF-IMPROVEMENT.md" in portfolio
    assert "pi/agent/bin/README.md" in portfolio
    assert "openrouter/z-ai/glm-5.3-flash" in portfolio
    assert "manual canary" in portfolio


def test_approved_openrouter_models_have_cataloged_runtime_metadata():
    families = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    assert set(families) == {
        "gpt-5.6-sol",
        "gpt-5.6-luna",
        "claude-opus-5",
        "gpt-6-astra",
        "gpt-6.1-sol",
        "gpt-5.6-terra",
        "gpt-6-luna",
        "claude-opus-5.5",
        "minimax-m3",
        "kimi-k3",
        "minimax-m3.1-flash",
        "kimi-k2.7-code",
        "kimi-k3.1-pro",
        "glm-5.3-flash",
    }
    expected = {
        "minimax-m3.1-flash": {
            "target": "openrouter/minimax/minimax-m3.1-flash",
            "contextWindow": 1_048_576,
            "rates": {"input": 0.15, "output": 0.6, "cacheRead": 0.015},
        },
        "kimi-k2.7-code": {
            "target": "openrouter/moonshotai/kimi-k2.7-code",
            "contextWindow": 262_144,
            "rates": {"input": 0.6712, "output": 3.35, "cacheRead": 0.15},
        },
        "kimi-k3.1-pro": {
            "target": "openrouter/moonshotai/kimi-k3.1-pro",
            "contextWindow": 1_048_576,
            "rates": {"input": 2.0, "output": 10.0, "cacheRead": 0.2},
        },
        "claude-opus-5.5": {
            "target": "openrouter/anthropic/claude-opus-5.5",
            "contextWindow": 1_000_000,
            "rates": {"input": 4.0, "output": 20.0, "cacheRead": 0.2, "cacheWrite": 5.0},
        },
        "glm-5.3-flash": {
            "target": "openrouter/z-ai/glm-5.3-flash",
            "contextWindow": 1_048_575,
            "rates": {"input": 0.15, "output": 0.5, "cacheRead": 0.03},
        },
    }

    for family_id, wanted in expected.items():
        family = families[family_id]
        venue = next(item for item in family["venues"] if item["target"] == wanted["target"])
        assert venue["billingClass"] == "metered"
        assert venue["reasoning"] is True
        assert venue["contextWindow"] == wanted["contextWindow"]
        assert family["openrouterRates"] == wanted["rates"]


def test_openrouter_runtime_matches_routing_metadata():
    families = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    overrides = json.loads(MODELS.read_text(encoding="utf-8"))["providers"]["openrouter"]["modelOverrides"]
    for target in APPROVED_OPENROUTER_MODELS:
        model = target.removeprefix("openrouter/")
        family = next(f for f in families.values() if any(v["target"] == target for v in f["venues"]))
        venue = next(v for v in family["venues"] if v["target"] == target)
        runtime = overrides[model]
        for field in ("contextWindow", "thinkingLevelMap", "reasoning", "input"):
            assert runtime[field] == venue[field], (model, field)
        assert runtime["cost"] == {"cacheWrite": 0, **family["openrouterRates"]}
        assert runtime["input"] == ["text", "image"]
    assert overrides["minimax/minimax-m3.1-flash"]["thinkingLevelMap"] == {
        "off": None, "minimal": None, "low": "low", "medium": "medium",
        "high": "high", "xhigh": "xhigh", "max": "max",
    }
    assert overrides["moonshotai/kimi-k3.1-pro"]["thinkingLevelMap"] == {
        "off": "none", "minimal": None, "low": "low", "medium": None,
        "high": "high", "xhigh": None, "max": "max",
    }


def test_active_task_targets_and_workers_have_enabled_cataloged_overrides(common):
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    enabled = set(settings["enabledModels"])
    families = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    venues = {
        venue["target"]: venue
        for family in families.values()
        for venue in family["venues"]
    }
    providers = json.loads(MODELS.read_text(encoding="utf-8"))["providers"]
    route_keys = ("preferred", "qualified", "reviewLow", "reviewMedium", "reviewHigh", "reserveReview", "hardCapReview")
    for path in sorted((AGENT / "tasks").glob("*.md")):
        meta, _ = common.parse_frontmatter_file(path)
        for key in route_keys:
            for target in meta.get(key, []):
                assert target in enabled, (path.name, key, target)
                assert target in venues, (path.name, key, target)
                assert venues[target]["billingClass"] in {"subscription", "metered"}
    for provider, config in providers.items():
        for model in config["modelOverrides"]:
            target = f"{provider}/{model}"
            assert target in enabled
            assert target in venues
    worker = settings["observational-memory"]["model"]
    assert f"{worker['provider']}/{worker['id']}" in enabled & venues.keys()


def test_retired_catalog_facts_remain_separate_and_disabled(common):
    enabled = json.loads(SETTINGS.read_text(encoding="utf-8"))["enabledModels"]
    for target, family in (
        ("openai-codex/gpt-5.6-sol", "gpt-5.6-sol"),
        ("openai-codex/gpt-5.6-luna", "gpt-5.6-luna"),
        ("openrouter/anthropic/claude-opus-5", "claude-opus-5"),
        ("openrouter/minimax/minimax-m3", "minimax-m3"),
        ("openrouter/moonshotai/kimi-k3", "kimi-k3"),
    ):
        assert target not in enabled
        assert common.family_for_target(target) == family
    assert common.opportunity_rates("openai-codex/gpt-5.6-luna") == {
        "input": 0.75, "output": 4.5, "cacheRead": 0.0, "cacheWrite": 0.0,
    }
    assert common.opportunity_rates("openrouter/anthropic/claude-opus-5") == {
        "input": 5.0, "output": 25.0, "cacheRead": 0.5, "cacheWrite": 6.25,
    }


def test_october_codex_metadata_does_not_inherit_old_audio_or_effort():
    families = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    for family in ("gpt-6-astra", "gpt-6.1-sol", "gpt-5.6-terra", "gpt-6-luna"):
        venue = families[family]["venues"][0]
        assert venue["target"] == f"openai-codex/{family}"
        assert venue["input"] == ["text", "image"]
        assert venue["contextWindow"] == (500_000 if family == "gpt-6.1-sol" else 272_000)
        assert venue["reasoning"] is True
        assert venue["billingClass"] == "subscription"
        assert venue["thinkingLevelMap"] == {
            "off": None, "minimal": "low", "low": "low", "medium": "medium",
            "high": "high", "xhigh": "xhigh", "max": "max",
        }
    opus = families["claude-opus-5.5"]["venues"][0]
    assert opus["thinkingLevelMap"] == {
        "off": None, "minimal": None, "low": "low", "medium": "medium",
        "high": "high", "xhigh": "xhigh", "max": "max",
    }


def test_approved_dispatch_roles_use_direct_openrouter_targets():
    task = lambda name: (AGENT / "tasks" / f"{name}.md").read_text(encoding="utf-8")

    assert "openrouter/minimax/minimax-m3.1-flash" in task("cheap-peer")
    assert "openrouter/moonshotai/kimi-k2.7-code" in task("implementation")
    assert "openrouter/moonshotai/kimi-k2.7-code" in task("review")
    assert "openrouter/anthropic/claude-opus-5.5" in task("review")
    assert "openrouter/moonshotai/kimi-k3.1-pro" not in task("implementation")
    assert "openrouter/moonshotai/kimi-k3.1-pro" not in task("cheap-peer")
