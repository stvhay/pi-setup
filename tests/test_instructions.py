"""agent-instructions: family overlays precede venue refinements."""

from pathlib import Path


def test_model_candidates_include_family_overlay_first(instructions):
    candidates = instructions.model_candidates("openai-codex/gpt-5.6-sol")
    assert candidates[0] == Path("gpt-5.6-sol.md")


def test_unknown_target_still_gets_venue_chain(instructions):
    candidates = instructions.model_candidates("someprovider/somemodel")
    assert Path("someprovider.md") in candidates
    assert Path("someprovider/somemodel.md") in candidates


def test_family_overlay_resolves_for_configured_venue(instructions, tmp_path):
    root = tmp_path / "AGENTS.md"
    root.write_text("# Root\n", encoding="utf-8")
    models_dir = tmp_path / "AGENTS.d" / "models"
    models_dir.mkdir(parents=True)
    overlay = models_dir / "gpt-5.6-sol.md"
    overlay.write_text("Family overlay content.\n", encoding="utf-8")

    assert overlay in instructions.existing_model_files(root, "openai-codex/gpt-5.6-sol")


def test_venue_specific_file_refines_family_overlay(instructions, tmp_path):
    root = tmp_path / "AGENTS.md"
    root.write_text("# Root\n", encoding="utf-8")
    models_dir = tmp_path / "AGENTS.d" / "models"
    (models_dir / "openai-codex").mkdir(parents=True)
    family = models_dir / "gpt-5.6-sol.md"
    family.write_text("family\n", encoding="utf-8")
    venue = models_dir / "openai-codex" / "gpt-5.6-sol.md"
    venue.write_text("venue\n", encoding="utf-8")

    files = instructions.existing_model_files(root, "openai-codex/gpt-5.6-sol")
    assert files.index(family) < files.index(venue)
