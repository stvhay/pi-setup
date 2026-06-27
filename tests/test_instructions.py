"""agent-instructions: family overlays apply across venues."""

from pathlib import Path


def test_model_candidates_include_family_overlay_first(instructions):
    for target in (
        "ollama/gemma4:31b",
        "openrouter-localish/google/gemma-4-31b-it",
        "olla-local/gemma4:31b",
    ):
        candidates = instructions.model_candidates(target)
        assert candidates[0] == Path("gemma4-31b.md"), target


def test_unknown_target_still_gets_venue_chain(instructions):
    candidates = instructions.model_candidates("someprovider/somemodel")
    assert Path("someprovider.md") in candidates
    assert Path("someprovider/somemodel.md") in candidates


def test_family_overlay_resolves_for_all_venues(instructions, tmp_path):
    root = tmp_path / "AGENTS.md"
    root.write_text("# Root\n", encoding="utf-8")
    models_dir = tmp_path / "AGENTS.d" / "models"
    models_dir.mkdir(parents=True)
    overlay = models_dir / "gemma4-31b.md"
    overlay.write_text("Family overlay content.\n", encoding="utf-8")

    local = instructions.existing_model_files(root, "ollama/gemma4:31b")
    openrouter = instructions.existing_model_files(
        root, "openrouter-localish/google/gemma-4-31b-it"
    )
    assert overlay in local
    assert overlay in openrouter


def test_venue_specific_file_refines_family_overlay(instructions, tmp_path):
    root = tmp_path / "AGENTS.md"
    root.write_text("# Root\n", encoding="utf-8")
    models_dir = tmp_path / "AGENTS.d" / "models"
    (models_dir / "ollama").mkdir(parents=True)
    family = models_dir / "gemma4-31b.md"
    family.write_text("family\n", encoding="utf-8")
    venue = models_dir / "ollama" / "gemma4:31b.md"
    venue.write_text("venue\n", encoding="utf-8")

    files = instructions.existing_model_files(root, "ollama/gemma4:31b")
    assert files.index(family) < files.index(venue)
