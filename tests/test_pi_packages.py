from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
KEYBINDINGS = ROOT / "pi" / "agent" / "keybindings.json"
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


def test_architecture_skill_package_is_pinned_and_filtered_to_dependencies():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert ARCHITECTURE_SKILL_PACKAGE in settings["packages"]


def test_native_clipboard_package_is_pinned_for_archimedes_image_paste():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert "npm:pi-archimedes" in settings["packages"]
    assert "npm:@mariozechner/clipboard@0.3.9" in settings["packages"]


def test_builtin_image_paste_keybinding_is_disabled_for_archimedes():
    keybindings = json.loads(KEYBINDINGS.read_text(encoding="utf-8"))

    assert keybindings["app.clipboard.pasteImage"] == []
