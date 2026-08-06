"""Catalog lookups: model-family facts stay data-driven."""


def test_family_resolution_for_active_venues(common):
    assert common.family_for_target("openai-codex/gpt-5.6-sol") == "gpt-5.6-sol"
    assert common.family_for_target("openrouter/minimax/minimax-m3") == "minimax-m3"
    assert common.family_for_target("openrouter/moonshotai/kimi-k3") == "kimi-k3"
    assert common.family_for_target("unknown/model") is None


def test_catalog_opportunity_rates(common):
    rates = common.opportunity_rates("openai-codex/gpt-5.6-luna")
    assert rates["input"] == 0.75
    assert rates["output"] == 4.5

    rates = common.opportunity_rates("openrouter/minimax/minimax-m3")
    assert rates["input"] == 0.3
    assert rates["cacheRead"] == 0.06

    rates = common.opportunity_rates("openrouter/moonshotai/kimi-k2.7-code")
    assert rates["input"] == 0.73
    assert rates["output"] == 3.5

    rates = common.opportunity_rates("openrouter/moonshotai/kimi-k3")
    assert rates["input"] == 3.0
    assert rates["output"] == 15.0


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
