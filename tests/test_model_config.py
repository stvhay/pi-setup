from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "pi" / "agent"
SETTINGS = AGENT / "settings.json"
MODELS = AGENT / "models.json"
CATALOG = AGENT / "catalog.json"
APPROVED_OPENROUTER_MODELS = {
    "openrouter/anthropic/claude-opus-5",
    "openrouter/minimax/minimax-m3",
    "openrouter/moonshotai/kimi-k2.7-code",
    "openrouter/moonshotai/kimi-k3",
}


def test_active_routes_use_builtin_openrouter_without_local_or_olla_targets():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    enabled = set(settings["enabledModels"])
    task_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((AGENT / "tasks").glob("*.md"))
    )

    assert {target for target in enabled if target.startswith("openrouter/")} == APPROVED_OPENROUTER_MODELS
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
        "anthropic/claude-opus-5",
        "minimax/minimax-m3",
        "moonshotai/kimi-k2.7-code",
        "moonshotai/kimi-k3",
    }
    assert all(item == {"maxTokens": 16_384} for item in provider["modelOverrides"].values())
    assert "models" not in provider
    assert "apiKey" not in provider


def test_metered_openrouter_models_require_fresh_delegation_context():
    instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")

    assert "metered OpenRouter only for bounded diversity, specialist review, or explicit canary work" in instructions
    assert "always in fresh subagents" in instructions
    assert "metered repository inspection requires route-generated justification, estimates, aggregate budget, and per-child limits" in instructions
    assert "Keep subscription OpenAI/Codex as root/default controller" in instructions


def test_review_skill_matches_approved_diversity_matrix():
    skill = (AGENT / "skills" / "requesting-code-review" / "SKILL.md").read_text(encoding="utf-8")

    assert "**Subscription-backed default:** `openai-codex/gpt-5.6-terra` at high thinking" in skill
    assert "openrouter/moonshotai/kimi-k2.7-code" in skill
    assert "openrouter/anthropic/claude-opus-5" in skill
    assert "Kimi K3 is never an automatic review target" in skill
    assert "Only tracked Codex and OpenRouter routes are configured" in skill


def test_approved_openrouter_models_have_cataloged_runtime_metadata():
    families = json.loads(CATALOG.read_text(encoding="utf-8"))["families"]
    assert set(families) == {
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "claude-opus-5",
        "minimax-m3",
        "kimi-k2.7-code",
        "kimi-k3",
    }
    expected = {
        "minimax-m3": {
            "target": "openrouter/minimax/minimax-m3",
            "contextWindow": 524_288,
            "rates": {"input": 0.3, "output": 1.2, "cacheRead": 0.06},
        },
        "kimi-k2.7-code": {
            "target": "openrouter/moonshotai/kimi-k2.7-code",
            "contextWindow": 262_144,
            "rates": {"input": 0.73, "output": 3.5, "cacheRead": 0.15},
        },
        "kimi-k3": {
            "target": "openrouter/moonshotai/kimi-k3",
            "contextWindow": 1_048_576,
            "rates": {"input": 3.0, "output": 15.0, "cacheRead": 0.3},
        },
        "claude-opus-5": {
            "target": "openrouter/anthropic/claude-opus-5",
            "contextWindow": 1_000_000,
            "rates": {"input": 5.0, "output": 25.0, "cacheRead": 0.5, "cacheWrite": 6.25},
        },
    }

    for family_id, wanted in expected.items():
        family = families[family_id]
        venue = next(item for item in family["venues"] if item["target"] == wanted["target"])
        assert venue["billingClass"] == "metered"
        assert venue["reasoning"] is True
        assert venue["contextWindow"] == wanted["contextWindow"]
        assert family["openrouterRates"] == wanted["rates"]


def test_approved_dispatch_roles_use_direct_openrouter_targets():
    task = lambda name: (AGENT / "tasks" / f"{name}.md").read_text(encoding="utf-8")

    assert "openrouter/minimax/minimax-m3" in task("cheap-peer")
    assert "openrouter/moonshotai/kimi-k2.7-code" in task("implementation")
    assert "openrouter/moonshotai/kimi-k2.7-code" in task("review")
    assert "openrouter/anthropic/claude-opus-5" in task("review")
    assert "openrouter/moonshotai/kimi-k3" not in task("implementation")
    assert "openrouter/moonshotai/kimi-k3" not in task("cheap-peer")
