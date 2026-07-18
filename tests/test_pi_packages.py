from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
KEYBINDINGS = ROOT / "pi" / "agent" / "keybindings.json"


def test_native_clipboard_package_is_pinned_for_archimedes_image_paste():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    assert "npm:pi-archimedes" in settings["packages"]
    assert "npm:@mariozechner/clipboard@0.3.9" in settings["packages"]


def test_builtin_image_paste_keybinding_is_disabled_for_archimedes():
    keybindings = json.loads(KEYBINDINGS.read_text(encoding="utf-8"))

    assert keybindings["app.clipboard.pasteImage"] == []
