"""Catalog lookups: family/venue equivalence is data, not code."""


def test_family_resolution_across_venues(common):
    assert common.family_for_target("ollama/gemma4:31b") == "gemma4-31b"
    assert common.family_for_target("olla-local/gemma4:31b") == "gemma4-31b"
    assert (
        common.family_for_target("openrouter-localish/google/gemma-4-31b-it")
        == "gemma4-31b"
    )
    assert common.family_for_target("openai-codex/gpt-5.5") == "gpt-5.5"
    assert common.family_for_target("olla-cloud/glm-5.2") == "glm-5.2"
    assert common.family_for_target("unknown/model") is None


def test_local_proxy_derived_from_family(common):
    proxy = common.proxy_for_target("ollama/gemma4:31b")
    assert proxy == {
        "target": "openrouter-localish/google/gemma-4-31b-it",
        "quality": "exact-family",
    }

    proxy = common.proxy_for_target("olla-local/qwen3:8b")
    assert proxy == {
        "target": "openrouter-localish/qwen/qwen3.5-9b",
        "quality": "approximate-family",
    }

    proxy = common.proxy_for_target("olla-local/deepseek-r1:14b")
    assert (
        proxy["target"] == "openrouter-localish/deepseek/deepseek-r1-distill-qwen-32b"
    )
    assert proxy["quality"] == "approximate-family"


def test_subscription_opportunity_rates(common):
    rates = common.opportunity_rates("olla-cloud/gpt-4.1-mini")
    assert rates["input"] == 0.4
    assert rates["output"] == 1.6

    rates = common.opportunity_rates("openai-codex/gpt-5.4-mini")
    assert rates["input"] == 0.75
    assert rates["output"] == 4.5

    assert common.opportunity_rates("ollama/gemma4:31b") is None


def test_provider_gpu_watt_defaults(common):
    assert common.provider_gpu_watts("ollama") == 34.2
    assert common.provider_gpu_watts("olla-local") == 208.0
    assert common.provider_gpu_watts("olla-cloud") is None


def test_frontmatter_parsing(common):
    meta, body = common.split_frontmatter(
        "---\n"
        "id: review\n"
        "writeAccess: false\n"
        "preferred:\n"
        "  - a/b\n"
        "  - c/d\n"
        "tags: [x, y]\n"
        "---\n"
        "Body text.\n"
    )
    assert meta["id"] == "review"
    assert meta["writeAccess"] is False
    assert meta["preferred"] == ["a/b", "c/d"]
    assert meta["tags"] == ["x", "y"]
    assert body.strip() == "Body text."

    meta, body = common.split_frontmatter("No frontmatter here.\n")
    assert meta == {}
